# Observability Module

Provisions CloudWatch dashboards, metric filters, and alert alarms for execution health, timeouts, stale states, and configuration drift.

## Usage Example

```hcl
module "observability" {
  source                 = "../../modules/observability"
  project_name           = "tf2-finops"
  environment            = "sandbox"
  state_machine_arn      = "arn:aws:states:ap-southeast-1:123456789012:stateMachine:tf2-finops-orchestrator"
  lambda_function_names  = ["cost-puller", "normalizer", "ai-client", "router", "containment-worker", "audit-writer"]
  engineering_topic_arn  = "arn:aws:sns:ap-southeast-1:123456789012:tf2-finops-engineering-alerts"
  finance_topic_arn      = "arn:aws:sns:ap-southeast-1:123456789012:tf2-finops-finance-alerts"
  log_retention_days     = 14
}
```
