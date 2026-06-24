variable "aws_region" {
  type        = string
  description = "AWS region for provisioning resources"
  default     = "ap-southeast-1"
}

variable "project_name" {
  type        = string
  description = "The prefix name of the project"
  default     = "tf2-finops"
}

variable "github_repository" {
  type        = string
  description = "GitHub repository in format owner/repo"
  default     = "hungxqt/tf2-finops-iac"
}
