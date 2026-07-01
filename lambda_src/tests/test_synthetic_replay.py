import pytest
import os
import sys
import json
import gzip
from datetime import datetime
from workers.cost_puller import handler
import finops_common


def test_cost_puller_synthetic_replay_ready_path():
    # Set environments
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    os.environ["SYNTHETIC_REPLAY_ENABLED"] = "true"
    os.environ["SYNTHETIC_REPLAY_BUSINESS_CONTEXT_URI"] = "s3://company-cdo-112233-telemetry/replay/business_context.json"
    
    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })
        
    def fake_head_object(bucket, key):
        return {"ETag": '"abc123"'}

    fake_business_context = {
        "daily_context": {
            "2026-03-28": {
                "traffic_volume": 15000.0,
                "traffic_source": "ALB",
                "campaign_flag": False,
                "load_test_flag": False,
                "migration_flag": True,
                "resource_utilization_metrics": [
                    {
                        "resource_id": "i-00123",
                        "cpu_percent": 30.0,
                        "cpu_utilization_hourly": [30.0] * 24
                    }
                ]
            }
        },
        "cost_explorer_daily": [
            {
                "date": "2026-03-27",
                "linked_account_id": "112233",
                "linked_account_name": "sandbox",
                "service": "Amazon Elastic Compute Cloud - Compute",
                "service_code": "AmazonEC2",
                "region": "us-east-1",
                "unblended_cost": 120.0,
                "is_estimated": False
            }
        ]
    }

    def fake_get_object(bucket, key):
        if "business_context.json" in key:
            return json.dumps(fake_business_context).encode("utf-8")
        # Default manifest
        return json.dumps({
            "executionId": "exec-12345",
            "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233:export/cur2",
            "columns": [
                {"name": "bill_billing_period_start_date", "type": "timestamp"},
                {"name": "line_item_usage_start_date", "type": "timestamp"},
                {"name": "line_item_usage_account_id", "type": "string"},
                {"name": "line_item_product_code", "type": "string"},
                {"name": "line_item_usage_type", "type": "string"},
                {"name": "line_item_usage_amount", "type": "double"},
                {"name": "pricing_unit", "type": "string"},
                {"name": "line_item_unblended_cost", "type": "double"},
                {"name": "resource_tags_user_environment", "type": "string"},
            ],
            "dataFiles": ["s3://tf2-finops-cur-export-bucket/cur/manifest/data/BILLING_PERIOD=2026-03/part.parquet"]
        }).encode("utf-8")
        
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object,
        get_object_func=fake_get_object,
        head_object_func=fake_head_object
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = finops_common.FakeSTS(get_caller_identity_func=lambda: {"Account": "112233"})
    
    event_data = {
        "run_id": "run-replay-ready",
        "correlation_id": "corr-replay-ready",
        "account_id": "112233",
        "cost_period": "2026-03",
        "execution_date": "2026-03-28",
    }
    
    try:
        resp = handler.handle_request(event_data, None)
        assert resp["status"] == "READY"
        assert resp["details"]["business_context"][0]["traffic_volume"] == 15000.0
        assert resp["details"]["business_context"][0]["migration_flag"] is True
        assert resp["details"]["resource_utilization_metrics"][0]["resource_id"] == "i-00123"
        assert resp["details"]["missing_cloudwatch"] is False
    finally:
        # Cleanup
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
        del os.environ["CUR_SOURCE_BUCKET"]
        del os.environ["SYNTHETIC_REPLAY_ENABLED"]
        del os.environ["SYNTHETIC_REPLAY_BUSINESS_CONTEXT_URI"]
        handler.s3_client = None
        handler.sts_client = None


def test_cost_puller_synthetic_replay_delayed_ce_fallback():
    # Set environments
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    os.environ["SYNTHETIC_REPLAY_ENABLED"] = "true"
    os.environ["SYNTHETIC_REPLAY_BUSINESS_CONTEXT_URI"] = "s3://company-cdo-112233-telemetry/replay/business_context.json"
    
    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })
        
    def fake_head_object(bucket, key):
        # Trigger manifest error -> CUR delay
        raise Exception("Manifest not found")

    fake_business_context = {
        "daily_context": {
            "2026-03-28": {
                "traffic_volume": 15000.0,
                "traffic_source": "ALB",
                "campaign_flag": False,
                "load_test_flag": False,
                "migration_flag": True,
                "resource_utilization_metrics": []
            }
        },
        "cost_explorer_daily": [
            {
                "date": "2026-03-27",
                "linked_account_id": "112233",
                "linked_account_name": "sandbox",
                "service": "Amazon Elastic Compute Cloud - Compute",
                "service_code": "AmazonEC2",
                "region": "us-east-1",
                "unblended_cost": 120.0,
                "is_estimated": False
            }
        ]
    }

    def fake_get_object(bucket, key):
        if "business_context.json" in key:
            return json.dumps(fake_business_context).encode("utf-8")
        raise Exception("Not found")
        
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object,
        get_object_func=fake_get_object,
        head_object_func=fake_head_object
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = finops_common.FakeSTS(get_caller_identity_func=lambda: {"Account": "112233"})
    
    event_data = {
        "run_id": "run-replay-delayed",
        "correlation_id": "corr-replay-delayed",
        "account_id": "112233",
        "cost_period": "2026-03",
        "execution_date": "2026-03-28",
    }
    
    try:
        resp = handler.handle_request(event_data, None)
        assert resp["status"] == "READY"
        assert resp["details"]["delayed_cur"] is True
        
        # Verify S3 writes: raw data and features
        raw_write = next(p for p in put_called if "_raw.json.gz" in p["key"])
        raw_bytes = raw_write["body"]
        decompressed = gzip.decompress(raw_bytes)
        envelope = json.loads(decompressed.decode("utf-8"))
        assert len(envelope["aws_cost_explorer_daily"]) == 1
        assert envelope["aws_cost_explorer_daily"][0]["unblended_cost"] == 120.0
    finally:
        # Cleanup
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
        del os.environ["CUR_SOURCE_BUCKET"]
        del os.environ["SYNTHETIC_REPLAY_ENABLED"]
        del os.environ["SYNTHETIC_REPLAY_BUSINESS_CONTEXT_URI"]
        handler.s3_client = None
        handler.sts_client = None


def test_generate_business_context():
    import tempfile
    import shutil
    
    with tempfile.TemporaryDirectory() as tmpdir:
        out_full = os.path.join(tmpdir, "bc_full.json")
        out_smoke = os.path.join(tmpdir, "bc_smoke.json")
        
        import subprocess
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/generate_business_context.py"))
        
        # Test full generation
        res = subprocess.run([
            sys.executable, script_path,
            "--scope", "full",
            "--account-id", "123456789012",
            "--output", out_full,
            "--seed", "tf2-finops-synthetic-v1"
        ], capture_output=True, text=True)
        assert res.returncode == 0
        
        with open(out_full, "r") as f:
            full_data = json.load(f)
            
        assert len(full_data["daily_context"]) == 92
        
        # Test smoke generation
        res_smoke = subprocess.run([
            sys.executable, script_path,
            "--scope", "smoke",
            "--account-id", "123456789012",
            "--output", out_smoke,
            "--seed", "tf2-finops-synthetic-v1"
        ], capture_output=True, text=True)
        assert res_smoke.returncode == 0
        
        with open(out_smoke, "r") as f:
            smoke_data = json.load(f)
            
        assert len(smoke_data["daily_context"]) == 16
        
        # Deterministic check: run full again and check if byte-identical
        out_full_2 = os.path.join(tmpdir, "bc_full_2.json")
        subprocess.run([
            sys.executable, script_path,
            "--scope", "full",
            "--account-id", "123456789012",
            "--output", out_full_2,
            "--seed", "tf2-finops-synthetic-v1"
        ], check=True)
        
        with open(out_full, "rb") as f1, open(out_full_2, "rb") as f2:
            assert f1.read() == f2.read()
            
        # Target validations
        # B2 days have migration_flag = true
        b2_context = full_data["daily_context"].get("2026-03-28")
        assert b2_context is not None
        assert b2_context["migration_flag"] is True
        assert b2_context["traffic_source"] == "Synthetic"
        
        # A2 and A6 days have no benign flags (campaign, load_test, migration are false)
        a2_context = full_data["daily_context"].get("2026-03-22")
        assert a2_context is not None
        assert a2_context["migration_flag"] is False
        assert a2_context["campaign_flag"] is False
        assert a2_context["load_test_flag"] is False
        
        # A2 RDS resource db-staging-orphan-01 is present on A2 day with low utilization
        a2_rds_metric = next(m for m in a2_context["resource_utilization_metrics"] if m["resource_id"] == "arn:aws:rds:us-east-1:acct:db:db-staging-orphan-01")
        assert a2_rds_metric["cpu_percent"] == 1.2
        assert a2_rds_metric["cpu_utilization_hourly"] == [1.2] * 24
        
        # Check required fields exist in daily_context entries
        for date_str, ctx in full_data["daily_context"].items():
            assert "traffic_volume" in ctx
            assert ctx["traffic_source"] == "Synthetic"
            assert "campaign_flag" in ctx
            assert "load_test_flag" in ctx
            assert "migration_flag" in ctx
            
        # No fake account IDs remain in linked_account_id after projection
        for row in full_data["cost_explorer_daily"]:
            assert row["linked_account_id"] == "123456789012"

