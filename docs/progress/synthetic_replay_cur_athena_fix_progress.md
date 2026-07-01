# Progress: Synthetic Replay CUR Reads Through Athena Fix

Fixed the synthetic replay CUR reads through Athena by aligning the raw CUR table projection, normalizer Athena SQL predicates, replay Parquet schema, and replay runner payload.

## Deployed Elements

1. **Glue Catalog Table Projection Upgrade (`modules/lakehouse/main.tf`)**:
   - Added support for member-account partitioning mode.
   - When member accounts are configured via `telemetry_member_account_ids`, the raw CUR table (`raw_cur_data`) dynamically adds `source_account_id` as the first partition key, followed by `billing_period`.
   - The storage template location is dynamically updated to: `s3://${local.cur_export_bucket_name}/$${source_account_id}/${var.cur_export_name}/data/BILLING_PERIOD=$${billing_period}/`.
   - Exposed `cur_raw_account_partition_key` output representing the member partition key.

2. **Compute Lambda Environment Configuration (`modules/compute-lambda/main.tf` & `environments/*`)**:
   - Added `cur_raw_account_partition_key` variable to the compute-lambda module.
   - Configured `CUR_RAW_ACCOUNT_PARTITION_KEY` environment variable on the normalizer Lambda.
   - Wired environments (`sandbox`, `staging`, `prod`) to pass the partition key from the lakehouse module output.

3. **Normalizer Athena SQL Queries Hardening (`normalizer/handler.py`)**:
   - Updated query formulation to always filter by `billing_period = '<YYYY-MM>'`.
   - Dynamically appends `source_account_id = '<12-digit-account-id>'` when member-account partition key is configured.
   - Kept the typed half-open timestamp window query filters.
   - Hardened validation by applying strict regex checks to all injected SQL literals (`billing_period`, `account_id`, `start_ts`, `end_ts`).
   - Redacted raw CUR row details from error/info logging to prevent data leakage.

4. **Replay Scripts Correction (`scripts/prepare_replay.py` & `scripts/run_replay.py`)**:
   - Updated `prepare_replay.py` to write CUR timestamp columns (`bill_billing_period_start_date`, `line_item_usage_start_date`, `line_item_usage_end_date`) as PyArrow `timestamp` types (`pa.timestamp('us')`) instead of strings, matching Glue catalog types.
   - Updated `run_replay.py` to send date-only `execution_date` (`YYYY-MM-DD`) and include `billing_period` (`YYYY-MM`) in the Step Functions execution input payload.

5. **Guides & Documentation Updates**:
   - Updated `docs/GUIDES.md`, `docs/GUIDES_vi.md`, `docs/synthetic_replay_instructions.md`, and `docs/synthetic_replay_instructions_vi.md` to reflect the canonical member S3 CUR path and updated date-only payload format.

## Test Validation
- Added assertions in `modules/lakehouse/lakehouse.tftest.hcl` validating raw CUR table partition keys and storage templates when member mode is enabled.
- Added a regression unit test `test_normalizer_athena_member_account_mode_query` in `lambda_src/tests/test_normalizer_cur2.py` asserting proper Athena SQL query generation, including `source_account_id` and `billing_period` predicates.
