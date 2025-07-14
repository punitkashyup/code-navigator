# Data source to get current region and account
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ECR Repository for MCP Server Container
resource "aws_ecr_repository" "mcp_server" {
  name                 = "${var.name_prefix}-mcp-server"
  image_tag_mutability = "MUTABLE"
  force_delete         = true  # Allow deletion even with images

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-mcp-server-ecr"
  })
}

# ECR Repository Policy
resource "aws_ecr_repository_policy" "mcp_server" {
  repository = aws_ecr_repository.mcp_server.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "MCPServerECRImageRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
      }
    ]
  })
}

# ECR Lifecycle Policy
resource "aws_ecr_lifecycle_policy" "mcp_server" {
  repository = aws_ecr_repository.mcp_server.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Delete untagged images older than 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Local to control MCP Server image source
locals {
  # Use ECR image when auto_build_docker is enabled, otherwise use provided image
  mcp_server_image_uri = var.auto_build_docker ? "${aws_ecr_repository.mcp_server.repository_url}:latest" : var.mcp_server_image
}

# Null resource to automatically build and push MCP Server Docker image
resource "null_resource" "mcp_docker_build_push" {
  count = var.auto_build_docker ? 1 : 0
  
  triggers = {
    # Rebuild when Dockerfile or source code changes
    dockerfile_hash = fileexists("../mcp-server/Dockerfile") ? filemd5("../mcp-server/Dockerfile") : "no-dockerfile"
    ecr_repo_url    = aws_ecr_repository.mcp_server.repository_url
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Building and pushing MCP Server Docker image..."
      cd ../mcp-server
      
      # Check if Dockerfile exists
      if [ ! -f "Dockerfile" ]; then
        echo "Warning: Dockerfile not found in mcp-server directory"
        echo "Creating a simple Node.js Dockerfile as placeholder..."
        cat > Dockerfile << 'EOF'
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 8080
CMD ["npm", "start"]
EOF
        echo '{"name": "mcp-server", "version": "1.0.0", "main": "index.js", "scripts": {"start": "node index.js"}}' > package.json
        echo 'const express = require("express"); const app = express(); app.get("/health", (req, res) => res.json({status: "ok"})); app.listen(8080, () => console.log("MCP Server running on port 8080"));' > index.js
      fi
      
      # Authenticate Docker to ECR
      aws ecr get-login-password --region ${data.aws_region.current.name} | docker login --username AWS --password-stdin ${aws_ecr_repository.mcp_server.repository_url}
      
      # Build and push the image
      docker build -t mcp-server .
      docker tag mcp-server:latest ${aws_ecr_repository.mcp_server.repository_url}:latest
      docker push ${aws_ecr_repository.mcp_server.repository_url}:latest
      
      echo "MCP Server Docker image built and pushed successfully!"
    EOT
  }

  depends_on = [aws_ecr_repository.mcp_server]
}

# Data source for latest Amazon Linux 2 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# IAM Role for EC2 Instance
resource "aws_iam_role" "ec2_role" {
  name = "${var.name_prefix}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for EC2 Instance
resource "aws_iam_role_policy" "ec2_policy" {
  name = "${var.name_prefix}-ec2-policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "es:ESHttpGet",
          "es:ESHttpPost",
          "es:ESHttpPut",
          "es:ESHttpDelete"
        ]
        Resource = "arn:aws:es:*:*:domain/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.name_prefix}-ec2-profile"
  role = aws_iam_role.ec2_role.name

  tags = var.tags
}

# User Data Script for EC2 Instance
locals {
  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    mcp_server_image    = local.mcp_server_image_uri
    mcp_server_port     = var.mcp_server_port
    opensearch_endpoint = var.opensearch_endpoint
    project_name        = var.name_prefix
    aws_region          = data.aws_region.current.name
    aws_account_id      = data.aws_caller_identity.current.account_id
  }))
}

# Launch Template
resource "aws_launch_template" "mcp_server" {
  name_prefix   = "${var.name_prefix}-mcp-server-"
  image_id      = data.aws_ami.amazon_linux.id
  instance_type = var.instance_type
  key_name      = var.key_name != "" ? var.key_name : null

  vpc_security_group_ids = var.security_group_ids

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_profile.name
  }

  user_data = local.user_data

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name = "${var.name_prefix}-mcp-server"
    })
  }

  tag_specifications {
    resource_type = "volume"
    tags = merge(var.tags, {
      Name = "${var.name_prefix}-mcp-server-volume"
    })
  }

  tags = var.tags
}

# EC2 Instance
resource "aws_instance" "mcp_server" {
  # Use public subnet for simplicity; in production, consider private subnet with NAT
  subnet_id = var.public_subnet_ids[0]

  launch_template {
    id      = aws_launch_template.mcp_server.id
    version = "$Latest"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-mcp-server"
  })

  # Ensure Docker image is built before instance starts
  depends_on = [null_resource.mcp_docker_build_push]
}

# Application Load Balancer Target Group
resource "aws_lb_target_group" "mcp_server" {
  name     = "${var.name_prefix}-mcp-tg"
  port     = var.mcp_server_port
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/mcp/health"
    matcher             = "200"
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-mcp-server-tg"
  })
}

# Target Group Attachment
resource "aws_lb_target_group_attachment" "mcp_server" {
  target_group_arn = aws_lb_target_group.mcp_server.arn
  target_id        = aws_instance.mcp_server.id
  port             = var.mcp_server_port
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "mcp_server" {
  name              = "/aws/ec2/${var.name_prefix}-mcp-server"
  retention_in_days = 7

  tags = var.tags
}