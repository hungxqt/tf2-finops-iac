# TF2 FinOps IaC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Terraform repository skeleton for TF2 FinOps Watch so the team can provision the AWS platform foundation for lakehouse ingestion, scheduled orchestration, CDO-hosted AI Engine integration via private internal ALB and Lambda container runtime, alerting, safe containment, audit evidence, and CI/CD-controlled deployments.

**Architecture:** Terraform is the single source of truth for AWS infrastructure. The platform uses S3/Glue/Athena as the lakehouse data plane, EventBridge Scheduler and Step Functions for 24h orchestration, Lambda for short CDO adapters and policy workers (running Python 3.13), and AWS Lambda container platform infrastructure for the AIOps-provided AI Engine. This repo owns ECR repositories (digest-pinned images, scan-on-push), the AI Engine Request Lambda and Worker Lambda (`package_type = "Image"`), Lambda aliases/versions, private internal HTTPS ALB, Route 53 private hosted zone, private networking, execution roles, secrets plumbing, and infrastructure integration points.

**Tech Stack:** Terraform `>= 1.10.0`, AWS provider `>= 5.47, < 6.0`, Python 3.13 managed Lambda workers, AWS Lambda container platform (Image package type), ECR, Route 53 private DNS, Secrets Manager, CloudWatch metrics/logs, X-Ray tracing, GitHub Actions OIDC, TFLint, Trivy, Checkov, S3 backend with `use_lockfile = true`.

---

## 1. Implementation Contract

### Version and Execution Assumptions

- Runtime: Terraform, not OpenTofu.
- Local checked tools at planning time:
  - Terraform `v1.10.0+`
  - TFLint `0.63.1+`
  - Trivy `0.71.1+`
  - Checkov `3.2.524+`
- Provider floor:
  - `hashicorp/aws >= 5.47, < 6.0`
  - `hashicorp/archive >= 2.4, < 3.0`
- Backend:
  - `bootstrap/` starts local for first creation of the state backend.
  - All long-lived environment roots use S3 backend with `use_lockfile = true`.
  - Do not create a DynamoDB lock table.
- Region default: `ap-southeast-1`.
- Environment criticality:
  - `sandbox`: fast iteration, containment apply allowed only for non-prod examples.
  - `staging`: integration and dry-run validation.
  - `prod`: manual approval only, tag/suggest/dry-run containment only.

### Source Priority

When implementation details conflict, use this order:

1. Explicit user instructions in the current conversation.
2. `AGENTS.md`.
3. Current scenario documents under `../tf2-finops-docs/`, especially `AGENTS.md`, `TF2_FINOPS_LEARNER.md`, and `docs/tf2-finops/01-04*.md`.
4. This `IMPLEMENTATION.md`.
5. `README.md`.

If `README.md` or in-repo docs still describe the older Lambda-only or ECS-based scenarios, treat them as stale/superseded.

### Risk Categories Addressed

- **State corruption:** S3 backend, versioning, KMS encryption, native lock file, no committed state.
- **Secret exposure:** no committed `.tfvars`, no provider credentials in HCL, Secrets Manager references only, and no webhook/API secret values in examples.
- **Blast radius:** separate environment roots, prod manual approval, `prevent_destroy` on critical resources.
- **CI drift:** pinned runtime/provider versions, reviewed plan artifacts, apply consumes the saved artifact.
- **Compliance gaps:** Trivy, Checkov, TFLint, encrypted storage, audit retention, Object Lock, OIDC, ECR scan-on-push, and VPC private access controls.
- **Provider upgrade risk:** version constraints and lockfile committed after first `terraform init`.
- **Testing blind spots:** module validation, environment validate, Lambda unit tests (pytest), ECR static scans, AI contract checks, and security scans.

### Non-Negotiable Guardrails

- AWS only.
- Synthetic data unless real billing access is explicitly granted.
- Default cadence is 24h unless the user changes the approved design.
- CDO owns cost ingestion, normalized cost windows, ownership/tag metadata, scheduling, idempotency, workflow state, dashboard views, containment guardrails, audit logs, platform SLOs, and the AI Engine integration platform hooks.
- AIOps owns anomaly detection logic, model selection, model training/retraining design, model versions, confidence scoring, classification, explanation text, AI Engine code/model internals, and backtest metrics.
- Finance and Engineering alert routes stay separate.
- Audit retention is at least 90 days.
- Containment defaults to dry-run.
- Production containment never applies destructive actions.
- Automated containment must never terminate prod, delete data, or modify IAM.

---

## 2. Target Repository Tree

Create this structure under `tf2-finops-iac/`:

```text
.
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
│   │       ├── state/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── cost_puller/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── normalizer/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── router/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── audit_writer/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       ├── containment_worker/
│   │       │   ├── __init__.py
│   │       │   └── handler.py
│   │       └── vpc_alb_caller/
│   │           ├── __init__.py
│   │           └── handler.py
│   └── tests/
│       ├── conftest.py
│       ├── test_audit_writer.py
│       ├── test_containment_worker.py
│       ├── test_cost_puller.py
│       ├── test_finops_common.py
│       ├── test_normalizer.py
│       ├── test_router.py
│       ├── test_state.py
│       ├── test_state_machine.py
│       ├── test_step_function_lambda_coverage.py
│       └── test_vpc_alb_caller.py
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
├── scripts/
│   ├── validate.ps1
│   └── package-lambdas.ps1
├── .gitignore
├── .pre-commit-config.yaml
├── .terraform-version
├── .tflint.hcl
├── Makefile
├── README.md
└── IMPLEMENTATION.md
```

Each Terraform module must contain:

```text
README.md
main.tf
variables.tf
outputs.tf
versions.tf
```

---

## 3. Module Contracts

### `modules/networking`

Creates the private network foundation for Lambda workers, internal load balancer resources, VPC endpoints, and internal AI Engine traffic.

Resources:

- VPC with DNS hostnames and DNS support enabled.
- Two public subnets for NAT gateways.
- Private subnets shared by Lambda workers, internal load balancer resources, and VPC endpoints.
- Internet gateway for public subnets.
- NAT gateway count controlled by environment:
  - sandbox: one NAT gateway.
  - staging/prod: two NAT gateways unless cost override is explicitly set.
- Route tables and associations.
- Lambda security group with no ingress.
- VPC endpoint security group with HTTPS ingress from Lambda and other security groups.
- Gateway endpoints for S3 and DynamoDB.
- Interface endpoints for KMS, Secrets Manager, Athena, CloudWatch Logs, X-Ray, STS, ECR API, ECR Docker registry, and SQS.

Inputs:

- `project_name`
- `environment`
- `aws_region`
- `vpc_cidr_block`
- `public_subnet_cidr_blocks`
- `private_subnet_cidr_blocks`
- `availability_zones`
- `single_nat_gateway`
- `tags`

Outputs:

- `vpc_id`
- `private_subnet_ids`
- `public_subnet_ids`
- `lambda_security_group_id`
- `vpc_endpoint_security_group_id`
- `vpc_cidr_block`

Security requirements:

- Do not use the default VPC.
- Use separate `aws_vpc_security_group_ingress_rule` and `aws_vpc_security_group_egress_rule` resources.
- Restrict Lambda egress to HTTPS where service behavior allows it.
- Keep AI Engine traffic private. Do not expose an internet-facing AI endpoint.
- Allow Lambda to reach the internal AI Engine endpoint on HTTPS only.

### `modules/lakehouse`

Creates durable cost, audit, feature, and query storage.

Resources:

- KMS keys and aliases:
  - data key
  - audit key
  - DynamoDB key
- S3 lakehouse bucket for raw and curated prefixes.
- S3 audit bucket with Object Lock enabled in compliance mode (retention of 90 days).
- S3 public access blocks for every bucket.
- S3 bucket versioning for every bucket.
- S3 SSE-KMS encryption for every bucket.
- TLS-only bucket policies.
- Lifecycle rules:
  - raw and curated objects transition after hot review period.
  - audit objects retain at least 90 days.
- Glue catalog database.
- Athena workgroup with enforced output location and query bytes cutoff.

Inputs:

- `project_name`
- `environment`
- `aws_region`
- `audit_retention_days`
- `athena_query_bytes_cutoff`
- `tags`
- `destroyable` (for sandbox S3 bucket teardown and KMS deletion window)

Outputs:

- `lakehouse_bucket_name`
- `lakehouse_bucket_arn`
- `audit_bucket_name`
- `audit_bucket_arn`
- `glue_database_name`
- `athena_workgroup_name`
- `data_kms_key_arn`
- `audit_kms_key_arn`
- `ddb_kms_key_arn`

Security requirements:

- No unencrypted S3 bucket.
- No public bucket policy.
- Audit bucket Object Lock must be enabled at creation time for staging/prod.
- Critical buckets use static destroy guard sentinel resources when `destroyable = false`.

### `modules/iam`

Creates least-privilege execution roles, platform roles, and unsafe-action guardrails.

Resources:

- Step Functions execution role.
- Lambda execution roles for Python workers (`state`, `cost_puller`, `normalizer`, `router`, `containment_worker`, `audit_writer`, `vpc_alb_caller`).
- CDO caller role for AI Engine service invocation (using IAM SigV4 authentication).
- Explicit deny policy boundary for unsafe automation (preventing IAM modification, EC2 termination, RDS deletion, S3 deletes, etc.).

Inputs:

- `project_name`
- `environment`
- `lakehouse_bucket_arn`
- `audit_bucket_arn`
- `dynamodb_table_arns`
- `kms_key_arns`
- `ai_engine_secret_arn`
- `containment_apply_enabled`
- `tags`

Outputs:

- `step_functions_role_arn`
- `scheduler_role_arn`
- `lambda_role_arns`
- `cdo_caller_role_arn`
- `permissions_boundary_arn`

Security requirements:

- No `Action = "*"` policies.
- No wildcard trust principals.
- Explicit deny must include IAM modification, organization modification, S3 deletes, DynamoDB deletes, RDS deletes, and EC2 termination.
- Prod roles must not allow destructive containment apply actions.

### `modules/ai-runtime-lambda`

Creates the CDO-owned Lambda container hosting platform for the AIOps-provided AI Engine.

Resources:

- ECR repository with KMS encryption, immutable image tags, and scan-on-push enabled.
- Private internal Application Load Balancer (ALB) exposing target groups on port 8080 (health check `/health`) and HTTPS listener on port 443.
- ACM Self-Signed TLS certificate for secure private transit.
- Route 53 private hosted zone and record alias (`ai-engine.<project>-<env>.local`).
- AI Engine Request Lambda and Worker Lambda (`package_type = "Image"`) utilizing the digest-pinned images.
- Lambda execution roles and VPC event source mapping for SQS.
- KMS-encrypted CloudWatch log groups.

Inputs:

- `project_name`
- `environment`
- `vpc_id`
- `private_subnet_ids`
- `lambda_security_group_id`
- `request_image_uri`
- `worker_image_uri`
- `detect_queue_arn`
- `results_table_arn`
- `kms_key_arns`
- `secret_arns`
- `destroyable`
- `tags`

Outputs:

- `ecr_repository_url`
- `internal_alb_dns_name`
- `ai_engine_internal_endpoint_url`
- `request_lambda_arn`
- `worker_lambda_arn`

Rules:

- Do not deploy `latest` or mutable container tags; reference images by immutable digests.
- Enforce private HTTPS endpoints inside the VPC (no public ingress).

### `modules/compute-lambda`

Packages and deploys Lambda worker zip packages for CDO adapters and policy workers.

Resources:

- Archive artifacts for each worker from `lambda_src/`.
- Lambda functions running Python 3.13:
  - `state`
  - `cost_puller`
  - `normalizer`
  - `router`
  - `containment_worker`
  - `audit_writer`
  - `vpc_alb_caller`
- Lambda handlers configured as `workers.<worker>.handler.handle_request`.
- Lambda stable/canary version aliases.
- Lambda log groups with retention.
- X-Ray active tracing.
- Reserved concurrency limits.

Inputs:

- `project_name`
- `environment`
- `private_subnet_ids`
- `lambda_security_group_id`
- `lambda_role_arns`
- `lakehouse_bucket_name`
- `audit_bucket_name`
- `dynamodb_table_names`
- `alb_base_url`
- `sigv4_service_name`
- `containment_apply_enabled`
- `log_retention_days`
- `tags`

Outputs:

- `lambda_function_names`
- `lambda_function_arns`
- `lambda_alias_arns`

Implementation rules:

- Lambda code is minimal but deployable. It validates required event fields, logs structured JSON, and returns a typed status object.
- `vpc_alb_caller` calls the private internal ALB endpoint through standard HTTPS with IAM SigV4 (`Authorization`) header.
- Handlers handle AI API error codes defensively: service down, rate limit, schema mismatch, and timeouts must fail closed.

### `modules/orchestration`

Creates scheduled workflow state, DynamoDB tables, and control flow.

Resources:

- DynamoDB tables:
  - run state (hash key: `idempotency_key`, TTL: `ttl_expiry`)
  - anomaly records (hash key: `anomaly_id`)
  - routing state (hash key: `route_id`)
  - containment audit index (hash key: `audit_id`)
  - dashboard materialized views (hash key: `view_id`)
  - account policy table (hash key: `account_id`)
  - error budget table (hash key: `tenant_id`)
  - AI results table (hash key: `audit_id`)
  - Rollback cache table (hash key: `anomaly_id`, TTL: `ttl_expiry` for 90-day retention)
- Step Functions Standard state machine invoking Python workers sequentially.
- EventBridge Scheduler schedule with 24h default cadence.
- SQS primary detection queue, DLQ, and rollback status queue.

Inputs:

- `project_name`
- `environment`
- `scheduler_expression`
- `step_functions_role_arn`
- `scheduler_role_arn`
- `lambda_function_arns`
- `ddb_kms_key_arn`
- `audit_bucket_name`
- `ai_engine_contract_version`
- `tags`

Outputs:

- `state_machine_arn`
- `scheduler_arn`
- `dynamodb_table_names`
- `dynamodb_table_arns`
- `rollback_cache_table_name`

Workflow shape:

```text
EventBridge Scheduler
-> Step Functions
-> PrepareRunContext (state)
-> LoadAccountPolicy (DynamoDB getItem)
-> PullCostData (cost_puller)
-> NormalizeCostData (normalizer)
-> InvokeDetect (vpc_alb_caller -> private internal ALB -> AI Request Lambda -> synchronous /v1/detect)
-> EvaluateDetectResponse
-> InvokeDecide (vpc_alb_caller -> private internal ALB -> AI Request Lambda -> synchronous /v1/decide)
-> EvaluateDecideResponse
-> ExecuteContainment (containment_worker)
-> ReportVerifyResult (vpc_alb_caller -> private internal ALB -> AI Request Lambda -> synchronous /v1/verify)
-> WritePostActionAudit (audit_writer)
-> MarkRunComplete (state)
```

Failure behavior:

- Duplicate idempotency key exits without cost pulling, AI calls, alerts, or containment.
- AI Engine unavailable, timeout, schema mismatch, or rate limits alerts Engineering and fails closed (no automated containment).
- Audit write failure fails closed before containment apply.

### `modules/alerting`

Creates separate business and engineering alert routes.

Resources:

- Finance SNS topic.
- Engineering SNS topic.
- Optional email subscriptions.
- KMS encryption for SNS topics.

Inputs:

- `project_name`
- `environment`
- `finance_email_subscriptions`
- `engineering_email_subscriptions`
- `sns_kms_key_arn`
- `tags`

Outputs:

- `finance_topic_arn`
- `engineering_topic_arn`

Security requirements:

- Finance and Engineering routes must not share a topic.
- SNS topics must be encrypted.

### `modules/observability`

Creates platform visibility for Step Functions, Lambda, lakehouse freshness, and AI Engine availability.

Resources:

- CloudWatch dashboard.
- Metric alarms:
  - workflow failed
  - ALB request failures
  - AI Engine endpoint unavailable
  - audit write failed
  - stale workflow over 26h
  - drift detected custom metric emitted by CI
- Log metric filters for structured Lambda status logs.

Inputs:

- `project_name`
- `environment`
- `state_machine_arn`
- `lambda_function_names`
- `engineering_topic_arn`
- `finance_topic_arn`
- `log_retention_days`
- `tags`

Outputs:

- `dashboard_name`
- `alarm_names`

### `modules/dashboard`

Creates dashboard infrastructure hooks using S3 bucket hosting, CloudFront CDN, and Cognito authentication.

Resources:

- S3 bucket for static dashboard assets (`dashboard_assets`) and S3 bucket for dashboard JSON summaries (`dashboard_data`).
- S3 public access blocks, versioning, SSE-KMS encryption, and TLS-only policies.
- CloudFront distribution with Origin Access Control (OAC) and WAFv2 Web ACL.
- Cognito user pool, pool client, domain, identity pool, and authenticated role.
- Athena named queries for finance-friendly cost views.
- QuickSight data source (optional, disabled by default).

Inputs:

- `project_name`
- `environment`
- `glue_database_name`
- `athena_workgroup_name`
- `dashboard_kms_key_arn`
- `s3_logging_bucket_id`
- `dashboard_assets_replica_bucket_arn`
- `dashboard_data_replica_bucket_arn`
- `cloudfront_aliases`
- `cloudfront_acm_certificate_arn`
- `enable_quicksight`
- `tags`

Outputs:

- `dashboard_url`
- `cognito_user_pool_id`
- `cognito_identity_pool_id`
- `athena_named_query_ids`

Rule:

- The static assets are hosted in S3 and delivered via CloudFront, enabling finance-readable SQL-free views by reading from DynamoDB dashboard read-caches.

---

## 4. Environment Composition Contract

Each environment root calls all modules and provides only environment-specific values.

### Sandbox

- Backend key: `sandbox/terraform.tfstate`
- `single_nat_gateway = true`
- `containment_apply_enabled = true` only for non-prod/synthetic examples.
- `scheduler_expression = "rate(24 hours)"`
- Log retention: 14 days
- `destroyable = true` to allow full sandbox teardown.
- ECR repository `force_delete = true`, S3 bucket `force_destroy = true`.
- Email subscriptions can be empty by default.
- Used for base build, W12 testing, and synthetic E2E runs.

### Staging

- Backend key: `staging/terraform.tfstate`
- `single_nat_gateway = false`
- `containment_apply_enabled = false`
- `scheduler_expression = "rate(24 hours)"`
- Log retention: 30 days
- `destroyable = false` for protected infrastructure state.
- Used for AI contract validation, AIOps container artifact validation, E2E testing, and chaos/failure tests.

### Prod

- Backend key: `prod/terraform.tfstate`
- `single_nat_gateway = false`
- `containment_apply_enabled = false`
- `scheduler_expression = "rate(24 hours)"`
- Log retention: 30 days
- `destroyable = false`
- Critical resources use `prevent_destroy` via static destroy guard sentinel resources.
- Apply only through GitHub environment approval.
- Production containment is tag, suggest, or dry-run only.

Each root must expose stable outputs for:

- S3 bucket names and ARNs.
- DynamoDB table names and ARNs.
- ECR repository URL.
- AI Engine internal endpoint URL.
- Step Functions ARN.
- EventBridge Scheduler ARN.
- Lambda names and ARNs.
- SNS topic ARNs.
- CloudWatch dashboard name.
- Cognito pool metadata.

Module call order:

1. networking
2. lakehouse
3. alerting
4. base iam
5. ai_runtime_lambda
6. compute-lambda
7. orchestration
8. observability
9. dashboard

---

## 5. Task Breakdown

### Task 1: Baseline Repository Hygiene

**Files:**

- Create: `.gitignore`
- Create: `.terraform-version`
- Create: `.tflint.hcl`
- Create: `.pre-commit-config.yaml`
- Create: `Makefile`
- Create: `scripts/validate.ps1`
- Create: `scripts/package-lambdas.ps1`

Steps:

- [ ] Add `.gitignore` entries for `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfvars`, `crash.log`, `tfplan`, `tfplan.json`, `.env`, `.build/`, Lambda package zips, and local editor/system files.
- [ ] Add `.terraform-version` with `1.10.0+`.
- [ ] Configure TFLint with AWS plugin enabled and Terraform ruleset enabled.
- [ ] Add pre-commit hooks for Terraform fmt, validate, tflint, and basic trailing whitespace checks.
- [ ] Add `scripts/validate.ps1` to run `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate`, `tflint`, `trivy config .`, `checkov -d . --framework terraform`, and `cd lambda_src && python -m pytest`.
- [ ] Add `scripts/package-lambdas.ps1` to bundle Python dependencies and zip files under `.build/lambda/`.

Validation:

```powershell
.\scripts\validate.ps1
```

### Task 2: Bootstrap Remote State and GitHub OIDC

**Files:**

- Create: `bootstrap/README.md`
- Create: `bootstrap/backend.tf`
- Create: `bootstrap/versions.tf`
- Create: `bootstrap/providers.tf`
- Create: `bootstrap/variables.tf`
- Create: `bootstrap/locals.tf`
- Create: `bootstrap/main.tf`
- Create: `bootstrap/outputs.tf`

Steps:

- [ ] Configure provider version constraints and default AWS tags.
- [ ] Create KMS key and alias for Terraform state encryption.
- [ ] Create S3 state bucket named from `project_name`, `account_id`, and `aws_region`.
- [ ] Enable versioning, SSE-KMS, bucket key, object ownership, and public access block.
- [ ] Add bucket policy denying insecure transport.
- [ ] Add `lifecycle { prevent_destroy = true }` to state bucket and KMS key (unless destroyable override is set).
- [ ] Create GitHub OIDC provider for `token.actions.githubusercontent.com`.
- [ ] Create deploy roles for sandbox, staging, and prod with branch/environment-restricted trust.
- [ ] Output state bucket name, state KMS key ARN, and deploy role ARNs.

Validation:

```powershell
terraform -chdir=bootstrap fmt -check
terraform -chdir=bootstrap init
terraform -chdir=bootstrap validate
terraform -chdir=bootstrap plan -out=bootstrap.tfplan
```

### Task 3: Lambda Worker Python Stubs and Tests

**Files:**

- Create all files under `lambda_src/`.

Steps:

- [ ] Create shared validation helper requiring `run_id`, `correlation_id`, `cost_period`, `environment`, and `source_data_version`.
- [ ] Create shared response helper returning `status`, `run_id`, `correlation_id`, `worker`, and `details`.
- [ ] Implement `cost_puller` handler to return a synthetic `raw_data_uri`.
- [ ] Implement `normalizer` handler to return a synthetic `curated_data_uri`.
- [ ] Implement `vpc_alb_caller` to send signed HTTPS requests to the ALB base URL utilizing IAM SigV4 (`Authorization`).
- [ ] Implement logical AI paths (`/v1/detect`, `/v1/decide`, `/v1/verify`, `/v1/status/{id}`, `/v1/audit/{audit_id}/rollback`, `/health`) and ensure required SigV4/context headers are passed (`Content-Type`, `Accept`, `X-Tenant-Id`, `X-Idempotency-Key`, `X-Correlation-Id`, `X-Payload-SHA256`, `X-Request-Timestamp`, `X-Dry-Run-Mode`).
- [ ] Implement `router` handler to produce separate Finance and Engineering route decisions.
- [ ] Implement `containment_worker` handler to force `dry-run` for `environment = "prod"` regardless of requested action.
- [ ] Implement `audit_writer` handler to write audit records to S3 and DynamoDB.
- [ ] Implement `state` handler to manage Step Functions execution state and check idempotency.
- [ ] Add Pytest tests proving every handler accepts the shared contract and fails closed defensively.

Validation:

```powershell
Push-Location lambda_src; python -m pytest; Pop-Location
```

### Task 4: Networking Module

**Files:**

- Create: `modules/networking/*`

Steps:

- [ ] Implement VPC, subnets, internet gateway, NAT, routes, and route table associations.
- [ ] Implement Lambda, internal load balancer, and endpoint security groups with separate rule resources.
- [ ] Implement S3 and DynamoDB gateway endpoints.
- [ ] Implement KMS, Secrets Manager, Athena, CloudWatch Logs, X-Ray, STS, ECR API, ECR Docker registry, and SQS interface endpoints.
- [ ] Add outputs listed in the module contract.

Validation:

```powershell
terraform fmt -check -recursive modules/networking
```

### Task 5: Lakehouse Module

**Files:**

- Create: `modules/lakehouse/*`

Steps:

- [ ] Implement KMS keys and aliases for data, audit, and DynamoDB encryption.
- [ ] Implement lakehouse bucket with raw and curated prefixes.
- [ ] Implement audit bucket with Object Lock enabled.
- [ ] Enable versioning, SSE-KMS, lifecycle, public access blocks, and TLS-only policies.
- [ ] Implement Glue database.
- [ ] Implement Athena workgroup with encrypted output and bytes-scanned cutoff.
- [ ] Add outputs listed in the module contract.
- [ ] Document S3 prefix conventions:
  - `cost/raw/`
  - `cost/curated/`
  - `ownership/`
  - `anomaly/`
  - `alert/`
  - `containment/`
  - `audit/`

Validation:

```powershell
terraform fmt -check -recursive modules/lakehouse
```

### Task 6: IAM Module

**Files:**

- Create: `modules/iam/*`

Steps:

- [ ] Create policy documents using `aws_iam_policy_document`.
- [ ] Create Step Functions role with Lambda invoke, DynamoDB access, SNS publish, CloudWatch logging, X-Ray permissions, and internal AI invocation permissions.
- [ ] Create EventBridge Scheduler role.
- [ ] Create one Lambda role per worker class.
- [ ] Create SigV4 CDO caller role for AI Engine service invocation.
- [ ] Scope S3 permissions by bucket and prefix.
- [ ] Scope DynamoDB permissions by exact table ARNs.
- [ ] Scope Secrets Manager access to the AI Engine secret only.
- [ ] Create explicit deny boundary for unsafe actions.
- [ ] Ensure prod containment role cannot stop instances or apply quota changes.

Validation:

```powershell
checkov -d modules/iam --framework terraform
```

### Task 7: ECR and Lambda Container Runtime Module

**Files:**

- Create: `modules/ai-runtime-lambda/*`
- Create or update: `docs/progress/ai_runtime_lambda_progress.md`
- Create or update: `docs/progress/ai_runtime_lambda_progress_vi.md`

Steps:

- [ ] Provision ECR repository with scan-on-push and immutability enforced.
- [ ] Provision private internal Application Load Balancer (ALB) exposing target groups on port 8080 (health check `/health`) and HTTPS listener on port 443.
- [ ] Set up Route 53 private hosted zone and record alias for `ai-engine` service DNS lookup.
- [ ] Configure AI Engine Request Lambda and Worker Lambda (`package_type = "Image"`) utilizing ECR digest-pinned images.
- [ ] Configure task execution roles, Lambda event source mapping for SQS, and KMS-encrypted CloudWatch log groups.
- [ ] Update paired English and Vietnamese progress files with identical facts and section order.

Validation:

```powershell
terraform fmt -check -recursive modules/ai-runtime-lambda
trivy config modules/ai-runtime-lambda
checkov -d modules/ai-runtime-lambda --framework terraform
```

### Task 8: Compute Lambda Module

**Files:**

- Create: `modules/compute-lambda/*`

Steps:

- [ ] Package Lambda source with `archive_file` or consume zip files from `.build/lambda/`.
- [ ] Create seven Lambda functions with environment variables wired from module inputs.
- [ ] Configure VPC attachment to private subnets and Lambda security group.
- [ ] Set runtime to `python3.13` and deploy Python zip artifacts with handler `workers.<worker>.handler.handle_request`.
- [ ] Set timeouts and memory per worker.
- [ ] Enable X-Ray active tracing and create CloudWatch log groups with retention.
- [ ] Create `stable` and `canary` aliases.

Validation:

```powershell
.\scripts\package-lambdas.ps1
terraform fmt -check -recursive modules/compute-lambda
```

### Task 9: Orchestration Module

**Files:**

- Create: `modules/orchestration/*`

Steps:

- [ ] Create DynamoDB tables (including `rollback_cache` with composite key `anomaly_id` and TTL attribute `ttl_expiry`).
- [ ] Create Step Functions ASL with worker invocation order.
- [ ] Add catch path invoking fail-closed behavior for AI timeout, unavailable endpoint, contract mismatch, and rate limiting.
- [ ] Create EventBridge Scheduler with 24h default expression.
- [ ] Output state machine ARN, scheduler ARN, rollback cache table name, and table metadata.

Validation:

```powershell
terraform fmt -check -recursive modules/orchestration
```

### Task 10: Alerting, Observability, and Dashboard Modules

**Files:**

- Create: `modules/alerting/*`
- Create: `modules/observability/*`
- Create: `modules/dashboard/*`

Steps:

- [ ] Create separate encrypted SNS topics for Finance and Engineering.
- [ ] Create CloudWatch alarms for workflow failure, ALB request failures, AI Engine unavailable, audit write failure, and stale workflow.
- [ ] Create CloudWatch dashboard for CDO operations.
- [ ] Create S3 buckets for static dashboard assets and dashboard JSON data.
- [ ] Create CloudFront distribution with Origin Access Control (OAC) and WAFv2 Web ACL.
- [ ] Create Cognito user pool, pool client, domain, identity pool, and authenticated role.
- [ ] Create Athena named queries for finance-readable spend and anomaly views.

Validation:

```powershell
terraform fmt -check -recursive modules/alerting modules/observability modules/dashboard
```

### Task 11: Environment Roots

**Files:**

- Create all files under `environments/sandbox/`
- Create all files under `environments/staging/`
- Create all files under `environments/prod/`

Steps:

- [ ] Add S3 backend config using the bootstrap output bucket and `use_lockfile = true`.
- [ ] Call modules in sequential order.
- [ ] Add `terraform.tfvars.example` only.
- [ ] Set environment-specific containment behavior and destroyable variables.
- [ ] Wire `modules/ai-runtime-lambda` outputs into IAM, compute-lambda, orchestration, and observability modules.
- [ ] Add environment READMEs.

Validation:

```powershell
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
```

### Task 12: GitHub Actions CI/CD

**Files:**

- Create: `.github/workflows/terraform-ci.yml`
- Create: `.github/workflows/terraform-apply.yml`
- Create: `.github/workflows/drift-detection.yml`

Steps:

- [ ] Add PR workflow for fmt, validate, tflint, pytest, Trivy, and Checkov.
- [ ] Add ECR scan-on-push requirement for AI Engine images.
- [ ] Use GitHub OIDC role assumption.
- [ ] Add plan job that uploads `tfplan` as a restricted artifact.
- [ ] Add apply workflow that downloads and applies the reviewed plan artifact.
- [ ] Configure sandbox apply from `develop`, staging apply from `main`, and prod apply through GitHub environment approval.
- [ ] Add scheduled drift detection using `terraform plan -detailed-exitcode` and alert on drift (never auto-apply).

### Task 13: Final Validation and Evidence

Steps:

- [ ] Run the repository validation script: `.\scripts\validate.ps1`.
- [ ] Run environment init and validate with `-backend=false`.
- [ ] Confirm no tracked files include real secrets, `.tfvars`, state, or plan JSON.
- [ ] Verify that the AI Engine endpoint is private by design.
- [ ] Confirm prod containment remains dry-run only.

---

## 6. Rollback and Recovery Notes

- Do not apply directly to staging or prod from a laptop.
- All staging/prod applies must use reviewed plan artifacts in CI.
- To roll back Lambda code, use alias version rollback or re-apply the previous Terraform revision.
- To roll back Step Functions, re-apply the previous state machine definition from Git.
- To roll back the AI Engine workload, update the task definition with the previous immutable image digest in `modules/ai-runtime-lambda`.
- Rollbacks execute using the cached Boto3 payload from `finops-rollback-cache-{env}` table, which stores the rollback parameters for 90 days.
- Do not delete the state bucket, KMS state key, audit bucket, lakehouse bucket, ECR repositories, or DynamoDB tables during normal rollback.

---

## 7. Implementation Defaults

- Terraform over AWS SAM, CDK, CloudFormation, or Pulumi for platform IaC.
- S3 native lockfile over DynamoDB lock table.
- Lambda (Python 3.13) for CDO adapters and policy workers.
- AWS Lambda Container Platform (Image package type) for the AIOps-provided AI Engine.
- ECR scan-on-push with image tag immutability.
- Private internal HTTPS Application Load Balancer for the AI Engine integration.
- S3, CloudFront with OAC and WAFv2, and Cognito user/identity pools for dashboard hosting.
- Prod containment apply disabled by default and must remain disabled.
- `prevent_destroy` on state, audit, lakehouse, KMS, ECR repositories, and core DynamoDB resources when `destroyable = false`.

---

## 8. Final Self-Review Checklist

- [ ] No real secret values in HCL, YAML, README, examples, or tests.
- [ ] No committed `*.tfvars`, state files, plan files, or plan JSON.
- [ ] No wildcard IAM admin policies.
- [ ] No wildcard trust policy principals.
- [ ] No public S3 buckets.
- [ ] No public AI Engine endpoint.
- [ ] All S3 buckets encrypted and versioned.
- [ ] DynamoDB tables encrypted with CMK.
- [ ] ECR scan-on-push enabled for AI Engine repositories.
- [ ] SNS topics encrypted.
- [ ] GitHub Actions use OIDC and environment approval for prod.
- [ ] Drift detection alerts instead of auto-applying.
- [ ] Prod containment is tag/suggest/dry-run only.
- [ ] AI unavailable, timeout, schema mismatch, and rate limiting paths fail closed.
- [ ] Audit retention is at least 90 days.
- [ ] `terraform fmt -check -recursive` passes.
- [ ] `terraform validate` passes for bootstrap and each environment.
- [ ] `tflint --recursive` passes.
- [ ] `trivy config .` passes.
- [ ] `checkov -d . --framework terraform` passes.
- [ ] `Push-Location lambda_src; python -m pytest; Pop-Location` passes.
