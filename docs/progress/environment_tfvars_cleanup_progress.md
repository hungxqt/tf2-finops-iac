# Environment Terraform Variables Example Cleanup Progress

## Status
Validated (all roots initialized, formatted, and validated successfully; all unit tests passing)

## Scope
Clean up and complete coverage in all `terraform.tfvars.example` files to represent every variable declared in the root `variables.tf` files with safe, non-secret placeholder values. This covers `bootstrap`, `environments/sandbox`, `environments/staging`, and `environments/prod`.

## Key Changes

### Bootstrap (`bootstrap/terraform.tfvars.example`)
- Added `tags` to document default common tagging behavior.
- Added `destroyable = false` to enforce environment safety by default.

### Environments (`environments/*/terraform.tfvars.example`)
- Added the following missing variables across sandbox, staging, and prod configurations:
  - `destroyable`: Indicates whether resources can be destroyed. Set to `true` in `sandbox` but `false` in `staging` and `prod`.
  - `telemetry_member_account_ids`: Configured with standard placeholder account `["123456789012"]`.
  - `telemetry_member_role_name`: Configured with `"cdo-telemetry-ingestion-role"`.
  - `cur_source_bucket_arn`: Configured with `"arn:aws:s3:::company-cdo-123456789012-telemetry"`.
  - `create_member_telemetry_ingestion_role`: Configured with `false`.
  - `trusted_cost_puller_role_arns`: Configured with `[]` (empty list for safety by default).
- Preserved Environment Safety constraints:
  - Staging/prod enforce `destroyable = false`.
  - Staging/prod enforce `enable_alb_https = true` for security compliance.

## Files Modified
- [bootstrap/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/terraform.tfvars.example)
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example)
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example)
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example)

## Validation Commands
```powershell
# Format code
terraform fmt -check -recursive

# Validate all roots
./scripts/validate.ps1
```
