#!/usr/bin/env python3
import os
import sys
import json
import argparse
import datetime
import time
import uuid
import subprocess
import boto3

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

def main():
    parser = argparse.ArgumentParser(description="Run synthetic cost replay backtest against Sandbox Step Functions.")
    parser.add_argument("--mode", choices=["smoke", "warmup", "full"], default="smoke",
                        help="Replay mode: smoke (3 days), warmup (20 days), or full (92 days/3 months).")
    parser.add_argument("--account-id", help="Target AWS account ID. If omitted, will query via STS.")
    parser.add_argument("--region", default="ap-southeast-1", help="AWS region (default: ap-southeast-1).")
    parser.add_argument("--state-machine-arn", help="Step Functions State Machine ARN.")
    parser.add_argument("--table-name", help="DynamoDB account policy table name.")
    parser.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds for SFN executions.")
    
    args = parser.parse_args()
    
    sandbox_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../environments/sandbox"))
    tf_outputs = get_terraform_outputs(sandbox_dir)
    
    # 1. Resolve Account ID
    account_id = args.account_id
    if not account_id:
        account_id = get_real_account_id()
    
    # 2. Resolve State Machine ARN
    sfn_arn = args.state_machine_arn
    if not sfn_arn:
        if "state_machine_arn" in tf_outputs:
            sfn_arn = tf_outputs["state_machine_arn"]["value"]
        else:
            sfn_arn = f"arn:aws:states:{args.region}:{account_id}:stateMachine:tf2-finops-sandbox-workflow"
            
    # 3. Resolve DynamoDB Account Policy Table Name
    policy_table = args.table_name
    if not policy_table:
        policy_table = "tf2-finops-sandbox-account-policy" # Default
        
    print(f"Replay target Account ID: {account_id}")
    print(f"Replay state machine ARN: {sfn_arn}")
    print(f"Replay account policy table: {policy_table}")
    
    # 4. Seed the account-policy row
    print(f"Seeding account policy for {account_id} in {policy_table}...")
    ddb = boto3.client("dynamodb", region_name=args.region)
    try:
        ddb.put_item(
            TableName=policy_table,
            Item={
                "account_id": {"S": account_id},
                "environment": {"S": "sandbox"}
            }
        )
        print("Account policy seeded successfully.")
    except Exception as e:
        print(f"Error seeding account policy: {e}")
        print("Please ensure the DynamoDB table exists and you have write permissions.")
        sys.exit(1)
        
    # 5. Define date range based on mode
    # Smoke: 2026-03-01 to 2026-03-03
    # Warmup: 2026-03-01 to 2026-03-20 (up to the RDS orphan anomaly date)
    # Full: 2026-03-01 to 2026-05-31
    start_date = datetime.date(2026, 3, 1)
    if args.mode == "smoke":
        end_date = datetime.date(2026, 3, 3)
    elif args.mode == "warmup":
        end_date = datetime.date(2026, 3, 20)
    else:
        end_date = datetime.date(2026, 5, 31)
        
    delta = end_date - start_date
    dates_to_replay = [start_date + datetime.timedelta(days=i) for i in range(delta.days + 1)]
    print(f"Mode: {args.mode.upper()}")
    print(f"Replaying {len(dates_to_replay)} daily executions sequentially from {start_date} to {end_date}...")
    
    sfn = boto3.client("stepfunctions", region_name=args.region)
    
    success_count = 0
    fail_count = 0
    
    for i, d in enumerate(dates_to_replay):
        date_str = d.strftime("%Y-%m-%d")
        exec_date_full = date_str
        run_id = f"rep-{date_str}-{str(uuid.uuid4())[:8]}"
        correlation_id = str(uuid.uuid4())
        
        print(f"\n[{i+1}/{len(dates_to_replay)}] Starting replay execution for {date_str} (run_id: {run_id})...")
        
        # Prepare execution input
        execution_input = {
            "run_id": run_id,
            "correlation_id": correlation_id,
            "account_id": account_id,
            "execution_date": exec_date_full,
            "cost_period": date_str,
            "is_ad_hoc": True,
            "tenant_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tf2-finops:{account_id}"))
        }
        
        try:
            # Start Step Functions Execution
            exec_name = f"replay-{date_str}-{int(time.time())}"
            resp = sfn.start_execution(
                stateMachineArn=sfn_arn,
                name=exec_name,
                input=json.dumps(execution_input)
            )
            exec_arn = resp["executionArn"]
            print(f"Execution started. ARN: {exec_arn}")
            
            # Poll status
            print("Polling status...", end="", flush=True)
            status = "RUNNING"
            while status == "RUNNING":
                time.sleep(args.poll_interval)
                desc = sfn.describe_execution(executionArn=exec_arn)
                status = desc["status"]
                print(".", end="", flush=True)
                
            print(f" Finished with status: {status}")
            if status == "SUCCEEDED":
                success_count += 1
            else:
                fail_count += 1
                print(f"Warning: Execution {exec_name} failed or timed out.")
                
        except Exception as ex:
            print(f"Failed to start/poll execution for {date_str}: {ex}")
            fail_count += 1
            
    print("\n=============================================================")
    print("Synthetic Replay Execution Summary:")
    print(f"Total Dates Replayed: {len(dates_to_replay)}")
    print(f"Succeeded:            {success_count}")
    print(f"Failed/Interrupted:   {fail_count}")
    print("=============================================================")
    
if __name__ == "__main__":
    main()
