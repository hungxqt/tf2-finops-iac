# IAM execution roles for Step Functions and EventBridge Scheduler.
# Located inside modules/orchestration because resources, Lambda versions, SNS topics, SQS queues and DynamoDB table ARNs are known here.

# 1. Step Functions Execution Role
data "aws_iam_policy_document" "sfn_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "step_functions" {
  name               = "${var.project_name}-${var.environment}-sfn-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "step_functions" {
  statement {
    sid       = "LambdaInvoke"
    actions   = ["lambda:InvokeFunction"]
    resources = values(var.lambda_function_arns)
  }

  statement {
    sid = "DynamoDBReadWrite"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem"
    ]
    resources = [
      aws_dynamodb_table.run_state.arn,
      aws_dynamodb_table.anomaly.arn,
      aws_dynamodb_table.routing_state.arn,
      aws_dynamodb_table.audit.arn,
      aws_dynamodb_table.dashboard_views.arn,
      aws_dynamodb_table.account_policy.arn,
      aws_dynamodb_table.error_budget.arn,
      aws_dynamodb_table.rollback_cache.arn
    ]
  }

  statement {
    sid     = "SNSPublish"
    actions = ["sns:Publish"]
    resources = [
      var.finance_alerts_topic_arn,
      var.engineering_alerts_topic_arn
    ]
  }

  statement {
    sid     = "SQSSendMessage"
    actions = ["sqs:SendMessage"]
    resources = [
      aws_sqs_queue.rollback_status_queue.arn
    ]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "CloudWatch Logs delivery APIs do not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "CloudWatch Logs delivery APIs require wildcard resource"
    sid = "CloudWatchLogsDelivery"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups"
    ]
    resources = ["*"]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "X-Ray tracing APIs do not support resource-level permissions"
    # checkov:skip=CKV_AWS_356: "X-Ray tracing APIs require wildcard resource"
    sid = "XRayTracing"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets"
    ]
    resources = ["*"]
  }

  statement {
    sid = "KMSDecryption"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
      "kms:Encrypt"
    ]
    resources = [
      var.ddb_kms_key_arn,
      var.sqs_kms_key_arn,
      var.cloudwatch_log_kms_key_arn
    ]
  }
}

resource "aws_iam_role_policy" "step_functions" {
  name   = "sfn-policy"
  role   = aws_iam_role.step_functions.id
  policy = data.aws_iam_policy_document.step_functions.json
}


# 2. EventBridge Scheduler Execution Role
data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.project_name}-${var.environment}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    sid       = "StartExecution"
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.workflow.arn]
  }

  statement {
    sid = "KMSScheduler"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey"
    ]
    resources = [var.scheduler_kms_key_arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "scheduler-policy"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}
