# TF2 FinOps IaC Developer Guide

This guide outlines the step-by-step workflow for developers and operators working with the **Task Force 2 - FinOps Watch** Infrastructure as Code (IaC) repository.

---

## 1. Prerequisites
Ensure you have the following tools installed and configured:
* **Terraform** (>= 1.10)
* **AWS CLI** (configured with administrator credentials)
* **Python** (>= 3.13) & `pip` (for local worker testing)
* **PowerShell** (for packaging scripts on Windows)

### 1.1 Cross-Account Telemetry Prerequisites (Optional)
If your deployment involves pulling cost and utilization telemetry from separate AWS member accounts:
1. **Payer/CDO Account Configuration**:
   - Set the `telemetry_member_account_ids` input variable to the list of member account IDs.
   - Configure the CUR source bucket and prefix using `cur_source_bucket_arn` and `cur_source_prefix` in the `iam` module parameters.
2. **Member Account Role Setup**:
   - Each member account must deploy the telemetry ingestion IAM role (`cdo-telemetry-ingestion-role`).
   - The role trust policy must authorize the CDO cost-puller IAM role ARN from the Payer/CDO account.
   - The role permissions policy must grant read access (`s3:ListBucket`, `s3:GetObject`) to the local CUR bucket/prefix, and allow querying Cost Explorer (`ce:GetCostAndUsage`) and CloudWatch metrics (`cloudwatch:GetMetricData`).

---

## 2. Step-by-Step Deployment Workflow

### Step 2.1: Run Local Tests
Verify the adapter functions are contract-compliant by running Python pytest suite:
```powershell
cd lambda_src
pip install -r requirements-dev.txt
python -m pytest
cd ..
```

### Step 2.2: Bootstrap the State Backend and OIDC Role
Bootstrapping sets up keyless GitHub authentication (OIDC) and creates the remote state storage bucket.

#### Option A: Initial Setup / First-time Bootstrapping (Done Once)
If this is the first time setting up the project and the S3 backend is not yet active:
1. **Deploy local bootstrap**:
   Ensure the `backend "s3"` block in [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) is commented out, then run:
   ```powershell
   cd bootstrap
   terraform init
   terraform apply
   ```
2. **Migrate State to S3**:
   - Copy the outputted state KMS Key ARN.
   - Open [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) and uncomment the `terraform` backend block, replacing `kms_key_id` with your ARN:
     ```hcl
     terraform {
       backend "s3" {
         bucket       = "tf2-finops-state-bucket"
         key          = "bootstrap/terraform.tfstate"
         region       = "ap-southeast-1"
         encrypt      = true
         kms_key_id   = "arn:aws:kms:ap-southeast-1:093490087544:key/f0382479-e89e-41af-8041-89d10f275bf4"
         use_lockfile = true
       }
     }
     ```
   - Migrate state to the remote S3 bucket:
     ```powershell
     terraform init -migrate-state
     ```

#### Option B: Teammates Continuing Work (For Subsequent Developers)
If the bootstrap has already been run once and the S3 backend configuration is active in the repository:
1. **Initialize Backend**:
   Directly initialize Terraform. It will detect the active S3 backend block in [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) and connect to the existing remote state:
   ```powershell
   cd bootstrap
   terraform init
   ```
   *Note: Teammates do not need to run `apply` or `migrate-state` in the bootstrap folder unless making changes to the bootstrap infrastructure itself.*

### Step 2.3: Package Lambda Zip Files
Package the 7 Python adapter functions into the `.build/lambda/` folder:
```powershell
cd ..
.\scripts\package-lambdas.ps1
```

### Step 2.4: Deploy the CodeBuild Publishing Layer
The `codebuild` root owns the shared ECR repository and CodeBuild wrapper image publishing pipeline. Apply this root before deploying the main environments.
```powershell
cd codebuild
terraform init
terraform apply
```

### Step 2.5: Build the Lambda Web Adapter Wrapper Image
Trigger the manual CodeBuild project with a valid upstream AIOps digest:
```powershell
aws codebuild start-build \
  --project-name tf2-finops-ai-wrapper-build \
  --environment-variables-override name=UPSTREAM_IMAGE_URI,value=200000000012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2/finops-ai-engine@sha256:456c2438cb20d88047915518b209d88047915518b209d88047915518b209d880,type=PLAINTEXT
```

### Step 2.6: Read the Deployed Wrapper Image URI
Read the latest published image digest URI from SSM Parameter Store:
```powershell
aws ssm get-parameter --name "/tf2-finops/shared/ai-wrapper/latest-image-uri" --query "Parameter.Value" --output text
```

### Step 2.7: Deploy the Target Environment (Composition)
Deploy environments sequentially (Sandbox first, followed by Staging and Prod).

#### Environment Backend and Variable Setup:
* **Remote State Connection**: The remote state backend block is already pre-configured in `backend.tf` for each environment (`sandbox/terraform.tfstate`, `staging/terraform.tfstate`, `prod/terraform.tfstate`). You only need to run `terraform init` to automatically connect to the shared remote S3 state.
* **Variable Configuration**: Before planning or applying, copy the `terraform.tfvars.example` file in the environment directory to a local `terraform.tfvars` file (which is git-ignored) and update the values. You MUST set `request_image_uri` to the wrapper image URI retrieved from SSM Parameter Store in Step 2.6.
* **EventBridge Scheduler Activation Guard**: By default, the EventBridge Scheduler daily run schedule is disabled (`scheduler_enabled = false`) to prevent automated Step Functions executions immediately after initial infrastructure apply. Verify that the outputs show `scheduler_state = "DISABLED"`. Activating scheduled daily runs requires a separate, reviewed and approved plan setting `scheduler_enabled = true`.

1. **Sandbox Deployment**:
   ```powershell
   cd ../environments/sandbox
   # Copy variables template and populate it
   cp terraform.tfvars.example terraform.tfvars
   # Initialize and connect to remote state
   terraform init
   # Plan and apply
   terraform plan -out=sandbox.tfplan
   terraform apply sandbox.tfplan
   ```
2. **Staging Deployment**:
   ```powershell
   cd ../staging
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=staging.tfplan
   terraform apply staging.tfplan
   ```
3. **Production Deployment** (Requires plan review and approval):
   ```powershell
   cd ../prod
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=prod.tfplan
   # Production apply requires verification and is triggered via GitHub Environments
   terraform apply prod.tfplan
   ```

### Step 2.8: Post-Apply Lambda Diagnostics
VPC-attached Lambda functions (both zip-based workers and container-based AI runtimes) require AWS-side provisioning of Hyperplane ENIs and image optimization. This process runs asynchronously after the Terraform apply completes and can take several minutes.

Run the following diagnostics loop (AWS CLI) to check the status of all 9 Lambda functions:

For PowerShell (Windows):
```powershell
$workers = "state", "cost_puller", "normalizer", "router", "audit_writer", "containment_worker", "vpc_alb_caller", "ai-request", "ai-worker"
foreach ($w in $workers) {
    aws lambda get-function --function-name "tf2-finops-sandbox-$w" --query "Configuration.[FunctionName, State, StateReason, LastUpdateStatus]" --output json
}
```

For Bash (macOS/Linux):
```bash
for fn in state cost_puller normalizer router audit_writer containment_worker vpc_alb_caller ai-request ai-worker; do
  aws lambda get-function --function-name tf2-finops-sandbox-$fn --query "Configuration.[FunctionName, State, StateReason, LastUpdateStatus]" --output table
done
```

**Verification Criteria:**
* **State**: Should eventually be `Active`. (If it is `Pending`, wait 1-2 minutes for AWS control-plane processes to finish).
* **StateReason**: Should be empty or null. If it mentions ENI creation errors or missing permissions, check the IAM roles and security groups.
* **LastUpdateStatus**: Should eventually be `Successful`.

### 2.4. Teardown / Destroy Sandbox Environment

To destroy the sandbox environment for cleanups or testing teardowns:
1. Generate the destroy plan:
   ```powershell
   cd environments/sandbox
   terraform plan -destroy -out=sandbox-destroy.tfplan
   ```
2. Review the generated plan to verify the resources being destroyed.
3. Apply the destroy plan:
   ```powershell
   terraform apply sandbox-destroy.tfplan
   ```

> [!WARNING]
> **AWS Object Lock Teardown Limitation**: 
> If the sandbox audit bucket already contains compliance-mode retained object versions, AWS enforces a hard restriction that prevents deleting these versions until their retention period expires. In this case, Terraform will fail to delete the audit bucket itself. Compliance-mode object lock is disabled for *newly created* sandbox audit buckets to make teardowns possible, but if retention was previously enabled and objects exist, they must expire before full teardown can succeed.
>
> **AWS Lambda VPC ENI Teardown Delay**:
> When destroying a VPC-attached Lambda environment, AWS Lambda keeps the Hyperplane ENIs cached for up to 20 minutes after the Lambda functions themselves have been deleted. During this cooldown period, Terraform will display `Still destroying...` and appear to hang on deleting the private subnets and the Lambda security group because they remain linked to these active network interfaces. This is expected AWS control-plane behavior. Do not interrupt the process; once AWS asynchronously releases the ENIs (typically within 10 to 15 minutes), the subnets and security group will be successfully deleted and the Terraform destroy will complete.

Staging and production environments are strictly protected by a count-conditional `destroy_guard` sentinel resource and cannot be destroyed using a standard destroy plan.

---

## 3. Post-Deployment GitOps Handoff
Once applied, fetch the Outputs to feed the Application Layer (`tf2-finops-gitops`):
```powershell
terraform output
```

* `private_alb_endpoint`: The HTTPS base URL for accessing the private ALB (either Route 53 private DNS alias or internal ALB DNS name).
* `private_alb_dns_name`: The raw DNS name of the internal ALB.
* `private_alb_security_group_id`: The security group ID of the internal ALB.
* `request_lambda_function_name`: AI Engine Request Lambda function name (container-based, invoked via internal ALB target group on port 443).
* `worker_lambda_function_name`: AI Engine Worker Lambda function name (container-based, processes asynchronous anomaly ingestion).
* `ecr_repository_url`: ECR Repository URL for Lambda container images.
* `state_machine_arn`: Orchestrator State Machine ARN.
* `dynamodb_table_names`: Ingestion, state, results, audit, and rollback cache table mappings.
* `synchronous_ai_endpoints`: The endpoints `/v1/detect`, `/v1/decide`, and `/v1/verify` are synchronous operations called via `VpcAlbCallerLambda` and Route 53 private DNS alias. `/v1/status/{id}` is for remediation audit/status only, not for detection polling. There is no detection SQS or polling loop in the default path; SQS is restricted to alert retry and `finops-watch-rollback` audit completion notifications.


### Step 3.1: Dashboard Deployment & Asset Handoff
Once the Terraform plan is applied, the dashboard infrastructure is ready. The handoff process follows these rules:
1. **Terraform Roles**: Terraform provisions the underlying AWS assets, S3 buckets, CloudFront distribution (excluding VPC Origin/origin Lambda@Edge configurations), Cognito Identity & User Pools, Athena named queries, and IAM roles.
2. **Authenticated Front Door**: All static assets and JSON summaries (under `/${dashboard_data_prefix}*`) are served via CloudFront and protected by the viewer-request Lambda@Edge function using Cognito PKCE auth.
3. **No Direct API Proxying (Disabled)**: Direct `/v1/*` proxying through CloudFront is disabled because AWS does not support origin-request Lambda@Edge associations with CloudFront VPC origins. Direct AI queries and containment actions continue to run securely through the `VpcAlbCallerLambda` integration path.
4. **Asset Upload**: Static frontend assets for the UI shell must be built and uploaded independently to the static asset S3 bucket (configured in the output `dashboard_asset_bucket_name`). Terraform only provisions the private bucket, CloudFront front door, Cognito access control, and the non-secret `dashboard_runtime_config.json` object; it does not publish UI files automatically.
5. **Cognito Groups**: Users should be added to the created Cognito groups (`finops-finance-readonly`, `finops-engineering-operator`, `finops-cdo-admin`) to control authorization.
6. **Data Generation**: Cost-data writers must publish JSON summaries to the configured prefix (e.g., `summaries/`) inside the dashboard data S3 bucket (configured in the output `dashboard_data_bucket_name`).


### Step 3.2: Account Policy DynamoDB Seeding
Before running or enabling the Orchestrator Step Functions workflow (either manually or via the EventBridge scheduler), you must seed the environment's `account-policy` DynamoDB table.
With the multi-account analysis targets capability, the orchestrator runs in the management/CDO account but fans out over target linked member accounts specified in `analysis_target_account_ids` (configured via `telemetry_member_account_ids` in each environment root).
Therefore, you must seed a row for each target linked/member AWS Account ID being analyzed, not only the executing management account.
Refer to the dedicated [ACCOUNT_POLICY_SEEDING.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING.md) guide for detailed item schema specifications, PowerShell command sequences, and verification troubleshooting steps.


---

## 4. Continuous Integration & Code Validation
Before committing modifications, run the full validation suite locally:
```powershell
# Format code
terraform fmt -check -recursive

# Validate configurations
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate

# Verify static security analysis
trivy config .
checkov -d . --framework terraform
```

---

## 5. Glue Schema & Partition Projection Validation

To support automated and cost-effective querying without maintaining resource-heavy crawlers or scheduling manual repair queries, the lakehouse uses Athena Partition Projection.

### Step 5.1: Verify Terraform glue table configurations
Run the focused module test to assert partition keys, input/output formats, and static table configurations:
```powershell
cd modules/lakehouse
terraform init
terraform test
cd ../..
```

### Step 5.2: Validate Athena DDL Matching Schemas
To inspect, debug, or manually check the schema definitions and parameters for the Parquet `cur_data` and JSON `containment_audit` tables, review the validation script:
* [scripts/athena_validation.sql](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/athena_validation.sql)

Ensure the table projection ranges (e.g. `2024,2035`), formats, and S3 partition locations exactly align with the worker output paths.

---

## 7. Telemetry Ingestion Configuration and Validation

The `cost_puller` worker acquires raw billing and utilization telemetry. It operates in a hybrid ingestion mode, reading CUR files from the source S3 bucket or falling back to Cost Explorer when CUR updates are delayed.

### Step 7.1: Configuration Parameters
The ingestion behavior is controlled by these Terraform variables passed to the `compute_lambda` module:
* `cur_source_bucket`: S3 bucket where AWS CUR is delivered.
* `cur_source_prefix`: Prefix path in the source bucket for CUR files.
* `cur_delay_threshold_hours`: Delay threshold in hours before switching to CE fallback (default: `36`).
* `ce_lookback_window_days`: Days of CE history retrieved during fallback (default: `30`).
* `traffic_metric_identifiers`: Identifiers for querying physical traffic metrics (e.g., ALB names).

There is no generated telemetry fallback. `cost_puller` requires a configured lakehouse bucket and CUR source bucket for normal ingestion. If CUR is delayed and Cost Explorer returns no records, or if cached telemetry is unavailable during CE throttling, the worker returns `CUR_DELAY` or `CE_THROTTLED` and the workflow must remain dry-run/alert-only.

### Step 7.2: Verification and Simulation
Operators can verify the retry/wait and error-handling state machine branches using simulation actions in the execution event:
* **Simulate CUR Delay**: Send `"action": "simulate-cur-delay"` to force CUR delayed status and trigger the Cost Explorer fallback path. The worker still requires real Cost Explorer records or cached telemetry to continue.
* **Simulate CE Throttling**: Send `"action": "simulate-ce-throttled"` to throttle CE requests. If cached telemetry exists in the destination bucket, it will recover telemetry and set the `stale_cost_explorer` quality flag; otherwise, it returns `CE_THROTTLED`.

Verify the gzipped JSON raw envelopes outputted by checking S3 key prefixes:
* Main Cost Telemetry: `s3://<lakehouse-bucket>/cur/account_id=<id>/year=YYYY/month=MM/day=DD/<run-id>_raw.json.gz`
* Utilization Features: `s3://<lakehouse-bucket>/features/account_id=<id>/year=YYYY/month=MM/day=DD/<run-id>_features.json.gz`

---

## 8. Containment Worker — Local Development & Testing

The `containment_worker` is a production-grade Lambda that executes containment actions against
member account resources. Because it makes real AWS API calls (EC2, RDS, SageMaker, STS, S3,
DynamoDB), all tests use **moto** to mock the AWS layer — no real AWS credentials or resources
are required to run the suite locally.

### 8.1 Install Dev Dependencies

```powershell
cd lambda_src
pip install -r requirements-dev.txt
```

This installs `moto[ec2,rds,s3,dynamodb,sts]>=5.0.0` alongside `pytest` and `boto3`.

### 8.2 Run All Tests

```powershell
# From repo root
Push-Location lambda_src; python -m pytest; Pop-Location
```

### 8.3 Run Only Containment Worker Tests

```powershell
Push-Location lambda_src
# Full containment suite
python -m pytest tests/test_containment_worker.py -v

# Only hard-boundary tests (no moto needed — fast)
python -m pytest tests/test_containment_worker.py -v -k "boundary"

# Only audit/S3/DynamoDB tests (requires moto)
python -m pytest tests/test_containment_worker.py -v -k "audit"

# Only action-dispatch tests (requires moto)
python -m pytest tests/test_containment_worker.py -v -k "actions"
Pop-Location
```

### 8.4 Key Hard Boundaries — What to Verify

| Scenario | Input | Expected `execution_mode_applied` | Expected `status` |
|---|---|---|---|
| Prod environment + apply | `environment=prod`, `execution_mode=apply` | `dry-run` | `dry-run` |
| Low confidence | `data_confidence=LOW`, `execution_mode=apply` | `dry-run` | `dry-run` |
| Approval denied | `approval_status=denied` | `denied` | `denied` |
| Sandbox apply (approved) | `environment=sandbox`, `approval_status=approved` | `apply` | `completed` |
| Prod tag (allowed) | `environment=prod`, `execution_mode=tag` | `tag` | `completed` |

### 8.5 Verify S3 and DynamoDB Audit After a Real Run (Sandbox)

After invoking the Lambda against a live sandbox environment using test events from
`containment-lambda/test-events/`:

```bash
aws lambda invoke \
  --function-name tf2-finops-sandbox-containment_worker \
  --payload file://containment-lambda/test-events/01_dry_run_sandbox.json \
  --cli-binary-format raw-in-base64-out \
  output.json && cat output.json
```

**S3 Audit** — two files must appear (pre-action + post-action):
```
s3://company-cdo-{account_id}-telemetry/audit/year=YYYY/month=MM/{audit_id}.json
s3://company-cdo-{account_id}-telemetry/audit/year=YYYY/month=MM/{audit_id}_post.json
```

**DynamoDB Dashboard Cache** — one item per anomaly:
```
Table : finops-dashboard-cache-{env}
Key   : anomaly_id = "<anomaly_id from event>"
Fields: status, execution_mode_applied, audit_record_s3_uri
```

**DynamoDB Rollback Cache** — cached before action execution:
```
Table : finops-rollback-cache
Key   : anomaly_id = "<anomaly_id from event>"
Fields: boto3_equivalent, ttl_epoch (90-day TTL)
```

> **Note (Denied scenario):** When `approval_status=denied` the Lambda returns immediately.
> Nothing is written to S3 or DynamoDB — this is the expected behavior.

---

## 9. Guide Maintenance
This developer guide must be kept current. Future agents and contributors must update both `docs/GUIDES.md` and `docs/GUIDES_vi.md` in the same change whenever a developer/operator workflow, command sequence, validation path, script, CI job, deployment step, or handoff procedure is added or changed.

---

## 10. Step Functions Workflow Verification

The `test_step_function_payload_contract.py` suite provides a **repo-local, no-AWS verification layer** that proves:

- The ASL has every required state (44+ states checked).
- No stale async-detection polling states, detection queues, or detection SQS references exist.
- Every Task/Pass state can resolve its JSONPath references against real fixture data from the preceding state's output.
- The telemetry contract is honoured (S3_POINTER default, CE fallback, quality gates).
- The /v1/detect, /v1/decide, /v1/verify call shapes match the active AI API contract.
- Prod+destructive containment modes are denied; dry-run forced paths are denied.
- Only `rollback_status_queue` SQS queue exists (no detection queue).
- Fail-closed and CUR-delay-exceeded audit chains carry all required context fields.

### 10.1 Run Payload Contract Tests Only

```powershell
Push-Location lambda_src
python -m pytest tests/test_step_function_payload_contract.py -v
Pop-Location
```

### 10.2 Run All Step Functions Verification Tests

```powershell
Push-Location lambda_src
python -m pytest -q tests/test_step_function_payload_contract.py tests/test_state_machine.py tests/test_step_function_lambda_coverage.py tests/test_vpc_alb_caller.py
Pop-Location
```

### 10.3 Run the Full Suite

```powershell
Push-Location lambda_src
python -m pytest
Pop-Location
```

Expected result: **all tests pass, zero failures**.

### 10.4 Fixture Reference

Deterministic fixtures are in [`lambda_src/tests/fixtures/step_function_payloads.py`](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/fixtures/step_function_payloads.py).
Each fixture is a plain Python dict representing the Step Functions execution context (`$`) at a specific workflow boundary.
Adding a new state or changing an existing state's Parameters/ResultPath requires updating the matching fixture and adding/updating the relevant test.

### 10.5 Lightweight JSONPath Resolver

The `_resolve_path(ctx, path)` helper in the test file resolves:

| Expression | Meaning |
|-----------|---------|
| `"$"` | Entire context dict |
| `"$.a.b.c"` | Nested key traversal |
| `"$.anomalies_list[0].anomaly_id"` | Array index 0, then key |

This is sufficient for all `Parameters` (JSONPath `key.$`) and `Choice` variable expressions used by this state machine, without a full ASL runtime.

---

## 11. AI Request Integrity Deployment Gate

The `scripts/test-ai-request-integrity.ps1` script is a **post-apply deployment gate** that validates request integrity of the deployed `VpcAlbCallerLambda` → private internal ALB → AI Request Lambda path before promoting a container image to the next environment.

### 11.1 When to Run

Run this gate **after every `terraform apply`** that changes any of the following:
- `modules/compute-lambda` (vpc_alb_caller function code or environment variables)
- `modules/ai-runtime-lambda` (AI Request Lambda image or ALB configuration)
- `modules/iam` (vpc_alb_caller execution role or idempotency policy)
- AI Engine container image promotion from sandbox → staging → prod

### 11.2 How to Run

```powershell
# After sandbox apply (minimum gate before promoting to staging)
.\scripts\test-ai-request-integrity.ps1 -Environment sandbox

# After staging apply (required before prod promotion)
.\scripts\test-ai-request-integrity.ps1 -Environment staging

# With an explicit function name (if the naming convention was overridden)
.\scripts\test-ai-request-integrity.ps1 -Environment sandbox -LambdaFunctionName my-vpc-alb-caller
```

> [!IMPORTANT]
> The script requires AWS CLI to be configured with credentials that can invoke the target Lambda function.

### 11.3 Probe Types and Acceptance Criteria

The gate runs four probes. **All must pass** for the environment to be considered compliant:

| # | Probe | Type | Acceptance Criteria |
|---|-------|------|---------------------|
| 1 | `POSITIVE_DETECT` | Positive | Signed `/v1/detect` call succeeds (no FunctionError, no 5xx) |
| 2 | `REPLAY_STALE_TS` | Negative | Stale `X-Request-Timestamp` must fail closed (FunctionError or 400 `ERR_REPLAY_DETECTED`) |
| 3 | `MISSING_AUTH` | Negative | Missing credentials must raise `ConfigMissingError` / `ERR_AUTH_FAILED` (fail-closed) |
| 4 | `HASH_MISMATCH` | Negative | Mismatched `X-Payload-SHA256` must fail closed (FunctionError or 4xx `ERR_PAYLOAD_HASH`) |

> [!NOTE]
> **ALB/SigV4 Boundary**: The private internal ALB does not itself enforce SigV4 at the listener level. Request integrity is enforced at the AI Request Lambda/container level. Probe 2, 3, and 4 test that the AI Lambda correctly rejects invalid requests. If the AI Engine image cannot pass these probes, block promotion and record the runtime as non-compliant.

### 11.4 Non-Compliance Handling

If any probe fails, the script exits with code 1 and writes a results JSON to `docs/progress/request_integrity_gate_results_{environment}.json`.

**Do not claim section-3 compliance until all four probes pass.**

When the AI Engine image cannot pass the negative probes (because the container does not enforce replay/auth/hash validation), record the gap in `docs/progress/request_integrity_progress.md` and add an explicit capstone exception note. Do not suppress or bypass the gate.

### 11.5 Gate Results Reference

Results are written to `docs/progress/request_integrity_gate_results_{environment}.json` after each run. This file is git-ignored and is for local operator reference only. The CI `terraform-apply.yml` workflow step should call this script and fail the job if the exit code is non-zero.

```json
{
  "timestamp": "2026-06-27T14:30:00Z",
  "environment": "sandbox",
  "lambda": "tf2-finops-sandbox-vpc_alb_caller",
  "compliance_status": "COMPLIANT",
  "probes": [
    {"name": "POSITIVE_DETECT", "passed": true},
    {"name": "REPLAY_STALE_TS", "passed": true},
    {"name": "MISSING_AUTH",    "passed": true},
    {"name": "HASH_MISMATCH",   "passed": true}
  ]
}
```

---

## 12. CodeBuild Wrapper Image Publish Guide

The repository includes a CodeBuild project to build and publish the AI Engine wrapper image. The wrapper copies the AWS Lambda Web Adapter into the upstream AIOps FastAPI container, allowing it to execute properly on the AWS Lambda platform.

### 12.1 Manual Execution Workflow

The build must be triggered manually by an operator. The operator must provide the upstream image URI pinned by its digest. Mutable tags (such as `:latest`) are rejected to guarantee image immutability.

To start a build using the AWS CLI, run:

```bash
aws codebuild start-build \
  --project-name tf2-finops-sandbox-ai-wrapper-build \
  --environment-variables-override name=UPSTREAM_IMAGE_URI,value=200000000012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2/finops-ai-engine@sha256:456c2438cb20d88047915518b209d88047915518b209d88047915518b209d880,type=PLAINTEXT
```

*(Replace `sandbox` with `staging` or `prod` as appropriate, and replace the `--project-name` and `value` with the correct project name and upstream digest).*

### 12.2 Rebuild Skipping Behavior

If the generated wrapper image tag (`wrapped-<upstream-digest-short>`) already exists in the target ECR repository, the CodeBuild execution will skip the Docker build and push phases, return the existing digest, and write the URIs to SSM Parameter Store.

### 12.3 SSM Parameter Store Recording

After a successful run, CodeBuild writes the following parameters to the SSM Parameter Store:
- `/tf2-finops/<env>/ai-wrapper/latest-image-uri`: The URI of the wrapper image pinned by digest.
- `/tf2-finops/<env>/ai-wrapper/latest-upstream-image-uri`: The original upstream image URI.

These parameters are used by operators during standard Reviewed Terraform Deployments to update the `request_image_uri` variable.

---

## 13. Sandbox AI Lambda CodeDeploy Rollout Guide

The repository configures CodeDeploy-controlled linear traffic shifting for the AI Engine Request Lambda in `modules/ai-runtime-lambda`, scoped initially to the `sandbox` environment.

### 13.1 Rollout Configuration
- **Deployment Strategy**: CodeDeploy shifts traffic using the `CodeDeployDefault.LambdaLinear10PercentEvery1Minute` configuration.
- **Service Role**: AWS CodeDeploy is assigned an IAM role attached to the `AWSCodeDeployRoleForLambda` managed policy.
- **Target Alias**: The `live` Lambda alias is used. Terraform is configured to ignore version and routing drift on this alias (`lifecycle { ignore_changes = [function_version, routing_config] }`), handing full control of traffic shifting to CodeDeploy.

### 13.2 Automated Rollback Alarms
The deployment group is associated with four automated CloudWatch alarms that trigger an automatic rollback if they fire during a deployment:
1. **Lambda Errors**: Fires if `Errors` metric > 0.
2. **Lambda Throttles**: Fires if `Throttles` metric > 0.
3. **P99 Duration**: Fires if the P99 execution time exceeds 800 ms.
4. **ALB Target 5xx**: Fires if the internal ALB target group encounters any `HTTPCode_Target_5XX_Count` > 0.

If any of these alarms are triggered during the traffic-shifting phase, CodeDeploy automatically rolls back the `live` alias traffic to the previous version and fails the deployment.

### 13.3 Manual or CI Scripted Rollout
To deploy a new image wrapper version via CodeDeploy:
1. Build and publish the image using CodeBuild to write the digest to SSM.
2. Run Terraform plan/apply with the new digest. Terraform publishes the new Lambda version but leaves the `live` alias pointing to the old version.
3. Run the deployment script to trigger and monitor CodeDeploy:
   ```powershell
   ./scripts/start-ai-lambda-codedeploy.ps1 `
     -ApplicationName "finops-watch-sandbox-ai-request" `
     -DeploymentGroupName "finops-watch-sandbox-ai-request-dg" `
     -FunctionName "finops-watch-sandbox-ai-request" `
     -AliasName "live" `
     -TargetVersion "<new-published-version>"
   ```
4. The script polls every 15 seconds, outputting the rollout status. If CodeDeploy rolls back or fails, the script exits with code `1`, causing the CI/CD pipeline to fail.


