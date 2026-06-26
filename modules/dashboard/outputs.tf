output "dashboard_url" {
  description = "The URL of the CloudFront dashboard distribution"
  value       = "https://${aws_cloudfront_distribution.dashboard.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "The ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.dashboard.id
}

output "cloudfront_domain_name" {
  description = "The domain name of the CloudFront distribution"
  value       = aws_cloudfront_distribution.dashboard.domain_name
}

output "asset_bucket_name" {
  description = "The name of the static asset S3 bucket"
  value       = aws_s3_bucket.dashboard_assets.id
}

output "data_bucket_name" {
  description = "The name of the dashboard data S3 bucket"
  value       = aws_s3_bucket.dashboard_data.id
}

output "data_prefix" {
  description = "The S3 folder prefix where precomputed dashboard JSON summaries are stored"
  value       = var.dashboard_data_prefix
}

output "cognito_user_pool_id" {
  description = "The Cognito User Pool ID"
  value       = aws_cognito_user_pool.dashboard.id
}

output "cognito_user_pool_client_id" {
  description = "The Cognito User Pool Client ID"
  value       = aws_cognito_user_pool_client.dashboard.id
}

output "cognito_identity_pool_id" {
  description = "The Cognito Identity Pool ID"
  value       = aws_cognito_identity_pool.dashboard.id
}

output "athena_named_query_ids" {
  description = "Map of Athena named query names to their IDs"
  value       = { for k, v in aws_athena_named_query.queries : k => v.id }
}

output "quicksight_enabled" {
  description = "Boolean flag indicating whether QuickSight resources were enabled"
  value       = var.enable_quicksight
}

output "edge_auth_viewer_lambda_qualified_arn" {
  description = "The qualified ARN of the viewer request authentication Lambda@Edge function"
  value       = aws_lambda_function.edge_viewer_auth.qualified_arn
}

output "edge_auth_origin_lambda_qualified_arn" {
  description = "The qualified ARN of the origin request authentication Lambda@Edge function"
  value       = aws_lambda_function.edge_origin_sigv4.qualified_arn
}

output "vpc_origin_id" {
  description = "The ID of the CloudFront VPC origin"
  value       = aws_cloudfront_vpc_origin.api.id
}

output "api_origin_id" {
  description = "The origin ID used for the VPC ALB API origin"
  value       = "VpcOrigin-API"
}

output "cognito_group_names" {
  description = "The names of the Cognito user groups created"
  value = [
    aws_cognito_user_group.finance.name,
    aws_cognito_user_group.engineering.name,
    aws_cognito_user_group.cdo.name
  ]
}

