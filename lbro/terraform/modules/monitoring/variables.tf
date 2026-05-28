variable "name"                   { type = string }
variable "kms_key_id"             { type = string }
variable "alert_emails"           { type = list(string); default = [] }
variable "alb_arn_suffix"         { type = string }
variable "ecs_cluster_name"       { type = string }
variable "api_service_name"       { type = string }
variable "worker_service_name"    { type = string }
variable "db_instance_id"         { type = string }
variable "incident_queue_name"    { type = string }
variable "containment_queue_name" { type = string }
variable "notification_queue_name"{ type = string }
variable "tags"                   { type = map(string); default = {} }
variable "alerts_sns_topic_arn" {
  description = "ARN of the pre-created SNS alerts topic (created in env root to break circular deps)"
  type        = string
}
