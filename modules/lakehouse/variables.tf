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

variable "lakehouse_replica_bucket_arn" {
  type        = string
  description = "ARN of the replica S3 bucket for lakehouse data"
}

variable "audit_replica_bucket_arn" {
  type        = string
  description = "ARN of the replica S3 bucket for audit records"
}

variable "athena_replica_bucket_arn" {
  type        = string
  description = "ARN of the replica S3 bucket for Athena query results"
}

variable "destroyable" {
  type        = bool
  description = "Set to true to make S3 buckets, KMS keys, ECR, etc. destroyable (Sandbox exceptions)"
}

variable "create_cur_export_bucket" {
  type        = bool
  description = "Set to true to create the dedicated CUR 2.0 / AWS Data Exports landing bucket managed by this module. Set to false when the bucket is provisioned externally or pre-exists."
  default     = false
}

variable "cur_export_bucket_name" {
  type        = string
  description = "Name for the CUR 2.0 export landing bucket. Defaults to 'tf2-finops-cur-export-bucket' when empty."
  default     = ""
}

variable "cur_raw_prefix" {
  type        = string
  description = "S3 prefix under the CUR export bucket where AWS Data Exports writes raw CUR 2.0 files (e.g. 'my-export'). Used to scope the bcm-data-exports bucket policy statement and the IAM GetObject grant for cost_puller."
  default     = ""
}

variable "cur_export_name" {
  type        = string
  description = "The AWS Data Exports export name (e.g. accountCUR) used to generate prefixes"
  default     = "accountCUR"
}

variable "telemetry_member_account_ids" {
  type        = list(string)
  description = "AWS Account IDs for member accounts from which CDO pulls telemetry"
  default     = []
}


