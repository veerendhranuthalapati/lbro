variable "name"                           { type = string }
variable "aws_region"                     { type = string }
variable "alb_arn"                        { type = string }
variable "kms_key_arn"                    { type = string }
variable "blocked_country_codes"          { type = list(string); default = [] }
variable "alarm_sns_topic_arns"           { type = list(string); default = [] }
variable "blocked_requests_alarm_threshold" { type = number; default = 500 }
variable "tags"                           { type = map(string); default = {} }
