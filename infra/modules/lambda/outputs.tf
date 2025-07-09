output "webhook_function_name" {
  description = "Name of the webhook Lambda function"
  value       = aws_lambda_function.webhook.function_name
}

output "webhook_function_arn" {
  description = "ARN of the webhook Lambda function"
  value       = aws_lambda_function.webhook.arn
}

output "webhook_invoke_arn" {
  description = "Invoke ARN of the webhook Lambda function"
  value       = aws_lambda_function.webhook.invoke_arn
}

output "api_gateway_url" {
  description = "API Gateway URL for webhook"
  value       = "https://${aws_api_gateway_rest_api.webhook.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/prod"
}

output "webhook_endpoint" {
  description = "Complete webhook endpoint URL"
  value       = "https://${aws_api_gateway_rest_api.webhook.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/prod/webhook"
}

output "health_endpoint" {
  description = "Complete health check endpoint URL"
  value       = "https://${aws_api_gateway_rest_api.webhook.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/prod/health"
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_api_gateway_rest_api.webhook.id
}

output "lambda_role_arn" {
  description = "ARN of the Lambda IAM role"
  value       = aws_iam_role.lambda_role.arn
}

output "log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

# ECR Outputs
output "ecr_repository_url" {
  description = "URL of the ECR repository for Lambda container"
  value       = aws_ecr_repository.lambda_webhook.repository_url
}

output "ecr_repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.lambda_webhook.name
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.lambda_webhook.arn
}