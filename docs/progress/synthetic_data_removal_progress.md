# Synthetic Data Removal Progress

## Status
Completed

## Scope
- Removed Terraform wiring for the former generated-telemetry fallback flag from the `compute_lambda` module and all environment roots.
- Removed automatic manifest, STS credential, Cost Explorer, CloudWatch traffic, and Athena CUR record generation from Lambda runtime paths.
- Changed `cost_puller` and `normalizer` to require configured telemetry inputs and explicit test fixtures.
- Updated unit tests to use explicit fake S3, STS, CloudWatch, Cost Explorer, and Athena fixtures.
- Updated operator documentation to describe fail-closed behavior when CUR, CE, cache, or Athena inputs are missing.

## Files Changed
- `modules/compute-lambda/main.tf`
- `modules/compute-lambda/variables.tf`
- `environments/sandbox/main.tf`
- `environments/sandbox/terraform.tfvars` (local ignored file only; removed obsolete setting)
- `environments/sandbox/variables.tf`
- `environments/sandbox/terraform.tfvars.example`
- `environments/staging/main.tf`
- `environments/staging/variables.tf`
- `environments/staging/terraform.tfvars.example`
- `environments/prod/main.tf`
- `environments/prod/variables.tf`
- `environments/prod/terraform.tfvars.example`
- `lambda_src/src/finops_common/aws_clients.py`
- `lambda_src/src/workers/cost_puller/handler.py`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_cost_puller.py`
- `lambda_src/tests/test_normalizer.py`
- `README.md`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`
- `docs/progress/cost_puller_telemetry_progress.md`
- `docs/progress/cost_puller_telemetry_progress_vi.md`
- `docs/progress/lambda_python_migration_progress.md`
- `docs/progress/lambda_skeletons_progress.md`

## Validation Commands
```powershell
Push-Location lambda_src; python -m pytest tests/test_cost_puller.py tests/test_normalizer.py; Pop-Location
Push-Location lambda_src; python -m pytest; Pop-Location
terraform fmt -check -recursive
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/sandbox plan -destroy -out sandbox-destroy.tfplan
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
tflint --recursive
trivy config .
checkov -d . --framework terraform
rg --no-ignore -n "<removed-synthetic-runtime-markers>" lambda_src/src lambda_src/tests modules environments README.md docs/GUIDES.md docs/GUIDES_vi.md docs/progress
```

## Results
- Focused cost-puller and normalizer unit tests pass: 24 passed.
- Full Lambda pytest suite passes: 195 passed.
- `terraform fmt -check -recursive` passes.
- Terraform init and validate pass for `bootstrap`, `environments/sandbox`, `environments/staging`, and `environments/prod`.
- Sandbox destroy plan succeeds and reports no objects to destroy, with no `prevent_destroy` blocker. The generated `sandbox-destroy.tfplan` artifact was removed after validation.
- Strict synthetic-marker scan has no matches in runtime source, tests, modules, environments, guides, README, or progress docs.
- `checkov -d . --framework terraform` passes: 1203 passed, 0 failed, 234 skipped.
- `tflint --recursive` still reports unrelated pre-existing warnings: unused `modules/compute-lambda.aws_region`, missing `archive` provider constraint in `modules/dashboard`, and unused dashboard auth TTL variables.
- `trivy config .` completes with exit code 0 but reports existing low/medium S3 logging/versioning and Lambda@Edge tracing findings outside this cleanup.

## Blockers
None for synthetic data removal.

## Next Step
Decide separately whether to clean up the existing tflint and Trivy findings.
