# Sandbox Full Teardown Progress

## Status
Completed (all tests and static validations passing; destroyable inputs and guards successfully wired).

## Scope
Make the `environments/sandbox` environment fully destroyable while ensuring `staging` and `prod` remain protected:
- Added a shared `destroyable` variable to `lakehouse`, `orchestration`, `dashboard`, and `ai-runtime-lambda` modules.
- Passed `destroyable = true` from `environments/sandbox` and `destroyable = false` from staging/production.
- Removed static `prevent_destroy = true` lifecycle blocks from all core module resources (KMS keys, S3 buckets, and DynamoDB tables).
- Added a count-conditional `destroy_guard` sentinel resource (`terraform_data`) in all four core modules to block full destroys in non-sandbox environments.
- Wired S3 bucket `force_destroy = var.destroyable` for logging, lakehouse, audit, dashboard data, and replica S3 buckets.
- Configured ECR repository `force_delete = var.destroyable`.
- Modified KMS key `deletion_window_in_days = var.destroyable ? 7 : 30`.
- Configured conditional Compliance Object Lock for sandbox: disabled S3 Object Lock configuration when `var.destroyable` is true to enable clean sandbox teardowns, keeping the 90-day Compliance Object Lock for staging/prod.
- Updated `docs/GUIDES.md` and `docs/GUIDES_vi.md` to document the sandbox destroy workflow and hard AWS Object Lock teardown limitations.

## Files Changed
- `modules/lakehouse/variables.tf`
- `modules/lakehouse/main.tf`
- `modules/dashboard/variables.tf`
- `modules/dashboard/main.tf`
- `modules/orchestration/variables.tf`
- `modules/orchestration/main.tf`
- `modules/ai-runtime-lambda/variables.tf`
- `modules/ai-runtime-lambda/main.tf`
- `environments/sandbox/variables.tf`
- `environments/sandbox/main.tf`
- `environments/staging/variables.tf`
- `environments/staging/main.tf`
- `environments/prod/variables.tf`
- `environments/prod/main.tf`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`

## Validation Commands
```powershell
# Format check
terraform fmt -check -recursive

# Validate configurations
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Run unit tests
cd lambda_src
python -m pytest
cd ..
```

## Results
- `terraform fmt -check -recursive`: Success.
- `terraform validate` (sandbox/staging/prod): Success.
- `python -m pytest`: Success (All 40 tests passed cleanly).

## Blockers
None.

## Next Step
Sandbox is ready for teardown testing.
