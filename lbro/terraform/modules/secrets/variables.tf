variable "name"                { type = string }
variable "environment"         { type = string }
variable "enable_rotation"     { type = bool; default = false }
variable "rotation_lambda_arn" { type = string; default = "" }
variable "tags"                { type = map(string); default = {} }
