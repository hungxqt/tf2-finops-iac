# Bootstrap

This folder contains Terraform configuration to initialize the remote state backend (S3 bucket and KMS key) and establish GitHub Actions OIDC federation for secure CI/CD deployments.

## Setup Instructions

1. **Initial Run (Local State)**:
   Ensure `backend.tf` is commented out or not present initially, so that Terraform stores the state locally.
   ```bash
   terraform init
   terraform plan -out=bootstrap.tfplan
   terraform apply bootstrap.tfplan
   ```

2. **Migrate to Remote State**:
   Uncomment/configure the backend block in `backend.tf` to point to the newly created S3 bucket, then run:
   ```bash
   terraform init -migrate-state
   ```
