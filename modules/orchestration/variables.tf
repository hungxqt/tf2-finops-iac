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

variable "sqs_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for SQS encryption"
}

variable "ai_engine_contract_version" {
  type        = string
  description = "Version of the AI Engine contract"
  default     = "v1"
}



variable "cloudwatch_log_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for CloudWatch Log Group encryption"
}

variable "scheduler_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for EventBridge Scheduler encryption"
}

variable "cur_retry_interval_seconds" {
  type        = number
  description = "Wait duration in seconds before retrying CUR pull"
  default     = 3600
}

variable "destroyable" {
  type        = bool
  description = "Set to true to make orchestration DynamoDB tables destroyable (Sandbox exceptions)"
}

variable "scheduler_enabled" {
  type        = bool
  description = "Whether to enable the EventBridge Scheduler schedule. If false, the schedule state is DISABLED."
  default     = false
}

variable "analysis_target_account_ids" {
  type        = list(string)
  description = "List of linked/member AWS account IDs to analyze"
  default     = []
}

