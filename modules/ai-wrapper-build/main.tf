data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ECR Repository for the AI Engine Wrapper Images (Shared across all environments)
# trivy:ignore:AVD-AWS-0033
# trivy:ignore:AWS-0033
resource "aws_ecr_repository" "ai_engine" {
  name                 = "${var.project_name}-ai-wrapper"
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

resource "aws_cloudwatch_log_group" "codebuild" {
  # checkov:skip=CKV_AWS_338: "Build logs do not need to be retained for 1 year"
  name              = "/aws/codebuild/${var.project_name}-ai-wrapper-build"
  retention_in_days = 14
  kms_key_id        = var.kms_key_arn != "" ? var.kms_key_arn : null

  tags = var.tags
}

resource "aws_iam_role" "codebuild" {
  name               = "${var.project_name}-ai-wrapper-build-role"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume_role.json
  tags               = var.tags
}

data "aws_iam_policy_document" "codebuild_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "codebuild" {
  name   = "${var.project_name}-ai-wrapper-build-policy"
  role   = aws_iam_role.codebuild.name
  policy = data.aws_iam_policy_document.codebuild_policy.json
}

data "aws_iam_policy_document" "codebuild_policy" {
  # checkov:skip=CKV_AWS_111: "GetAuthorizationToken requires wildcard resource"
  # checkov:skip=CKV_AWS_356: "GetAuthorizationToken requires wildcard resource"
  # checkov:skip=CKV_AWS_109: "GetAuthorizationToken requires wildcard resource"
  # checkov:skip=CKV_AWS_107: "GetAuthorizationToken requires wildcard resource"
  statement {
    sid    = "AllowECRAuth"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr-public:GetAuthorizationToken",
      "sts:GetServiceBearerToken"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "AllowTargetECR"
    effect = "Allow"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:ListImages"
    ]
    resources = [aws_ecr_repository.ai_engine.arn]
  }

  statement {
    sid    = "AllowSourceECR"
    effect = "Allow"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
      "ecr:DescribeImages"
    ]
    resources = [var.aiops_source_ecr_repository_arn != "" ? var.aiops_source_ecr_repository_arn : "*"]
  }

  statement {
    sid    = "AllowSSMWrite"
    effect = "Allow"
    actions = [
      "ssm:PutParameter",
      "ssm:GetParameter"
    ]
    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/tf2-finops/${var.environment}/ai-wrapper/*"
    ]
  }

  statement {
    sid    = "AllowLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:${aws_cloudwatch_log_group.codebuild.name}:*"
    ]
  }
}

locals {
  buildspec = yamlencode({
    version = "0.2"
    phases = {
      pre_build = {
        commands = [
          "echo \"Validating UPSTREAM_IMAGE_URI...\"",
          "if [ -z \"$UPSTREAM_IMAGE_URI\" ]; then echo \"ERROR: UPSTREAM_IMAGE_URI environment variable is required.\"; exit 1; fi",
          "if ! echo \"$UPSTREAM_IMAGE_URI\" | grep -qE \"@sha256:[a-fA-F0-9]{64}$\"; then echo \"ERROR: UPSTREAM_IMAGE_URI must be pinned by digest (e.g. repo@sha256:<64-hex-chars>). Mutable tags are rejected.\"; exit 1; fi",
          "UPSTREAM_DIGEST=$(echo \"$UPSTREAM_IMAGE_URI\" | sed -E 's/.*@sha256:(.*)/\\1/')",
          "UPSTREAM_DIGEST_SHORT=$(echo \"$UPSTREAM_DIGEST\" | cut -c1-12)",
          "TARGET_TAG=\"wrapped-$${UPSTREAM_DIGEST_SHORT}\"",
          "echo \"Upstream Digest Short: $${UPSTREAM_DIGEST_SHORT}\"",
          "echo \"Target Tag: $${TARGET_TAG}\"",
          "echo \"Logging in to target ECR...\"",
          "TARGET_REGISTRY=$(echo \"$TARGET_ECR_REPO_URL\" | cut -d'/' -f1)",
          "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $TARGET_REGISTRY",
          "if [ -n \"$AIOPS_SOURCE_REGISTRY_ID\" ]; then echo \"Logging in to source ECR registry $AIOPS_SOURCE_REGISTRY_ID...\"; aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $${AIOPS_SOURCE_REGISTRY_ID}.dkr.ecr.$${AWS_DEFAULT_REGION}.amazonaws.com || echo \"Proceeding without logging in to source registry (assuming cross-account policy is set or image is public)\"; fi",
          "echo \"Logging in to public.ecr.aws...\"",
          "aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws || true",
          "echo \"Checking if target tag $TARGET_TAG already exists in target ECR...\"",
          "EXISTING_DIGEST=$(aws ecr describe-images --repository-name \"$TARGET_ECR_REPO_NAME\" --image-ids imageTag=\"$TARGET_TAG\" --query 'imageDetails[0].imageDigest' --output text 2>/dev/null || true)",
          "if [ -n \"$EXISTING_DIGEST\" ] && [ \"$EXISTING_DIGEST\" != \"None\" ]; then echo \"Found existing image with digest $EXISTING_DIGEST. Skipping rebuild.\"; WRAPPED_URI=\"$TARGET_ECR_REPO_URL@$EXISTING_DIGEST\"; echo \"Writing latest image URIs to SSM Parameter Store...\"; aws ssm put-parameter --name \"/tf2-finops/$${ENVIRONMENT}/ai-wrapper/latest-image-uri\" --value \"$WRAPPED_URI\" --type \"String\" --overwrite; aws ssm put-parameter --name \"/tf2-finops/$${ENVIRONMENT}/ai-wrapper/latest-upstream-image-uri\" --value \"$UPSTREAM_IMAGE_URI\" --type \"String\" --overwrite; echo \"Process complete. Wrapper URI is: $WRAPPED_URI\"; echo \"true\" > /tmp/skip_build; else echo \"false\" > /tmp/skip_build; fi"
        ]
      }
      build = {
        commands = [
          "SKIP_BUILD=$(cat /tmp/skip_build 2>/dev/null || echo \"false\")",
          "if [ \"$SKIP_BUILD\" = \"true\" ]; then echo \"Skipping build phase...\"; else echo \"Creating wrapper Dockerfile...\"; printf \"FROM %s\\nCOPY --from=%s /lambda-adapter /opt/extensions/lambda-adapter\\nENV AWS_LWA_PORT=8080\\nENV AWS_LWA_READINESS_CHECK_PATH=/health\\nENV AWS_LWA_ASYNC_INIT=true\\n\" \"$UPSTREAM_IMAGE_URI\" \"$LAMBDA_WEB_ADAPTER_IMAGE\" > Dockerfile; echo \"Building Docker image...\"; docker build -t \"$TARGET_ECR_REPO_URL:$TARGET_TAG\" .; fi"
        ]
      }
      post_build = {
        commands = [
          "SKIP_BUILD=$(cat /tmp/skip_build 2>/dev/null || echo \"false\")",
          "if [ \"$SKIP_BUILD\" = \"true\" ]; then echo \"Skipping post_build phase...\"; else echo \"Pushing Docker image to target ECR...\"; docker push \"$TARGET_ECR_REPO_URL:$TARGET_TAG\"; echo \"Retrieving pushed image digest...\"; PUSHED_DIGEST=$(aws ecr describe-images --repository-name \"$TARGET_ECR_REPO_NAME\" --image-ids imageTag=\"$TARGET_TAG\" --query 'imageDetails[0].imageDigest' --output text); WRAPPED_URI=\"$TARGET_ECR_REPO_URL@$PUSHED_DIGEST\"; echo \"Writing latest image URIs to SSM Parameter Store...\"; aws ssm put-parameter --name \"/tf2-finops/$${ENVIRONMENT}/ai-wrapper/latest-image-uri\" --value \"$WRAPPED_URI\" --type \"String\" --overwrite; aws ssm put-parameter --name \"/tf2-finops/$${ENVIRONMENT}/ai-wrapper/latest-upstream-image-uri\" --value \"$UPSTREAM_IMAGE_URI\" --type \"String\" --overwrite; echo \"Process complete. Wrapper URI is: $WRAPPED_URI\"; fi"
        ]
      }
    }
  })
}

resource "aws_codebuild_project" "wrapper_build" {
  # checkov:skip=CKV_AWS_316: "Privileged mode is required to build Docker images"
  name          = "${var.project_name}-ai-wrapper-build"
  description   = "CodeBuild project to build and publish the AI Engine wrapper image"
  build_timeout = 20
  service_role  = aws_iam_role.codebuild.arn

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type    = "BUILD_GENERAL1_SMALL"
    image           = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type            = "LINUX_CONTAINER"
    privileged_mode = true

    environment_variable {
      name  = "ENVIRONMENT"
      value = var.environment
    }

    environment_variable {
      name  = "TARGET_ECR_REPO_URL"
      value = aws_ecr_repository.ai_engine.repository_url
    }

    environment_variable {
      name  = "TARGET_ECR_REPO_NAME"
      value = aws_ecr_repository.ai_engine.name
    }

    environment_variable {
      name  = "LAMBDA_WEB_ADAPTER_IMAGE"
      value = var.lambda_web_adapter_image
    }

    environment_variable {
      name  = "AIOPS_SOURCE_REGISTRY_ID"
      value = var.aiops_source_registry_id
    }
  }

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.codebuild.name
      stream_name = "wrapper-build"
    }
  }

  source {
    type      = "NO_SOURCE"
    buildspec = local.buildspec
  }

  tags = var.tags
}
