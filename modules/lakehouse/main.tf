# Lakehouse Module Resources
# This module creates durable cost, audit, and query storage.

data "aws_caller_identity" "current" {}

# Common KMS Key Policy Document
data "aws_iam_policy_document" "kms_policy" {
  statement {
    sid    = "Enable IAM User Permissions"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }
}

# KMS Key for general data (Lakehouse, Athena Results)
resource "aws_kms_key" "data" {
  description             = "KMS key for data encryption (Lakehouse, Athena)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_policy.json
  lifecycle {
    prevent_destroy = true
  }
  tags = var.tags
}

resource "aws_kms_alias" "data" {
  name          = "alias/${var.project_name}-${var.environment}-data-key"
  target_key_id = aws_kms_key.data.key_id
}

# KMS Key for Audit Log Encryption
resource "aws_kms_key" "audit" {
  description             = "KMS key for Audit log encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_policy.json
  lifecycle {
    prevent_destroy = true
  }
  tags = var.tags
}

resource "aws_kms_alias" "audit" {
  name          = "alias/${var.project_name}-${var.environment}-audit-key"
  target_key_id = aws_kms_key.audit.key_id
}

# KMS Key for DynamoDB Table Encryption
resource "aws_kms_key" "ddb" {
  description             = "KMS key for DynamoDB state encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_policy.json
  lifecycle {
    prevent_destroy = true
  }
  tags = var.tags
}

resource "aws_kms_alias" "ddb" {
  name          = "alias/${var.project_name}-${var.environment}-ddb-key"
  target_key_id = aws_kms_key.ddb.key_id
}

# S3 Lakehouse Bucket
resource "aws_s3_bucket" "lakehouse" {
  bucket        = "${var.project_name}-${var.environment}-lakehouse-bucket"
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
  tags = var.tags
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
  force_destroy       = false
  object_lock_enabled = true
  lifecycle {
    prevent_destroy = true
  }
  tags = var.tags
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
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.audit_retention_days
    }
  }
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

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data.arn
      sse_algorithm     = "aws:kms"
    }
  }
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
