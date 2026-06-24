# Sandbox Environment Root

This directory contains the sandbox environment composition root.

## Deploying Sandbox Locally

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
