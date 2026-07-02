# ── DLQ depth alarm ────────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${var.name_prefix}-dlq-depth"
  alarm_description   = "Messages stuck in DLQ — processing failures detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = { QueueName = var.dlq_name }

  alarm_actions = [var.sns_topic_arn]
  ok_actions    = [var.sns_topic_arn]
}

# ── ECS API CPU alarm ──────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "api_cpu_high" {
  alarm_name          = "${var.name_prefix}-api-cpu-high"
  alarm_description   = "API service CPU > 85% — consider scaling"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "missing"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.api_service_name
  }

  alarm_actions = [var.sns_topic_arn]
}

# ── ECS API memory alarm ───────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "api_memory_high" {
  alarm_name          = "${var.name_prefix}-api-memory-high"
  alarm_description   = "API service memory > 90% — risk of OOM"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 90
  treat_missing_data  = "missing"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.api_service_name
  }

  alarm_actions = [var.sns_topic_arn]
}

# ── Worker CPU alarm ───────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "worker_cpu_high" {
  alarm_name          = "${var.name_prefix}-worker-cpu-high"
  alarm_description   = "Worker service CPU > 85%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "missing"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.worker_service_name
  }

  alarm_actions = [var.sns_topic_arn]
}

# ── ALB 5xx error rate ─────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.name_prefix}-alb-5xx"
  alarm_description   = "ALB 5xx errors > 1% of requests"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "100 * errors / MAX([errors, requests])"
    label       = "5xx Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "HTTPCode_Target_5XX_Count"
      namespace   = "AWS/ApplicationELB"
      period      = 60
      stat        = "Sum"
      dimensions = {
        LoadBalancer = var.alb_arn_suffix
      }
    }
  }

  metric_query {
    id = "requests"
    metric {
      metric_name = "RequestCount"
      namespace   = "AWS/ApplicationELB"
      period      = 60
      stat        = "Sum"
      dimensions = {
        LoadBalancer = var.alb_arn_suffix
      }
    }
  }

  alarm_actions = [var.sns_topic_arn]
}

# ── API latency P99 ────────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "api_latency_p99" {
  alarm_name          = "${var.name_prefix}-api-latency-p99"
  alarm_description   = "API P99 response time > 2s"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p99"
  threshold           = 2
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.api_target_group_arn_suffix
  }

  alarm_actions = [var.sns_topic_arn]
}

# ── RDS CPU alarm ──────────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.name_prefix}-rds-cpu"
  alarm_description   = "RDS CPU > 80% — query optimization or scale needed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "missing"

  dimensions = { DBInstanceIdentifier = var.rds_instance_id }

  alarm_actions = [var.sns_topic_arn]
}

# ── RDS free storage alarm ─────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${var.name_prefix}-rds-storage-low"
  alarm_description   = "RDS free storage < 2 GiB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Minimum"
  threshold           = 2147483648  # 2 GiB in bytes
  treat_missing_data  = "missing"

  dimensions = { DBInstanceIdentifier = var.rds_instance_id }

  alarm_actions = [var.sns_topic_arn]
}

# ── RDS connections alarm ──────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${var.name_prefix}-rds-connections"
  alarm_description   = "RDS connection count > 80 — connection pool pressure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = { DBInstanceIdentifier = var.rds_instance_id }

  alarm_actions = [var.sns_topic_arn]
}

# ── CloudWatch Dashboard ───────────────────────────────────────────────────────
resource "aws_cloudwatch_dashboard" "lbro" {
  dashboard_name = "${var.name_prefix}-dashboard"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "API CPU & Memory"
          period = 60
          metrics = [
            ["AWS/ECS", "CPUUtilization",    "ClusterName", var.ecs_cluster_name, "ServiceName", var.api_service_name],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.api_service_name]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "ALB Request Rate & Errors"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "RequestCount",            "LoadBalancer", var.alb_arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer", var.alb_arn_suffix]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "RDS Metrics"
          period = 60
          metrics = [
            ["AWS/RDS", "CPUUtilization",       "DBInstanceIdentifier", var.rds_instance_id],
            ["AWS/RDS", "DatabaseConnections",  "DBInstanceIdentifier", var.rds_instance_id],
            ["AWS/RDS", "FreeStorageSpace",     "DBInstanceIdentifier", var.rds_instance_id]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "SQS DLQ Depth"
          period = 300
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.dlq_name]
          ]
        }
      }
    ]
  })
}
