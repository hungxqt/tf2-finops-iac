data "aws_caller_identity" "current" {}

# KMS Key Policy for State Key
data "aws_iam_policy_document" "kms_state_policy" {
  statement {
    # checkov:skip=CKV_AWS_109: "KMS key policy must specify resource = * as it is attached directly to the key"
    # checkov:skip=CKV_AWS_111: "KMS key policy must specify resource = * as it is attached directly to the key"
    # checkov:skip=CKV_AWS_356: "KMS key policy must specify resource = * as it is attached directly to the key"
    sid    = "Enable Root Account Administration"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions = [
      "kms:Create*",
      "kms:Describe*",
      "kms:Enable*",
      "kms:List*",
      "kms:Put*",
      "kms:Update*",
      "kms:Revoke*",
      "kms:Disable*",
      "kms:Get*",
      "kms:Delete*",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion"
    ]
    resources = ["*"]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "KMS key policy must specify resource = * as it is attached directly to the key"
    # checkov:skip=CKV_AWS_356: "KMS key policy must specify resource = * as it is attached directly to the key"
    sid    = "AllowServiceUsage"
    effect = "Allow"
    principals {
      type = "Service"
      identifiers = [
        "s3.amazonaws.com"
      ]
    }
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
      "kms:Encrypt"
    ]
    resources = ["*"]
  }
}

# KMS Key for Terraform state encryption
resource "aws_kms_key" "state" {
  description             = "KMS key for Terraform state encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_state_policy.json

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "state" {
  name          = "alias/${var.project_name}-state-key"
  target_key_id = aws_kms_key.state.key_id
}

# Dedicated S3 Access Logging Bucket for Bootstrap
resource "aws_s3_bucket" "logging" {
  # checkov:skip=CKV_AWS_18: "Logging bucket does not need access logging itself"
  # checkov:skip=CKV_AWS_144: "Logging bucket does not need replication"
  # checkov:skip=CKV_AWS_21: "Logging bucket does not need versioning"
  # checkov:skip=CKV2_AWS_61: "Logging bucket does not need lifecycle configuration"
  # checkov:skip=CKV2_AWS_62: "Logging bucket does not need event notifications"
  bucket        = "${var.project_name}-state-logging"
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "logging" {
  bucket                  = aws_s3_bucket.logging.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logging" {
  bucket = aws_s3_bucket.logging.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.state.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_policy" "logging_tls_only" {
  bucket     = aws_s3_bucket.logging.id
  policy     = data.aws_iam_policy_document.s3_tls_only_logging.json
  depends_on = [aws_s3_bucket_public_access_block.logging]
}

data "aws_iam_policy_document" "s3_tls_only_logging" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.logging.arn,
      "${aws_s3_bucket.logging.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# S3 Bucket for Terraform remote state storage
resource "aws_s3_bucket" "state" {
  bucket = "${var.project_name}-state-bucket"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.state.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "state" {
  bucket        = aws_s3_bucket.state.id
  target_bucket = aws_s3_bucket.logging.id
  target_prefix = "state-logs/"
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "abort-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_notification" "state" {
  bucket      = aws_s3_bucket.state.id
  eventbridge = true
}

resource "aws_s3_bucket_replication_configuration" "state" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "replicate-state"
    status = "Enabled"

    destination {
      bucket        = var.state_replica_bucket_arn
      storage_class = "STANDARD"
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state_bucket.json
}

data "aws_iam_policy_document" "state_bucket" {
  statement {
    sid    = "EnforceTLSRequestsOnly"
    effect = "Deny"
    actions = [
      "s3:*"
    ]
    resources = [
      aws_s3_bucket.state.arn,
      "${aws_s3_bucket.state.arn}/*"
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# GitHub OIDC Provider
data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

# GitHub Actions OIDC execution role
resource "aws_iam_role" "github_actions" {
  name               = "${var.project_name}-github-actions-role"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume.json
}

data "aws_iam_policy_document" "github_actions_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:*"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "github_actions" {
  # checkov:skip=CKV_AWS_274: "GitHub Actions deployment execution role requires AdministratorAccess to provision the entire Terraform infrastructure stack"
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# IAM Role for S3 Replication in Bootstrap Module
resource "aws_iam_role" "replication" {
  name = "${var.project_name}-bootstrap-repl-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
    }]
  })
  tags = {
    Project = var.project_name
  }
}

resource "aws_iam_role_policy" "replication" {
  name = "bootstrap-replication-policy"
  role = aws_iam_role.replication.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.state.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Resource = [
          "${aws_s3_bucket.state.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Resource = [
          "${var.state_replica_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          aws_kms_key.state.arn
        ]
      }
    ]
  })
}
