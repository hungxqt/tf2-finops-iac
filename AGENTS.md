# AGENTS.md - TF2 FinOps IaC Implementation Guide

## Purpose

This repository is the Terraform infrastructure-as-code home for **Task Force 2 - FinOps Watch**. Agents working here must implement AWS platform infrastructure according to the repository skeleton below, the new EKS-based scenario documented in `../tf2-finops-docs`, the task plan in `IMPLEMENTATION.md`, and the read-only architecture documents in `tf2-finops-docs`.

This file is authoritative for implementation agents. When instructions conflict, follow this priority order:

1. Explicit user instructions in the current conversation.
2. This `AGENTS.md`.
3. Scenario authority from `../tf2-finops-docs/AGENTS.md`, `../tf2-finops-docs/TF2_FINOPS_LEARNER.md`, and `../tf2-finops-docs/docs/tf2-finops/`.
4. `IMPLEMENTATION.md`.
5. `README.md`.
6. Read-only reference documents under `./docs/tf2-finops/`.

If `IMPLEMENTATION.md` or `README.md` still describes the older Lambda/serverless-only scenario, treat that as stale guidance. Follow this file plus `../tf2-finops-docs` for the current scenario and report the mismatch.

## Repository Scope

This repo owns:

- Terraform modules and environment roots for sandbox, staging, and production.
- Remote state bootstrap, locking, and CI plan/apply controls.
- AWS cost-data platform resources: S3 raw/curated/audit zones, Glue Data Catalog, Athena workgroup, and related KMS keys.
- Scheduled workflow resources: EventBridge Scheduler, Step Functions Standard, Lambda workers, and DynamoDB run-state tables.
- CDO-owned EKS hosting platform for the AIOps-provided AI Engine: EKS control plane, private managed node groups, ECR repositories, IRSA/OIDC foundations, internal service exposure, secrets-injection infrastructure, autoscaling hooks, and Container Insights plumbing.
- Finance and Engineering alert routing, dashboard infrastructure hooks, containment audit records, and operational observability.
- Least-privilege IAM roles for CDO workflow execution, read-only cost ingestion, and tightly scoped non-prod containment.
- AI Engine integration infrastructure: endpoint configuration, authentication secret references, timeout/retry/circuit-breaker settings, unavailable-AI fallback wiring, and evidence/audit storage paths.

This repo does not own:

- AI model code, anomaly detection internals, training algorithms, retraining logic, explanation logic, model versions, confidence scoring, or backtest implementation.
- Runtime workload manifests, Helm values, Argo CD applications, or application desired state after the EKS platform exists. Those belong to `tf2-finops-gitops`.
- Business documentation or design-doc rewrites.
- Runtime desired state belonging to `tf2-finops-gitops`.

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
│   ├── eks/
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
- Use Terraform as the platform IaC tool for AWS infrastructure, including EKS. Do not replace the platform design with AWS SAM, CDK, CloudFormation, Pulumi, or application workload manifests.
- Keep each module focused on one responsibility. Do not create a single large module that owns all resources.
- Keep environment-specific values in `environments/*`. Do not hardcode sandbox, staging, or prod choices inside reusable modules.
- Use `terraform.tfvars.example` for examples only. Do not commit real `.tfvars`.
- Use S3 backend with `use_lockfile = true` for long-lived state. Do not add a DynamoDB lock table for new state.
- Keep GitHub Actions authentication keyless through OIDC. Do not add static AWS credentials to workflow files.
- Use reviewed plan artifacts for apply workflows. Do not re-run `terraform plan` inside apply jobs.
- Drift detection must alert or open an issue. It must not auto-apply changes.
- Keep Lambda worker code minimal, deployable, contract-validating, and safe by default.
- Use Lambda for short CDO adapters and policy workers. Use EKS for the CDO-hosted AI Engine runtime and batch workloads.
- Keep Kubernetes workload deployment state in `tf2-finops-gitops`; Terraform may create the cluster, add-ons, node groups, ECR repositories, IAM roles, IRSA/OIDC bindings, security groups, internal load-balancer prerequisites, and secrets infrastructure.
- Configure AI Engine integration through versioned contract inputs: contract version, internal endpoint URL, auth secret name or ARN, timeout, retry policy, circuit-breaker behavior, and fail-closed fallback behavior.
- If the AI Engine is unavailable, fails schema validation, times out, or returns an unsafe recommendation, fail closed for containment: do not apply automatic containment, alert operators, preserve run state, and write an audit record.
- Place stable AI Engine API workloads such as `ai-engine-api`, `ai-engine-explainer`, monitoring, and core CDO services on on-demand node groups.
- Place interruptible AI Engine workloads such as `ai-engine-worker`, batch scoring jobs, feature engineering jobs, and model retraining jobs on spot node groups with retry/backoff and checkpoint storage expectations.
- Support EKS scaling through HPA/KEDA for pods and Cluster Autoscaler or Karpenter for node capacity. Use node affinity, taints, and tolerations to keep on-demand and spot workloads separate.
- Use `prevent_destroy` for state, audit, lakehouse, KMS, and core DynamoDB resources.

## EKS AI Engine Hosting Contract

The current scenario requires CDO to host the AIOps-owned AI Engine on EKS while preserving the model ownership boundary.

`modules/eks` must own infrastructure for:

- EKS control plane in private subnets.
- Managed on-demand node group for stable API, explainer, monitoring, and core CDO workloads.
- Managed spot node group for `ai-engine-worker`, batch scoring, feature engineering, and retraining jobs.
- ECR repositories for AIOps-provided container images, with image scanning enabled.
- EKS OIDC provider and IRSA role foundations for AI Engine API, worker, and secrets access service accounts.
- Internal AI Engine service exposure through internal ALB/NLB prerequisites or a private ClusterIP-facing integration path.
- Secrets Manager access plumbing for External Secrets Operator or Secrets Store CSI driver.
- CloudWatch Container Insights, EKS control plane logs, node logs, and metrics hooks.
- Autoscaling prerequisites for HPA/KEDA and Cluster Autoscaler or Karpenter.

Expected inputs include:

- `project_name`
- `environment`
- `aws_region`
- `vpc_id`
- `private_subnet_ids`
- `cluster_version`
- `on_demand_node_group_config`
- `spot_node_group_config`
- `ai_engine_namespace`
- `ai_engine_service_name`
- `ai_engine_contract_version`
- `ai_engine_secret_name`
- `ecr_repository_names`
- `enable_karpenter`
- `enable_container_insights`
- `tags`

Expected outputs include:

- `cluster_name`
- `cluster_arn`
- `cluster_endpoint`
- `cluster_security_group_id`
- `oidc_provider_arn`
- `on_demand_node_group_name`
- `spot_node_group_name`
- `ecr_repository_urls`
- `ai_engine_internal_endpoint`
- `ai_engine_api_irsa_role_arn`
- `ai_engine_worker_irsa_role_arn`
- `external_secrets_irsa_role_arn`

Do not create or maintain AI Engine source code, model weights, model configuration internals, Kubernetes Deployment manifests, Helm chart values, or Argo CD `Application` resources in this repo unless the user explicitly changes repository ownership.

## Read-Only Documentation Sources

These files are reference material for implementation. Agents must read them when the implementation touches matching behavior, but must not edit them unless the user explicitly asks for documentation changes.

### In-repo references (`./docs/tf2-finops/`)

- `./docs/tf2-finops/01_requirements_analysis.md`
- `./docs/tf2-finops/02_infra_design.md`
- `./docs/tf2-finops/03_security_design.md`
- `./docs/tf2-finops/04_deployment_design.md`

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

If implementation progress reveals that a design document is stale, record the discrepancy in `docs/progress/` and mention it in the final response. Do not patch the docs repo.

## FinOps Watch Guardrails

All implementation must preserve these hard requirements:

- AWS only.
- Synthetic data unless real billing access is explicitly provided.
- Default cadence is 24h unless the user changes the approved design.
- The scenario architecture is lakehouse-centric FinOps control plane with serverless orchestration and AIOps-owned AI Engine integration.
- CDO owns cost ingestion, normalized cost windows, ownership/tag metadata, scheduling, idempotency, workflow state, dashboard views, alert routing, containment guardrails, audit logs, platform SLOs, and the EKS hosting platform.
- AIOps owns anomaly detection logic, model selection, training/retraining design, model versioning, confidence scoring, classification, explanation text, AI Engine code/model internals, and backtest metrics.
- Finance and Engineering alert routing must remain separate.
- Dashboard infrastructure must support finance-readable views and must not require Finance users to know SQL.
- Containment must be dry-run first.
- Production containment is tag, suggest, or dry-run only.
- Audit records must capture actor, timestamp, correlation ID, idempotency key, anomaly ID, target owner, before state, proposed or applied after state, execution mode, rollback path, approval status, retention location, and retention period.
- Audit retention must be at least 90 days.
- Automated containment must **NEVER terminate prod, delete data, or modify IAM**.

## Required Implementation Order

Use this order unless the user asks for a smaller scoped change:

1. Baseline repository hygiene and validation scripts.
2. `bootstrap/` state backend and GitHub OIDC.
3. `lambda_src/` worker stubs and tests.
4. `modules/networking`.
5. `modules/lakehouse`.
6. Base `modules/iam` roles and policies needed by networking, lakehouse, Lambda, and EKS.
7. `modules/eks` AI Engine hosting platform: cluster, on-demand and spot node groups, ECR, IRSA, internal exposure prerequisites, secrets plumbing, scaling hooks, and Container Insights.
8. `modules/compute-lambda`.
9. `modules/orchestration`, including AI Engine endpoint/contract wiring and fail-closed behavior.
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
docs/progress/eks_hosting_progress.md
docs/progress/eks_hosting_progress_vi.md
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

- Update both `docs/GUIDES.md` and `docs/GUIDES_vi.md` in the same change whenever a new working flow is added or an existing flow changes.
- A "working flow" includes bootstrap, backend migration, Lambda packaging/testing, Terraform init/validate/plan/apply, environment deployment, drift detection, security scans, CI jobs, Makefile/script usage, EKS infrastructure handoff, and any new required manual operator step.
- Do not update guides for purely internal implementation changes that do not change commands, order of operations, prerequisites, or operator/developer behavior.
- If no guide update is needed, the final response must explicitly say `No guide impact` with a short explanation.
- Keep `docs/GUIDES.md` and `docs/GUIDES_vi.md` factually equivalent, with the same section order and command blocks. Translate prose in Vietnamese, but keep technical names, commands, file paths, and AWS service names in English.
- If a new flow is planned but not validated, document it as planned or blocked, not as a completed workflow.

## Validation Requirements

Run the narrowest relevant validation after each meaningful change. Before calling a task complete, run the broad validation set when the files exist:

```powershell
terraform fmt -check -recursive
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
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

When EKS or AI Engine hosting infrastructure is touched, also run the narrowest available checks for the changed surface:

```powershell
terraform fmt -check -recursive modules/eks
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
trivy config modules/eks
checkov -d modules/eks --framework terraform
```

If Kubernetes manifests or Helm charts are present because the user explicitly expanded this repo's ownership, validate them with `helm lint`, schema checks, and policy scans. Otherwise, keep workload manifest validation in `tf2-finops-gitops`.

## Security Rules

- Do not commit AWS access keys, secret values, API keys, real webhook URLs, private certificates, state files, plan files, or plan JSON.
- Do not put secret values in variable defaults, examples, workflow files, logs, or progress docs.
- Do not output full secret ARNs plus secret values together.
- Do not create IAM policies with wildcard administrative permissions.
- Do not create wildcard trust policies.
- Do not create public S3 buckets.
- Encrypt S3, DynamoDB, SNS, CloudWatch log destinations where supported, and Terraform state.
- Enforce TLS-only S3 bucket policies.
- Use separate security group rule resources instead of inline ingress or egress blocks.
- Keep prod apply behind GitHub environment approval.
- Keep EKS control plane and AI Engine runtime access private; do not expose the AI Engine through a public internet endpoint.
- Use IRSA for pod-level AWS access. Do not let AI Engine pods rely on broad node-instance permissions.
- Encrypt EKS node EBS volumes and enable control plane audit/API/authenticator logs where supported.
- Use separate security group rule resources for EKS cluster, node group, Lambda, VPC endpoint, and internal load balancer traffic.
- Do not grant AI Engine API or worker pods permissions to terminate prod resources, delete data, modify IAM, or bypass containment policy.
- Store AI Engine auth material and external webhooks in Secrets Manager. Mount or sync them to EKS workloads through External Secrets Operator or Secrets Store CSI driver only when runtime ownership is explicitly in scope.
- Enable ECR scan on push for AIOps-provided images and block deployment guidance on critical image findings unless the user documents an accepted capstone exception.

## Final Response Expectations

When finishing work in this repo, the agent must report:

- Files created or modified.
- Which skeleton area was implemented.
- Validation commands run and their outcomes.
- Any commands that could not run and why.
- Progress files updated in English and Vietnamese.
- `docs/GUIDES.md` and `docs/GUIDES_vi.md` updated, or `No guide impact` with a short reason.
- Any discovered mismatch between implementation and read-only docs.
- Any stale guidance found in `README.md`, `IMPLEMENTATION.md`, or in-repo `./docs/tf2-finops/**` compared with the current `../tf2-finops-docs` EKS scenario.

Do not claim success for unvalidated infrastructure. Use precise status such as "created", "validated", "planned", or "blocked".
