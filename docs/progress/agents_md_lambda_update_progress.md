# AGENTS.md Lambda Container Update Progress

## Status
Completed

## Scope
Documentation-control update to AGENTS.md replacing all ECS/Fargate/ALB AI hosting instructions with Lambda container image hosting instructions. No Terraform resources or state were modified. No edits to `docs/contracts/**` or `docs/tf2-finops/**`.

Key changes:
- Replaced ECS/Fargate hosting scope with Lambda container hosting scope (`modules/ai-runtime-lambda`).
- Clarified that ECS/ALB/API Gateway wording in `docs/contracts/**` is stale transport wording.
- Named `docs/tf2-finops/01, 02, 04, 08_adrs.md` as the runtime-platform source of truth.
- Updated implementation order: `modules/ai-runtime-lambda` added as step 8, before `modules/orchestration`.
- Updated validation checks with Lambda-container-specific items (ECR digest pinning, scan-on-push, aliases, reserved concurrency, `maximum_concurrency`, KMS-encrypted logs, X-Ray, VPC private subnets).
- Updated security rules: replaced internal ALB/HTTPS endpoint rules with VPC private subnet/Lambda function URL restrictions and ECR digest pinning.
- Updated conflict handling with explicit stale-technology exclusion list and behavioral-intent preservation guidance.
- Updated AI API contract section: described direct Lambda invocation and DynamoDB getItem polling as the implementation of `/v1/detect` semantics.

## Files Changed
- Modified:
  - `AGENTS.md`

## Validation Commands
```powershell
rg -n "ECS|Fargate|ALB|EKS|Kubernetes|k8s|Argo|API Gateway" AGENTS.md
rg -n "Lambda container|Request Lambda|Worker Lambda|SQS|DLQ|DynamoDB|ECR|reserved concurrency|modules/ai-runtime-lambda" AGENTS.md
```

## Results
- Stale term check: Only references to ECS/ALB/EKS/API Gateway appear in the conflict-handling section (lines 290-292) where they are explicitly listed as **not** part of the current platform, and in security rules (line 499) prohibiting public API Gateways. No baseline AI-hosting instructions remain for those terms.
- Lambda term check: All required Lambda container responsibilities present across Repository Scope, Implementation Rules, Contract Handling, AI API Contract, Deployment/SLO, Implementation Order, Validation, and Security Rules sections.

## Blockers
None

## Next Step
No further action required for this documentation-control change. Future Terraform changes should follow the updated AGENTS.md instructions.
