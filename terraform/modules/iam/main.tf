# ── ECS Task Execution Role ────────────────────────────────────────────────────
# Used by ECS agent to pull images from ECR and write logs to CloudWatch.
resource "aws_iam_role" "ecs_execution" {
  name = "${var.name_prefix}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow reading secrets from Secrets Manager at task start
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  count = length(var.secrets_arns) > 0 ? 1 : 0
  role  = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue", "ssm:GetParameters", "kms:Decrypt"]
      Resource = var.secrets_arns
    }]
  })
}

# ── ECS Task Role (API + Worker) ───────────────────────────────────────────────
# Least-privilege permissions for the application at runtime.
resource "aws_iam_role" "ecs_task" {
  name = "${var.name_prefix}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${var.name_prefix}-task-s3"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EvidenceReadWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:ListBucket",
          "s3:GetBucketVersioning"
        ]
        Resource = [
          var.evidence_bucket_arn,
          "${var.evidence_bucket_arn}/*"
        ]
      },
      {
        Sid    = "ReportsReadWrite"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [
          var.reports_bucket_arn,
          "${var.reports_bucket_arn}/*"
        ]
      },
      {
        Sid    = "MLModelsRead"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          var.ml_models_bucket_arn,
          "${var.ml_models_bucket_arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_task_sqs" {
  name = "${var.name_prefix}-task-sqs"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ChangeMessageVisibility"
      ]
      Resource = [
        var.incident_queue_arn,
        var.notification_queue_arn,
        var.dlq_arn
      ]
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_secrets" {
  count = length(var.secrets_arns) > 0 ? 1 : 0
  name  = "${var.name_prefix}-task-secrets"
  role  = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.secrets_arns
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_cloudwatch" {
  name = "${var.name_prefix}-task-cw"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # CloudWatch Logs — scoped to LBRO log group prefix
        Sid    = "CWLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:log-group:/ecs/${var.name_prefix}/*"
      },
      {
        # PutMetricData cannot be scoped to a resource (AWS requirement: must be *)
        Sid      = "CWMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      }
    ]
  })
}
