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
      "s3:ListBucket",
      "s3:GetBucketLocation"
    ]
    resources = concat(
      [
        var.lakehouse_bucket_arn,
        "${var.lakehouse_bucket_arn}/*",
        var.audit_bucket_arn,
        "${var.audit_bucket_arn}/*"
      ],
      var.cur_source_bucket_arn != "" ? [
        var.cur_source_bucket_arn,
        "${var.cur_source_bucket_arn}/*"
      ] : [],
      var.athena_results_bucket_arn != "" ? [
        var.athena_results_bucket_arn,
        "${var.athena_results_bucket_arn}/*"
      ] : []
    )
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
      "kms:GenerateDataKey",
      "kms:Encrypt"
    ]
    resources = var.kms_key_arns
  }

  statement {
    sid    = "AllowAthenaActions"
    effect = "Allow"
    actions = [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:StopQueryExecution",
      "athena:GetWorkGroup"
    ]
    resources = var.athena_workgroup_arn != "" ? [var.athena_workgroup_arn] : ["*"]
  }

  statement {
    sid    = "AllowGlueActions"
    effect = "Allow"
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetPartitions"
    ]
    resources = concat(
      compact([
        var.glue_database_arn != "" ? var.glue_database_arn : "",
        "arn:aws:glue:*:*:catalog"
      ]),
      var.glue_table_arns
    )
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
    # checkov:skip=CKV_AWS_111: "Lambda VPC ENI management actions require wildcard resource *"
    # checkov:skip=CKV_AWS_356: "ec2:CreateNetworkInterface, ec2:DescribeNetworkInterfaces, ec2:DescribeSubnets, ec2:DeleteNetworkInterface require wildcard resource *"
    sid    = "AllowLambdaVPCAccess"
    effect = "Allow"
    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeSubnets",
      "ec2:DeleteNetworkInterface",
      "ec2:AssignPrivateIpAddresses",
      "ec2:UnassignPrivateIpAddresses"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DenyENIFromFunctionCode"
    effect = "Deny"
    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeSubnets",
      "ec2:DeleteNetworkInterface",
      "ec2:AssignPrivateIpAddresses",
      "ec2:UnassignPrivateIpAddresses"
    ]
    resources = ["*"]
    condition {
      test     = "Null"
      variable = "lambda:SourceFunctionArn"
      values   = ["false"]
    }
  }

  statement {
    # checkov:skip=CKV_AWS_111: "ce:GetCostAndUsage, cloudwatch:GetMetricData, and xray:* do not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "ce:GetCostAndUsage, cloudwatch:GetMetricData, and xray:* require wildcard resource *"
    # checkov:skip=CKV_AWS_108: "ce:GetCostAndUsage requires wildcard resource *"
    sid    = "AllowCostAndXRayActions"
    effect = "Allow"
    actions = [
      "ce:GetCostAndUsage",
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "cloudwatch:GetMetricData"
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

  dynamic "statement" {
    for_each = length(var.telemetry_member_account_ids) > 0 ? [1] : []
    content {
      sid    = "AllowSTSAssumeAndTagSession"
      effect = "Allow"
      actions = [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
      resources = [for acc in var.telemetry_member_account_ids : "arn:aws:iam::${acc}:role/${var.telemetry_member_role_name}"]
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
  worker_names = ["state", "cost_puller", "normalizer", "router", "audit_writer", "containment_worker", "vpc_alb_caller"]
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
    sid       = "AllowLakehouseTelemetryList"
    actions   = ["s3:ListBucket"]
    resources = [var.lakehouse_bucket_arn]
  }

  statement {
    sid = "AllowLakehouseObjectAccess"
    actions = [
      "s3:GetObject",
      "s3:PutObject"
    ]
    resources = ["${var.lakehouse_bucket_arn}/*"]
  }

  dynamic "statement" {
    for_each = var.cur_source_bucket_arn != "" ? [1] : []
    content {
      sid       = "AllowCURSourceList"
      actions   = ["s3:ListBucket"]
      resources = [var.cur_source_bucket_arn]
    }
  }

  dynamic "statement" {
    for_each = var.cur_source_bucket_arn != "" ? [1] : []
    content {
      sid     = "AllowCURSourceGet"
      actions = ["s3:GetObject", "s3:HeadObject"]
      resources = length(var.telemetry_member_account_ids) > 0 ? [
        for acc in var.telemetry_member_account_ids : "${var.cur_source_bucket_arn}/${acc}/${var.cur_export_name}/*"
        ] : [
        var.cur_source_prefix != "" ? "${var.cur_source_bucket_arn}/${var.cur_source_prefix}*" : "${var.cur_source_bucket_arn}/*"
      ]
    }
  }

  dynamic "statement" {
    for_each = length(var.telemetry_member_account_ids) > 0 ? [1] : []
    content {
      sid = "AllowAssumeRoleInMembers"
      actions = [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
      resources = [for acc in var.telemetry_member_account_ids : "arn:aws:iam::${acc}:role/${var.telemetry_member_role_name}"]
    }
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
    sid       = "AllowCostExplorer"
    actions   = ["ce:GetCostAndUsage"]
    resources = ["*"]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "cloudwatch:GetMetricData does not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "cloudwatch:GetMetricData requires wildcard resource"
    sid       = "AllowCloudWatchMetricData"
    actions   = ["cloudwatch:GetMetricData"]
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
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [
      var.lakehouse_bucket_arn,
      "${var.lakehouse_bucket_arn}/*",
      var.athena_results_bucket_arn,
      "${var.athena_results_bucket_arn}/*"
    ]
  }
  statement {
    actions = [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:StopQueryExecution",
      "athena:GetWorkGroup"
    ]
    resources = [var.athena_workgroup_arn]
  }
  statement {
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetPartitions"
    ]
    resources = concat(
      compact([
        var.glue_database_arn,
        "arn:aws:glue:*:*:catalog"
      ]),
      var.glue_table_arns
    )
  }
  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:GenerateDataKey", "kms:Encrypt"]
      resources = var.kms_key_arns
    }
  }

  dynamic "statement" {
    for_each = var.cur_source_bucket_arn != "" ? [1] : []
    content {
      sid       = "AllowCURSourceList"
      actions   = ["s3:ListBucket"]
      resources = [var.cur_source_bucket_arn]
    }
  }

  dynamic "statement" {
    for_each = var.cur_source_bucket_arn != "" ? [1] : []
    content {
      sid     = "AllowCURSourceGet"
      actions = ["s3:GetObject", "s3:HeadObject"]
      resources = length(var.telemetry_member_account_ids) > 0 ? [
        for acc in var.telemetry_member_account_ids : "${var.cur_source_bucket_arn}/${acc}/${var.cur_export_name}/*"
        ] : [
        var.cur_source_prefix != "" ? "${var.cur_source_bucket_arn}/${var.cur_source_prefix}*" : "${var.cur_source_bucket_arn}/*"
      ]
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

  # Cross-account AssumeRole into member accounts for containment execution
  statement {
    # checkov:skip=CKV_AWS_111: "sts:AssumeRole for cross-account containment requires member account role ARNs"
    sid     = "AssumeContainmentRoleInMembers"
    actions = ["sts:AssumeRole"]
    resources = length(var.telemetry_member_account_ids) > 0 ? [
      for acc in var.telemetry_member_account_ids :
      "arn:aws:iam::${acc}:role/FinOpsContainmentWorkerRole"
    ] : ["arn:aws:iam::*:role/FinOpsContainmentWorkerRole"]
  }

  # Write pre-action and post-action audit records to S3 Object Lock
  statement {
    sid       = "AuditBucketWrite"
    actions   = ["s3:PutObject"]
    resources = ["${var.audit_bucket_arn}/audit/*"]
  }

  # Update DynamoDB Dashboard Cache (best-effort)
  statement {
    sid       = "DashboardCacheWrite"
    actions   = ["dynamodb:PutItem"]
    resources = var.dynamodb_table_arns
  }

  # Cache and read rollback payload (finops-rollback-cache)
  statement {
    sid       = "RollbackCacheReadWrite"
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem"]
    resources = var.dynamodb_table_arns
  }

  # Read external_id from Secrets Manager
  statement {
    sid       = "SecretsManagerContainmentExternalId"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:*:*:secret:finops/containment/*"]
  }

  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
      resources = var.kms_key_arns
    }
  }
}

# Cross-account containment documents for outputs

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

# 7. VpcAlbCaller – dedicated idempotency table policy (least-privilege)
# Only created when ai_payload_idempotency_table_arn is provided.
# This scopes vpc_alb_caller to ONLY the idempotency table, not all DynamoDB tables.
resource "aws_iam_role_policy" "vpc_alb_caller_idempotency" {
  count  = var.ai_payload_idempotency_table_arn != "" ? 1 : 0
  name   = "vpc_alb_caller-idempotency-policy"
  role   = aws_iam_role.workers["vpc_alb_caller"].id
  policy = data.aws_iam_policy_document.vpc_alb_caller_idempotency[0].json
}

data "aws_iam_policy_document" "vpc_alb_caller_idempotency" {
  count = var.ai_payload_idempotency_table_arn != "" ? 1 : 0

  statement {
    sid = "VpcAlbCallerIdempotencyTableAccess"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem"
    ]
    resources = [var.ai_payload_idempotency_table_arn]
  }

  dynamic "statement" {
    for_each = length(var.kms_key_arns) > 0 ? [1] : []
    content {
      sid       = "VpcAlbCallerKMSAccess"
      actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
      resources = var.kms_key_arns
    }
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

resource "aws_iam_role_policy" "workers_sqs" {
  for_each = toset(local.worker_names)
  name     = "sqs-dlq-policy"
  role     = aws_iam_role.workers[each.key].id
  policy   = data.aws_iam_policy_document.workers_sqs.json
}

data "aws_iam_policy_document" "workers_sqs" {
  dynamic "statement" {
    for_each = length(var.queue_arns) > 0 ? [1] : []
    content {
      # checkov:skip=CKV_AWS_111: "SQS DLQ SendMessage action is scoped to the specifically passed queue ARNs"
      # checkov:skip=CKV_AWS_356: "SQS DLQ SendMessage action requires queue ARNs which may be dynamically generated"
      sid    = "AllowSQSSendMessage"
      effect = "Allow"
      actions = [
        "sqs:SendMessage"
      ]
      resources = var.queue_arns
    }
  }
}

data "aws_iam_policy_document" "member_telemetry_assume_role" {
  count = var.create_member_telemetry_ingestion_role ? 1 : 0
  statement {
    actions = [
      "sts:AssumeRole",
      "sts:TagSession"
    ]
    principals {
      type        = "AWS"
      identifiers = var.trusted_cost_puller_role_arns
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = var.trusted_tenant_ids
    }
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/tenant_id"
      values   = var.trusted_tenant_ids
    }
  }
}

# checkov:skip=CKV_AWS_274: "Permissions boundary is managed at the organization level or by the member account platform controls"
resource "aws_iam_role" "member_telemetry_ingestion" {
  count              = var.create_member_telemetry_ingestion_role ? 1 : 0
  name               = var.telemetry_member_role_name
  assume_role_policy = data.aws_iam_policy_document.member_telemetry_assume_role[0].json
  tags               = var.tags
}

data "aws_iam_policy_document" "member_telemetry_ingestion" {
  count = var.create_member_telemetry_ingestion_role ? 1 : 0

  statement {
    # checkov:skip=CKV_AWS_111: "ce:GetCostAndUsage and cloudwatch:GetMetricData do not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "ce:GetCostAndUsage and cloudwatch:GetMetricData require wildcard resource"
    # checkov:skip=CKV_AWS_108: "ce:GetCostAndUsage requires wildcard resource *"
    sid = "AllowMemberCostExplorerAndMetrics"
    actions = [
      "ce:GetCostAndUsage",
      "cloudwatch:GetMetricData"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "member_telemetry_ingestion" {
  count  = var.create_member_telemetry_ingestion_role ? 1 : 0
  name   = "member-telemetry-ingestion-policy"
  role   = aws_iam_role.member_telemetry_ingestion[0].id
  policy = data.aws_iam_policy_document.member_telemetry_ingestion[0].json
}
