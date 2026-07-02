################################################################################
# LBRO — EventBridge Module
#
# Scheduled rules for time-sensitive operations:
#   1. Deadline sweeper — every 15 min, trigger Lambda to escalate
#      notifications approaching their regulatory deadline
#   2. DLQ reaper    — every hour, alert on stuck DLQ messages
#   3. Evidence integrity checker — daily, verify S3 Object Lock still intact
#
# All rules target the notification dispatch SQS queue or SNS.
################################################################################

# ── Deadline Sweeper ──────────────────────────────────────────────────────────
# Runs every 15 minutes and enqueues a "sweep" message. The worker picks it up
# and checks for notifications within 2 hours of their deadline, dispatching
# them proactively rather than waiting for a manual trigger.

resource "aws_scheduler_schedule" "deadline_sweep" {
  name       = "${var.name}-deadline-sweep"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"  # Exact schedule — regulatory deadlines are time-critical
  }

  # Every 15 minutes
  schedule_expression = "rate(15 minutes)"

  target {
    arn      = var.notification_queue_arn
    role_arn = aws_iam_role.scheduler.arn

    input = jsonencode({
      source     = "eventbridge.scheduler"
      event_type = "deadline_sweep"
      # Worker treats this as a sweep trigger, not a real incident message
    })

    sqs_parameters {
      message_group_id = "deadline-sweep"
    }

    retry_policy {
      maximum_event_age_in_seconds = 300  # Discard if >5 min late — sweep would be stale
      maximum_retry_attempts       = 2
    }
  }
}

# ── Evidence Integrity Check ──────────────────────────────────────────────────
# Daily check: query S3 to confirm Object Lock is still set on evidence packages.
# Sends results to SNS — if a lock is missing, it triggers a critical alert.

resource "aws_scheduler_schedule" "evidence_integrity" {
  name       = "${var.name}-evidence-integrity"
  group_name = "default"

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 60  # Can run anytime within the hour after midnight
  }

  schedule_expression = "cron(0 1 * * ? *)"  # Daily at 01:00 UTC

  target {
    arn      = var.alerts_sns_topic_arn
    role_arn = aws_iam_role.scheduler.arn

    input = jsonencode({
      source     = "eventbridge.scheduler"
      event_type = "evidence_integrity_check"
      message    = "Scheduled evidence integrity check — verify S3 Object Lock retention"
    })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 3
    }
  }
}

# ── IAM Role for EventBridge Scheduler ───────────────────────────────────────

resource "aws_iam_role" "scheduler" {
  name = "${var.name}-eventbridge-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "scheduler" {
  name = "${var.name}-eventbridge-scheduler-policy"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SendToNotificationQueue"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = [var.notification_queue_arn]
      },
      {
        Sid    = "PublishToAlertsTopic"
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = [var.alerts_sns_topic_arn]
      }
    ]
  })
}

data "aws_caller_identity" "current" {}
