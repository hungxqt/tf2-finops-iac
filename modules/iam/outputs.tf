output "step_functions_role_arn" {
  description = "The ARN of the Step Functions execution role"
  value       = aws_iam_role.step_functions.arn
}

output "lambda_role_arns" {
  description = "Map of Lambda worker execution role ARNs"
  value       = { for k, v in aws_iam_role.workers : k => v.arn }
}

output "permissions_boundary_arn" {
  description = "The ARN of the permissions boundary for Lambda worker roles"
  value       = aws_iam_policy.boundary.arn
}

output "member_read_policy_json" {
  description = "The JSON policy document for cross-account cost reading"
  value       = data.aws_iam_policy_document.member_read.json
}

output "member_containment_policy_json" {
  description = "The JSON policy document for cross-account containment actions"
  value       = data.aws_iam_policy_document.member_containment.json
}

output "scheduler_role_arn" {
  description = "The ARN of the EventBridge Scheduler execution role"
  value       = aws_iam_role.scheduler.arn
}

output "cdo_caller_role_arn" {
  description = "The ARN of the SigV4-compatible CDO caller role"
  value       = aws_iam_role.cdo_caller.arn
}


