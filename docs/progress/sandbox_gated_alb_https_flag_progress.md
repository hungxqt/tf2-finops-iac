# Sandbox-Gated ALB HTTPS Flag Progress

## Status
Validated (all tests passing, Terraform validation completed)

## Scope
Configure `enable_alb_https` as a Terraform boolean (defaulting to true) to control:
- ALB listener protocol (HTTPS / HTTP) and ports (443 / 80).
- `VpcAlbCallerLambda`'s `ALB_BASE_URL` scheme (`https` / `http`).
- Validation rules ensuring HTTP mode is rejected in staging and production, and only allowed in sandbox.
- Egress/ingress security group rules dynamic configuration based on HTTP/HTTPS mode.

## Files Changed
- [modules/ai-runtime-lambda/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/variables.tf) - Added `enable_alb_https` variable.
- [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf) - Updated internal ALB listener and SG ingress rules to be dynamic based on HTTPS/HTTP mode.
- [modules/compute-lambda/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/variables.tf) - Added `allow_insecure_alb_http` variable.
- [modules/compute-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/main.tf) - Passed `ALLOW_INSECURE_ALB_HTTP` environment variable to `vpc_alb_caller` Lambda, and added a conditional HTTP egress SG rule for Lambda.
- [lambda_src/src/workers/vpc_alb_caller/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/vpc_alb_caller/handler.py) - Updated `validate_alb_base_url` to reject `http://` unless `ALLOW_INSECURE_ALB_HTTP=true`.
- [lambda_src/tests/test_vpc_alb_caller.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_vpc_alb_caller.py) - Added unit tests validating the scheme validation logic and env overrides.
- [environments/sandbox/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/variables.tf) - Added `enable_alb_https` variable.
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf) - Passed `enable_alb_https` and computed dynamic `alb_base_url`.
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example) - Documented example `enable_alb_https` value.
- [environments/staging/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/variables.tf) - Added `enable_alb_https` variable with validation rule ensuring it must be true.
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) - Passed `enable_alb_https` and `alb_base_url` values.
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example) - Documented `enable_alb_https` staging requirement.
- [environments/prod/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/variables.tf) - Added `enable_alb_https` variable with validation rule ensuring it must be true.
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) - Passed `enable_alb_https` and `alb_base_url` values.
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example) - Documented `enable_alb_https` prod requirement.

## Validation Commands
```powershell
# Format code
terraform fmt -check -recursive

# Run unit tests
pytest lambda_src/tests/test_vpc_alb_caller.py
```
