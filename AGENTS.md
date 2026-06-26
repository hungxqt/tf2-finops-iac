# AGENTS.md - TF2 FinOps IaC Implementation Guide

## Purpose

This repository is the Terraform infrastructure-as-code home for **Task Force 2 - FinOps Watch**. Agents working here must implement AWS platform infrastructure according to the repository skeleton below, the current scenario documented in `../tf2-finops-docs`, the task plan in `IMPLEMENTATION.md`, the read-only architecture documents in `tf2-finops-docs`, and the API, telemetry, deployment, SLO, and security contracts in `docs/contracts`.

This file is authoritative for implementation agents. When instructions conflict, follow this priority order:

1. Explicit user instructions in the current conversation.
2. This `AGENTS.md`.
3. Scenario authority from `../tf2-finops-docs/AGENTS.md`, `../tf2-finops-docs/TF2_FINOPS_LEARNER.md`, and `../tf2-finops-docs/docs/tf2-finops/`.
4. Contract authority from `./docs/contracts/`.
5. `IMPLEMENTATION.md`.
6. `README.md`.
7. Read-only reference documents under `./docs/tf2-finops/`.

If `IMPLEMENTATION.md`, `README.md`, `./docs/contracts/`, or `./docs/tf2-finops/` contain runtime-platform or application-deployment wording that conflicts with this file or explicit user scope, preserve the platform-neutral requirements from those documents, keep this repo focused on Terraform-owned AWS platform infrastructure, Lambda container runtime infrastructure, and CDO workflow integration.

## Repository Scope

This repo owns:

- Terraform modules and environment roots for sandbox, staging, and production.
- Remote state bootstrap, locking, and CI plan/apply controls.
- AWS cost-data platform resources: S3 raw/curated/audit zones, Glue Data Catalog, Athena workgroup, and related KMS keys.
- Scheduled workflow resources: EventBridge Scheduler, Step Functions Standard, Lambda workers, and DynamoDB run-state tables.
- Lambda container AI hosting infrastructure: `modules/ai-runtime-lambda` providing ECR repository (digest-pinned images, scan-on-push), AI Engine Request Lambda and Worker Lambda (`package_type = "Image"`), Lambda aliases/versions, reserved concurrency and optional provisioned concurrency, SQS event source mapping, KMS-encrypted CloudWatch log groups, and X-Ray tracing.
- Finance and Engineering alert routing, dashboard infrastructure hooks, containment audit records, and operational observability.
- Least-privilege IAM roles for CDO workflow execution, read-only cost ingestion, Lambda VPC-endpoint access, and tightly scoped non-prod containment.
- AI Engine integration infrastructure: Step Functions direct Lambda invocation, SQS detection queue and DLQ, DynamoDB result/idempotency/state/error-budget tables, S3 evidence/checkpoint paths, IAM SigV4 authentication, timeout/retry/circuit-breaker settings, unavailable-AI fallback wiring, and audit storage paths.
- Contract implementation scaffolding for API integration, telemetry collection/normalization, SLO monitoring, queue/state infrastructure, deployment gates, and security guardrails described under `docs/contracts`.

This repo does not own:

- AI model code, anomaly detection internals, training algorithms, retraining logic, explanation logic, model versions, confidence scoring, or backtest implementation.
- AI Engine runtime application code (e.g. internal service business logic or Python models) or application desired state definitions outside of the Lambda function/image configuration provisioned in modules/ai-runtime-lambda.
- Business documentation or design-doc rewrites.

## Required Repository Skeleton

Agents must create and maintain this structure. Do not create alternate top-level folders or rename modules unless the user explicitly updates the plan.

```text
tf2-finops-iac/
├── .github/
│   └── workflows/
│       ├── terraform-ci.yml
│       ├── terraform-apply.yml
│       └── drift-detection.yml
├── bootstrap/
│   ├── README.md
│   ├── backend.tf
│   ├── locals.tf
│   ├── main.tf
│   ├── outputs.tf
│   ├── providers.tf
│   ├── variables.tf
│   └── versions.tf
├── environments/
│   ├── sandbox/
│   │   ├── README.md
│   │   ├── backend.tf
│   │   ├── locals.tf
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── terraform.tfvars.example
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── staging/
│   │   ├── README.md
│   │   ├── backend.tf
│   │   ├── locals.tf
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── terraform.tfvars.example
│   │   ├── variables.tf
│   │   └── versions.tf
│   └── prod/
│       ├── README.md
│       ├── backend.tf
│       ├── locals.tf
│       ├── main.tf
│       ├── outputs.tf
│       ├── providers.tf
│       ├── terraform.tfvars.example
│       ├── variables.tf
│       └── versions.tf
├── lambda_src/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── src/
│   │   ├── finops_common/
│   │   │   ├── __init__.py
│   │   │   ├── aws_clients.py
│   │   │   ├── event.py
│   │   │   └── utils.py
│   │   └── workers/
│   │       ├── __init__.py
│   │       ├── ai_client/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── audit_writer/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── containment_worker/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── cost_puller/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── normalizer/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       └── router/
│   │           ├── __init__.py
│   │           └── handler.py
│   └── tests/
│       ├── conftest.py
│       ├── test_ai_client.py
│       ├── test_audit_writer.py
│       ├── test_containment_worker.py
│       ├── test_cost_puller.py
│       ├── test_finops_common.py
│       ├── test_normalizer.py
│       ├── test_router.py
│       └── test_state.py
├── modules/
│   ├── ai-runtime-lambda/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── alerting/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── compute-lambda/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── dashboard/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── iam/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── lakehouse/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── networking/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   ├── observability/
│   │   ├── README.md
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── variables.tf
│   │   └── versions.tf
│   └── orchestration/
│       ├── README.md
│       ├── main.tf
│       ├── outputs.tf
│       ├── variables.tf
│       └── versions.tf
├── docs/
│   ├── contracts/
│   │   ├── ai-api-contract.md
│   │   ├── deployment-contract.md
│   │   └── telemetry-contract.md
│   ├── GUIDES.md
│   ├── GUIDES_vi.md
│   ├── SKELETON.md
│   ├── SKELETON_vi.md
│   ├── progress/
│   └── tf2-finops/
│       ├── 01_requirements_analysis.md
│       ├── 02_infra_design.md
│       ├── 03_security_design.md
│       └── 04_deployment_design.md
├── scripts/
│   ├── validate.ps1
│   └── package-lambdas.ps1
├── .gitignore
├── .pre-commit-config.yaml
├── .terraform-version
├── .tflint.hcl
├── AGENTS.md
├── IMPLEMENTATION.md
├── Makefile
└── README.md
```

## Implementation Rules

- Read `IMPLEMENTATION.md` before creating or modifying implementation files.
- Follow the module contracts and task order in `IMPLEMENTATION.md` only when they do not contradict this file or the current `../tf2-finops-docs` scenario.
- Read the matching file under `docs/contracts/` before changing any Terraform, Lambda, CI, deployment, telemetry, SLO, or AI integration behavior covered by that contract.
- Treat `docs/contracts/ai-api-contract.md`, `docs/contracts/telemetry-contract.md`, and `docs/contracts/deployment-contract.md` as implementation contracts for behavior and controls, not as permission to move AI model code, runtime deployment descriptors, or application desired state into this repo.
- Use Terraform as the platform IaC tool for AWS infrastructure. Do not replace the platform design with AWS SAM, CDK, CloudFormation, Pulumi, or application deployment definitions.
- Keep each module focused on one responsibility. Do not create a single large module that owns all resources.
- Keep environment-specific values in `environments/*`. Do not hardcode sandbox, staging, or prod choices inside reusable modules.
- Use `terraform.tfvars.example` for examples only. Do not commit real `.tfvars`.
- Use S3 backend with `use_lockfile = true` for long-lived state. Do not add a DynamoDB lock table for new state.
- Keep GitHub Actions authentication keyless through OIDC. Do not add static AWS credentials to workflow files.
- Use reviewed plan artifacts for apply workflows. Do not re-run `terraform plan` inside apply jobs.
- Drift detection must alert or open an issue. It must not auto-apply changes.
- Keep Lambda worker code minimal, deployable, contract-validating, and safe by default.
- Use Lambda for short CDO adapters and policy workers, and host the AIOps-provided AI Engine runtime using the AWS Lambda container platform infrastructure provisioned in modules/ai-runtime-lambda.
- Configure AI Engine integration through versioned contract inputs: contract version, AI Engine Request Lambda ARN, IAM SigV4 authentication, required tenant/idempotency/correlation headers, timeout, retry policy, circuit-breaker behavior, DynamoDB result-polling behavior, and fail-closed fallback behavior.
- The default AI Engine execution path is: Step Functions → AI Engine Request Lambda (direct invocation) → SQS detection queue → AI Engine Worker Lambda (event source mapping) → DynamoDB results table / S3 evidence → Step Functions (direct DynamoDB getItem polling).
- If the AI Engine is unavailable, fails schema validation, times out, returns a cross-tenant result, exceeds rate limits, or returns an unsafe recommendation, fail closed for containment: do not apply automatic containment, alert operators through the static/rule-based fallback path where applicable, preserve run state, and write an audit record.
- Use CDO as the telemetry source of truth. AI Engine components must not directly pull CDO-owned Cost Explorer, CUR, CloudWatch, Athena, Glue, or containment-state data unless a user explicitly changes the ownership boundary.
- Reusable modules must support `destroyable = true` for sandbox teardown, but default to protected behavior (`destroyable = false`) for staging/prod.
- Use static destroy guard resources (such as `terraform_data.destroy_guard` with `count = var.destroyable ? 0 : 1` and static `lifecycle { prevent_destroy = true }`) for non-sandbox environments. Do not put unconditional `prevent_destroy` on shared module resources that sandbox must destroy.
- Configure S3 bucket `force_destroy = var.destroyable` for logging, lakehouse, audit, dashboard data, and replica buckets.
- Configure ECR repository `force_delete = var.destroyable` and KMS key `deletion_window_in_days = var.destroyable ? 7 : 30` to permit sandbox teardown.
- Staging and production state, audit, lakehouse, KMS, and core DynamoDB resources must remain protected from accidental teardowns via the static destroy guard sentinel resources when `destroyable = false`.

## Read-Only Documentation Sources

These files are reference material for implementation. Agents must read them when the implementation touches matching behavior, but must not edit them unless the user explicitly asks for documentation changes.

### In-repo references (`./docs/tf2-finops/`)

- `./docs/tf2-finops/01_requirements_analysis.md`
- `./docs/tf2-finops/02_infra_design.md`
- `./docs/tf2-finops/03_security_design.md`
- `./docs/tf2-finops/04_deployment_design.md`
- `./docs/tf2-finops/05_cost_analysis.md`
- `./docs/tf2-finops/06_dashboard_alerting_design.md`
- `./docs/tf2-finops/07_test_eval_report.md`
- `./docs/tf2-finops/08_adrs.md`
- `./docs/tf2-finops/09_demo_and_presentation_pack.md`

### Contract references (`./docs/contracts/`)

- `./docs/contracts/ai-api-contract.md`
- `./docs/contracts/deployment-contract.md`
- `./docs/contracts/telemetry-contract.md`

### External repo references (`../tf2-finops-docs/`)

- `../tf2-finops-docs/AGENTS.md`
- `../tf2-finops-docs/TF2_FINOPS_LEARNER.md`
- `../tf2-finops-docs/docs/tf2-finops/01_requirements_analysis.md`
- `../tf2-finops-docs/docs/tf2-finops/01_requirements_analysis_vi.md`
- `../tf2-finops-docs/docs/tf2-finops/02_infra_design.md`
- `../tf2-finops-docs/docs/tf2-finops/02_infra_design_vi.md`
- `../tf2-finops-docs/docs/tf2-finops/03_security_design.md`
- `../tf2-finops-docs/docs/tf2-finops/03_security_design_vi.md`
- `../tf2-finops-docs/docs/tf2-finops/04_deployment_design.md`
- `../tf2-finops-docs/docs/tf2-finops/04_deployment_design_vi.md`

Never edit or overwrite:

- `./docs/tf2-finops/**`
- `./docs/contracts/**`

If implementation progress reveals that a design document is stale, record the discrepancy in `docs/progress/` and mention it in the final response. Do not patch the docs repo.

## Contract-Driven Implementation

Agents must use `docs/contracts/` as the behavior contract layer for implementation details that are more specific than the high-level architecture documents.

### Required contract reads

- Read `docs/contracts/ai-api-contract.md` before changing `lambda_src/src/workers/ai_client/**`, `modules/compute-lambda`, `modules/ai-runtime-lambda`, `modules/orchestration`, AI Engine Lambda variables, Step Functions AI states, DynamoDB result-polling states, dashboard actions that poll AI results, or tests for AI integration.
- Read `docs/contracts/telemetry-contract.md` before changing `lambda_src/src/workers/cost_puller/**`, `lambda_src/src/workers/normalizer/**`, `modules/lakehouse`, Glue/Athena resources, telemetry schemas, cost-data prefixes, S3 pointer behavior, tenant context, idempotency, quality scoring, or tests for ingestion/normalization.
- Read `docs/contracts/deployment-contract.md` before changing `modules/networking`, `modules/iam`, `modules/ai-runtime-lambda`, `modules/orchestration`, `modules/observability`, queue/DLQ resources, CI deployment gates, canary/rollback controls, or security scans.

### Conflict handling

- `AGENTS.md` and explicit user instructions decide repository ownership and platform target. Future implementation agents must follow the active `docs/tf2-finops` architecture, which describes the AI Engine integration via a private internal HTTPS ALB.
- The active, approved AI Engine integration path is: `Step Functions` -> `VpcAlbCallerLambda` -> `private internal ALB` -> `AI Request Lambda (live alias)`.
- AGENTS.md must enforce repository safety and implementation rules, but must not contradict active `docs/tf2-finops` architecture or `docs/contracts`.
- ECS Cluster, Fargate/Fargate Spot capacity providers, Private API Gateway, EKS, Kubernetes, and Argo CD are **not** part of the active AI hosting platform. Any references to these in `docs/contracts/**` or older ADRs are stale or superseded transport wording.
- Where contracts or design documents mention transport mechanisms like ECS Fargate clusters or Private API Gateways, these are treated as stale or superseded transport names. The physical private internal ALB is active, and it is the physical integration target of the `VpcAlbCallerLambda`.
- Specifically, the logical HTTPS `/v1/*` endpoints are mapped to standard Lambda target group invocations via the internal ALB, keeping the API contract behaviorally compatible.

### AI API contract requirements

- AI integration requires implementing these logical operations: `/v1/detect`, `/v1/decide`, `/v1/verify`, `/v1/status/{id}` (for remediation/self-healing status only), `/v1/audit/{audit_id}/rollback` (for result notification), and `/health`.
- Step Functions invokes the `VpcAlbCallerLambda` with the target path (e.g. `/v1/detect`), which forwards the request to the internal HTTPS ALB, which in turn invokes the AI Engine Request Lambda live alias. The logical `/v1/detect` submission and result polling contracts are fully preserved.
- AI Engine calls must require secure context headers: `Content-Type`, `Accept`, `X-Tenant-Id` (tenant isolation), `X-Idempotency-Key` (idempotency check), `X-Correlation-Id` (correlation ID), `X-Payload-SHA256` (payload hash), `X-Request-Timestamp` (request timestamp), and `X-Dry-Run-Mode` (dry-run mode). Communication is secured via AWS IAM SigV4 (`Authorization`).
- Do not use static API keys or bearer tokens as the long-term authentication design. If placeholder secret material exists for local tests, keep it non-production, non-real, and document it as a stub.
- Support both `RAW_JSON` and `S3_POINTER` ingestion modes at the CDO/AI boundary. CUR/Data Exports via `S3_POINTER` is the default ingestion mode; Cost Explorer daily data via `RAW_JSON` is the fallback mode when CUR delay is detected (delayed > 36 hours).
- Handle AI API error codes defensively: invalid schema, idempotency mismatch, auth failure, cross-tenant denial, not found, duplicate in progress, rollback unsupported, rate limiting, model timeout, and service down must not trigger automatic containment.
- SQS/DLQ queues are used strictly for alert retry and audit notification buffers (`finops-watch-rollback`) unless a contract explicitly adds another queue use.

### Telemetry contract requirements

- CDO pulls and normalizes AWS telemetry from CUR or AWS Data Exports in S3, Cost Explorer, and CloudWatch. AI Engine must consume normalized CDO payloads or S3 pointers, not independently call AWS telemetry APIs.
- Normalized payloads must carry tenant context, account context, correlation ID, idempotency key, source timestamps, request timestamp, payload hash, schema version, and quality/freshness/integrity fields when those features are implemented.
- `cost_puller` owns raw telemetry acquisition. `normalizer` owns schema validation, field normalization, S3 raw-to-curated transformation, partition conventions, quality scoring, and Glue/Athena readiness hooks.
- Preserve untagged spend signals instead of dropping incomplete ownership fields. Missing owner/team/cost-center tags are a Finance escalation signal.
- If CUR is delayed, CloudWatch is missing, Cost Explorer is stale, data is estimated, or telemetry completeness is below the contract threshold, the workflow must degrade to dry-run/alert-only containment and write audit evidence.

### Storage and State Policy

- **Idempotency Hot Path**: DynamoDB `finops-idempotency-{env}` is the hot path for idempotency validation (keyed on composite key with a 24-hour TTL (`ttl_expiry`)).
- **Durable Audit Trail**: S3 with Object Lock (compliance mode) remains the authoritative evidence store for audit and telemetry retention, and must retain containment logs for at least 90 days.
  - **Object Lock Sandbox Teardown Caveat**: Compliance-mode retained S3 objects cannot be destroyed until retention expires, so sandbox audit buckets must avoid Compliance retention if full teardown is required. Staging and production audit buckets must retain the mandatory 90-day compliance-mode Object Lock.
- **Rollback Caching**: DynamoDB `finops-rollback-cache` stores the `rollback_payload.boto3_equivalent` cached from `/v1/decide` for 90 days (backed by Object Lock S3 copies).
- **Rollback Execution**: CDO workers execute rollbacks directly using the cached Boto3 payload from `finops-rollback-cache` (enabling independent execution even when the AI Engine is offline). The SQS queue `finops-watch-rollback` is for audit completion notification only, not rollback command dispatch.

### Dashboard and Presentation Policy

- **Dashboard Target**: The dashboard is hosted as static assets in S3, delivered via CloudFront, and authenticated by Cognito user/identity pools.
- **Finance Usability**: The dashboard must support finance-readable, SQL-free views (reading from DynamoDB dashboard read-caches). QuickSight remains an optional/future BI integration.

### Deployment, SLO, and telemetry operations

- AI Engine integration infrastructure must use private networking: Lambda functions execute in VPC private subnets with VPC Interface endpoints (SQS, DynamoDB, S3 Gateway, KMS, Secrets Manager, CloudWatch Logs, X-Ray). Observable through CloudWatch Logs, CloudWatch Metrics, and X-Ray tracing.
- Artifact guidance must prefer immutable references, signed artifacts where available, SBOM/provenance evidence where available, and blocking critical findings unless the user records an accepted capstone exception.
- If implementing async queues, create a primary detection queue, DLQ, and rollback/status queue under `modules/orchestration`; keep queue retention, visibility timeout, poison-message threshold, and encryption aligned with the deployment contract.
- Observability must cover the contract SLOs where infrastructure can measure them: AI API availability, 5xx/error rate, timeout count, result-polling failures, workflow failure, stale telemetry over 26h, ingestion freshness, containment/rollback failure, budget circuit breaker state, and error-budget lock state.
- Deployment gates must include Terraform fmt/validate, TFLint, Trivy, Checkov, Lambda tests, AI contract compatibility checks where available, artifact review, reviewed plan artifacts for apply, and prod environment approval.

## FinOps Watch Guardrails

All implementation must preserve these hard requirements:

- AWS only.
- Synthetic data unless real billing access is explicitly provided.
- Default cadence is 24h unless the user changes the approved design.
- The scenario architecture is lakehouse-centric FinOps control plane with serverless orchestration and AIOps-owned AI Engine integration.
- CDO owns cost ingestion, normalized cost windows, ownership/tag metadata, scheduling, idempotency, workflow state, dashboard views, alert routing, containment guardrails, audit logs, platform SLOs, and AI Engine integration platform hooks.
- AIOps owns anomaly detection logic, model selection, training/retraining design, model versioning, confidence scoring, classification, explanation text, AI Engine code/model internals, and backtest metrics.
- Finance and Engineering alert routing must remain separate.
- Dashboard infrastructure must support finance-readable views and must not require Finance users to know SQL.
- Containment must be dry-run first.
- Production containment is tag, suggest, or dry-run only.
- Audit records must capture actor, timestamp, correlation ID, idempotency key, anomaly ID, target owner, before state, proposed or applied after state, execution mode, rollback path, approval status, retention location, and retention period.
- Audit retention must be at least 90 days.
  - **Sandbox Exception**: Sandbox contains synthetic/non-production data and may use teardown-compatible retention settings; staging/prod must preserve audit/state/lakehouse/KMS/DynamoDB protection.
- Automated containment must **NEVER terminate prod, delete data, or modify IAM**.
- Every AI request and telemetry payload must preserve tenant isolation, account context, idempotency, correlation ID, and contract/schema version.
- Telemetry quality failures, stale Cost Explorer data, delayed CUR data, missing CloudWatch metrics, estimated billing data, and low completeness scores must force dry-run or alert-only containment.
- SLO and circuit-breaker state must be observable. Budget guardrails, AI error rate, timeout rate, and containment error-budget locks must never silently fail open.

## Required Implementation Order

Use this order unless the user asks for a smaller scoped change:

1. Baseline repository hygiene and validation scripts.
2. `bootstrap/` state backend and GitHub OIDC.
3. `lambda_src/` worker stubs and tests.
4. `modules/networking`.
5. `modules/lakehouse`.
6. Base `modules/iam` roles and policies needed by networking, lakehouse, Lambda, and orchestration.
7. `modules/compute-lambda`.
8. `modules/ai-runtime-lambda` (ECR repository, AI Engine Request Lambda, AI Engine Worker Lambda, Lambda aliases/versions, reserved concurrency, SQS event source mapping, KMS-encrypted log groups, X-Ray).
9. `modules/orchestration`, including SQS detection queue/DLQ/rollback-status queue, DynamoDB run-state/error-budget/idempotency/ai-results tables, Step Functions state machine wiring with direct Lambda invocation and direct DynamoDB result polling, telemetry quality branching, circuit-breaker state, and fail-closed behavior.
10. `modules/alerting`, `modules/observability`, and `modules/dashboard`.
11. `environments/sandbox`, `environments/staging`, and `environments/prod`.
12. GitHub Actions workflows.
13. Final validation and progress documentation.

When working on a single feature, update only the relevant module, environment root, tests, and progress files.

## Progress Tracking

Agents must record feature and function progress under:

```text
tf2-finops-iac/docs/progress/
```

For each feature or function, create or update a paired English and Vietnamese progress file:

```text
docs/progress/<feature-name>_progress.md
docs/progress/<feature-name>_progress_vi.md
```

Examples:

```text
docs/progress/networking_progress.md
docs/progress/networking_progress_vi.md
docs/progress/lakehouse_progress.md
docs/progress/lakehouse_progress_vi.md
docs/progress/orchestration_progress.md
docs/progress/orchestration_progress_vi.md
```

Both files must contain the same facts and section order. Use this section structure:

```markdown
# <Feature Name> Progress

## Status

## Scope

## Files Changed

## Validation Commands

## Results

## Blockers

## Next Step
```

For Vietnamese files, use this equivalent structure and keep technical names in English:

```markdown
# Tiến độ <Feature Name>

## Trạng thái

## Phạm vi

## Các file đã thay đổi

## Lệnh kiểm tra

## Kết quả

## Vướng mắc

## Bước tiếp theo
```

Progress files must be factual. Do not claim a module is complete until validation for that module has run or the reason validation could not run is recorded.

## Guide Maintenance

Agents must keep `docs/GUIDES.md` and `docs/GUIDES_vi.md` current whenever they add or change a developer/operator workflow, command sequence, validation path, script, CI job, deployment step, or handoff procedure.

- Update both `docs/GUIDES.md` and `docs/GUIDES_vi.md` in the same change whenever a new working flow is added, an existing flow changes, or sandbox destroy workflow commands change.
- A "working flow" includes bootstrap, backend migration, Lambda packaging/testing, Terraform init/validate/plan/apply, environment deployment, drift detection, security scans, CI jobs, sandbox destroy plans, Makefile/script usage, AI Engine integration handoff, and any new required manual operator step.
- Do not update guides for purely internal implementation changes that do not change commands, order of operations, prerequisites, or operator/developer behavior.
- If no guide update is needed, the final response must explicitly say `No guide impact` with a short explanation.
- Keep `docs/GUIDES.md` and `docs/GUIDES_vi.md` factually equivalent, with the same section order and command blocks. Translate prose in Vietnamese, but keep technical names, commands, file paths, and AWS service names in English.
- If a new flow is planned but not validated, document it as planned or blocked, not as a completed workflow.

## Validation Requirements

Run the narrowest relevant validation after each meaningful change. Before calling a task complete, run the broad validation set when the files exist. In particular, verify sandbox destroyability using the sandbox destroy-plan check (`terraform -chdir=environments/sandbox plan -destroy -out=sandbox-destroy.tfplan`), with the expected result being no prevent_destroy blocker:

```powershell
terraform fmt -check -recursive
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/sandbox plan -destroy -out=sandbox-destroy.tfplan
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
tflint --recursive
trivy config .
checkov -d . --framework terraform
Push-Location lambda_src; python -m pytest; Pop-Location
```

If a command cannot run because its target files are not created yet, record that in the relevant progress file and final response.

When AI Engine contract integration infrastructure is touched, also run the narrowest available checks for the changed surface:

```powershell
terraform fmt -check -recursive modules/ai-runtime-lambda modules/compute-lambda modules/orchestration modules/iam modules/networking
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
trivy config .
checkov -d modules/ai-runtime-lambda modules/orchestration --framework terraform
```

Lambda container-specific checks to verify:

- ECR image references use digest-pinning (no mutable `:latest` tags in production).
- ECR scan-on-push is enabled.
- Lambda functions use aliases ("live") for stable invocation targets.
- Reserved concurrency is configured; optional provisioned concurrency for latency-sensitive paths.
- SQS event source mapping has `maximum_concurrency` scaling config.
- CloudWatch log groups are KMS-encrypted.
- X-Ray active tracing is enabled.
- Lambda functions run in VPC private subnets with no public endpoint.
- No secret values are stored in Terraform state, variable defaults, or Lambda environment variables.

## Security Rules

- Do not commit AWS access keys, secret values, API keys, real webhook URLs, private certificates, state files, plan files, or plan JSON.
- Do not put secret values in variable defaults, examples, workflow files, logs, or progress docs.
- Do not output full secret ARNs plus secret values together.
- Do not use static API keys as the production authentication pattern for CDO-to-AI Engine calls. Use IAM SigV4 and scoped IAM roles for inter-service authentication.
- Do not log AI request payloads, authorization headers, SigV4 material, tenant-sensitive telemetry, secret references paired with values, or raw CUR rows that could contain sensitive account metadata.
- Do not create IAM policies with wildcard administrative permissions.
- Do not create wildcard trust policies.
- Do not create public S3 buckets.
- Encrypt S3, DynamoDB, SNS, CloudWatch log destinations where supported, and Terraform state.
- Enforce TLS-only S3 bucket policies.
- Keep Lambda functions in VPC private subnets. Do not attach public IPs or create public-facing Lambda function URLs for AI Engine Lambdas.
- Use separate security group rule resources instead of inline ingress or egress blocks.
- Keep prod apply behind GitHub environment approval.
- Keep AI Engine execution private; do not expose the AI Engine Request or Worker Lambdas through public internet endpoints, public Lambda function URLs, or public API Gateways from this repo.
- Use separate security group rule resources for Lambda, VPC endpoint, and SQS/DynamoDB/S3 VPC endpoint traffic.
- Do not grant AI Engine integration roles or CDO workers permissions to terminate prod resources, delete data, modify IAM, or bypass containment policy.
- Store AI Engine auth material and external webhooks in Secrets Manager. Do not commit secret values or sync runtime secrets from this repo.
- Prefer immutable artifact references for handoff/deployment references. Use ECR image digest pinning for production AI Engine Lambda deployments. Do not recommend mutable `:latest` or floating tags for production image references.
- If SBOM, signing, or provenance artifacts are introduced, keep them as deployment evidence and do not embed secret signing material in Terraform, workflows, or docs.
- Do not grant AI Engine Lambda execution roles or SQS event source mappings permissions beyond the scoped DynamoDB tables, S3 evidence/curated paths, SQS queues, KMS keys, Secrets Manager secrets, and CloudWatch/X-Ray destinations required by the contract.

## Final Response Expectations

When finishing work in this repo, the agent must report:

- Files created or modified.
- Which skeleton area was implemented.
- Validation commands run and their outcomes.
- Any commands that could not run and why.
- Progress files updated in English and Vietnamese.
- `docs/GUIDES.md` and `docs/GUIDES_vi.md` updated, or `No guide impact` with a short reason.
- Which `docs/contracts/**` files were read and which contract requirements were implemented or intentionally left out of scope.
- Any contract coverage gaps for AI API behavior, telemetry quality, SLO observability, queues/DLQs, deployment gates, or security controls.
- Any stale runtime-platform, application-deployment, or application-rollout wording found in `docs/contracts/**` or `docs/tf2-finops/**` compared with the current Terraform platform/integration boundary.
- Any discovered mismatch between implementation and read-only docs.
- Any stale guidance found in `README.md`, `IMPLEMENTATION.md`, or in-repo `./docs/tf2-finops/**` compared with the current Terraform platform/integration boundary.

Do not claim success for unvalidated infrastructure. Use precise status such as "created", "validated", "planned", or "blocked".
