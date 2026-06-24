output "state_bucket_name" {
  description = "The name of the Terraform remote state S3 bucket"
  value       = aws_s3_bucket.state.id
}

output "state_kms_key_arn" {
  description = "The ARN of the KMS key for state encryption"
  value       = aws_kms_key.state.arn
}

output "github_actions_role_arn" {
  description = "The ARN of the GitHub Actions execution OIDC role"
  value       = aws_iam_role.github_actions.arn
}
