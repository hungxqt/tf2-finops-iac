# Progress: Synthetic Data Replay Integration

Integrated sandbox-only synthetic data replay harness to support backtest scenarios (smoke, warmup, and full-backtest) on 3-month historical data.

## Deployed Elements

1. **Business Context Generator Script (`scripts/generate_business_context.py`)**:
   - Deterministically generates `business_context.json` matching `docs/synthetic-data`.
   - Supports `--scope full` (92-day dataset) and `--scope smoke` (custom replay windows + CE lookback padding).
   - Generates daily context with `traffic_source = "Synthetic"`.
   - Simulates normal traffic from a deterministic baseline and organic growth, scales B2 traffic to keep cost-per-request stable, and includes low utilization for A2 database `db-staging-orphan-01`.
   - Saves output locally at `.build/synthetic-replay/` and uploads to S3 when `--upload` is passed.

2. **Replay Preparation Script (`scripts/prepare_replay.py`)**:
   - Parses the high-fidelity synthetic CSV files (`cur_line_items.csv` and `anomaly_labels_public.csv`).
   - Converts the CUR rows to AWS Data Exports CUR 2.0 Parquet format partitioned by month.
   - Deterministically generates CUR 2.0 metadata manifests listing the Parquet data files.
   - Projects all synthetic account IDs to the real target sandbox account ID, while preserving original names/tags in metadata.
   - Uploads CUR data files and manifests to the sandbox S3 bucket under KMS encryption.

3. **Replay Runner Script (`scripts/run_replay.py`)**:
   - Seeds the target account policy mapping in the `account-policy` DynamoDB table for the sandbox account.
   - Triggers the orchestrator Step Functions state machine sequentially day-by-day.
   - Automatically polls the SFN execution until completion and outputs progress summaries.
   - Supports `--mode smoke` (3 days), `--mode warmup` (20 days), and `--mode full` (92 days).

4. **Adapter Code Modifications (`cost_puller/handler.py`)**:
   - Added synthetic replay support via `SYNTHETIC_REPLAY_ENABLED` and `SYNTHETIC_REPLAY_BUSINESS_CONTEXT_URI`.
   - When enabled, overrides normal CloudWatch traffic/utilization queries by reading from the staged S3 business context file, avoiding degraded dry-run scores.
   - When CUR is delayed, intercepts Cost Explorer fallback logic to load synthetic CE records from the business context instead of calling real AWS CE APIs.

5. **Terraform Safety Safeguards (`compute-lambda/variables.tf`, `sandbox/main.tf`)**:
   - Added `synthetic_replay_enabled` and `synthetic_replay_business_context_uri` variables.
   - Added a validation rule in the Terraform module ensuring `synthetic_replay_enabled` can only be set to `true` when `environment == "sandbox"`. Any attempt to enable it in staging or prod is rejected during plan validation.

6. **Guides & Documentation**:
   - Documented operator instructions in `docs/GUIDES.md` and `docs/GUIDES_vi.md`.

## Test Execution
- Created new unit tests in `lambda_src/tests/test_synthetic_replay.py` validating cost_puller ready/delayed paths and deterministic constraints of the business context generator.
- Executed `pytest` successfully, passing all 380 tests in the repository.
