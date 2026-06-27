variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., sandbox, staging, prod)"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "List of private subnet IDs for VPC-attached Lambda execution"
}

variable "lambda_role_arns" {
  type        = map(string)
  description = "Map of execution role ARNs for each Lambda worker"
}

variable "lakehouse_bucket_name" {
  type        = string
  description = "The name of the S3 bucket for cost data"
}

variable "audit_bucket_name" {
  type        = string
  description = "The name of the S3 bucket for audit records"
}

variable "dynamodb_table_names" {
  type        = map(string)
  description = "Map of DynamoDB table names for worker read/write"
  default     = {}
}

variable "containment_apply_enabled" {
  type        = bool
  description = "True if automatic containment action is enabled (Sandbox/Staging dry-run/apply controls)"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "ap-southeast-1"
}

variable "cloudwatch_log_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for CloudWatch Log Group encryption"
}

variable "lambda_env_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for Lambda environment variables encryption at rest"
}

variable "sqs_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for SQS DLQ encryption"
}

variable "vpc_id" {
  type        = string
  description = "The ID of the VPC"
}

variable "vpc_endpoint_security_group_id" {
  type        = string
  description = "The security group ID of the VPC interface endpoints"
}

variable "alb_base_url" {
  type        = string
  description = "The private internal ALB base URL"
}

variable "sigv4_service_name" {
  type        = string
  description = "SigV4 service name for authentication"
  default     = "ai-engine"
}

variable "reserved_concurrent_executions" {
  type        = number
  description = "The amount of reserved concurrent executions for each Lambda worker. Set to null to disable."
  default     = null
}

variable "cur_source_bucket" {
  type        = string
  description = "The source S3 bucket where raw CUR is delivered"
  default     = ""
}

variable "cur_source_prefix" {
  type        = string
  description = "The prefix under cur_source_bucket for CUR files"
  default     = ""
}

variable "cur_delay_threshold_hours" {
  type        = number
  description = "The threshold in hours to consider CUR as delayed"
  default     = 36
}

variable "ce_lookback_window_days" {
  type        = number
  description = "The lookback window in days for Cost Explorer queries"
  default     = 30
}

variable "traffic_metric_identifiers" {
  type        = list(string)
  description = "List of identifiers for traffic volume query (e.g. ALB names)"
  default     = []
}

variable "athena_workgroup_name" {
  type        = string
  description = "The name of the Athena workgroup"
  default     = ""
}

variable "glue_database_name" {
  type        = string
  description = "The name of the Glue Catalog database"
  default     = ""
}

variable "cur_data_table_name" {
  type        = string
  description = "The name of the Glue Catalog table for curated cost data"
  default     = ""
}

variable "athena_results_bucket_name" {
  type        = string
  description = "The name of the Athena query results S3 bucket"
  default     = ""
}

