output "cluster_id"   { value = aws_ecs_cluster.this.id }
output "cluster_name" { value = aws_ecs_cluster.this.name }

output "alb_dns_name"  { value = aws_lb.this.dns_name }
output "alb_zone_id"   { value = aws_lb.this.zone_id }
output "alb_arn"       { value = aws_lb.this.arn }
# arn_suffix is the short form required by CloudWatch ALB metric dimensions
# e.g. "app/lbro-dev-alb/abc123def456" (not the full ARN)
output "alb_arn_suffix" { value = aws_lb.this.arn_suffix }

output "api_ecr_repository_url"    { value = aws_ecr_repository.api.repository_url }
output "worker_ecr_repository_url" { value = aws_ecr_repository.worker.repository_url }

output "api_service_name"    { value = aws_ecs_service.api.name }
output "worker_service_name" { value = aws_ecs_service.worker.name }

output "api_sg_id"    { value = aws_security_group.ecs_api.id }
output "worker_sg_id" { value = aws_security_group.ecs_worker.id }
