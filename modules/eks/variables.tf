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
  description = "AWS region for EKS deployment"
}

variable "vpc_id" {
  type        = string
  description = "The ID of the VPC"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "List of private subnet IDs for EKS control plane and nodes"
}

variable "cluster_version" {
  type        = string
  description = "EKS Kubernetes version"
  default     = "1.31"
}

variable "on_demand_node_group_config" {
  type = object({
    instance_types = list(string)
    min_size       = number
    max_size       = number
    desired_size   = number
  })
  description = "Configuration for on-demand EKS managed node group"
  default = {
    instance_types = ["t3.medium"]
    min_size       = 1
    max_size       = 3
    desired_size   = 1
  }
}

variable "spot_node_group_config" {
  type = object({
    instance_types = list(string)
    min_size       = number
    max_size       = number
    desired_size   = number
  })
  description = "Configuration for spot EKS managed node group"
  default = {
    instance_types = ["t3.medium"]
    min_size       = 0
    max_size       = 5
    desired_size   = 1
  }
}

variable "ai_engine_namespace" {
  type        = string
  description = "Namespace where AI Engine is deployed"
  default     = "ai-engine"
}

variable "ai_engine_service_name" {
  type        = string
  description = "Internal Kubernetes service name for EKS exposure"
  default     = "ai-engine-service"
}

variable "ai_engine_contract_version" {
  type        = string
  description = "Supported AI Engine API version contract"
  default     = "v1.0"
}

variable "ai_engine_secret_name" {
  type        = string
  description = "Name of Secrets Manager credentials secret"
  default     = "ai-engine-auth"
}

variable "ecr_repository_names" {
  type        = list(string)
  description = "List of ECR repository names to create"
  default     = ["ai-engine-api", "ai-engine-worker"]
}

variable "enable_karpenter" {
  type        = bool
  description = "Enable Karpenter prerequisites provision"
  default     = false
}

variable "enable_container_insights" {
  type        = bool
  description = "Enable CloudWatch Container Insights on EKS"
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
