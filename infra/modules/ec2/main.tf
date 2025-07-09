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
    mcp_server_image    = var.mcp_server_image
    mcp_server_port     = var.mcp_server_port
    opensearch_endpoint = var.opensearch_endpoint
    project_name        = var.name_prefix
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
}

# Application Load Balancer Target Group
resource "aws_lb_target_group" "mcp_server" {
  name     = "${var.name_prefix}-mcp-server-tg"
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