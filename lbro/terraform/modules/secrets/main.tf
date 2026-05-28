################################################################################
# LBRO — Secrets Module
# Creates the Secrets Manager secret with placeholder values.
# Actual values are injected by CI/CD or manually by operators — never in TF state.
################################################################################

resource "aws_kms_key" "secrets" {
  description             = "LBRO Secrets Manager encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(var.tags, { Name = "${var.name}-secrets-kms" })
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.name}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "${var.name}/app"
  description             = "LBRO application secrets — database credentials, API keys, queue URLs"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = merge(var.tags, {
    Name        = "${var.name}-app-secrets"
    Environment = var.environment
  })
}

# Seed with placeholder values — operators/CI replace these
resource "aws_secretsmanager_secret_version" "app_initial" {
  secret_id = aws_secretsmanager_secret.app.id

  secret_string = jsonencode({
    database_url       = "REPLACE_ME_postgresql://lbro_app:PASSWORD@HOST:5432/lbro"
    secret_key         = "REPLACE_ME_$(openssl rand -hex 32)"
    sqs_queue_url      = "REPLACE_ME"
    s3_evidence_bucket = "REPLACE_ME"
  })

  lifecycle {
    # Never overwrite once set — secrets are managed outside Terraform
    ignore_changes = [secret_string]
  }
}

# Rotation placeholder — hook to a Lambda rotator in prod
resource "aws_secretsmanager_secret_rotation" "app" {
  count = var.enable_rotation ? 1 : 0

  secret_id           = aws_secretsmanager_secret.app.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 30
  }
}
