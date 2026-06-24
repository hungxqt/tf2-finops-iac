# Lakehouse Module

Provisions S3 buckets (lakehouse and audit), KMS encryption keys, Glue Catalog, and Athena workgroup.

## Usage Example

```hcl
module "lakehouse" {
  source                    = "../../modules/lakehouse"
  project_name              = "tf2-finops"
  environment               = "sandbox"
  aws_region                = "ap-southeast-1"
  audit_retention_days      = 90
  athena_query_bytes_cutoff = 10000000000
}
```
