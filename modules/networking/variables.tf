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
  description = "AWS region for network deployment"
}

variable "vpc_cidr_block" {
  type        = string
  description = "The CIDR block for the VPC"
  validation {
    condition     = can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$", var.vpc_cidr_block))
    error_message = "VPC CIDR block must be in valid CIDR notation."
  }
}

variable "public_subnet_cidr_blocks" {
  type        = list(string)
  description = "The CIDR blocks for the public subnets"
  validation {
    condition     = length(var.public_subnet_cidr_blocks) == 2
    error_message = "Must specify exactly two public subnet CIDR blocks."
  }
}

variable "private_subnet_cidr_blocks" {
  type        = list(string)
  description = "The CIDR blocks for the private subnets"
  validation {
    condition     = length(var.private_subnet_cidr_blocks) == 2
    error_message = "Must specify exactly two private subnet CIDR blocks."
  }
}

variable "availability_zones" {
  type        = list(string)
  description = "List of availability zones to use"
}

variable "single_nat_gateway" {
  type        = bool
  description = "Should be true if you want to provision a single shared NAT Gateway"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
