# Orchestration Progress

## Status
Completed

## Scope
Update the Step Functions flow to match the refreshed docs/tf2-finops stash: synchronous `/v1/detect`, `/v1/decide` for action planning, `/v1/verify` for outcome verification, S3 authoritative audit, DynamoDB hot-path idempotency and rollback cache, no detection polling via `/v1/status` in ASL, and fail-closed containment. 

Specifically:
- Corrected the state machine definition and documentation to explicitly route through the VPC ALB caller helper Lambda.
- Fixed unreachable states in the ASL graph:
  - Directed `SendEscalationAlertForAnomaly` Next to `AnomalyEscalated` and Catch block to `AnomalyPlatformFailed` (preventing silent pending state for failures).
  - Added `Catch` handling to root-level SNS alert states (`SendFailClosedAlert` and `SendCURDelayAlert`) to transition to `WriteAlertDeliveryFailureAudit` upon SNS failure, making `WriteAlertDeliveryFailureAudit` reachable.
  - Changed `ProcessDetectedAnomalies` Map `Catch` transition to `WriteContainmentFailureAudit`, making `WriteContainmentFailureAudit` reachable.
- Updated python unit tests (`test_state_machine.py`, `test_step_function_payload_contract.py`) to align with the new next-state flow.
- Added a graph reachability regression test in `test_state_machine.py` to ensure all states are reachable.

## Files Changed
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [lambda_src/tests/test_state_machine.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_state_machine.py)
- [lambda_src/tests/test_step_function_payload_contract.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_step_function_payload_contract.py)

## Validation Commands
```powershell
terraform fmt -check -recursive modules/orchestration
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
Push-Location lambda_src; python -m pytest -q -p no:cacheprovider tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location
```

## Results
- `terraform fmt -check -recursive`: Success (All files properly formatted)
- `environments/sandbox validate`: Success (Configuration is valid)
- Python Lambda tests: Success (137 tests passed, including the new graph reachability regression test validating both template and mock ASL schemas)

## Blockers
None

## Next Step
Proceed with deployment or sandbox validation.
