################################################################################
# LBRO — Monitoring Module
# CloudWatch Dashboard, composite alarms, SNS topic for alerts
################################################################################

################################################################################
# SNS Topic for Alerts
################################################################################

# SNS topic is created in the environment root (dev/main.tf) to avoid
# circular dependencies: SQS and RDS need the topic ARN for alarms, but
# monitoring depends on ECS/RDS/SQS. Receiving it as a variable breaks the cycle.
locals {
  alerts_topic_arn = var.alerts_sns_topic_arn
}

################################################################################
# Custom Metric Namespace alarms (LBRO business metrics)
################################################################################

resource "aws_cloudwatch_metric_alarm" "breach_response_latency" {
  alarm_name          = "${var.name}-breach-response-p99"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "BreachResponseLatencyMs"
  namespace           = "LBRO"
  period              = 60
  extended_statistic  = "p99"
  threshold           = 300000 # Alert if p99 > 5 minutes
  alarm_description   = "LBRO SLA BREACH: p99 response time exceeds 5 minutes"
  alarm_actions       = [local.alerts_topic_arn]
  treat_missing_data  = "notBreaching"

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "failed_containments" {
  alarm_name          = "${var.name}-failed-containments"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ContainmentFailures"
  namespace           = "LBRO"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "LBRO CRITICAL: Containment action failed — manual intervention required"
  alarm_actions       = [local.alerts_topic_arn]
  treat_missing_data  = "notBreaching"

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "notification_deadline_risk" {
  alarm_name          = "${var.name}-notification-deadline-risk"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "NotificationDeadlineRiskCount"
  namespace           = "LBRO"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "LBRO: Incidents approaching regulatory notification deadline without dispatch"
  alarm_actions       = [local.alerts_topic_arn]
  treat_missing_data  = "notBreaching"

  tags = var.tags
}

################################################################################
# API Health Alarms
################################################################################

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name}-api-5xx-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "API returning >10 5xx errors per minute"
  alarm_actions       = [local.alerts_topic_arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "api_latency_p99" {
  alarm_name          = "${var.name}-api-latency-p99"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p99"
  threshold           = 2 # 2 seconds
  alarm_description   = "API p99 latency > 2s"
  alarm_actions       = [local.alerts_topic_arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
  tags = var.tags
}

################################################################################
# CloudWatch Dashboard
################################################################################

resource "aws_cloudwatch_dashboard" "lbro" {
  dashboard_name = "${var.name}-ops"

  dashboard_body = jsonencode({
    widgets = [
      # ── Row 1: Business KPIs ──────────────────────────────────────────────
      {
        type   = "text"
        x = 0; y = 0; width = 24; height = 1
        properties = { markdown = "## LBRO Operations Dashboard — Business KPIs" }
      },
      {
        type = "metric"
        x = 0; y = 1; width = 6; height = 6
        properties = {
          title  = "Breach Response Latency (p50/p99)"
          view   = "timeSeries"
          period = 60
          metrics = [
            ["LBRO", "BreachResponseLatencyMs", { stat = "p50", label = "p50" }],
            ["LBRO", "BreachResponseLatencyMs", { stat = "p99", label = "p99", color = "#ff0000" }]
          ]
          annotations = {
            horizontal = [{ value = 300000, label = "5 min SLA", color = "#ff0000" }]
          }
        }
      },
      {
        type = "metric"
        x = 6; y = 1; width = 6; height = 6
        properties = {
          title  = "Incidents Processed"
          view   = "timeSeries"
          period = 300
          metrics = [
            ["LBRO", "IncidentsReceived",   { stat = "Sum", label = "Received" }],
            ["LBRO", "IncidentsContained",  { stat = "Sum", label = "Contained", color = "#00cc00" }],
            ["LBRO", "ContainmentFailures", { stat = "Sum", label = "Failed",    color = "#ff0000" }]
          ]
        }
      },
      {
        type = "metric"
        x = 12; y = 1; width = 6; height = 6
        properties = {
          title  = "Regulatory Notifications"
          view   = "timeSeries"
          period = 300
          metrics = [
            ["LBRO", "NotificationsDispatched",     { stat = "Sum", label = "Dispatched" }],
            ["LBRO", "NotificationDeadlineRiskCount",{ stat = "Sum", label = "At Risk", color = "#ff9900" }]
          ]
        }
      },
      {
        type = "alarm"
        x = 18; y = 1; width = 6; height = 6
        properties = {
          title  = "Active Alarms"
          alarms = [
            aws_cloudwatch_metric_alarm.breach_response_latency.arn,
            aws_cloudwatch_metric_alarm.failed_containments.arn,
            aws_cloudwatch_metric_alarm.notification_deadline_risk.arn,
            aws_cloudwatch_metric_alarm.api_5xx.arn
          ]
        }
      },

      # ── Row 2: Infrastructure ─────────────────────────────────────────────
      {
        type   = "text"
        x = 0; y = 7; width = 24; height = 1
        properties = { markdown = "## Infrastructure Health" }
      },
      {
        type = "metric"
        x = 0; y = 8; width = 8; height = 6
        properties = {
          title  = "ECS CPU/Memory — API"
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/ECS", "CPUUtilization",    "ClusterName", var.ecs_cluster_name, "ServiceName", var.api_service_name,    { stat = "Average", label = "CPU" }],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.api_service_name,    { stat = "Average", label = "Memory" }]
          ]
        }
      },
      {
        type = "metric"
        x = 8; y = 8; width = 8; height = 6
        properties = {
          title  = "ECS CPU/Memory — Worker"
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/ECS", "CPUUtilization",    "ClusterName", var.ecs_cluster_name, "ServiceName", var.worker_service_name, { stat = "Average", label = "CPU" }],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.worker_service_name, { stat = "Average", label = "Memory" }]
          ]
        }
      },
      {
        type = "metric"
        x = 16; y = 8; width = 8; height = 6
        properties = {
          title  = "SQS Queue Depths"
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.incident_queue_name,      { stat = "Maximum", label = "Incidents" }],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.containment_queue_name,   { stat = "Maximum", label = "Containment" }],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.notification_queue_name,  { stat = "Maximum", label = "Notifications" }]
          ]
        }
      },

      # ── Row 3: Database ───────────────────────────────────────────────────
      {
        type = "metric"
        x = 0; y = 14; width = 8; height = 6
        properties = {
          title  = "RDS Performance"
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/RDS", "CPUUtilization",    "DBInstanceIdentifier", var.db_instance_id, { stat = "Average", label = "CPU %" }],
            ["AWS/RDS", "DatabaseConnections","DBInstanceIdentifier", var.db_instance_id, { stat = "Average", label = "Connections", yAxis = "right" }]
          ]
        }
      },
      {
        type = "metric"
        x = 8; y = 14; width = 8; height = 6
        properties = {
          title  = "RDS Latency"
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/RDS", "ReadLatency",  "DBInstanceIdentifier", var.db_instance_id, { stat = "Average", label = "Read" }],
            ["AWS/RDS", "WriteLatency", "DBInstanceIdentifier", var.db_instance_id, { stat = "Average", label = "Write" }]
          ]
        }
      },
      {
        type = "metric"
        x = 16; y = 14; width = 8; height = 6
        properties = {
          title  = "ALB Request Rate + Errors"
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "RequestCount",             "LoadBalancer", var.alb_arn_suffix, { stat = "Sum",     label = "Requests" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count","LoadBalancer", var.alb_arn_suffix, { stat = "Sum",     label = "5xx",      color = "#ff0000" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count","LoadBalancer", var.alb_arn_suffix, { stat = "Sum",     label = "4xx",      color = "#ff9900" }]
          ]
        }
      }
    ]
  })
}

################################################################################
# Composite Alarms — reduce noise by combining conditions
# Only page on-call when BOTH infrastructure AND business metrics are degraded
################################################################################

resource "aws_cloudwatch_composite_alarm" "breach_response_critical" {
  alarm_name        = "${var.name}-breach-response-CRITICAL"
  alarm_description = "LBRO CRITICAL: API degraded AND breach response SLA breached simultaneously"

  alarm_rule = "ALARM(${aws_cloudwatch_metric_alarm.api_5xx.alarm_name}) AND ALARM(${aws_cloudwatch_metric_alarm.breach_response_latency.alarm_name})"

  alarm_actions = [local.alerts_topic_arn]
  ok_actions    = [local.alerts_topic_arn]

  tags = var.tags
}

resource "aws_cloudwatch_composite_alarm" "notification_deadline_critical" {
  alarm_name        = "${var.name}-notification-deadline-CRITICAL"
  alarm_description = "LBRO CRITICAL: Regulatory deadline at risk — immediate escalation required"

  # Fire when notifications at risk AND the API or worker appears unhealthy
  alarm_rule = "ALARM(${aws_cloudwatch_metric_alarm.notification_deadline_risk.alarm_name}) AND (ALARM(${aws_cloudwatch_metric_alarm.api_5xx.alarm_name}) OR ALARM(${aws_cloudwatch_metric_alarm.failed_containments.alarm_name}))"

  alarm_actions = [local.alerts_topic_arn]
  ok_actions    = [local.alerts_topic_arn]

  tags = var.tags
}

################################################################################
# Log Metric Filters — turn log patterns into metrics
################################################################################

resource "aws_cloudwatch_log_metric_filter" "containment_failures" {
  name           = "${var.name}-containment-failures"
  pattern        = "[timestamp, level=\"ERROR\", component=\"containment\", ...]"
  log_group_name = "/ecs/${var.name}/worker"

  metric_transformation {
    name          = "ContainmentFailures"
    namespace     = "LBRO"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "evidence_writes" {
  name           = "${var.name}-evidence-writes"
  pattern        = "[timestamp, ..., action=\"evidence_written\", ...]"
  log_group_name = "/ecs/${var.name}/worker"

  metric_transformation {
    name          = "EvidencePackagesWritten"
    namespace     = "LBRO"
    value         = "1"
    default_value = "0"
  }
}
