output "state_machine_arn" {
  description = "The ARN of the Step Functions State Machine"
  value       = aws_sfn_state_machine.workflow.arn
}

output "scheduler_arn" {
  description = "The ARN of the EventBridge Scheduler schedule"
  value       = aws_scheduler_schedule.run_workflow.arn
}

output "dynamodb_table_names" {
  description = "Map of DynamoDB table names created"
  value = {
    run_state       = aws_dynamodb_table.run_state.name
    anomaly         = aws_dynamodb_table.anomaly.name
    routing_state   = aws_dynamodb_table.routing_state.name
    audit           = aws_dynamodb_table.audit.name
    dashboard_views = aws_dynamodb_table.dashboard_views.name
    account_policy  = aws_dynamodb_table.account_policy.name
  }
}

output "dynamodb_table_arns" {
  description = "Map of DynamoDB table ARNs created"
  value = {
    run_state       = aws_dynamodb_table.run_state.arn
    anomaly         = aws_dynamodb_table.anomaly.arn
    routing_state   = aws_dynamodb_table.routing_state.arn
    audit           = aws_dynamodb_table.audit.arn
    dashboard_views = aws_dynamodb_table.dashboard_views.arn
    account_policy  = aws_dynamodb_table.account_policy.arn
  }
}
