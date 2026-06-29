# Lakehouse Module Resources
# This module creates durable cost, audit, and query storage.

data "aws_caller_identity" "current" {}

# Common KMS Key Policy Document
data "aws_iam_policy_document" "kms_policy" {
  statement {
    # checkov:skip=CKV_AWS_109: "KMS key policy must specify resource = * as it is attached directly to the key"
    # checkov:skip=CKV_AWS_111: "KMS key policy must specify resource = * as it is attached directly to the key"
    # checkov:skip=CKV_AWS_356: "KMS key policy must specify resource = * as it is attached directly to the key"
    sid    = "Enable Root Account Administration"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    # checkov:skip=CKV_AWS_111: "KMS key policy must specify resource = * as it is attached directly to the key"
    # checkov:skip=CKV_AWS_356: "KMS key policy must specify resource = * as it is attached directly to the key"
    sid    = "AllowServiceUsage"
    effect = "Allow"
    principals {
      type = "Service"
      identifiers = [
        "s3.amazonaws.com",
        "sns.amazonaws.com",
        "dynamodb.amazonaws.com",
        "logs.amazonaws.com",
        "cloudwatch.amazonaws.com",
        "scheduler.amazonaws.com",
        "states.amazonaws.com"
      ]
    }
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
      "kms:Encrypt"
    ]
    resources = ["*"]
  }
}

# KMS Key for general data (Lakehouse, Athena Results)
resource "aws_kms_key" "data" {
  description             = "KMS key for data encryption (Lakehouse, Athena)"
  deletion_window_in_days = var.destroyable ? 7 : 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_policy.json
  tags = merge(var.tags, {
    Region = var.aws_region
  })
}

resource "aws_kms_alias" "data" {
  name          = "alias/${var.project_name}-${var.environment}-data-key"
  target_key_id = aws_kms_key.data.key_id
}

# KMS Key for Audit Log Encryption
resource "aws_kms_key" "audit" {
  description             = "KMS key for Audit log encryption"
  deletion_window_in_days = var.destroyable ? 7 : 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_policy.json
  tags                    = var.tags
}

resource "aws_kms_alias" "audit" {
  name          = "alias/${var.project_name}-${var.environment}-audit-key"
  target_key_id = aws_kms_key.audit.key_id
}

# KMS Key for DynamoDB Table Encryption
resource "aws_kms_key" "ddb" {
  description             = "KMS key for DynamoDB state encryption"
  deletion_window_in_days = var.destroyable ? 7 : 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_policy.json
  tags                    = var.tags
}

resource "aws_kms_alias" "ddb" {
  name          = "alias/${var.project_name}-${var.environment}-ddb-key"
  target_key_id = aws_kms_key.ddb.key_id
}

# Dedicated S3 Access Logging Bucket
resource "aws_s3_bucket" "logging" {
  # checkov:skip=CKV_AWS_18: "Logging bucket does not need access logging itself"
  # checkov:skip=CKV_AWS_144: "Logging bucket does not need replication"
  # checkov:skip=CKV_AWS_21: "Logging bucket does not need versioning"
  # checkov:skip=CKV_AWS_145: "S3 server access logging target bucket uses SSE-S3 because default SSE-KMS is not supported for S3 server access log delivery"
  # checkov:skip=CKV2_AWS_61: "Logging bucket does not need lifecycle configuration"
  # checkov:skip=CKV2_AWS_62: "Logging bucket does not need event notifications"
  bucket        = "${var.project_name}-${var.environment}-s3-logging"
  force_destroy = var.destroyable
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "logging" {
  bucket                  = aws_s3_bucket.logging.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "logging" {
  bucket = aws_s3_bucket.logging.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}



# trivy:ignore:AVD-AWS-0132
# trivy:ignore:AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "logging" {
  bucket = aws_s3_bucket.logging.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "logging_tls_only" {
  bucket     = aws_s3_bucket.logging.id
  policy     = data.aws_iam_policy_document.s3_tls_only_logging.json
  depends_on = [aws_s3_bucket_public_access_block.logging]
}

data "aws_elb_service_account" "main" {}

data "aws_iam_policy_document" "s3_tls_only_logging" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.logging.arn,
      "${aws_s3_bucket.logging.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "AllowALBAccessLogs"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = [data.aws_elb_service_account.main.arn]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.logging.arn}/*"]
  }

  statement {
    sid    = "AllowLogDeliveryWrite"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.logging.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }

  statement {
    sid    = "AllowLogDeliveryAcl"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.logging.arn]
  }
}


# S3 Lakehouse Bucket
resource "aws_s3_bucket" "lakehouse" {
  bucket        = "${var.project_name}-${var.environment}-lakehouse-bucket"
  force_destroy = var.destroyable
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "lakehouse" {
  bucket                  = aws_s3_bucket.lakehouse.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_logging" "lakehouse" {
  bucket        = aws_s3_bucket.lakehouse.id
  target_bucket = aws_s3_bucket.logging.id
  target_prefix = "lakehouse/"
}

resource "aws_s3_bucket_lifecycle_configuration" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id

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

  rule {
    id     = "transition-raw"
    status = "Enabled"
    filter {
      prefix = "raw/"
    }
    transition {
      days          = 30
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "transition-curated"
    status = "Enabled"
    filter {
      prefix = "curated/"
    }
    transition {
      days          = 30
      storage_class = "GLACIER"
    }
  }
}

resource "aws_s3_bucket_notification" "lakehouse" {
  bucket      = aws_s3_bucket.lakehouse.id
  eventbridge = true
}

resource "aws_s3_bucket_replication_configuration" "lakehouse" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.lakehouse.id

  rule {
    id     = "replicate-lakehouse"
    status = "Enabled"

    destination {
      bucket        = var.lakehouse_replica_bucket_arn
      storage_class = "STANDARD"
    }
  }

  depends_on = [aws_s3_bucket_versioning.lakehouse]
}

resource "aws_s3_bucket_policy" "lakehouse_tls_only" {
  bucket     = aws_s3_bucket.lakehouse.id
  policy     = data.aws_iam_policy_document.s3_tls_only_lakehouse.json
  depends_on = [aws_s3_bucket_public_access_block.lakehouse]
}

data "aws_iam_policy_document" "s3_tls_only_lakehouse" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.lakehouse.arn,
      "${aws_s3_bucket.lakehouse.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# S3 Audit Bucket (with Object Lock enabled in compliance mode)
resource "aws_s3_bucket" "audit" {
  bucket              = "${var.project_name}-${var.environment}-audit-bucket"
  force_destroy       = var.destroyable
  object_lock_enabled = !var.destroyable
  tags                = var.tags
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.audit.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  count  = var.destroyable ? 0 : 1
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.audit_retention_days
    }
  }
}

resource "aws_s3_bucket_logging" "audit" {
  bucket        = aws_s3_bucket.audit.id
  target_bucket = aws_s3_bucket.logging.id
  target_prefix = "audit/"
}

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id

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

resource "aws_s3_bucket_notification" "audit" {
  bucket      = aws_s3_bucket.audit.id
  eventbridge = true
}

resource "aws_s3_bucket_replication_configuration" "audit" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.audit.id

  rule {
    id     = "replicate-audit"
    status = "Enabled"

    destination {
      bucket        = var.audit_replica_bucket_arn
      storage_class = "STANDARD"
    }
  }

  depends_on = [aws_s3_bucket_versioning.audit]
}

resource "aws_s3_bucket_policy" "audit_tls_only" {
  bucket     = aws_s3_bucket.audit.id
  policy     = data.aws_iam_policy_document.s3_tls_only_audit.json
  depends_on = [aws_s3_bucket_public_access_block.audit]
}

data "aws_iam_policy_document" "s3_tls_only_audit" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.audit.arn,
      "${aws_s3_bucket.audit.arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# Glue Catalog Database
resource "aws_glue_catalog_database" "lakehouse" {
  name        = "${var.project_name}_${var.environment}_database"
  description = "Glue Catalog Database for TF2 FinOps Lakehouse"
}

# Glue Catalog Table for Curated Cost Data
resource "aws_glue_catalog_table" "cur_data" {
  name          = "cur_data"
  database_name = aws_glue_catalog_database.lakehouse.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification"             = "parquet"
    "projection.enabled"         = "true"
    "projection.account_id.type" = "injected"
    "projection.year.type"       = "integer"
    "projection.year.range"      = "2024,2035"
    "projection.month.type"      = "integer"
    "projection.month.range"     = "1,12"
    "projection.month.digits"    = "2"
    "storage.location.template"  = "s3://${aws_s3_bucket.lakehouse.id}/cost/curated/account_id=$${account_id}/year=$${year}/month=$${month}/"
  }

  partition_keys {
    name = "account_id"
    type = "string"
  }

  partition_keys {
    name = "year"
    type = "int"
  }

  partition_keys {
    name = "month"
    type = "int"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lakehouse.id}/cost/curated/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "parquet"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "service"
      type = "string"
    }

    columns {
      name = "region"
      type = "string"
    }

    columns {
      name = "owner"
      type = "string"
    }

    columns {
      name = "cost"
      type = "double"
    }

    columns {
      name = "currency"
      type = "string"
    }

    columns {
      name = "timestamp"
      type = "string"
    }

    columns {
      name = "curated_at"
      type = "string"
    }

    columns {
      name = "unblended_cost"
      type = "double"
    }

    columns {
      name = "service_code"
      type = "string"
    }

    columns {
      name = "resource_id"
      type = "string"
    }

    columns {
      name = "squad"
      type = "string"
    }

    columns {
      name = "cost_center"
      type = "string"
    }

    columns {
      name = "schema_version"
      type = "string"
    }

    columns {
      name = "correlation_id"
      type = "string"
    }

    columns {
      name = "idempotency_key"
      type = "string"
    }

    columns {
      name = "quality_score"
      type = "double"
    }
  }
}

# Glue Catalog Table for Containment Audit Records
resource "aws_glue_catalog_table" "containment_audit" {
  name          = "containment_audit"
  database_name = aws_glue_catalog_database.lakehouse.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification"             = "json"
    "projection.enabled"         = "true"
    "projection.account_id.type" = "injected"
    "projection.year.type"       = "integer"
    "projection.year.range"      = "2024,2035"
    "projection.month.type"      = "integer"
    "projection.month.range"     = "1,12"
    "projection.month.digits"    = "2"
    "storage.location.template"  = "s3://${aws_s3_bucket.audit.id}/audit/account_id=$${account_id}/year=$${year}/month=$${month}/"
  }

  partition_keys {
    name = "account_id"
    type = "string"
  }

  partition_keys {
    name = "year"
    type = "int"
  }

  partition_keys {
    name = "month"
    type = "int"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.audit.id}/audit/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      name                  = "json"
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "audit_id"
      type = "string"
    }

    columns {
      name = "audit_uri"
      type = "string"
    }

    columns {
      name = "audit_type"
      type = "string"
    }

    columns {
      name = "actor"
      type = "string"
    }

    columns {
      name = "timestamp"
      type = "string"
    }

    columns {
      name = "correlation_id"
      type = "string"
    }

    columns {
      name = "idempotency_key"
      type = "string"
    }

    columns {
      name = "anomaly_id"
      type = "string"
    }

    columns {
      name = "target_owner"
      type = "string"
    }

    columns {
      name = "before_state"
      type = "string"
    }

    columns {
      name = "proposed_after_state"
      type = "string"
    }

    columns {
      name = "applied_after_state"
      type = "string"
    }

    columns {
      name = "execution_mode"
      type = "string"
    }

    columns {
      name = "rollback_path"
      type = "string"
    }

    columns {
      name = "approval_status"
      type = "string"
    }

    columns {
      name = "retention_location"
      type = "string"
    }

    columns {
      name = "retention_period"
      type = "string"
    }

    columns {
      name = "account_id"
      type = "string"
    }

    columns {
      name = "resource_id"
      type = "string"
    }

    columns {
      name = "owner"
      type = "string"
    }

    columns {
      name = "audit_score"
      type = "double"
    }

    columns {
      name = "numeric_audit_score"
      type = "double"
    }
  }
}


# Athena Query Results Bucket
resource "aws_s3_bucket" "athena_results" {
  bucket        = "${var.project_name}-${var.environment}-athena-results"
  force_destroy = true
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket                  = aws_s3_bucket.athena_results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_logging" "athena_results" {
  bucket        = aws_s3_bucket.athena_results.id
  target_bucket = aws_s3_bucket.logging.id
  target_prefix = "athena/"
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

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

resource "aws_s3_bucket_notification" "athena_results" {
  bucket      = aws_s3_bucket.athena_results.id
  eventbridge = true
}

resource "aws_s3_bucket_replication_configuration" "athena_results" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "replicate-athena"
    status = "Enabled"

    destination {
      bucket        = var.athena_replica_bucket_arn
      storage_class = "STANDARD"
    }
  }

  depends_on = [aws_s3_bucket_versioning.athena_results]
}

# Athena Workgroup
resource "aws_athena_workgroup" "lakehouse" {
  name = "${var.project_name}-${var.environment}-workgroup"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.athena_query_bytes_cutoff

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/results/"

      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = aws_kms_key.data.arn
      }
    }
  }
  tags = var.tags
}

# IAM Role for S3 Replication
resource "aws_iam_role" "replication" {
  name = "${var.project_name}-${var.environment}-s3-replication-role"
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
  name = "s3-replication-policy"
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
          aws_s3_bucket.lakehouse.arn,
          aws_s3_bucket.audit.arn,
          aws_s3_bucket.athena_results.arn
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
          "${aws_s3_bucket.lakehouse.arn}/*",
          "${aws_s3_bucket.audit.arn}/*",
          "${aws_s3_bucket.athena_results.arn}/*"
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
          "${var.lakehouse_replica_bucket_arn}/*",
          "${var.audit_replica_bucket_arn}/*",
          "${var.athena_replica_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          aws_kms_key.data.arn,
          aws_kms_key.audit.arn
        ]
      }
    ]
  })
}

resource "terraform_data" "destroy_guard" {
  count = var.destroyable ? 0 : 1
  lifecycle {
    prevent_destroy = true
  }
}

# ──────────────────────────────────────────────────────────────────────────────
# CUR 2.0 / AWS Data Exports Landing Bucket
# This bucket receives raw CUR 2.0 exports written by bcm-data-exports.amazonaws.com.
# It is distinct from the lakehouse bucket. cost_puller reads manifests and Parquet
# files from here; no CDO-internal service writes to it.
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "cur_export" {
  # checkov:skip=CKV_AWS_144: "CUR export landing bucket does not need cross-region replication (raw source only)"
  # checkov:skip=CKV2_AWS_62: "CUR export landing bucket is polled by cost_puller and does not need event notifications"
  count         = var.create_cur_export_bucket ? 1 : 0
  bucket        = var.cur_export_bucket_name != "" ? var.cur_export_bucket_name : "tf2-finops-cur-export-bucket"
  force_destroy = var.destroyable
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "cur_export" {
  count                   = var.create_cur_export_bucket ? 1 : 0
  bucket                  = aws_s3_bucket.cur_export[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "cur_export" {
  count  = var.create_cur_export_bucket ? 1 : 0
  bucket = aws_s3_bucket.cur_export[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cur_export" {
  count  = var.create_cur_export_bucket ? 1 : 0
  bucket = aws_s3_bucket.cur_export[0].id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_logging" "cur_export" {
  count         = var.create_cur_export_bucket ? 1 : 0
  bucket        = aws_s3_bucket.cur_export[0].id
  target_bucket = aws_s3_bucket.logging.id
  target_prefix = "cur-export/"
}

resource "aws_s3_bucket_lifecycle_configuration" "cur_export" {
  count  = var.create_cur_export_bucket ? 1 : 0
  bucket = aws_s3_bucket.cur_export[0].id

  rule {
    id     = "abort-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "expire-raw-cur"
    status = "Enabled"
    filter {
      prefix = var.cur_raw_prefix != "" ? "${var.cur_raw_prefix}/" : ""
    }
    expiration {
      days = 90
    }
  }
}

# Bucket policy: allow bcm-data-exports to write only to raw CUR prefixes.
# Deny all other writes and deny HTTP.
# Per: https://docs.aws.amazon.com/cur/latest/userguide/dataexports-s3-bucket.html
resource "aws_s3_bucket_policy" "cur_export" {
  count      = var.create_cur_export_bucket ? 1 : 0
  bucket     = aws_s3_bucket.cur_export[0].id
  policy     = data.aws_iam_policy_document.cur_export[0].json
  depends_on = [aws_s3_bucket_public_access_block.cur_export]
}

data "aws_iam_policy_document" "cur_export" {
  count = var.create_cur_export_bucket ? 1 : 0

  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.cur_export[0].arn,
      "${aws_s3_bucket.cur_export[0].arn}/*"
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # Allow AWS Data Exports service to PUT raw CUR files under the configured prefix.
  # aws:SourceArn and aws:SourceAccount conditions prevent confused-deputy attacks.
  statement {
    sid    = "AllowBCMDataExportsPut"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["bcm-data-exports.amazonaws.com"]
    }
    actions = [
      "s3:PutObject"
    ]
    # Scope writes to the raw export prefix only; curated/, ai-input/, audit/, features/ are excluded.
    resources = [
      var.cur_raw_prefix != "" ? "${aws_s3_bucket.cur_export[0].arn}/${var.cur_raw_prefix}/*" : "${aws_s3_bucket.cur_export[0].arn}/*"
    ]
    condition {
      test     = "StringLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bcm-data-exports:us-east-1:${data.aws_caller_identity.current.account_id}:export/*"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  # Deny writes to protected prefixes (curated, ai-input, audit, features) from all principals.
  statement {
    sid    = "DenyWritesToProtectedPrefixes"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:PutObject", "s3:DeleteObject"]
    resources = [
      "${aws_s3_bucket.cur_export[0].arn}/curated/*",
      "${aws_s3_bucket.cur_export[0].arn}/ai-input/*",
      "${aws_s3_bucket.cur_export[0].arn}/audit/*",
      "${aws_s3_bucket.cur_export[0].arn}/features/*",
    ]
  }
}
