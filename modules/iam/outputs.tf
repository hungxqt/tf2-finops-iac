output "lambda_role_arns" {
  description = "Map of Lambda worker execution role ARNs"
  value       = { for k, v in aws_iam_role.workers : k => v.arn }
  depends_on = [
    aws_iam_role_policy_attachment.lambda_vpc,
    aws_iam_role_policy.state,
    aws_iam_role_policy.cost_puller,
    aws_iam_role_policy.normalizer,
    aws_iam_role_policy.router,
    aws_iam_role_policy.audit_writer,
    aws_iam_role_policy.containment_worker,
    aws_iam_role_policy.workers_xray,
    aws_iam_role_policy.workers_sqs
  ]
}

output "permissions_boundary_arn" {
  description = "The ARN of the permissions boundary for Lambda worker roles"
  value       = aws_iam_policy.boundary.arn
}

output "member_telemetry_ingestion_role_arn" {
  description = "The ARN of the deployable member telemetry ingestion role"
  value       = var.create_member_telemetry_ingestion_role && length(aws_iam_role.member_telemetry_ingestion) > 0 ? aws_iam_role.member_telemetry_ingestion[0].arn : null
}

output "member_containment_policy_json" {
  description = "The JSON policy document for cross-account containment actions"
  value       = data.aws_iam_policy_document.member_containment.json
}
