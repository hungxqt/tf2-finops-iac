# ECR Repository for the AI Engine Images
resource "aws_ecr_repository" "ai_engine" {
  name                 = "${var.project_name}-${var.environment}-ai-engine"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }

  tags = var.tags
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "request" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-ai-request"
  retention_in_days = 365
  kms_key_id        = length(var.kms_key_arns) > 0 ? var.kms_key_arns[0] : null
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-ai-worker"
  retention_in_days = 365
  kms_key_id        = length(var.kms_key_arns) > 0 ? var.kms_key_arns[0] : null
  tags              = var.tags
}

# IAM Execution Roles
resource "aws_iam_role" "request" {
  name = "${var.project_name}-${var.environment}-ai-request-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "request_vpc" {
  role       = aws_iam_role.request.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_policy" "request" {
  name = "${var.project_name}-${var.environment}-ai-request-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = [var.detect_queue_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = [var.results_table_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["${aws_cloudwatch_log_group.request.arn}:*"]
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = ["*"]
      }
      ],
      length(var.secret_arns) > 0 ? [
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:GetSecretValue"
          ]
          Resource = var.secret_arns
        }
      ] : [],
      length(var.kms_key_arns) > 0 ? [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:GenerateDataKey"
          ]
          Resource = var.kms_key_arns
        }
    ] : [])
  })
}

resource "aws_iam_role_policy_attachment" "request" {
  role       = aws_iam_role.request.name
  policy_arn = aws_iam_policy.request.arn
}

resource "aws_iam_role" "worker" {
  name = "${var.project_name}-${var.environment}-ai-worker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "worker_vpc" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_policy" "worker" {
  name = "${var.project_name}-${var.environment}-ai-worker-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [var.detect_queue_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = ["arn:aws:s3:::${var.curated_bucket_name}/*"]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = ["arn:aws:s3:::${var.evidence_bucket_name}/${var.evidence_prefix}*"]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [var.results_table_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["${aws_cloudwatch_log_group.worker.arn}:*"]
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = ["*"]
      }
      ],
      length(var.secret_arns) > 0 ? [
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:GetSecretValue"
          ]
          Resource = var.secret_arns
        }
      ] : [],
      length(var.kms_key_arns) > 0 ? [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:GenerateDataKey"
          ]
          Resource = var.kms_key_arns
        }
    ] : [])
  })
}

resource "aws_iam_role_policy_attachment" "worker" {
  role       = aws_iam_role.worker.name
  policy_arn = aws_iam_policy.worker.arn
}

# Request Lambda Container Function
resource "aws_lambda_function" "request" {
  # checkov:skip=CKV_AWS_272: "Code signing is not supported for container image Lambda packages (package_type = Image)"
  # checkov:skip=CKV_AWS_116: "Lambda DLQ is not used because this function is invoked synchronously by Step Functions"
  function_name = "${var.project_name}-${var.environment}-ai-request"
  role          = aws_iam_role.request.arn
  package_type  = "Image"
  image_uri     = var.request_image_uri
  timeout       = var.request_timeout_seconds
  publish       = true
  kms_key_arn   = length(var.kms_key_arns) > 0 ? var.kms_key_arns[0] : null

  reserved_concurrent_executions = var.request_reserved_concurrency

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      ENVIRONMENT                = var.environment
      PROJECT_NAME               = var.project_name
      DETECT_QUEUE_URL           = var.detect_queue_url
      RESULTS_TABLE_NAME         = var.results_table_name
      AI_ENGINE_CONTRACT_VERSION = var.ai_engine_contract_version
    }
  }

  depends_on = [aws_cloudwatch_log_group.request]
  tags       = var.tags
}

resource "aws_lambda_alias" "request" {
  name             = "live"
  description      = "Alias for live deployment"
  function_name    = aws_lambda_function.request.function_name
  function_version = aws_lambda_function.request.version
}

# Worker Lambda Container Function
resource "aws_lambda_function" "worker" {
  # checkov:skip=CKV_AWS_272: "Code signing is not supported for container image Lambda packages (package_type = Image)"
  # checkov:skip=CKV_AWS_116: "Lambda DLQ is not used because this function is triggered by SQS which has its own SQS DLQ"
  function_name = "${var.project_name}-${var.environment}-ai-worker"
  role          = aws_iam_role.worker.arn
  package_type  = "Image"
  image_uri     = var.worker_image_uri
  timeout       = var.worker_timeout_seconds
  publish       = true
  kms_key_arn   = length(var.kms_key_arns) > 0 ? var.kms_key_arns[0] : null

  reserved_concurrent_executions = var.worker_reserved_concurrency

  ephemeral_storage {
    size = var.worker_ephemeral_storage_mb
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      ENVIRONMENT                = var.environment
      PROJECT_NAME               = var.project_name
      CURATED_BUCKET_NAME        = var.curated_bucket_name
      EVIDENCE_BUCKET_NAME       = var.evidence_bucket_name
      EVIDENCE_PREFIX            = var.evidence_prefix
      RESULTS_TABLE_NAME         = var.results_table_name
      AI_ENGINE_CONTRACT_VERSION = var.ai_engine_contract_version
    }
  }

  depends_on = [aws_cloudwatch_log_group.worker]
  tags       = var.tags
}

resource "aws_lambda_alias" "worker" {
  name             = "live"
  description      = "Alias for live deployment"
  function_name    = aws_lambda_function.worker.function_name
  function_version = aws_lambda_function.worker.version
}

# Event Source Mapping (SQS to Worker Lambda)
resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn = var.detect_queue_arn
  function_name    = aws_lambda_alias.worker.arn
  batch_size       = var.worker_batch_size
  enabled          = true

  dynamic "scaling_config" {
    for_each = var.worker_max_concurrency != null ? [1] : []
    content {
      maximum_concurrency = var.worker_max_concurrency
    }
  }
}
