variable "export_name" {
  type        = string
  description = "AWS Data Exports export name, e.g. accountCUR"
  default     = "accountCUR"
}

variable "description" {
  type        = string
  description = "Description for the CUR 2.0 Data Export"
  default     = "TF2 FinOps CUR 2.0 source account export"
}

variable "destination_bucket_name" {
  type        = string
  description = "S3 bucket name in the lakehouse account that receives CUR 2.0 files"
}

variable "destination_prefix" {
  type        = string
  description = "Top-level S3 prefix for this source account export, usually the 12-digit account ID"
}

variable "destination_region" {
  type        = string
  description = "AWS region of the destination S3 bucket"
}

variable "billing_view_arn" {
  type        = string
  description = "Optional Billing View ARN. Leave empty to use the default COST_AND_USAGE_REPORT view available to the source account."
  default     = ""
}

variable "time_granularity" {
  type        = string
  description = "CUR time granularity"
  default     = "HOURLY"

  validation {
    condition     = contains(["HOURLY", "DAILY", "MONTHLY"], var.time_granularity)
    error_message = "time_granularity must be one of HOURLY, DAILY, or MONTHLY."
  }
}

variable "include_split_cost_allocation_data" {
  type        = bool
  description = "Include split cost allocation data in the export"
  default     = false
}

variable "overwrite" {
  type        = string
  description = "Data Exports overwrite mode"
  default     = "OVERWRITE_REPORT"
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
