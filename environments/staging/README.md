# Staging Environment Root

This directory contains the staging environment composition root.

## Deploying Staging Locally (Dry-run / Validation)

1. **Initialize**:
   ```bash
   terraform init -backend=false
   ```
2. **Validate**:
   ```bash
   terraform validate
   ```
3. **Plan**:
   ```bash
   terraform plan -var-file=terraform.tfvars
   ```
