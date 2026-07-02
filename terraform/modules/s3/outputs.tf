output "evidence_bucket_name" { value = aws_s3_bucket.evidence.bucket }
output "evidence_bucket_arn"  { value = aws_s3_bucket.evidence.arn }
output "reports_bucket_name"  { value = aws_s3_bucket.reports.bucket }
output "reports_bucket_arn"   { value = aws_s3_bucket.reports.arn }
output "ml_models_bucket_name" { value = aws_s3_bucket.ml_models.bucket }
output "ml_models_bucket_arn"  { value = aws_s3_bucket.ml_models.arn }
