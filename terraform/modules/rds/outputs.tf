output "db_endpoint"           { value = aws_db_instance.main.address }
output "db_port"               { value = aws_db_instance.main.port }
output "db_name"               { value = aws_db_instance.main.db_name }
output "db_identifier"         { value = aws_db_instance.main.identifier }
output "db_security_group_id"  { value = aws_security_group.rds.id }
