import pytest
import os
import json
from workers.cost_puller import handler
import finops_common

def test_cost_puller_simulated_modes():
    # Test CUR_DELAY override
    event_delay = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
        "action": "simulate-cur-delay"
    }
    resp = handler.handle_request(event_delay, None)
    assert resp["status"] == "CUR_DELAY"
    assert "not yet exported" in resp["details"]["error"]

    # Test CE_THROTTLED override
    event_throttled = {
        "run_id": "run-2",
        "correlation_id": "corr-2",
        "cost_period": "2026-06",
        "action": "simulate-ce-throttled"
    }
    resp2 = handler.handle_request(event_throttled, None)
    assert resp2["status"] == "CE_THROTTLED"
    assert "rate limit exceeded" in resp2["details"]["error"]

def test_cost_puller_standard_s3_write():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse-bucket"
    
    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })
        
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object
    )

    event_data = {
        "run_id": "run-999",
        "correlation_id": "corr-999",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    assert resp["raw_data_uri"].startswith("s3://test-lakehouse-bucket/cost/raw/")
    
    assert len(put_called) == 1
    assert put_called[0]["bucket"] == "test-lakehouse-bucket"
    assert "cost/raw/year=2026/month=06/day=24/run-999_raw.json" in put_called[0]["key"]
    
    # Verify body contents
    records = json.loads(put_called[0]["body"].decode("utf-8"))
    assert len(records) == 1
    assert records[0]["account_id"] == "112233"
    assert records[0]["service"] == "AmazonEC2"
    assert records[0]["cost"] == 150.00

    # Clean up
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None
