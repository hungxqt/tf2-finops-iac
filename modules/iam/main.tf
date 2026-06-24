# IAM Module Resources
# This module creates least-privilege execution roles and guardrails.

data "aws_caller_identity" "current" {}

# Permissions boundary to deny destructive operations
resource "aws_iam_policy" "boundary" {
  name        = "${var.project_name}-${var.environment}-permissions-boundary"
  description = "Permissions boundary for Lambda roles to prevent destructive operations"
  policy      = data.aws_iam_policy_document.boundary.json
  tags        = var.tags
}

data "aws_iam_policy_document" "boundary" {
  statement {
    sid       = "AllowAllExceptGuardrails"
    effect    = "Allow"
    actions   = ["*"]
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
  worker_names = ["state", "cost_puller", "normalizer", "ai_client", "router", "audit_writer", "containment_worker"]
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

# 4. AI Client
resource "aws_iam_role_policy" "ai_client" {
  name   = "ai_client-policy"
  role   = aws_iam_role.workers["ai_client"].id
  policy = data.aws_iam_policy_document.ai_client.json
}

data "aws_iam_policy_document" "ai_client" {
  dynamic "statement" {
    for_each = var.ai_engine_secret_arn != "" ? [1] : []
    content {
      actions   = ["secretsmanager:GetSecretValue"]
      resources = [var.ai_engine_secret_arn]
    }
  }
  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt"]
      resources = var.kms_key_arns
    }
  }
}

# 5. Router
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
    resources = ["*"]
  }
}

# 6. Audit Writer
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

# 7. Containment Worker
resource "aws_iam_role_policy" "containment_worker" {
  name   = "containment_worker-policy"
  role   = aws_iam_role.workers["containment_worker"].id
  policy = data.aws_iam_policy_document.containment_worker.json
}

data "aws_iam_policy_document" "containment_worker" {
  statement {
    actions = [
      "ec2:CreateTags",
      "ec2:DescribeInstances",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeVolumes"
    ]
    resources = ["*"]
  }
  dynamic "statement" {
    for_each = var.environment != "prod" && var.containment_apply_enabled ? [1] : []
    content {
      actions   = ["ec2:StopInstances"]
      resources = ["*"]
    }
  }
}

# Step Functions Execution Role
resource "aws_iam_role" "step_functions" {
  name               = "${var.project_name}-${var.environment}-sfn-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "sfn_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "step_functions" {
  name   = "sfn-policy"
  role   = aws_iam_role.step_functions.id
  policy = data.aws_iam_policy_document.step_functions.json
}

data "aws_iam_policy_document" "step_functions" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = ["*"]
  }
  statement {
    actions   = ["dynamodb:GetItem"]
    resources = var.dynamodb_table_arns
  }
  statement {
    actions   = ["sns:Publish"]
    resources = ["*"]
  }
}

# Cross-account cost data read and containment documents for outputs
data "aws_iam_policy_document" "member_read" {
  statement {
    actions = [
      "ce:GetCostAndUsage",
      "s3:GetObject"
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "member_containment" {
  statement {
    actions = [
      "ec2:CreateTags",
      "ec2:DescribeInstances",
      "ec2:StopInstances"
    ]
    resources = ["*"]
  }
}

# EventBridge Scheduler Execution Role
resource "aws_iam_role" "scheduler" {
  name               = "${var.project_name}-${var.environment}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "scheduler-policy"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["states:StartExecution"]
    resources = ["*"]
  }
}

