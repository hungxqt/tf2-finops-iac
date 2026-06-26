# Glue Catalog Schema & Partition Projection Progress

## Status
Completed

## Scope
Implement Glue Catalog schemas for curated cost data and containment audit records using Athena Partition Projection with no Glue Crawler dependency. Align workers and update tests/validation scripts.

## Files Changed
- [modules/lakehouse/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/main.tf) (Modified: Added aws_glue_catalog_table resources for cur_data and containment_audit)
- [modules/lakehouse/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/outputs.tf) (Modified: Added outputs for table names and database/table map)
- [environments/sandbox/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/outputs.tf) (Modified: Propagated glue_catalog_tables output)
- [environments/staging/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/outputs.tf) (Modified: Propagated glue_catalog_tables output)
- [environments/prod/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/outputs.tf) (Modified: Propagated glue_catalog_tables output)
- [lambda_src/requirements.txt](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/requirements.txt) (Modified: Added pyarrow dependency)
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py) (Modified: Updated output path to include account_id and partition by year/month, outputting real Parquet format using pyarrow)
- [lambda_src/src/workers/audit_writer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/audit_writer/handler.py) (Modified: Updated output path to partition by account_id/year/month, included all required metadata fields and numeric audit score)
- [lambda_src/tests/test_normalizer.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_normalizer.py) (Modified: Updated path assertions, loaded Parquet bytes with pyarrow, and validated the schema fields)
- [lambda_src/tests/test_audit_writer.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_audit_writer.py) (Modified: Updated path assertions, verified new audit properties in JSON)
- [scripts/athena_validation.sql](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/athena_validation.sql) (Created: Added Athena DDL matching schemas and projection settings)
- [modules/lakehouse/lakehouse.tftest.hcl](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/lakehouse.tftest.hcl) (Created: Added Terraform validation tests)
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md) (Modified: Added section on Glue Schema & Partition Projection Validation)
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md) (Modified: Added section on Glue Schema & Partition Projection Validation)

## Validation Commands
- Validate sandbox configuration: `terraform -chdir=environments/sandbox validate` (Success)
- Validate staging configuration: `terraform -chdir=environments/staging validate` (Success)
- Validate prod configuration: `terraform -chdir=environments/prod validate` (Success)
- Run Terraform tests: `terraform test` inside `modules/lakehouse` (Success)
- Run python workers unit tests: `python -m pytest` inside `lambda_src` (Success)
- Trivy scan check: `trivy config modules/lakehouse` (Clean)
- Checkov scan check: `checkov -d modules/lakehouse --framework terraform` (Clean for new tables)

## Results
- Added `cur_data` and `containment_audit` external tables with Athena Partition Projection enabled.
- Normalizer output aligns with the new layout, writing real Parquet format bytes.
- Audit writer output partitions by account_id and execution date, writing full details including numeric audit score.
- All Terraform and python unit tests run and pass successfully.

## Blockers
None

## Next Step
Integrate with continuous deployment pipelines.
