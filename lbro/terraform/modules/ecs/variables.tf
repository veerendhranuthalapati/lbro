variable "name"        { type = string }
variable "environment" { type = string }
variable "aws_region"  { type = string }
variable "vpc_id"      { type = string }
variable "vpc_cidr"    { type = string }

variable "public_subnet_ids"  { type = list(string) }
variable "private_subnet_ids" { type = list(string) }

variable "kms_key_arn"              { type = string }
variable "secrets_arn"              { type = string }
variable "acm_certificate_arn"      { type = string }
variable "alb_access_log_bucket"    { type = string }
variable "incident_queue_name"      { type = string }

variable "ecs_execution_role_arn"      { type = string }
variable "ecs_api_task_role_arn"       { type = string }
variable "ecs_worker_task_role_arn"    { type = string }

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "api_cpu"            { type = number; default = 512  }
variable "api_memory"         { type = number; default = 1024 }
variable "api_desired_count"  { type = number; default = 2    }
variable "api_max_count"      { type = number; default = 10   }

variable "worker_cpu"            { type = number; default = 1024 }
variable "worker_memory"         { type = number; default = 2048 }
variable "worker_desired_count"  { type = number; default = 2    }
variable "worker_max_count"      { type = number; default = 20   }

variable "tags" { type = map(string); default = {} }

variable "enable_container_insights" { type = bool; default = true; description = "Enable ECS Container Insights (~$8/mo). Disable in dev to save cost." }
