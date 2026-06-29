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

  point_in_time_recovery {
    enabled = true
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

  point_in_time_recovery {
    enabled = true
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

  point_in_time_recovery {
    enabled = true
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

  point_in_time_recovery {
    enabled = true
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

  point_in_time_recovery {
    enabled = true
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

  point_in_time_recovery {
    enabled = true
  }



  tags = var.tags
}

# - Error budget table (Hash key: tenant_id)
resource "aws_dynamodb_table" "error_budget" {
  name         = "${var.project_name}-${var.environment}-error-budget"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }



  tags = var.tags
}



# - Rollback Cache table (Hash key: anomaly_id)
resource "aws_dynamodb_table" "rollback_cache" {
  name         = "${var.project_name}-${var.environment}-rollback-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "anomaly_id"

  attribute {
    name = "anomaly_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl_expiry"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }



  tags = var.tags
}

# - AI payload idempotency hot path (Hash key: idempotency_key, TTL: ttl_expiry)
# Separate from run_state: this table is the contract idempotency store for /v1/detect,
# /v1/decide, and /v1/verify; run_state remains Step Functions run-control only.
resource "aws_dynamodb_table" "ai_payload_idempotency" {
  name         = "finops-idempotency-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "idempotency_key"

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  ttl {
    attribute_name = "ttl_expiry"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.ddb_kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

# CloudWatch Log Group for Step Functions execution logs
resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/vendedlogs/states/${var.project_name}-${var.environment}-workflow"
  retention_in_days = 365
  kms_key_id        = var.cloudwatch_log_kms_key_arn
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "feedback_sfn" {
  name              = "/aws/vendedlogs/states/${var.project_name}-${var.environment}-human-feedback"
  retention_in_days = 365
  kms_key_id        = var.cloudwatch_log_kms_key_arn
  tags              = var.tags
}

# Step Functions Standard State Machine:
resource "aws_sfn_state_machine" "workflow" {
  name     = "${var.project_name}-${var.environment}-workflow"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode(jsondecode(templatefile("${path.module}/statemachine.json", {
    state_lambda_arn                 = var.lambda_function_arns["state"]
    cost_puller_lambda_arn           = var.lambda_function_arns["cost_puller"]
    normalizer_lambda_arn            = var.lambda_function_arns["normalizer"]
    vpc_alb_caller_lambda_arn        = var.lambda_function_arns["vpc_alb_caller"]
    router_lambda_arn                = var.lambda_function_arns["router"]
    audit_writer_lambda_arn          = var.lambda_function_arns["audit_writer"]
    containment_worker_lambda_arn    = var.lambda_function_arns["containment_worker"]
    finance_alerts_sns_topic_arn     = var.finance_alerts_topic_arn
    engineering_alerts_sns_topic_arn = var.engineering_alerts_topic_arn

    account_policy_table_name  = aws_dynamodb_table.account_policy.name
    rollback_cache_table_name  = aws_dynamodb_table.rollback_cache.name
    rollback_status_queue_url  = aws_sqs_queue.rollback_status_queue.id
    ai_engine_contract_version = var.ai_engine_contract_version
    cur_retry_interval_seconds = var.cur_retry_interval_seconds
  })))

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tracing_configuration {
    enabled = true
  }

  tags = var.tags
}

resource "aws_sfn_state_machine" "feedback" {
  name     = "${var.project_name}-${var.environment}-human-feedback"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode(jsondecode(templatefile("${path.module}/feedback_statemachine.json", {
    vpc_alb_caller_lambda_arn = var.lambda_function_arns["vpc_alb_caller"]
    audit_writer_lambda_arn   = var.lambda_function_arns["audit_writer"]
  })))

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.feedback_sfn.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tracing_configuration {
    enabled = true
  }

  tags = var.tags
}

# EventBridge Scheduler schedule with 24h default expression.
resource "aws_scheduler_schedule" "run_workflow" {
  name        = "${var.project_name}-${var.environment}-schedule"
  description = "Triggers the Step Functions workflow on a schedule"
  group_name  = "default"
  kms_key_arn = var.scheduler_kms_key_arn
  state       = var.scheduler_enabled ? "ENABLED" : "DISABLED"

  schedule_expression = var.scheduler_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.workflow.arn
    role_arn = aws_iam_role.scheduler.arn

    input = jsonencode({
      account_id   = data.aws_caller_identity.current.account_id
      is_ad_hoc    = false
      trigger_type = "scheduled"
    })
  }
}



# Rollback/status queue
resource "aws_sqs_queue" "rollback_status_queue" {
  name                              = "${var.project_name}-${var.environment}-rollback-status-queue"
  kms_master_key_id                 = var.sqs_kms_key_arn
  kms_data_key_reuse_period_seconds = 300
  visibility_timeout_seconds        = 300
  message_retention_seconds         = 1209600 # 14 days

  tags = var.tags
}

resource "terraform_data" "destroy_guard" {
  count = var.destroyable ? 0 : 1
  lifecycle {
    prevent_destroy = true
  }
}
