variable "name"                      { type = string }
variable "rds_instance_arns"         { type = list(string) }
variable "alarm_sns_topic_arns"      { type = list(string); default = [] }
variable "backup_copy_region"        { type = string; default = "" }
variable "enable_vault_lock"         { type = bool; default = false }
variable "vault_lock_changeable_days" { type = number; default = 3 }
variable "tags"                      { type = map(string); default = {} }
