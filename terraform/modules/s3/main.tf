# ── Evidence bucket (WORM / immutable) ────────────────────────────────────────
resource "aws_s3_bucket" "evidence" {
  bucket        = "${var.name_prefix}-evidence"
  force_destroy = var.force_destroy
  tags = { Name = "${var.name_prefix}-evidence", Environment = var.environment }
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Object Lock – compliance mode prevents deletion for 7 years in production
resource "aws_s3_bucket_object_lock_configuration" "evidence" {
  count  = var.environment == "production" ? 1 : 0
  bucket = aws_s3_bucket.evidence.id
  rule {
    default_retention {
      mode  = "COMPLIANCE"
      years = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    id     = "transition-to-glacier"
    status = "Enabled"
    filter { prefix = "" }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# ── Reports bucket ─────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "reports" {
  bucket        = "${var.name_prefix}-reports"
  force_destroy = var.force_destroy
  tags = { Name = "${var.name_prefix}-reports", Environment = var.environment }
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    id     = "expire-old-reports"
    status = "Enabled"
    filter { prefix = "" }
    expiration { days = 365 }
  }
}

# ── ML models bucket ───────────────────────────────────────────────────────────
resource "aws_s3_bucket" "ml_models" {
  bucket        = "${var.name_prefix}-ml-models"
  force_destroy = var.force_destroy
  tags = { Name = "${var.name_prefix}-ml-models", Environment = var.environment }
}

resource "aws_s3_bucket_versioning" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "ml_models" {
  bucket                  = aws_s3_bucket.ml_models.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
