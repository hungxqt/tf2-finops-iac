output "ecr_repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.ai_engine.repository_url
}

output "request_lambda_function_name" {
  description = "The name of the AI Request Lambda function"
  value       = aws_lambda_function.request.function_name
}

output "request_lambda_alias_arn" {
  description = "The ARN of the AI Request Lambda live alias"
  value       = aws_lambda_alias.request.arn
}

output "worker_lambda_function_name" {
  description = "The name of the AI Worker Lambda function"
  value       = aws_lambda_function.worker.function_name
}

output "worker_lambda_alias_arn" {
  description = "The ARN of the AI Worker Lambda live alias"
  value       = aws_lambda_alias.worker.arn
}

output "request_execution_role_arn" {
  description = "The ARN of the AI Request Lambda execution role"
  value       = aws_iam_role.request.arn
}

output "worker_execution_role_arn" {
  description = "The ARN of the AI Worker Lambda execution role"
  value       = aws_iam_role.worker.arn
}

output "worker_event_source_mapping_uuid" {
  description = "The UUID of the SQS worker event source mapping"
  value       = aws_lambda_event_source_mapping.worker.uuid
}

output "ai_runtime_log_group_names" {
  description = "List of CloudWatch log group names created by the runtime"
  value = [
    aws_cloudwatch_log_group.request.name,
    aws_cloudwatch_log_group.worker.name
  ]
}

output "alb_dns_name" {
  description = "The DNS name of the internal ALB"
  value       = aws_lb.ai.dns_name
}

output "alb_arn" {
  description = "The ARN of the internal ALB"
  value       = aws_lb.ai.arn
}

output "alb_security_group_id" {
  description = "The ID of the security group for the internal ALB"
  value       = aws_security_group.alb.id
}

