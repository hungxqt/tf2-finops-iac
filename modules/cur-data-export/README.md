# CUR 2.0 Data Export Module

This module manages `aws_bcmdataexports_export` in the source billing account.
Do not run it with the lakehouse bucket account provider unless that account is
also the CUR source account.

Example:

```hcl
provider "aws" {
  alias  = "cur_source"
  region = "us-east-1"

  assume_role {
    role_arn = "arn:aws:iam::336805808730:role/<cur-data-export-admin-role>"
  }
}

module "account_cur_export" {
  source = "../../modules/cur-data-export"

  providers = {
    aws = aws.cur_source
  }

  export_name             = "accountCUR"
  destination_bucket_name = "tf2-finops-cur-export-bucket-2"
  destination_prefix      = "336805808730"
  destination_region      = "ap-southeast-1"
  billing_view_arn        = "arn:aws:billing::336805808730:billingview/primary"
  tags                    = var.tags
}
```

The matching lakehouse bucket policy must allow
`bcm-data-exports.amazonaws.com` from the same source account to write to:

```text
s3://<destination_bucket>/<destination_prefix>/<export_name>/*
```
