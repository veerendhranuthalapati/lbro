variable "name_prefix"       { type = string }
variable "environment"       { type = string }
variable "subnet_ids"        { type = list(string) }
variable "vpc_id"            { type = string }
variable "instance_class"    { type = string; default = "db.t4g.micro" }
variable "db_name"           { type = string; default = "lbro" }
variable "db_username"       { type = string; default = "lbro_admin" }
variable "db_password"       { type = string; sensitive = true }
variable "allowed_sg_ids"    { type = list(string); default = [] }
variable "deletion_protection" { type = bool; default = true }
variable "backup_retention_days" { type = number; default = 7 }
