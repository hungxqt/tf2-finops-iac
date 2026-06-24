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

variable "lambda_security_group_id" {
  type        = string
  description = "The security group ID allowing egress for VPC-attached Lambda execution"
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

variable "ai_engine_endpoint_url" {
  type        = string
  description = "AI Engine API endpoint URL"
  default     = ""
}

variable "ai_engine_secret_name" {
  type        = string
  description = "AI Engine client auth credentials secret name in Secrets Manager"
  default     = ""
}

variable "containment_apply_enabled" {
  type        = bool
  description = "True if automatic containment action is enabled (Sandbox/Staging dry-run/apply controls)"
  default     = false
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention in days"
  default     = 14
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
