# TF2 FinOps IaC Repository Architecture & Structure

This document provides a detailed overview of the structure, design patterns, and components of the Infrastructure-as-Code (IaC) repository for **Task Force 2 - FinOps Watch**.

---

## 1. Directory Structure Overview

The repository is organized following standard Terraform best practices to separate reusable logic (modules), environment configurations (roots), bootstrap components, runtime execution binaries (Lambda), and CI/CD pipelines.

```text
tf2-finops-iac/
├── .github/
│   └── workflows/              # GitHub Actions CI/CD workflows
│       ├── terraform-ci.yml    # Linting, formatting, tests, and planning
│       ├── terraform-apply.yml # Target environment deployments
│       └── drift-detection.yml # Scheduled drift scanning
├── bootstrap/                  # Remote state and identity bootstrapping
│   ├── README.md
│   ├── backend.tf              # Backend configuration (migrated to S3 after bootstrap)
│   ├── locals.tf
│   ├── main.tf                 # KMS, S3 bucket, OIDC provider, execution roles
│   ├── outputs.tf
│   ├── providers.tf
│   ├── variables.tf
│   └── versions.tf
├── docs/                       # Architectural and progress documentation
│   ├── progress/               # Feature tracking files (EN & VI pairs)
│   └── SKELETON.md             # Deep-dive repository structure description
├── environments/               # Environment composition roots
│   ├── sandbox/                # Fast iteration environment
│   ├── staging/                # Integration and pre-production testing
│   └── prod/                   # Production environment (manual gate checks)
├── lambda_src/                 # Serverless Python Lambda worker source code
│   ├── requirements.txt        # Production dependencies (boto3, etc.)
│   ├── requirements-dev.txt    # Development/testing dependencies (pytest, etc.)
│   ├── src/
│   │   ├── finops_common/      # Shared utilities, dataclasses, validation, and responses
│   │   └── workers/            # Serverless Python Lambda workers
│   │       ├── state/          # Manages execution context and idempotency checks
│   │       ├── cost_puller/    # Cost data ingestion worker
│   │       ├── normalizer/     # Transforms/standardizes raw cost schema to normalized format
│   │       ├── router/         # Routes anomalies to alerting topics
│   │       ├── audit_writer/   # Writes workflow logs & containment audit trails to S3/DynamoDB
│   │       ├── containment_worker/ # Executes safe containment/remediation actions
│   │       └── vpc_alb_caller/ # Performs IAM SigV4 requests to private internal ALB for AI Engine
│   └── tests/                  # Pytest unit tests for all workers and common logic
├── modules/                    # Reusable, single-responsibility Terraform modules
│   ├── ai-runtime-lambda/      # ECR digest-pinned Lambda container runtime behind private internal ALB
│   ├── alerting/               # Separate SNS routes for Finance and Engineering
│   ├── compute-lambda/         # Deployment definitions for Python zip Lambda workers
│   ├── dashboard/              # S3 static assets, CloudFront, Cognito user/identity pools
│   ├── iam/                    # Least-privilege roles and permissions boundary
│   ├── lakehouse/              # S3 buckets, Object Lock, Glue Catalog, and KMS keys
│   ├── networking/             # Private VPC subnets and VPC Interface endpoints
│   ├── observability/          # CW Dashboards and CloudWatch alarms
│   └── orchestration/          # DynamoDB tables and Step Functions state machine
├── scripts/                    # Automation utilities
│   ├── validate.ps1            # Code formatting, linting, and testing verification
│   └── package-lambdas.ps1     # Python zip bundling utility
├── .gitignore                  # Git pattern ignore configuration
├── .pre-commit-config.yaml     # Hooks to prevent bad formatting/commits
├── .terraform-version          # Pinned version constraint for Terraform execution
├── .tflint.hcl                 # Custom linter configurations
├── Makefile                    # Simple build, test, and validation aliases
└── README.md                   # Repository entry point documentation
```

---

## 2. Core Architectural Design Patterns

### A. Reusable Modules vs. Compositions
- **Modules (`modules/`)**: Own single-responsibility, logical components. They contain generic code with parameters/variables, but no environment-specific configuration or hardcoded secrets.
- **Compositions (`environments/`)**: Compositions instantiate the modules by supplying environment-specific parameter values. This ensures that staging and production environments use identical infrastructure definitions with customized configurations.

### B. Remote State Security
- A bootstrap layer (`bootstrap/`) is created locally to provision an S3 state bucket and a KMS customer managed key (CMK).
- All compositions configure an S3 remote backend pointing to this bucket.
- **Locking**: Native S3 State Lock (using `use_lockfile = true` starting in Terraform 1.10) is used to prevent concurrent modifications. No extra DynamoDB locking tables are needed.
- **Encryption**: Bucket access is TLS-only. Objects are encrypted at rest via the state KMS key.

### C. OIDC Authentication
- Deployments do not require static, long-lived AWS IAM credentials.
- The `bootstrap/` layer creates a GitHub OIDC identity provider linked to the repository.
- Workflow runners assume short-lived, branch-scoped IAM role sessions to execute planning and applying actions securely.

---

## 3. Detailed Component Breakdown

### A. Terraform Modules (`modules/`)
1. **`networking`**: Creates a private VPC with two public subnets (hosting NAT Gateways) and two private subnets (hosting Lambda workers). Ingress to the private subnets is blocked. Gateway and interface endpoints are defined for required AWS APIs (S3, DynamoDB, KMS, Secrets Manager, Athena, CloudWatch Logs, X-Ray, STS) to keep traffic inside the AWS backbone.
2. **`lakehouse`**: Creates S3 storage zones with Object Lock configured in compliance mode for the Audit bucket (minimum 90 days retention). Sets up bucket versioning, lifecycle transitions, TLS-only policies, KMS keys (for data, audit logs, and DynamoDB), a Glue Catalog database, and an Athena workgroup with byte scan cutoff protection.
3. **`iam`**: Implements least-privilege AWS execution roles. A permission boundary enforces strict controls: preventing IAM modifications, organization modifications, RDS deletes, EC2 terminations, and S3 deletes. Remediations in production must never terminate servers or mutate policies/data.
4. **`ai-runtime-lambda`**: Deploys ECR digest-pinned Lambda container runtime (AI Engine Request Lambda and Worker Lambda) behind a private internal Application Load Balancer (ALB) and maps private DNS lookup names via Route 53 private hosted zones.
5. **`compute-lambda`**: Deploys the seven Python worker functions (`state`, `cost_puller`, `normalizer`, `router`, `audit_writer`, `containment_worker`, and `vpc_alb_caller`) as VPC-attached Lambda functions running on the standard `python3.13` managed runtime. Configures timeouts, memory sizes, reserved concurrency, active X-Ray tracing, stable/canary deployment aliases, and code signing.
6. **`orchestration`**: Provisions DynamoDB on-demand, encrypted tables to manage state (run state, anomaly list, alert routing index, containment audit trail, materialized views, and rollback-cache). Builds the Step Functions Standard state machine mapping the data processing workflow.
7. **`alerting`**: Establishes separate SNS notification topics for Finance (cost alerts, digests) and Engineering (infrastructure health, errors) to keep concern boundaries clear. Alarms use dedicated KMS keys for topic encryption.
8. **`observability`**: Builds the operational CloudWatch dashboard and registers metric filters and alarms for workflow failures, AI engine timeouts, stale runs (>26h), and CI configuration drift.
9. **`dashboard`**: Hosts static assets in S3, delivered via CloudFront, authenticated by Cognito user/identity pools, and integrates Athena named queries for finance-readable spent reports with QuickSight as a future optional BI integration.

### B. Environment Composition Roots (`environments/`)
Each directory calls the eight core modules sequentially. Environment profiles dictate behaviour:

| Parameter / Guardrail | Sandbox | Staging | Production |
| :--- | :--- | :--- | :--- |
| **State Key** | `sandbox/terraform.tfstate` | `staging/terraform.tfstate` | `prod/terraform.tfstate` |
| **NAT Gateways** | `1` (Cost optimized) | `2` (High availability) | `2` (High availability) |
| **Containment Action** | `apply` (Remediation active) | `dry-run` | `dry-run` (Never destruct) |
| **Log Retention** | `14 Days` | `30 Days` | `30 Days` |
| **CI Gate** | Automatic apply | Merge to main apply | Manual approval gate |
| **Critical Resource Protection** | Normal | Normal | `prevent_destroy = true` |

---

## 4. Lambda Subsystem (`lambda_src/`)

All workers are implemented in **Python (3.13)** to facilitate native compatibility with CDO adapter frameworks and AWS runtime management:
- **`finops_common`**: Holds shared utilities, dataclasses, validation, and standard response helpers.
- **`workers`**: Houses individual packages for each of the seven workers. Handlers conform to the `workers.<worker>.handler.handle_request` signature.
- **Build / Deploy Packaging**: The `package-lambdas.ps1` script packages each Python function together with required dependencies (from `requirements.txt`) into individual zip files under `.build/lambda/` for deployment.
- **Unit Testing**: Unit tests reside under the `tests/` directory and can be executed via `pytest` (`Push-Location lambda_src; python -m pytest; Pop-Location`).

---

## 5. Repository Validation & Hygiene

A series of tools are automated locally and in CI to guarantee compliance:
- **Terraform Linter**: Custom configurations inside `.tflint.hcl` evaluate rule violations.
- **Terraform Formatting**: Standardised HCL format enforced via `terraform fmt -check -recursive`.
- **Security Checkers**: 
  - **Trivy**: Scans IAC patterns and third-party workflow imports.
  - **Checkov**: Validates secure HCL attributes (verifies no wildcard trust relationships, no public S3 buckets, and proper encryption/logging mappings).
  - **Validation Wrapper**: `validate.ps1` bundles syntax checking, testing, and security scanning into a single executing command.
