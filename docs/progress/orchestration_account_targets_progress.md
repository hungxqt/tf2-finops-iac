# Progress: Management Scheduler With Explicit Analysis Targets Plan

This progress document outlines the implementation of the explicit multi-account analysis targets plan.

## 1. Accomplishments

- **Orchestration Module Variable**: Added `analysis_target_account_ids` (`list(string)`) variable to the orchestration module.
- **Environment Integration**: Wired the variable to `var.telemetry_member_account_ids` in all root environments (`sandbox`, `staging`, `prod`).
- **Validation Resource**: Created a `terraform_data.config_validation` resource in `modules/orchestration/main.tf` to assert that scheduled executions fail validation if no analysis targets are configured.
- **EventBridge Scheduler Input**: Updated the scheduler target input block from a single executing `account_id` to:
  - `management_account_id`: Executing management/CDO account ID.
  - `analysis_targets`: Sourced from `var.analysis_target_account_ids`.
- **Nesting in State Machine**:
  - Wrapped all per-account logic inside a new sequential Map state `ProcessAnalysisTargets` (`MaxConcurrency = 1`).
  - Item selector maps `account_id` dynamically to `$$.Map.Item.Value.account_id` while preserving execution metadata (`run_id`, `correlation_id`, `cost_period`, `execution_date`, retry structures, dry-run flags).
  - Maintained anomaly-level `ProcessDetectedAnomalies` Map state nested within.
- **State Lambda Upgrades**:
  - Modified the state Lambda `prepare` handler to normalize analysis targets (handles list of strings/dicts) and validate scheduled executions.
  - Failed closed scheduled runs with missing targets via ValueError.
  - Implemented manual run fallback mapping a single `account_id` to `analysis_targets` for backward compatibility.
- **Test Hardening**:
  - Added unit tests for multi-account scheduled runs, manual fallback, and failure validation.
  - Hardened state machine ASL contract and reachability tests to check nested state routing and parameter resolution.
- **Documentation Updates**:
  - Updated `ACCOUNT_POLICY_SEEDING.md` and `GUIDES.md` to specify that operators must seed a policy row for each linked analysis account, not just the executing management account.

- **Status**: Completed / 100% Green.
- **Tests**: All 346 tests passing successfully.

## 3. Tenant Context Propagation Fix

- **Root Cause**: The step function Map state was not passing `tenant_id` down inside each item context. Consequently, states like `CheckErrorBudgetLock` (which relies on `$.tenant_id`) encountered JSONPath lookup failures because `tenant_id` was absent from the item scope, or incorrectly read from the root execution level instead of the specific linked account tenant.
- **Files Changed**:
  - `lambda_src/src/workers/state/handler.py`: Modified target normalization to inject `tenant_id` (either explicit or derived from `_default_tenant_id(account_id)`) per analysis target, and avoided broadcasting management `tenant_id` to linked accounts.
  - `modules/orchestration/statemachine.json`: Added `tenant_id.$ = $$.Map.Item.Value.tenant_id` to `ProcessAnalysisTargets.ItemSelector` and passed it to `CheckRunState`.
  - `docs/statemachine.json`: Regenerated using render script.
  - `lambda_src/tests/test_state.py` & `test_state_machine.py`: Added regression tests verifying per-account tenant isolation, manual fallback mapping, and ASL parameter resolution.
- **Validation Commands**:
  - `python scripts/render-static-asl.py`
  - `terraform fmt -check -recursive`
  - `terraform -chdir=environments/sandbox init -backend=false`
  - `Push-Location lambda_src; python -m pytest; Pop-Location`
- **Results**: All 346 tests pass successfully. Terraform validation passes. State machine JSON is rendered correctly.
- **Next Step**: Deploy changes through Terraform CI/CD to sandbox/staging/prod environments, and trigger test executions to verify end-to-end integration.

