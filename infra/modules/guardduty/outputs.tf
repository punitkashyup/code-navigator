output "detector_id" {
  description = "ID of the GuardDuty detector"
  value       = data.aws_guardduty_detector.main.id
}

output "detector_arn" {
  description = "ARN of the GuardDuty detector"
  value       = data.aws_guardduty_detector.main.arn
}

output "account_id" {
  description = "AWS account ID where GuardDuty is enabled"
  value       = data.aws_caller_identity.current.account_id
}

output "log_group_name" {
  description = "Name of the CloudWatch log group for GuardDuty findings"
  value       = aws_cloudwatch_log_group.guardduty_findings.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch log group for GuardDuty findings"
  value       = aws_cloudwatch_log_group.guardduty_findings.arn
}

output "event_rule_arn" {
  description = "ARN of the CloudWatch event rule for GuardDuty findings"
  value       = aws_cloudwatch_event_rule.guardduty_findings.arn
}

output "high_severity_alarm_arn" {
  description = "ARN of the CloudWatch alarm for high severity findings"
  value       = aws_cloudwatch_metric_alarm.high_severity_findings.arn
}

output "bucket_name" {
  description = "Name of the S3 bucket for GuardDuty assets"
  value       = length(var.trusted_ip_list) > 0 || length(var.threat_intel_list) > 0 ? aws_s3_bucket.guardduty[0].bucket : null
}

output "ipset_id" {
  description = "ID of the GuardDuty IPSet (if created)"
  value       = length(var.trusted_ip_list) > 0 ? aws_guardduty_ipset.trusted_ips[0].id : null
}

output "threatintelset_id" {
  description = "ID of the GuardDuty ThreatIntelSet (if created)"
  value       = length(var.threat_intel_list) > 0 ? aws_guardduty_threatintelset.threat_intel[0].id : null
}

output "member_account_ids" {
  description = "List of member account IDs invited to GuardDuty"
  value       = [for member in aws_guardduty_member.members : member.account_id]
}