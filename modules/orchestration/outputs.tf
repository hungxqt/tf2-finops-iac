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
    run_state          = aws_dynamodb_table.run_state.name
    anomaly            = aws_dynamodb_table.anomaly.name
    routing_state      = aws_dynamodb_table.routing_state.name
    audit              = aws_dynamodb_table.audit.name
    dashboard_views    = aws_dynamodb_table.dashboard_views.name
    account_policy     = aws_dynamodb_table.account_policy.name
    error_budget       = aws_dynamodb_table.error_budget.name
    rollback_cache     = aws_dynamodb_table.rollback_cache.name
    ai_payload_idempotency = aws_dynamodb_table.ai_payload_idempotency.name
  }
}

output "dynamodb_table_arns" {
  description = "Map of DynamoDB table ARNs created"
  value = {
    run_state          = aws_dynamodb_table.run_state.arn
    anomaly            = aws_dynamodb_table.anomaly.arn
    routing_state      = aws_dynamodb_table.routing_state.arn
    audit              = aws_dynamodb_table.audit.arn
    dashboard_views    = aws_dynamodb_table.dashboard_views.arn
    account_policy     = aws_dynamodb_table.account_policy.arn
    error_budget       = aws_dynamodb_table.error_budget.arn
    rollback_cache     = aws_dynamodb_table.rollback_cache.arn
    ai_payload_idempotency = aws_dynamodb_table.ai_payload_idempotency.arn
  }
}

output "idempotency_table_name" {
  description = "Name of the AI payload idempotency DynamoDB table (contract hot path)"
  value       = aws_dynamodb_table.ai_payload_idempotency.name
}

output "rollback_status_queue_url" {
  description = "The URL of the rollback and status SQS queue"
  value       = aws_sqs_queue.rollback_status_queue.id
}

output "rollback_status_queue_arn" {
  description = "The ARN of the rollback and status SQS queue"
  value       = aws_sqs_queue.rollback_status_queue.arn
}

output "audit_bucket_name" {
  description = "The passed audit bucket name"
  value       = var.audit_bucket_name
}

output "step_functions_role_arn" {
  description = "The ARN of the Step Functions execution role"
  value       = aws_iam_role.step_functions.arn
}

output "scheduler_role_arn" {
  description = "The ARN of the EventBridge Scheduler execution role"
  value       = aws_iam_role.scheduler.arn
}


