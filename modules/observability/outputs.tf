output "dashboard_name" {
  description = "The name of the CloudWatch dashboard created"
  value       = aws_cloudwatch_dashboard.finops_dashboard.dashboard_name
}

output "alarm_names" {
  description = "List of names of created CloudWatch alarms"
  value = concat(
    [
      aws_cloudwatch_metric_alarm.step_functions_failed.alarm_name,
      aws_cloudwatch_metric_alarm.step_functions_timed_out.alarm_name,
      aws_cloudwatch_metric_alarm.stale_workflow.alarm_name,
      aws_cloudwatch_metric_alarm.drift_detected.alarm_name
    ],
    values({ for k, v in aws_cloudwatch_metric_alarm.lambda_errors : k => v.alarm_name })
  )
}

output "finance_topic_arn" {
  description = "The passed finance topic ARN"
  value       = var.finance_topic_arn
}

output "log_retention_days" {
  description = "The passed log retention days"
  value       = var.log_retention_days
}
