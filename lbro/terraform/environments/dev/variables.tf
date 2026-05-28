variable "aws_region"          { type = string; default = "ap-south-1" }
variable "owner_team"          { type = string; default = "security-platform" }
variable "acm_certificate_arn" { type = string; description = "ACM cert ARN for HTTPS ALB listener" }
variable "alert_emails"        { type = list(string); default = [] }
variable "image_tag"           { type = string; default = "latest" }
