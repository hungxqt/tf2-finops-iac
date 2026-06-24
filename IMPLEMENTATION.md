# TF2 FinOps IaC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Terraform repository skeleton for TF2 FinOps Watch so the team can provision the AWS platform foundation for lakehouse ingestion, scheduled orchestration, CDO-hosted AI Engine integration on EKS, alerting, safe containment, audit evidence, and CI/CD-controlled deployments.

**Architecture:** Terraform is the single source of truth for AWS infrastructure. The platform uses S3/Glue/Athena as the lakehouse data plane, EventBridge Scheduler and Step Functions for 24h orchestration, Lambda for short CDO adapters and policy workers, and EKS for the CDO-hosted AIOps AI Engine runtime. Runtime Kubernetes desired state remains in `tf2-finops-gitops`; this repo owns the EKS cluster, managed node groups, ECR repositories, IRSA/OIDC foundations, private networking, secrets plumbing, and infrastructure integration points.

**Tech Stack:** Terraform `>= 1.10`, AWS provider `>= 5.47, < 6.0`, Python 3.13 Lambda workers, Amazon EKS, managed on-demand and spot node groups, ECR, IRSA/OIDC, Secrets Manager, External Secrets Operator or Secrets Store CSI support, CloudWatch Container Insights, GitHub Actions OIDC, TFLint, Trivy, Checkov, S3 backend with `use_lockfile = true`.

---

## 1. Implementation Contract

### Version and Execution Assumptions

- Runtime: Terraform, not OpenTofu.
- Local checked tools at planning time:
  - Terraform `v1.15.6`
  - TFLint `0.63.1`
  - Trivy `0.71.1`
  - Checkov `3.2.524`
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

If `README.md` or in-repo docs still describe the older Lambda-only scenario, record that as stale guidance and follow `AGENTS.md` plus `../tf2-finops-docs`.

### Risk Categories Addressed

- **State corruption:** S3 backend, versioning, KMS encryption, native lock file, no committed state.
- **Secret exposure:** no committed `.tfvars`, no provider credentials in HCL, Secrets Manager references only, and no webhook/API secret values in examples.
- **Blast radius:** separate environment roots, prod manual approval, `prevent_destroy` on critical resources.
- **CI drift:** pinned runtime/provider versions, reviewed plan artifacts, apply consumes the saved artifact.
- **Compliance gaps:** Trivy, Checkov, TFLint, encrypted storage, audit retention, Object Lock, OIDC, ECR scan-on-push, and EKS private access controls.
- **Provider upgrade risk:** version constraints and lockfile committed after first `terraform init`.
- **Testing blind spots:** module validation, environment validate, Lambda unit tests, EKS static scans, AI contract checks, and security scans.

### Non-Negotiable Guardrails

- AWS only.
- Synthetic data unless real billing access is explicitly granted.
- Default cadence is 24h unless the user changes the approved design.
- CDO owns ingestion, scheduling, idempotency, dashboard views, alert routing, containment guardrails, audit logs, platform SLOs, and the EKS hosting platform.
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
│   ├── alerting/
│   ├── compute-lambda/
│   ├── dashboard/
│   ├── eks/
│   ├── iam/
│   ├── lakehouse/
│   ├── networking/
│   ├── observability/
│   └── orchestration/
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

Use `locals.tf`, `data.tf`, or `policies.tf` inside a module only when `main.tf` becomes difficult to scan.

---

## 3. Module Contracts

### `modules/networking`

Creates the private network foundation for Lambda workers, EKS nodes, VPC endpoints, and internal AI Engine traffic.

Resources:

- VPC with DNS hostnames and DNS support enabled.
- Two public subnets for NAT gateways.
- Private subnets shared by Lambda workers, EKS nodes, internal load balancer resources, and VPC endpoints.
- Internet gateway for public subnets.
- NAT gateway count controlled by environment:
  - sandbox: one NAT gateway.
  - staging/prod: two NAT gateways unless cost override is explicitly set.
- Route tables and associations.
- Lambda security group with no ingress.
- EKS cluster security group.
- EKS node security group.
- Internal AI Engine load balancer security group.
- VPC endpoint security group with HTTPS ingress from Lambda and EKS node security groups.
- Gateway endpoints for S3 and DynamoDB.
- Interface endpoints for KMS, Secrets Manager, Athena, CloudWatch Logs, X-Ray, STS, ECR API, and ECR Docker registry.

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
- `eks_cluster_security_group_id`
- `eks_node_security_group_id`
- `ai_engine_internal_lb_security_group_id`
- `vpc_endpoint_security_group_id`
- `vpc_cidr_block`

Security requirements:

- Do not use the default VPC.
- Use separate `aws_vpc_security_group_ingress_rule` and `aws_vpc_security_group_egress_rule` resources.
- Restrict Lambda egress to HTTPS where service behavior allows it.
- Keep AI Engine traffic private. Do not expose an internet-facing AI endpoint.
- Allow Lambda to reach the internal AI Engine endpoint on HTTPS only.
- Allow EKS nodes to reach VPC endpoints for ECR, Secrets Manager, CloudWatch Logs, S3, and DynamoDB.

### `modules/lakehouse`

Creates durable cost, audit, feature, and query storage.

Resources:

- KMS keys and aliases:
  - data key
  - audit key
  - DynamoDB key
  - EKS node-volume key, if not placed in `modules/eks`
- S3 lakehouse bucket for raw and curated prefixes.
- S3 audit bucket with Object Lock enabled in compliance mode.
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
- `node_volume_kms_key_arn`

Security requirements:

- No unencrypted S3 bucket.
- No public bucket policy.
- Audit bucket Object Lock must be enabled at creation time.
- Critical buckets use `lifecycle { prevent_destroy = true }`.

### `modules/iam`

Creates least-privilege execution roles, platform roles, IRSA foundations, and unsafe-action guardrails.

Resources:

- Step Functions execution role.
- Lambda execution roles:
  - cost puller
  - normalizer
  - AI client
  - router
  - containment worker
  - audit writer
- EKS cluster role.
- EKS node group role.
- IRSA roles:
  - `ai-engine-api` role with read-only model artifact and curated-feature access.
  - `ai-engine-worker` role with scoped checkpoint/output access.
  - external-secrets role with read-only access to named Secrets Manager secrets.
- Permission boundary or explicit deny policy for unsafe automation.
- Cross-account read role policy document for member-account deployment.
- Cross-account containment role policy document for member-account deployment.
- Optional IAM role outputs for GitHub OIDC roles if not handled entirely in `bootstrap/`.

Inputs:

- `project_name`
- `environment`
- `member_account_ids`
- `lakehouse_bucket_arn`
- `audit_bucket_arn`
- `dynamodb_table_arns`
- `kms_key_arns`
- `ai_engine_secret_arn`
- `eks_oidc_provider_arn`
- `eks_oidc_provider_url`
- `containment_apply_enabled`
- `tags`

Outputs:

- `step_functions_role_arn`
- `scheduler_role_arn`
- `lambda_role_arns`
- `eks_cluster_role_arn`
- `eks_node_role_arn`
- `ai_engine_api_irsa_role_arn`
- `ai_engine_worker_irsa_role_arn`
- `external_secrets_irsa_role_arn`
- `permissions_boundary_arn`
- `member_read_policy_json`
- `member_containment_policy_json`

Security requirements:

- No `Action = "*"` policies.
- No wildcard trust principals.
- Do not let AI Engine pods rely on broad node-instance permissions.
- Explicit deny must include IAM modification, organization modification, S3 deletes, DynamoDB deletes, RDS deletes, and EC2 termination.
- Prod roles must not allow `ec2:StopInstances` or other destructive containment apply actions.

### `modules/eks`

Creates the CDO-owned EKS hosting platform for the AIOps-provided AI Engine.

Resources:

- EKS control plane in private subnets.
- EKS access configuration for CI and platform operators.
- EKS managed on-demand node group for stable workloads:
  - `ai-engine-api`
  - `ai-engine-explainer`
  - monitoring
  - ingress/controller support
  - core CDO services that must stay available
- EKS managed spot node group for interruptible workloads:
  - `ai-engine-worker`
  - batch scoring jobs
  - feature engineering jobs
  - model retraining jobs
- ECR repositories for AIOps-provided AI Engine images with scan-on-push enabled.
- EKS add-ons required for secure operation:
  - VPC CNI
  - CoreDNS
  - kube-proxy
  - EBS CSI driver when persistent volumes are needed
- OIDC provider output for IRSA if not created in IAM.
- Internal ALB/NLB prerequisites or private service integration values for the AI Engine endpoint.
- Secrets Manager plumbing for External Secrets Operator or Secrets Store CSI driver.
- CloudWatch Container Insights and EKS control plane logging.
- Autoscaling prerequisites for HPA/KEDA and Cluster Autoscaler or Karpenter.

Inputs:

- `project_name`
- `environment`
- `aws_region`
- `vpc_id`
- `private_subnet_ids`
- `cluster_version`
- `cluster_role_arn`
- `node_role_arn`
- `on_demand_node_group_config`
- `spot_node_group_config`
- `cluster_security_group_id`
- `node_security_group_id`
- `ai_engine_internal_lb_security_group_id`
- `ai_engine_namespace`
- `ai_engine_service_name`
- `ai_engine_contract_version`
- `ai_engine_secret_name`
- `ecr_repository_names`
- `node_volume_kms_key_arn`
- `enable_karpenter`
- `enable_container_insights`
- `tags`

Outputs:

- `cluster_name`
- `cluster_arn`
- `cluster_endpoint`
- `cluster_security_group_id`
- `oidc_provider_arn`
- `oidc_provider_url`
- `on_demand_node_group_name`
- `spot_node_group_name`
- `ecr_repository_urls`
- `ai_engine_internal_endpoint`
- `ai_engine_contract_version`
- `container_insights_log_group_name`

Rules:

- Do not create AI Engine source code, model weights, Helm values, Kubernetes Deployments, or Argo CD `Application` resources in this repo.
- Do not expose the AI Engine publicly.
- Encrypt node EBS volumes.
- Enable ECR scan on push.
- Keep stable API workloads on on-demand capacity and interruptible batch workloads on spot capacity.

### `modules/compute-lambda`

Packages and deploys Lambda worker stubs for CDO adapters and policy workers.

Resources:

- Archive artifacts for each worker from `lambda_src/`.
- Lambda functions:
  - `cost-puller`
  - `normalizer`
  - `ai-client`
  - `router`
  - `containment-worker`
  - `audit-writer`
- Lambda aliases:
  - `stable`
  - `canary`
- Lambda log groups with retention.
- X-Ray active tracing.
- Reserved concurrency limits.
- Optional CodeDeploy application/deployment group for canary in non-sandbox environments.

Inputs:

- `project_name`
- `environment`
- `private_subnet_ids`
- `lambda_security_group_id`
- `lambda_role_arns`
- `lakehouse_bucket_name`
- `audit_bucket_name`
- `dynamodb_table_names`
- `ai_engine_endpoint_url`
- `ai_engine_contract_version`
- `ai_engine_secret_name`
- `ai_engine_timeout_seconds`
- `ai_engine_retry_attempts`
- `containment_apply_enabled`
- `log_retention_days`
- `tags`

Outputs:

- `lambda_function_names`
- `lambda_function_arns`
- `lambda_alias_arns`
- `audit_writer_function_name`
- `ai_client_function_name`

Implementation rules:

- Lambda code is intentionally minimal but deployable. It validates required event fields, logs structured JSON, returns a typed status object, and never applies prod containment.
- `ai-client` calls the internal EKS AI Engine endpoint through the versioned contract.
- If the endpoint URL, secret, contract version, or response schema is invalid, `ai-client` returns an unavailable/error status and never triggers containment directly.

### `modules/orchestration`

Creates scheduled workflow state and control flow.

Resources:

- DynamoDB tables:
  - run state
  - anomaly records
  - routing state
  - containment audit index
  - dashboard materialized views
- Step Functions Standard state machine.
- EventBridge Scheduler schedule with 24h default cadence.
- IAM linkages from scheduler to Step Functions.

Inputs:

- `project_name`
- `environment`
- `scheduler_expression`
- `step_functions_role_arn`
- `scheduler_role_arn`
- `lambda_function_arns`
- `ddb_kms_key_arn`
- `audit_bucket_name`
- `ai_engine_internal_endpoint`
- `ai_engine_contract_version`
- `tags`

Outputs:

- `state_machine_arn`
- `scheduler_arn`
- `dynamodb_table_names`
- `dynamodb_table_arns`

Workflow shape:

```text
EventBridge Scheduler
-> Step Functions
-> idempotency/run-state check
-> cost-puller
-> normalizer
-> ai-client
-> router
-> containment-worker
-> audit-writer
```

Failure behavior:

- Duplicate idempotency key exits without Cost Explorer calls, AI calls, alert, or containment.
- AI unavailable, timeout, schema mismatch, or unsafe recommendation alerts Engineering and fails closed.
- Audit write failure fails closed before containment apply.
- Containment denial writes a denied audit record and alerts Engineering/Security.

### `modules/alerting`

Creates separate business and engineering alert routes.

Resources:

- Finance SNS topic.
- Engineering SNS topic.
- Optional email subscriptions supplied by variables.
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

Creates platform visibility for Step Functions, Lambda, lakehouse freshness, EKS, and AI Engine hosting.

Resources:

- CloudWatch dashboard.
- Metric alarms:
  - workflow failed
  - AI client timeout
  - AI Engine endpoint unavailable
  - audit write failed
  - stale workflow over 26h
  - EKS node group unhealthy
  - spot interruption or excessive pending pods
  - drift detected custom metric emitted by CI
- Log metric filters for structured Lambda status logs.
- Container Insights log groups or integration hooks.

Inputs:

- `project_name`
- `environment`
- `state_machine_arn`
- `lambda_function_names`
- `eks_cluster_name`
- `on_demand_node_group_name`
- `spot_node_group_name`
- `ai_engine_internal_endpoint`
- `engineering_topic_arn`
- `finance_topic_arn`
- `log_retention_days`
- `tags`

Outputs:

- `dashboard_name`
- `alarm_names`

### `modules/dashboard`

Creates dashboard infrastructure hooks without owning dashboard application code.

Resources:

- Athena named queries for finance-friendly cost views.
- Optional QuickSight resource definitions behind `enable_quicksight = false`.

Inputs:

- `project_name`
- `environment`
- `glue_database_name`
- `athena_workgroup_name`
- `enable_quicksight`
- `tags`

Outputs:

- `athena_named_query_ids`
- `quicksight_enabled`

Rule:

- Do not create a dashboard frontend here. Runtime dashboard app config belongs in `tf2-finops-gitops`.

---

## 4. Environment Composition Contract

Each environment root calls all modules and provides only environment-specific values.

### Sandbox

- Backend key: `sandbox/terraform.tfstate`
- `single_nat_gateway = true`
- `containment_apply_enabled = true` only for non-prod/synthetic examples.
- `scheduler_expression = "rate(24 hours)"`
- Log retention: 14 days
- Minimal EKS sizing:
  - on-demand node group: small baseline capacity for `ai-engine-api`.
  - spot node group: enabled only when batch testing is in scope.
- Email subscriptions can be empty by default.
- Used for base build, W12 testing, and synthetic E2E runs.

### Staging

- Backend key: `staging/terraform.tfstate`
- `single_nat_gateway = false`
- `containment_apply_enabled = false`
- `scheduler_expression = "rate(24 hours)"`
- Log retention: 30 days
- EKS on-demand and spot node groups enabled for integration testing.
- Used for AI contract validation, AIOps container artifact validation, E2E testing, and chaos/failure tests.

### Prod

- Backend key: `prod/terraform.tfstate`
- `single_nat_gateway = false`
- `containment_apply_enabled = false`
- `scheduler_expression = "rate(24 hours)"`
- Log retention: 30 days
- EKS control plane and AI Engine endpoint are private only.
- Critical resources use `prevent_destroy`.
- Apply only through GitHub environment approval.
- Production containment is tag, suggest, or dry-run only.

Each root must expose stable outputs for:

- S3 bucket names and ARNs.
- DynamoDB table names and ARNs.
- EKS cluster name and ARN.
- EKS node group names.
- ECR repository URLs.
- AI Engine internal endpoint.
- Step Functions ARN.
- EventBridge Scheduler ARN.
- Lambda names and ARNs.
- SNS topic ARNs.
- CloudWatch dashboard name.

Module call order:

1. networking
2. lakehouse
3. alerting
4. base IAM
5. EKS
6. IAM bindings that need the EKS OIDC provider, if split from base IAM
7. compute-lambda
8. orchestration
9. observability
10. dashboard.

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
- Modify: `README.md` only if the user explicitly expands scope beyond `IMPLEMENTATION.md`

Steps:

- [ ] Add `.gitignore` entries for `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfvars`, `crash.log`, `tfplan`, `tfplan.json`, `.env`, `.build/`, Lambda package zips, and local editor/system files.
- [ ] Add `.terraform-version` with `1.15.6`.
- [ ] Configure TFLint with AWS plugin enabled and Terraform ruleset enabled.
- [ ] Add pre-commit hooks for Terraform fmt, validate, tflint, and basic trailing whitespace checks.
- [ ] Add `scripts/validate.ps1` to run `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate`, `tflint`, `trivy config .`, `checkov -d . --framework terraform`, and `cd lambda_src && python -m pytest`.
- [ ] Add `scripts/package-lambdas.ps1` to create local Lambda zip artifacts under `.build/lambda/`.
- [ ] If README alignment is in scope, update `README.md` with usage flow: bootstrap first, then environment init/plan/apply through CI.

Validation:

```powershell
.\scripts\validate.ps1
```

Expected before Terraform files exist: script should fail with a clear message naming missing roots. After later tasks, it should pass.

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
- [ ] Add `lifecycle { prevent_destroy = true }` to state bucket and KMS key.
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

Apply rule:

- Only run `terraform -chdir=bootstrap apply bootstrap.tfplan` after reviewing the plan.
- After bootstrap apply, migrate bootstrap itself to the S3 backend in a separate commit.

### Task 3: Lambda Worker Stubs and Tests

**Files:**

- Create all files under `lambda_src/`.

Steps:

- [ ] Create shared validation helper requiring `run_id`, `correlation_id`, `cost_period`, `environment`, and `source_data_version`.
- [ ] Create shared response helper returning `status`, `run_id`, `correlation_id`, `worker`, and `details`.
- [ ] Implement `cost_puller/main.go` to return a synthetic `raw_data_uri`.
- [ ] Implement `normalizer/main.go` to return a synthetic `curated_data_uri`.
- [ ] Implement `ai_client/main.go` to call the configured internal AI Engine endpoint only when endpoint URL, secret name, and contract version are present.
- [ ] Make `ai_client/main.go` return `ai_unavailable` or `contract_invalid` on missing endpoint config, timeout, schema mismatch, or unsafe recommendation.
- [ ] Implement `router/main.go` to produce separate Finance and Engineering route decisions.
- [ ] Implement `containment_worker/main.go` to force `dry-run` for `environment = "prod"` regardless of requested action.
- [ ] Implement `audit_writer/main.go` to return an `audit_uri`.
- [ ] Add tests proving every handler accepts the shared contract.
- [ ] Add tests proving AI unavailable does not produce containment apply.
- [ ] Add tests proving prod containment cannot return `apply`.

Validation:

```powershell
Push-Location lambda_src; python -m pytest; Pop-Location
```

Expected: all tests pass without AWS credentials.

### Task 4: Networking Module

**Files:**

- Create: `modules/networking/*`

Steps:

- [ ] Implement VPC, subnets, internet gateway, NAT, routes, and route table associations.
- [ ] Implement Lambda, EKS cluster, EKS node, internal load balancer, and endpoint security groups with separate rule resources.
- [ ] Implement S3 and DynamoDB gateway endpoints.
- [ ] Implement KMS, Secrets Manager, Athena, CloudWatch Logs, X-Ray, STS, ECR API, and ECR Docker interface endpoints.
- [ ] Add variable validations for subnet counts and CIDR shape.
- [ ] Add outputs listed in the module contract.
- [ ] Add `README.md` with input/output tables and example module call.

Validation:

```powershell
terraform fmt -check -recursive modules/networking
```

Validate through `environments/sandbox` after environment composition exists.

### Task 5: Lakehouse Module

**Files:**

- Create: `modules/lakehouse/*`

Steps:

- [ ] Implement KMS keys and aliases for data, audit, DynamoDB, and optional EKS node-volume encryption.
- [ ] Implement lakehouse bucket with raw and curated prefixes represented by documented key conventions.
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
  - `ai/features/`
  - `ai/checkpoints/`

Validation:

```powershell
terraform fmt -check -recursive modules/lakehouse
```

### Task 6: IAM Module

**Files:**

- Create: `modules/iam/*`

Steps:

- [ ] Create policy documents using `aws_iam_policy_document`.
- [ ] Create Step Functions role with Lambda invoke, DynamoDB access, SNS publish, CloudWatch logging, X-Ray permissions, and internal AI invocation permissions where applicable.
- [ ] Create EventBridge Scheduler role.
- [ ] Create one Lambda role per worker class.
- [ ] Create EKS cluster and node group roles.
- [ ] Create IRSA roles for `ai-engine-api`, `ai-engine-worker`, and external-secrets access after the EKS OIDC provider is available.
- [ ] Scope S3 permissions by bucket and prefix.
- [ ] Scope DynamoDB permissions by exact table ARNs.
- [ ] Scope Secrets Manager access to the AI Engine secret only.
- [ ] Create explicit deny boundary for unsafe actions.
- [ ] Ensure prod containment role cannot stop instances or apply quota changes.
- [ ] Output role ARNs and policy JSON documents for member-account setup.

Validation:

```powershell
checkov -d modules/iam --framework terraform
```

Expected: no wildcard-admin or wildcard-trust findings.

### Task 7: EKS AI Engine Hosting Module

**Files:**

- Create: `modules/eks/*`
- Create or update: `docs/progress/eks_hosting_progress.md`
- Create or update: `docs/progress/eks_hosting_progress_vi.md`

Steps:

- [ ] Create EKS control plane in private subnets.
- [ ] Enable EKS control plane logs for API, audit, authenticator, controller manager, and scheduler where supported.
- [ ] Create managed on-demand node group for `ai-engine-api`, `ai-engine-explainer`, monitoring, ingress/controller support, and stable CDO platform pods.
- [ ] Create managed spot node group for `ai-engine-worker`, batch scoring, feature engineering, and retraining jobs.
- [ ] Encrypt node EBS volumes using the configured KMS key.
- [ ] Create ECR repositories for AIOps-provided images with scan-on-push enabled.
- [ ] Configure EKS add-ons for VPC CNI, CoreDNS, kube-proxy, and EBS CSI driver when needed.
- [ ] Expose outputs needed for IRSA role binding: OIDC provider ARN and URL.
- [ ] Provide private AI Engine endpoint integration values for internal ALB/NLB or private ClusterIP-facing integration.
- [ ] Add support flags for External Secrets Operator or Secrets Store CSI driver infrastructure.
- [ ] Add support flags for Container Insights.
- [ ] Add support values for HPA/KEDA and Cluster Autoscaler or Karpenter prerequisites.
- [ ] Document that Kubernetes Deployments, Helm values, and Argo CD applications belong in `tf2-finops-gitops`.
- [ ] Update paired English and Vietnamese EKS progress files with identical facts and section order.

Validation:

```powershell
terraform fmt -check -recursive modules/eks
trivy config modules/eks
checkov -d modules/eks --framework terraform
```

### Task 8: Compute Lambda Module

**Files:**

- Create: `modules/compute-lambda/*`

Steps:

- [ ] Package Lambda source with `archive_file` or consume artifacts from `.build/lambda/`.
- [ ] Create six Lambda functions with environment variables wired from module inputs.
- [ ] Configure VPC attachment to private subnets and Lambda security group.
- [ ] Configure `ai-client` with internal AI Engine endpoint, contract version, timeout, retry attempts, and secret name.
- [ ] Set runtime to `python3.13` and deploy Python zip artifacts with handler `workers.<worker>.handler.handle_request`.
- [ ] Set timeout and memory per worker:
  - cost puller: 120 seconds, 512 MB
  - normalizer: 120 seconds, 512 MB
  - AI client: 30 seconds, 256 MB
  - router: 30 seconds, 256 MB
  - containment worker: 60 seconds, 256 MB
  - audit writer: 30 seconds, 256 MB
- [ ] Enable X-Ray active tracing.
- [ ] Create CloudWatch log groups with retention from input.
- [ ] Create `stable` and `canary` aliases.
- [ ] Keep CodeDeploy optional behind `enable_codedeploy_canary`.

Validation:

```powershell
.\scripts\package-lambdas.ps1
terraform fmt -check -recursive modules/compute-lambda
```

### Task 9: Orchestration Module

**Files:**

- Create: `modules/orchestration/*`

Steps:

- [ ] Create DynamoDB tables using on-demand billing and CMK encryption.
- [ ] Use stable table names that include project and environment.
- [ ] Define keys:
  - run state: `idempotency_key`
  - anomaly records: `anomaly_id`
  - routing state: `route_id`
  - containment audit index: `audit_id`
  - dashboard materialized views: `view_id`
- [ ] Create Step Functions ASL with worker invocation order.
- [ ] Add AI Engine contract version into workflow input.
- [ ] Add retry for transient Lambda failures.
- [ ] Add catch path for AI timeout, unavailable endpoint, contract mismatch, and unsafe recommendation.
- [ ] Add catch path for audit write failure.
- [ ] Create EventBridge Scheduler with 24h default expression.
- [ ] Output state machine ARN, scheduler ARN, and table metadata.

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
- [ ] Add optional email subscriptions controlled by variables.
- [ ] Create CloudWatch alarms for workflow failure, AI timeout, AI Engine endpoint unavailable, audit write failure, stale workflow, EKS node group health, spot interruption or excessive pending pods, and drift-detected metrics emitted by CI.
- [ ] Create CloudWatch dashboard for CDO operations, Lambda status, Step Functions state, EKS node groups, and AI Engine availability.
- [ ] Create Athena named queries for finance-readable spend and anomaly views.
- [ ] Keep QuickSight disabled by default.

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
- [ ] Add providers with default tags.
- [ ] Add common locals for names and tags.
- [ ] Call modules in this order:
  1. networking
  2. lakehouse
  3. alerting
  4. base iam
  5. eks
  6. iam bindings that need the EKS OIDC provider, if split from base IAM
  7. compute-lambda
  8. orchestration
  9. observability
  10. dashboard
- [ ] Add `terraform.tfvars.example` only; do not commit real `.tfvars`.
- [ ] Set environment-specific containment behavior exactly as defined in Section 4.
- [ ] Set environment-specific EKS node group sizing defaults.
- [ ] Wire `modules/eks` outputs into IAM, Lambda, orchestration, and observability modules.
- [ ] Add environment READMEs with init, plan, and apply commands.

Validation:

```powershell
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
```

### Task 12: GitHub Actions CI/CD

**Files:**

- Create: `.github/workflows/terraform-ci.yml`
- Create: `.github/workflows/terraform-apply.yml`
- Create: `.github/workflows/drift-detection.yml`

Steps:

- [ ] Add PR workflow for fmt, validate, tflint, Lambda tests, Trivy, and Checkov.
- [ ] Add EKS/module-specific static checks for `modules/eks`.
- [ ] Add AI contract compatibility check against the configured contract version and AIOps-provided schema artifact when available.
- [ ] Add ECR scan-on-push requirement for AI Engine images.
- [ ] Use GitHub OIDC role assumption; do not use static AWS keys.
- [ ] Use normal `pull_request`, not `pull_request_target`.
- [ ] Avoid direct `${{ github.event.* }}` interpolation inside shell commands; pass untrusted values through `env`.
- [ ] Pin third-party non-GitHub actions to full commit SHAs during implementation.
- [ ] Add plan job that uploads `tfplan` as a restricted artifact.
- [ ] Add apply workflow that downloads and applies the reviewed plan artifact.
- [ ] Configure sandbox apply from `develop`, staging apply from `main`, and prod apply through GitHub environment approval.
- [ ] Add scheduled drift detection using `terraform plan -detailed-exitcode`; alert or create issue on exit code 2; never auto-apply drift.

Validation:

```powershell
trivy config .github/workflows
```

### Task 13: Final Validation and Evidence

**Files:**

- Modify: progress files relevant to implemented features.
- Modify: `README.md` only if the user requests documentation alignment beyond this implementation plan.

Steps:

- [ ] Run the repository validation script.
- [ ] Run environment init and validate with `-backend=false`.
- [ ] Run `terraform fmt -check -recursive`.
- [ ] Run `tflint --recursive`.
- [ ] Run `trivy config .`.
- [ ] Run `checkov -d . --framework terraform`.
- [ ] Run `trivy config modules/eks`.
- [ ] Run `checkov -d modules/eks --framework terraform`.
- [ ] Run `Push-Location lambda_src; python -m pytest; Pop-Location`.
- [ ] Capture outputs in a local evidence note or PR comment.
- [ ] Confirm no tracked files include real secrets, `.tfvars`, state, or plan JSON.
- [ ] Record any stale mismatch in `README.md` or in-repo docs compared with `../tf2-finops-docs`.

Validation command:

```powershell
.\scripts\validate.ps1
```

Acceptance criteria:

- All Terraform roots validate locally with `-backend=false`.
- Lambda tests pass without AWS credentials.
- EKS module static checks pass or findings are documented with accepted capstone rationale.
- No security scan finding contradicts the hard guardrails.
- The AI Engine endpoint is private by design.
- ECR repositories have scan-on-push enabled.
- IRSA roles are scoped by service account and namespace.
- Prod containment is tag/suggest/dry-run only.
- The repo can produce a reviewed plan for `sandbox` after bootstrap is applied.

---

## 6. Rollback and Recovery Notes

- Do not apply directly to staging or prod from a laptop.
- All staging/prod applies must use reviewed plan artifacts in CI.
- To roll back non-destructive changes, revert the PR and apply the previous reviewed plan.
- To roll back Lambda code, use alias rollback or re-apply the previous Terraform revision.
- To roll back Step Functions, re-apply the previous state machine definition from Git.
- To roll back EKS workload desired state, revert the corresponding `tf2-finops-gitops` commit; do not manage workload manifests directly here.
- To roll back EKS infrastructure, review the Terraform plan carefully and preserve cluster, node group, IAM, and data dependencies unless a full teardown is explicitly approved.
- Do not delete state bucket, KMS state key, audit bucket, lakehouse bucket, ECR repositories, or DynamoDB tables during normal rollback.
- If a lock is stuck, investigate active CI/local Terraform processes before using `terraform force-unlock`.
- Keep S3 state bucket versioning enabled; state recovery uses object version restore, not manual state editing.

---

## 7. Implementation Defaults

- Terraform over AWS SAM, CDK, CloudFormation, or Pulumi for platform IaC.
- S3 native lockfile over DynamoDB lock table.
- Lambda for CDO adapters and policy workers.
- EKS for CDO-hosted AIOps AI Engine runtime and batch workloads.
- On-demand node groups for stable API, explainer, ingress/controller support, monitoring, and core CDO services.
- Spot node groups for `ai-engine-worker`, batch scoring, feature engineering, and retraining jobs.
- ECR scan-on-push for AIOps-provided images.
- IRSA for pod-level AWS access.
- Private internal AI Engine endpoint only.
- CloudWatch-native observability plus Container Insights for capstone scope.
- QuickSight disabled by default until dashboard ownership is confirmed.
- Synthetic data path enabled by default.
- Prod containment apply disabled by default and must remain disabled.
- `prevent_destroy` on state, audit, lakehouse, KMS, ECR repositories, and core DynamoDB resources.

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
- [ ] EKS node EBS volumes encrypted.
- [ ] ECR scan-on-push enabled for AI Engine repositories.
- [ ] IRSA configured for AI Engine API, worker, and external secrets access.
- [ ] AI Engine pods do not rely on broad node-instance permissions.
- [ ] On-demand and spot node groups are separated by labels, taints, tolerations, or documented scheduling constraints.
- [ ] SNS topics encrypted.
- [ ] GitHub Actions use OIDC and environment approval for prod.
- [ ] Drift detection alerts instead of auto-applying.
- [ ] Prod containment is tag/suggest/dry-run only.
- [ ] AI unavailable, timeout, schema mismatch, and unsafe recommendation paths fail closed.
- [ ] Audit retention is at least 90 days.
- [ ] `terraform fmt -check -recursive` passes.
- [ ] `terraform validate` passes for bootstrap and each environment.
- [ ] `tflint --recursive` passes.
- [ ] `trivy config .` passes or findings are documented with accepted capstone rationale.
- [ ] `checkov -d . --framework terraform` passes or findings are documented with accepted capstone rationale.
- [ ] `trivy config modules/eks` passes or findings are documented with accepted capstone rationale.
- [ ] `checkov -d modules/eks --framework terraform` passes or findings are documented with accepted capstone rationale.
- [ ] `Push-Location lambda_src; python -m pytest; Pop-Location` passes.
