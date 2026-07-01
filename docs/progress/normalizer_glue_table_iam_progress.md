# Normalizer Athena Glue Table IAM Progress

## Status
Validated (all tests passing, Terraform validation completed)

## Scope
Resolve the `TABLE_NOT_FOUND` error for the normalizer Lambda by updating IAM boundary and policy documents. The normalizer role and its permissions boundary previously only allowed Glue metadata reads for `cur_data_table_arn` (which was mapped to curated cost data). This change generalizes the interface to accept a list of table ARNs (`glue_table_arns`) and configures environments to pass the raw CUR table ARN (`raw_cur_table_arn`) which is the target table the normalizer queries.

Key Changes:
- Replaced the scalar `cur_data_table_arn` input variable with `glue_table_arns` list of strings in the `iam` module.
- Updated the `boundary` permissions boundary and the `normalizer` policy document to grant access to all table ARNs specified in `var.glue_table_arns` for `glue:GetDatabase`, `glue:GetTable`, and `glue:GetPartitions` actions.
- Configured sandbox, staging, and production environment roots to pass `glue_table_arns = [module.lakehouse.raw_cur_table_arn]` to the `iam` module.
- Removed the deprecated `cur_data_table_arn` parameter from the environment-level `iam` module instantiations.
- Wrote regression tests in `lambda_src/tests/test_iam_cur_source_policy.py` to assert correct propagation and usage of `glue_table_arns` and ensure no references to `cur_data_table_arn` remain.

## Files Changed
- [modules/iam/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/variables.tf) - Replaced `cur_data_table_arn` variable with `glue_table_arns`.
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf) - Updated `boundary` and `normalizer` policies to grant permissions using `var.glue_table_arns`.
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf) - Updated `iam` module wiring to pass `glue_table_arns = [module.lakehouse.raw_cur_table_arn]`.
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) - Updated `iam` module wiring to pass `glue_table_arns = [module.lakehouse.raw_cur_table_arn]`.
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) - Updated `iam` module wiring to pass `glue_table_arns = [module.lakehouse.raw_cur_table_arn]`.
- [lambda_src/tests/test_iam_cur_source_policy.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_iam_cur_source_policy.py) - Added regression test verifying the updated IAM and environment variables.

## Validation Commands
All validations were executed and passed successfully:

```powershell
# Format check
terraform fmt -check -recursive

# Terraform validate (Sandbox)
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate

# Terraform validate (Staging)
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate

# Terraform validate (Production)
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Run pytest suite
python -m pytest tests/test_iam_cur_source_policy.py tests/test_normalizer_cur2.py tests/test_normalizer.py -v
```
