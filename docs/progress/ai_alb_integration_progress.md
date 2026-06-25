# Private ALB AI Engine Integration Progress

## Status
Validated (all tests and static validation passing; plan generation validated)

## Scope
Integrate Private HTTPS ALB into the AI Engine Request path:
- Step Functions -> VpcAlbCallerLambda -> private internal ALB -> AI Engine Request Lambda (live alias)
- Least-privilege IAM and secure network isolation (internal only, HTTPS-only listener, security groups with separate rules, WAF rate-limit baseline).
- Standard validation and pytest checks. No terraform apply is executed.

## Files Changed
- `AGENTS.md` - Updated authoritative transport and integration guidance to use Private internal ALB.
- `modules/ai-runtime-lambda/variables.tf` - Declared variables for VPC, Certificate, Route 53, and Logging.
- `modules/ai-runtime-lambda/main.tf` - Added internal ALB, Target Group, Target Group Attachment, Listener, Lambda Permission, WAFv2 Web ACL, and Route 53 A record resources.
- `modules/ai-runtime-lambda/outputs.tf` - Exported ALB DNS name, ARN, and Security Group ID.
- `lambda_src/src/workers/vpc_alb_caller/handler.py` - Created python worker for signing and calling the ALB.
- `lambda_src/src/workers/vpc_alb_caller/__init__.py` - Empty worker module marker.
- `lambda_src/tests/test_vpc_alb_caller.py` - Added unit tests for happy path, input validation, and fail-closed handling.
- `scripts/package-lambdas.ps1` - Added `vpc_alb_caller` to packaging loop.
- `modules/compute-lambda/variables.tf` - Added `alb_base_url` and `sigv4_service_name`.
- `modules/compute-lambda/main.tf` - Registered `vpc_alb_caller` in local workers configuration.
- `modules/orchestration/main.tf` - Replaced direct `ai_request` Lambda call with `vpc_alb_caller` in State Machine.
- `environments/sandbox/variables.tf` - Declared sandbox variables for cert, DNS, and service name.
- `environments/sandbox/main.tf` - Wired ALB variables to `ai_runtime_lambda` and base URL/service name to `compute_lambda`.
- `environments/sandbox/outputs.tf` - Added sandbox outputs for private ALB parameters.
- `environments/sandbox/terraform.tfvars` - Added sandbox variable values.
- `environments/sandbox/terraform.tfvars.example` - Added sandbox variable examples.
- `environments/staging/variables.tf` - Declared staging variables for cert, DNS, and service name.
- `environments/staging/main.tf` - Wired ALB variables to modules in staging.
- `environments/staging/outputs.tf` - Added staging outputs for private ALB parameters.
- `environments/staging/terraform.tfvars.example` - Added staging variable examples.
- `environments/prod/variables.tf` - Declared prod variables for cert, DNS, and service name.
- `environments/prod/main.tf` - Wired ALB variables to modules in prod.
- `environments/prod/outputs.tf` - Added prod outputs for private ALB parameters.
- `environments/prod/terraform.tfvars.example` - Added prod variable examples.
- `docs/GUIDES.md` - Updated developer guide with Private ALB outputs.
- `docs/GUIDES_vi.md` - Updated Vietnamese developer guide with Private ALB outputs.

## Validation Commands
```powershell
# Format code
terraform fmt -check -recursive

# Validate configurations
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Run unit tests
cd lambda_src
python -m pytest
cd ..
```

## Results
- `terraform fmt -check -recursive`: Success (0 code style issues).
- `terraform validate` (bootstrap/sandbox/staging/prod): Success (All modules compile and validate correctly).
- `python -m pytest` (lambda_src): Success (40/40 tests passing, including 8 new tests for `vpc_alb_caller` coverage).

## Blockers
None.

## Next Step
Prepare deployment plan for review.
