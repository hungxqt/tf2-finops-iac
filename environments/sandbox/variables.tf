variable "aws_region" {
  type        = string
  description = "AWS region for sandbox environment"
  default     = "ap-southeast-1"
}

variable "project_name" {
  type        = string
  description = "The prefix name of the project"
  default     = "tf2-finops"
}

variable "environment" {
  type        = string
  description = "The environment name"
  default     = "sandbox"
}

variable "tags" {
  type        = map(string)
  description = "Common resources tags"
  default = {
    Environment = "sandbox"
    Project     = "tf2-finops"
    ManagedBy   = "Terraform"
  }
}

variable "request_image_digest" {
  type        = string
  description = "ECR image digest (sha256 hash) for the AI Request Lambda function"
  validation {
    condition     = can(regex("^sha256:[a-fA-F0-9]{64}$", var.request_image_digest))
    error_message = "The request_image_digest must be a valid sha256 hash (e.g. sha256:<64-hex-characters>)."
  }
}



variable "replica_region" {
  type        = string
  description = "AWS region for S3 cross-region replication"
  default     = "ap-southeast-2"
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

variable "alb_certificate_arn" {
  type        = string
  description = "ACM Certificate ARN for the internal ALB HTTPS listener"
}

variable "private_hosted_zone_id" {
  type        = string
  description = "Private Hosted Zone ID for internal Route 53 record"
  default     = ""
}

variable "private_dns_name" {
  type        = string
  description = "Private DNS name to assign to the internal ALB"
  default     = ""
}

variable "sigv4_service_name" {
  type        = string
  description = "SigV4 service name for authentication"
  default     = "ai-engine"
}

variable "destroyable" {
  type        = bool
  description = "Set to true to make S3 buckets, KMS keys, ECR, etc. destroyable (Sandbox exceptions)"
  default     = true
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

variable "cur_exports_json" {
  type        = string
  description = "JSON string (account-keyed map) of CUR 2.0 Data Exports config per member account. If set, this manual override takes precedence over the automatically generated config from telemetry_member_account_ids and cur_export_name. Advanced/explicit use only."
  default     = ""
}

variable "cur_export_name" {
  type        = string
  description = "The AWS Data Exports export name (e.g. accountCUR) used to generate prefixes"
  default     = "accountCUR"
}


variable "create_cur_export_bucket" {
  type        = bool
  description = "Set to true to create the dedicated CUR 2.0 / AWS Data Exports landing bucket via the lakehouse module."
  default     = false
}

variable "cur_export_bucket_name" {
  type        = string
  description = "Override name for the CUR 2.0 export landing bucket. Defaults to 'tf2-finops-cur-export-bucket' when empty."
  default     = ""
}

variable "cur_raw_prefix" {
  type        = string
  description = "S3 prefix under the CUR export bucket where AWS Data Exports writes raw CUR 2.0 Parquet files (e.g. 'finops-cur-export'). Used for IAM scoping and bcm-data-exports bucket policy."
  default     = ""
}

variable "enable_alb_https" {
  type        = bool
  description = "Enable HTTPS for the internal ALB. If false, HTTP port 80 is used (Sandbox only)."
  default     = true
}

variable "scheduler_enabled" {
  type        = bool
  description = "Whether to enable the EventBridge Scheduler schedule (triggers daily workflow runs). If false, the schedule state is DISABLED."
  default     = false
}

variable "bedrock_secret_arn" {
  type        = string
  description = "Secrets Manager secret ARN or name for Bedrock access. If set, IAM permissions will be granted to read this secret."
  default     = null
}

variable "synthetic_replay_enabled" {
  type        = bool
  description = "Enable sandbox-only synthetic replay harness"
  default     = false
}

variable "synthetic_replay_business_context_uri" {
  type        = string
  description = "The S3 URI for sandbox-only synthetic replay business/traffic context JSON file"
  default     = ""
}


