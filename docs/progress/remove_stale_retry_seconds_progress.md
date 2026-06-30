# Remove retry_after_seconds From Step Functions Context Progress

## Status
Completed

## Scope
Remove the stale `retry_after_seconds` field from the orchestration workflow, tests, and internal event models. The workflow will rely on existing wait states instead: `WaitForCURExport.Seconds = var.cur_retry_interval_seconds` and `WaitForCostExplorer.Seconds = 300`. This closes the gap between fixture-shaped payloads and live EventBridge scheduled input.

Specifically:
- Removed `retry_after_seconds.$` from `EvaluateErrorBudgetLock` and `SetTelemetryForceDryRun` parameters in `modules/orchestration/statemachine.json` and mirrored `docs/statemachine.json`.
- Preserved `cur_retry`, `ce_retry`, `ai_retry`, `force_dry_run`, and `error_budget_locked` propagation.
- Added `ce_retry.$` to `EvaluateErrorBudgetLock` and `SetTelemetryForceDryRun` since it was missing but required for CE retry states.
- Removed `retry_after_seconds` field, parse, and serialize handling from `Response` and `Event` classes in `lambda_src/src/finops_common/event.py`.
- Removed `retry_after_seconds` from `SCHEDULED_WORKFLOW_INPUT` in `lambda_src/tests/fixtures/step_function_payloads.py`.
- Added a payload-resolution test proving `EvaluateErrorBudgetLock` resolves against the real prepared scheduled context plus `error_budget_check` without `retry_after_seconds`.
- Added a static ASL test asserting `retry_after_seconds` is absent from both ASL files.
- Verified that wait states and other retry-count tests (`cur_retry`, `ce_retry`) function correctly.

## Root Cause
`retry_after_seconds` was a stale field in the orchestration workflow. Removing it ensures clean payloads and closes potential drift between test payload shapes and real scheduled EventBridge execution inputs.

## Files Changed
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)
- [lambda_src/src/finops_common/event.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/event.py)
- [lambda_src/tests/fixtures/step_function_payloads.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/fixtures/step_function_payloads.py)
- [lambda_src/tests/test_step_function_payload_contract.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_step_function_payload_contract.py)

## Validation Commands
```powershell
Push-Location lambda_src
python -m pytest tests/test_state.py tests/test_state_machine.py tests/test_step_function_payload_contract.py tests/test_finops_common.py
python -m pytest
Pop-Location
terraform -chdir=environments/sandbox validate
trivy config .
checkov -d modules/orchestration --framework terraform
```

## Results
- `terraform -chdir=environments/sandbox validate`: Success (Success! The configuration is valid.)
- targeted unit tests: Success (All 168 passed)
- full unit tests: Success (All 357 passed)
- trivy static scan: Success (No blocker issues found)
- checkov static scan: Success (All checks passed)

## Blockers
None

## Next Step
Proceed with continuous deployment and pipeline validation.
