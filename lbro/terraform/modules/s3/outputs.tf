output "evidence_bucket_id"       { value = aws_s3_bucket.evidence.id }
output "evidence_bucket_arn"      { value = aws_s3_bucket.evidence.arn }
output "notifications_bucket_id"  { value = aws_s3_bucket.notifications.id }
output "notifications_bucket_arn" { value = aws_s3_bucket.notifications.arn }
output "alb_logs_bucket_id"       { value = aws_s3_bucket.alb_logs.id }
output "alb_logs_bucket_name"     { value = aws_s3_bucket.alb_logs.bucket }
output "s3_kms_key_arn"           { value = aws_kms_key.s3.arn }
output "s3_kms_key_id"            { value = aws_kms_key.s3.key_id }
