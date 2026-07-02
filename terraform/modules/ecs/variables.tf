variable "name_prefix"            { type = string }
variable "environment"            { type = string }
variable "vpc_id"                 { type = string }
variable "public_subnet_ids"      { type = list(string) }
variable "private_subnet_ids"     { type = list(string) }
variable "execution_role_arn"     { type = string }
variable "task_role_arn"          { type = string }
variable "aws_region"             { type = string; default = "us-east-1" }

variable "api_image"              { type = string }
variable "worker_image"           { type = string }
variable "frontend_image"         { type = string }

variable "api_cpu"                { type = number; default = 512 }
variable "api_memory"             { type = number; default = 1024 }
variable "worker_cpu"             { type = number; default = 256 }
variable "worker_memory"          { type = number; default = 512 }
variable "frontend_cpu"           { type = number; default = 256 }
variable "frontend_memory"        { type = number; default = 512 }

variable "api_desired_count"      { type = number; default = 2 }
variable "worker_desired_count"   { type = number; default = 1 }
variable "frontend_desired_count" { type = number; default = 1 }

variable "api_env_vars"           { type = list(object({ name = string; value = string })); default = [] }
variable "api_secrets"            { type = list(object({ name = string; valueFrom = string })); default = [] }
variable "worker_env_vars"        { type = list(object({ name = string; value = string })); default = [] }
variable "worker_secrets"         { type = list(object({ name = string; valueFrom = string })); default = [] }
variable "certificate_arn"        { type = string; default = "" }
