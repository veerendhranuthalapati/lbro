################################################################################
# LBRO — WAF Module (AWS WAFv2)
#
# Protects the ALB with:
#   1. AWS Managed Rules — core rule set (SQLi, XSS, known-bad IPs)
#   2. AWS Managed Rules — known-bad inputs (Log4Shell, SSRF, Spring4Shell)
#   3. AWS Managed Rules — SQLi protection
#   4. IP rate-based rule — 2000 requests/5min per IP (coarse; fine limits in app)
#   5. Geo-block (optional) — deny countries outside operational jurisdictions
#   6. All blocked requests logged to CloudWatch for forensic audit
################################################################################

resource "aws_wafv2_web_acl" "this" {
  name        = "${var.name}-waf"
  description = "LBRO ALB WAF — rate limiting, managed rules, geo-block"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rule 1: AWS Managed Core Rule Set (SQLi, XSS, CSRF, path traversal)
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 10
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
        # Count body size violations — evidence uploads may exceed default limits
        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use { count {} }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-waf-common"
      sampled_requests_enabled   = true
    }
  }

  # Rule 2: Known-bad inputs (Log4Shell, Spring4Shell, SSRF patterns)
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 20
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-waf-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # Rule 3: SQL injection protection
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 30
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-waf-sqli"
      sampled_requests_enabled   = true
    }
  }

  # Rule 4: IP-based rate limit — 2000 req/5min per IP
  # Coarse guard; fine-grained per-endpoint limits live in slowapi.
  rule {
    name     = "RateLimitPerIP"
    priority = 40
    action { block {} }
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-waf-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  # Rule 5: Geo-block (optional — empty list disables rule entirely)
  dynamic "rule" {
    for_each = length(var.blocked_country_codes) > 0 ? [1] : []
    content {
      name     = "GeoBlock"
      priority = 50
      action { block {} }
      statement {
        geo_match_statement {
          country_codes = var.blocked_country_codes
        }
      }
      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.name}-waf-geo"
        sampled_requests_enabled   = true
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.name}-waf"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

# Associate WAF ACL with the ALB
resource "aws_wafv2_web_acl_association" "this" {
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.this.arn
}

# WAF access logs — all blocked requests retained 90 days for forensic audit
# Log group name MUST start with aws-waf-logs- (AWS requirement)
resource "aws_cloudwatch_log_group" "waf" {
  name              = "aws-waf-logs-${var.name}"
  retention_in_days = 90
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_wafv2_web_acl_logging_configuration" "this" {
  log_destination_configs = [aws_cloudwatch_log_group.waf.arn]
  resource_arn            = aws_wafv2_web_acl.this.arn

  # Redact the API key header from WAF logs — credentials must never appear in logs
  redacted_fields {
    single_header {
      name = "x-lbro-api-key"
    }
  }
}

# Alarm: burst of blocked requests indicates an active attack
resource "aws_cloudwatch_metric_alarm" "blocked_requests" {
  alarm_name          = "${var.name}-waf-blocked-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = var.blocked_requests_alarm_threshold

  dimensions = {
    Rule   = "ALL"
    WebACL = aws_wafv2_web_acl.this.name
    Region = var.aws_region
  }

  alarm_description = "WAF blocked >${var.blocked_requests_alarm_threshold} requests in 10 min — active attack likely"
  alarm_actions     = var.alarm_sns_topic_arns
  tags              = var.tags
}
