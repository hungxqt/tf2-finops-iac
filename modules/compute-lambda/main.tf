# Compute Lambda Module Resources
# This module packages and deploys Lambda worker functions.

locals {
  lambda_archive_dir = "${path.module}/../../.build/lambda"
  workers            = ["state", "cost_puller", "normalizer", "ai_client", "router", "audit_writer", "containment_worker"]

  worker_configs = {
    state = {
      timeout     = 30
      memory_size = 256
      env = {
        RUN_STATE_TABLE_NAME = lookup(var.dynamodb_table_names, "run_state", "")
      }
    }
    cost_puller = {
      timeout     = 120
      memory_size = 512
      env = {
        LAKEHOUSE_BUCKET_NAME = var.lakehouse_bucket_name
      }
    }
    normalizer = {
      timeout     = 120
      memory_size = 512
      env = {
        LAKEHOUSE_BUCKET_NAME = var.lakehouse_bucket_name
      }
    }
    ai_client = {
      timeout     = 30
      memory_size = 256
      env = {
        AI_ENGINE_ENDPOINT_URL     = var.ai_engine_endpoint_url
        AI_ENGINE_SECRET_NAME      = var.ai_engine_secret_name
        AI_ENGINE_CONTRACT_VERSION = "v1.0"
        AI_ENGINE_ALLOWED_HOSTS    = "ai-engine.${var.project_name}-${var.environment}.local"
        AI_ENGINE_TIMEOUT_SECONDS  = "10"
        AI_ENGINE_RETRY_ATTEMPTS   = "3"
        AWS_REGION                 = var.aws_region
      }
    }
    router = {
      timeout     = 30
      memory_size = 256
      env = {
        ROUTING_STATE_TABLE_NAME = lookup(var.dynamodb_table_names, "routing_state", "")
      }
    }
    audit_writer = {
      timeout     = 30
      memory_size = 256
      env = {
        AUDIT_BUCKET_NAME = var.audit_bucket_name
        AUDIT_TABLE_NAME  = lookup(var.dynamodb_table_names, "audit", "")
      }
    }
    containment_worker = {
      timeout     = 60
      memory_size = 256
      env = {
        CONTAINMENT_APPLY_ENABLED = tostring(var.containment_apply_enabled)
      }
    }
  }
}

# AWS Lambda Functions
resource "aws_lambda_function" "workers" {
  for_each      = toset(local.workers)
  function_name = "${var.project_name}-${var.environment}-${each.key}"
  role          = lookup(var.lambda_role_arns, each.key, "")
  handler       = "workers.${each.key}.handler.handle_request"
  runtime       = "python3.13"
  filename      = "${local.lambda_archive_dir}/${each.key}.zip"

  # We can calculate source_code_hash dynamically to update when code changes
  source_code_hash = fileexists("${local.lambda_archive_dir}/${each.key}.zip") ? filebase64sha256("${local.lambda_archive_dir}/${each.key}.zip") : null

  timeout     = local.worker_configs[each.key].timeout
  memory_size = local.worker_configs[each.key].memory_size

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config {
    mode = "Active"
  }

  reserved_concurrent_executions = 10

  environment {
    variables = local.worker_configs[each.key].env
  }

  tags = var.tags
}

# CloudWatch Log Groups with retention
resource "aws_cloudwatch_log_group" "logs" {
  for_each          = toset(local.workers)
  name              = "/aws/lambda/${aws_lambda_function.workers[each.key].function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# Stable Lambda Alias
resource "aws_lambda_alias" "stable" {
  for_each         = toset(local.workers)
  name             = "stable"
  description      = "Stable version alias"
  function_name    = aws_lambda_function.workers[each.key].function_name
  function_version = aws_lambda_function.workers[each.key].version
}

# Canary Lambda Alias
resource "aws_lambda_alias" "canary" {
  for_each         = toset(local.workers)
  name             = "canary"
  description      = "Canary version alias pointing to LATEST"
  function_name    = aws_lambda_function.workers[each.key].function_name
  function_version = "$LATEST"
}
