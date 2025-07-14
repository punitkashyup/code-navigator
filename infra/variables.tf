# Project Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "code-navigator"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnets" {
  description = "List of public subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnets" {
  description = "List of private subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.3.0/24", "10.0.4.0/24"]
}

# EC2 Configuration
variable "ec2_instance_type" {
  description = "EC2 instance type for MCP server"
  type        = string
  default     = "t3.medium"
}

variable "ec2_key_name" {
  description = "EC2 key pair name"
  type        = string
  default     = ""
}

variable "mcp_server_image" {
  description = "Docker image for MCP server"
  type        = string
  default     = "codenavigator/mcp-server:latest"
}

variable "mcp_server_port" {
  description = "Port for MCP server"
  type        = number
  default     = 8080
}

# Load Balancer Configuration
variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ARN of the SSL/TLS certificate"
  type        = string
  default     = ""
}

# OpenSearch Configuration
variable "opensearch_instance_type" {
  description = "OpenSearch instance type"
  type        = string
  default     = "t3.small.search"
}

variable "opensearch_instance_count" {
  description = "Number of OpenSearch instances"
  type        = number
  default     = 2
}

variable "opensearch_volume_size" {
  description = "EBS volume size for OpenSearch (GB)"
  type        = number
  default     = 20
}

variable "opensearch_master_user" {
  description = "OpenSearch master username"
  type        = string
  default     = "admin"
}

variable "opensearch_master_password" {
  description = "OpenSearch master password"
  type        = string
  sensitive   = true
}

# Lambda Configuration
variable "github_webhook_secret" {
  description = "GitHub webhook secret"
  type        = string
  sensitive   = true
}

variable "github_token" {
  description = "GitHub personal access token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "auto_build_docker" {
  description = "Whether to automatically build and push Docker image during deployment"
  type        = bool
  default     = false
}

variable "enable_lambda_creation" {
  description = "Whether to create the Lambda function (use false for first deployment, true after Docker image is built)"
  type        = bool
  default     = false
}