data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

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

  lifecycle {
    create_before_destroy = true
  }
}


# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "request" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-ai-request"
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
      },
      {
        # checkov:skip=CKV_AWS_111: "EC2 Container Registry read actions are needed on all repositories to support dynamic image configuration"
        # checkov:skip=CKV_AWS_356: "EC2 Container Registry read actions require wildcard resource to support dynamic image configuration"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
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
      ] : [],
      var.ai_request_s3_pointer_bucket_arn != "" ? [
        {
          # checkov:skip=CKV_AWS_356: "s3:ListBucket with prefix condition is appropriately scoped"
          Sid      = "AIRequestS3PointerList"
          Effect   = "Allow"
          Action   = ["s3:ListBucket"]
          Resource = [var.ai_request_s3_pointer_bucket_arn]
          Condition = {
            StringLike = {
              "s3:prefix" = var.ai_request_s3_pointer_prefixes
            }
          }
        }
      ] : [],
      var.ai_request_s3_pointer_bucket_arn != "" ? [
        {
          Sid      = "AIRequestS3PointerGet"
          Effect   = "Allow"
          Action   = ["s3:GetObject"]
          Resource = [for p in var.ai_request_s3_pointer_prefixes : "${var.ai_request_s3_pointer_bucket_arn}/${p}"]
        }
      ] : []
    )
  })
}

resource "aws_iam_role_policy_attachment" "request" {
  role       = aws_iam_role.request.name
  policy_arn = aws_iam_policy.request.arn
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
      AI_ENGINE_CONTRACT_VERSION = var.ai_engine_contract_version
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.request,
    aws_iam_role_policy_attachment.request_vpc,
    aws_iam_role_policy_attachment.request
  ]
  tags = var.tags
}

resource "aws_lambda_alias" "request" {
  name             = "live"
  description      = "Alias for live deployment"
  function_name    = aws_lambda_function.request.function_name
  function_version = aws_lambda_function.request.version

  lifecycle {
    ignore_changes = [
      function_version,
      routing_config
    ]
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

resource "aws_security_group_rule" "alb_ingress_cloudfront" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  prefix_list_ids   = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  security_group_id = aws_security_group.alb.id
  description       = "Allow HTTPS from CloudFront origin-facing IPs"
}

# trivy:ignore:AVD-AWS-0104
# trivy:ignore:AWS-0104
resource "aws_security_group_rule" "alb_egress_all" {
  # checkov:skip=CKV_AWS_382: "Internal ALB requires unrestricted egress to allow routing to dynamic Lambda target groups"
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
  # checkov:skip=CKV_AWS_192: "Log4j protection is managed at the Lambda runtime level, not WAF"
  # checkov:skip=CKV2_AWS_31: "WAF logging is disabled to reduce logging storage and cost in non-prod environments"
  name        = "${var.project_name}-${var.environment}-ai-waf"
  description = "WAF for AI Engine internal ALB"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "BlockMissingTenantId"
    priority = 1

    action {
      block {}
    }

    statement {
      and_statement {
        statement {
          byte_match_statement {
            search_string         = "/v1/"
            positional_constraint = "STARTS_WITH"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
        statement {
          not_statement {
            statement {
              size_constraint_statement {
                comparison_operator = "GT"
                size                = 0
                field_to_match {
                  single_header {
                    name = "x-tenant-id"
                  }
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AIMissingTenantIdMetric"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "TenantRateLimit"
    priority = 2

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit                 = 100
        aggregate_key_type    = "CUSTOM_KEYS"
        evaluation_window_sec = 60

        scope_down_statement {
          byte_match_statement {
            search_string         = "/v1/"
            positional_constraint = "STARTS_WITH"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }

        custom_key {
          header {
            name = "x-tenant-id"
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AITenantRateLimitMetric"
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

# CodeDeploy Role for Lambda Deployment
resource "aws_iam_role" "codedeploy" {
  count = var.enable_codedeploy ? 1 : 0
  name  = "${var.project_name}-${var.environment}-codedeploy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "codedeploy.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "codedeploy" {
  count      = var.enable_codedeploy ? 1 : 0
  role       = aws_iam_role.codedeploy[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSCodeDeployRoleForLambda"
}

# CloudWatch Rollback Alarms
# checkov:skip=CKV_AWS_119: "Alarm actions are configured dynamically via variables and may be empty in non-production environments to avoid unnecessary notifications"
resource "aws_cloudwatch_metric_alarm" "request_errors" {
  count               = var.enable_codedeploy ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-ai-request-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda errors for AI Request function"
  alarm_actions       = var.codedeploy_alarm_actions

  dimensions = {
    FunctionName = aws_lambda_function.request.function_name
    Resource     = "${aws_lambda_function.request.function_name}:${aws_lambda_alias.request.name}"
  }

  tags = var.tags
}

# checkov:skip=CKV_AWS_119: "Alarm actions are configured dynamically via variables and may be empty in non-production environments to avoid unnecessary notifications"
resource "aws_cloudwatch_metric_alarm" "request_throttles" {
  count               = var.enable_codedeploy ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-ai-request-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda throttles for AI Request function"
  alarm_actions       = var.codedeploy_alarm_actions

  dimensions = {
    FunctionName = aws_lambda_function.request.function_name
    Resource     = "${aws_lambda_function.request.function_name}:${aws_lambda_alias.request.name}"
  }

  tags = var.tags
}

# checkov:skip=CKV_AWS_119: "Alarm actions are configured dynamically via variables and may be empty in non-production environments to avoid unnecessary notifications"
resource "aws_cloudwatch_metric_alarm" "request_p99_duration" {
  count               = var.enable_codedeploy ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-ai-request-p99-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  extended_statistic  = "p99"
  threshold           = var.deployment_p99_latency_threshold_ms
  alarm_description   = "P99 duration threshold exceeded for AI Request function"
  alarm_actions       = var.codedeploy_alarm_actions

  dimensions = {
    FunctionName = aws_lambda_function.request.function_name
    Resource     = "${aws_lambda_function.request.function_name}:${aws_lambda_alias.request.name}"
  }

  tags = var.tags
}

# checkov:skip=CKV_AWS_119: "Alarm actions are configured dynamically via variables and may be empty in non-production environments to avoid unnecessary notifications"
resource "aws_cloudwatch_metric_alarm" "alb_target_5xx" {
  count               = var.enable_codedeploy ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-ai-request-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "ALB target 5xx errors for AI Target Group"
  alarm_actions       = var.codedeploy_alarm_actions

  dimensions = {
    TargetGroup  = aws_lb_target_group.ai.arn_suffix
    LoadBalancer = aws_lb.ai.arn_suffix
  }

  tags = var.tags
}

# CodeDeploy Application and Deployment Group
resource "aws_codedeploy_app" "request" {
  count            = var.enable_codedeploy ? 1 : 0
  compute_platform = "Lambda"
  name             = "${var.project_name}-${var.environment}-ai-request"
  tags             = var.tags
}

resource "aws_codedeploy_deployment_group" "request" {
  count                  = var.enable_codedeploy ? 1 : 0
  app_name               = aws_codedeploy_app.request[0].name
  deployment_group_name  = "${var.project_name}-${var.environment}-ai-request-dg"
  service_role_arn       = aws_iam_role.codedeploy[0].arn
  deployment_config_name = var.codedeploy_deployment_config_name

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "ALARM_TO_REVERT"]
  }

  alarm_configuration {
    enabled = true
    alarms = concat(
      [
        aws_cloudwatch_metric_alarm.request_errors[0].alarm_name,
        aws_cloudwatch_metric_alarm.request_throttles[0].alarm_name,
        aws_cloudwatch_metric_alarm.request_p99_duration[0].alarm_name,
        aws_cloudwatch_metric_alarm.alb_target_5xx[0].alarm_name
      ],
      var.codedeploy_extra_alarm_names
    )
    ignore_poll_alarm_failure = false
  }

  tags = var.tags
}

