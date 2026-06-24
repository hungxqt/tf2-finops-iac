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

1. **Deploy local bootstrap**:
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
         kms_key_id   = "arn:aws:kms:ap-southeast-1:123456789012:key/some-key-id"
         use_lockfile = true
       }
     }
     ```
   - Migrate state:
     ```powershell
     terraform init -migrate-state
     ```

### Step 2.3: Package Lambda Zip Files
Package the 7 Python adapter functions into the `.build/lambda/` folder:
```powershell
cd ..
.\scripts\package-lambdas.ps1
```

### Step 2.4: Deploy the Target Environment (Composition)
Deploy environments sequentially (Sandbox first, followed by Staging and Prod).

1. **Sandbox Deployment**:
   ```powershell
   cd environments/sandbox
   terraform init
   terraform plan -out=sandbox.tfplan
   terraform apply sandbox.tfplan
   ```
2. **Staging Deployment**:
   ```powershell
   cd ../staging
   terraform init
   terraform plan -out=staging.tfplan
   terraform apply staging.tfplan
   ```
3. **Production Deployment** (Requires plan review and approval):
   ```powershell
   cd ../prod
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

The outputs supply critical connection endpoints:
* `cluster_name`: Kubernetes EKS cluster name.
* `ecr_repository_urls`: Repository endpoints for target workload images.
* `state_machine_arn`: Orchestrator State Machine ARN.
* `dynamodb_table_names`: Ingestion, state, and audit table mappings.

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
trivy config modules/eks
checkov -d modules/eks --framework terraform
```

---

## 5. Guide Maintenance
This developer guide must be kept current. Future agents and contributors must update both `docs/GUIDES.md` and `docs/GUIDES_vi.md` in the same change whenever a developer/operator workflow, command sequence, validation path, script, CI job, deployment step, or handoff procedure is added or changed.

