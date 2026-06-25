data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  queries = {
    spend_by_service = {
      description = "Total spend grouped by AWS service code for the past 30 days"
      query       = <<EOF
SELECT 
  line_item_product_code, 
  SUM(line_item_unblended_cost) AS total_cost
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -30, current_date)
GROUP BY line_item_product_code
ORDER BY total_cost DESC;
EOF
    }
    spend_by_account = {
      description = "Total spend grouped by AWS account for the past 30 days"
      query       = <<EOF
SELECT 
  line_item_usage_account_id, 
  SUM(line_item_unblended_cost) AS total_cost
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -30, current_date)
GROUP BY line_item_usage_account_id
ORDER BY total_cost DESC;
EOF
    }
    anomaly_spend_trends = {
      description = "Daily spend by service and account for the past 7 days"
      query       = <<EOF
SELECT 
  line_item_product_code, 
  line_item_usage_account_id, 
  SUM(line_item_unblended_cost) AS total_cost, 
  line_item_usage_start_date
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -7, current_date)
GROUP BY line_item_product_code, line_item_usage_account_id, line_item_usage_start_date
ORDER BY line_item_usage_start_date DESC;
EOF
    }
    spend_trend = {
      description = "Daily spend trends for the past 90 days"
      query       = <<EOF
SELECT 
  line_item_usage_start_date,
  SUM(line_item_unblended_cost) AS daily_cost
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -90, current_date)
GROUP BY line_item_usage_start_date
ORDER BY line_item_usage_start_date DESC;
EOF
    }
    anomaly_detail = {
      description = "Detailed look at anomalous cost entries exceeding standard thresholds"
      query       = <<EOF
SELECT 
  line_item_usage_start_date,
  line_item_usage_account_id,
  line_item_product_code,
  line_item_usage_type,
  line_item_unblended_cost
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -14, current_date)
  AND line_item_unblended_cost > 50.0
ORDER BY line_item_unblended_cost DESC;
EOF
    }
    containment_audit_summary = {
      description = "Summary of applied automated containment actions"
      query       = <<EOF
SELECT 
  actor,
  action,
  target_resource,
  status,
  timestamp
FROM "${var.glue_database_name}"."containment_audit"
WHERE timestamp >= date_add('day', -90, current_date)
ORDER BY timestamp DESC;
EOF
    }
    monthly_waste_summary = {
      description = "Monthly waste analysis by service for finance reporting (identifies non-prod and untagged costs)"
      query       = <<EOF
SELECT 
  line_item_product_code,
  SUM(line_item_unblended_cost) AS total_spent,
  SUM(CASE WHEN resource_tags_user_environment <> 'prod' THEN line_item_unblended_cost ELSE 0 END) AS non_prod_spent,
  SUM(CASE WHEN resource_tags_user_owner IS NULL OR resource_tags_user_owner = '' THEN line_item_unblended_cost ELSE 0 END) AS untagged_spent
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -30, current_date)
GROUP BY line_item_product_code
ORDER BY untagged_spent DESC;
EOF
    }
    dashboard_freshness = {
      description = "Check the timestamp of the latest cost records loaded"
      query       = <<EOF
SELECT 
  MAX(line_item_usage_start_date) AS last_updated_date,
  COUNT(*) AS total_records
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -2, current_date);
EOF
    }
  }
}

resource "aws_athena_named_query" "queries" {
  for_each    = local.queries
  name        = "${var.project_name}-${var.environment}-${replace(each.key, "_", "-")}"
  workgroup   = var.athena_workgroup_name
  database    = var.glue_database_name
  description = each.value.description
  query       = each.value.query
}

# 1. Private S3 bucket for static dashboard assets (replaceable)
resource "aws_s3_bucket" "dashboard_assets" {
  bucket        = "${var.project_name}-${var.environment}-dashboard-assets"
  force_destroy = true
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "dashboard_assets" {
  bucket                  = aws_s3_bucket.dashboard_assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.dashboard_kms_key_arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# 2. Private S3 bucket for precomputed dashboard JSON summaries (retained, prevent_destroy)
resource "aws_s3_bucket" "dashboard_data" {
  bucket        = "${var.project_name}-${var.environment}-dashboard-data"
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
  tags = var.tags
}

resource "aws_s3_bucket_public_access_block" "dashboard_data" {
  bucket                  = aws_s3_bucket.dashboard_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "dashboard_data" {
  bucket = aws_s3_bucket.dashboard_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dashboard_data" {
  bucket = aws_s3_bucket.dashboard_data.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.dashboard_kms_key_arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "dashboard_data" {
  bucket = aws_s3_bucket.dashboard_data.id
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# S3 Bucket CORS Configuration for the dashboard data bucket
resource "aws_s3_bucket_cors_configuration" "dashboard_data" {
  bucket = aws_s3_bucket.dashboard_data.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = [
      "http://localhost:3000",
      "http://localhost:5173",
      "https://${aws_cloudfront_distribution.dashboard.domain_name}"
    ]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# 3. CloudFront Distribution with Origin Access Control (OAC)
resource "aws_cloudfront_origin_access_control" "dashboard" {
  name                              = "${var.project_name}-${var.environment}-dashboard-oac"
  description                       = "OAC for dashboard static assets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "dashboard" {
  origin {
    domain_name              = aws_s3_bucket.dashboard_assets.bucket_regional_domain_name
    origin_id                = "S3-DashboardAssets"
    origin_access_control_id = aws_cloudfront_origin_access_control.dashboard.id
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-DashboardAssets"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}

# S3 Bucket Policies enforcing TLS and restricting asset bucket to CloudFront OAC
data "aws_iam_policy_document" "dashboard_assets_policy" {
  statement {
    sid    = "AllowCloudFrontOAC"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.dashboard_assets.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.dashboard.arn]
    }
  }

  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.dashboard_assets.arn,
      "${aws_s3_bucket.dashboard_assets.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id
  policy = data.aws_iam_policy_document.dashboard_assets_policy.json
}

data "aws_iam_policy_document" "dashboard_data_policy" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.dashboard_data.arn,
      "${aws_s3_bucket.dashboard_data.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "dashboard_data" {
  bucket = aws_s3_bucket.dashboard_data.id
  policy = data.aws_iam_policy_document.dashboard_data_policy.json
}

# 4. Cognito User Pool, Client, Domain, Identity Pool, and Auth IAM Role
resource "aws_cognito_user_pool" "dashboard" {
  name = "${var.project_name}-${var.environment}-user-pool"

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  mfa_configuration = "OFF"

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = var.tags
}

resource "aws_cognito_user_pool_client" "dashboard" {
  name         = "${var.project_name}-${var.environment}-user-pool-client"
  user_pool_id = aws_cognito_user_pool.dashboard.id

  allowed_oauth_flows                  = ["code", "implicit"]
  allowed_oauth_scopes                 = ["phone", "email", "openid", "profile", "aws.cognito.signin.user.admin"]
  callback_urls                        = ["https://${aws_cloudfront_distribution.dashboard.domain_name}"]
  logout_urls                          = ["https://${aws_cloudfront_distribution.dashboard.domain_name}"]
  supported_identity_providers         = ["COGNITO"]
  allowed_oauth_flows_user_pool_client = true

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]
}

resource "aws_cognito_user_pool_domain" "dashboard" {
  domain       = "${var.project_name}-${var.environment}-dash-${data.aws_caller_identity.current.account_id}"
  user_pool_id = aws_cognito_user_pool.dashboard.id
}

resource "aws_cognito_identity_pool" "dashboard" {
  identity_pool_name               = "${replace(var.project_name, "-", "_")}_${replace(var.environment, "-", "_")}_id_pool"
  allow_unauthenticated_identities = false

  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.dashboard.id
    provider_name           = aws_cognito_user_pool.dashboard.endpoint
    server_side_token_check = false
  }
}

data "aws_iam_policy_document" "authenticated_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = ["cognito-identity.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "cognito-identity.amazonaws.com:aud"
      values   = [aws_cognito_identity_pool.dashboard.id]
    }
    condition {
      test     = "ForAnyValue:StringLike"
      variable = "cognito-identity.amazonaws.com:amr"
      values   = ["authenticated"]
    }
  }
}

resource "aws_iam_role" "authenticated" {
  name               = "${var.project_name}-${var.environment}-dashboard-auth-role"
  assume_role_policy = data.aws_iam_policy_document.authenticated_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "authenticated_permissions" {
  statement {
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.dashboard_data.arn,
      "${aws_s3_bucket.dashboard_data.arn}/${var.dashboard_data_prefix}*"
    ]
  }
}

resource "aws_iam_role_policy" "authenticated" {
  name   = "${var.project_name}-${var.environment}-dashboard-auth-policy"
  role   = aws_iam_role.authenticated.id
  policy = data.aws_iam_policy_document.authenticated_permissions.json
}

resource "aws_cognito_identity_pool_roles_attachment" "dashboard" {
  identity_pool_id = aws_cognito_identity_pool.dashboard.id

  roles = {
    "authenticated" = aws_iam_role.authenticated.arn
  }
}

# 5. Emit a non-secret dashboard_runtime_config JSON object into the asset bucket
resource "aws_s3_object" "runtime_config" {
  bucket       = aws_s3_bucket.dashboard_assets.id
  key          = "dashboard_runtime_config.json"
  content_type = "application/json"
  content = jsonencode({
    aws_region          = data.aws_region.current.name
    user_pool_id        = aws_cognito_user_pool.dashboard.id
    user_pool_client_id = aws_cognito_user_pool_client.dashboard.id
    identity_pool_id    = aws_cognito_identity_pool.dashboard.id
    hosted_ui_domain    = "${aws_cognito_user_pool_domain.dashboard.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
    data_bucket_name    = aws_s3_bucket.dashboard_data.id
    data_prefix         = var.dashboard_data_prefix
    cloudfront_domain   = aws_cloudfront_distribution.dashboard.domain_name
  })
}

# 6. Optional QuickSight Data Source (disabled by default)
resource "aws_quicksight_data_source" "athena" {
  count          = var.enable_quicksight ? 1 : 0
  data_source_id = "${var.project_name}-${var.environment}-athena-ds"
  name           = "${var.project_name}-${var.environment}-athena-ds"
  type           = "ATHENA"
  aws_account_id = data.aws_caller_identity.current.account_id

  parameters {
    athena {
      work_group = var.athena_workgroup_name
    }
  }
}
