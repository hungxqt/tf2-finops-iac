data "aws_caller_identity" "current" {}

# DynamoDB Tables:
# - Run state (Hash key: idempotency_key)
resource "aws_dynamodb_table" "run_state" {
  name         = "${var.project_name}-${var.environment}-run-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "idempotency_key"

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# - Anomaly records (Hash key: anomaly_id)
resource "aws_dynamodb_table" "anomaly" {
  name         = "${var.project_name}-${var.environment}-anomaly"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "anomaly_id"

  attribute {
    name = "anomaly_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# - Routing state (Hash key: route_id)
resource "aws_dynamodb_table" "routing_state" {
  name         = "${var.project_name}-${var.environment}-routing-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "route_id"

  attribute {
    name = "route_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# - Containment audit index (Hash key: audit_id)
resource "aws_dynamodb_table" "audit" {
  name         = "${var.project_name}-${var.environment}-containment-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "audit_id"

  attribute {
    name = "audit_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# - Dashboard materialized views (Hash key: view_id)
resource "aws_dynamodb_table" "dashboard_views" {
  name         = "${var.project_name}-${var.environment}-dashboard-views"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "view_id"

  attribute {
    name = "view_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# - Account policy table (Hash key: account_id)
resource "aws_dynamodb_table" "account_policy" {
  name         = "${var.project_name}-${var.environment}-account-policy"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "account_id"

  attribute {
    name = "account_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# Step Functions Standard State Machine:
locals {
  raw_definition = file("${path.module}/../../docs/statemachine.json")

  # Replace Lambda ARNs with exact matches from the map
  def_with_state       = replace(local.raw_definition, "arn:aws:lambda:ap-southeast-1:ACCOUNT_ID:function:tf2-finops-state", var.lambda_function_arns["state"])
  def_with_cost        = replace(local.def_with_state, "arn:aws:lambda:ap-southeast-1:ACCOUNT_ID:function:tf2-finops-cost-puller", var.lambda_function_arns["cost_puller"])
  def_with_norm        = replace(local.def_with_cost, "arn:aws:lambda:ap-southeast-1:ACCOUNT_ID:function:tf2-finops-normalizer", var.lambda_function_arns["normalizer"])
  def_with_ai          = replace(local.def_with_norm, "arn:aws:lambda:ap-southeast-1:ACCOUNT_ID:function:tf2-finops-ai-client", var.lambda_function_arns["ai_client"])
  def_with_router      = replace(local.def_with_ai, "arn:aws:lambda:ap-southeast-1:ACCOUNT_ID:function:tf2-finops-router", var.lambda_function_arns["router"])
  def_with_audit       = replace(local.def_with_router, "arn:aws:lambda:ap-southeast-1:ACCOUNT_ID:function:tf2-finops-audit-writer", var.lambda_function_arns["audit_writer"])
  def_with_containment = replace(local.def_with_audit, "arn:aws:lambda:ap-southeast-1:ACCOUNT_ID:function:tf2-finops-containment-worker", var.lambda_function_arns["containment_worker"])

  # Replace SNS Topic ARNs
  def_with_fin_sns = replace(local.def_with_containment, "arn:aws:sns:ap-southeast-1:ACCOUNT_ID:tf2-finops-finance-alerts", var.finance_alerts_topic_arn)
  def_with_eng_sns = replace(local.def_with_fin_sns, "arn:aws:sns:ap-southeast-1:ACCOUNT_ID:tf2-finops-engineering-alerts", var.engineering_alerts_topic_arn)

  # Replace DynamoDB table name
  definition = replace(local.def_with_eng_sns, "tf2-finops-account-policy", aws_dynamodb_table.account_policy.name)
}

resource "aws_sfn_state_machine" "workflow" {
  name     = "${var.project_name}-${var.environment}-workflow"
  role_arn = var.step_functions_role_arn

  definition = local.definition

  tags = var.tags
}

# EventBridge Scheduler schedule with 24h default expression.
resource "aws_scheduler_schedule" "run_workflow" {
  name        = "${var.project_name}-${var.environment}-schedule"
  description = "Triggers the Step Functions workflow on a schedule"
  group_name  = "default"

  schedule_expression = var.scheduler_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.workflow.arn
    role_arn = var.scheduler_role_arn

    input = jsonencode({
      account_id = data.aws_caller_identity.current.account_id
    })
  }
}
