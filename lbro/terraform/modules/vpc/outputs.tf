output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (ECS tasks)"
  value       = aws_subnet.private[*].id
}

output "db_subnet_ids" {
  description = "Database subnet IDs (isolated)"
  value       = aws_subnet.db[*].id
}

output "db_subnet_group_name" {
  description = "RDS subnet group name"
  value       = aws_db_subnet_group.this.name
}

output "availability_zones" {
  description = "AZs used"
  value       = local.azs
}

output "vpc_endpoint_sg_id" {
  description = "Security group for VPC interface endpoints"
  value       = aws_security_group.vpc_endpoints.id
}

output "nat_gateway_ids" {
  description = "NAT Gateway IDs"
  value       = aws_nat_gateway.this[*].id
}
