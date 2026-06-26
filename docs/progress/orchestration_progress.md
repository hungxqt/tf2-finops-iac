# Orchestration Progress

## Status
Completed for state/idempotency alignment scope.

## Scope
Aligned the CDO state worker and orchestration idempotency infrastructure with the signed AI API, telemetry, and deployment contracts:
- Renamed the physical run-state/idempotency table to `finops-idempotency-{environment}` while preserving the `run_state` output key for module compatibility.
- Enabled DynamoDB TTL on `ttl_expiry` for 24-hour idempotency/run locks.
- Updated the state worker idempotency key format to `{tenant_id}:{billing_period_date}:{batch_type}`.
- Added payload hash mismatch handling with `ERR_IDEMPOTENCY_MISMATCH` status semantics.
- Added `FAILED_CONTRACT_CHECK` through the `fail_contract_check` operation.
- Added contract field validation for 12-digit AWS account IDs, lowercase SHA-256 payload hashes, and semantic contract versions.
- Wired `ERROR_BUDGET_TABLE_NAME` into the state worker environment and tested that locked error budgets force dry-run.
- Removed the legacy standalone `services/state-lambda` directory from the root capstone workspace after confirming the IAC state worker covers the required DynamoDB idempotency behavior.

## Files Changed
- `lambda_src/src/workers/state/handler.py`
- `lambda_src/src/workers/audit_writer/handler.py`
- `lambda_src/src/workers/cost_puller/handler.py`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/src/workers/router/handler.py`
- `lambda_src/src/finops_common/utils.py`
- `lambda_src/src/finops_common/__init__.py`
- `lambda_src/src/finops_common/aws_clients.py`
- `lambda_src/tests/test_state.py`
- `lambda_src/tests/test_finops_common.py`
- `lambda_src/tests/test_step_function_lambda_coverage.py`
- `pytest.ini`
- `modules/orchestration/main.tf`
- `modules/compute-lambda/main.tf`
- `environments/sandbox/main.tf`
- `environments/staging/main.tf`
- `environments/prod/main.tf`
- `docs/progress/orchestration_progress.md`
- `docs/progress/orchestration_progress_vi.md`
- `docs/progress/state_lambda_implementation_notes.md`
- `docs/progress/state_lambda_implementation_notes_vi.md`

## Validation Commands
```powershell
python -m pytest lambda_src\tests\test_state.py lambda_src\tests\test_finops_common.py lambda_src\tests\test_step_function_lambda_coverage.py -q
terraform fmt -recursive modules\orchestration modules\compute-lambda environments\sandbox environments\staging environments\prod
terraform fmt -check -recursive modules\orchestration modules\compute-lambda environments\sandbox environments\staging environments\prod
python -m pytest
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
```

## Results
- Focused Python tests: Success, 21 passed with no warnings.
- Terraform formatting for touched modules/environments: Success.
- Full Lambda Python tests: Success, 45 passed with no warnings.
- Sandbox Terraform init with `-backend=false`: Success.
- Sandbox Terraform validate: Success, configuration is valid.
- Staging Terraform init with `-backend=false`: Success.
- Staging Terraform validate: Success, configuration is valid.
- Prod Terraform init with `-backend=false`: Success.
- Prod Terraform validate: Success, configuration is valid.

## Blockers
None for this scope.

## Next Step
Run optional Trivy/Checkov scans for the changed Terraform surface when security scan tooling is needed for the next handoff.