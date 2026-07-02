################################################################################
# LBRO — AWS Backup Module
#
# Centralised backup policy covering:
#   RDS instances       — daily snapshots, 30-day retention, cross-region copy
#   S3 evidence bucket  — continuous backup via versioning (handled by S3 module)
#
# Backup vault uses a separate KMS key with a 14-day deletion window so
# backups cannot be immediately destroyed even if the main key is compromised.
################################################################################

resource "aws_kms_key" "backup_vault" {
  description             = "LBRO backup vault encryption"
  deletion_window_in_days = 14
  enable_key_rotation     = true

  tags = merge(var.tags, { Name = "${var.name}-backup-vault-kms" })
}

resource "aws_kms_alias" "backup_vault" {
  name          = "alias/${var.name}-backup-vault"
  target_key_id = aws_kms_key.backup_vault.key_id
}

# Backup vault — locked after creation (vault lock prevents backup deletion)
resource "aws_backup_vault" "this" {
  name        = "${var.name}-vault"
  kms_key_arn = aws_kms_key.backup_vault.arn
  tags        = var.tags
}

# Vault lock — COMPLIANCE mode: even root cannot delete backups within retention
resource "aws_backup_vault_lock_configuration" "this" {
  count             = var.enable_vault_lock ? 1 : 0
  backup_vault_name = aws_backup_vault.this.name
  min_retention_days = 7
  max_retention_days = 36500  # 100 years
  # changeable_for_days: 0 = lock is permanent immediately
  # Set to 3 during initial setup to allow correction before lock becomes permanent
  changeable_for_days = var.vault_lock_changeable_days
}

# IAM Role for AWS Backup
resource "aws_iam_role" "backup" {
  name = "${var.name}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "backup.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup",
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores",
  ]

  tags = var.tags
}

# Backup Plan — daily + weekly schedule
resource "aws_backup_plan" "this" {
  name = "${var.name}-backup-plan"

  rule {
    rule_name         = "daily-30d-retention"
    target_vault_name = aws_backup_vault.this.name
    schedule          = "cron(0 2 * * ? *)"  # Daily at 02:00 UTC

    start_window_minutes      = 60
    completion_window_minutes = 180

    lifecycle {
      cold_storage_after = 14   # Move to cold storage after 14 days
      delete_after       = 30   # Delete after 30 days
    }

    # Cross-region copy for disaster recovery
    dynamic "copy_action" {
      for_each = var.backup_copy_region != "" ? [1] : []
      content {
        destination_vault_arn = "arn:aws:backup:${var.backup_copy_region}:${data.aws_caller_identity.current.account_id}:backup-vault:${var.name}-vault-dr"
        lifecycle {
          delete_after = 30
        }
      }
    }
  }

  rule {
    rule_name         = "weekly-90d-retention"
    target_vault_name = aws_backup_vault.this.name
    schedule          = "cron(0 3 ? * SUN *)"  # Weekly on Sundays at 03:00 UTC

    start_window_minutes      = 60
    completion_window_minutes = 360

    lifecycle {
      cold_storage_after = 30
      delete_after       = 90
    }
  }

  tags = var.tags
}

# Assign RDS instances to the backup plan
resource "aws_backup_selection" "rds" {
  name         = "${var.name}-rds-backup-selection"
  iam_role_arn = aws_iam_role.backup.arn
  plan_id      = aws_backup_plan.this.id

  resources = var.rds_instance_arns

  condition {
    string_equals {
      key   = "aws:ResourceTag/ManagedBy"
      value = "Terraform"
    }
  }
}

# Alert when backups fail
resource "aws_cloudwatch_metric_alarm" "backup_failed" {
  alarm_name          = "${var.name}-backup-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "NumberOfBackupJobsFailed"
  namespace           = "AWS/Backup"
  period              = 86400  # Check daily
  statistic           = "Sum"
  threshold           = 0

  dimensions        = { BackupVaultName = aws_backup_vault.this.name }
  alarm_description = "LBRO: Backup job failed — manual verification required"
  alarm_actions     = var.alarm_sns_topic_arns
  tags              = var.tags
}

data "aws_caller_identity" "current" {}
