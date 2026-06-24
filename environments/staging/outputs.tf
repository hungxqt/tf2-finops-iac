output "lakehouse_bucket_name" {
  description = "The name of the lakehouse S3 bucket"
  value       = module.lakehouse.lakehouse_bucket_name
}

output "lakehouse_bucket_arn" {
  description = "The ARN of the lakehouse S3 bucket"
  value       = module.lakehouse.lakehouse_bucket_arn
}

output "audit_bucket_name" {
  description = "The name of the audit S3 bucket"
  value       = module.lakehouse.audit_bucket_name
}

output "audit_bucket_arn" {
  description = "The ARN of the audit S3 bucket"
  value       = module.lakehouse.audit_bucket_arn
}

output "dynamodb_table_names" {
  description = "Map of DynamoDB table names"
  value       = module.orchestration.dynamodb_table_names
}

output "dynamodb_table_arns" {
  description = "Map of DynamoDB table ARNs"
  value       = module.orchestration.dynamodb_table_arns
}

output "state_machine_arn" {
  description = "The ARN of the Step Functions Orchestrator State Machine"
  value       = module.orchestration.state_machine_arn
}

output "scheduler_arn" {
  description = "The ARN of the EventBridge Scheduler schedule"
  value       = module.orchestration.scheduler_arn
}

output "lambda_function_names" {
  description = "Map of Lambda function names"
  value       = module.compute_lambda.lambda_function_names
}

output "lambda_function_arns" {
  description = "Map of Lambda function ARNs"
  value       = module.compute_lambda.lambda_function_arns
}

output "finance_topic_arn" {
  description = "The ARN of the Finance SNS Topic"
  value       = module.alerting.finance_topic_arn
}

output "engineering_topic_arn" {
  description = "The ARN of the Engineering SNS Topic"
  value       = module.alerting.engineering_topic_arn
}

output "dashboard_name" {
  description = "The name of the CloudWatch dashboard"
  value       = module.observability.dashboard_name
}
