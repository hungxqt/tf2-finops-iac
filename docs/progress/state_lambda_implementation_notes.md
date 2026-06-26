# State Lambda Idempotency Implementation Notes

## Goal

This change aligns the State Lambda in `tf2-finops-iac` with the signed AI API, Telemetry, and Deployment contracts. The focus is moving the idempotency hot path to the required DynamoDB table `finops-idempotency-{environment}`, using a 24-hour TTL, and removing reliance on the old standalone `services/state-lambda` implementation in the root workspace.

## Why this changed

Before this change, the state worker was directionally correct because it ran inside Step Functions and used DynamoDB. However, it still diverged from the contracts in several important ways:

- The run-state table name did not follow the `finops-idempotency-{env}` pattern.
- The idempotency key did not follow the contract format `{tenant_id}:{billing_period_date}:{batch_type}`.
- The run-state table did not enable `ttl_expiry` for the 24-hour lock.
- The worker did not clearly handle the same idempotency key with a different payload hash.
- The state worker did not receive `ERROR_BUDGET_TABLE_NAME` to check error-budget lock state and force dry-run.
- The old standalone `services/state-lambda` used a separate flow and S3 store that no longer matched the current IaC architecture.

## Main changes

### State worker

Main file: `lambda_src/src/workers/state/handler.py`

The state worker now supports these operations:

- `prepare`: creates run context, tenant ID, batch type, and a contract-compliant idempotency key.
- `check`: writes an `IN_PROGRESS` lock when missing; returns the existing status when the lock already exists.
- `complete`: updates status to `COMPLETED`.
- `failed`: updates status to `FAILED`.
- `fail_contract_check`: updates status to `FAILED_CONTRACT_CHECK`.
- `check_quota`: limits ad-hoc runs to 5 per tenant per day.
- `check_error_budget`: reads the error budget table and sets `force_dry_run = true` when the tenant is locked.

The DynamoDB item stores these fields:

- `idempotency_key`
- `payload_sha256`
- `status`
- `run_id`
- `correlation_id`
- `tenant_id`
- `billing_period_date`
- `batch_type`
- `created_at`
- `updated_at`
- `ttl_expiry`
- `failure_code` when present

When the same `idempotency_key` is reused with a different `payload_sha256`, the state worker returns `ERR_IDEMPOTENCY_MISMATCH` to prevent processing the wrong duplicate payload.

### Shared helper

The helpers in `lambda_src/src/finops_common/utils.py` were updated for shared use:

- `utc_now()`
- `iso_utc_now()`
- `deterministic_tenant_id(account_id)`
- `idempotency_key(tenant_id, billing_period_date, batch_type)`

`FakeDynamoDB` in `lambda_src/src/finops_common/aws_clients.py` was also extended so tests can cover conditional writes and duplicate state without calling real AWS.

### Terraform

`modules/orchestration/main.tf` changes the physical run-state table to:

```hcl
name = "finops-idempotency-${var.environment}"
```

The table enables TTL:

```hcl
ttl {
  attribute_name = "ttl_expiry"
  enabled        = true
}
```

`modules/compute-lambda/main.tf` adds the state worker environment variable:

```hcl
ERROR_BUDGET_TABLE_NAME = lookup(var.dynamodb_table_names, "error_budget", "")
```

The `sandbox`, `staging`, and `prod` environment roots were updated so IAM pre-wiring points to the correct `finops-idempotency-{environment}` table.

## Legacy service removed

The standalone directory below was removed from the root workspace because it is no longer the primary implementation path:

```text
services/state-lambda/
```

Removal reasons:

- It used a separate service interface such as `ACQUIRE_RUN`, `GET_RUN`, and `REDRIVE_RUN` instead of the current Step Functions operations.
- It had a separate S3 state store, while the contract requires DynamoDB as the idempotency hot path.
- It had its own Terraform/package flow outside the `tf2-finops-iac` skeleton.
- It could confuse the team during deployment or review.

Useful semantics were preserved: `IN_PROGRESS`, `COMPLETED`, `FAILED`, `FAILED_CONTRACT_CHECK`, basic schema validation, ad-hoc quota checks, and payload hash mismatch handling.

## Tests updated

Key tests updated or added:

- `lambda_src/tests/test_state.py`
- `lambda_src/tests/test_finops_common.py`
- `lambda_src/tests/test_step_function_lambda_coverage.py`

Important cases:

- Fresh `check` writes `IN_PROGRESS` and includes `ttl_expiry`.
- Duplicate with the same key returns the current status.
- Duplicate with the same key and a different `payload_sha256` returns `ERR_IDEMPOTENCY_MISMATCH`.
- `complete`, `failed`, and `fail_contract_check` update the expected status.
- `check_quota` blocks the sixth ad-hoc run for the same tenant/day.
- `check_error_budget` reads `ERROR_BUDGET_TABLE_NAME` and forces dry-run when locked.
- Static coverage verifies compute Lambda has `RUN_STATE_TABLE_NAME` and `ERROR_BUDGET_TABLE_NAME`.

## Validation run

```powershell
python -m pytest lambda_src\tests\test_state.py lambda_src\tests\test_finops_common.py lambda_src\tests\test_step_function_lambda_coverage.py -q
terraform fmt -check -recursive modules\orchestration modules\compute-lambda environments\sandbox environments\staging environments\prod
python -m pytest
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
```

Results:

- Focused Python tests: 21 passed with no warnings.
- Full Lambda tests: 45 passed with no warnings.
- Terraform fmt check for touched paths: passed.
- Sandbox, staging, and prod Terraform init/validate with `-backend=false`: passed.

## Remaining notes

- README still has older wording about ECS/Fargate hosting. AGENTS/IMPLEMENTATION now prioritize Lambda container + private internal ALB. README should be cleaned up in a separate docs PR if the team wants to remove stale wording.