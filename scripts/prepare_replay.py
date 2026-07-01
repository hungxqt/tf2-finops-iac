#!/usr/bin/env python3
import os
import sys
import json
import argparse
import datetime
import random
import re
import subprocess
import tempfile
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

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
    parser = argparse.ArgumentParser(description="Prepare and stage synthetic cost replay data in Sandbox S3.")
    parser.add_argument("--bucket", help="Target S3 bucket for CUR exports. If omitted, will attempt to parse from terraform.tfvars or outputs.")
    parser.add_argument("--lakehouse-bucket", help="Target S3 bucket for curated/telemetry data. If omitted, will attempt to parse from outputs.")
    parser.add_argument("--account-id", help="Real AWS account ID to project the data to. If omitted, will query via STS.")
    parser.add_argument("--region", default="ap-southeast-1", help="AWS region (default: ap-southeast-1).")
    parser.add_argument("--export-name", default="accountCUR", help="CUR Data Exports export name (default: accountCUR).")
    parser.add_argument("--prefix", help="S3 raw data prefix. If omitted, defaults to the AWS account ID.")
    
    args = parser.parse_args()
    
    sandbox_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../environments/sandbox"))
    tf_outputs = get_terraform_outputs(sandbox_dir)
    
    # 1. Resolve Account ID
    account_id = args.account_id
    if not account_id:
        account_id = get_real_account_id()
    print(f"Target projected Account ID: {account_id}")
    
    # 2. Resolve Prefix
    prefix = args.prefix
    if not prefix:
        prefix = account_id
    print(f"Target S3 prefix: {prefix}")
    
    # 3. Resolve Buckets
    cur_bucket = args.bucket
    lakehouse_bucket = args.lakehouse_bucket
    
    if not cur_bucket or not lakehouse_bucket:
        # Try to read terraform.tfvars
        tfvars_path = os.path.join(sandbox_dir, "terraform.tfvars")
        if os.path.exists(tfvars_path):
            with open(tfvars_path, "r") as f:
                content = f.read()
                if not cur_bucket:
                    m = re.search(r'cur_export_bucket_name\s*=\s*"([^"]+)"', content)
                    if m:
                        cur_bucket = m.group(1)
                    else:
                        m_src = re.search(r'cur_source_bucket\s*=\s*"([^"]+)"', content)
                        if m_src:
                            cur_bucket = m_src.group(1)
        
        # Try outputs
        if not cur_bucket and "cur_export_bucket_name" in tf_outputs:
            cur_bucket = tf_outputs["cur_export_bucket_name"]["value"]
        if not lakehouse_bucket and "lakehouse_bucket_name" in tf_outputs:
            lakehouse_bucket = tf_outputs["lakehouse_bucket_name"]["value"]
            
    if not cur_bucket:
        cur_bucket = "tf2-finops-cur-export-bucket-2" # Fallback default
    if not lakehouse_bucket:
        lakehouse_bucket = "tf2-finops-sandbox-lakehouse" # Fallback default
        
    print(f"Target CUR export bucket: {cur_bucket}")
    print(f"Target lakehouse bucket: {lakehouse_bucket}")
    
    # 4. Resolve KMS key for upload
    kms_key_arn = resolve_kms_key_arn(args.region)
    extra_s3_args = {}
    if kms_key_arn:
        extra_s3_args = {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": kms_key_arn
        }
        print(f"Using KMS encryption key: {kms_key_arn}")
    else:
        print("Using S3 default bucket encryption.")
        
    # 5. Read CSV files
    cur_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/synthetic-data/cur_line_items.csv"))
    ce_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/synthetic-data/cost_explorer_daily.csv"))
    labels_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/synthetic-data/anomaly_labels_public.csv"))
    
    print(f"Reading synthetic data files from {os.path.dirname(cur_csv_path)}...")
    df_cur = pd.read_csv(cur_csv_path)
    df_ce = pd.read_csv(ce_csv_path)
    df_labels = pd.read_csv(labels_csv_path)
    
    # 6. Project Account IDs to real AWS Account ID
    # Preserve original account ID and name as metadata columns if needed, but in standard CUR we project it
    print("Projecting account IDs to the real AWS account ID...")
    df_cur["bill_payer_account_id"] = account_id
    df_cur["line_item_usage_account_id"] = account_id
    df_ce["linked_account_id"] = account_id
    
    # Clean up empty tags and NaN values to avoid Parquet writing errors
    df_cur = df_cur.fillna("")
    df_ce = df_ce.fillna("")
    
    # Keep dates as pandas datetime64 objects to let pyarrow write them as Parquet timestamp types
    df_cur["line_item_usage_start_date"] = pd.to_datetime(df_cur["line_item_usage_start_date"])
    df_cur["line_item_usage_end_date"] = pd.to_datetime(df_cur["line_item_usage_end_date"])
    df_cur["bill_billing_period_start_date"] = pd.to_datetime(df_cur["bill_billing_period_start_date"])
    
    # 7. Convert and upload CUR Parquet by Billing Period (Month)
    s3 = boto3.client("s3", region_name=args.region)
    months = df_cur["line_item_usage_start_date"].dt.strftime("%Y-%m").unique()
    
    for month in months:
        print(f"Processing billing period: {month}...")
        df_month = df_cur[df_cur["line_item_usage_start_date"].dt.strftime("%Y-%m") == month].copy()
        
        # Write to temporary Parquet file
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            # We want to match Glue schema types
            # Map columns to correct types
            schema = pa.schema([
                ("bill_billing_period_start_date", pa.timestamp('ms')),
                ("bill_payer_account_id", pa.string()),
                ("line_item_usage_account_id", pa.string()),
                ("line_item_usage_account_name", pa.string()),
                ("line_item_line_item_type", pa.string()),
                ("line_item_usage_start_date", pa.timestamp('ms')),
                ("line_item_usage_end_date", pa.timestamp('ms')),
                ("line_item_product_code", pa.string()),
                ("line_item_usage_type", pa.string()),
                ("line_item_operation", pa.string()),
                ("line_item_resource_id", pa.string()),
                ("line_item_usage_amount", pa.float64()),
                ("pricing_unit", pa.string()),
                ("line_item_unblended_rate", pa.float64()),
                ("line_item_unblended_cost", pa.float64()),
                ("line_item_currency_code", pa.string()),
                ("product_product_name", pa.string()),
                ("product_region_code", pa.string()),
                ("product_instance_type", pa.string()),
                ("resource_tags_user_team", pa.string()),
                ("resource_tags_user_environment", pa.string()),
                ("resource_tags_user_cost_center", pa.string()),
                ("resource_tags_user_owner", pa.string())
            ])
            
            # Cast types of dataframe to match schema
            for col, pa_type in zip(schema.names, schema.types):
                if pa_type == pa.float64():
                    df_month[col] = pd.to_numeric(df_month[col], errors='coerce').fillna(0.0).astype(float)
                elif isinstance(pa_type, pa.TimestampType):
                    df_month[col] = pd.to_datetime(df_month[col], errors='coerce')
                else:
                    df_month[col] = df_month[col].astype(str)
            
            table = pa.Table.from_pandas(df_month[schema.names], schema=schema, preserve_index=False)
            pq.write_table(table, tmp_path, compression='snappy')
            
            # Upload Parquet file
            parquet_key = f"{prefix}/{args.export_name}/data/BILLING_PERIOD={month}/part-00000.snappy.parquet"
            print(f"Uploading Parquet data to s3://{cur_bucket}/{parquet_key}...")
            s3.upload_file(tmp_path, cur_bucket, parquet_key, ExtraArgs=extra_s3_args)
            
            # Generate and upload Manifest file
            manifest = {
                "executionId": f"re-{month}-{account_id}",
                "exportArn": f"arn:aws:bcm-data-exports:us-east-1:{account_id}:export/{args.export_name}",
                "columns": [{"name": name} for name in schema.names],
                "dataFiles": [
                    f"s3://{cur_bucket}/{parquet_key}"
                ]
            }
            manifest_json = json.dumps(manifest, indent=2)
            manifest_key = f"{prefix}/{args.export_name}/metadata/BILLING_PERIOD={month}/{args.export_name}-Manifest.json"
            
            print(f"Uploading Manifest metadata to s3://{cur_bucket}/{manifest_key}...")
            s3.put_object(
                Bucket=cur_bucket,
                Key=manifest_key,
                Body=manifest_json.encode("utf-8"),
                ContentType="application/json",
                **extra_s3_args
            )
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    # 8. Generate Business Context & CPU metrics
    print("Generating synthetic business context and CPU metrics...")
    daily_context = {}
    
    # Generate list of all unique dates across 2026-03-01 to 2026-05-31
    start_date = datetime.date(2026, 3, 1)
    end_date = datetime.date(2026, 5, 31)
    delta = end_date - start_date
    dates = [start_date + datetime.timedelta(days=i) for i in range(delta.days + 1)]
    
    # Scan CUR for resource IDs to know which EC2 instances exist
    all_instances = set()
    for rid in df_cur["line_item_resource_id"].unique():
        if isinstance(rid, str) and rid.startswith("i-"):
            all_instances.add(rid)
    print(f"Found {len(all_instances)} EC2 instances in raw CUR data.")
    
    # We will seed metrics for each date
    for d in dates:
        date_str = d.strftime("%Y-%m-%d")
        
        # B2 migration is 2026-03-28 to 2026-03-30
        is_migration = (datetime.date(2026, 3, 28) <= d <= datetime.date(2026, 3, 30))
        
        # Base traffic volume is around 12000 requests, with weekdays higher and weekends lower
        day_of_week = d.weekday()
        is_weekend = (day_of_week >= 5)
        base_traffic = 8000.0 if is_weekend else 12500.0
        traffic_vol = base_traffic + random.uniform(-500.0, 500.0)
        
        # Generate utilization metrics for instances active on this day
        # Look up instance IDs used on this date
        day_df = df_cur[df_cur["line_item_usage_start_date"].dt.strftime("%Y-%m-%d") == date_str]
        day_instances = set()
        for rid in day_df["line_item_resource_id"].unique():
            if isinstance(rid, str) and rid.startswith("i-"):
                day_instances.add(rid)
        
        utilization_metrics = []
        for inst in day_instances:
            # Generate CPU. Default is 25-50%
            avg_cpu = random.uniform(20.0, 45.0)
            
            # If this is the runaway training GPU instance (runaway_usage) let's give it high CPU
            # If this is a benign idle instance or similar, let's give it low CPU
            # For A2 (RDS db-staging-orphan-01) - it's RDS, but if it was EC2, we'd give low CPU.
            # Let's say if instance name contains 'idle' or similar, we give low CPU
            if "idle" in inst or "orphan" in inst:
                avg_cpu = random.uniform(0.5, 2.0)
                
            hourly_values = [max(0.1, avg_cpu + random.uniform(-3.0, 3.0)) for _ in range(24)]
            utilization_metrics.append({
                "resource_id": inst,
                "cpu_percent": avg_cpu,
                "cpu_utilization_hourly": hourly_values
            })
            
        daily_context[date_str] = {
            "traffic_volume": traffic_vol,
            "traffic_source": "ALB",
            "campaign_flag": False,
            "load_test_flag": False,
            "migration_flag": is_migration,
            "resource_utilization_metrics": utilization_metrics
        }
        
    # 9. Format CE daily records
    ce_list = []
    for _, row in df_ce.iterrows():
        ce_list.append({
            "date": str(row["date"]),
            "linked_account_id": account_id,
            "linked_account_name": str(row["linked_account_name"]),
            "service": str(row["service"]),
            "service_code": str(row["service_code"]),
            "region": str(row["region"]),
            "unblended_cost": float(row["unblended_cost"]),
            "is_estimated": str(row["is_estimated"]).lower() == "true"
        })
        
    # 10. Combine business context and CE daily into a single file
    combined_bc = {
        "daily_context": daily_context,
        "cost_explorer_daily": ce_list
    }
    combined_bc_json = json.dumps(combined_bc, indent=2)
    
    # Upload context to S3
    bc_key = "replay/business_context.json"
    print(f"Uploading replay business context to s3://{lakehouse_bucket}/{bc_key}...")
    s3.put_object(
        Bucket=lakehouse_bucket,
        Key=bc_key,
        Body=combined_bc_json.encode("utf-8"),
        ContentType="application/json",
        **extra_s3_args
    )
    
    print("\n-------------------------------------------------------------")
    print("Synthetic Replay Data preparation and upload COMPLETED.")
    print(f"Target CUR Bucket: s3://{cur_bucket}/{prefix}/")
    print(f"Business Context URI: s3://{lakehouse_bucket}/{bc_key}")
    print("-------------------------------------------------------------")
    print("\nNext steps to run replay:")
    print("1. Update terraform.tfvars to enable synthetic replay:")
    print("   synthetic_replay_enabled              = true")
    print(f"   synthetic_replay_business_context_uri = \"s3://{lakehouse_bucket}/{bc_key}\"")
    print("2. Run 'terraform apply' to deploy these variables to the Lambda workers.")
    print("3. Run the replay runner script: python scripts/run_replay.py --mode smoke")

if __name__ == "__main__":
    main()
