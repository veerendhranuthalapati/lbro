variable "name"                { type = string }
variable "environment"         { type = string }
variable "aws_region"          { type = string; default = "ap-south-1" }
variable "vpc_id"              { type = string }
variable "db_subnet_group_name" { type = string }
variable "db_subnet_ids"       { type = list(string) }
variable "allowed_sg_ids"      { type = list(string) }
variable "kms_key_arn"         { type = string }
variable "db_secret_arn"       { type = string; description = "Secrets Manager ARN for RDS Proxy auth" }
variable "db_name"             { type = string; default = "lbro" }
variable "db_username"         { type = string; default = "lbro_app" }
variable "db_password"         { type = string; sensitive = true }
variable "instance_class"      { type = string; default = "db.t4g.medium" }
variable "replica_instance_class" { type = string; default = "db.t4g.medium" }
variable "allocated_storage"   { type = number; default = 20 }
variable "max_allocated_storage" { type = number; default = 100 }
variable "max_connections"     { type = string; default = "200" }
variable "create_read_replica" { type = bool; default = false }
variable "enable_rds_proxy" {
  description = "Enable RDS Proxy for connection pooling. Recommended for prod. Adds ~$22/mo in dev."
  type        = bool
  default     = true
}
variable "alarm_sns_topic_arns" { type = list(string); default = [] }
variable "max_connections_alarm_threshold" { type = number; default = 150 }
variable "tags"                { type = map(string); default = {} }
