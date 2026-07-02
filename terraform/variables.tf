variable "aws_region" {
  description = "AWS region to deploy LBRO"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (development/staging/production)"
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "api_image" {
  description = "Docker image for the API service (ECR URI)"
  type        = string
}

variable "worker_image" {
  description = "Docker image for the Worker service (ECR URI)"
  type        = string
}

variable "frontend_image" {
  description = "Docker image for the Frontend (ECR URI)"
  type        = string
}

variable "api_cpu" {
  description = "CPU units for API task (256=0.25vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Memory in MiB for API task"
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  description = "CPU units for Worker task"
  type        = number
  default     = 256
}

variable "worker_memory" {
  description = "Memory in MiB for Worker task"
  type        = number
  default     = 512
}

variable "api_desired_count" {
  description = "Desired number of API tasks"
  type        = number
  default     = 2
}

variable "worker_desired_count" {
  description = "Desired number of Worker tasks"
  type        = number
  default     = 1
}

variable "app_secret_key" {
  description = "Application secret key for JWT signing (min 32 chars)"
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.app_secret_key) >= 32
    error_message = "app_secret_key must be at least 32 characters."
  }
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "Comma-separated list of allowed CORS origins for the API. Set after first deploy once the ALB DNS name is known (e.g. https://lbro-prod-alb.us-east-1.elb.amazonaws.com). Defaults to '*' for initial deployment."
  type        = string
  default     = "*"
}
