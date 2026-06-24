# Orchestration Module

Provisions the Step Functions standard state machine, DynamoDB state tables (run state, anomalies, routing, containment audit, materialized views), and EventBridge Scheduler triggers.

## Usage Example

```hcl
module "orchestration" {
  source                  = "../../modules/orchestration"
  project_name            = "tf2-finops"
  environment             = "sandbox"
  scheduler_expression    = "rate(24 hours)"
  step_functions_role_arn = "arn:aws:iam::123456789012:role/step-functions-role"
  scheduler_role_arn      = "arn:aws:iam::123456789012:role/scheduler-role"
  ddb_kms_key_arn         = "arn:aws:kms:ap-southeast-1:123456789012:key/some-key"
  audit_bucket_name       = "tf2-finops-audit"
  lambda_function_arns    = {
    cost_puller        = "arn:aws:lambda:ap-southeast-1:123456789012:function:cost-puller:stable"
    normalizer         = "arn:aws:lambda:ap-southeast-1:123456789012:function:normalizer:stable"
    ai_client          = "arn:aws:lambda:ap-southeast-1:123456789012:function:ai-client:stable"
    router             = "arn:aws:lambda:ap-southeast-1:123456789012:function:router:stable"
    containment_worker = "arn:aws:lambda:ap-southeast-1:123456789012:function:containment-worker:stable"
    audit_writer       = "arn:aws:lambda:ap-southeast-1:123456789012:function:audit-writer:stable"
  }
}
```
