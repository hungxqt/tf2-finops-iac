data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_canonical_user_id" "current" {}
data "aws_cloudfront_log_delivery_canonical_user_id" "this" {}

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

# Locals to parse bucket names from ARNs
locals {
  replica_assets_bucket_name = replace(var.dashboard_assets_replica_bucket_arn, "arn:aws:s3:::", "")
  replica_data_bucket_name   = replace(var.dashboard_data_replica_bucket_arn, "arn:aws:s3:::", "")
}

# 1. Private S3 bucket for static dashboard assets (replaceable)
resource "aws_s3_bucket" "dashboard_assets" {
  bucket        = "${var.project_name}-${var.environment}-dashboard-assets"
  force_destroy = var.destroyable
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

resource "aws_s3_bucket_logging" "dashboard_assets" {
  bucket        = aws_s3_bucket.dashboard_assets.id
  target_bucket = var.s3_logging_bucket_id
  target_prefix = "dashboard-assets/"
}

resource "aws_s3_bucket_lifecycle_configuration" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id
  rule {
    id     = "abort-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_notification" "dashboard_assets" {
  bucket      = aws_s3_bucket.dashboard_assets.id
  eventbridge = true
}

resource "aws_s3_bucket_replication_configuration" "dashboard_assets" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.dashboard_assets.id

  rule {
    id     = "replicate-assets"
    status = "Enabled"

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }

    destination {
      bucket        = var.dashboard_assets_replica_bucket_arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = var.dashboard_replica_kms_key_arn
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.dashboard_assets]
}

# 2. Private S3 bucket for precomputed dashboard JSON summaries
resource "aws_s3_bucket" "dashboard_data" {
  bucket        = "${var.project_name}-${var.environment}-dashboard-data"
  force_destroy = var.destroyable
  tags          = var.tags
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

resource "aws_s3_bucket_logging" "dashboard_data" {
  bucket        = aws_s3_bucket.dashboard_data.id
  target_bucket = var.s3_logging_bucket_id
  target_prefix = "dashboard-data/"
}

resource "aws_s3_bucket_lifecycle_configuration" "dashboard_data" {
  bucket = aws_s3_bucket.dashboard_data.id
  rule {
    id     = "abort-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_notification" "dashboard_data" {
  bucket      = aws_s3_bucket.dashboard_data.id
  eventbridge = true
}

resource "aws_s3_bucket_replication_configuration" "dashboard_data" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.dashboard_data.id

  rule {
    id     = "replicate-data"
    status = "Enabled"

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }

    destination {
      bucket        = var.dashboard_data_replica_bucket_arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = var.dashboard_replica_kms_key_arn
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.dashboard_data]
}

# S3 Bucket CORS Configuration for the dashboard data bucket
resource "aws_s3_bucket_cors_configuration" "dashboard_data" {
  bucket = aws_s3_bucket.dashboard_data.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = concat(
      [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://${aws_cloudfront_distribution.dashboard.domain_name}"
      ],
      [for alias in var.cloudfront_aliases : "https://${alias}"]
    )
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Dedicated CloudFront logs S3 bucket
resource "aws_s3_bucket" "cloudfront_logs" {
  # checkov:skip=CKV_AWS_18: "CloudFront logs bucket should not have access logging enabled to avoid infinite logging loops"
  # checkov:skip=CKV_AWS_144: "Cross-region replication is not required for standard CloudFront logs"
  # checkov:skip=CKV_AWS_145: "KMS encryption is not supported for standard CloudFront log delivery (requires SSE-S3)"
  # checkov:skip=CKV2_AWS_62: "Event notifications are not required for standard CloudFront logs"
  bucket        = "${var.project_name}-${var.environment}-cloudfront-logs"
  force_destroy = var.destroyable
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "cloudfront_logs" {
  bucket                  = aws_s3_bucket.cloudfront_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

# trivy:ignore:AVD-AWS-0132
# trivy:ignore:AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id
  rule {
    id     = "abort-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  rule {
    id     = "expire-logs"
    status = "Enabled"
    filter {}
    expiration {
      days = 90
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "cloudfront_logs" {
  # checkov:skip=CKV2_AWS_65: "ACLs are required for CloudFront log delivery"
  bucket = aws_s3_bucket.cloudfront_logs.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  depends_on = [aws_s3_bucket_ownership_controls.cloudfront_logs]

  access_control_policy {
    grant {
      grantee {
        id   = data.aws_canonical_user_id.current.id
        type = "CanonicalUser"
      }
      permission = "FULL_CONTROL"
    }

    grant {
      grantee {
        id   = data.aws_cloudfront_log_delivery_canonical_user_id.this.id
        type = "CanonicalUser"
      }
      permission = "FULL_CONTROL"
    }

    owner {
      id = data.aws_canonical_user_id.current.id
    }
  }
}

data "aws_iam_policy_document" "cloudfront_logs_policy" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.cloudfront_logs.arn,
      "${aws_s3_bucket.cloudfront_logs.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id
  policy = data.aws_iam_policy_document.cloudfront_logs_policy.json
}

# 3. CloudFront Distribution with Origin Access Control (OAC) and WAFv2
resource "aws_cloudfront_origin_access_control" "dashboard" {
  name                              = "${var.project_name}-${var.environment}-dashboard-oac"
  description                       = "OAC for dashboard static assets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Response Headers Policy to enforce security headers
resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name    = "${var.project_name}-${var.environment}-security-headers"
  comment = "Enforces strict security headers"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "same-origin"
      override        = true
    }
    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }
}

# us-east-1 region WAFv2 Web ACL for CloudFront
resource "aws_wafv2_web_acl" "cloudfront" {
  # checkov:skip=CKV2_AWS_31: "WAFv2 logging is disabled to avoid complex us-east-1 Kinesis/S3 configuration in this dashboard setup"
  provider    = aws.us_east_1
  name        = "${var.project_name}-${var.environment}-waf-web-acl"
  description = "WAFv2 Web ACL for CloudFront distribution"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesKnownBadInputsMetric"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${replace(var.project_name, "-", "_")}_${var.environment}_waf_metrics"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}



resource "aws_cloudfront_distribution" "dashboard" {
  # checkov:skip=CKV_AWS_310: "Origin failover is enabled via origin_group"
  # checkov:skip=CKV2_AWS_42: "Custom SSL certificate is conditionally configured via cloudfront_acm_certificate_arn variable"
  # checkov:skip=CKV2_AWS_47: "WAFv2 is configured with KnownBadInputsRuleSet protecting against Log4j, but scanner does not resolve it dynamically"
  origin {
    domain_name              = aws_s3_bucket.dashboard_assets.bucket_regional_domain_name
    origin_id                = "S3-DashboardAssets"
    origin_access_control_id = aws_cloudfront_origin_access_control.dashboard.id
  }

  origin {
    domain_name              = "${local.replica_assets_bucket_name}.s3.ap-southeast-2.amazonaws.com"
    origin_id                = "S3-DashboardAssetsReplica"
    origin_access_control_id = aws_cloudfront_origin_access_control.dashboard.id
  }

  origin_group {
    origin_id = "OriginGroup-DashboardAssets"

    failover_criteria {
      status_codes = [500, 502, 503, 504, 403, 404]
    }

    member {
      origin_id = "S3-DashboardAssets"
    }

    member {
      origin_id = "S3-DashboardAssetsReplica"
    }
  }

  origin {
    domain_name              = aws_s3_bucket.dashboard_data.bucket_regional_domain_name
    origin_id                = "S3-DashboardData"
    origin_access_control_id = aws_cloudfront_origin_access_control.dashboard.id
  }

  origin {
    domain_name              = "${local.replica_data_bucket_name}.s3.ap-southeast-2.amazonaws.com"
    origin_id                = "S3-DashboardDataReplica"
    origin_access_control_id = aws_cloudfront_origin_access_control.dashboard.id
  }

  origin_group {
    origin_id = "OriginGroup-DashboardData"

    failover_criteria {
      status_codes = [500, 502, 503, 504, 403, 404]
    }

    member {
      origin_id = "S3-DashboardData"
    }

    member {
      origin_id = "S3-DashboardDataReplica"
    }
  }



  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  web_acl_id          = aws_wafv2_web_acl.cloudfront.arn
  aliases             = var.cloudfront_acm_certificate_arn != "" ? var.cloudfront_aliases : []

  logging_config {
    bucket          = aws_s3_bucket.cloudfront_logs.bucket_domain_name
    include_cookies = false
    prefix          = "cloudfront/"
  }

  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = "OriginGroup-DashboardAssets"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id

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

    lambda_function_association {
      event_type   = "viewer-request"
      lambda_arn   = aws_lambda_function.edge_viewer_auth.qualified_arn
      include_body = false
    }
  }

  ordered_cache_behavior {
    path_pattern               = "/${var.dashboard_data_prefix}*"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = "OriginGroup-DashboardData"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id

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

    lambda_function_association {
      event_type   = "viewer-request"
      lambda_arn   = aws_lambda_function.edge_viewer_auth.qualified_arn
      include_body = false
    }
  }



  restrictions {
    geo_restriction {
      restriction_type = var.dashboard_geo_restriction_type
      locations        = var.dashboard_geo_restriction_type != "none" ? var.dashboard_geo_restriction_locations : null
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.cloudfront_acm_certificate_arn != "" ? var.cloudfront_acm_certificate_arn : null
    cloudfront_default_certificate = var.cloudfront_acm_certificate_arn == "" ? true : null
    ssl_support_method             = var.cloudfront_acm_certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version       = var.cloudfront_acm_certificate_arn != "" ? "TLSv1.2_2021" : null
  }

  tags = var.tags

  depends_on = [aws_s3_bucket_acl.cloudfront_logs]
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
    sid    = "AllowCloudFrontOAC"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.dashboard_data.arn}/*"]
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

  allowed_oauth_flows  = ["code"]
  allowed_oauth_scopes = ["phone", "email", "openid", "profile"]
  callback_urls = concat(
    ["https://${aws_cloudfront_distribution.dashboard.domain_name}/oauth2/callback"],
    [for alias in var.cloudfront_aliases : "https://${alias}/oauth2/callback"]
  )
  logout_urls = concat(
    ["https://${aws_cloudfront_distribution.dashboard.domain_name}/logout"],
    [for alias in var.cloudfront_aliases : "https://${alias}/logout"]
  )
  supported_identity_providers         = ["COGNITO"]
  allowed_oauth_flows_user_pool_client = true

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]
}

resource "aws_ssm_parameter" "cognito_client_id" {
  name        = "/${var.project_name}/${var.environment}/dashboard/cognito_client_id"
  type        = "SecureString"
  value       = aws_cognito_user_pool_client.dashboard.id
  description = "Cognito User Pool Client ID for Dashboard"
  key_id      = var.dashboard_kms_key_arn
  tags        = var.tags
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
    server_side_token_check = true
  }
}

resource "aws_cognito_user_group" "finance" {
  name         = var.group_name_finance
  user_pool_id = aws_cognito_user_pool.dashboard.id
  description  = "Finance read-only access"
}

resource "aws_cognito_user_group" "engineering" {
  name         = var.group_name_engineering
  user_pool_id = aws_cognito_user_pool.dashboard.id
  description  = "Engineering operator access"
}

resource "aws_cognito_user_group" "cdo" {
  name         = var.group_name_cdo
  user_pool_id = aws_cognito_user_pool.dashboard.id
  description  = "CDO admin access"
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

# IAM Role for S3 Replication in Dashboard Module
resource "aws_iam_role" "replication" {
  name = "${var.project_name}-${var.environment}-db-repl-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "replication" {
  name = "dashboard-replication-policy"
  role = aws_iam_role.replication.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.dashboard_assets.arn,
          aws_s3_bucket.dashboard_data.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Resource = [
          "${aws_s3_bucket.dashboard_assets.arn}/*",
          "${aws_s3_bucket.dashboard_data.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Resource = [
          "${var.dashboard_assets_replica_bucket_arn}/*",
          "${var.dashboard_data_replica_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          var.dashboard_kms_key_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          var.dashboard_replica_kms_key_arn
        ]
      }
    ]
  })
}

# Lambda@Edge IAM Role and Policies
resource "aws_iam_role" "edge_auth" {
  name = "${var.project_name}-${var.environment}-edge-auth-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = [
          "lambda.amazonaws.com",
          "edgelambda.amazonaws.com"
        ]
      }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "edge_auth" {
  name = "${var.project_name}-${var.environment}-edge-auth-policy"
  role = aws_iam_role.edge_auth.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/dashboard/cognito_client_id"
        ]
      }
    ]
  })
}

# Dynamic package for Lambda@Edge dashboard auth
data "archive_file" "dashboard_auth" {
  type        = "zip"
  output_path = "${path.module}/../../.build/lambda/dashboard_auth_deploy.zip"

  source {
    content  = file("${path.module}/../../lambda_src/edge/dashboard_auth/viewer_auth.py")
    filename = "viewer_auth.py"
  }



  source {
    content  = <<EOF
COGNITO_DOMAIN          = "${aws_cognito_user_pool_domain.dashboard.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
COGNITO_CLIENT_ID_PARAM = "/${var.project_name}/${var.environment}/dashboard/cognito_client_id"
USER_POOL_ID            = "${aws_cognito_user_pool.dashboard.id}"
REGION                  = "${data.aws_region.current.name}"
TARGET_REGION           = "${data.aws_region.current.name}"
TARGET_SERVICE          = "lambda"
EOF
    filename = "config.py"
  }
}

resource "aws_lambda_function" "edge_viewer_auth" {
  # checkov:skip=CKV_AWS_50: "Lambda@Edge does not support X-Ray active tracing"
  # checkov:skip=CKV_AWS_115: "Lambda@Edge does not support reserved concurrency"
  # checkov:skip=CKV_AWS_116: "Lambda@Edge does not support DLQs"
  # checkov:skip=CKV_AWS_117: "Lambda@Edge must not be deployed inside a VPC"
  # checkov:skip=CKV_AWS_272: "Code signing is not configured for edge authentication handlers"
  provider         = aws.us_east_1
  function_name    = "${var.project_name}-${var.environment}-edge-viewer-auth"
  description      = "Lambda@Edge for dashboard authentication using Cognito"
  role             = aws_iam_role.edge_auth.arn
  handler          = "viewer_auth.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.dashboard_auth.output_path
  source_code_hash = data.archive_file.dashboard_auth.output_base64sha256
  publish          = true

  tags = var.tags
}



resource "terraform_data" "destroy_guard" {
  count = var.destroyable ? 0 : 1
  lifecycle {
    prevent_destroy = true
  }
}

