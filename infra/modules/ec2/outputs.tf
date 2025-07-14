output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.mcp_server.id
}

output "public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_instance.mcp_server.public_ip
}

output "private_ip" {
  description = "Private IP of the EC2 instance"
  value       = aws_instance.mcp_server.private_ip
}

output "instance_arn" {
  description = "ARN of the EC2 instance"
  value       = aws_instance.mcp_server.arn
}

output "target_group_arn" {
  description = "ARN of the target group"
  value       = aws_lb_target_group.mcp_server.arn
}

output "launch_template_id" {
  description = "ID of the launch template"
  value       = aws_launch_template.mcp_server.id
}

output "iam_role_arn" {
  description = "ARN of the IAM role"
  value       = aws_iam_role.ec2_role.arn
}

output "log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.mcp_server.name
}

# MCP Server ECR Outputs
output "mcp_ecr_repository_url" {
  description = "URL of the ECR repository for MCP Server container"
  value       = aws_ecr_repository.mcp_server.repository_url
}

output "mcp_ecr_repository_name" {
  description = "Name of the MCP Server ECR repository"
  value       = aws_ecr_repository.mcp_server.name
}

output "mcp_ecr_repository_arn" {
  description = "ARN of the MCP Server ECR repository"
  value       = aws_ecr_repository.mcp_server.arn
}