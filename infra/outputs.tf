# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnet_ids
}

# EC2 Outputs
output "ec2_instance_id" {
  description = "ID of the EC2 instance"
  value       = module.ec2.instance_id
}

output "ec2_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = module.ec2.public_ip
}

output "ec2_private_ip" {
  description = "Private IP of the EC2 instance"
  value       = module.ec2.private_ip
}

# Load Balancer Outputs
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.alb.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = module.alb.zone_id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = module.alb.arn
}

# Lambda Outputs
output "webhook_function_name" {
  description = "Name of the webhook Lambda function"
  value       = module.lambda.webhook_function_name
}

output "webhook_function_arn" {
  description = "ARN of the webhook Lambda function"
  value       = module.lambda.webhook_function_arn
}

output "webhook_api_gateway_url" {
  description = "API Gateway URL for webhook"
  value       = module.lambda.api_gateway_url
}

output "webhook_endpoint" {
  description = "Complete webhook endpoint URL"
  value       = module.lambda.webhook_endpoint
}

# ECR Outputs
output "ecr_repository_url" {
  description = "URL of the ECR repository for Lambda container"
  value       = module.lambda.ecr_repository_url
}

output "ecr_repository_name" {
  description = "Name of the ECR repository"
  value       = module.lambda.ecr_repository_name
}

output "mcp_ecr_repository_url" {
  description = "URL of the ECR repository for MCP Server container"
  value       = module.ec2.mcp_ecr_repository_url
}

output "mcp_ecr_repository_name" {
  description = "Name of the MCP Server ECR repository"
  value       = module.ec2.mcp_ecr_repository_name
}

# OpenSearch Outputs
output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = module.opensearch.endpoint
}

output "opensearch_kibana_endpoint" {
  description = "OpenSearch Kibana endpoint"
  value       = module.opensearch.kibana_endpoint
}

output "opensearch_arn" {
  description = "ARN of the OpenSearch domain"
  value       = module.opensearch.arn
}

# GuardDuty Outputs
output "guardduty_detector_id" {
  description = "ID of the GuardDuty detector"
  value       = module.guardduty.detector_id
}

# Security Group Outputs
output "security_group_ids" {
  description = "Map of security group IDs"
  value = {
    ec2        = module.security.ec2_security_group_id
    alb        = module.security.alb_security_group_id
    lambda     = module.security.lambda_security_group_id
    opensearch = module.security.opensearch_security_group_id
  }
}

# AWS Region Output
output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = data.aws_region.current.name
}