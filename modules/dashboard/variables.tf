variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., sandbox, staging, prod)"
}

variable "glue_database_name" {
  type        = string
  description = "The name of the Glue Catalog database"
}

variable "athena_workgroup_name" {
  type        = string
  description = "The name of the Athena workgroup"
}

variable "enable_quicksight" {
  type        = bool
  description = "Whether to provision QuickSight infrastructure hooks (defaults to false)"
  default     = false
}

variable "dashboard_kms_key_arn" {
  type        = string
  description = "The KMS Master Key ARN used to encrypt the S3 buckets"
}

variable "dashboard_data_prefix" {
  type        = string
  description = "The S3 folder prefix where precomputed dashboard JSON summaries are stored"
  default     = "summaries/"
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}

variable "cloudfront_acm_certificate_arn" {
  type        = string
  description = "The ARN of the ACM certificate in us-east-1 for CloudFront custom domain"
}

variable "cloudfront_aliases" {
  type        = list(string)
  description = "List of domain aliases (hostnames) for the CloudFront distribution"
}

variable "dashboard_geo_restriction_type" {
  type        = string
  description = "CloudFront geo restriction type (none, whitelist, blacklist)"
  default     = "blacklist"
}

variable "dashboard_geo_restriction_locations" {
  type        = list(string)
  description = "List of ISO 3166-1-alpha-2 country codes for geo restriction"
  default     = ["CU", "IR", "KP", "SY"]
}

variable "s3_logging_bucket_id" {
  type        = string
  description = "The ID of the S3 bucket for access logs"
}

variable "dashboard_assets_replica_bucket_arn" {
  type        = string
  description = "ARN of the replica S3 bucket for dashboard assets"
}

variable "dashboard_data_replica_bucket_arn" {
  type        = string
  description = "ARN of the replica S3 bucket for dashboard data"
}

variable "destroyable" {
  type        = bool
  description = "Set to true to make dashboard data S3 bucket destroyable (Sandbox exceptions)"
}

variable "dashboard_replica_kms_key_arn" {
  type        = string
  description = "The ARN of the KMS key in the replica region"
}

variable "auth_cookie_ttl" {
  type        = number
  description = "The cookie TTL in seconds"
  default     = 3600
}

variable "auth_session_ttl" {
  type        = number
  description = "The Cognito session token validity duration in seconds"
  default     = 3600
}

variable "group_name_finance" {
  type        = string
  description = "Cognito group name for Finance Read-Only users"
  default     = "finops-finance-readonly"
}

variable "group_name_engineering" {
  type        = string
  description = "Cognito group name for Engineering Operator users"
  default     = "finops-engineering-operator"
}

variable "group_name_cdo" {
  type        = string
  description = "Cognito group name for CDO Admin users"
  default     = "finops-cdo-admin"
}

