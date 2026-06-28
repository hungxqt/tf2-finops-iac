output "ecr_repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.ai_engine.repository_url
}

output "ecr_repository_name" {
  description = "The name of the ECR repository"
  value       = aws_ecr_repository.ai_engine.name
}

output "ecr_repository_arn" {
  description = "The ARN of the ECR repository"
  value       = aws_ecr_repository.ai_engine.arn
}

output "wrapper_build_project_name" {
  description = "The name of the CodeBuild wrapper image publish project"
  value       = aws_codebuild_project.wrapper_build.name
}

output "wrapper_build_role_arn" {
  description = "The IAM role ARN of the CodeBuild project"
  value       = aws_iam_role.codebuild.arn
}

output "latest_wrapper_image_parameter_name" {
  description = "The SSM parameter name storing the latest wrapped image URI"
  value       = "/tf2-finops/${var.environment}/ai-wrapper/latest-image-uri"
}
