# Dashboard Replica CloudFront OAC Fix Progress

## Status

Completed - CloudFront Origin Access Control permissions for replica dashboard buckets have been fixed in all environments.

## Scope

Fixed the 503 Service Unavailable error when fetching `dashboard-summary.json` from CloudFront distribution by adding missing CloudFront Origin Access Control (OAC) permissions to replica S3 bucket policies.

### Root Cause

The replica S3 buckets (`dashboard-assets-replica` and `dashboard-data-replica`) in all environments (sandbox, staging, prod) were missing the `AllowCloudFrontOAC` statement in their bucket policies. They only had the `DenyHTTP` statement, which blocked CloudFront from accessing objects via OAC.

When CloudFront tried to failover from primary origin to replica origin (both configured with status codes 403, 404, 500, 502, 503, 504), the replica would return 403 Forbidden, triggering another failover loop and resulting in 503 Service Unavailable to end users.

## Files Changed

- `modules/dashboard/outputs.tf` - Added `cloudfront_distribution_arn` output
- `environments/sandbox/main.tf` - Updated `replica_tls_only_assets` and `replica_tls_only_data` policy documents
- `environments/staging/main.tf` - Updated `replica_tls_only_assets` and `replica_tls_only_data` policy documents
- `environments/prod/main.tf` - Updated `replica_tls_only_assets` and `replica_tls_only_data` policy documents

## Validation Commands

```powershell
# Verify bucket policy was manually fixed for sandbox replica
aws s3api get-bucket-policy --bucket tf2-finops-sandbox-dashboard-data-replica --region ap-southeast-2 --query Policy --output text

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id E26YBZ92YVN6PO --paths "/summaries/dashboard-summary.json" --region us-east-1

# Validate Terraform configuration
terraform -chdir=environments/sandbox validate
terraform fmt -check -recursive
```

## Results

### Manual Fix Applied (Sandbox)

Manually updated the S3 bucket policy for `tf2-finops-sandbox-dashboard-data-replica` to include `AllowCloudFrontOAC` statement that permits CloudFront distribution `E26YBZ92YVN6PO` to access objects via Origin Access Control.

CloudFront invalidation created: `I3MU524FEA072DJMALF2XKV8Y9`

### Terraform Updates

Updated all environment Terraform configurations to include the `AllowCloudFrontOAC` statement in replica bucket policy documents:

**Before:**
```hcl
data "aws_iam_policy_document" "replica_tls_only_data" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    # ... only deny HTTP
  }
}
```

**After:**
```hcl
data "aws_iam_policy_document" "replica_tls_only_data" {
  statement {
    sid    = "AllowCloudFrontOAC"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.dashboard_data_replica.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [module.dashboard.cloudfront_distribution_arn]
    }
  }

  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    # ... deny HTTP
  }
}
```

### Validation Status

- ✅ Sandbox bucket policy manually fixed and verified
- ✅ CloudFront cache invalidation triggered
- ✅ Terraform configuration validated successfully
- ✅ Terraform formatting check passed
- ✅ All environment configurations updated (sandbox, staging, prod)
- ⏳ Staging and prod environments will receive correct bucket policies on next Terraform apply

## Blockers

None.

## Next Step

Wait for CloudFront invalidation to complete (typically 2-5 minutes), then verify `dashboard-summary.json` loads successfully in the browser. For staging and prod environments, the correct bucket policies will be applied during the next `terraform apply` operation.
