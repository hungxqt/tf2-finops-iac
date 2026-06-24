# Compute Lambda Module

Deploys Lambda worker functions inside the private VPC subnet infrastructure with appropriate environment configurations, timeouts, and execution roles.

## Usage Example

```hcl
module "compute-lambda" {
  source                     = "../../modules/compute-lambda"
  project_name               = "tf2-finops"
  environment                = "sandbox"
  private_subnet_ids         = ["subnet-12345678", "subnet-87654321"]
  lambda_security_group_id   = "sg-12345678"
  lambda_role_arns           = {
    cost_puller        = "arn:aws:iam::123456789012:role/cost-puller-role"
    normalizer         = "arn:aws:iam::123456789012:role/normalizer-role"
    ai_client          = "arn:aws:iam::123456789012:role/ai-client-role"
    router             = "arn:aws:iam::123456789012:role/router-role"
    containment_worker = "arn:aws:iam::123456789012:role/containment-worker-role"
    audit_writer       = "arn:aws:iam::123456789012:role/audit-writer-role"
  }
  lakehouse_bucket_name      = "tf2-finops-lakehouse"
  audit_bucket_name          = "tf2-finops-audit"
  ai_engine_endpoint_url     = "https://ai.local/v1"
  containment_apply_enabled  = true
}
```
