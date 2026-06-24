import pytest
import os
import json
from workers.normalizer import handler
import finops_common

def test_normalizer_local_fallback():
    # Test fallback mode when no S3 client or raw URI is present
    handler.s3_client = None
    if "LAKEHOUSE_BUCKET_NAME" in os.environ:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]

    event_data = {
        "run_id": "run-local",
        "correlation_id": "corr-local",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    assert resp["curated_data_uri"].startswith("s3://tf2-finops-lakehouse-bucket/cost/curated/")

def test_normalizer_s3_read_write_filtering():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"

    raw_cost_data = [
        # Valid EC2 untagged record
        {
            "account_id": "112233",
            "service": "AmazonEC2",
            "region": "us-east-1",
            "owner": "  ", # Untagged
            "cost": 100.00,
            "currency": "USD",
            "timestamp": "2026-06-24T00:00:00Z"
        },
        # Valid RDS tagged record
        {
            "account_id": "112233",
            "service": "AmazonRDS",
            "region": "us-east-1",
            "owner": "Finance",
            "cost": 250.00,
            "currency": "USD",
            "timestamp": "2026-06-24T00:00:00Z"
        },
        # Invalid: missing service
        {
            "account_id": "112233",
            "service": "",
            "region": "us-east-1",
            "owner": "Engineering",
            "cost": 50.00,
            "currency": "USD",
            "timestamp": "2026-06-24T00:00:00Z"
        },
        # Invalid: negative cost
        {
            "account_id": "112233",
            "service": "AmazonS3",
            "region": "us-east-1",
            "owner": "Engineering",
            "cost": -10.00,
            "currency": "USD",
            "timestamp": "2026-06-24T00:00:00Z"
        }
    ]

    raw_json = json.dumps(raw_cost_data).encode("utf-8")
    
    get_called = []
    put_called = []
    
    def fake_get_object(bucket, key):
        get_called.append((bucket, key))
        return raw_json
        
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })

    handler.s3_client = finops_common.FakeS3(
        get_object_func=fake_get_object,
        put_object_func=fake_put_object
    )

    event_data = {
        "run_id": "run-400",
        "correlation_id": "corr-400",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "status": "READY",
            "run_id": "run-400",
            "correlation_id": "corr-400",
            "worker": "cost_puller",
            "raw_data_uri": "s3://test-lakehouse/cost/raw/year=2026/month=06/day=24/run-400_raw.json",
            "details": {}
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    assert resp["curated_data_uri"] == "s3://test-lakehouse/cost/curated/year=2026/month=06/day=24/run-400_curated.parquet"

    # Assert S3 GET was called on the correct path
    assert len(get_called) == 1
    assert get_called[0] == ("test-lakehouse", "cost/raw/year=2026/month=06/day=24/run-400_raw.json")

    # Assert S3 PUT was called with filtered/curated records
    assert len(put_called) == 1
    assert put_called[0]["bucket"] == "test-lakehouse"
    assert put_called[0]["key"] == "cost/curated/year=2026/month=06/day=24/run-400_curated.parquet"

    curated_records = json.loads(put_called[0]["body"].decode("utf-8"))
    
    # 4 input records, 2 should be filtered out
    assert len(curated_records) == 2
    
    # First record should have owner overridden to "untagged"
    assert curated_records[0]["service"] == "AmazonEC2"
    assert curated_records[0]["owner"] == "untagged"
    assert curated_records[0]["cost"] == 100.00
    
    # Second record should preserve "Finance"
    assert curated_records[1]["service"] == "AmazonRDS"
    assert curated_records[1]["owner"] == "Finance"
    assert curated_records[1]["cost"] == 250.00

    # Clean up
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None
