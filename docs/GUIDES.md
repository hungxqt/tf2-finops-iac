# TF2 FinOps IaC Developer Guide

This guide outlines the step-by-step workflow for developers and operators working with the **Task Force 2 - FinOps Watch** Infrastructure as Code (IaC) repository.

---

## 1. Prerequisites
Ensure you have the following tools installed and configured:
* **Terraform** (>= 1.10)
* **AWS CLI** (configured with administrator credentials)
* **Python** (>= 3.13) & `pip` (for local worker testing)
* **PowerShell** (for packaging scripts on Windows)

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

### Step 2.4: Deploy the Target Environment (Composition)
Deploy environments sequentially (Sandbox first, followed by Staging and Prod).

#### Environment Backend and Variable Setup:
* **Remote State Connection**: The remote state backend block is already pre-configured in `backend.tf` for each environment (`sandbox/terraform.tfstate`, `staging/terraform.tfstate`, `prod/terraform.tfstate`). You only need to run `terraform init` to automatically connect to the shared remote S3 state.
* **Variable Configuration**: Before planning or applying, you must copy the `terraform.tfvars.example` file in the environment directory to a local `terraform.tfvars` file (which is git-ignored) and update the values (such as ECR Image URIs and ACM Certificate ARNs) as appropriate for your deployment.

1. **Sandbox Deployment**:
   ```powershell
   cd environments/sandbox
   # Copy variables template and populate it
   cp terraform.tfvars.example terraform.tfvars
   # Initialize and connect to remote state
   terraform init
   # Provide the required alb_certificate_arn variable (e.g. via tfvars or command line)
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


### Step 3.1: Dashboard Deployment & Asset Handoff
Once the Terraform plan is applied, the dashboard infrastructure is ready. The handoff process follows these rules:
1. **Terraform Roles**: Terraform only provisions the underlying AWS assets (S3 buckets, CloudFront distribution, Cognito Identity & User Pools, Athena named queries, and IAM data access role).
2. **Asset Upload**: Static frontend assets (the UI app) must be uploaded separately to the static asset S3 bucket (configured in the output `dashboard_asset_bucket_name`).
3. **Cognito Administration**: Real Cognito users, groups, and passwords must be administered directly in the AWS Console or via Cognito API/CLI outside of Terraform.
4. **Data Generation**: Cost-data writers/summarizers (e.g., Lambda functions or batch jobs) must publish JSON summaries to the configured prefix (e.g., `summaries/`) inside the dashboard data S3 bucket (configured in the output `dashboard_data_bucket_name`).

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
checkov -d modules/orchestration --framework terraform
```

---

## 5. Guide Maintenance
This developer guide must be kept current. Future agents and contributors must update both `docs/GUIDES.md` and `docs/GUIDES_vi.md` in the same change whenever a developer/operator workflow, command sequence, validation path, script, CI job, deployment step, or handoff procedure is added or changed.

