# Orchestration Progress

## Status
Completed

## Scope
Update the Step Functions flow to match the refreshed docs/tf2-finops stash: synchronous `/v1/detect`, `/v1/decide` for action planning, `/v1/verify` for outcome verification, S3 authoritative audit, DynamoDB hot-path idempotency and rollback cache, no detection polling via `/v1/status` in ASL, and fail-closed containment. 

Specifically, corrected the state machine definition and documentation to explicitly route through the VPC ALB caller helper Lambda:
- Step Functions -> VpcAlbCallerLambda -> HTTPS private internal ALB -> AI Engine Request Lambda
- Renamed `${ai_request_lambda_arn}` template placeholder to `${vpc_alb_caller_lambda_arn}` in `InvokeDetect`, `InvokeDecide`, and `ReportVerifyResult` states.
- Added explanatory comments inside target states describing the ALB routing.
- Removed unused direct `ai_request` mapping from environment `lambda_function_arns` variables so Step Functions only receives permissions for the VPC ALB caller helper.
- Updated python unit tests and rendering script to assert and verify the correct structure.

## Files Changed
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf)
- [modules/orchestration/iam.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/iam.tf)
- [modules/orchestration/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/outputs.tf)
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf)
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf)
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf)
- [scripts/render-static-asl.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/render-static-asl.py)
- [lambda_src/tests/test_state_machine.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_state_machine.py)
- [lambda_src/tests/test_step_function_lambda_coverage.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_step_function_lambda_coverage.py)

## Validation Commands
```powershell
terraform fmt -check -recursive
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
python scripts/render-static-asl.py
Push-Location lambda_src; python -m pytest; Pop-Location
```

## Results
- `terraform fmt -check -recursive`: Success (All files properly formatted)
- `environments/sandbox validate`: Success (Configuration is valid)
- Python Lambda tests: Success (All 40 tests passed, including state machine and lambda coverage checks verifying the VPC ALB caller flow)
- Checkov scan: Passed successfully (All standard policies verified)

## Blockers
None

## Next Step
Proceed with deployment or sandbox validation.
