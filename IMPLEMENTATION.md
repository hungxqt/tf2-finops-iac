# TF2 FinOps IaC Implementation Plan & Backlog

**Goal:** Build the Terraform repository skeleton for TF2 FinOps Watch to provision the AWS platform foundation for lakehouse ingestion, scheduled orchestration, CDO-hosted AI Engine integration via private internal ALB and Lambda container runtime, alerting, safe containment, audit evidence, and CI/CD-controlled deployments.

**Architecture:** Terraform is the single source of truth for AWS infrastructure. The platform uses S3/Glue/Athena as the lakehouse data plane, EventBridge Scheduler and Step Functions for 24h orchestration, Lambda for short CDO adapters and policy workers (running Python 3.13), and AWS Lambda container platform infrastructure for the AIOps-provided AI Engine. This repo owns ECR repositories (digest-pinned images, scan-on-push), the AI Engine Request Lambda and Worker Lambda (`package_type = "Image"`), Lambda aliases/versions, private internal HTTPS ALB, Route 53 private hosted zone, private networking, execution roles, secrets plumbing, and infrastructure integration points.

**Tech Stack:** Terraform `>= 1.10.0` (floor for `use_lockfile = true`, active version `1.15.6`), AWS provider `>= 5.47, < 6.0`, Python 3.13 managed Lambda workers, AWS Lambda container platform (Image package type), ECR, Route 53 private DNS, Secrets Manager, CloudWatch metrics/logs, X-Ray tracing, GitHub Actions OIDC, TFLint, Trivy, Checkov, S3 backend with `use_lockfile = true`.

---

## 1. Contract Coverage Matrix

Future implementation work must verify compliance against this contract coverage matrix:

### 1.1 AI API Contract
- **Authentication**: SigV4 header security with role-based validation. No static API keys in production.
- **Payload Headers**: Secure context headers passed: `Content-Type`, `Accept`, `X-Tenant-Id` (tenant isolation), `X-Idempotency-Key` (idempotency check), `X-Correlation-Id` (correlation ID), `X-Payload-SHA256` (payload hash), `X-Request-Timestamp` (request timestamp), and `X-Dry-Run-Mode` (dry-run mode).
- **Ingestion Mode**: CDO/AI boundary supports both `RAW_JSON` and `S3_POINTER` modes.
- **Logical Operations**: `/v1/detect`, `/v1/decide`, and `/v1/verify` are synchronous operations. `/v1/status/{id}` is for remediation audit/status only (not for detection polling). `/v1/audit/{audit_id}/rollback` handles result notifications. `/health` is for backend health check.
- **Metadata Context**: Schema versioning, optional `callback_url`, `data_confidence` score, and `rollback_payload.boto3_equivalent` parameters are preserved.
- **Error Handling**: Fail-closed logic for AI timeout, rate limits (`429`), schema mismatch, cross-tenant denial (`403`), and unavailable service.

### 1.2 Telemetry Ingestion Contract
- **CUR Processing**: Ingests billing metadata using S3 pointers by default (`S3_POINTER`).
- **Cost Explorer Fallback**: Daily query via `RAW_JSON` runs only when CUR delivery delay exceeds 36 hours.
- **Degradation Policy**: If CloudWatch metrics are missing or CUR delay exceeds fallback tolerance, the workflow degrades to dry-run/alert-only containment and writes audit evidence.

### 1.3 Deployment Contract
- **Identity & Credentials**: Keyless GitHub Actions deployment via AWS OIDC provider.
- **Workflow Safety**: No auto-apply on drift detection (only alarms/GitHub issues). Save and upload `tfplan` as a workflow artifact, ensuring that `terraform apply` consumes the reviewed plan artifact.
- **Lambda Traffic Splitting**: Lambda weighted routing aliases (`live`, `canary`) for zero-downtime rollouts.
- **Step Functions Release**: Versioned State Machine definitions corresponding to deployments.
- **Rollback Triggers**: Deployment smoke-test failure triggers automatic rollback to the previous version.

### 1.4 Storage & State Policy
- **Idempotency Hot Path**: Composite key lookup in DynamoDB table `finops-idempotency-{env}` with a 24-hour Time-to-Live (`ttl_expiry`).
- **Audit Logging**: compliance-mode Object Lock enabled on S3 audit buckets for staging/prod (minimum 90 days retention).
- **Sandbox Teardown Caveat**: To allow complete resource destruction in sandbox environment, sandbox audit buckets must bypass S3 Object Lock compliance retention.
- **Rollback Cache**: DynamoDB table `finops-rollback-cache` stores the `rollback_payload.boto3_equivalent` configuration for 90 days (`ttl_expiry`).

### 1.5 Dashboard Hosting
- **Architecture**: Static assets hosted in S3 and delivered via CloudFront CDN.
- **Authentication**: Cognito User Pools and Identity Pools integrated with CloudFront OAC.
- **Database Querying**: Athena named queries provide finance-friendly SQL views. Materialized views in DynamoDB dashboard read-caches support SQL-free dashboard performance. QuickSight is a future-only BI integration.

---

## 2. Module Target Behaviors & Known Drift

### `modules/networking`
- **Target Behavior**: Creates private VPC, subnets, NAT, VPC Route Tables, and Gateway/Interface VPC Endpoints (S3, DynamoDB, KMS, Secrets Manager, CloudWatch Logs, X-Ray, STS, ECR, SQS) to keep all AI Engine traffic entirely private.
- **Known Drift**: None. Already matches the active VPC design.

### `modules/lakehouse`
- **Target Behavior**: Provision raw/curated S3 bucket, audit S3 bucket with versioning and KMS SSE, Glue Catalog databases, and Athena workgroup.
- **Known Drift**: Sandboxes must pass `destroyable = true` to skip S3 Object Lock compliance-mode retention and set short KMS deletion windows; staging and prod must default to `destroyable = false` for data protection.

### `modules/iam`
- **Target Behavior**: Scoped execution roles for Step Functions, EventBridge Scheduler, and Lambda adapters. Includes a strict permission boundary policy blocking IAM modification, organization modifications, S3 deletes, and EC2/RDS termination on production resources.
- **Known Drift**: Ensure the CDO caller role can assume a SigV4 credential context for the private HTTPS ALB calls.

### `modules/ai-runtime-lambda`
- **Target Behavior**: Deploys private internal Application Load Balancer (ALB) exposing target groups on port 8080 (health check `/health`) and HTTPS listener on port 443. Configures Route 53 private hosted zone and record alias for `ai-engine` service DNS lookup. Deploys AI Engine Request Lambda and Worker Lambda (`package_type = "Image"`) utilizing ECR digest-pinned images. Enforces reserved concurrency and KMS-encrypted CloudWatch log groups. No public Function URLs are allowed.
- **Known Drift**: None. All references to public Function URLs, ECS clusters, Fargate capacity providers, or Private API Gateways are retired or marked as superseded reference wording.

### `modules/compute-lambda`
- **Target Behavior**: Packages and deploys Lambda worker zip files (Python 3.13) for CDO adapters (`state`, `cost_puller`, `normalizer`, `router`, `containment_worker`, `audit_writer`, and `vpc_alb_caller`). Attaches functions to the VPC and security groups. Configures log retention, X-Ray tracing, and stable/canary aliases.
- **Known Drift**: Replace `ai_client` references with `vpc_alb_caller`. (Fully completed in code stubs and tests).

### `modules/orchestration`
- **Target Behavior**: Creates DynamoDB run-state, idempotency (24h TTL), rollback cache (90d TTL), and result tables. Deploys Step Functions Standard state machine invoking Python workers and polling results directly from DynamoDB.
- **Known Drift**: Remove any SQS-based detection queue or result-polling loop in the default execution path. The `VpcAlbCallerLambda` performs synchronous calls to `/v1/detect`, `/v1/decide`, and `/v1/verify` directly. SQS/DLQ are restricted to alert retry and `finops-watch-rollback` notifications.

### `modules/alerting`
- **Target Behavior**: Separate, encrypted SNS topics for Finance and Engineering.
- **Known Drift**: None.

### `modules/observability`
- **Target Behavior**: CloudWatch operational dashboard and alarms for workflow failures, ALB request errors, AI Engine unavailable, stale telemetry (>26h), and CI drift detection custom metric.
- **Known Drift**: Ensure alarms are aligned with synchronous ALB error indicators rather than asynchronous queue metrics.

### `modules/dashboard`
- **Target Behavior**: S3 asset hosting bucket, CloudFront distribution with Origin Access Control (OAC), Cognito user/identity pools, and Athena named queries for finance usability.
- **Known Drift**: None.

---

## 3. Backlog Implementation Backlog

### [x] Task 1: Baseline Repository Hygiene
- **Status**: Completed & Maintained.
- **Details**: Local validation scripts (`validate.ps1`), packaging scripts, `.gitignore`, `.pre-commit-config.yaml`, and TFLint configurations are in place.

### [x] Task 2: Bootstrap Remote State and GitHub OIDC
- **Status**: Completed & Maintained.
- **Details**: Local bootstrap executes cleanly. OIDC deploy roles are provisioned. Long-lived state runs on S3 with `use_lockfile = true` and no DynamoDB lock table.

### [x] Task 3: Lambda Worker Python Stubs and Tests
- **Status**: Completed & Maintained.
- **Details**: Python 3.13 adapter functions (`state`, `cost_puller`, `normalizer`, `router`, `containment_worker`, `audit_writer`, and `vpc_alb_caller`) are present. Pytest unit suite validates the code. Stale `ai_client` references are deleted.

### [ ] Task 4: Networking Module Implementation
- **Status**: Scheduled.
- **Target**: Set up VPC, subnets, route tables, security groups, and VPC endpoint interfaces. Define route configurations to private internal ALB.

### [ ] Task 5: Lakehouse Storage Implementation
- **Status**: Scheduled.
- **Target**: Set up raw, curated, and audit buckets. Configure S3 versioning, lifecycle rules, KMS SSE-KMS, and S3 Object Lock. Apply `destroyable` guardrails.

### [ ] Task 6: IAM Permissions & Boundaries
- **Status**: Scheduled.
- **Target**: Set up IAM roles for Lambda adapters, Step Functions execution, and scheduler. Define the explicit deny permissions boundary to guard production assets.

### [ ] Task 7: ECR & Private Lambda Container AI Runtime (`modules/ai-runtime-lambda`)
- **Status**: Scheduled.
- **Target**: Provision ECR repository with scan-on-push. Deploy private internal ALB with self-signed certificate. Route 53 private DNS records. Deploys AI Engine Request Lambda and Worker Lambda as container functions.

### [ ] Task 8: Compute Lambda Configuration
- **Status**: Scheduled.
- **Target**: Package and upload zip-based Python Lambdas. Configure VPC bindings, memory limits, log retention, and stable/canary weighted aliases.

### [ ] Task 9: Step Functions Orchestration & Control Flow
- **Status**: Scheduled.
- **Target**: Deploy DynamoDB tables (`finops-idempotency-{env}`, `finops-rollback-cache`). Write Step Functions ASL containing synchronous `VpcAlbCallerLambda` invocations, idempotency checks, and fail-closed error transitions.

### [ ] Task 10: Alerting, Observability, and Dashboard Modules
- **Status**: Scheduled.
- **Target**: Encrypted SNS topics. CloudWatch operational dashboard and alarms. S3 asset hosting, CloudFront OAC distribution, and Cognito pools for dashboard users.

### [ ] Task 11: Environment Roots Composition
- **Status**: Scheduled.
- **Target**: Set up environment files under `environments/sandbox/`, `staging/`, and `prod/` calling modules with appropriate variables. Ensure staging/prod are protected from teardown.

### [ ] Task 12: CI/CD GitHub Actions & Drift Detection
- **Status**: Scheduled.
- **Target**: GitHub Actions workflow configurations for CI validation, artifact-based plans/applies, and daily scheduled drift detection check with alerting.

### [ ] Task 13: E2E Verification & Handoff
- **Status**: Scheduled.
- **Target**: Execute `validate.ps1`, verify dry-run containment safety, ensure no hardcoded secrets, and generate output parameters for GitOps handoff.

---

## 4. Rollback and Recovery Notes

- **Git Reverts**: The primary rollback for IaC configurations is a normal Git revert of the corresponding pull request.
- **Staging/Prod Approvals**: Applies to staging and production are strictly performed via CI using reviewed plan artifacts.
- **Lambda Recovery**: Lambda functions use stable version aliases. Code rollback is executed by pointing the alias back to the previous version or re-deploying the previous Git commit.
- **Step Functions Recovery**: Apply the previous state machine definition from Git.
- **AI Workload Recovery**: To roll back the container runtime, update the module configuration with the previous immutable image digest.
- **Containment Rollback Execution**: Rollbacks execute using the cached Boto3 payload from the `finops-rollback-cache` table, which is retained for 90 days. The SQS queue `finops-watch-rollback` is strictly for audit completion notifications, not dispatch.
- **Data Protection**: Remote state bucket, KMS keys, audit buckets, lakehouse buckets, and primary DynamoDB tables are protected by `prevent_destroy` sentinel resources when `destroyable = false`.

---

## 5. Implementation Defaults & Guardrails

- **Platform Target**: Terraform is the exclusive platform IaC tool for AWS infrastructure.
- **Remote Locking**: S3 native lockfile (`use_lockfile = true`) is used. No DynamoDB locking table.
- **AI Engine Integration**: Synchronous invocations via `vpc_alb_caller` Lambda -> private internal HTTPS ALB -> AI Request Lambda live alias.
- **No Async Polling**: No SQS-based detection queue or DynamoDB-polling loops.
- **Containment Safety**: Dry-run by default. Automated containment must **NEVER** terminate prod instances, delete data, or modify IAM roles/policies.
- **Audit Trails**: compliance-mode S3 Object Lock audit retention (min 90 days) in staging and prod. Sandbox defaults to teardown-compatible settings.
- **VPC Security**: Egress rules are separate security group resources. No public IPs or public function URLs.
- **Telemetry Fallback**: CUR `S3_POINTER` is the default. Cost Explorer fallback (`RAW_JSON`) triggers only after a CUR delay of > 36 hours. Telemetry quality issues force a fail-closed / dry-run degradation.
