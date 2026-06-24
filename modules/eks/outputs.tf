output "cluster_name" {
  description = "The name of the EKS Cluster"
  value       = aws_eks_cluster.main.name
}

output "cluster_arn" {
  description = "The ARN of the EKS Cluster"
  value       = aws_eks_cluster.main.arn
}

output "cluster_endpoint" {
  description = "The endpoint of the EKS Cluster control plane"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_security_group_id" {
  description = "The security group ID of the EKS Cluster"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "The ARN of the OIDC provider associated with the cluster"
  value       = aws_iam_openid_connect_provider.oidc.arn
}

output "on_demand_node_group_name" {
  description = "The name of the on-demand node group"
  value       = aws_eks_node_group.on_demand.node_group_name
}

output "spot_node_group_name" {
  description = "The name of the spot node group"
  value       = aws_eks_node_group.spot.node_group_name
}

output "ecr_repository_urls" {
  description = "Map of ECR repository names to repository URLs"
  value       = { for k, v in aws_ecr_repository.repos : k => v.repository_url }
}

output "ai_engine_internal_endpoint" {
  description = "Internal endpoint for reaching the AI Engine"
  value       = "http://${var.ai_engine_service_name}.${var.ai_engine_namespace}.svc.cluster.local"
}

output "ai_engine_api_irsa_role_arn" {
  description = "The ARN of the IAM role for the AI Engine API service account"
  value       = aws_iam_role.ai_engine_api.arn
}

output "ai_engine_worker_irsa_role_arn" {
  description = "The ARN of the IAM role for the AI Engine worker service account"
  value       = aws_iam_role.ai_engine_worker.arn
}

output "external_secrets_irsa_role_arn" {
  description = "The ARN of the IAM role for the External Secrets service account"
  value       = aws_iam_role.external_secrets.arn
}
