output "incident_events_queue_url"       { value = aws_sqs_queue.main["incident_events"].id }
output "incident_events_queue_arn"       { value = aws_sqs_queue.main["incident_events"].arn }
output "incident_events_queue_name"      { value = aws_sqs_queue.main["incident_events"].name }

output "containment_actions_queue_url"   { value = aws_sqs_queue.main["containment_actions"].id }
output "containment_actions_queue_arn"   { value = aws_sqs_queue.main["containment_actions"].arn }
output "containment_actions_queue_name"  { value = aws_sqs_queue.main["containment_actions"].name }

output "notification_dispatch_queue_url"  { value = aws_sqs_queue.main["notification_dispatch"].id }
output "notification_dispatch_queue_arn"  { value = aws_sqs_queue.main["notification_dispatch"].arn }
output "notification_dispatch_queue_name" { value = aws_sqs_queue.main["notification_dispatch"].name }

output "all_queue_arns" {
  value = [for q in aws_sqs_queue.main : q.arn]
}

output "all_dlq_arns" {
  value = [for q in aws_sqs_queue.dlq : q.arn]
}
