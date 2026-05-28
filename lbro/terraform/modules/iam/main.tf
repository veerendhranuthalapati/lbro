################################################################################
# LBRO — IAM Module
# Roles: ECS Execution, API Task, Worker Task
# Every role follows least-privilege: only what the service actually calls
################################################################################

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

################################################################################
# ECS Task Execution Role
# Used by ECS control plane to: pull images, fetch secrets, write logs
################################################################################

resource "aws_iam_role" "ecs_execution" {
  name = "${var.name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${var.name}-ecs-execution-secrets"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetSecrets"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [var.secrets_arn]
      },
      {
        Sid    = "DecryptWithKMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:DescribeKey"]
        Resource = [var.kms_key_arn]
      }
    ]
  })
}

################################################################################
# API Task Role
# Permissions: SQS (send), RDS (via network), CloudWatch, X-Ray
################################################################################

resource "aws_iam_role" "ecs_api_task" {
  name = "${var.name}-ecs-api-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnLike = {
          "aws:SourceArn" = "arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
        }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "api_task" {
  name = "${var.name}-api-task-policy"
  role = aws_iam_role.ecs_api_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSSendIncidents"
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
        Resource = var.sqs_queue_arns
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = { "cloudwatch:namespace" = "LBRO" }
        }
      },
      {
        Sid    = "XRayTracing"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      },
      {
        Sid    = "SSMExecSessionDev"
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ]
        Resource = "*"
      }
    ]
  })
}

################################################################################
# Worker Task Role
# Permissions: SQS (recv/del), S3 evidence bucket (put/get), RDS, X-Ray
# Workers have MORE access because they execute containment and write evidence
################################################################################

resource "aws_iam_role" "ecs_worker_task" {
  name = "${var.name}-ecs-worker-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "worker_task" {
  name = "${var.name}-worker-task-policy"
  role = aws_iam_role.ecs_worker_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSWorker"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
          "sqs:SendMessage" # For forwarding to downstream queues
        ]
        Resource = var.sqs_queue_arns
      },
      {
        Sid    = "S3EvidenceWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectTagging",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.evidence_bucket_arn,
          "${var.evidence_bucket_arn}/*"
        ]
      },
      {
        Sid    = "S3NotificationsWrite"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject"]
        Resource = ["${var.notifications_bucket_arn}/*"]
      },
      {
        Sid    = "KMSDecryptEvidence"
        Effect = "Allow"
        Action = ["kms:GenerateDataKey", "kms:Decrypt", "kms:DescribeKey"]
        Resource = [var.kms_key_arn, var.s3_kms_key_arn]
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = { "cloudwatch:namespace" = "LBRO" }
        }
      },
      {
        Sid    = "XRayTracing"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      },
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [var.secrets_arn]
      }
    ]
  })
}
