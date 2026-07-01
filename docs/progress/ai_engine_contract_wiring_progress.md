# AI Engine Contract Environment Wiring Progress

## Status
Completed (all variables, table resources, IAM permissions, and environments successfully updated and validated).

## Scope
Wire the AI Engine Lambda to the environment variables defined in `deployment-contract.md` and create the feature-store DynamoDB table using the schema from `feature-store-schema.md`.
- Created `aws_dynamodb_table.feature_store` in `modules/orchestration` with partition key `resource_id` (S), sort key `date` (S), TTL `ttl_expiry`, KMS CMK encryption, and Point-In-Time-Recovery (PITR) enabled.
- Wired AI runtime env vars: `AWS_REGION`, `S3_TELEMETRY_BUCKET`, `S3_CDO_NAMESPACE`, `DYNAMODB_IDEMPOTENCY_TABLE`, `DYNAMODB_FEATURE_STORE_TABLE`, and `BEDROCK_API_KEY` (as the contract-safe Secrets Manager Bedrock secret reference).
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
- `modules/ai-runtime-lambda/main.tf` (Added environment variables wiring and updated Lambda IAM execution policy)
- `environments/sandbox/variables.tf` (Added bedrock_secret_arn variable)
- `environments/sandbox/main.tf` (Updated module.iam and module.ai_runtime_lambda parameter blocks)
- `environments/staging/variables.tf` (Added bedrock_secret_arn variable)
- `environments/staging/main.tf` (Updated module.iam and module.ai_runtime_lambda parameter blocks)
- `environments/prod/variables.tf` (Added bedrock_secret_arn variable)
- `environments/prod/main.tf` (Updated module.iam and module.ai_runtime_lambda parameter blocks)
- `docs/GUIDES.md` (Updated post-deployment documentation)
- `docs/GUIDES_vi.md` (Updated Vietnamese post-deployment documentation)

## Validation Commands
```powershell
# Format check
terraform fmt -check -recursive

# Validate configurations in each environment root
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate

terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate

terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Verify plan generation (sandbox destroy dry run)
terraform -chdir=environments/sandbox plan -destroy -out=sandbox-destroy.tfplan
```
