# Data sources
data "aws_caller_identity" "current" {}

# GuardDuty Detector
# Use data source instead of resource to reference existing detector
data "aws_guardduty_detector" "main" {
}

# GuardDuty IPSet for trusted IPs (optional)
resource "aws_guardduty_ipset" "trusted_ips" {
  count = length(var.trusted_ip_list) > 0 ? 1 : 0

  activate    = true
  detector_id = data.aws_guardduty_detector.main.id
  format      = "TXT"
  location    = aws_s3_object.trusted_ips[0].bucket
  name        = "${var.name_prefix}-trusted-ips"

  depends_on = [aws_s3_object.trusted_ips]

  tags = var.tags
}

# S3 Bucket for GuardDuty assets
resource "aws_s3_bucket" "guardduty" {
  count = length(var.trusted_ip_list) > 0 || length(var.threat_intel_list) > 0 ? 1 : 0

  bucket = "${var.name_prefix}-guardduty-${random_string.bucket_suffix.result}"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-guardduty-bucket"
  })
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# S3 Bucket public access block
resource "aws_s3_bucket_public_access_block" "guardduty" {
  count = length(var.trusted_ip_list) > 0 || length(var.threat_intel_list) > 0 ? 1 : 0

  bucket = aws_s3_bucket.guardduty[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket versioning
resource "aws_s3_bucket_versioning" "guardduty" {
  count = length(var.trusted_ip_list) > 0 || length(var.threat_intel_list) > 0 ? 1 : 0

  bucket = aws_s3_bucket.guardduty[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Object for trusted IPs
resource "aws_s3_object" "trusted_ips" {
  count = length(var.trusted_ip_list) > 0 ? 1 : 0

  bucket  = aws_s3_bucket.guardduty[0].bucket
  key     = "trusted-ips.txt"
  content = join("\n", var.trusted_ip_list)

  tags = var.tags
}

# GuardDuty ThreatIntelSet for known malicious IPs (optional)
resource "aws_guardduty_threatintelset" "threat_intel" {
  count = length(var.threat_intel_list) > 0 ? 1 : 0

  activate    = true
  detector_id = data.aws_guardduty_detector.main.id
  format      = "TXT"
  location    = aws_s3_object.threat_intel[0].bucket
  name        = "${var.name_prefix}-threat-intel"

  depends_on = [aws_s3_object.threat_intel]

  tags = var.tags
}

# S3 Object for threat intelligence
resource "aws_s3_object" "threat_intel" {
  count = length(var.threat_intel_list) > 0 ? 1 : 0

  bucket  = aws_s3_bucket.guardduty[0].bucket
  key     = "threat-intel.txt"
  content = join("\n", var.threat_intel_list)

  tags = var.tags
}

# CloudWatch Event Rule for GuardDuty findings
resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  name        = "${var.name_prefix}-guardduty-findings"
  description = "Capture GuardDuty findings"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
  })

  tags = var.tags
}

# CloudWatch Log Group for GuardDuty findings
resource "aws_cloudwatch_log_group" "guardduty_findings" {
  name              = "/aws/guardduty/${var.name_prefix}"
  retention_in_days = 30

  tags = var.tags
}

# CloudWatch Event Target (Log Group)
resource "aws_cloudwatch_event_target" "guardduty_log_target" {
  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "GuardDutyLogTarget"
  arn       = aws_cloudwatch_log_group.guardduty_findings.arn
}

# CloudWatch Metric Filter for High Severity Findings
resource "aws_cloudwatch_log_metric_filter" "high_severity_findings" {
  name           = "${var.name_prefix}-guardduty-high-severity"
  log_group_name = aws_cloudwatch_log_group.guardduty_findings.name
  pattern        = "{ $.detail.severity >= 7.0 }"

  metric_transformation {
    name      = "GuardDutyHighSeverityFindings"
    namespace = "GuardDuty/Findings"
    value     = "1"
  }
}

# CloudWatch Alarm for High Severity Findings
resource "aws_cloudwatch_metric_alarm" "high_severity_findings" {
  alarm_name          = "${var.name_prefix}-guardduty-high-severity-findings"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "GuardDutyHighSeverityFindings"
  namespace           = "GuardDuty/Findings"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors high severity GuardDuty findings"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  tags = var.tags
}

# CloudWatch Metric Filter for Medium Severity Findings
resource "aws_cloudwatch_log_metric_filter" "medium_severity_findings" {
  name           = "${var.name_prefix}-guardduty-medium-severity"
  log_group_name = aws_cloudwatch_log_group.guardduty_findings.name
  pattern        = "{ ($.detail.severity >= 4.0) && ($.detail.severity < 7.0) }"

  metric_transformation {
    name      = "GuardDutyMediumSeverityFindings"
    namespace = "GuardDuty/Findings"
    value     = "1"
  }
}

# GuardDuty Filter for excluding known false positives
# Disabled due to organization restrictions
# resource "aws_guardduty_filter" "exclude_false_positives" {
#   detector_id = data.aws_guardduty_detector.main.id
#   name        = "${var.name_prefix}-exclude-false-positives"
#   action      = "ARCHIVE"
#   rank        = 1

#   finding_criteria {
#     criterion {
#       field  = "type"
#       equals = [
#         "Recon:EC2/PortProbeUnprotectedPort",
#         "Recon:EC2/Portscan"
#       ]
#     }
#   }

#   tags = var.tags
# }

# GuardDuty Member Accounts (if applicable)
resource "aws_guardduty_member" "members" {
  for_each = var.member_accounts

  account_id                 = each.value.account_id
  detector_id               = data.aws_guardduty_detector.main.id
  email                     = each.value.email
  invite                    = true
  invitation_message        = "Please accept GuardDuty invitation for ${var.name_prefix}"
  disable_email_notification = false
}

# Organization Configuration (if using AWS Organizations)
resource "aws_guardduty_organization_configuration" "main" {
  count = var.enable_organization_configuration ? 1 : 0

  auto_enable_organization_members = "ALL"
  detector_id = data.aws_guardduty_detector.main.id

  datasources {
    s3_logs {
      auto_enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          auto_enable = true
        }
      }
    }
  }
}