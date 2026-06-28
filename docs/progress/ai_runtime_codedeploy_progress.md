# AI Runtime Lambda CodeDeploy Progress

## Status
Completed

## Scope
Add CodeDeploy-controlled linear rollout for the AI Engine Request Lambda in `modules/ai-runtime-lambda`, scoped initially to the `sandbox` environment:
- Added `aws_codedeploy_app` with `compute_platform = "Lambda"`.
- Added CodeDeploy IAM service role with `AWSCodeDeployRoleForLambda` managed policy.
- Added `aws_codedeploy_deployment_group` supporting dynamic configuration.
- Configured 4 automated CloudWatch rollback alarms (Errors, Throttles, P99 Duration > 800ms, and ALB target 5xx).
- Updated Lambda alias to ignore version/routing drift to let CodeDeploy manage the traffic.
- Added module input variables and outputs for CodeDeploy configuration.
- Wired CodeDeploy into `environments/sandbox/main.tf` with a 10% per 1-minute linear strategy and engineering SNS topic.
- Created `scripts/start-ai-lambda-codedeploy.ps1` to orchestrate AppSpec generation, trigger, poll, and wait for CodeDeploy.
- Updated GitHub Actions workflows (`sandbox-deploy.yml` and `terraform-apply.yml`) to support plan/apply separation and automatic CodeDeploy traffic shifting.
- Added unit tests in `lambda_src/tests/test_ai_runtime_codedeploy.py` verifying Terraform configurations.

## Files Changed
- Created:
  - `lambda_src/tests/test_ai_runtime_codedeploy.py`
  - `scripts/start-ai-lambda-codedeploy.ps1`
  - `.github/workflows/sandbox-deploy.yml`
- Modified:
  - `modules/ai-runtime-lambda/main.tf`
  - `modules/ai-runtime-lambda/variables.tf`
  - `modules/ai-runtime-lambda/outputs.tf`
  - `environments/sandbox/main.tf`
  - `environments/sandbox/outputs.tf`
  - `environments/staging/outputs.tf`
  - `environments/prod/outputs.tf`
  - `.github/workflows/terraform-apply.yml`
  - `docs/GUIDES.md`
  - `docs/GUIDES_vi.md`

## Validation Commands
```powershell
terraform fmt -check -recursive
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/sandbox plan -destroy -out sandbox-destroy.tfplan
Push-Location lambda_src; python -m pytest tests/test_ai_runtime_codedeploy.py; Pop-Location
trivy config .
checkov -d modules/ai-runtime-lambda -d environments/sandbox --framework terraform
```

## Results
- `terraform fmt -check -recursive`: Success
- `environments/sandbox init`: Success
- `environments/sandbox validate`: Success
- `environments/sandbox plan -destroy`: Success
- Python Lambda tests: Success (7/7 tests passed in `test_ai_runtime_codedeploy.py`)
- Trivy config scan: Success
- Checkov scan: Success (All checks passed)

## Blockers
None

## Next Step
Execute sandbox release pipeline using non-production image digest to verify E2E CodeDeploy traffic shift and automated rollback logic.
