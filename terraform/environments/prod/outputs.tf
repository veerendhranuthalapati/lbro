output "api_url"              { value = "https://${module.ecs.alb_dns_name}" }
output "ecr_api_url"          { value = module.ecs.api_ecr_repository_url }
output "ecr_worker_url"       { value = module.ecs.worker_ecr_repository_url }
output "evidence_bucket"      { value = module.s3.evidence_bucket_id }
output "db_proxy_endpoint"    { value = module.rds.proxy_endpoint; sensitive = true }
output "alerts_sns_topic_arn" { value = aws_sns_topic.alerts.arn }
output "waf_web_acl_arn"      { value = module.waf.web_acl_arn }
output "backup_vault_arn"     { value = module.backup.vault_arn }
output "cloudwatch_dashboard" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home#dashboards:name=${module.monitoring.dashboard_name}"
}
