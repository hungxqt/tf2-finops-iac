variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., sandbox, staging, prod)"
}

variable "finance_email_subscriptions" {
  type        = list(string)
  description = "List of email addresses for finance alerts"
  default     = []
}

variable "engineering_email_subscriptions" {
  type        = list(string)
  description = "List of email addresses for engineering alerts"
  default     = []
}

variable "sns_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for SNS topic encryption"
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
