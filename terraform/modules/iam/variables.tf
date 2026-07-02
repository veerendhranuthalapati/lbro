variable "name_prefix"            { type = string }
variable "environment"            { type = string }
variable "evidence_bucket_arn"    { type = string }
variable "reports_bucket_arn"     { type = string }
variable "ml_models_bucket_arn"   { type = string }
variable "incident_queue_arn"     { type = string }
variable "notification_queue_arn" { type = string }
variable "dlq_arn"                { type = string }
variable "secrets_arns"           { type = list(string); default = [] }
