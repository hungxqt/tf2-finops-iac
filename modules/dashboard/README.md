# Dashboard Module

This module provisions an AWS-native, secure dashboard hosting and data access foundation. It enforces CloudFront as the authenticated front door for static assets and dashboard JSON summaries using Cognito Authorization Code + PKCE authentication at the edge.

## React/Vite Frontend Asset Handoff

Terraform does not publish frontend UI files to the dashboard asset bucket. The React/Vite source lives in `modules/dashboard/frontend/` and builds deterministic static output into `modules/dashboard/resources/`.

Build and upload the static UI shell independently to the asset bucket output (`asset_bucket_name` / handoff name `dashboard_asset_bucket_name`):

```powershell
cd modules/dashboard/frontend
npm install
npm run typecheck
npm run lint
npm test
npm run build
```

Terraform continues to emit only the non-secret `dashboard_runtime_config.json` object so the external frontend can discover Cognito, CloudFront, and dashboard data prefix settings at runtime.

## Authenticated Front-Door Architecture

Rather than allowing unauthenticated access to frontend shells or exposing API endpoints directly:
1. **Authenticated Delivery**: All static assets and precomputed JSON summaries (`/${dashboard_data_prefix}*`) are delivered via CloudFront and protected by Lambda@Edge viewer-request JWT authentication.
2. **Cognito Authorization Code + PKCE**: Unauthenticated requests are intercepted at the edge and redirected to the Cognito Hosted UI to initiate code exchange and PKCE validation.
3. **No Direct API Proxying (Disabled)**: Dashboard direct `/v1/*` API proxying through CloudFront is disabled because AWS does not support associating origin-request Lambda@Edge functions with CloudFront distributions utilizing VPC origins. Direct AI queries and containment actions continue to run securely through the `VpcAlbCallerLambda` backend integration path.
4. **KMS Encrypted Replication**: S3 replication configurations for both assets and data are secured with source KMS decryption and destination KMS encryption.

## Dashboard UX Contract

- The dashboard is read-only first for Finance, Engineering, and CDO users.
- It reads precomputed JSON summaries from the dashboard data bucket, defaulting to `summaries/dashboard-summary.json`.
- It validates the summary contract in the frontend using TypeScript and runtime schema validation.
- It shows action status, audit evidence, approval intent, and containment eligibility, but does not perform Verify, Rollback, or Approval mutations.
- Real interactive actions require a future backend action gateway/API and must not be implemented as direct `/v1/*` CloudFront calls.

## Usage Example

```hcl
module "dashboard" {
  source                              = "../../modules/dashboard"
  project_name                        = "tf2-finops"
  environment                         = "sandbox"
  glue_database_name                  = "tf2_finops_lakehouse_sandbox"
  athena_workgroup_name               = "tf2-finops-athena-sandbox"
  dashboard_kms_key_arn               = "arn:aws:kms:ap-southeast-1:123456789012:key/xxx"
  dashboard_replica_kms_key_arn       = "arn:aws:kms:ap-southeast-2:123456789012:key/yyy"
  dashboard_data_prefix               = "summaries/"
  s3_logging_bucket_id                = "logging-bucket-id"
  dashboard_assets_replica_bucket_arn = "arn:aws:s3:::replica-assets-bucket"
  dashboard_data_replica_bucket_arn   = "arn:aws:s3:::replica-data-bucket"
  cloudfront_acm_certificate_arn      = ""
  cloudfront_aliases                  = []
  destroyable                         = true
}
```

## Logging Configuration

- `s3_logging_bucket_id`: This input variable specifies the S3 bucket used as the target for server-access logs of the dashboard asset and data S3 buckets.
- **CloudFront Logs**: Standard logs for the CloudFront distribution are written to a dedicated, module-managed S3 bucket (`aws_s3_bucket.cloudfront_logs`) named `${var.project_name}-${var.environment}-cloudfront-logs`. This dedicated bucket utilizes ACL-based delivery (via `BucketOwnerPreferred` ownership and canonical user grants) to comply with CloudFront logging requirements, while the main lakehouse logging bucket remains hardened with `BucketOwnerEnforced`.

