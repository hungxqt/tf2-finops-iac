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

## 2. Status

- **Status**: Completed / 100% Green.
- **Tests**: All 341 tests passing successfully.
