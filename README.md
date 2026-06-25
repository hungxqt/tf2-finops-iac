# TF2 FinOps IaC

This repository is the Infrastructure as Code (IaC) home for **Task Force 2 - FinOps Watch**. Its purpose is to define and provision the AWS platform foundation that runs the FinOps cost ingestion, anomaly workflow integration, ECS/Fargate hosting platform for the AI Engine, alerting, dashboards, containment guardrails, and audit trail.

---

## 1. Purpose & Scope

This repository provisions all foundational AWS infrastructure needed before the FinOps Watch workloads and AIOps-provided AI Engine can run.

### In Scope (What this repository owns)
* **VPC Networking**: Private subnets, NAT Gateways, and secure routing.
* **Lakehouse Storage**: S3 raw/curated/audit zones, Glue Data Catalog, and Athena views.
* **ECS/Fargate Hosting Platform**: Private ECS Cluster, Fargate and Fargate Spot capacity providers, internal ALB, Route 53 private DNS, ECR repositories, and task execution/task roles.
* **Serverless Orchestration**: Step Functions Standard workflows, EventBridge Scheduler, Python 3.13 Lambda workers, and DynamoDB run-state tables.
* **Security & IAM**: KMS keys, least-privilege IAM roles for ingestion/containment, and keyless GitHub OIDC authentication.
* **Observability & Dashboards**: CloudWatch container metrics, metrics hooks, alerting pipelines, and Athena-backed dashboard configurations.

### Out of Scope (What this repository does NOT own)
* **AI Model Code & Internals**: Model selection, training/retraining logic, explanation prose, and classification algorithms (owned by AIOps).
* **Runtime Workload Manifests**: ECS Task definition task/container configurations belong here, but the model code/binaries are pulled from ECR.
* **External Documentation**: Business design updates or architecture rewrites (owned by `tf2-finops-docs`).

---

## 2. Directory Structure

A quick guide to the layout of this repository (see [SKELETON.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/SKELETON.md) for details):
* `bootstrap/`: Initial state backend and GitHub OIDC setup.
* `environments/`: Sandbox, staging, and production environment compositions.
* `modules/`: Reusable Terraform modules (networking, ai-runtime-lambda, lakehouse, IAM, etc.).
* `lambda_src/`: Python 3.13 source code and tests for the serverless adapter workers.
* `docs/`: Architecture designs, repository structure details, and development guides.
* `scripts/`: Utilities for packaging Lambdas and code validation.

---

## 3. Developer & Operator Guides

Detailed onboarding workflows, deployment procedures, validation checks, and operational playbooks are maintained in:
* **English**: [GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md)
* **Vietnamese**: [GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md)

Please read these guides carefully before starting development or triggering Terraform plans/applies.

---

## 4. FinOps Guardrails

All infrastructure and workflows provisioned by this repository must adhere to the following strict safety guardrails:
* **AWS Only**: The entire platform relies exclusively on AWS native services.
* **Synthetic Data Default**: Unless explicit billing access is provided, synthetic cost data is utilized.
* **Dry-Run First**: Automated containment actions must run in dry-run first mode.
* **No Destructive Actions**: Containment actions must **NEVER** terminate production resources, delete data, or modify IAM policies.
* **Fail-Closed Design**: If the AI Engine is unavailable or schema validation fails, the orchestrator fails closed, logs run states, alerts operators, and writes audit trails.
* **Audit Retention**: Comprehensive audit logs must be kept in the audit S3/DynamoDB zones for a minimum of 90 days.
* **Private ECS Hosting**: No public ingress for the AI Engine or cluster; all communication is restricted to internal VPC endpoints and internal ALB.
