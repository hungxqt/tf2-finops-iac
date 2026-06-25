variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g. sandbox, staging, prod)"
}

# tflint-ignore: terraform_unused_declarations
variable "aws_region" {
  type        = string
  description = "The AWS region"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "VPC private subnet IDs for the Lambda functions"
}

variable "lambda_security_group_id" {
  type        = string
  description = "Security group ID for the Lambda functions"
}

variable "request_image_uri" {
  type        = string
  description = "ECR image URI for the AI Request Lambda function"
}

variable "worker_image_uri" {
  type        = string
  description = "ECR image URI for the AI Worker Lambda function"
}

variable "request_reserved_concurrency" {
  type        = number
  description = "Reserved concurrency for the AI Request Lambda function"
  default     = null
}

variable "worker_reserved_concurrency" {
  type        = number
  description = "Reserved concurrency for the AI Worker Lambda function"
  default     = null
}

variable "worker_batch_size" {
  type        = number
  description = "SQS batch size for the AI Worker Lambda function"
  default     = 10
}

variable "worker_max_concurrency" {
  type        = number
  description = "Maximum concurrency for the SQS event source mapping"
  default     = null
}

variable "request_timeout_seconds" {
  type        = number
  description = "Timeout in seconds for the AI Request Lambda function"
  default     = 60
}

variable "worker_timeout_seconds" {
  type        = number
  description = "Timeout in seconds for the AI Worker Lambda function"
  default     = 300
}

variable "worker_ephemeral_storage_mb" {
  type        = number
  description = "Ephemeral storage in MB for the AI Worker Lambda function"
  default     = 512
}

variable "detect_queue_url" {
  type        = string
  description = "URL of the primary SQS detection queue"
}

variable "detect_queue_arn" {
  type        = string
  description = "ARN of the primary SQS detection queue"
}

variable "results_table_name" {
  type        = string
  description = "Name of the DynamoDB AI results table"
}

variable "results_table_arn" {
  type        = string
  description = "ARN of the DynamoDB AI results table"
}

variable "curated_bucket_name" {
  type        = string
  description = "Name of the curated S3 bucket"
}

variable "evidence_bucket_name" {
  type        = string
  description = "Name of the evidence S3 bucket"
}

variable "evidence_prefix" {
  type        = string
  description = "S3 prefix/path for audit evidence"
  default     = "evidence/"
}

variable "secret_arns" {
  type        = list(string)
  description = "List of Secrets Manager secret ARNs needed by the runtimes"
  default     = []
}

variable "kms_key_arns" {
  type        = list(string)
  description = "List of KMS customer managed key ARNs used for encryption/decryption"
  default     = []
}

variable "ai_engine_contract_version" {
  type        = string
  description = "Version of the AI Engine contract"
  default     = "v1"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}
