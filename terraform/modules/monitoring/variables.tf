variable "name_prefix"            { type = string }
variable "environment"            { type = string }
variable "sns_topic_arn"          { type = string }
variable "ecs_cluster_name"       { type = string }
variable "api_service_name"       { type = string }
variable "worker_service_name"    { type = string }
variable "dlq_arn"                { type = string; default = "" }
variable "dlq_name"               { type = string }
variable "rds_instance_id"        { type = string }
variable "alb_arn_suffix"         { type = string }
variable "api_target_group_arn_suffix" { type = string }
