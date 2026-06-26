# Remove Stale Async Detection Transport Progress

## Status
Completed

## Scope
Remove legacy async detection transport including SQS `detection_queue`, `detection_dlq`, AI Worker Lambda, event-source mapping, DynamoDB `ai_results` table, and associated variables, outputs, and alarms. Ensure the system exclusively uses the approved synchronous ALB-based path.

## Files Changed
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf) (Modified)
- [environments/sandbox/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/outputs.tf) (Modified)
- [environments/sandbox/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/variables.tf) (Modified)
- [environments/sandbox/terraform.tfvars](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars) (Modified)
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example) (Modified)
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) (Modified)
- [environments/staging/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/outputs.tf) (Modified)
- [environments/staging/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/variables.tf) (Modified)
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example) (Modified)
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) (Modified)
- [environments/prod/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/outputs.tf) (Modified)
- [environments/prod/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/variables.tf) (Modified)
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example) (Modified)
- [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf) (Modified)
- [modules/ai-runtime-lambda/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/outputs.tf) (Modified)
- [modules/ai-runtime-lambda/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/variables.tf) (Modified)
- [modules/observability/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/observability/main.tf) (Modified)
- [modules/observability/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/observability/variables.tf) (Modified)
- [modules/orchestration/iam.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/iam.tf) (Modified)
- [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf) (Modified)
- [modules/orchestration/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/outputs.tf) (Modified)
- [modules/orchestration/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/variables.tf) (Modified)
- [lambda_src/tests/test_step_function_lambda_coverage.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_step_function_lambda_coverage.py) (Modified)

## Validation Commands
- `terraform -chdir=environments/sandbox plan -destroy -out sandbox-destroy.tfplan` (Success, no lifecycle blockers)
- `terraform -chdir=environments/staging validate` (Success)
- `terraform -chdir=environments/prod validate` (Success)
- `tflint --recursive` (Success, 0 warnings/errors related to modified codebase)
- `trivy config .` (Success)
- `checkov -d modules/ai-runtime-lambda -d modules/orchestration --framework terraform` (Success)
- `python -m pytest -q` (Success, 110 passed)

## Results
- Stale SQS queues (`detection_queue`, `detection_dlq`), AI Worker Lambda (along with ECR tags, mappings, log groups, and roles), and `ai_results` table configurations are completely removed.
- Validated that the synchronous ALB-based invocation pathway works correctly via the Step Function ASL parsing.
- Extended Python tests to prevent regression/reintroduction of any retired resources.

## Read-Only Doc Discrepancy
- None. `AGENTS.md`, `IMPLEMENTATION.md`, `README.md`, `README_vi.md`, `docs/GUIDES.md`, and `docs/GUIDES_vi.md` were reviewed and correctly declare that there is no detection SQS, AI worker dispatch, or DynamoDB results table polling.
