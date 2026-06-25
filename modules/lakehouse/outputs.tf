output "lakehouse_bucket_name" {
  description = "The name of the S3 bucket for cost data"
  value       = aws_s3_bucket.lakehouse.id
}

output "lakehouse_bucket_arn" {
  description = "The ARN of the S3 bucket for cost data"
  value       = aws_s3_bucket.lakehouse.arn
}

output "audit_bucket_name" {
  description = "The name of the S3 bucket for audit data"
  value       = aws_s3_bucket.audit.id
}

output "audit_bucket_arn" {
  description = "The ARN of the S3 bucket for audit data"
  value       = aws_s3_bucket.audit.arn
}

output "glue_database_name" {
  description = "The name of the Glue Catalog database"
  value       = aws_glue_catalog_database.lakehouse.name
}

output "athena_workgroup_name" {
  description = "The name of the Athena workgroup"
  value       = aws_athena_workgroup.lakehouse.name
}

output "data_kms_key_arn" {
  description = "The ARN of the KMS key for data encryption"
  value       = aws_kms_key.data.arn
}

output "audit_kms_key_arn" {
  description = "The ARN of the KMS key for audit encryption"
  value       = aws_kms_key.audit.arn
}

output "ddb_kms_key_arn" {
  description = "The ARN of the KMS key for DynamoDB encryption"
  value       = aws_kms_key.ddb.arn
}

output "logging_bucket_name" {
  description = "The name of the S3 bucket for access logging"
  value       = aws_s3_bucket.logging.id
}

