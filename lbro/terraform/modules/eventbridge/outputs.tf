output "deadline_sweep_schedule_arn"   { value = aws_scheduler_schedule.deadline_sweep.arn }
output "evidence_integrity_schedule_arn" { value = aws_scheduler_schedule.evidence_integrity.arn }
output "scheduler_role_arn"            { value = aws_iam_role.scheduler.arn }
