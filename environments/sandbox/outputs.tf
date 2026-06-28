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

output "dashboard_url" {
  description = "The URL of the CloudFront dashboard distribution"
  value       = module.dashboard.dashboard_url
}

output "dashboard_asset_bucket_name" {
  description = "The name of the static asset S3 bucket"
  value       = module.dashboard.asset_bucket_name
}

output "dashboard_data_bucket_name" {
  description = "The name of the dashboard data S3 bucket"
  value       = module.dashboard.data_bucket_name
}

output "dashboard_data_prefix" {
  description = "The S3 folder prefix where precomputed dashboard JSON summaries are stored"
  value       = module.dashboard.data_prefix
}

output "dashboard_cloudfront_distribution_id" {
  description = "The ID of the CloudFront distribution"
  value       = module.dashboard.cloudfront_distribution_id
}

output "dashboard_cognito_user_pool_id" {
  description = "The Cognito User Pool ID"
  value       = module.dashboard.cognito_user_pool_id
}

output "dashboard_cognito_user_pool_client_id" {
  description = "The Cognito User Pool Client ID"
  value       = module.dashboard.cognito_user_pool_client_id
}

output "dashboard_cognito_identity_pool_id" {
  description = "The Cognito Identity Pool ID"
  value       = module.dashboard.cognito_identity_pool_id
}

output "dashboard_athena_named_query_ids" {
  description = "Map of Athena named query names to their IDs"
  value       = module.dashboard.athena_named_query_ids
}

output "request_lambda_function_name" {
  description = "The name of the AI Request Lambda function"
  value       = module.ai_runtime_lambda.request_lambda_function_name
}

output "request_lambda_alias_arn" {
  description = "The ARN of the AI Request Lambda live alias"
  value       = module.ai_runtime_lambda.request_lambda_alias_arn
}

output "request_execution_role_arn" {
  description = "The ARN of the AI Request Lambda execution role"
  value       = module.ai_runtime_lambda.request_execution_role_arn
}

output "ai_runtime_log_group_names" {
  description = "List of CloudWatch log group names created by the runtime"
  value       = module.ai_runtime_lambda.ai_runtime_log_group_names
}

output "rollback_status_queue_url" {
  description = "The URL of the rollback status SQS queue"
  value       = module.orchestration.rollback_status_queue_url
}

output "rollback_status_queue_arn" {
  description = "The ARN of the rollback status SQS queue"
  value       = module.orchestration.rollback_status_queue_arn
}

output "private_alb_dns_name" {
  description = "The DNS name of the internal ALB"
  value       = module.ai_runtime_lambda.alb_dns_name
}

output "private_alb_arn" {
  description = "The ARN of the internal ALB"
  value       = module.ai_runtime_lambda.alb_arn
}

output "private_alb_security_group_id" {
  description = "The ID of the security group for the internal ALB"
  value       = module.ai_runtime_lambda.alb_security_group_id
}

output "private_alb_endpoint" {
  description = "The HTTPS base URL for accessing the private ALB"
  value       = var.private_hosted_zone_id != "" && var.private_dns_name != "" ? "https://${var.private_dns_name}" : "https://${module.ai_runtime_lambda.alb_dns_name}"
}

output "glue_catalog_tables" {
  description = "Map of Glue database and tables"
  value       = module.lakehouse.glue_catalog_tables
}




