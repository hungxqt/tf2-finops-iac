# Verification and Scanner Hardening Progress

## Status
In progress

## Scope
Fix the Terraform CI failures observed after the merged normalizer alignment work. This update focuses on the six Checkov failures from GitHub Actions run `28227058326` and confirms the current Lambda unit-test failure from run `28227178445` is already resolved on `origin/main`.

## Files Changed
- `modules/ai-runtime-lambda/main.tf`: added `create_before_destroy` lifecycle handling for the generated ACM certificate.
- `modules/lakehouse/main.tf`: disabled ACL ownership on the S3 logging target bucket with `BucketOwnerEnforced`, removed the logging bucket ACL resource, documented the SSE-S3 exception for S3 server access log delivery, and added the targeted Trivy `AWS-0132` ignore for that logging-destination encryption resource.
- `environments/sandbox/main.tf`: added an explicit replica KMS key policy and attached it to `aws_kms_key.replica`.
- `environments/staging/main.tf`: added the same explicit replica KMS key policy.
- `environments/prod/main.tf`: added the same explicit replica KMS key policy.
- `modules/orchestration/main.tf`: applied Terraform formatting required by PR CI after pulling the latest `main`.

## Validation Commands
- `python -m pytest lambda_src\tests\test_cost_puller.py::test_handle_request_remote_session_override`
- `Push-Location lambda_src; python -m pytest; Pop-Location`
- `terraform fmt modules\ai-runtime-lambda\main.tf modules\lakehouse\main.tf environments\sandbox\main.tf environments\staging\main.tf environments\prod\main.tf`
- `terraform -chdir=environments/sandbox init -backend=false`
- `terraform -chdir=environments/staging init -backend=false`
- `terraform -chdir=environments/prod init -backend=false`
- `terraform -chdir=environments/sandbox validate`
- `terraform -chdir=environments/staging validate`
- `terraform -chdir=environments/prod validate`
- `terraform fmt modules\orchestration\main.tf`
- `terraform fmt -check -recursive`
- `git diff --check`
- `trivy config --severity HIGH,CRITICAL .`
- Attempted: `python -m pip install checkov==3.2.524`

## Results
- Narrow Lambda test passed: `1 passed`.
- Full Lambda test suite passed locally: `109 passed`.
- Terraform init passed for sandbox, staging, and prod with backend disabled.
- Terraform validate passed for sandbox, staging, and prod.
- Pulled latest `origin/main` into local `main`, rebased the fix branch, and formatted `modules/orchestration/main.tf` after CI reported it.
- Added the targeted Trivy ignore for the S3 server access logging destination SSE-S3 exception after PR CI reported `AWS-0132`.
- Local Trivy passed with 0 HIGH/CRITICAL misconfigurations.
- Terraform format check passed for the full repository.
- `git diff --check`
- `trivy config --severity HIGH,CRITICAL .` passed with only line-ending warnings.
- Local Checkov verification is blocked because PyPI reset the package download connection while installing `checkov==3.2.524`.
- GitHub Actions must run the final Checkov parity check after the PR is opened.

## Blockers
- Local Checkov binary is unavailable, and `python -m pip install checkov==3.2.524` failed with `ConnectionResetError(10054)` from the package download connection.

## Next Step
Open a clean PR from `origin/main` with the Checkov-targeted Terraform fixes and let GitHub Actions confirm the Checkov scan on Ubuntu.