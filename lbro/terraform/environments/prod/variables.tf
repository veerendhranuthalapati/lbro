variable "aws_region"          { type = string; default = "ap-south-1" }
variable "dr_region"           { type = string; default = "ap-southeast-1" }
variable "owner_team"          { type = string; default = "security-platform" }
variable "acm_certificate_arn" { type = string }
variable "alert_emails"        { type = list(string); default = [] }
variable "image_tag"           { type = string }
variable "blocked_country_codes" { type = list(string); default = [] }
