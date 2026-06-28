output "ecr_repository_url" {
  description = "The URL of the shared ECR repository"
  value       = module.ai_wrapper_build.ecr_repository_url
}

output "ecr_repository_arn" {
  description = "The ARN of the shared ECR repository"
  value       = module.ai_wrapper_build.ecr_repository_arn
}

output "ecr_repository_name" {
  description = "The name of the shared ECR repository"
  value       = module.ai_wrapper_build.ecr_repository_name
}

output "wrapper_build_project_name" {
  description = "The name of the shared CodeBuild wrapper image publish project"
  value       = module.ai_wrapper_build.wrapper_build_project_name
}

output "wrapper_build_role_arn" {
  description = "The IAM role ARN of the shared CodeBuild project"
  value       = module.ai_wrapper_build.wrapper_build_role_arn
}

output "latest_wrapper_image_parameter_name" {
  description = "The SSM parameter name storing the latest wrapped image URI"
  value       = module.ai_wrapper_build.latest_wrapper_image_parameter_name
}
