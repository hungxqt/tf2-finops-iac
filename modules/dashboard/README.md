# Dashboard Module

This module provisions an AWS-native, low-cost static dashboard hosting and data access foundation for Finance users. It includes S3 bucket structures for dashboard assets and precomputed summary data, CloudFront with Origin Access Control (OAC), Cognito user authentication, and Athena named queries for finance-facing data insights.

## Cognito Data-Access Model

Rather than making dashboard summary data public, this module implements a secure, authenticated data-access model:
1. **CloudFront Delivery**: Serves public static frontend shell assets (e.g., `index.html`, javascript packages) from the asset bucket via a CloudFront distribution with Origin Access Control (OAC).
2. **Cognito Authentication**: The static frontend app must enforce login using the Cognito User Pool (Hosted UI).
3. **IAM S3 Data Access**: Once authenticated, the frontend swaps Cognito user tokens for temporary credentials via the Cognito Identity Pool.
4. **S3 Direct Fetch**: The frontend fetches precomputed dashboard JSON summaries directly from the private dashboard data bucket using these temporary credentials.

An unauthenticated visitor can view the static shell but cannot access any underlying cost summary files.

## Runtime Configuration Discovery

During deployment, this module emits a non-secret configuration file `dashboard_runtime_config.json` directly into the static assets S3 bucket:
```json
{
  "aws_region": "ap-southeast-1",
  "user_pool_id": "ap-southeast-1_XXXXX",
  "user_pool_client_id": "XXXXX",
  "identity_pool_id": "ap-southeast-1:XXXX-XXXX-XXXX",
  "hosted_ui_domain": "my-project-sandbox-dash.auth.ap-southeast-1.amazoncognito.com",
  "data_bucket_name": "my-project-sandbox-dashboard-data",
  "data_prefix": "summaries/",
  "cloudfront_domain": "dxxxxx.cloudfront.net"
}
```
The static frontend application fetches this JSON at startup (relative path: `/dashboard_runtime_config.json`) to discover Cognito and data S3 bucket coordinates dynamically.

## Usage Example

```hcl
module "dashboard" {
  source                 = "../../modules/dashboard"
  project_name           = "tf2-finops"
  environment            = "sandbox"
  glue_database_name     = "tf2_finops_lakehouse_sandbox"
  athena_workgroup_name  = "tf2-finops-athena-sandbox"
  dashboard_kms_key_arn  = "arn:aws:kms:ap-southeast-1:123456789012:key/xxx"
  dashboard_data_prefix  = "summaries/"
  enable_quicksight      = false
}
```
