variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., sandbox, staging, prod)"
}

variable "scheduler_expression" {
  type        = string
  description = "EventBridge Scheduler schedule expression (e.g., rate(24 hours))"
  default     = "rate(24 hours)"
}

variable "step_functions_role_arn" {
  type        = string
  description = "ARN of the IAM role for Step Functions execution"
}

variable "scheduler_role_arn" {
  type        = string
  description = "ARN of the IAM role for EventBridge Scheduler triggering Step Functions"
}

variable "lambda_function_arns" {
  type        = map(string)
  description = "Map of Lambda function/alias ARNs for Step Functions state transitions"
}

variable "ddb_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for DynamoDB encryption"
}

variable "audit_bucket_name" {
  type        = string
  description = "The name of the audit S3 bucket"
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}

variable "finance_alerts_topic_arn" {
  type        = string
  description = "ARN of the SNS topic for finance alerts"
}

variable "engineering_alerts_topic_arn" {
  type        = string
  description = "ARN of the SNS topic for engineering alerts"
}

