data "aws_caller_identity" "current" {}

# Generate self-signed certificate if no certificate_arn is provided or if it's the dummy certificate
locals {
  is_dummy_cert = var.alb_certificate_arn == "" || contains(split(":", var.alb_certificate_arn), "123456789012")
}

resource "tls_private_key" "self_signed" {
  count     = local.is_dummy_cert ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "self_signed" {
  count           = local.is_dummy_cert ? 1 : 0
  private_key_pem = tls_private_key.self_signed[0].private_key_pem

  subject {
    common_name  = "*.ap-southeast-1.compute.internal"
    organization = "TF2 FinOps"
  }

  validity_period_hours = 87600 # 10 years

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]
}

resource "aws_acm_certificate" "self_signed" {
  count            = local.is_dummy_cert ? 1 : 0
  private_key      = tls_private_key.self_signed[0].private_key_pem
  certificate_body = tls_self_signed_cert.self_signed[0].cert_pem
}

# ECR Repository for the AI Engine Images
resource "aws_ecr_repository" "ai_engine" {
  name                 = "${var.project_name}-${var.environment}-ai-engine"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.destroyable

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }

  tags = var.tags
}

resource "aws_ecr_repository_policy" "lambda" {
  repository = aws_ecr_repository.ai_engine.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaECRImageRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
      },
      {
        Sid    = "AllowAccountAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
      }
    ]
  })
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

  depends_on = [aws_cloudwatch_log_group.request, aws_ecr_repository_policy.lambda]
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

  depends_on = [aws_cloudwatch_log_group.worker, aws_ecr_repository_policy.lambda]
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

# Internal ALB for AI Request Lambda integration
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-${var.environment}-ai-alb-sg"
  description = "Security group for AI Engine internal ALB"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group_rule" "alb_ingress_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_block]
  security_group_id = aws_security_group.alb.id
  description       = "Allow HTTPS from within the VPC"
}

resource "aws_security_group_rule" "alb_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
  description       = "Allow all outbound traffic"
}

resource "aws_lb" "ai" {
  # checkov:skip=CKV_AWS_150: "Deletion protection is disabled for non-prod environments to allow teardown"
  # checkov:skip=CKV_AWS_91: "Access logging is optional and configurable"
  name                       = "${var.project_name}-${var.environment}-ai-alb"
  internal                   = true
  load_balancer_type         = "application"
  subnets                    = var.private_subnet_ids
  security_groups            = [aws_security_group.alb.id]
  enable_deletion_protection = false
  drop_invalid_header_fields = true

  dynamic "access_logs" {
    for_each = var.alb_access_logs_bucket != "" ? [1] : []
    content {
      bucket  = var.alb_access_logs_bucket
      prefix  = var.alb_access_logs_prefix
      enabled = true
    }
  }

  tags = var.tags
}

resource "aws_lb_target_group" "ai" {
  name        = "${var.project_name}-${var.environment}-ai-tg"
  target_type = "lambda"

  tags = var.tags
}

resource "aws_lb_target_group_attachment" "ai" {
  target_group_arn = aws_lb_target_group.ai.arn
  target_id        = aws_lambda_alias.request.arn
  depends_on       = [aws_lambda_permission.alb_invoke_request]
}

resource "aws_lambda_permission" "alb_invoke_request" {
  statement_id  = "AllowALBInvokeRequestLambda"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.request.function_name
  principal     = "elasticloadbalancing.amazonaws.com"
  source_arn    = aws_lb_target_group.ai.arn
  qualifier     = aws_lambda_alias.request.name
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.ai.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = local.is_dummy_cert ? aws_acm_certificate.self_signed[0].arn : var.alb_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ai.arn
  }
}

resource "aws_wafv2_web_acl" "alb" {
  # checkov:skip=CKV_AWS_84: "WAF logging is disabled to reduce costs in sandbox"
  name        = "${var.project_name}-${var.environment}-ai-waf"
  description = "WAF for AI Engine internal ALB"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "RateLimit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AIRateLimitMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "AIWebACLMetric"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = aws_lb.ai.arn
  web_acl_arn  = aws_wafv2_web_acl.alb.arn
}

resource "aws_route53_record" "alb" {
  count   = var.private_hosted_zone_id != "" && var.private_dns_name != "" ? 1 : 0
  zone_id = var.private_hosted_zone_id
  name    = var.private_dns_name
  type    = "A"

  alias {
    name                   = aws_lb.ai.dns_name
    zone_id                = aws_lb.ai.zone_id
    evaluate_target_health = true
  }
}

resource "terraform_data" "destroy_guard" {
  count = var.destroyable ? 0 : 1
  lifecycle {
    prevent_destroy = true
  }
}

