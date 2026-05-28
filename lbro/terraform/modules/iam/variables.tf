variable "name"                    { type = string }
variable "secrets_arn"             { type = string }
variable "kms_key_arn"             { type = string }
variable "s3_kms_key_arn"          { type = string }
variable "sqs_queue_arns"          { type = list(string) }
variable "evidence_bucket_arn"     { type = string }
variable "notifications_bucket_arn" { type = string }
variable "tags"                    { type = map(string); default = {} }
