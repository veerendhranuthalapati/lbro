variable "name"                    { type = string }
variable "worker_task_role_arn"    { type = string }
variable "evidence_event_queue_arn" { type = string }
variable "tags"                    { type = map(string); default = {} }
