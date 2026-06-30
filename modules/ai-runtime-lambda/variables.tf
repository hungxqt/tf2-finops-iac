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
  validation {
    condition     = can(regex("@sha256:[a-fA-F0-9]{64}$", var.request_image_uri))
    error_message = "The request_image_uri must be pinned to an immutable image digest (e.g. name@sha256:<64-hex-characters>)."
  }
}

variable "request_reserved_concurrency" {
  type        = number
  description = "Reserved concurrency for the AI Request Lambda function"
  default     = null
}

variable "request_timeout_seconds" {
  type        = number
  description = "Timeout in seconds for the AI Request Lambda function"
  default     = 60
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

variable "vpc_id" {
  type        = string
  description = "VPC ID where the ALB and Target Group will be created"
}

variable "vpc_cidr_block" {
  type        = string
  description = "CIDR block of the VPC for security group rules"
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

variable "alb_access_logs_bucket" {
  type        = string
  description = "S3 bucket name for ALB access logs"
  default     = ""
}

variable "alb_access_logs_prefix" {
  type        = string
  description = "S3 prefix for ALB access logs"
  default     = "alb-access-logs"
}

variable "destroyable" {
  type        = bool
  description = "Set to true to make ECR repository destroyable (Sandbox exceptions)"
}

variable "ai_request_s3_pointer_bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket containing AI input pointers (e.g. lakehouse bucket). Leave empty to grant no additional S3 access."
  default     = ""
}

variable "ai_request_s3_pointer_prefixes" {
  type        = list(string)
  description = "S3 key prefixes under ai_request_s3_pointer_bucket_arn that the AI Request Lambda may read. Defaults to ai-input/*."
  default     = ["ai-input/*"]
}

variable "enable_codedeploy" {
  type        = bool
  description = "Enable CodeDeploy rollout for the request Lambda"
  default     = true
}

variable "codedeploy_deployment_config_name" {
  type        = string
  description = "CodeDeploy deployment config name"
  default     = "CodeDeployDefault.LambdaLinear10PercentEvery10Minutes"
}

variable "codedeploy_extra_alarm_names" {
  type        = list(string)
  description = "List of extra CloudWatch alarm names to trigger rollback"
  default     = []
}

variable "codedeploy_alarm_actions" {
  type        = list(string)
  description = "List of alarm actions (e.g. SNS topics) for deployment alarms"
  default     = []
}

variable "deployment_p99_latency_threshold_ms" {
  type        = number
  description = "Latency threshold in ms for the P99 duration alarm"
  default     = 800
}

variable "enable_alb_https" {
  type        = bool
  description = "Enable HTTPS for the internal ALB. If set to false, HTTP on port 80 is used (Sandbox only)."
  default     = true
}
