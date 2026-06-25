# IAM Module Resources
# This module creates least-privilege execution roles and guardrails for Lambda workers.

# Permissions boundary to deny destructive operations
resource "aws_iam_policy" "boundary" {
  name        = "${var.project_name}-${var.environment}-permissions-boundary"
  description = "Permissions boundary for Lambda roles to prevent destructive operations"
  policy      = data.aws_iam_policy_document.boundary.json
  tags        = var.tags
}

data "aws_iam_policy_document" "boundary" {
  statement {
    sid    = "AllowS3Actions"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket"
    ]
    resources = [
      var.lakehouse_bucket_arn,
      "${var.lakehouse_bucket_arn}/*",
      var.audit_bucket_arn,
      "${var.audit_bucket_arn}/*"
    ]
  }

  statement {
    sid    = "AllowDynamoDBActions"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem"
    ]
    resources = var.dynamodb_table_arns
  }

  statement {
    sid    = "AllowKMSActions"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey"
    ]
    resources = var.kms_key_arns
  }

  statement {
    sid    = "AllowSNSActions"
    effect = "Allow"
    actions = [
      "sns:Publish"
    ]
    resources = var.sns_topic_arns
  }

  statement {
    sid    = "AllowSQSActions"
    effect = "Allow"
    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = var.queue_arns
  }

  statement {
    sid    = "AllowLogsActions"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:log-group:/aws/lambda/${var.project_name}-${var.environment}-*"]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "EC2 describe/tag actions require wildcard permissions"
    # checkov:skip=CKV_AWS_356: "ec2:Describe* actions require wildcard resource *"
    sid    = "AllowEC2DescribeActions"
    effect = "Allow"
    actions = [
      "ec2:CreateTags",
      "ec2:DescribeInstances",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeVolumes"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "AllowEC2StopActions"
    effect = "Allow"
    actions = [
      "ec2:StopInstances"
    ]
    resources = ["arn:aws:ec2:*:*:instance/*"]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "ce:GetCostAndUsage and xray:* do not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "ce:GetCostAndUsage and xray:* require wildcard resource *"
    # checkov:skip=CKV_AWS_108: "ce:GetCostAndUsage requires wildcard resource *"
    sid    = "AllowCostAndXRayActions"
    effect = "Allow"
    actions = [
      "ce:GetCostAndUsage",
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DenyDestructiveActions"
    effect = "Deny"
    actions = [
      "iam:*",
      "organizations:*",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:DeleteBucket",
      "dynamodb:DeleteTable",
      "dynamodb:DeleteItem",
      "rds:DeleteDBInstance",
      "rds:DeleteDBSnapshot",
      "ec2:TerminateInstances"
    ]
    resources = ["*"]
  }

  # If prod, strictly deny ec2:StopInstances
  dynamic "statement" {
    for_each = var.environment == "prod" ? [1] : []
    content {
      sid       = "DenyProdStopInstances"
      effect    = "Deny"
      actions   = ["ec2:StopInstances"]
      resources = ["*"]
    }
  }
}

# Trust policy for Lambda service
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

locals {
  worker_names = ["state", "cost_puller", "normalizer", "router", "audit_writer", "containment_worker"]
}

# Lambda Worker Roles
resource "aws_iam_role" "workers" {
  for_each             = toset(local.worker_names)
  name                 = "${var.project_name}-${var.environment}-${each.key}-role"
  assume_role_policy   = data.aws_iam_policy_document.lambda_trust.json
  permissions_boundary = aws_iam_policy.boundary.arn
  tags                 = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  for_each   = toset(local.worker_names)
  role       = aws_iam_role.workers[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Specific Policies for Workers
# 1. State
resource "aws_iam_role_policy" "state" {
  name   = "state-policy"
  role   = aws_iam_role.workers["state"].id
  policy = data.aws_iam_policy_document.state.json
}

data "aws_iam_policy_document" "state" {
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem"
    ]
    resources = var.dynamodb_table_arns
  }
  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
      resources = var.kms_key_arns
    }
  }
}

# 2. Cost Puller
resource "aws_iam_role_policy" "cost_puller" {
  name   = "cost_puller-policy"
  role   = aws_iam_role.workers["cost_puller"].id
  policy = data.aws_iam_policy_document.cost_puller.json
}

data "aws_iam_policy_document" "cost_puller" {
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${var.lakehouse_bucket_arn}/*"]
  }
  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
      resources = var.kms_key_arns
    }
  }
  statement {
    # checkov:skip=CKV_AWS_111: "ce:GetCostAndUsage does not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "ce:GetCostAndUsage requires wildcard resource"
    actions   = ["ce:GetCostAndUsage"]
    resources = ["*"]
  }
}

# 3. Normalizer
resource "aws_iam_role_policy" "normalizer" {
  name   = "normalizer-policy"
  role   = aws_iam_role.workers["normalizer"].id
  policy = data.aws_iam_policy_document.normalizer.json
}

data "aws_iam_policy_document" "normalizer" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${var.lakehouse_bucket_arn}/*"]
  }
  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
      resources = var.kms_key_arns
    }
  }
}

# 4. Router
resource "aws_iam_role_policy" "router" {
  name   = "router-policy"
  role   = aws_iam_role.workers["router"].id
  policy = data.aws_iam_policy_document.router.json
}

data "aws_iam_policy_document" "router" {
  statement {
    actions   = ["dynamodb:PutItem"]
    resources = var.dynamodb_table_arns
  }
  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
      resources = var.kms_key_arns
    }
  }
  statement {
    actions   = ["sns:Publish"]
    resources = var.sns_topic_arns
  }
}

# 5. Audit Writer
resource "aws_iam_role_policy" "audit_writer" {
  name   = "audit_writer-policy"
  role   = aws_iam_role.workers["audit_writer"].id
  policy = data.aws_iam_policy_document.audit_writer.json
}

data "aws_iam_policy_document" "audit_writer" {
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${var.audit_bucket_arn}/*"]
  }
  statement {
    actions   = ["dynamodb:PutItem"]
    resources = var.dynamodb_table_arns
  }
  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
      resources = var.kms_key_arns
    }
  }
}

# 6. Containment Worker
resource "aws_iam_role_policy" "containment_worker" {
  name   = "containment_worker-policy"
  role   = aws_iam_role.workers["containment_worker"].id
  policy = data.aws_iam_policy_document.containment_worker.json
}

data "aws_iam_policy_document" "containment_worker" {
  statement {
    # checkov:skip=CKV_AWS_111: "EC2 Describe APIs do not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "EC2 Describe APIs require wildcard resource"
    sid = "EC2WildcardDescribes"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeVolumes"
    ]
    resources = ["*"]
  }

  statement {
    sid       = "EC2CreateTagsScoped"
    actions   = ["ec2:CreateTags"]
    resources = ["arn:aws:ec2:*:*:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = [var.environment]
    }
  }

  dynamic "statement" {
    for_each = var.environment != "prod" && var.containment_apply_enabled ? [1] : []
    content {
      sid       = "EC2StopInstancesScoped"
      actions   = ["ec2:StopInstances"]
      resources = ["arn:aws:ec2:*:*:instance/*"]
      condition {
        test     = "StringEquals"
        variable = "aws:ResourceTag/Environment"
        values   = [var.environment]
      }
    }
  }
}

# Cross-account cost data read and containment documents for outputs
data "aws_iam_policy_document" "member_read" {
  statement {
    # checkov:skip=CKV_AWS_111: "ce:GetCostAndUsage does not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "ce:GetCostAndUsage requires wildcard resource"
    # checkov:skip=CKV_AWS_108: "ce:GetCostAndUsage and member S3 cost reading require wildcard permissions"
    actions = [
      "ce:GetCostAndUsage",
      "s3:GetObject"
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "member_containment" {
  statement {
    # checkov:skip=CKV_AWS_111: "EC2 describe/stop actions in target member accounts require flexible target resources"
    # checkov:skip=CKV_AWS_356: "ec2:DescribeInstances requires wildcard resource"
    actions = [
      "ec2:CreateTags",
      "ec2:DescribeInstances",
      "ec2:StopInstances"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "workers_xray" {
  for_each = toset(local.worker_names)
  name     = "xray-policy"
  role     = aws_iam_role.workers[each.key].id
  policy   = data.aws_iam_policy_document.xray.json
}

data "aws_iam_policy_document" "xray" {
  statement {
    # checkov:skip=CKV_AWS_111: "X-Ray tracing requires wildcard resource"
    # checkov:skip=CKV_AWS_356: "X-Ray tracing requires wildcard resource"
    sid = "XRayWriteOnly"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords"
    ]
    resources = ["*"]
  }
}
