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

variable "request_image_uri" {
  type        = string
  description = "ECR image URI with immutable digest for the AI Request Lambda function"
}

variable "worker_image_uri" {
  type        = string
  description = "ECR image URI with immutable digest for the AI Worker Lambda function"
}

