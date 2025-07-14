# OpenSearch Domain
resource "aws_opensearch_domain" "main" {
  domain_name           = "${var.name_prefix}-os"
  engine_version        = "OpenSearch_2.11"

  cluster_config {
    instance_type            = var.instance_type
    instance_count           = var.instance_count
    dedicated_master_enabled = var.instance_count > 2
    zone_awareness_enabled   = var.instance_count > 1
    
    dynamic "zone_awareness_config" {
      for_each = var.instance_count > 1 ? [1] : []
      content {
        availability_zone_count = min(var.instance_count, length(var.subnet_ids))
      }
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.volume_size
    throughput  = 125
    iops        = 3000
  }

  vpc_options {
    subnet_ids         = var.instance_count > 1 ? var.subnet_ids : [var.subnet_ids[0]]
    security_group_ids = var.security_group_ids
  }

  # Enable encryption
  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  # Fine-grained access control
  advanced_security_options {
    enabled                        = true
    anonymous_auth_enabled         = false
    internal_user_database_enabled = true
    
    master_user_options {
      master_user_name     = var.master_user
      master_user_password = var.master_password
    }
  }

  # Access policy - permissive for VPC access with fine-grained access control
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action   = "es:*"
        Resource = "arn:aws:es:*:*:domain/${var.name_prefix}-os/*"
      }
    ]
  })

  # Advanced options
  advanced_options = {
    "indices.fielddata.cache.size"  = "20"
    "indices.query.bool.max_clause_count" = "1024"
  }

  # Auto-tune is not supported on t2/t3 instances
  # Only enable for production instance types
  dynamic "auto_tune_options" {
    for_each = !startswith(var.instance_type, "t2") && !startswith(var.instance_type, "t3") ? [1] : []
    content {
      desired_state       = "ENABLED"
      rollback_on_disable = "NO_ROLLBACK"
      
      maintenance_schedule {
        start_at = "2023-01-01T00:00:00Z"
        duration {
          value = "2"
          unit  = "HOURS"
        }
        cron_expression_for_recurrence = "cron(0 3 ? * SUN *)"
      }
    }
  }

  # Logging
  log_publishing_options {
    enabled                  = true
    log_type                 = "INDEX_SLOW_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_index_slow.arn
  }

  log_publishing_options {
    enabled                  = true
    log_type                 = "SEARCH_SLOW_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_search_slow.arn
  }

  log_publishing_options {
    enabled                  = true
    log_type                 = "ES_APPLICATION_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_application.arn
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-opensearch"
  })
}

# CloudWatch Log Groups for OpenSearch
resource "aws_cloudwatch_log_group" "opensearch_index_slow" {
  name              = "/aws/opensearch/domains/${var.name_prefix}-opensearch/index-slow"
  retention_in_days = 7

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "opensearch_search_slow" {
  name              = "/aws/opensearch/domains/${var.name_prefix}-opensearch/search-slow"
  retention_in_days = 7

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "opensearch_application" {
  name              = "/aws/opensearch/domains/${var.name_prefix}-opensearch/application"
  retention_in_days = 7

  tags = var.tags
}

# CloudWatch Log Resource Policy for OpenSearch
resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${var.name_prefix}-opensearch-log-policy"

  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "es.amazonaws.com"
        }
        Action = [
          "logs:PutLogEvents",
          "logs:CreateLogGroup",
          "logs:CreateLogStream"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# OpenSearch Domain Policy
resource "aws_opensearch_domain_policy" "main" {
  domain_name = aws_opensearch_domain.main.domain_name

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action = "es:*"
        Resource = "${aws_opensearch_domain.main.arn}/*"
      }
    ]
  })
}

# CloudWatch Alarms for OpenSearch
resource "aws_cloudwatch_metric_alarm" "opensearch_cluster_status" {
  alarm_name          = "${var.name_prefix}-opensearch-cluster-status"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ClusterStatus.yellow"
  namespace           = "AWS/ES"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "0"
  alarm_description   = "This metric monitors OpenSearch cluster status"
  alarm_actions       = []

  dimensions = {
    DomainName = aws_opensearch_domain.main.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "opensearch_free_storage" {
  alarm_name          = "${var.name_prefix}-opensearch-free-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "StorageUtilization"
  namespace           = "AWS/ES"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors OpenSearch free storage space"
  alarm_actions       = []

  dimensions = {
    DomainName = aws_opensearch_domain.main.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  tags = var.tags
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# OpenSearch Dashboard URL (Kibana)
locals {
  kibana_endpoint = "https://${aws_opensearch_domain.main.endpoint}/_dashboards/"
}