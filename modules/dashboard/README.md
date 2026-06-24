# Dashboard Module

Provisions Athena Named Queries for finance-readable dashboards and optional QuickSight resource skeletons.

## Usage Example

```hcl
module "dashboard" {
  source                 = "../../modules/dashboard"
  project_name           = "tf2-finops"
  environment            = "sandbox"
  glue_database_name     = "tf2_finops_lakehouse_sandbox"
  athena_workgroup_name  = "tf2-finops-athena-sandbox"
  enable_quicksight      = false
}
```
