# Member-Account CUR Prefix Progress

This log tracks the progress of the member-account CUR 2.0 manifest prefix fixes and the Cost Explorer fallback dimensions fix.

## Progress Summary

- **Completed**: Fix CUR 2.0 manifest discovery to support account-specific prefixes: `s3://<cur_source_bucket>/<account_id>/<cur_export_name>/metadata/BILLING_PERIOD=YYYY-MM/<cur_export_name>-Manifest.json`.
- **Completed**: Generate `CUR_EXPORTS_JSON` dynamically from `telemetry_member_account_ids` and `cur_export_name` in each environment root, avoiding manual config drift.
- **Completed**: Update IAM policies and S3 bucket policies/lifecycle configurations to scope down to generated member-account prefixes.
- **Completed**: Fix Cost Explorer fallback dimension bug by querying only 2 dimensions (`LINKED_ACCOUNT`, `SERVICE`) and normalizing region to `"global"`.
- **Completed**: Added comprehensive test cases for manifest key generation, multi-account config with custom bucket (`tf2-finops-cur-export-bucket-2`), unconfigured event account rejection, and Cost Explorer fallback.

## Details of Changes

### Lambda Workers
- **Cost Puller** (`lambda_src/src/workers/cost_puller/handler.py`):
  - Reject unconfigured event accounts if `CUR_EXPORTS_JSON` is configured.
  - Parse and return `allowed_raw_prefix` in the details response.
  - Validate manifest dataFiles against `effective_cur_bucket` (instead of hardcoded bucket).
  - Call Cost Explorer with only 2 dimensions (LINKED_ACCOUNT, SERVICE) and set region default to `"global"`.
- **Normalizer** (`lambda_src/src/workers/normalizer/handler.py`):
  - Retrieve `allowed_raw_prefix` from `ingestion.details`.
  - Validate dataFiles against the bucket name parsed from the manifest S3 URI.

### Infrastructure (Terraform)
- **Lakehouse Module** (`modules/lakehouse`):
  - Declare variables `cur_export_name` and `telemetry_member_account_ids`.
  - Update `aws_s3_bucket_lifecycle_configuration.cur_export` to expire files per member-account prefix.
  - Scope `AllowBCMDataExportsPut` bucket policy statement to member-account prefixes.
- **IAM Module** (`modules/iam`):
  - Declare variable `cur_export_name`.
  - Scope down `AllowCURSourceGet` and `AllowMemberCURGet` resources to generated member-account prefixes when `telemetry_member_account_ids` is provided.
- **Environments** (`sandbox`, `staging`, `prod`):
  - Added variables `cur_export_name`, `cur_exports_json`, `create_cur_export_bucket`, `cur_export_bucket_name`, and `cur_raw_prefix` consistently.
  - Generate `local.cur_exports_json` and pass it to `compute_lambda`.
  - Pass `cur_export_name` and `telemetry_member_account_ids` to `lakehouse` and `iam` modules.

### Tests
- **Cost Puller Tests** (`lambda_src/tests/test_cost_puller_cur2.py` & `test_cost_puller.py`):
  - Test manifest key generation format.
  - Test multi-account config and validation on custom bucket `tf2-finops-cur-export-bucket-2`.
  - Test rejection on unconfigured event account.
  - Test CE fallback dimensions and region normalization to `"global"`.
- **Normalizer Tests** (`lambda_src/tests/test_normalizer_cur2.py`):
  - Test acceptance of valid member-account prefix and rejection of mismatching prefix.

## Verification Run
- Pytest: 363 tests passed successfully.
- Terraform validate: Sandbox, Staging, and Prod validated successfully.
- Static checks: Trivy and Checkov passed successfully.
