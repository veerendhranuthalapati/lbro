variable "name"                   { type = string }
variable "notification_queue_arn" { type = string }
variable "alerts_sns_topic_arn"   { type = string }
variable "tags"                   { type = map(string); default = {} }
