################################################################################
# LBRO — SQS Module
# Queues: incident-events (main), containment-actions, notification-dispatch
# Each queue has a DLQ + CloudWatch alarm on DLQ depth
################################################################################

locals {
  queues = {
    incident_events = {
      name                       = "${var.name}-incident-events"
      visibility_timeout_seconds = 300   # 5 min: full breach response window
      message_retention_seconds  = 86400 # 24h
      delay_seconds              = 0
      description                = "Raw breach alerts from detectors"
    }
    containment_actions = {
      name                       = "${var.name}-containment-actions"
      visibility_timeout_seconds = 120   # 2 min: containment must be fast
      message_retention_seconds  = 3600  # 1h: if unprocessed, escalate
      delay_seconds              = 0
      description                = "Containment commands (isolate, revoke, block)"
    }
    notification_dispatch = {
      name                       = "${var.name}-notification-dispatch.fifo"
      visibility_timeout_seconds = 60
      message_retention_seconds  = 345600 # 4 days: covers GDPR 72h + buffer
      delay_seconds              = 0
      description                = "Regulatory notification jobs (FIFO: prevents duplicate legal dispatches)"
    }
  }
}

################################################################################
# Dead-Letter Queues
################################################################################

resource "aws_sqs_queue" "dlq" {
  for_each = local.queues

  name                      = "${each.value.name}-dlq"
  message_retention_seconds = 1209600 # 14 days: preserve for forensics
  kms_master_key_id         = var.kms_key_id
  sqs_managed_sse_enabled   = false

  tags = merge(var.tags, {
    Name     = "${each.value.name}-dlq"
    QueueFor = each.key
  })
}

################################################################################
# Main Queues
################################################################################

resource "aws_sqs_queue" "main" {
  for_each = local.queues

  name                       = each.value.name
  visibility_timeout_seconds = each.value.visibility_timeout_seconds
  message_retention_seconds  = each.value.message_retention_seconds
  delay_seconds              = each.value.delay_seconds
  kms_master_key_id          = var.kms_key_id
  sqs_managed_sse_enabled    = false
  # FIFO + content-based dedup for notification_dispatch only
  fifo_queue                  = each.key == "notification_dispatch" ? true : false
  content_based_deduplication = each.key == "notification_dispatch" ? true : false

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 3 # After 3 failures → DLQ → triggers human review
  })

  tags = merge(var.tags, {
    Name        = each.value.name
    Description = each.value.description
  })
}

################################################################################
# Queue Policies
# Pattern: deny non-HTTPS globally, then allow specific IAM roles.
# The DenyNonVPC approach requires conditions that don't work with empty lists,
# so we use the correct two-statement pattern:
#   1. Deny all non-HTTPS (always enforced)
#   2. Allow only approved IAM roles (conditional on var.allowed_principal_arns)
################################################################################

data "aws_iam_policy_document" "queue_policy" {
  for_each = local.queues

  # Statement 1: Deny all non-TLS traffic unconditionally
  statement {
    sid    = "DenyNonTLS"
    effect = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.main[each.key].arn]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # Statement 2: Allow only approved ECS task roles
  # When allowed_principal_arns is empty (bootstrap), no Allow exists → no access.
  dynamic "statement" {
    for_each = length(var.allowed_principal_arns) > 0 ? [1] : []
    content {
      sid    = "AllowECSTasks"
      effect = "Allow"
      principals {
        type        = "AWS"
        identifiers = var.allowed_principal_arns
      }
      actions = [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ChangeMessageVisibility",
      ]
      resources = [aws_sqs_queue.main[each.key].arn]
    }
  }
}

resource "aws_sqs_queue_policy" "main" {
  for_each  = local.queues
  queue_url = aws_sqs_queue.main[each.key].id
  policy    = data.aws_iam_policy_document.queue_policy[each.key].json
}

################################################################################
# CloudWatch Alarms — any DLQ message is an immediate alert
################################################################################

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each = local.queues

  alarm_name          = "${each.value.name}-dlq-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0

  dimensions = {
    QueueName = aws_sqs_queue.dlq[each.key].name
  }

  alarm_description = "LBRO: Messages in ${each.key} DLQ — requires investigation"
  alarm_actions     = var.alarm_sns_topic_arns
  ok_actions        = var.alarm_sns_topic_arns

  tags = var.tags
}

# Alert if an incident event sits unprocessed for more than 2 minutes
resource "aws_cloudwatch_metric_alarm" "oldest_message_age" {
  alarm_name          = "${var.name}-incident-events-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 120

  dimensions = {
    QueueName = aws_sqs_queue.main["incident_events"].name
  }

  alarm_description = "LBRO CRITICAL: Incident event unprocessed >2 minutes"
  alarm_actions     = var.alarm_sns_topic_arns

  tags = var.tags
}
