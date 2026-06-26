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
            "team": "Finance",
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
    assert resp["curated_data_uri"] == "s3://test-lakehouse/cost/curated/account_id=112233/year=2026/month=06/run-400_curated.parquet"

    # Assert S3 GET was called on the correct path
    assert len(get_called) == 1
    assert get_called[0] == ("test-lakehouse", "cost/raw/year=2026/month=06/day=24/run-400_raw.json")

    # Assert S3 PUT was called with filtered/curated records
    assert len(put_called) == 1
    assert put_called[0]["bucket"] == "test-lakehouse"
    assert put_called[0]["key"] == "cost/curated/account_id=112233/year=2026/month=06/run-400_curated.parquet"

    # Parse Parquet data using pyarrow
    import io
    import pyarrow.parquet as pq
    table = pq.read_table(io.BytesIO(put_called[0]["body"]))
    curated_records = table.to_pylist()

    # 4 input records, 2 should be filtered out
    assert len(curated_records) == 2

    # First record should have owner overridden to "untagged"
    assert curated_records[0]["service"] == "AmazonEC2"
    assert curated_records[0]["owner"] == "untagged"
    assert curated_records[0]["cost"] == 100.00
    assert curated_records[0]["unblended_cost"] == 100.00
    assert curated_records[0]["service_code"] == "AmazonEC2"
    assert curated_records[0]["schema_version"] == "3.2.0"
    assert curated_records[0]["correlation_id"] == "corr-400"
    assert curated_records[0]["quality_score"] == 1.0

    # Second record should preserve "Finance"
    assert curated_records[1]["service"] == "AmazonRDS"
    assert curated_records[1]["owner"] == "Finance"
    assert curated_records[1]["cost"] == 250.00
    assert curated_records[1]["squad"] == "Finance"

    # Clean up
    if "LAKEHOUSE_BUCKET_NAME" in os.environ:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None


def test_normalizer_with_new_gzipped_envelope():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"

    raw_envelope = {
        "schema_version": "3.2.0",
        "tenant_id": "tenant-123",
        "account_id": "112233",
        "correlation_id": "corr-new",
        "idempotency_key": "idemp-new",
        "request_timestamp": "2026-06-24T00:00:00Z",
        "aws_cur_line_items": [
            {
                "line_item_usage_start_date": "2026-06-24T00:00:00Z",
                "line_item_usage_account_id": "112233",
                "line_item_product_code": "AmazonEC2",
                "line_item_unblended_cost": 100.0,
                "pricing_unit": "Hrs",
                "line_item_usage_amount": 24.0,
                "resource_tags_user_environment": "prod",
                "resource_tags_user_owner": "owner-1",
                "resource_tags_user_team": "team-1"
            }
        ],
        "aws_cost_explorer_daily": [],
        "resource_utilization_metrics": [],
        "quality": {
            "completeness_score": 0.8,
            "delayed_cur": True,
            "missing_cloudwatch": True
        }
    }

    import gzip
    envelope_bytes = json.dumps(raw_envelope).encode("utf-8")
    gzipped_bytes = gzip.compress(envelope_bytes)

    get_called = []
    put_called = []

    def fake_get_object(bucket, key):
        get_called.append((bucket, key))
        return gzipped_bytes

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
        "run_id": "run-new",
        "correlation_id": "corr-new",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "status": "READY",
            "run_id": "run-new",
            "correlation_id": "corr-new",
            "worker": "cost_puller",
            "raw_data_uri": "s3://test-lakehouse/cur/account_id=112233/year=2026/month=06/day=24/run-new_raw.json.gz",
            "details": {}
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    assert resp["curated_data_uri"] == "s3://test-lakehouse/cost/curated/account_id=112233/year=2026/month=06/run-new_curated.parquet"
    assert resp["telemetry_quality"] == 0.8

    # Verify quality flags are propagated from envelope
    assert resp["details"]["completeness_score"] == 0.8
    assert resp["details"]["delayed_cur"] is True
    assert resp["details"]["missing_cloudwatch"] is True
    assert resp["details"]["stale_cost_explorer"] is False
    assert resp["details"]["estimated_billing"] is False

    # Read Parquet output
    import io
    import pyarrow.parquet as pq
    table = pq.read_table(io.BytesIO(put_called[0]["body"]))
    curated_records = table.to_pylist()

    assert len(curated_records) == 1
    assert curated_records[0]["service"] == "AmazonEC2"
    assert curated_records[0]["unblended_cost"] == 100.0
    assert curated_records[0]["squad"] == "team-1"
    assert curated_records[0]["quality_score"] == 0.8

    # Clean up
    if "LAKEHOUSE_BUCKET_NAME" in os.environ:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None


def test_normalizer_fail_contract_check():
    """fail_contract_check operation records CONTRACT_MISMATCH."""
    handler.ddb_client = None
    if "RUN_STATE_TABLE_NAME" in os.environ:
        del os.environ["RUN_STATE_TABLE_NAME"]

    event_data = {
        "run_id": "run-contract-1",
        "correlation_id": "corr-contract-1",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "operation": "fail_contract_check",
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "FAILED_CONTRACT_CHECK"
    assert resp["details"]["failure_code"] == "CONTRACT_MISMATCH"
    assert resp["worker"] == "normalizer"


def test_normalizer_fail_contract_check_dynamodb():
    """fail_contract_check persists FAILED_CONTRACT_CHECK status to DynamoDB."""
    os.environ["RUN_STATE_TABLE_NAME"] = "test-run-state-table"

    put_called = []
    def fake_put_item(table_name, item):
        put_called.append(item)

    handler.ddb_client = finops_common.FakeDynamoDB(
        put_item_func=fake_put_item
    )

    event_data = {
        "run_id": "run-contract-2",
        "correlation_id": "corr-contract-2",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "operation": "fail_contract_check",
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "FAILED_CONTRACT_CHECK"

    # Verify DynamoDB put was called
    assert len(put_called) == 1
    assert put_called[0]["status"] == "FAILED_CONTRACT_CHECK"
    assert put_called[0]["failure_code"] == "CONTRACT_MISMATCH"
    assert put_called[0]["idempotency_key"] == "112233:2026-06:2026-06-24"

    # Clean up
    del os.environ["RUN_STATE_TABLE_NAME"]
    handler.ddb_client = None


def test_normalizer_quality_flags_from_event_data():
    """Quality flags from event_data override envelope quality."""
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"

    raw_envelope = {
        "schema_version": "3.2.0",
        "aws_cur_line_items": [
            {
                "line_item_usage_start_date": "2026-06-24T00:00:00Z",
                "line_item_usage_account_id": "112233",
                "line_item_product_code": "AmazonEC2",
                "line_item_unblended_cost": 50.0,
                "pricing_unit": "Hrs",
                "line_item_usage_amount": 24.0,
                "resource_tags_user_environment": "sandbox",
            }
        ],
        "quality": {
            "completeness_score": 0.5,
            "delayed_cur": False,
        }
    }

    raw_json = json.dumps(raw_envelope).encode("utf-8")

    get_called = []
    put_called = []

    def fake_get_object(bucket, key):
        get_called.append((bucket, key))
        return raw_json

    def fake_put_object(bucket, key, body):
        put_called.append({"bucket": bucket, "key": key})

    handler.s3_client = finops_common.FakeS3(
        get_object_func=fake_get_object, put_object_func=fake_put_object
    )

    # event_data quality flags should take precedence over envelope
    event_data = {
        "run_id": "run-quality-1",
        "correlation_id": "corr-quality-1",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "completeness_score": 0.9,
        "delayed_cur": True,
        "missing_cloudwatch": True,
        "ingestion": {
            "status": "READY",
            "run_id": "run-quality-1",
            "correlation_id": "corr-quality-1",
            "worker": "cost_puller",
            "raw_data_uri": "s3://test-lakehouse/cost/raw/year=2026/month=06/day=24/run-quality-1_raw.json",
            "details": {}
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    # event_data overrides envelope
    assert resp["details"]["completeness_score"] == 0.9
    assert resp["details"]["delayed_cur"] is True
    assert resp["details"]["missing_cloudwatch"] is True

    # Clean up
    if "LAKEHOUSE_BUCKET_NAME" in os.environ:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None


def test_normalizer_no_utcnow():
    """Ensure no datetime.utcnow() calls remain in normalizer handler."""
    import inspect
    source = inspect.getsource(handler)
    assert "datetime.utcnow()" not in source, \
        "normalizer handler still uses deprecated datetime.utcnow() — use datetime.now(timezone.utc) instead"
    assert "datetime.utcnow" not in source, \
        "normalizer handler still uses deprecated datetime.utcnow — use datetime.now(timezone.utc) instead"
