# Compute Lambda Module Resources
# This module packages, signs, and deploys Lambda worker functions with hardened security controls.

locals {
  lambda_archive_dir = "${path.module}/../../.build/lambda"
  workers            = ["state", "cost_puller", "normalizer", "router", "audit_writer", "containment_worker", "vpc_alb_caller"]

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
        LAKEHOUSE_BUCKET_NAME      = var.lakehouse_bucket_name
        CUR_SOURCE_BUCKET          = var.cur_source_bucket
        CUR_SOURCE_PREFIX          = var.cur_source_prefix
        CUR_DELAY_THRESHOLD_HOURS  = tostring(var.cur_delay_threshold_hours)
        CE_LOOKBACK_WINDOW_DAYS    = tostring(var.ce_lookback_window_days)
        TRAFFIC_METRIC_IDENTIFIERS = join(",", var.traffic_metric_identifiers)
        SYNTHETIC_FALLBACK_ENABLED = tostring(var.synthetic_fallback_enabled)
      }
    }
    normalizer = {
      timeout     = 120
      memory_size = 512
      env = {
        LAKEHOUSE_BUCKET_NAME = var.lakehouse_bucket_name
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
    vpc_alb_caller = {
      timeout     = 90
      memory_size = 256
      env = {
        ALB_BASE_URL            = var.alb_base_url
        SIGV4_SERVICE_NAME      = var.sigv4_service_name
        REQUEST_TIMEOUT_SECONDS = "60"
      }
    }
  }
}

# Lambda Security Group (Created in compute-lambda to align security group with the attached resource)
resource "aws_security_group" "lambda" {
  name        = "${var.project_name}-${var.environment}-lambda-sg"
  description = "Security group for Lambda workers"
  vpc_id      = var.vpc_id
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-sg"
    }
  )
}

# Allow outbound HTTPS only (port 443) from Lambda to NAT/VPC endpoints
# trivy:ignore:AVD-AWS-0104
# trivy:ignore:AWS-0104
resource "aws_vpc_security_group_egress_rule" "lambda_https" {
  security_group_id = aws_security_group.lambda.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Allow HTTPS outbound traffic from Lambda"
}

# Ingress rule for VPC Endpoint Security Group allowing ingress from Lambda security group
resource "aws_vpc_security_group_ingress_rule" "endpoints_from_lambda" {
  security_group_id            = var.vpc_endpoint_security_group_id
  referenced_security_group_id = aws_security_group.lambda.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Allow HTTPS from Lambda security group"
}

# AWS Signer Profile for Code Signing
resource "aws_signer_signing_profile" "lambda_signer" {
  platform_id = "AWSLambda-SHA384-ECDSA"
  name_prefix = replace("${var.project_name}${var.environment}signer", "/[^a-zA-Z0-9]/", "")
  tags        = var.tags
}

# AWS Lambda Code Signing Configuration
resource "aws_lambda_code_signing_config" "signed_config" {
  allowed_publishers {
    signing_profile_version_arns = [aws_signer_signing_profile.lambda_signer.arn]
  }
  policies {
    untrusted_artifact_on_deployment = "Warn"
  }
}

# SQS Dead Letter Queue for synchronous Lambda failures
resource "aws_sqs_queue" "lambda_dlq" {
  name                              = "${var.project_name}-${var.environment}-lambda-dlq"
  kms_master_key_id                 = var.sqs_kms_key_arn
  kms_data_key_reuse_period_seconds = 300
  message_retention_seconds         = 1209600 # 14 days
  tags                              = var.tags
}

# AWS Lambda Functions
resource "aws_lambda_function" "workers" {
  for_each      = toset(local.workers)
  function_name = "${var.project_name}-${var.environment}-${each.key}"
  role          = lookup(var.lambda_role_arns, each.key, "")
  handler       = "workers.${each.key}.handler.handle_request"
  runtime       = "python3.13"
  filename      = "${local.lambda_archive_dir}/${each.key}.zip"

  # We calculate source_code_hash dynamically to update when code changes
  source_code_hash = fileexists("${local.lambda_archive_dir}/${each.key}.zip") ? filebase64sha256("${local.lambda_archive_dir}/${each.key}.zip") : null

  timeout     = local.worker_configs[each.key].timeout
  memory_size = local.worker_configs[each.key].memory_size

  # Code signing and encryption hardening
  code_signing_config_arn = aws_lambda_code_signing_config.signed_config.arn
  kms_key_arn             = var.lambda_env_kms_key_arn

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  tracing_config {
    mode = "Active"
  }

  reserved_concurrent_executions = var.reserved_concurrent_executions

  environment {
    variables = local.worker_configs[each.key].env
  }

  depends_on = [
    aws_cloudwatch_log_group.logs
  ]

  tags = var.tags
}

# CloudWatch Log Groups with retention and encryption
resource "aws_cloudwatch_log_group" "logs" {
  for_each          = toset(local.workers)
  name              = "/aws/lambda/${var.project_name}-${var.environment}-${each.key}"
  retention_in_days = 365
  kms_key_id        = var.cloudwatch_log_kms_key_arn
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
