# Alerting Module

Provisions separate, encrypted SNS topics and email subscriptions for Finance and Engineering teams.

## Usage Example

```hcl
module "alerting" {
  source                          = "../../modules/alerting"
  project_name                    = "tf2-finops"
  environment                     = "sandbox"
  finance_email_subscriptions     = ["finance-alerts@example.com"]
  engineering_email_subscriptions = ["eng-alerts@example.com"]
  sns_kms_key_arn                 = "arn:aws:kms:ap-southeast-1:123456789012:key/some-key"
}
```
