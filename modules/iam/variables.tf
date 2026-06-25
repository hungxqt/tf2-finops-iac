variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., sandbox, staging, prod)"
}

variable "lakehouse_bucket_arn" {
  type        = string
  description = "ARN of the lakehouse S3 bucket"
}

variable "audit_bucket_arn" {
  type        = string
  description = "ARN of the audit S3 bucket"
}

variable "dynamodb_table_arns" {
  type        = list(string)
  description = "List of DynamoDB table ARNs"
  default     = []
}

variable "kms_key_arns" {
  type        = list(string)
  description = "List of KMS Key ARNs for decryption"
  default     = []
}

variable "containment_apply_enabled" {
  type        = bool
  description = "Whether automatic containment action apply is enabled"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}

variable "queue_arns" {
  type        = list(string)
  description = "List of SQS queue ARNs for worker access"
  default     = []
}

variable "sns_topic_arns" {
  type        = list(string)
  description = "List of SNS topic ARNs for router alert delivery"
  default     = []
}
