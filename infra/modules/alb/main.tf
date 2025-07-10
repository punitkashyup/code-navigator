# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = var.security_group_ids
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb"
  })
}

# HTTP Listener - conditionally redirects to HTTPS or forwards directly
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  dynamic "default_action" {
    for_each = var.certificate_arn != "" ? [1] : []
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [1] : []
    content {
      type             = "forward"
      target_group_arn = var.mcp_server_target_group_arn
    }
  }

  tags = var.tags
}

# HTTPS Listener (only when certificate is provided)
resource "aws_lb_listener" "https" {
  count = var.certificate_arn != "" ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = var.mcp_server_target_group_arn
  }

  tags = var.tags
}

# Listener Rule for MCP Server
resource "aws_lb_listener_rule" "mcp_server" {
  count = var.certificate_arn != "" ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = var.mcp_server_target_group_arn
  }

  condition {
    path_pattern {
      values = ["/mcp/*"]
    }
  }

  tags = var.tags
}

# Listener Rule for MCP Server (HTTP)
resource "aws_lb_listener_rule" "mcp_server_http" {
  count = var.certificate_arn == "" ? 1 : 0

  listener_arn = aws_lb_listener.http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = var.mcp_server_target_group_arn
  }

  condition {
    path_pattern {
      values = ["/mcp/*"]
    }
  }

  tags = var.tags
}

# Lambda Target Group for Webhook
resource "aws_lb_target_group" "webhook" {
  name        = "${var.name_prefix}-webhook-tg"
  target_type = "lambda"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-webhook-tg"
  })
}

# Lambda Target Group Attachment
resource "aws_lb_target_group_attachment" "webhook" {
  count = var.enable_lambda_integration ? 1 : 0
  
  target_group_arn = aws_lb_target_group.webhook.arn
  target_id        = var.webhook_lambda_arn
  depends_on       = [aws_lambda_permission.alb_invoke]
}

# Lambda Permission for ALB
resource "aws_lambda_permission" "alb_invoke" {
  count = var.enable_lambda_integration ? 1 : 0
  
  statement_id  = "AllowExecutionFromALB"
  action        = "lambda:InvokeFunction"
  function_name = var.webhook_lambda_arn
  principal     = "elasticloadbalancing.amazonaws.com"
  source_arn    = aws_lb_target_group.webhook.arn
}

# Listener Rule for Webhook
resource "aws_lb_listener_rule" "webhook" {
  count = var.certificate_arn != "" ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.webhook.arn
  }

  condition {
    path_pattern {
      values = ["/webhook", "/webhook/*"]
    }
  }

  tags = var.tags
}

# Listener Rule for Webhook (HTTP)
resource "aws_lb_listener_rule" "webhook_http" {
  count = var.certificate_arn == "" ? 1 : 0

  listener_arn = aws_lb_listener.http.arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.webhook.arn
  }

  condition {
    path_pattern {
      values = ["/webhook", "/webhook/*"]
    }
  }

  tags = var.tags
}

# Route 53 Record (if domain name is provided)
data "aws_route53_zone" "main" {
  count = var.domain_name != "" ? 1 : 0

  name         = replace(var.domain_name, "/^[^.]+\\./", "")
  private_zone = false
}

resource "aws_route53_record" "main" {
  count = var.domain_name != "" ? 1 : 0

  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# SSL Certificate (if domain name is provided but certificate ARN is not)
resource "aws_acm_certificate" "main" {
  count = var.domain_name != "" && var.certificate_arn == "" ? 1 : 0

  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}"
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-cert"
  })
}

# Certificate Validation
resource "aws_route53_record" "cert_validation" {
  for_each = var.domain_name != "" && var.certificate_arn == "" ? {
    for dvo in aws_acm_certificate.main[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main[0].zone_id
}

resource "aws_acm_certificate_validation" "main" {
  count = var.domain_name != "" && var.certificate_arn == "" ? 1 : 0

  certificate_arn         = aws_acm_certificate.main[0].arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# Update HTTPS Listener to use the created certificate
resource "aws_lb_listener" "https_with_created_cert" {
  count = var.domain_name != "" && var.certificate_arn == "" ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate_validation.main[0].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = var.mcp_server_target_group_arn
  }

  tags = var.tags
}