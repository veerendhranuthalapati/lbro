output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.ecs.alb_dns_name
}

output "api_service_name" {
  description = "ECS service name for the API"
  value       = module.ecs.api_service_name
}

output "worker_service_name" {
  description = "ECS service name for the Worker"
  value       = module.ecs.worker_service_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = module.rds.db_endpoint
  sensitive   = true
}

output "evidence_bucket_name" {
  description = "S3 bucket name for evidence vault"
  value       = module.s3.evidence_bucket_name
}

output "reports_bucket_name" {
  description = "S3 bucket name for reports"
  value       = module.s3.reports_bucket_name
}

output "incident_queue_url" {
  description = "SQS URL for incident processing queue"
  value       = module.sqs.incident_queue_url
}

output "notification_queue_url" {
  description = "SQS URL for notification sending queue"
  value       = module.sqs.notification_queue_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "sns_alerts_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}
