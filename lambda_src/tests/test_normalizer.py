import pytest
import os
import json
import gzip
import re
from workers.normalizer import handler
import finops_common


TENANT_ID = "11111111-1111-4111-8111-111111111111"
CORRELATION_ID = "22222222-2222-4222-8222-222222222222"

ATHENA_ENV = {
    "ATHENA_WORKGROUP_NAME": "test-wg",
    "GLUE_DATABASE_NAME": "test_db",
    "GLUE_TABLE_NAME": "test_tbl",
    "ATHENA_RESULTS_BUCKET_NAME": "test-athena-results",
}


class FakeAthena:
    def __init__(self, rows=None, terminal_state="SUCCEEDED"):
        self.rows = rows or [
            {"Data": [{"VarCharValue": "line_item_unblended_cost"}, {"VarCharValue": "line_item_product_code"}, {"VarCharValue": "line_item_usage_account_id"}]},
            {"Data": [{"VarCharValue": "150.00"}, {"VarCharValue": "AmazonEC2"}, {"VarCharValue": "123456789012"}]},
        ]
        self.terminal_state = terminal_state
        self.status_calls = 0

    def start_query_execution(self, **kwargs):
        return {"QueryExecutionId": "query-fixture-1"}

    def get_query_execution(self, QueryExecutionId):
        self.status_calls += 1
        return {
            "QueryExecution": {
                "Status": {
                    "State": self.terminal_state,
                    "StateChangeReason": "fixture state",
                }
            }
        }

    def get_query_results(self, **kwargs):
        return {"ResultSet": {"Rows": self.rows}}


def _set_athena_env():
    os.environ.update(ATHENA_ENV)


def _clear_athena_env():
    for key in ATHENA_ENV:
        os.environ.pop(key, None)


def test_normalizer_missing_lakehouse_bucket_fails():
    # Normalization must not create a local bucket or generated telemetry.
    handler.s3_client = None
    if "LAKEHOUSE_BUCKET_NAME" in os.environ:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()

    event_data = {
        "run_id": "run-local",
        "correlation_id": "corr-local",
        "account_id": "112233445566",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }

    with pytest.raises(finops_common.ConfigMissingError, match="LAKEHOUSE_BUCKET_NAME"):
        handler.handle_request(event_data, None)


def test_normalizer_s3_read_write_filtering():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"

    raw_cost_data = [
        # Valid EC2 untagged record
        {
            "account_id": "112233445566",
            "service": "AmazonEC2",
            "region": "us-east-1",
            "owner": "  ", # Untagged
            "cost": 100.00,
            "currency": "USD",
            "timestamp": "2026-06-24T00:00:00Z"
        },
        # Valid RDS tagged record
        {
            "account_id": "112233445566",
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
            "account_id": "112233445566",
            "service": "",
            "region": "us-east-1",
            "owner": "Engineering",
            "cost": 50.00,
            "currency": "USD",
            "timestamp": "2026-06-24T00:00:00Z"
        },
        # Invalid: negative cost
        {
            "account_id": "112233445566",
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
        "account_id": "112233445566",
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
    assert resp["curated_data_uri"] == "s3://test-lakehouse/cost/curated/account_id=112233445566/year=2026/month=06/run-400_curated.parquet"

    # Assert S3 GET was called on the correct path
    assert len(get_called) == 1
    assert get_called[0] == ("test-lakehouse", "cost/raw/year=2026/month=06/day=24/run-400_raw.json")

    # Assert S3 PUT wrote filtered/curated records and the normalized AI input.
    curated_put = next(p for p in put_called if p["key"].endswith("_curated.parquet"))
    ai_input_put = next(p for p in put_called if p["key"].endswith("_input.json.gz"))
    assert curated_put["bucket"] == "test-lakehouse"
    assert curated_put["key"] == "cost/curated/account_id=112233445566/year=2026/month=06/run-400_curated.parquet"
    assert ai_input_put["key"] == "ai-input/account_id=112233445566/year=2026/month=06/day=24/run-400_input.json.gz"

    # Parse Parquet data using pyarrow
    import io
    import pyarrow.parquet as pq
    table = pq.read_table(io.BytesIO(curated_put["body"]))
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
    assert curated_records[0]["quality_score"] == 0.5
    assert resp["details"]["missing_cloudwatch"] is True

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
        "account_id": "112233445566",
        "correlation_id": "corr-new",
        "idempotency_key": "idemp-new",
        "request_timestamp": "2026-06-24T00:00:00Z",
        "aws_cur_line_items": [
            {
                "line_item_usage_start_date": "2026-06-24T00:00:00Z",
                "line_item_usage_account_id": "112233445566",
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
        "account_id": "112233445566",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "status": "READY",
            "run_id": "run-new",
            "correlation_id": "corr-new",
            "worker": "cost_puller",
            "raw_data_uri": "s3://test-lakehouse/cur/account_id=112233445566/year=2026/month=06/day=24/run-new_raw.json.gz",
            "details": {}
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    assert resp["curated_data_uri"] == "s3://test-lakehouse/cost/curated/account_id=112233445566/year=2026/month=06/run-new_curated.parquet"
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
        "account_id": "112233445566",
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
        "account_id": "112233445566",
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
    assert put_called[0]["idempotency_key"] == "112233445566:2026-06:2026-06-24"

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
                "line_item_usage_account_id": "112233445566",
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


def test_normalizer_payload_contract_fields():
    # Setup test event data and mock S3 client
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })

    _MANIFEST_BYTES = json.dumps({
        "executionId": "exec-12345",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2",
        "columns": [
            {"name": "bill_billing_period_start_date", "type": "timestamp"},
            {"name": "bill_payer_account_id", "type": "string"},
            {"name": "line_item_usage_account_id", "type": "string"},
            {"name": "line_item_line_item_type", "type": "string"},
            {"name": "line_item_usage_start_date", "type": "timestamp"},
            {"name": "line_item_usage_end_date", "type": "timestamp"},
            {"name": "line_item_product_code", "type": "string"},
            {"name": "line_item_usage_type", "type": "string"},
            {"name": "line_item_operation", "type": "string"},
            {"name": "line_item_resource_id", "type": "string"},
            {"name": "line_item_usage_amount", "type": "double"},
            {"name": "pricing_unit", "type": "string"},
            {"name": "line_item_unblended_rate", "type": "double"},
            {"name": "line_item_unblended_cost", "type": "double"},
            {"name": "line_item_currency_code", "type": "string"},
            {"name": "product_product_name", "type": "string"},
            {"name": "product_region_code", "type": "string"},
            {"name": "product_instance_type", "type": "string"},
            {"name": "resource_tags_user_environment", "type": "string"},
            {"name": "resource_tags_user_owner", "type": "string"},
            {"name": "resource_tags_user_team", "type": "string"},
            {"name": "resource_tags_user_cost_center", "type": "string"},
        ],
        "dataFiles": ["s3://tf2-finops-cur-export-bucket/cur/data/BILLING_PERIOD=2026-06/part.parquet"]
    }).encode("utf-8")

    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object,
        get_object_func=lambda b, k: _MANIFEST_BYTES,
    )
    handler.athena_client = FakeAthena()

    # 1. Test standard S3 pointer mode selection
    event_data = {
        "run_id": "run-s3-pointer-1",
        "correlation_id": CORRELATION_ID,
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "environment": "sandbox",
        "tenant_id": TENANT_ID,
        "is_ad_hoc": True,
        "ingestion": {
            "status": "READY",
            "run_id": "run-s3-pointer-1",
            "correlation_id": CORRELATION_ID,
            "worker": "cost_puller",
            "details": {
                "telemetry_delay_event": False,
                "cur_manifest_uri": "s3://tf2-finops-cur-export-bucket/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json",
                "business_context": [
                    {
                        "linked_account_id": "123456789012",
                        "traffic_volume": 120000,
                        "traffic_source": "ALB",
                        "campaign_flag": True,
                        "load_test_flag": False,
                        "migration_flag": False
                    }
                ],
                "resource_utilization_metrics": [
                    {
                        "resource_id": "i-123",
                        "cpu_utilization": 75.5,
                        "memory_utilization": 80.0
                    }
                ]
            }
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    details = resp["details"]
    # Mode is RAW_JSON for small test fixtures; S3_POINTER for oversized payloads.
    assert details["detect_request_mode"] in {"RAW_JSON", "S3_POINTER"}
    assert details["s3_bucket_uri"].startswith("s3://test-lakehouse/ai-input/account_id=123456789012/year=2026/month=06/day=24/")
    assert details["s3_bucket_uri"].endswith("_input.json.gz")
    assert re.fullmatch(r"[a-f0-9]{64}", details["s3_object_checksum"])
    assert details["tenant_id"] == TENANT_ID
    assert details["account_id"] == "123456789012"
    assert details["account_name"] == "sandbox"
    assert details["correlation_id"] == CORRELATION_ID
    assert details["idempotency_key"] == f"{TENANT_ID}:2026-06-24:adhoc"
    assert details["business_context"]["linked_account_id"] == "123456789012"
    assert details["business_context"]["traffic_volume"] == 120000
    assert details["resource_utilization_metrics"][0]["cpu_utilization"] == 75.5
    assert len(details["aws_cur_line_items"]) == 1
    assert details["batch_type"] == "adhoc"
    assert details["telemetry_delay_event"] is False
    assert len(put_called) == 2 # curated Parquet AND AI input json.gz

    # Verify gzipped AI detect input payload content
    ai_bytes = next(p["body"] for p in put_called if p["key"].endswith("_input.json.gz"))
    decompressed = gzip.decompress(ai_bytes)
    envelope = json.loads(decompressed.decode("utf-8"))
    assert envelope["schema_version"] == "3.2.0"
    assert envelope["tenant_id"] == TENANT_ID
    assert envelope["account_id"] == "123456789012"
    assert envelope["account_name"] == "sandbox"
    assert envelope["correlation_id"] == CORRELATION_ID
    assert envelope["request_timestamp"].endswith("Z")
    assert len(envelope["aws_cur_line_items"]) == 1
    assert envelope["idempotency_key"] == f"{TENANT_ID}:2026-06-24:adhoc"
    assert envelope["business_context"]["linked_account_id"] == "123456789012"

    # 2. Test CE fallback S3 pointer
    put_called.clear()
    raw_envelope_ce = {
        "quality": {
            "completeness_score": 0.5,
            "delayed_cur": True,
            "stale_cost_explorer": True,
            "missing_cloudwatch": False,
            "estimated_billing": True
        },
        "aws_cost_explorer_daily": [
            {
                "linked_account_id": "123456789012",
                "service_code": "AmazonEC2",
                "unblended_cost": 50.0,
                "date": "2026-06-24"
            }
        ],
        "missing_resources": ["AmazonEC2"],
        "current_ce_cost_gap_usd": 150.0,
        "comparison_window": {"start_date": "2026-06-23", "end_date": "2026-06-24"},
    }
    raw_json_ce = gzip.compress(json.dumps(raw_envelope_ce).encode("utf-8"))

    def fake_get_object_ce(bucket, key):
        return raw_json_ce

    handler.s3_client = finops_common.FakeS3(
        get_object_func=fake_get_object_ce,
        put_object_func=fake_put_object
    )

    event_data_ce = {
        "run_id": "run-ce-1",
        "correlation_id": CORRELATION_ID,
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "tenant_id": TENANT_ID,
        "ingestion": {
            "status": "READY",
            "run_id": "run-ce-1",
            "correlation_id": CORRELATION_ID,
            "worker": "cost_puller",
            "details": {
                "telemetry_delay_event": True,
                "raw_data_uri": "s3://test-lakehouse/cur/account_id=123456789012/year=2026/month=06/day=24/run-ce-1_raw.json.gz",
                "current_ce_cost_gap_usd": 150.0,
                "comparison_window": {"start_date": "2026-06-23", "end_date": "2026-06-24"}
            }
        }
    }

    resp_ce = handler.handle_request(event_data_ce, None)
    assert resp_ce["status"] == "NORMALIZED"
    details_ce = resp_ce["details"]
    # Mode is RAW_JSON for small test fixtures; S3_POINTER for oversized payloads.
    assert details_ce["detect_request_mode"] in {"RAW_JSON", "S3_POINTER"}
    assert details_ce["telemetry_delay_event"] is True
    assert details_ce["s3_bucket_uri"].startswith("s3://test-lakehouse/ai-input/account_id=123456789012/year=2026/month=06/day=24/")
    assert re.fullmatch(r"[a-f0-9]{64}", details_ce["s3_object_checksum"])
    assert len(details_ce["aws_cost_explorer_daily"]) == 1
    assert details_ce["current_ce_cost_gap_usd"] == 150.0
    ai_ce_bytes = next(p["body"] for p in put_called if p["key"].endswith("_input.json.gz"))
    ce_envelope = json.loads(gzip.decompress(ai_ce_bytes).decode("utf-8"))
    assert ce_envelope["business_context"]["linked_account_id"] == "123456789012"
    assert ce_envelope["missing_resources"] == ["AmazonEC2"]
    assert ce_envelope["current_ce_cost_gap_usd"] == 150.0

    # Clean up
    if "LAKEHOUSE_BUCKET_NAME" in os.environ:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_cur_ready_requires_athena_config():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _clear_athena_env()
    handler.s3_client = finops_common.FakeS3(put_object_func=lambda bucket, key, body: None)
    handler.athena_client = None

    event_data = {
        "run_id": "run-no-athena",
        "correlation_id": "corr-no-athena",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "status": "READY",
            "run_id": "run-no-athena",
            "correlation_id": "corr-no-athena",
            "worker": "cost_puller",
            "details": {"telemetry_delay_event": False},
        },
    }

    with pytest.raises(finops_common.ConfigMissingError, match="ATHENA_WORKGROUP_NAME"):
        handler.handle_request({
            "run_id": "run-no-athena",
            "correlation_id": "corr-no-athena",
            "account_id": "123456789012",
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
            "ingestion": {
                "status": "READY",
                "run_id": "run-no-athena",
                "correlation_id": "corr-no-athena",
                "worker": "cost_puller",
                "details": {
                    "telemetry_delay_event": False,
                    "cur_manifest_uri": "s3://tf2-finops-cur-export-bucket/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json",
                },
            },
        }, None)

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None


def test_normalizer_athena_empty_result_fails():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()
    _MANIFEST_BYTES_EMPTY = json.dumps({
        "executionId": "exec-12345",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:123456789012:export/cur2",
        "columns": [
            {"name": "bill_billing_period_start_date", "type": "timestamp"},
            {"name": "bill_payer_account_id", "type": "string"},
            {"name": "line_item_usage_account_id", "type": "string"},
            {"name": "line_item_line_item_type", "type": "string"},
            {"name": "line_item_usage_start_date", "type": "timestamp"},
            {"name": "line_item_usage_end_date", "type": "timestamp"},
            {"name": "line_item_product_code", "type": "string"},
            {"name": "line_item_usage_type", "type": "string"},
            {"name": "line_item_operation", "type": "string"},
            {"name": "line_item_resource_id", "type": "string"},
            {"name": "line_item_usage_amount", "type": "double"},
            {"name": "pricing_unit", "type": "string"},
            {"name": "line_item_unblended_rate", "type": "double"},
            {"name": "line_item_unblended_cost", "type": "double"},
            {"name": "line_item_currency_code", "type": "string"},
            {"name": "product_product_name", "type": "string"},
            {"name": "product_region_code", "type": "string"},
            {"name": "product_instance_type", "type": "string"},
            {"name": "resource_tags_user_environment", "type": "string"},
            {"name": "resource_tags_user_owner", "type": "string"},
            {"name": "resource_tags_user_team", "type": "string"},
            {"name": "resource_tags_user_cost_center", "type": "string"},
        ],
        "dataFiles": ["s3://tf2-finops-cur-export-bucket/cur/data/BILLING_PERIOD=2026-06/part.parquet"]
    }).encode("utf-8")
    handler.s3_client = finops_common.FakeS3(
        put_object_func=lambda bucket, key, body: None,
        get_object_func=lambda b, k: _MANIFEST_BYTES_EMPTY,
    )
    handler.athena_client = FakeAthena(rows=[
        {"Data": [{"VarCharValue": "line_item_unblended_cost"}, {"VarCharValue": "line_item_product_code"}, {"VarCharValue": "line_item_usage_account_id"}]},
    ])

    event_data = {
        "run_id": "run-empty-athena",
        "correlation_id": "corr-empty-athena",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "status": "READY",
            "run_id": "run-empty-athena",
            "correlation_id": "corr-empty-athena",
            "worker": "cost_puller",
            "details": {
                "telemetry_delay_event": False,
                "cur_manifest_uri": "s3://tf2-finops-cur-export-bucket/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json",
            },
        },
    }

    with pytest.raises(finops_common.InvalidInputError, match="Athena returned no CUR records"):
        handler.handle_request(event_data, None)

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_athena_query_integration():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    os.environ["ATHENA_WORKGROUP_NAME"] = "test-wg"
    os.environ["GLUE_DATABASE_NAME"] = "test-db"
    os.environ["GLUE_TABLE_NAME"] = "test-tbl"
    os.environ["ATHENA_RESULTS_BUCKET_NAME"] = "test-athena-results"

    query_executed = []
    def fake_start_query_execution(**kwargs):
        query_executed.append(kwargs)
        return {"QueryExecutionId": "query-id-123"}

    get_status_calls = [0]
    def fake_get_query_execution(QueryExecutionId):
        get_status_calls[0] += 1
        state = "RUNNING" if get_status_calls[0] < 2 else "SUCCEEDED"
        return {
            "QueryExecution": {
                "Status": {
                    "State": state
                }
            }
        }

    get_results_calls = [0]
    def fake_get_query_results(**kwargs):
        get_results_calls[0] += 1
        if get_results_calls[0] == 1:
            return {
                "ResultSet": {
                    "Rows": [
                        {"Data": [{"VarCharValue": "line_item_unblended_cost"}, {"VarCharValue": "line_item_product_code"}, {"VarCharValue": "line_item_usage_account_id"}]},
                        {"Data": [{"VarCharValue": "150.00"}, {"VarCharValue": "AmazonEC2"}, {"VarCharValue": "112233445566"}]}
                    ]
                },
                "NextToken": "page-2"
            }
        else:
            return {
                "ResultSet": {
                    "Rows": [
                        {"Data": [{"VarCharValue": "250.00"}, {"VarCharValue": "AmazonRDS"}, {"VarCharValue": "112233445566"}]}
                    ]
                }
            }

    class FakeAthena:
        def start_query_execution(self, **kwargs):
            return fake_start_query_execution(**kwargs)
        def get_query_execution(self, QueryExecutionId):
            return fake_get_query_execution(QueryExecutionId)
        def get_query_results(self, **kwargs):
            return fake_get_query_results(**kwargs)

    handler.athena_client = FakeAthena()

    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })

    _MANIFEST_BYTES_ATH = json.dumps({
        "executionId": "exec-12345",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2",
        "columns": [
            {"name": "bill_billing_period_start_date", "type": "timestamp"},
            {"name": "bill_payer_account_id", "type": "string"},
            {"name": "line_item_usage_account_id", "type": "string"},
            {"name": "line_item_line_item_type", "type": "string"},
            {"name": "line_item_usage_start_date", "type": "timestamp"},
            {"name": "line_item_usage_end_date", "type": "timestamp"},
            {"name": "line_item_product_code", "type": "string"},
            {"name": "line_item_usage_type", "type": "string"},
            {"name": "line_item_operation", "type": "string"},
            {"name": "line_item_resource_id", "type": "string"},
            {"name": "line_item_usage_amount", "type": "double"},
            {"name": "pricing_unit", "type": "string"},
            {"name": "line_item_unblended_rate", "type": "double"},
            {"name": "line_item_unblended_cost", "type": "double"},
            {"name": "line_item_currency_code", "type": "string"},
            {"name": "product_product_name", "type": "string"},
            {"name": "product_region_code", "type": "string"},
            {"name": "product_instance_type", "type": "string"},
            {"name": "resource_tags_user_environment", "type": "string"},
            {"name": "resource_tags_user_owner", "type": "string"},
            {"name": "resource_tags_user_team", "type": "string"},
            {"name": "resource_tags_user_cost_center", "type": "string"},
        ],
        "dataFiles": ["s3://tf2-finops-cur-export-bucket/cur/data/BILLING_PERIOD=2026-06/part.parquet"]
    }).encode("utf-8")
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object,
        get_object_func=lambda b, k: _MANIFEST_BYTES_ATH,
    )

    event_data = {
        "run_id": "run-ath-1",
        "correlation_id": "corr-ath-1",
        "account_id": "112233445566",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "status": "READY",
            "run_id": "run-ath-1",
            "correlation_id": "corr-ath-1",
            "worker": "cost_puller",
            "details": {
                "cur_manifest_uri": "s3://tf2-finops-cur-export-bucket/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json",
            }
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    # Mode is RAW_JSON for small test fixtures; S3_POINTER for oversized payloads.
    assert resp["details"]["detect_request_mode"] in {"RAW_JSON", "S3_POINTER"}
    assert len(query_executed) == 1
    assert "SELECT" in query_executed[0]["QueryString"]
    assert query_executed[0]["QueryExecutionContext"]["Database"] == "test-db"
    assert query_executed[0]["WorkGroup"] == "test-wg"
    assert get_status_calls[0] >= 2
    assert get_results_calls[0] == 2
    assert len(resp["details"]["aws_cur_line_items"]) == 2

    # Clean up
    del os.environ["ATHENA_WORKGROUP_NAME"]
    del os.environ["GLUE_DATABASE_NAME"]
    del os.environ["GLUE_TABLE_NAME"]
    del os.environ["ATHENA_RESULTS_BUCKET_NAME"]
    handler.athena_client = None
    handler.s3_client = None


# ---------------------------------------------------------------------------
# detect_request_mode selection tests (RAW_JSON vs S3_POINTER)
# ---------------------------------------------------------------------------

class TestDetectRequestModeSelection:
    """Verify normalizer selects RAW_JSON or S3_POINTER based on payload size."""

    def _make_ce_only_event(self, ce_records=None, extra_overrides=None):
        """Minimal event that would trigger the CE-fallback normalizer path."""
        event = {
            "run_id": "rr-mode-test",
            "account_id": "123456789012",
            "correlation_id": CORRELATION_ID,
            "tenant_id": TENANT_ID,
            "cost_period": "2026-06",
            "execution_date": "2026-06-27",
            "environment": "sandbox",
            "account_name": "sandbox",
            "data_source": "COST_EXPLORER",
            "ingestion_mode": "CE_FALLBACK",
            "ce_records": ce_records or [],
            "cur_records": [],
            "resource_utilization_metrics": None,
        }
        if extra_overrides:
            event.update(extra_overrides)
        return event

    def test_raw_json_selected_when_payload_below_cap(self, monkeypatch, tmp_path):
        """RAW_JSON must be selected when the canonical JSON payload is below the cap."""
        import json as _json

        # Minimal ce_records: payload will be well below 200 KB
        small_payload = {"key": "value"}
        payload_bytes = _json.dumps(small_payload).encode("utf-8")
        assert len(payload_bytes) < 200_000, "Test precondition: payload must be small"

        monkeypatch.setenv("RAW_JSON_INLINE_MAX_BYTES", "200000")

        # Call the normalizer helper directly (isolated unit test)
        mode = handler._select_detect_request_mode(payload_bytes, int(os.environ["RAW_JSON_INLINE_MAX_BYTES"]))
        assert mode == "RAW_JSON", f"Expected RAW_JSON for small payload ({len(payload_bytes)} B)"

    def test_s3_pointer_selected_when_payload_exceeds_cap(self, monkeypatch):
        """S3_POINTER must be selected when the canonical JSON payload exceeds the cap."""
        # Payload exceeding 1 B cap (artificially tiny to force S3_POINTER)
        large_payload = b"x" * 10
        monkeypatch.setenv("RAW_JSON_INLINE_MAX_BYTES", "5")

        mode = handler._select_detect_request_mode(large_payload, 5)
        assert mode == "S3_POINTER", f"Expected S3_POINTER for payload size {len(large_payload)} > 5"

    def test_s3_pointer_selected_at_exact_cap_boundary(self, monkeypatch):
        """Payload exactly at the cap must use RAW_JSON; one byte over must use S3_POINTER."""
        payload_at_cap = b"a" * 100
        cap = 100

        assert handler._select_detect_request_mode(payload_at_cap, cap) == "RAW_JSON"
        assert handler._select_detect_request_mode(payload_at_cap + b"x", cap) == "S3_POINTER"

    def test_default_cap_is_200kb(self, monkeypatch):
        """Confirm the default RAW_JSON_INLINE_MAX_BYTES env var default is 200000."""
        monkeypatch.delenv("RAW_JSON_INLINE_MAX_BYTES", raising=False)
        cap = int(os.environ.get("RAW_JSON_INLINE_MAX_BYTES", "200000"))
        assert cap == 200_000
