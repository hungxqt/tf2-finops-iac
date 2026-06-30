# Cost Puller Telemetry Progress

## Status
Completed (Updated with Split Account Boundaries and CUR Normalization Fallback routing)

## Scope
Implement `lambda_src/src/workers/cost_puller` as the raw telemetry acquisition worker:
- Added AWS client wrappers in `finops_common` for least-privilege S3, Cost Explorer, CloudWatch, and STS.
- Implemented telemetry acquisition with CUR freshness detection and fallback to Cost Explorer daily costs when CUR is delayed > 36 hours.
- Implemented fallback to cached S3 telemetry when Cost Explorer is throttled, returning `READY` with `stale_cost_explorer = true` flag.
- Integrated best-effort CloudWatch metrics enrichment and contract-valid traffic context routing. Missing traffic metrics now lower telemetry quality instead of generating fallback traffic data.
- Fixed boto3 import issue in remote session role assumption and avoided swallowing programming errors.
- Extended IAM module and environments with optional deployable cross-account member telemetry ingestion role and trusted roles.
- Wired CUR and CE configuration variables into the `compute_lambda` Terraform module and environments.
- Implemented comprehensive unit tests for all fallback, delay, throttling, safety, and tenant-isolation validations, plus cross-account session construction and client overrides.
- Updated `normalizer` to support gzipped JSON raw envelopes and parquet curation of CUR/CE data.
- Implemented fail-closed behavior for cross-account `sts:AssumeRole` failures (preventing silent fallback to default management account credentials when remote member role assumption fails).
- Added structured `TELEMETRY_AUTH_FAILED` response details for failed cross-account role assumption (returning target_account_id, current_account_id, role_name, delayed_cur, and fail_closed = true).
- **Split Client/Session Boundaries**: Split AWS clients in `cost_puller` so that the management/payer account session is used for S3 CUR manifest and write operations, whereas the assumed member role session is used strictly for member telemetry APIs (`cloudwatch:GetMetricData` and `ce:GetCostAndUsage`).
- **Eliminated Member S3 Permissions**: Updated `member_telemetry_ingestion` IAM role policy to grant only CloudWatch and Cost Explorer access, completely removing S3 access.
- **Early Manifest & Data Verification**: Restructured `cost_puller` to perform S3 CUR manifest download, parsing, and data file metadata validations upfront. Manifest validation failures (missing files, invalid columns, legacy formats) now trigger Cost Explorer fallback instead of raising exceptions and terminating the workflow.
- **Workflow Fallback Routing**: Updated the Step Functions ASL template `modules/orchestration/statemachine.json` and `docs/statemachine.json` to catch `States.ALL` failures from the `NormalizeCostWindow` step and route them back to `IngestCostData` with a `force_ce_fallback = true` parameter, ensuring CUR normalization failures automatically route to CE fallback instead of crashing the run. Prevented infinite loops by checking `$.force_ce_fallback` first.

## Files Changed
- [lambda_src/src/finops_common/aws_clients.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/aws_clients.py)
- [lambda_src/src/finops_common/__init__.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/__init__.py)
- [lambda_src/src/workers/cost_puller/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/cost_puller/handler.py)
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py)
- [lambda_src/tests/test_cost_puller.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_cost_puller.py)
- [lambda_src/tests/test_cost_puller_cur2.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_cost_puller_cur2.py)
- [lambda_src/tests/test_normalizer.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_normalizer.py)
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf)
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)

## Validation Commands
```powershell
# Run python unit tests
Push-Location lambda_src; python -m pytest; Pop-Location

# Validate Terraform configurations
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate
```

## Results
- Pytest unit tests for all lambda workers pass cleanly (368 passed, including AssumeRole fail-closed, split boundaries, early validation, and fallback verifications).
- Terraform validation succeeds for all environments.

## Blockers
None

## Next Step
Orchestration workflow validation and Step Functions execution.
