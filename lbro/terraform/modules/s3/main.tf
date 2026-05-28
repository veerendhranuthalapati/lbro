################################################################################
# LBRO — S3 Module
# Buckets:
#   evidence        — WORM (Object Lock COMPLIANCE), forensic packages
#   notifications   — regulatory notification archives
#   alb-logs        — ALB access logs
#   tf-state        — Terraform state (created separately)
################################################################################

################################################################################
# KMS Key for S3 (separate from main KMS to allow granular rotation)
################################################################################

resource "aws_kms_key" "s3" {
  description             = "LBRO S3 evidence encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccess"
        Effect = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowECSTaskEncrypt"
        Effect = "Allow"
        Principal = { AWS = var.worker_task_role_arn }
        Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, { Name = "${var.name}-s3-kms" })
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${var.name}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

data "aws_caller_identity" "current" {}

################################################################################
# Evidence Bucket — WORM via Object Lock (COMPLIANCE mode)
# Compliance mode: even root cannot delete objects within retention period
# This is what makes forensic evidence legally defensible
################################################################################

resource "aws_s3_bucket" "evidence" {
  bucket = "${var.name}-evidence-${data.aws_caller_identity.current.account_id}"

  # Object Lock must be enabled at creation time
  object_lock_enabled = true

  tags = merge(var.tags, {
    Name            = "${var.name}-evidence"
    DataClass       = "forensic"
    RetentionPolicy = "worm-7-years"
    GDPR            = "true"
    HIPAA           = "true"
    DPDPA           = "true"
  })
}

resource "aws_s3_bucket_object_lock_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    default_retention {
      mode  = "COMPLIANCE" # Not GOVERNANCE — even admins can't delete
      years = 7            # Covers all jurisdictions (HIPAA requires 6yr, GDPR 6yr+)
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration {
    status = "Enabled" # Required for Object Lock
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_notification" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  queue {
    queue_arn     = var.evidence_event_queue_arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "incidents/"
  }
}

# Lifecycle: Intelligent Tiering for active evidence + Glacier for old evidence.
# Intelligent Tiering is more cost-efficient than a fixed transition because it
# automatically moves objects based on actual access patterns (no retrieval fees
# for objects accessed occasionally). Fixed Glacier transition charges retrieval fees.
resource "aws_s3_bucket_intelligent_tiering_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  name   = "evidence-tiering"

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180  # No access for 180 days → Deep Archive (~$0.00099/GB/mo)
  }

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90   # No access for 90 days → Archive (~$0.004/GB/mo)
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    id     = "intelligent-tiering"
    status = "Enabled"

    # Transition current versions to Intelligent Tiering immediately
    transition {
      days          = 0
      storage_class = "INTELLIGENT_TIERING"
    }

    # Noncurrent versions (overwritten objects) go to Glacier IR after 30d
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER_IR"
    }

    # Delete noncurrent versions after 7 years (WORM compliance period)
    noncurrent_version_expiration {
      noncurrent_days = 2555
    }
  }
}

# Bucket policy: deny unencrypted uploads, deny non-HTTPS, allow only task role
resource "aws_s3_bucket_policy" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyHTTP"
        Effect = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [
          aws_s3_bucket.evidence.arn,
          "${aws_s3_bucket.evidence.arn}/*"
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      },
      {
        Sid    = "DenyUnencryptedUploads"
        Effect = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.evidence.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = aws_kms_key.s3.arn
          }
        }
      },
      {
        Sid    = "AllowWorkerTaskOnly"
        Effect = "Allow"
        Principal = { AWS = var.worker_task_role_arn }
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.evidence.arn,
          "${aws_s3_bucket.evidence.arn}/*"
        ]
      }
    ]
  })
}

################################################################################
# Notifications Bucket — regulatory notifications archive
################################################################################

resource "aws_s3_bucket" "notifications" {
  bucket = "${var.name}-notifications-${data.aws_caller_identity.current.account_id}"

  tags = merge(var.tags, {
    Name      = "${var.name}-notifications"
    DataClass = "regulatory"
  })
}

resource "aws_s3_bucket_server_side_encryption_configuration" "notifications" {
  bucket = aws_s3_bucket.notifications.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "notifications" {
  bucket = aws_s3_bucket.notifications.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "notifications" {
  bucket                  = aws_s3_bucket.notifications.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "notifications" {
  bucket = aws_s3_bucket.notifications.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    noncurrent_version_expiration { noncurrent_days = 365 }
  }
}

################################################################################
# ALB Access Logs Bucket
################################################################################

data "aws_elb_service_account" "main" {}

resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.name}-alb-logs-${data.aws_caller_identity.current.account_id}"

  tags = merge(var.tags, { Name = "${var.name}-alb-logs" })
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket                  = aws_s3_bucket.alb_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  rule {
    id     = "expire-after-90d"
    status = "Enabled"
    expiration { days = 90 }
  }
}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = data.aws_elb_service_account.main.arn }
      Action    = "s3:PutObject"
      Resource  = "${aws_s3_bucket.alb_logs.arn}/alb/${var.name}/*"
    }]
  })
}
