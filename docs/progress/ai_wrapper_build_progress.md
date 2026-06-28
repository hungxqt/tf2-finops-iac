# CodeBuild Wrapper Image Publish Progress

## Status
Completed (standalone `codebuild/` root managing a single shared CodeBuild project and target ECR repository successfully implemented and validated).

## Scope
Introduce a standalone Terraform-managed CodeBuild root (`codebuild/`) to build and publish the Lambda Web Adapter wrapper image:
- Created a top-level `codebuild/` Terraform root containing exactly one shared CodeBuild project (`tf2-finops-ai-wrapper-build`), one CodeBuild IAM role/policy, one CodeBuild log group, and one target ECR repository (`tf2-finops-ai-wrapper`) shared across all environments.
- Refactored `modules/ai-wrapper-build` to fully own ECR repository creation, repository policies, CodeBuild projects, IAM roles, log groups, buildspecs, and SSM Parameter Store updates.
- Refactored `modules/ai-runtime-lambda` to remove all ECR repository creation, keeping it focused on Lambda runtime deployment (via `var.request_image_uri`) and version promotion.
- Cleaned up environment roots (`environments/sandbox`, `environments/staging`, `environments/prod`) by removing all wrapper build module declarations, inputs, and outputs.
- Structured the buildspec to validate that `UPSTREAM_IMAGE_URI` is digest-pinned, login to registries, skip rebuilding dynamically if the deterministic tag (`wrapped-<upstream-digest-short>`) is present in target ECR, and write output URIs to a shared SSM Parameter (`/tf2-finops/shared/ai-wrapper/latest-image-uri` and `/tf2-finops/shared/ai-wrapper/latest-upstream-image-uri`).
- Updated operator guides in English (`docs/GUIDES.md`) and Vietnamese (`docs/GUIDES_vi.md`) detailing the updated deployment order.

## Files Changed
- `modules/ai-runtime-lambda/main.tf`
- `modules/ai-runtime-lambda/outputs.tf`
- `modules/ai-wrapper-build/main.tf`
- `modules/ai-wrapper-build/variables.tf`
- `modules/ai-wrapper-build/outputs.tf`
- `codebuild/main.tf`
- `codebuild/variables.tf`
- `codebuild/outputs.tf`
- `codebuild/versions.tf`
- `codebuild/providers.tf`
- `codebuild/backend.tf`
- `codebuild/README.md`
- `environments/sandbox/variables.tf`
- `environments/sandbox/main.tf`
- `environments/sandbox/outputs.tf`
- `environments/staging/variables.tf`
- `environments/staging/main.tf`
- `environments/staging/outputs.tf`
- `environments/prod/variables.tf`
- `environments/prod/main.tf`
- `environments/prod/outputs.tf`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`
- `docs/progress/ai_wrapper_build_progress.md`
- `docs/progress/ai_wrapper_build_progress_vi.md`

## Validation Commands
```powershell
# Format check
terraform fmt -recursive

# Validate codebuild root
terraform -chdir=codebuild init -backend=false
terraform -chdir=codebuild validate

# Validate environments
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate

# Run Trivy and Checkov static analysis
trivy config .
checkov -d codebuild -d modules/ai-wrapper-build -d modules/ai-runtime-lambda --framework terraform
```

## Results
- `terraform fmt -recursive`: Success (no formatting issues).
- `terraform validate` (codebuild/sandbox/staging/prod): Success (all roots validate successfully).
- Static Analysis (Trivy/Checkov): Success (all new resources scanned and compliant).

## Blockers
None.

## Next Step
Trigger manual CodeBuild wrapper builds using the CLI.
