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

variable "telemetry_member_account_ids" {
  type        = list(string)
  description = "AWS Account IDs for member accounts from which CDO pulls telemetry"
  default     = []
}

variable "telemetry_member_role_name" {
  type        = string
  description = "The IAM role name expected in member accounts for CDO telemetry ingestion"
  default     = "cdo-telemetry-ingestion-role"
}

variable "cur_source_bucket_arn" {
  type        = string
  description = "The ARN of the member CUR source S3 bucket"
  default     = ""
}

variable "cur_source_prefix" {
  type        = string
  description = "The prefix of the CUR source in the member bucket"
  default     = ""
}

variable "cur_export_name" {
  type        = string
  description = "The AWS Data Exports export name (e.g. accountCUR) used to generate prefixes"
  default     = "accountCUR"
}


variable "create_member_telemetry_ingestion_role" {
  type        = bool
  description = "Whether to create the member telemetry ingestion role in this deployment context"
  default     = false
}

variable "trusted_cost_puller_role_arns" {
  type        = list(string)
  description = "The ARNs of trusted cost puller IAM roles allowed to assume the ingestion role"
  default     = []
}

variable "athena_results_bucket_arn" {
  type        = string
  description = "The ARN of the Athena query results S3 bucket"
  default     = ""
}

variable "athena_workgroup_arn" {
  type        = string
  description = "The ARN of the Athena workgroup"
  default     = ""
}

variable "glue_database_arn" {
  type        = string
  description = "The ARN of the Glue Catalog database"
  default     = ""
}

variable "glue_table_arns" {
  type        = list(string)
  description = "Glue Catalog table ARNs that Lambda worker IAM may resolve through Athena"
  default     = []
}

variable "ai_payload_idempotency_table_arn" {
  type        = string
  description = "ARN of the DynamoDB ai_payload_idempotency table. Used to grant vpc_alb_caller a least-privilege inline policy scoped to only this table."
  default     = ""
}

variable "trusted_tenant_ids" {
  type        = list(string)
  description = "Allowed tenant IDs used as sts:ExternalId and aws:RequestTag/tenant_id conditions on the member telemetry ingestion role trust policy. Required when create_member_telemetry_ingestion_role = true."
  default     = []
}
