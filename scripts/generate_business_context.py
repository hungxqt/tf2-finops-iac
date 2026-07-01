#!/usr/bin/env python3
import os
import sys
import json
import argparse
import datetime
import hashlib
import random
import re
import subprocess
import boto3
import pandas as pd

def get_real_account_id():
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        return identity["Account"]
    except Exception as e:
        print(f"Warning: Could not get caller identity from STS ({e}). Defaulting to '336805808730'.")
        return "336805808730"

def get_terraform_outputs(cwd):
    try:
        res = subprocess.run(["terraform", "output", "-json"], capture_output=True, text=True, cwd=cwd, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        print(f"Warning: Could not query terraform outputs in {cwd}: {e}")
        return {}

def resolve_kms_key_arn(aws_region):
    try:
        kms = boto3.client("kms", region_name=aws_region)
        alias_name = "alias/tf2-finops-sandbox-data-key"
        resp = kms.describe_key(KeyId=alias_name)
        return resp["KeyMetadata"]["Arn"]
    except Exception as e:
        print(f"Warning: Could not resolve KMS key ARN by alias ({e}). Relying on S3 default encryption.")
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate deterministic business context JSON for Sandbox Replay.")
    parser.add_argument("--scope", choices=["full", "smoke"], default="full", help="Generation scope (default: full).")
    parser.add_argument("--account-id", help="Real AWS account ID to project the data to. If omitted, will query via STS.")
    parser.add_argument("--region", default="ap-southeast-1", help="AWS region (default: ap-southeast-1).")
    parser.add_argument("--seed", default="tf2-finops-synthetic-v1", help="Random seed for deterministic noise.")
    parser.add_argument("--output", help="Local output file path. Defaults to .build/synthetic-replay/business_context.json.")
    parser.add_argument("--start-date", help="Custom slice start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", help="Custom slice end date (YYYY-MM-DD).")
    parser.add_argument("--upload", action="store_true", help="Upload the generated JSON directly to S3.")
    parser.add_argument("--lakehouse-bucket", help="Target S3 bucket for upload. If omitted, will resolve from Terraform.")
    
    args = parser.parse_args()
    
    # 1. Setup paths
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cur_csv_path = os.path.join(base_dir, "docs/synthetic-data/cur_line_items.csv")
    ce_csv_path = os.path.join(base_dir, "docs/synthetic-data/cost_explorer_daily.csv")
    
    # Resolve local output path
    output_path = args.output
    if not output_path:
        if args.scope == "smoke":
            output_path = os.path.join(base_dir, ".build/synthetic-replay/business_context-smoke.json")
        else:
            output_path = os.path.join(base_dir, ".build/synthetic-replay/business_context.json")
            
    # Create directory if needed
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 2. Resolve target account ID
    account_id = args.account_id
    if not account_id:
        account_id = get_real_account_id()
    print(f"Projecting accounts to Target Account ID: {account_id}")
    
    # 3. Initialize deterministic RNG
    seed_hash = int(hashlib.sha256(args.seed.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed_hash)
    
    # 4. Resolve date range
    start_date_limit = datetime.date(2026, 3, 1)
    end_date_limit = datetime.date(2026, 5, 31)
    
    if args.start_date:
        start_date_limit = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    if args.end_date:
        end_date_limit = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
        
    delta = end_date_limit - start_date_limit
    all_dates = [start_date_limit + datetime.timedelta(days=i) for i in range(delta.days + 1)]
    
    # Filter active dates by scope
    active_dates = []
    if args.scope == "smoke" and not (args.start_date or args.end_date):
        # Smoke scope covers:
        # - B2 migration window: 2026-03-28 to 2026-03-30
        # - A6 spike window: 2026-04-28 to 2026-05-04
        # - A2 validation window: 2026-03-20 to 2026-03-25
        smoke_windows = [
            (datetime.date(2026, 3, 20), datetime.date(2026, 3, 25)),
            (datetime.date(2026, 3, 28), datetime.date(2026, 3, 30)),
            (datetime.date(2026, 4, 28), datetime.date(2026, 5, 4))
        ]
        for start, end in smoke_windows:
            cur = start
            while cur <= end:
                active_dates.append(cur)
                cur += datetime.timedelta(days=1)
    else:
        active_dates = all_dates
        
    active_dates_str = {d.strftime("%Y-%m-%d") for d in active_dates}
    print(f"Generated scope: {args.scope.upper()} with {len(active_dates)} active replay dates.")
    
    # 5. Read raw CUR to discover EC2 instances and active days
    print(f"Reading raw CUR from {cur_csv_path} to trace active resources...")
    df_cur = pd.read_csv(cur_csv_path)
    
    daily_context = {}
    for d in active_dates:
        date_str = d.strftime("%Y-%m-%d")
        
        # Determine flags based on public anomalies
        # B2 Migration (2026-03-28 to 2026-03-30)
        is_b2 = (datetime.date(2026, 3, 28) <= d <= datetime.date(2026, 3, 30))
        migration_flag = is_b2
        campaign_flag = False
        load_test_flag = False
        
        # Normal Traffic generation
        day_of_week = d.weekday()
        is_weekend = (day_of_week >= 5)
        baseline_traffic = 8000.0 if is_weekend else 12500.0
        
        # Organic Trend: 0.1% daily compound growth from 2026-03-01
        days_since_start = (d - datetime.date(2026, 3, 1)).days
        trend_factor = 1.0 + (days_since_start * 0.001)
        
        # Noise
        noise = rng.uniform(-300.0, 300.0)
        traffic_vol = (baseline_traffic * trend_factor) + noise
        
        # Scale traffic upward for B2 to maintain cost-per-request stable
        if is_b2:
            # Egress cost spike is ~$650/day. Baseline daily cost is ~$6000.
            # Scaling traffic by (6000 + 650) / 6000 = ~1.108x
            traffic_vol = traffic_vol * (1.0 + 650.0 / 6000.0)
            
        # Discover EC2 instances active on this day in the CUR dataset
        day_df = df_cur[df_cur["line_item_usage_start_date"].str.startswith(date_str)]
        day_instances = set()
        for rid in day_df["line_item_resource_id"].unique():
            if isinstance(rid, str) and rid.startswith("i-"):
                day_instances.add(rid)
                
        resource_utilization_metrics = []
        for inst in sorted(day_instances):
            # Normal instances CPU: 20% to 45%
            avg_cpu = rng.uniform(20.0, 45.0)
            
            # Runaway or target EC2 instances from CUR
            # If instance contains idle or orphan, keep it very low
            if "idle" in inst or "orphan" in inst:
                avg_cpu = rng.uniform(0.5, 2.0)
                
            hourly_values = [max(0.1, avg_cpu + rng.uniform(-3.0, 3.0)) for _ in range(24)]
            resource_utilization_metrics.append({
                "resource_id": inst,
                "cpu_percent": avg_cpu,
                "cpu_utilization_hourly": hourly_values
            })
            
        # A2 RDS Idle Orphan db-staging-orphan-01 (2026-03-20 to 2026-05-31)
        is_a2_active = (datetime.date(2026, 3, 20) <= d <= datetime.date(2026, 5, 31))
        if is_a2_active:
            # Add RDS low utilization metric explicitly
            resource_utilization_metrics.append({
                "resource_id": "arn:aws:rds:us-east-1:acct:db:db-staging-orphan-01",
                "cpu_percent": 1.2,
                "cpu_utilization_hourly": [1.2] * 24
            })
            
        daily_context[date_str] = {
            "traffic_volume": round(traffic_vol, 2),
            "traffic_source": "Synthetic",
            "campaign_flag": campaign_flag,
            "load_test_flag": load_test_flag,
            "migration_flag": migration_flag,
            "resource_utilization_metrics": resource_utilization_metrics
        }
        
    # 6. Read CE Daily and filter based on Active replay range + CE lookback
    print(f"Reading CE Daily from {ce_csv_path}...")
    df_ce = pd.read_csv(ce_csv_path)
    
    ce_lookback_days = 30
    ce_list = []
    
    for _, row in df_ce.iterrows():
        r_date_str = str(row["date"])
        r_date = datetime.datetime.strptime(r_date_str, "%Y-%m-%d").date()
        
        # Check if the date falls in the replay dates or their 30-day lookback windows
        include_ce = False
        for active_d in active_dates:
            if active_d - datetime.timedelta(days=ce_lookback_days) <= r_date <= active_d:
                include_ce = True
                break
                
        if include_ce:
            ce_list.append({
                "date": r_date_str,
                "linked_account_id": account_id,
                "linked_account_name": str(row["linked_account_name"]),
                "service": str(row["service"]),
                "service_code": str(row["service_code"]),
                "region": str(row["region"]),
                "unblended_cost": float(row["unblended_cost"]),
                "is_estimated": str(row["is_estimated"]).lower() == "true"
            })
            
    print(f"Included {len(ce_list)} Cost Explorer daily records (including lookback padding).")
    
    # 7. Build Top Level JSON Shape
    replay_json = {
        "schema_version": "3.2.0",
        "source_dataset": "docs/synthetic-data",
        "projection": {
            "mode": "single_sandbox_account",
            "target_account_id": account_id
        },
        "date_range": {
            "start_date": start_date_limit.strftime("%Y-%m-%d"),
            "end_date": end_date_limit.strftime("%Y-%m-%d")
        },
        "daily_context": daily_context,
        "cost_explorer_daily": ce_list
    }
    
    # Save locally
    with open(output_path, "w") as f:
        json.dump(replay_json, f, indent=2)
    print(f"Successfully generated local JSON artifact at: {output_path}")
    
    # 8. Upload to S3 if requested
    if args.upload:
        sandbox_dir = os.path.join(base_dir, "environments/sandbox")
        
        # Resolve S3 Bucket Name
        lakehouse_bucket = args.lakehouse_bucket
        if not lakehouse_bucket:
            # Query outputs
            tf_outputs = get_terraform_outputs(sandbox_dir)
            if "lakehouse_bucket_name" in tf_outputs:
                lakehouse_bucket = tf_outputs["lakehouse_bucket_name"]["value"]
                
        if not lakehouse_bucket:
            # Try parsing tfvars
            tfvars_path = os.path.join(sandbox_dir, "terraform.tfvars")
            if os.path.exists(tfvars_path):
                with open(tfvars_path, "r") as f:
                    content = f.read()
                    m = re.search(r'lakehouse_bucket_name\s*=\s*"([^"]+)"', content)
                    if m:
                        lakehouse_bucket = m.group(1)
                        
        if not lakehouse_bucket:
            lakehouse_bucket = "tf2-finops-sandbox-lakehouse"
            
        print(f"Uploading context to S3 bucket: {lakehouse_bucket}...")
        s3 = boto3.client("s3", region_name=args.region)
        
        # Check KMS encryption
        kms_key_arn = resolve_kms_key_arn(args.region)
        extra_s3_args = {}
        if kms_key_arn:
            extra_s3_args = {
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": kms_key_arn
            }
            print(f"Encrypting upload with KMS key: {kms_key_arn}")
            
        s3_key = "replay/business_context.json"
        s3.put_object(
            Bucket=lakehouse_bucket,
            Key=s3_key,
            Body=json.dumps(replay_json, indent=2).encode("utf-8"),
            ContentType="application/json",
            **extra_s3_args
        )
        print(f"Upload completed. S3 URI: s3://{lakehouse_bucket}/{s3_key}")

if __name__ == "__main__":
    main()
