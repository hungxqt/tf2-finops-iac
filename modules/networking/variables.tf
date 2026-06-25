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
  description = "The AWS region"
}

variable "vpc_cidr_block" {
  type        = string
  description = "The CIDR block for the VPC"
}

variable "public_subnet_cidr_blocks" {
  type        = list(string)
  description = "List of public subnet CIDR blocks"
}

variable "private_subnet_cidr_blocks" {
  type        = list(string)
  description = "List of private subnet CIDR blocks"
}

variable "availability_zones" {
  type        = list(string)
  description = "List of availability zones"
}

variable "single_nat_gateway" {
  type        = bool
  description = "Whether to use a single NAT Gateway"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}

variable "cloudwatch_log_kms_key_arn" {
  type        = string
  description = "KMS Customer Managed Key (CMK) ARN for CloudWatch Log Group encryption"
}
