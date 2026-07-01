# AI Engine Contract Environment Wiring Progress

## Status
Completed. Hotfix applied to remove Terraform-managed `AWS_REGION` from the AI Request Lambda environment because Lambda injects that reserved key at runtime.

## Scope
Wire the AI Engine Lambda to the environment variables defined in `deployment-contract.md` and create the feature-store DynamoDB table using the schema from `feature-store-schema.md`.
- Created `aws_dynamodb_table.feature_store` in `modules/orchestration` with partition key `resource_id` (S), sort key `date` (S), TTL `ttl_expiry`, KMS CMK encryption, and Point-In-Time-Recovery (PITR) enabled.
- Relied on Lambda-managed `AWS_REGION` and wired the non-reserved AI runtime env vars: `S3_TELEMETRY_BUCKET`, `S3_CDO_NAMESPACE`, `DYNAMODB_IDEMPOTENCY_TABLE`, `DYNAMODB_FEATURE_STORE_TABLE`, and `BEDROCK_API_KEY` (as the contract-safe Secrets Manager Bedrock secret reference).
- Added `DYNAMODB_TABLE` as compatibility alias to `DYNAMODB_IDEMPOTENCY_TABLE` for the current container image.
- Expanded AI request Lambda IAM role policy to permit:
  - `dynamodb:GetItem`, `dynamodb:PutItem`, and `dynamodb:UpdateItem` on the idempotency table.
  - `dynamodb:GetItem` and `dynamodb:Query` on the feature store table.
  - `secretsmanager:GetSecretValue` on the Bedrock secret ARN/name when configured.
- Passed parameters from environment roots (`sandbox`, `staging`, `prod`) to the AI runtime module, sourcing table names and ARNs from `module.orchestration` outputs and the bucket from `module.lakehouse.lakehouse_bucket_name`.
- Added the feature-store table ARN to the IAM module table list in all environments so that CDO workers have appropriate access.
- Documented the feature store table name mapping in bilingual developer guides.

## Table Naming Decision
Per user decision and for repository prefix consistency, the feature store table name is provisioned as `tf2-finops-{env}-feature-store` (e.g., `tf2-finops-sandbox-feature-store`). This intentionally differs from `feature-store-schema.md`'s literal name of `finops-feature-store-{env}` while preserving the identical hash/range keys, TTL behavior, and IAM access controls.

## Files Changed
- `modules/orchestration/main.tf` (Added DynamoDB feature store table resource)
- `modules/orchestration/outputs.tf` (Added outputs for feature store table name/ARN and idempotency table ARN)
- `modules/ai-runtime-lambda/variables.tf` (Added input variables for table names/ARNs, S3 telemetry bucket, CDO namespace, and Bedrock secret)
- `modules/ai-runtime-lambda/main.tf` (Added environment variables wiring and updated Lambda IAM execution policy; removed Terraform-managed reserved `AWS_REGION`)
- `modules/ai-runtime-lambda/variables.tf` (Clarified `aws_region` is for regional ARNs, not Lambda environment variables)
- `environments/sandbox/variables.tf` (Added bedrock_secret_arn variable)
- `environments/sandbox/main.tf` (Updated module.iam and module.ai_runtime_lambda parameter blocks)
- `environments/staging/variables.tf` (Added bedrock_secret_arn variable)
- `environments/staging/main.tf` (Updated module.iam and module.ai_runtime_lambda parameter blocks)
- `environments/prod/variables.tf` (Added bedrock_secret_arn variable)
- `environments/prod/main.tf` (Updated module.iam and module.ai_runtime_lambda parameter blocks)
- `docs/GUIDES.md` (Updated post-deployment documentation)
- `docs/GUIDES_vi.md` (Updated Vietnamese post-deployment documentation)
- `docs/progress/ai_engine_contract_wiring_progress.md` and `docs/progress/ai_engine_contract_wiring_progress_vi.md` (Recorded the reserved-key hotfix and validation results)

## Validation Commands
```powershell
# Hotfix checks
rg -n "AWS_REGION\s*=" modules environments .github docs/GUIDES.md docs/GUIDES_vi.md README.md
terraform fmt -check -recursive modules\ai-runtime-lambda
terraform fmt -check -recursive modules\ai-runtime-lambda modules\compute-lambda modules\orchestration modules\iam modules\networking
terraform fmt -check -recursive
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
trivy config .
checkov -d modules\ai-runtime-lambda --framework terraform
checkov -d modules\orchestration --framework terraform
tflint --recursive
git diff --check
```

## Results

- Root cause: `modules/ai-runtime-lambda/main.tf` attempted to set `AWS_REGION` in `aws_lambda_function.request.environment.variables`; AWS Lambda rejects updates that modify reserved keys.
- Remediation: removed the Terraform-managed `AWS_REGION` key and kept the `aws_region` input for regional ARN construction.
- `rg` returned no remaining Terraform assignment of `AWS_REGION = ...`.
- `terraform fmt -check -recursive` passed for the touched module, the AI integration module set, and the full repository.
- `terraform -chdir=environments/sandbox init -backend=false` initially failed under sandboxed networking, then succeeded with approved network escalation using locked providers (`aws` v5.100.0, `archive` v2.8.0, `tls` v4.3.0).
- `terraform validate` passed for `environments/sandbox`, `environments/staging`, and `environments/prod`.
- `trivy config .` exited successfully. The touched `modules/ai-runtime-lambda/main.tf` target had 0 misconfigurations; Trivy still reports unrelated existing S3/logging findings in bootstrap, environment replica buckets, dashboard/lakehouse logging buckets, and `images-test/Dockerfile`.
- `checkov -d modules\ai-runtime-lambda --framework terraform` passed with 59 passed checks, 0 failed, 7 skipped.
- `checkov -d modules\orchestration --framework terraform` passed with 95 passed checks, 0 failed, 2 skipped.
- `tflint --recursive` still reports unrelated existing dashboard warnings: missing `archive` provider constraint and unused `auth_cookie_ttl` / `auth_session_ttl`.
- `git diff --check` passed.

## Blockers

- No blocker for this hotfix. Staging/prod `terraform init -backend=false` refresh under sandboxed network failed, and the escalation retry was rejected by the approval system usage limit, but both roots validated successfully using existing local initialization.

## Next Step

- Re-run the sandbox Terraform apply that failed with `InvalidParameterValueException`.
