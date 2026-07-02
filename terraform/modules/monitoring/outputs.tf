output "dlq_alarm_arn"        { value = aws_cloudwatch_metric_alarm.dlq_depth.arn }
output "api_cpu_alarm_arn"    { value = aws_cloudwatch_metric_alarm.api_cpu_high.arn }
output "rds_cpu_alarm_arn"    { value = aws_cloudwatch_metric_alarm.rds_cpu.arn }
output "dashboard_name"       { value = aws_cloudwatch_dashboard.lbro.dashboard_name }
