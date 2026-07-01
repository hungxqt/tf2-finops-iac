# Progress: Synthetic Data Replay Integration

Integrated sandbox-only synthetic data replay harness to support backtest scenarios (smoke, warmup, and full-backtest) on 3-month historical data.

## Deployed Elements

1. **Replay Preparation Script (`scripts/prepare_replay.py`)**:
   - Parses the high-fidelity synthetic CSV files (`cur_line_items.csv`, `cost_explorer_daily.csv`, and `anomaly_labels_public.csv`).
   - Converts the CUR rows to AWS Data Exports CUR 2.0 Parquet format partitioned by month.
   - Deterministically generates CUR 2.0 metadata manifests listing the Parquet data files.
   - Generates daily synthetic business/traffic context (ALB RequestCount) and instance CPU utilization metrics for all EC2 resources.
   - Projects all synthetic account IDs to the real target sandbox account ID, while preserving original names/tags in metadata.
   - Uploads CUR data files, manifests, and the compiled `business_context.json` file to sandbox S3 buckets under KMS encryption.

2. **Replay Runner Script (`scripts/run_replay.py`)**:
   - Seeds the target account policy mapping in the `account-policy` DynamoDB table for the sandbox account.
   - Triggers the orchestrator Step Functions state machine sequentially day-by-day.
   - Automatically polls the SFN execution until completion and outputs progress summaries.
   - Supports `--mode smoke` (3 days), `--mode warmup` (20 days), and `--mode full` (92 days).

3. **Adapter Code Modifications (`cost_puller/handler.py`)**:
   - Added synthetic replay support via `SYNTHETIC_REPLAY_ENABLED` and `SYNTHETIC_REPLAY_BUSINESS_CONTEXT_URI`.
   - When enabled, overrides normal CloudWatch traffic/utilization queries by reading from the staged S3 business context file, avoiding degraded dry-run scores.
   - When CUR is delayed, intercepts Cost Explorer fallback logic to load synthetic CE records from the business context instead of calling real AWS CE APIs.

4. **Terraform Safety Safeguards (`compute-lambda/variables.tf`, `sandbox/main.tf`)**:
   - Added `synthetic_replay_enabled` and `synthetic_replay_business_context_uri` variables.
   - Added a validation rule in the Terraform module ensuring `synthetic_replay_enabled` can only be set to `true` when `environment == "sandbox"`. Any attempt to enable it in staging or prod is rejected during plan validation.

5. **Guides & Documentation**:
   - Documented operator instructions in `docs/GUIDES.md` and `docs/GUIDES_vi.md`.

## Test Execution
- Created new unit tests in `lambda_src/tests/test_synthetic_replay.py` validating cost_puller ready/delayed paths under synthetic replay mode.
- Executed `pytest` successfully, passing all 379 tests in the repository.
