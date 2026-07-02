# ── Dead Letter Queue (shared) ─────────────────────────────────────────────────
resource "aws_sqs_queue" "dlq" {
  name                       = "${var.name_prefix}-dlq"
  message_retention_seconds  = 1209600  # 14 days
  kms_master_key_id          = var.kms_key_arn != "" ? var.kms_key_arn : null
  tags = { Name = "${var.name_prefix}-dlq", Environment = var.environment }
}

# ── Incident processing queue ─────────────────────────────────────────────────
resource "aws_sqs_queue" "incidents" {
  name                        = "${var.name_prefix}-incidents"
  visibility_timeout_seconds  = 300
  message_retention_seconds   = 86400
  receive_wait_time_seconds   = 20
  kms_master_key_id           = var.kms_key_arn != "" ? var.kms_key_arn : null

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.name_prefix}-incidents", Environment = var.environment }
}

# ── Notification sending queue ─────────────────────────────────────────────────
resource "aws_sqs_queue" "notifications" {
  name                        = "${var.name_prefix}-notifications"
  visibility_timeout_seconds  = 60
  message_retention_seconds   = 86400
  receive_wait_time_seconds   = 20
  kms_master_key_id           = var.kms_key_arn != "" ? var.kms_key_arn : null

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.name_prefix}-notifications", Environment = var.environment }
}
