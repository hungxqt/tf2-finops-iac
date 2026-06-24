output "lambda_function_names" {
  description = "Map of created Lambda function names"
  value       = { for k, v in aws_lambda_function.workers : k => v.function_name }
}

output "lambda_function_arns" {
  description = "Map of created Lambda function ARNs"
  value       = { for k, v in aws_lambda_function.workers : k => v.arn }
}

output "lambda_alias_arns" {
  description = "Map of Lambda alias (stable/canary) ARNs"
  value       = { for k, v in aws_lambda_alias.stable : k => v.arn }
}

output "audit_writer_function_name" {
  description = "The function name of the audit writer lambda"
  value       = aws_lambda_function.workers["audit_writer"].function_name
}

output "ai_client_function_name" {
  description = "The function name of the AI client lambda"
  value       = aws_lambda_function.workers["ai_client"].function_name
}
