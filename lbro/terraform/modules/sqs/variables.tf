variable "name"                  { type = string }
variable "vpc_id"                { type = string }
variable "kms_key_id"            { type = string }
variable "allowed_principal_arns" { type = list(string) }
variable "alarm_sns_topic_arns"  { type = list(string); default = [] }
variable "tags"                  { type = map(string); default = {} }
