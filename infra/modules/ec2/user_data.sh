#!/bin/bash
set -e

# Update system
yum update -y

# Install Docker and netcat
yum install -y docker nc
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install CloudWatch Agent
yum install -y amazon-cloudwatch-agent

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Configure CloudWatch Agent
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/mcp-server.log",
            "log_group_name": "/aws/ec2/${project_name}-mcp-server",
            "log_stream_name": "{instance_id}/mcp-server.log"
          },
          {
            "file_path": "/var/log/docker.log",
            "log_group_name": "/aws/ec2/${project_name}-mcp-server",
            "log_stream_name": "{instance_id}/docker.log"
          }
        ]
      }
    }
  },
  "metrics": {
    "namespace": "CodeNavigator/EC2",
    "metrics_collected": {
      "cpu": {
        "measurement": [
          "cpu_usage_idle",
          "cpu_usage_iowait",
          "cpu_usage_user",
          "cpu_usage_system"
        ],
        "metrics_collection_interval": 60
      },
      "disk": {
        "measurement": [
          "used_percent"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "diskio": {
        "measurement": [
          "io_time"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "mem": {
        "measurement": [
          "mem_used_percent"
        ],
        "metrics_collection_interval": 60
      }
    }
  }
}
EOF

# Start CloudWatch Agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

# Authenticate Docker to ECR if using ECR image
if [[ "${mcp_server_image}" == *".dkr.ecr."* ]]; then
    echo "Authenticating Docker to ECR for ${mcp_server_image}..."
    # Extract ECR registry URL from image URI
    ECR_REGISTRY=$(echo "${mcp_server_image}" | cut -d'/' -f1)
    aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin $ECR_REGISTRY
    
    # Verify authentication worked by trying to pull the image
    echo "Testing ECR authentication by pulling image..."
    docker pull ${mcp_server_image} || {
        echo "Failed to pull image from ECR. Retrying authentication..."
        sleep 5
        aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin $ECR_REGISTRY
        docker pull ${mcp_server_image}
    }
fi

# Create application directory
mkdir -p /opt/mcp-server
cd /opt/mcp-server

# Create Docker Compose file
cat > docker-compose.yml << 'EOF'
services:
  mcp-server:
    image: ${mcp_server_image}
    container_name: mcp-server
    ports:
      - "${mcp_server_port}:${mcp_server_port}"
    environment:
      - OPENSEARCH_URL=https://${opensearch_endpoint}
      - OPENSEARCH_ADMIN_PW=$${OPENSEARCH_ADMIN_PW}
      - OPENSEARCH_USER=$${OPENSEARCH_USER}
      - OPENSEARCH_INDEX=$${OPENSEARCH_INDEX}
      - OPENSEARCH_TEXT_FIELD=$${OPENSEARCH_TEXT_FIELD}
      - OPENSEARCH_VECTOR_FIELD=$${OPENSEARCH_VECTOR_FIELD}
      - OPENSEARCH_BULK_SIZE=$${OPENSEARCH_BULK_SIZE}
      - BEDROCK_MODEL_ID=$${BEDROCK_MODEL_ID}
      - GITHUB_TOKEN=$${GITHUB_TOKEN}
      - OPENAI_API_KEY=$${OPENAI_API_KEY}
      - CHUNKER_MAX_CHARS=$${CHUNKER_MAX_CHARS}
      - CHUNKER_COALESCE=$${CHUNKER_COALESCE}
      - GENERATE_AI_DESCRIPTIONS=$${GENERATE_AI_DESCRIPTIONS}
      - CHUNK_DESC_PROVIDER=$${CHUNK_DESC_PROVIDER}
      - MCP_API_KEY=$${MCP_API_KEY}
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${mcp_server_port}/"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    volumes:
      - /var/log/mcp-server.log:/var/log/mcp-server.log
EOF

# Create environment file with actual values from Terraform
cat > .env << EOF
# OpenSearch Configuration
OPENSEARCH_ADMIN_PW=${opensearch_master_password}
OPENSEARCH_USER=${opensearch_master_user}
OPENSEARCH_INDEX=code_index
OPENSEARCH_TEXT_FIELD=text
OPENSEARCH_VECTOR_FIELD=vector_field
OPENSEARCH_BULK_SIZE=500

# AWS Bedrock Configuration
BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0

# GitHub Configuration
GITHUB_TOKEN=${github_token}

# OpenAI Configuration
OPENAI_API_KEY=${openai_api_key}

# Chunker Configuration
CHUNKER_MAX_CHARS=1500
CHUNKER_COALESCE=200
GENERATE_AI_DESCRIPTIONS=true
CHUNK_DESC_PROVIDER=openai

# MCP Server Configuration
MCP_API_KEY=${mcp_api_key}
EOF

# Start MCP server with Docker Compose
echo "Starting MCP server with Docker Compose..."
cd /opt/mcp-server

# Simple startup with retry
for i in {1..3}; do
    if docker-compose up -d; then
        echo "MCP server started successfully"
        break
    else
        echo "Attempt $i failed, retrying in 10 seconds..."
        sleep 10
        # Re-authenticate to ECR before retry
        if [[ "${mcp_server_image}" == *".dkr.ecr."* ]]; then
            ECR_REGISTRY=$(echo "${mcp_server_image}" | cut -d'/' -f1)
            aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin $ECR_REGISTRY
        fi
    fi
done

# Check containers are running
docker-compose ps

# Add simple startup command to rc.local for boot
echo "cd /opt/mcp-server && docker-compose up -d" >> /etc/rc.local
chmod +x /etc/rc.local

# Create log rotation for MCP server logs
cat > /etc/logrotate.d/mcp-server << 'EOF'
/var/log/mcp-server.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    postrotate
        /bin/kill -USR1 $(cat /var/run/mcp-server.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF

# Create a simple health check script
cat > /opt/mcp-server/health-check.sh << 'EOF'
#!/bin/bash
curl -f http://localhost:${mcp_server_port}/ || exit 1
EOF

chmod +x /opt/mcp-server/health-check.sh

# Signal that the instance is ready (placeholder for future ASG integration)
echo "Instance setup completed successfully"

echo "MCP Server setup completed successfully!"