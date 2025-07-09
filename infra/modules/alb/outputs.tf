output "dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

output "arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "webhook_target_group_arn" {
  description = "ARN of the webhook target group"
  value       = aws_lb_target_group.webhook.arn
}

output "certificate_arn" {
  description = "ARN of the SSL certificate (if created)"
  value       = var.domain_name != "" && var.certificate_arn == "" ? aws_acm_certificate.main[0].arn : var.certificate_arn
}

output "url" {
  description = "URL of the Application Load Balancer"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.main.dns_name}"
}

output "mcp_server_url" {
  description = "URL for MCP server endpoint"
  value       = var.domain_name != "" ? "https://${var.domain_name}/mcp" : "http://${aws_lb.main.dns_name}/mcp"
}

output "webhook_url" {
  description = "URL for webhook endpoint"
  value       = var.domain_name != "" ? "https://${var.domain_name}/webhook" : "http://${aws_lb.main.dns_name}/webhook"
}