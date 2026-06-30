variable "project_name" {
  type        = string
  description = "The prefix name of the project"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., sandbox, staging, prod)"
}

variable "state_machine_arn" {
  type        = string
  description = "ARN of the Step Functions State Machine to monitor"
}

variable "lambda_function_names" {
  type        = list(string)
  description = "List of Lambda worker function names to monitor"
}

variable "engineering_topic_arn" {
  type        = string
  description = "ARN of the Engineering SNS Topic for alarm routing"
}

variable "finance_topic_arn" {
  type        = string
  description = "ARN of the Finance SNS Topic for alarm routing"
}

variable "log_retention_days" {
  type        = number
  description = "Retention period for logs in CloudWatch"
  default     = 14
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}




