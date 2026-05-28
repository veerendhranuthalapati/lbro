output "alerts_sns_topic_arn" { value = local.alerts_topic_arn }
output "dashboard_name"       { value = aws_cloudwatch_dashboard.lbro.dashboard_name }
