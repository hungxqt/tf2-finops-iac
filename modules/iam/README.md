# IAM Module

Provisions least-privilege IAM policies, permissions boundaries, worker execution roles, and cross-account validation templates.

## Usage Example

```hcl
module "iam" {
  source                    = "../../modules/iam"
  project_name              = "tf2-finops"
  environment               = "sandbox"
  lakehouse_bucket_arn      = "arn:aws:s3:::tf2-finops-lakehouse"
  audit_bucket_arn          = "arn:aws:s3:::tf2-finops-audit"
  dynamodb_table_arns       = ["arn:aws:dynamodb:ap-southeast-1:123456789012:table/tf2-finops-runs"]
  kms_key_arns              = ["arn:aws:kms:ap-southeast-1:123456789012:key/some-key"]
  containment_apply_enabled = true
}
```
