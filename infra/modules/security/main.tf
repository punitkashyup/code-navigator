# Security Group for Application Load Balancer
resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = var.vpc_id

  # HTTP
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }

  # HTTPS
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb-sg"
  })
}

# Security Group for EC2 Instance (MCP Server)
resource "aws_security_group" "ec2" {
  name        = "${var.name_prefix}-ec2-sg"
  description = "Security group for EC2 instance hosting MCP server"
  vpc_id      = var.vpc_id

  # SSH access (restrict to specific IP ranges in production)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Should be restricted in production
    description = "SSH"
  }

  # MCP Server port from ALB (includes health checks)
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "MCP Server and health check from ALB"
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-ec2-sg"
  })
}

# Security Group for Lambda Function
resource "aws_security_group" "lambda" {
  name        = "${var.name_prefix}-lambda-sg"
  description = "Security group for Lambda function"
  vpc_id      = var.vpc_id

  # All outbound traffic (Lambda needs to access OpenSearch, GitHub, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-lambda-sg"
  })
}

# Security Group for OpenSearch
resource "aws_security_group" "opensearch" {
  name        = "${var.name_prefix}-opensearch-sg"
  description = "Security group for OpenSearch cluster"
  vpc_id      = var.vpc_id

  # HTTPS access from Lambda
  ingress {
    from_port                = 443
    to_port                  = 443
    protocol                 = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description              = "HTTPS from Lambda"
  }

  # HTTPS access from EC2
  ingress {
    from_port                = 443
    to_port                  = 443
    protocol                 = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description              = "HTTPS from EC2"
  }

  # OpenSearch port from Lambda
  ingress {
    from_port                = 9200
    to_port                  = 9200
    protocol                 = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description              = "OpenSearch from Lambda"
  }

  # OpenSearch port from EC2
  ingress {
    from_port                = 9200
    to_port                  = 9200
    protocol                 = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description              = "OpenSearch from EC2"
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-opensearch-sg"
  })
}

# Security Group for RDS (if needed in the future)
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  description = "Security group for RDS database"
  vpc_id      = var.vpc_id

  # MySQL/Aurora access from EC2
  ingress {
    from_port                = 3306
    to_port                  = 3306
    protocol                 = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description              = "MySQL from EC2"
  }

  # MySQL/Aurora access from Lambda
  ingress {
    from_port                = 3306
    to_port                  = 3306
    protocol                 = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description              = "MySQL from Lambda"
  }

  # PostgreSQL access from EC2
  ingress {
    from_port                = 5432
    to_port                  = 5432
    protocol                 = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description              = "PostgreSQL from EC2"
  }

  # PostgreSQL access from Lambda
  ingress {
    from_port                = 5432
    to_port                  = 5432
    protocol                 = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description              = "PostgreSQL from Lambda"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-rds-sg"
  })
}