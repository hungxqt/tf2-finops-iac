# Dashboard Module

This module provisions an AWS-native, secure dashboard hosting and data access foundation. It enforces CloudFront as the authenticated front door for static assets, dashboard JSON summaries, and `/v1/*` API actions using Cognito Authorization Code + PKCE authentication at the edge.

## Frontend Asset Handoff

Terraform does not publish frontend UI files to the dashboard asset bucket. Build and upload the static UI shell independently to the asset bucket output (`asset_bucket_name` / handoff name `dashboard_asset_bucket_name`).

Terraform continues to emit only the non-secret `dashboard_runtime_config.json` object so the external frontend can discover Cognito, CloudFront, and dashboard data prefix settings at runtime.

## Authenticated Front-Door Architecture

Rather than allowing unauthenticated access to frontend shells or exposing API endpoints directly:
1. **Authenticated Delivery**: All static assets and precomputed JSON summaries (`/${dashboard_data_prefix}*`) are delivered via CloudFront and protected by Lambda@Edge viewer-request JWT authentication.
2. **Cognito Authorization Code + PKCE**: Unauthenticated requests are intercepted at the edge and redirected to the Cognito Hosted UI to initiate code exchange and PKCE validation.
3. **Protected API Gateway Proxy**: Requests to `/v1/*` are routed through a CloudFront VPC Origin targeting the private internal ALB. These requests are signed with AWS SigV4 by the origin-request Lambda@Edge handler, which also strips any Cognito cookies before reaching the ALB.
4. **KMS Encrypted Replication**: S3 replication configurations for both assets and data are secured with source KMS decryption and destination KMS encryption.

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
  dashboard_api_vpc_origin_alb_arn    = "arn:aws:elasticloadbalancing:ap-southeast-1:123456789012:loadbalancer/app/ai-alb/abc"
  dashboard_api_origin_domain_name    = "ai-alb-12345.ap-southeast-1.elb.amazonaws.com"
  dashboard_data_prefix               = "summaries/"
  s3_logging_bucket_id                = "logging-bucket-id"
  dashboard_assets_replica_bucket_arn = "arn:aws:s3:::replica-assets-bucket"
  dashboard_data_replica_bucket_arn   = "arn:aws:s3:::replica-data-bucket"
  cloudfront_acm_certificate_arn      = ""
  cloudfront_aliases                  = []
  destroyable                         = true
}
```


