variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., sandbox, staging, prod)"
}

variable "aws_region" {
  type        = string
  description = "AWS region for lakehouse deployment"
}

variable "audit_retention_days" {
  type        = number
  description = "Retention period for audit objects (at least 90 days)"
  default     = 90
  validation {
    condition     = var.audit_retention_days >= 90
    error_message = "Audit retention period must be at least 90 days."
  }
}

variable "athena_query_bytes_cutoff" {
  type        = number
  description = "Athena scan query bytes cutoff limit"
  default     = 10000000000 # 10 GB
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
