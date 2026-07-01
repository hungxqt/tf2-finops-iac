aws_region   = "ap-southeast-1"
project_name = "tf2-finops"
environment  = "sandbox"

tags = {
  Environment = "sandbox"
  Project     = "tf2-finops"
  ManagedBy   = "Terraform"
}

# AI Engine Lambda Container Images (must be digest-pinned to satisfy validation)
request_image_uri = "093490087544.dkr.ecr.ap-southeast-1.amazonaws.com/tf2-finops/ai-engine@sha256:feb534a2c1aabd20c4811250ad1c3ef63d78247e1e25772f8fc51aee8eb3e242"

# S3 Cross-Region Replication region
replica_region = "ap-southeast-2"

# CloudFront Custom Domain Configuration (ACM certificate must be in us-east-1)
cloudfront_acm_certificate_arn = "arn:aws:acm:us-east-1:093490087544:certificate/7f6569f4-d240-4ea4-9fc6-a4ba5a260764"
cloudfront_aliases             = ["dashboard-sandbox.hungtran.id.vn"]

# CloudFront Geo-restrictions
dashboard_geo_restriction_type      = "blacklist"
dashboard_geo_restriction_locations = ["CU", "IR", "KP", "SY"]

# ACM Certificate ARN for the internal ALB HTTPS listener
alb_certificate_arn = "arn:aws:acm:us-east-1:093490087544:certificate/7f6569f4-d240-4ea4-9fc6-a4ba5a260764"

# Route 53 parameters (Optional)
private_hosted_zone_id = ""
private_dns_name       = ""
sigv4_service_name     = "ai-engine"

# Set to true to make S3 buckets, KMS keys, ECR, etc. destroyable (Sandbox exceptions)
destroyable = true

# CUR and CE Ingestion parameters
cur_source_bucket          = "tf2-finops-cur-export-bucket-2"
cur_source_prefix          = ""
cur_delay_threshold_hours  = 36
ce_lookback_window_days    = 30
traffic_metric_identifiers = ["my-alb-identifier"]

# Member accounts telemetry ingestion parameters
telemetry_member_account_ids           = ["336805808730"]
telemetry_member_role_name             = "cdo-telemetry-ingestion-role"
cur_source_bucket_arn                  = "arn:aws:s3:::tf2-finops-cur-export-bucket-2"
create_member_telemetry_ingestion_role = false
trusted_cost_puller_role_arns          = []

# ──────────────────────────────────────────────────────────────────────────────
# CUR 2.0 / AWS Data Exports configuration (optional, preferred over legacy list-scan)
#
# Option A: Externally-managed CUR export bucket (pre-existing, e.g. managed by AWS Billing)
#   - Set cur_source_bucket to "tf2-finops-cur-export-bucket" (or your export bucket name)
#   - Set cur_raw_prefix to the export prefix (e.g. the export name at the top level)
#   - Set cur_exports_json with your account-keyed export configuration
#   - Leave create_cur_export_bucket = false (default)
#
# Option B: Terraform-managed CUR export landing bucket (Terraform creates the bucket)
#   - Set create_cur_export_bucket = true
#   - Optionally set cur_export_bucket_name to override the default "tf2-finops-cur-export-bucket"
#   - Set cur_raw_prefix and cur_exports_json as above
# ──────────────────────────────────────────────────────────────────────────────

# Set to true to create the CUR export landing bucket via Terraform (default: false)
create_cur_export_bucket = true

# Override the CUR export bucket name (leave empty to use "tf2-finops-cur-export-bucket")
cur_export_bucket_name = "tf2-finops-cur-export-bucket-2"

# S3 prefix under the CUR export bucket where AWS Data Exports writes raw CUR files.
# This is typically the export name you configured in the AWS Billing Console.
# Example: "finops-cur-export" → writes to s3://<bucket>/finops-cur-export/<export-name>/...
cur_raw_prefix = ""

# Account-keyed JSON map of CUR 2.0 export configurations.
# Each entry key is the source AWS Account ID; each value contains:
#   source_account_id: the account whose CUR data is being exported
#   prefix:           the top-level S3 prefix for the export (typically the export name prefix)
#   export_name:      the export name configured in AWS Billing Console Data Exports
#   allowed_raw_prefix: (optional) restrict manifest reportKey containment check to this prefix
# Example (single payer account):
cur_exports_json = <<-EOT
{
  "336805808730": {
    "source_account_id": "336805808730",
    "prefix": "336805808730",
    "export_name": "accountCUR",
    "allowed_raw_prefix": "336805808730"
  }
}
EOT

# Enable HTTPS for the internal ALB (default: true; set to false for Sandbox HTTP mode)
enable_alb_https = false

# Prevent Post-Apply Step Functions Execution
scheduler_enabled = true

# Sandbox-only Synthetic Replay Harness Configurations
synthetic_replay_enabled              = true
synthetic_replay_business_context_uri = "s3://tf2-finops-sandbox-lakehouse-bucket/replay/business_context.json"