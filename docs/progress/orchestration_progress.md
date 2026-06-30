# Orchestration Progress

## Status
Completed

## Scope
Update the Step Functions flow and orchestration components to implement a post-apply scheduler activation guard. This ensures that the EventBridge Scheduler is created in a DISABLED state by default, preventing automatic scheduled workflow execution after initial deployment. Daily runs are only enabled by an explicit, reviewed plan change.

Specifically:
- Added a `scheduler_enabled` boolean variable (default: `false`) to `modules/orchestration` and the environment roots (`sandbox`, `staging`, `prod`).
- Wired `aws_scheduler_schedule.run_workflow.state` using `var.scheduler_enabled ? "ENABLED" : "DISABLED"`.
- Set `scheduler_enabled = false` in each environment's `terraform.tfvars.example`.
- Added a `scheduler_state` output to the orchestration module and all environment outputs.
- Updated guides (`modules/orchestration/README.md`, `docs/GUIDES.md`, and `docs/GUIDES_vi.md`) to clarify that initial deployment keeps Step Functions execution disabled.
- Added python unit tests verifying the scheduler configuration variables, outputs, and preventing automatic execution.

## Files Changed
- [modules/orchestration/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/variables.tf)
- [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf)
- [modules/orchestration/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/outputs.tf)
- [environments/sandbox/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/variables.tf)
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf)
- [environments/sandbox/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/outputs.tf)
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example)
- [environments/staging/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/variables.tf)
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf)
- [environments/staging/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/outputs.tf)
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example)
- [environments/prod/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/variables.tf)
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf)
- [environments/prod/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/outputs.tf)
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example)
- [modules/orchestration/README.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/README.md)
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md)
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md)
- [lambda_src/tests/test_scheduler_configuration.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_scheduler_configuration.py)

## Validation Commands
```powershell
terraform fmt -check -recursive modules/orchestration environments/sandbox environments/staging environments/prod
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
Push-Location lambda_src; python -m pytest -v -p no:cacheprovider tests/test_scheduler_configuration.py; Pop-Location
```

## Results
- `terraform fmt -check -recursive`: Success (All files properly formatted)
- `environments/sandbox validate`: Success (Configuration is valid)
- `environments/staging validate`: Success (Configuration is valid)
- `environments/prod validate`: Success (Configuration is valid)
- Python unit tests: Success (All 3 new tests passed validating `scheduler_enabled` propagation, variables, `terraform.tfvars.example` constraints, and prevention of automatic execution triggers)

## Blockers
None

## Next Step
Proceed with pipeline integration and deployment tests.
