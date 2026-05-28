output "secret_arn"        { value = aws_secretsmanager_secret.app.arn }
output "secret_name"       { value = aws_secretsmanager_secret.app.name }
output "kms_key_arn"       { value = aws_kms_key.secrets.arn }
output "kms_key_id"        { value = aws_kms_key.secrets.key_id }
