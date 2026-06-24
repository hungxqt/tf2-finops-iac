# EKS Module Resources
# This module provisions the EKS control plane and managed node groups.

# Cluster IAM Role
resource "aws_iam_role" "cluster" {
  name = "${var.project_name}-${var.environment}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

# Node IAM Role
resource "aws_iam_role" "node" {
  name = "${var.project_name}-${var.environment}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_registry" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_ssm" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  role       = aws_iam_role.node.name
}

# EKS Cluster control plane (VPC-attached and Private-only)
resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-${var.environment}-cluster"
  role_arn = aws_iam_role.cluster.arn
  version  = var.cluster_version

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = false
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator"]

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy
  ]
  tags = var.tags
}

# EKS Addons
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"
}

# EKS Managed Node Group: On-demand (Stable workloads)
resource "aws_eks_node_group" "on_demand" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-${var.environment}-on-demand"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = var.on_demand_node_group_config.desired_size
    max_size     = var.on_demand_node_group_config.max_size
    min_size     = var.on_demand_node_group_config.min_size
  }

  instance_types = var.on_demand_node_group_config.instance_types
  capacity_type  = "ON_DEMAND"

  # Autoscaler tags
  tags = merge(
    var.tags,
    {
      "k8s.io/cluster-autoscaler/enabled"                      = "true",
      "k8s.io/cluster-autoscaler/${aws_eks_cluster.main.name}" = "owned"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_registry
  ]
}

# EKS Managed Node Group: Spot (Interruptible batch workloads)
resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-${var.environment}-spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = var.spot_node_group_config.desired_size
    max_size     = var.spot_node_group_config.max_size
    min_size     = var.spot_node_group_config.min_size
  }

  instance_types = var.spot_node_group_config.instance_types
  capacity_type  = "SPOT"

  labels = {
    "workload-type" = "spot"
  }

  taint {
    key    = "workload-type"
    value  = "spot"
    effect = "NO_SCHEDULE"
  }

  tags = merge(
    var.tags,
    {
      "k8s.io/cluster-autoscaler/enabled"                      = "true",
      "k8s.io/cluster-autoscaler/${aws_eks_cluster.main.name}" = "owned"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_registry
  ]
}

# CoreDNS depends on node group being active
resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"
  depends_on   = [aws_eks_node_group.on_demand]
}

# ECR Repositories for AI Engine Images
resource "aws_ecr_repository" "repos" {
  for_each             = toset(var.ecr_repository_names)
  name                 = "${var.project_name}-${var.environment}-${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
  tags = var.tags
}

# OIDC Provider
data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "oidc" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# IRSA Roles
# 1. AI Engine API role (lakehouse S3 read)
resource "aws_iam_role" "ai_engine_api" {
  name = "${var.project_name}-${var.environment}-ai-engine-api-irsa"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.oidc.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.oidc.url, "https://", "")}:sub" = "system:serviceaccount:${var.ai_engine_namespace}:ai-engine-api-sa"
        }
      }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "ai_engine_api" {
  name = "lakehouse-read-only"
  role = aws_iam_role.ai_engine_api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket"
      ]
      Resource = [
        "arn:aws:s3:::${var.project_name}-${var.environment}-lakehouse-bucket",
        "arn:aws:s3:::${var.project_name}-${var.environment}-lakehouse-bucket/*"
      ]
    }]
  })
}

# 2. AI Engine worker role (lakehouse S3 read/write)
resource "aws_iam_role" "ai_engine_worker" {
  name = "${var.project_name}-${var.environment}-ai-engine-worker-irsa"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.oidc.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.oidc.url, "https://", "")}:sub" = "system:serviceaccount:${var.ai_engine_namespace}:ai-engine-worker-sa"
        }
      }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "ai_engine_worker" {
  name = "lakehouse-read-write"
  role = aws_iam_role.ai_engine_worker.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ]
      Resource = [
        "arn:aws:s3:::${var.project_name}-${var.environment}-lakehouse-bucket",
        "arn:aws:s3:::${var.project_name}-${var.environment}-lakehouse-bucket/*"
      ]
    }]
  })
}

# 3. External Secrets role (Secrets Manager read)
data "aws_caller_identity" "current" {}

resource "aws_iam_role" "external_secrets" {
  name = "${var.project_name}-${var.environment}-external-secrets-irsa"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.oidc.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.oidc.url, "https://", "")}:sub" = "system:serviceaccount:${var.ai_engine_namespace}:external-secrets-sa"
        }
      }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "external_secrets" {
  name = "secrets-manager-read"
  role = aws_iam_role.external_secrets.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      Resource = ["arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-${var.ai_engine_secret_name}-*"]
    }]
  })
}
