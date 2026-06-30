# NormalizeCostWindow CUR Manifest Fix Progress

## Status
Validated (all unit tests passing, Terraform validation completed, Terraform module test passed)

## Scope
- Validate CUR manifest columns against the telemetry contract (line_item_usage_start_date, line_item_usage_account_id, line_item_product_code, line_item_usage_type, line_item_usage_amount, pricing_unit, line_item_unblended_cost, resource_tags_user_environment).
- Support normalization of column formats (string, dict with 'name', 'ColumnName', or 'columnName').
- Propagate `ContractMismatchError` to fail fast during cost pulling and normalization if columns are invalid.
- Add raw CUR database table resource in lakehouse module to separate raw and curated data.
- Wire normalizer GLUE_TABLE_NAME to the raw Glue table name.

## Files Changed
- [lambda_src/src/finops_common/utils.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/utils.py) - Added `validate_manifest_columns` validator.
- [lambda_src/src/finops_common/__init__.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/__init__.py) - Exposed `validate_manifest_columns` in the package exports.
- [lambda_src/src/workers/cost_puller/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/cost_puller/handler.py) - Call `validate_manifest_columns` on manifest read and allow exception propagation.
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py) - Call `validate_manifest_columns` in both local query generator and manifest parsing.
- [modules/lakehouse/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/main.tf) - Added `raw_cur_data` Glue Catalog Table.
- [modules/lakehouse/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/outputs.tf) - Exposed `raw_cur_table_name` and `raw_cur_table_arn`.
- [modules/lakehouse/lakehouse.tftest.hcl](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/lakehouse.tftest.hcl) - Added assertions for `raw_cur_data` and fixed bucket policy assertion to match the simplified bucket resource policy.
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf) - Wired `cur_data_table_name` parameter of compute-lambda to raw CUR table name output.
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) - Wired `cur_data_table_name` and Athena inputs of compute-lambda to raw CUR table name and outputs.
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) - Wired `cur_data_table_name` and Athena inputs of compute-lambda to raw CUR table name and outputs.
- [lambda_src/tests/test_cost_puller_cur2.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_cost_puller_cur2.py) - Added unit test `test_cost_puller_rejects_missing_required_column`.
- [lambda_src/tests/test_normalizer_cur2.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_normalizer_cur2.py) - Added unit tests `test_normalizer_rejects_missing_column_manifest` and `test_build_dynamic_select_fields_valid_and_optional_columns`.
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md) - Documented AWS Data Export tag/columns prerequisites.
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md) - Documented AWS Data Export tag/columns prerequisites (Vietnamese translation).

## Validation Commands
```powershell
python -m pytest tests/test_cost_puller_cur2.py tests/test_normalizer_cur2.py tests/test_normalizer.py
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate
cd modules/lakehouse; terraform test
```
