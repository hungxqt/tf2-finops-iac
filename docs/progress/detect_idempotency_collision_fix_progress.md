# Same-Day Detect Idempotency Collision Fix Progress

**Date**: 2026-06-30  
**Status**: COMPLETE

## Summary

Implemented the strict-contract fix for same-day detect idempotency collisions:
- Scheduled daily `/v1/detect` remains exactly-once per tenant/date.
- Same-day daily reruns are blocked and route to `AccountDuplicateIgnored` instead of re-entering `InvokeDetect`.
- Intentional same-day reruns must use `is_ad_hoc = true` which uses unique ad-hoc keys and consumes the daily ad-hoc quota.
- Existing hash-mismatch fail-closed behavior is preserved.
- No `finops-idempotency-{env}` rows are deleted or overwritten.

## Changes

### 1. Run-State Key & Duplicate Handling

| File | Change |
| --- | --- |
| `lambda_src/src/workers/state/handler.py` | Updated the run-state key logic so that ad-hoc run-state keys include the `run_id` to ensure uniqueness across manual/ad-hoc executions. The scheduled daily run-state key remains compatible (`account_id:period:date`). |
| `modules/orchestration/statemachine.json` | Updated the `DuplicateRun` choice state so that `FAILED` daily runs route to the terminal `AccountDuplicateIgnored` state instead of re-entering `InvokeDetect` and triggering idempotency collisions. |
| `docs/statemachine.json` | Re-rendered the static ASL copy using the render script to mirror the `statemachine.json` template changes. |

### 2. Telemetry Ingestion & API Key Validation

| File | Change |
| --- | --- |
| `lambda_src/src/workers/normalizer/handler.py` | Updated normalizer `batch_type` selection logic to emit `daily` unchanged for scheduled runs, and `adhoc-<safe-run-id>` for ad-hoc executions, where `safe_run_id` is sanitized to keep only alphanumeric characters, hyphens, and underscores. |
| `lambda_src/src/workers/vpc_alb_caller/handler.py` | Updated `AI_IDEMPOTENCY_KEY_PATTERN` regex and its `InvalidInputError` message to accept the new ad-hoc key format `tenant_id:execution_date:adhoc-<safe-run-id>` while still enforcing tenant/date validation and body consistency. |

### 3. Verification & Documentation

| File | Change |
| --- | --- |
| `docs/GUIDES.md` | Updated Step 3.3 to document that same-day daily reruns are blocked, and intentional reruns must be done as ad-hoc runs. |
| `docs/GUIDES_vi.md` | Updated Step 3.3 Vietnamese translation to document same-day daily rerun blockages. |
| `docs/MANUAL_STEP_FUNCTIONS_EXECUTION.md` | Added a dedicated section under Key Constraints & Safety Guardrails explaining the same-day daily rerun blocking behavior and ad-hoc overrides. |
| `docs/MANUAL_STEP_FUNCTIONS_EXECUTION_vi.md` | Added the Vietnamese translation of the same-day daily rerun blocking behavior and ad-hoc overrides. |
| `lambda_src/tests/test_state.py` | Added regression test `test_state_adhoc_run_state_key_uniqueness` verifying ad-hoc run-state keys are unique. |
| `lambda_src/tests/test_normalizer.py` | Added regression test `test_normalizer_batch_type_emissions` and updated existing ad-hoc mode assertions to match `adhoc-<safe-run-id>`. |
| `lambda_src/tests/test_vpc_alb_caller.py` | Added regression test `test_vpc_alb_caller_adhoc_key_validation` verifying validation behavior. |
| `lambda_src/tests/test_state_machine.py` | Added regression test `test_state_machine_failed_run_duplicate_handling` to ensure FAILED daily duplicate checks route to `AccountDuplicateIgnored`. |

## Validation Results

- Ran `python scripts/render-static-asl.py` successfully.
- Verified Terraform fmt/validate:
  - `terraform fmt -check -recursive modules/orchestration modules/compute-lambda modules/iam` (Success)
  - `terraform -chdir=environments/sandbox init -backend=false` (Success)
  - `terraform -chdir=environments/sandbox validate` (Success)
- Ran focused and full Python test suites:
  - `python -m pytest tests/test_state.py tests/test_normalizer.py tests/test_vpc_alb_caller.py tests/test_step_function_payload_contract.py tests/test_state_machine.py` (219 passed)
  - `python -m pytest` (374 passed, 0 failures)

## Next Steps

- Proceed with deploying to sandbox/staging environments.
- Inform operators to use `is_ad_hoc = true` for manual same-day reruns rather than attempting to delete database records.
