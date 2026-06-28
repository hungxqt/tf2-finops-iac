data "aws_caller_identity" "current" {}

locals {
  dynamodb_table_suffixes = ["run-state", "anomaly", "routing-state", "containment-audit", "dashboard-views", "account-policy", "rollback-cache"]
  dynamodb_table_arns = [
    for suffix in local.dynamodb_table_suffixes :
    "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.project_name}-${var.environment}-${suffix}"
  ]

  dynamodb_table_names = {
    run_state       = "${var.project_name}-${var.environment}-run-state"
    anomaly         = "${var.project_name}-${var.environment}-anomaly"
    routing_state   = "${var.project_name}-${var.environment}-routing-state"
    audit           = "${var.project_name}-${var.environment}-containment-audit"
    dashboard_views = "${var.project_name}-${var.environment}-dashboard-views"
    account_policy  = "${var.project_name}-${var.environment}-account-policy"
    rollback_cache  = "${var.project_name}-${var.environment}-rollback-cache"
  }
}


data "aws_iam_policy_document" "replica_kms_policy" {
  statement {
    # checkov:skip=CKV_AWS_109: "KMS key policy must specify resource = * because it is attached directly to the key"
    # checkov:skip=CKV_AWS_111: "KMS key policy must specify resource = * because it is attached directly to the key"
    # checkov:skip=CKV_AWS_356: "KMS key policy must specify resource = * because it is attached directly to the key"
    sid    = "EnableRootAccountAdministration"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "S3 service usage on a directly attached KMS key policy requires resource = *"
    # checkov:skip=CKV_AWS_356: "S3 service usage on a directly attached KMS key policy requires resource = *"
    sid    = "AllowS3ReplicaBucketUsage"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey*"
    ]
    resources = ["*"]
  }
}

# ================= Replica S3 Buckets in Replica Region (ap-southeast-2) =================

# 1. Lakehouse Replica S3 Bucket
resource "aws_s3_bucket" "lakehouse_replica" {
  provider      = aws.replica
  bucket        = "${var.project_name}-${var.environment}-lakehouse-replica"
  force_destroy = var.destroyable
  # checkov:skip=CKV_AWS_18: "Replica bucket does not need access logging itself"
  # checkov:skip=CKV_AWS_144: "Replica bucket does not need replication"
  # checkov:skip=CKV_AWS_21: "Versioning is enabled"
  # checkov:skip=CKV_AWS_145: "Replica bucket is encrypted with SSE-S3 (AES256) to simplify cross-region KMS key management"
  # checkov:skip=CKV2_AWS_61: "Replica bucket does not need lifecycle configuration"
  # checkov:skip=CKV2_AWS_62: "Replica bucket does not need event notifications"
}

resource "aws_s3_bucket_versioning" "lakehouse_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.lakehouse_replica.id
  versioning_configuration {
    status = "Enabled"
  }
}

# trivy:ignore:AVD-AWS-0132
# trivy:ignore:AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "lakehouse_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.lakehouse_replica.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lakehouse_replica" {
  provider                = aws.replica
  bucket                  = aws_s3_bucket.lakehouse_replica.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "lakehouse_replica_tls_only" {
  provider   = aws.replica
  bucket     = aws_s3_bucket.lakehouse_replica.id
  policy     = data.aws_iam_policy_document.replica_tls_only_lakehouse.json
  depends_on = [aws_s3_bucket_public_access_block.lakehouse_replica]
}

data "aws_iam_policy_document" "replica_tls_only_lakehouse" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.lakehouse_replica.arn,
      "${aws_s3_bucket.lakehouse_replica.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# 2. Audit Replica S3 Bucket
resource "aws_s3_bucket" "audit_replica" {
  provider      = aws.replica
  bucket        = "${var.project_name}-${var.environment}-audit-replica"
  force_destroy = var.destroyable
  # checkov:skip=CKV_AWS_18: "Replica bucket does not need access logging itself"
  # checkov:skip=CKV_AWS_144: "Replica bucket does not need replication"
  # checkov:skip=CKV_AWS_21: "Versioning is enabled"
  # checkov:skip=CKV_AWS_145: "Replica bucket is encrypted with SSE-S3 (AES256) to simplify cross-region KMS key management"
  # checkov:skip=CKV2_AWS_61: "Replica bucket does not need lifecycle configuration"
  # checkov:skip=CKV2_AWS_62: "Replica bucket does not need event notifications"
}

resource "aws_s3_bucket_versioning" "audit_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.audit_replica.id
  versioning_configuration {
    status = "Enabled"
  }
}

# trivy:ignore:AVD-AWS-0132
# trivy:ignore:AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "audit_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.audit_replica.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit_replica" {
  provider                = aws.replica
  bucket                  = aws_s3_bucket.audit_replica.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "audit_replica_tls_only" {
  provider   = aws.replica
  bucket     = aws_s3_bucket.audit_replica.id
  policy     = data.aws_iam_policy_document.replica_tls_only_audit.json
  depends_on = [aws_s3_bucket_public_access_block.audit_replica]
}

data "aws_iam_policy_document" "replica_tls_only_audit" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.audit_replica.arn,
      "${aws_s3_bucket.audit_replica.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# 3. Athena Results Replica S3 Bucket
resource "aws_s3_bucket" "athena_results_replica" {
  provider      = aws.replica
  bucket        = "${var.project_name}-${var.environment}-athena-results-replica"
  force_destroy = var.destroyable
  # checkov:skip=CKV_AWS_18: "Replica bucket does not need access logging itself"
  # checkov:skip=CKV_AWS_144: "Replica bucket does not need replication"
  # checkov:skip=CKV_AWS_21: "Versioning is enabled"
  # checkov:skip=CKV_AWS_145: "Replica bucket is encrypted with SSE-S3 (AES256) to simplify cross-region KMS key management"
  # checkov:skip=CKV2_AWS_61: "Replica bucket does not need lifecycle configuration"
  # checkov:skip=CKV2_AWS_62: "Replica bucket does not need event notifications"
}

resource "aws_s3_bucket_versioning" "athena_results_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.athena_results_replica.id
  versioning_configuration {
    status = "Enabled"
  }
}

# trivy:ignore:AVD-AWS-0132
# trivy:ignore:AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.athena_results_replica.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "athena_results_replica" {
  provider                = aws.replica
  bucket                  = aws_s3_bucket.athena_results_replica.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "athena_results_replica_tls_only" {
  provider   = aws.replica
  bucket     = aws_s3_bucket.athena_results_replica.id
  policy     = data.aws_iam_policy_document.replica_tls_only_athena.json
  depends_on = [aws_s3_bucket_public_access_block.athena_results_replica]
}

data "aws_iam_policy_document" "replica_tls_only_athena" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.athena_results_replica.arn,
      "${aws_s3_bucket.athena_results_replica.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# KMS Key in the replica region (ap-southeast-2)
resource "aws_kms_key" "replica" {
  provider                = aws.replica
  description             = "KMS key for replica region S3 buckets"
  deletion_window_in_days = var.destroyable ? 7 : 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.replica_kms_policy.json
  tags                    = var.tags
}

resource "aws_kms_alias" "replica" {
  provider      = aws.replica
  name          = "alias/${var.project_name}-${var.environment}-replica-key"
  target_key_id = aws_kms_key.replica.key_id
}

# 4. Dashboard Assets Replica S3 Bucket
resource "aws_s3_bucket" "dashboard_assets_replica" {
  provider      = aws.replica
  bucket        = "${var.project_name}-${var.environment}-dashboard-assets-replica"
  force_destroy = var.destroyable
  # checkov:skip=CKV_AWS_18: "Replica bucket does not need access logging itself"
  # checkov:skip=CKV_AWS_144: "Replica bucket does not need replication"
  # checkov:skip=CKV_AWS_21: "Versioning is enabled"
  # checkov:skip=CKV_AWS_145: "Replica bucket is encrypted with SSE-S3 (AES256) to simplify cross-region KMS key management"
  # checkov:skip=CKV2_AWS_61: "Replica bucket does not need lifecycle configuration"
  # checkov:skip=CKV2_AWS_62: "Replica bucket does not need event notifications"
}

resource "aws_s3_bucket_versioning" "dashboard_assets_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.dashboard_assets_replica.id
  versioning_configuration {
    status = "Enabled"
  }
}

# trivy:ignore:AVD-AWS-0132
# trivy:ignore:AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "dashboard_assets_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.dashboard_assets_replica.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.replica.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "dashboard_assets_replica" {
  provider                = aws.replica
  bucket                  = aws_s3_bucket.dashboard_assets_replica.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "dashboard_assets_replica_tls_only" {
  provider   = aws.replica
  bucket     = aws_s3_bucket.dashboard_assets_replica.id
  policy     = data.aws_iam_policy_document.replica_tls_only_assets.json
  depends_on = [aws_s3_bucket_public_access_block.dashboard_assets_replica]
}

data "aws_iam_policy_document" "replica_tls_only_assets" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.dashboard_assets_replica.arn,
      "${aws_s3_bucket.dashboard_assets_replica.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# 5. Dashboard Data Replica S3 Bucket
resource "aws_s3_bucket" "dashboard_data_replica" {
  provider      = aws.replica
  bucket        = "${var.project_name}-${var.environment}-dashboard-data-replica"
  force_destroy = var.destroyable
  # checkov:skip=CKV_AWS_18: "Replica bucket does not need access logging itself"
  # checkov:skip=CKV_AWS_144: "Replica bucket does not need replication"
  # checkov:skip=CKV_AWS_21: "Versioning is enabled"
  # checkov:skip=CKV_AWS_145: "Replica bucket is encrypted with SSE-S3 (AES256) to simplify cross-region KMS key management"
  # checkov:skip=CKV2_AWS_61: "Replica bucket does not need lifecycle configuration"
  # checkov:skip=CKV2_AWS_62: "Replica bucket does not need event notifications"
}

resource "aws_s3_bucket_versioning" "dashboard_data_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.dashboard_data_replica.id
  versioning_configuration {
    status = "Enabled"
  }
}

# trivy:ignore:AVD-AWS-0132
# trivy:ignore:AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "dashboard_data_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.dashboard_data_replica.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.replica.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "dashboard_data_replica" {
  provider                = aws.replica
  bucket                  = aws_s3_bucket.dashboard_data_replica.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "dashboard_data_replica_tls_only" {
  provider   = aws.replica
  bucket     = aws_s3_bucket.dashboard_data_replica.id
  policy     = data.aws_iam_policy_document.replica_tls_only_data.json
  depends_on = [aws_s3_bucket_public_access_block.dashboard_data_replica]
}

data "aws_iam_policy_document" "replica_tls_only_data" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.dashboard_data_replica.arn,
      "${aws_s3_bucket.dashboard_data_replica.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}


# ================= Core Modules Wiring =================

# 1. Networking Module
module "networking" {
  source = "../../modules/networking"

  project_name               = var.project_name
  environment                = var.environment
  aws_region                 = var.aws_region
  vpc_cidr_block             = "10.20.0.0/16"
  public_subnet_cidr_blocks  = ["10.20.1.0/24", "10.20.2.0/24"]
  private_subnet_cidr_blocks = ["10.20.10.0/24", "10.20.11.0/24"]
  availability_zones         = ["${var.aws_region}a", "${var.aws_region}b"]
  single_nat_gateway         = false
  cloudwatch_log_kms_key_arn = module.lakehouse.data_kms_key_arn
  tags                       = var.tags
}

# 2. Lakehouse Module
module "lakehouse" {
  source = "../../modules/lakehouse"

  project_name                 = var.project_name
  environment                  = var.environment
  aws_region                   = var.aws_region
  audit_retention_days         = 90
  lakehouse_replica_bucket_arn = aws_s3_bucket.lakehouse_replica.arn
  audit_replica_bucket_arn     = aws_s3_bucket.audit_replica.arn
  athena_replica_bucket_arn    = aws_s3_bucket.athena_results_replica.arn
  tags                         = var.tags
  destroyable                  = var.destroyable
}

# 3. Alerting Module
module "alerting" {
  source = "../../modules/alerting"

  project_name    = var.project_name
  environment     = var.environment
  sns_kms_key_arn = module.lakehouse.data_kms_key_arn
  tags            = var.tags
}

# 4. IAM Module
module "iam" {
  source = "../../modules/iam"

  project_name         = var.project_name
  environment          = var.environment
  lakehouse_bucket_arn = module.lakehouse.lakehouse_bucket_arn
  audit_bucket_arn     = module.lakehouse.audit_bucket_arn
  dynamodb_table_arns = concat(
    local.dynamodb_table_arns,
    [
      module.orchestration.dynamodb_table_arns["error_budget"],
      module.orchestration.dynamodb_table_arns["ai_payload_idempotency"],
    ]
  )
  ai_payload_idempotency_table_arn       = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/finops-idempotency-${var.environment}"
  kms_key_arns                           = [module.lakehouse.data_kms_key_arn, module.lakehouse.audit_kms_key_arn, module.lakehouse.ddb_kms_key_arn]
  containment_apply_enabled              = false
  queue_arns                             = [module.orchestration.rollback_status_queue_arn, module.compute_lambda.lambda_dlq_arn]
  sns_topic_arns                         = [module.alerting.finance_topic_arn, module.alerting.engineering_topic_arn]
  telemetry_member_account_ids           = var.telemetry_member_account_ids
  telemetry_member_role_name             = var.telemetry_member_role_name
  cur_source_bucket_arn                  = var.cur_source_bucket_arn
  create_member_telemetry_ingestion_role = var.create_member_telemetry_ingestion_role
  trusted_cost_puller_role_arns          = var.trusted_cost_puller_role_arns
  athena_results_bucket_arn              = module.lakehouse.athena_results_bucket_arn
  athena_workgroup_arn                   = module.lakehouse.athena_workgroup_arn
  glue_database_arn                      = module.lakehouse.glue_database_arn
  cur_data_table_arn                     = module.lakehouse.cur_data_table_arn
  tags                                   = var.tags
}

# 5. Lambda-based AI Engine Runtime
module "ai_runtime_lambda" {
  source = "../../modules/ai-runtime-lambda"

  project_name             = var.project_name
  environment              = var.environment
  aws_region               = var.aws_region
  private_subnet_ids       = module.networking.private_subnet_ids
  lambda_security_group_id = module.compute_lambda.lambda_security_group_id
  request_image_uri        = var.request_image_uri


  vpc_id                 = module.networking.vpc_id
  vpc_cidr_block         = module.networking.vpc_cidr_block
  alb_certificate_arn    = var.alb_certificate_arn
  private_hosted_zone_id = var.private_hosted_zone_id
  private_dns_name       = var.private_dns_name
  alb_access_logs_bucket = module.lakehouse.logging_bucket_name

  secret_arns  = []
  kms_key_arns = [module.lakehouse.data_kms_key_arn]
  tags         = var.tags
  destroyable  = var.destroyable

  ai_request_s3_pointer_bucket_arn = module.lakehouse.lakehouse_bucket_arn
  ai_request_s3_pointer_prefixes   = ["ai-input/*"]
}


# 6. Compute Lambda Module
module "compute_lambda" {
  source = "../../modules/compute-lambda"

  project_name                   = var.project_name
  environment                    = var.environment
  private_subnet_ids             = module.networking.private_subnet_ids
  vpc_id                         = module.networking.vpc_id
  vpc_endpoint_security_group_id = module.networking.vpc_endpoint_security_group_id
  lambda_role_arns               = module.iam.lambda_role_arns
  lakehouse_bucket_name          = module.lakehouse.lakehouse_bucket_name
  audit_bucket_name              = module.lakehouse.audit_bucket_name
  dynamodb_table_names = merge(
    local.dynamodb_table_names,
    {
      error_budget           = module.orchestration.dynamodb_table_names["error_budget"]
      ai_payload_idempotency = module.orchestration.idempotency_table_name
    }
  )
  containment_apply_enabled  = false
  cloudwatch_log_kms_key_arn = module.lakehouse.data_kms_key_arn
  lambda_env_kms_key_arn     = module.lakehouse.data_kms_key_arn
  sqs_kms_key_arn            = module.lakehouse.data_kms_key_arn
  alb_base_url               = var.private_hosted_zone_id != "" && var.private_dns_name != "" ? "https://${var.private_dns_name}" : "https://${module.ai_runtime_lambda.alb_dns_name}"
  sigv4_service_name         = var.sigv4_service_name
  tags                       = var.tags

  cur_source_bucket          = var.cur_source_bucket
  cur_source_prefix          = var.cur_source_prefix
  cur_delay_threshold_hours  = var.cur_delay_threshold_hours
  ce_lookback_window_days    = var.ce_lookback_window_days
  traffic_metric_identifiers = var.traffic_metric_identifiers
  telemetry_member_role_name = var.telemetry_member_role_name
}

# 7. Orchestration Module
module "orchestration" {
  source = "../../modules/orchestration"

  project_name                 = var.project_name
  environment                  = var.environment
  scheduler_expression         = "rate(24 hours)"
  lambda_function_arns         = module.compute_lambda.lambda_alias_arns
  ddb_kms_key_arn              = module.lakehouse.ddb_kms_key_arn
  sqs_kms_key_arn              = module.lakehouse.data_kms_key_arn
  audit_bucket_name            = module.lakehouse.audit_bucket_name
  finance_alerts_topic_arn     = module.alerting.finance_topic_arn
  engineering_alerts_topic_arn = module.alerting.engineering_topic_arn
  cloudwatch_log_kms_key_arn   = module.lakehouse.data_kms_key_arn
  scheduler_kms_key_arn        = module.lakehouse.data_kms_key_arn
  tags                         = var.tags
  destroyable                  = var.destroyable
}

# 8. Observability Module
module "observability" {
  source = "../../modules/observability"

  project_name      = var.project_name
  environment       = var.environment
  state_machine_arn = module.orchestration.state_machine_arn
  lambda_function_names = concat(
    values(module.compute_lambda.lambda_function_names),
    [
      module.ai_runtime_lambda.request_lambda_function_name
    ]
  )
  engineering_topic_arn = module.alerting.engineering_topic_arn
  finance_topic_arn     = module.alerting.finance_topic_arn
  log_retention_days    = 30
  tags                  = var.tags
}

# 10. Dashboard Module
module "dashboard" {
  source = "../../modules/dashboard"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  project_name                        = var.project_name
  environment                         = var.environment
  glue_database_name                  = module.lakehouse.glue_database_name
  athena_workgroup_name               = module.lakehouse.athena_workgroup_name
  enable_quicksight                   = false
  dashboard_kms_key_arn               = module.lakehouse.data_kms_key_arn
  dashboard_replica_kms_key_arn       = aws_kms_key.replica.arn
  dashboard_api_vpc_origin_alb_arn    = module.ai_runtime_lambda.alb_arn
  dashboard_api_origin_domain_name    = module.ai_runtime_lambda.alb_dns_name
  dashboard_data_prefix               = "summaries/"
  s3_logging_bucket_id                = module.lakehouse.logging_bucket_name
  dashboard_assets_replica_bucket_arn = aws_s3_bucket.dashboard_assets_replica.arn
  dashboard_data_replica_bucket_arn   = aws_s3_bucket.dashboard_data_replica.arn
  cloudfront_acm_certificate_arn      = var.cloudfront_acm_certificate_arn
  cloudfront_aliases                  = var.cloudfront_aliases
  dashboard_geo_restriction_type      = var.dashboard_geo_restriction_type
  dashboard_geo_restriction_locations = var.dashboard_geo_restriction_locations
  tags                                = var.tags
  destroyable                         = var.destroyable
}
