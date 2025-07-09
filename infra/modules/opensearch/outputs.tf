output "endpoint" {
  description = "OpenSearch domain endpoint"
  value       = aws_opensearch_domain.main.endpoint
}

output "kibana_endpoint" {
  description = "OpenSearch Kibana endpoint"
  value       = local.kibana_endpoint
}

output "arn" {
  description = "ARN of the OpenSearch domain"
  value       = aws_opensearch_domain.main.arn
}

output "domain_id" {
  description = "ID of the OpenSearch domain"
  value       = aws_opensearch_domain.main.domain_id
}

output "domain_name" {
  description = "Name of the OpenSearch domain"
  value       = aws_opensearch_domain.main.domain_name
}

output "vpc_options" {
  description = "VPC options for the OpenSearch domain"
  value       = aws_opensearch_domain.main.vpc_options
}

output "cluster_config" {
  description = "Cluster configuration for the OpenSearch domain"
  value       = aws_opensearch_domain.main.cluster_config
}

output "log_group_names" {
  description = "Names of the CloudWatch log groups"
  value = {
    index_slow    = aws_cloudwatch_log_group.opensearch_index_slow.name
    search_slow   = aws_cloudwatch_log_group.opensearch_search_slow.name
    application   = aws_cloudwatch_log_group.opensearch_application.name
  }
}

output "master_user" {
  description = "OpenSearch master username"
  value       = var.master_user
}

# Note: We don't output the master password for security reasons
output "connection_string" {
  description = "Connection string for OpenSearch"
  value       = "https://${var.master_user}:${var.master_password}@${aws_opensearch_domain.main.endpoint}"
  sensitive   = true
}