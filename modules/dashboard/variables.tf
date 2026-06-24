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

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
