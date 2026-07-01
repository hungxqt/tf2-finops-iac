# Synthetic Data Replay Operator Guide

This guide describes the complete step-by-step instructions for operators to stage, configure, execute, and roll back the synthetic data replay backtesting harness in the AWS Sandbox environment.

---

## 1. Prerequisites

Before starting, ensure that:
1. You have local credentials with administrative access to the AWS Sandbox account (`336805808730`).
2. You have Python (>= 3.13) and Terraform (>= 1.10) installed.
3. The Sandbox environment is deployed or initialized:
   ```powershell
   cd environments/sandbox
   terraform init
   cd ../..
   ```

---

## 2. Step-by-Step Implementation

### Step 2.1: Generate the Replay Business Context JSON
The business context generator builds a deterministic JSON file containing daily traffic context (set to `Synthetic`) and EC2/RDS CPU utilization metrics.

* **Option A: Full 92-Day Dataset (Recommended for final backtesting)**
  Generates a 92-day context (March 1, 2026 to May 31, 2026) and uploads it directly to the Sandbox lakehouse bucket:
  ```powershell
  python ./scripts/generate_business_context.py --scope full --account-id 336805808730 --upload
  ```

* **Option B: Smoke Test Dataset (For quick verification)**
  Generates a 16-day subset covering only targeted anomaly windows (A2, B2, A6) with 30-day Cost Explorer lookback padding:
  ```powershell
  python ./scripts/generate_business_context.py --scope smoke --account-id 336805808730 --upload
  ```

* **Option C: Generate Locally First**
  To review the output file before uploading:
  ```powershell
  python ./scripts/generate_business_context.py --scope full --account-id 336805808730 --output .build/synthetic-replay/business_context.json
  ```
  Then upload manually or run with the `--upload` flag.

---

### Step 2.2: Stage CUR Telemetry to S3
The replay preparation script converts raw synthetic CSV line items to snappy Parquet files partitioned by billing period (monthly), generates the Data Exports manifests, and uploads them to the CUR S3 bucket:
```powershell
python ./scripts/prepare_replay.py --account-id 336805808730
```

---

### Step 2.3: Configure and Deploy Terraform Variables
Enable replay mode in Terraform to instruct Lambda workers to read metrics and CE data from the synthetic context file rather than live AWS APIs.

1. Open `environments/sandbox/terraform.tfvars`.
2. Configure the following parameters (replace the bucket name with your actual sandbox lakehouse bucket name if overridden):
   ```hcl
   synthetic_replay_enabled              = true
   synthetic_replay_business_context_uri = "s3://tf2-finops-sandbox-lakehouse/replay/business_context.json"
   ```
3. Deploy the updated configurations:
   ```powershell
   cd environments/sandbox
   terraform apply
   cd ../..
   ```

---

### Step 2.4: Execute the Replay Runner
Trigger the backtest executions. The runner seeds the account policy in DynamoDB, starts the Step Functions workflow sequentially day-by-day, and polls each run to completion.

* **Smoke Mode (3 days, 2026-03-01 to 2026-03-03)**
  ```powershell
  python ./scripts/run_replay.py --mode smoke
  ```

* **Warmup Mode (20 days, 2026-03-01 to 2026-03-20)**
  Runs up to the date of the RDS orphan DB instance anomaly (A2).
  ```powershell
  python ./scripts/run_replay.py --mode warmup
  ```

* **Full Mode (92 days, 2026-03-01 to 2026-05-31)**
  Replays the entire historical period.
  ```powershell
  python ./scripts/run_replay.py --mode full
  ```

---

## 3. Verification & Auditing

As the replay progresses, verify executions and telemetry output:
1. **AWS Step Functions Console**: Locate `tf2-finops-sandbox-workflow` and check running/completed executions starting with `replay-`.
2. **DynamoDB tables**:
   - Check `tf2-finops-sandbox-account-policy` to verify account `336805808730` is seeded.
   - Check `finops-idempotency-sandbox` to confirm unique ad-hoc runs are processed successfully.
3. **S3 Audit Trail**: Verify that raw gzipped records and containment audit trails are written under `s3://tf2-finops-sandbox-lakehouse/audit/`.

---

## 4. Cleanup & Rollback

Once testing is complete, restore the sandbox to standard operational mode:

1. Open `environments/sandbox/terraform.tfvars`.
2. Revert the variables back to defaults:
   ```hcl
   synthetic_replay_enabled              = false
   synthetic_replay_business_context_uri = ""
   ```
3. Deploy the changes:
   ```powershell
   cd environments/sandbox
   terraform apply
   cd ../..
   ```
4. (Optional) Remove the business context file from S3:
   ```powershell
   aws s3 rm s3://tf2-finops-sandbox-lakehouse/replay/business_context.json
   ```
