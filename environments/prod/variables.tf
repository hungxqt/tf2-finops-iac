variable "aws_region" {
  type        = string
  description = "AWS region for prod environment"
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
  default     = "prod"
}

variable "tags" {
  type        = map(string)
  description = "Common resources tags"
  default = {
    Environment = "prod"
    Project     = "tf2-finops"
    ManagedBy   = "Terraform"
  }
}
