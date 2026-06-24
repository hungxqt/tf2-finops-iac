# Production Environment Root

This directory contains the production environment composition root.

## Deploying Production (Dry-run / Plan Verification only via CI)

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
