variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
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

variable "opensearch_endpoint" {
  description = "OpenSearch endpoint URL"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "auto_build_docker" {
  description = "Whether to automatically build and push MCP Server Docker image during deployment"
  type        = bool
  default     = false
}

# MCP Server Environment Variables
variable "opensearch_master_user" {
  description = "OpenSearch master user"
  type        = string
  default     = "admin"
}

variable "opensearch_master_password" {
  description = "OpenSearch master password"
  type        = string
  sensitive   = true
}

variable "github_token" {
  description = "GitHub personal access token"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}