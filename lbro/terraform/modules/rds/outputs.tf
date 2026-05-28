output "db_instance_id"  { value = aws_db_instance.this.id }
output "db_endpoint"     { value = aws_db_instance.this.endpoint }
output "db_host"         { value = aws_db_instance.this.address }
output "db_port"         { value = aws_db_instance.this.port }
output "db_name"         { value = aws_db_instance.this.db_name }
output "rds_sg_id"       { value = aws_security_group.rds.id }
output "rds_proxy_sg_id" { value = aws_security_group.rds_proxy.id }

output "proxy_endpoint" {
  description = "RDS Proxy endpoint (null when enable_rds_proxy=false)"
  value       = var.enable_rds_proxy ? aws_db_proxy.this[0].endpoint : aws_db_instance.this.address
}

output "replica_endpoint" {
  value = var.create_read_replica ? aws_db_instance.replica[0].address : null
}
