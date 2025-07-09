# GitHub Webhook Code Processor

A webhook handler that automatically processes GitHub repository changes, extracts code, generates embeddings, and indexes them in OpenSearch for semantic search. Supports both **Docker (local)** and **AWS Lambda** deployment.

## 🎯 Features

- **GitHub Webhook Integration** - Automatically processes push events
- **Code Processing** - Intelligent code chunking and analysis
- **AI-Powered Embeddings** - Uses AWS Bedrock for semantic understanding
- **OpenSearch Indexing** - Stores processed code for fast semantic search
- **Dual Deployment** - Run locally with Docker or deploy to AWS Lambda
- **Signature Verification** - Secure webhook validation
- **Real-time Processing** - Immediate code indexing on repository changes

## 📋 Quick Start

### Prerequisites

- **For Docker (Local Deployment & Lambda Deployment Process)**: Docker & Docker Compose (Docker is needed to build the image for Lambda)
- **For Lambda**: AWS CLI configured with appropriate permissions
- **For Both**: GitHub repository with webhook access

### 1. Environment Setup

```bash
# Clone/navigate to the project
cd webhook-solution

# Create environment file
cp env.example .env

# Edit .env with your actual values
nano .env
```

Required environment variables:
```env
# OpenSearch Configuration
OPENSEARCH_URL=http://opensearch:9200  # For Docker, or https://your-domain.aws.com for Lambda
OPENSEARCH_ADMIN_PW=your_opensearch_password
OPENSEARCH_USER=admin
OPENSEARCH_INDEX=ingested_code_index

# AWS Configuration (for Bedrock AI)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0

# GitHub Configuration
GITHUB_WEBHOOK_SECRET=your_secure_webhook_secret
GITHUB_TOKEN=your_github_token

# Processing Configuration
CHUNKER_MAX_CHARS=1500
CHUNKER_COALESCE=200
GENERATE_AI_DESCRIPTIONS=True
```

## 🐳 Option A: Docker Deployment (Local)

### Quick Start
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f webhook-server
```

### Set up Tunnel (for GitHub webhooks)
```bash
# In a new terminal - install ngrok first
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### Configure GitHub Webhook
1. Go to your GitHub repo → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**: `https://your-ngrok-url.ngrok.io/webhook`
3. **Content type**: `application/json`
4. **Secret**: Same value as `GITHUB_WEBHOOK_SECRET` in `.env`
5. **Events**: Just the push event ✅
6. **Active**: ✅

### Test Docker Setup
```bash
# Health check
curl https://your-ngrok-url.ngrok.io/health

# Should return: {"status": "healthy", "version": "1.0.0"}

# Make a commit and push to test webhook
```

### Docker Management
```bash
# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up --build

# View logs
docker-compose logs webhook-server

# Access OpenSearch
curl -u admin:your_password http://localhost:9200/_cluster/health
```

## ☁️ Option B: AWS Lambda Deployment

This method packages the webhook handler as a Docker container, pushes it to AWS ECR, and then deploys it as a Lambda function using AWS CloudFormation. The process is orchestrated by the `deploy-docker.sh` script.

### Quick Start
```bash
# Ensure Docker is running
# Deploy to AWS (builds Docker image, pushes to ECR, deploys Lambda via CloudFormation)
./deploy-docker.sh [image_tag] # Optionally provide an image tag, e.g., v1.0
```

The `deploy-docker.sh` script will:
- ✅ Build a Docker image of the webhook handler using the `Dockerfile`.
- ✅ Push the Docker image to AWS Elastic Container Registry (ECR).
- ✅ Create/Update the Lambda function and API Gateway via AWS CloudFormation (`lambda-cloudformation.yaml`).
- ✅ Configure IAM roles with necessary permissions.
- ✅ Set Lambda environment variables (fetched from `.env` or defaults in the script).
- ✅ Provide the API Gateway webhook URL as output.

### Configure GitHub Webhook
1. Use the API Gateway URL from deployment output
2. **Payload URL**: `https://your-api-gateway-id.execute-api.us-east-1.amazonaws.com/prod/webhook`
3. **Content type**: `application/json`
4. **Secret**: Same value as `GITHUB_WEBHOOK_SECRET` in `.env`
5. **Events**: Just the push event ✅

### Test Lambda Setup
```bash
# Health check
curl https://your-api-gateway-url.amazonaws.com/prod/health

# Should return: {"status": "healthy", "version": "1.0.0", "lambda": true}
```

### Lambda Management
```bash
# View logs for the Lambda function (replace with your function name if different)
aws logs tail /aws/lambda/github-webhook-server --follow

# Update function (after code changes)
# Re-run the deployment script. It will build a new Docker image and update the Lambda.
./deploy-docker.sh [new_image_tag]

# Delete function and all AWS resources
# This typically involves deleting the CloudFormation stack named 'code-navigator-lambda'
# and potentially the ECR repository if no longer needed.
# The cleanup-aws.sh script can assist with this.
./cleanup-aws.sh
```

## 🔧 OpenSearch Setup

### AWS OpenSearch

```bash
# Deploy OpenSearch cluster on AWS
./deploy-opensearch.sh

# Update OPENSEARCH_URL in .env to the AWS domain
```

## 📊 Monitoring & Debugging

### Docker Monitoring
```bash
# Real-time logs
docker-compose logs -f webhook-server

# Container status
docker-compose ps

# Test webhook directly
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{"repository":{"clone_url":"https://github.com/user/repo.git","full_name":"user/repo"},"ref":"refs/heads/main","after":"abc123","commits":[{"added":["test.py"],"modified":[],"removed":[]}]}'
```

### Lambda Monitoring
```bash
# Real-time logs
aws logs tail /aws/lambda/github-webhook-processor --follow

# Function status
aws lambda get-function --function-name github-webhook-processor

# Test webhook
curl -X POST https://your-api-url.amazonaws.com/prod/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{"repository":{"clone_url":"https://github.com/user/repo.git","full_name":"user/repo"},"ref":"refs/heads/main","after":"abc123","commits":[{"added":["test.py"],"modified":[],"removed":[]}]}'
```

## 🏗️ Architecture

### Docker Architecture
```
GitHub Push → Webhook → ngrok → Docker Container → simple_webhook_server.py → OpenSearch
```

### Lambda Architecture
```
GitHub Push → Webhook → API Gateway → Lambda → lambda_webhook_handler.py → OpenSearch
```

### Core Components
- **`simple_webhook_server.py`** - Docker webhook server (no FastAPI)
- **`lambda_webhook_handler.py`** - AWS Lambda handler
- **`lambda_code_updater.py`** - Core processing logic (shared)
- **`opensearch_ops.py`** - OpenSearch operations (shared)
- **`src/code_splitter/`** - Code analysis and chunking (shared)

## 🔒 Security

### GitHub Webhook Security
- **Signature Verification**: Uses HMAC-SHA256 with your secret
- **Event Filtering**: Only processes 'push' events
- **HTTPS Only**: All webhook URLs use HTTPS

### AWS Security
- **IAM Roles**: Minimal required permissions
- **VPC Support**: OpenSearch can be in private VPC
- **Secrets Manager**: Can store sensitive environment variables

## 🔧 Troubleshooting

### Common Issues

1. **Webhook 401 Unauthorized**
   ```bash
   # Check secret matches
   echo $GITHUB_WEBHOOK_SECRET
   # Verify in GitHub webhook settings
   ```

2. **OpenSearch Connection Failed**
   ```bash
   # For Docker
   docker-compose logs opensearch
   curl -u admin:password http://localhost:9200
   
   # For AWS
   # Check VPC settings and access policies
   ```

3. **Import Errors**
   ```bash
   # For Docker
   docker-compose logs webhook-server
   
   # For Lambda
   aws logs tail /aws/lambda/github-webhook-processor
   ```

4. **Memory/Timeout Issues (Lambda)**
   ```bash
   # Increase Lambda resources
   aws lambda update-function-configuration \
     --function-name github-webhook-processor \
     --memory-size 1024 \
     --timeout 600
   ```

## 📁 File Structure

```
webhook-solution/
├── README.md                    # This comprehensive guide
├── env.example                  # Environment variables template
├── requirements.txt             # Python dependencies (works for both Docker & Lambda)
├── docker-compose.yml           # Docker services configuration
├── Dockerfile                   # Docker image definition
├── deploy-docker.sh            # AWS Lambda deployment script
├── deploy-opensearch.sh        # AWS OpenSearch deployment script
├── cleanup-aws.sh              # AWS resources cleanup script
├── simple_webhook_server.py    # Docker webhook server (no FastAPI)
├── lambda_webhook_handler.py   # AWS Lambda handler
├── lambda_code_updater.py      # Core processing logic (shared)
├── opensearch_ops.py           # OpenSearch operations (shared)
└── src/code_splitter/          # Code analysis and chunking
    ├── processor.py            # Main code processing
    ├── splitter.py             # Code splitting logic
    ├── language_config.py      # Language-specific configurations
    └── ...                     # Other processing modules
```

## 🔄 Updates & Maintenance

### Update Docker
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose up --build -d
```

### Update Lambda
```bash
# Deploy updates
./deploy-docker.sh

# Or update specific components
aws lambda update-function-code \
  --function-name github-webhook-processor \
  --zip-file fileb://lambda-package.zip
```

### Update Environment Variables
```bash
# Edit .env file
nano .env

# For Docker: restart services
docker-compose up -d

# For Lambda: redeploy
./deploy-docker.sh
```

## 📞 Support

### Debug Commands
```bash
# Test code processing locally
python lambda_code_updater.py

# Test OpenSearch connection
python -c "from opensearch_ops import get_opensearch_client; print(get_opensearch_client().info())"

# Validate environment
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Loaded:', len([k for k in os.environ.keys() if k.startswith(('OPENSEARCH_', 'AWS_', 'GITHUB_'))]))"
```

### Log Locations
- **Docker**: `docker-compose logs webhook-server`
- **Lambda**: AWS CloudWatch `/aws/lambda/github-webhook-processor`
- **Local**: Console output when running Python scripts directly
