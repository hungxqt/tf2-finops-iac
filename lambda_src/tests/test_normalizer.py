import pytest
import os
import json
import gzip
from workers.normalizer import handler
import finops_common


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

    # Assert S3 PUT was called with filtered/curated records
    assert len(put_called) == 1
    assert put_called[0]["bucket"] == "test-lakehouse"
    assert put_called[0]["key"] == "cost/curated/account_id=112233445566/year=2026/month=06/run-400_curated.parquet"

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

    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object
    )
    handler.athena_client = FakeAthena()

    # 1. Test standard S3 pointer mode selection
    event_data = {
        "run_id": "run-s3-pointer-1",
        "correlation_id": "corr-s3-pointer-1",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "is_ad_hoc": True,
        "ingestion": {
            "status": "READY",
            "run_id": "run-s3-pointer-1",
            "correlation_id": "corr-s3-pointer-1",
            "worker": "cost_puller",
            "details": {
                "telemetry_delay_event": False,
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
    assert details["detect_request_mode"] == "S3_POINTER"
    assert details["s3_bucket_uri"].startswith("s3://test-lakehouse/ai-input/account_id=123456789012/year=2026/month=06/day=24/")
    assert details["s3_bucket_uri"].endswith("_input.json.gz")
    assert details["s3_object_checksum"] != ""
    assert details["business_context"][0]["linked_account_id"] == "123456789012"
    assert details["business_context"][0]["traffic_volume"] == 120000
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
    assert len(envelope["aws_cur_line_items"]) == 1
    assert envelope["idempotency_key"] == "tenant-default:2026-06-24:adhoc"

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
        "correlation_id": "corr-ce-1",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "status": "READY",
            "run_id": "run-ce-1",
            "correlation_id": "corr-ce-1",
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
    assert details_ce["detect_request_mode"] == "S3_POINTER"
    assert details_ce["telemetry_delay_event"] is True
    assert details_ce["s3_bucket_uri"] == "s3://test-lakehouse/cur/account_id=123456789012/year=2026/month=06/day=24/run-ce-1_raw.json.gz"
    assert len(details_ce["aws_cost_explorer_daily"]) == 1
    assert details_ce["current_ce_cost_gap_usd"] == 150.0

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
        handler.handle_request(event_data, None)

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None


def test_normalizer_athena_empty_result_fails():
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()
    handler.s3_client = finops_common.FakeS3(put_object_func=lambda bucket, key, body: None)
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
            "details": {"telemetry_delay_event": False},
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

    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object
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
            "details": {}
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NORMALIZED"
    assert resp["details"]["detect_request_mode"] == "S3_POINTER"
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
