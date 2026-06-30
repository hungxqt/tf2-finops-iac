variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g. sandbox, staging, prod)"
}

variable "destroyable" {
  type        = bool
  description = "Set to true to make ECR repository destroyable (Sandbox exceptions)"
}

variable "aiops_source_ecr_repository_arn" {
  type        = string
  description = "ARN of the AIOps source ECR repository"
  default     = ""
}

variable "aiops_source_registry_id" {
  type        = string
  description = "Registry ID of the source ECR repository"
  default     = ""
}

variable "lambda_web_adapter_image" {
  type        = string
  description = "Docker image URI of the Lambda Web Adapter to copy"
  default     = "public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4"
}

variable "kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key ARN for CloudWatch logs encryption"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}
