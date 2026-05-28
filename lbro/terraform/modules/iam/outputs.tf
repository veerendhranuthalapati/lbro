output "ecs_execution_role_arn"    { value = aws_iam_role.ecs_execution.arn }
output "ecs_api_task_role_arn"     { value = aws_iam_role.ecs_api_task.arn }
output "ecs_worker_task_role_arn"  { value = aws_iam_role.ecs_worker_task.arn }
output "ecs_worker_task_role_name" { value = aws_iam_role.ecs_worker_task.name }
