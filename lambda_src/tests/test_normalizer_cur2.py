"""
test_normalizer_cur2.py — Unit tests for the normalizer CUR 2.0 manifest-URI requirements
and reportKey prefix validation.
These tests are additive; existing test_normalizer.py tests remain unchanged.
"""
import pytest
import os
import json
import gzip
import hashlib
from workers.normalizer import handler
import finops_common


ATHENA_ENV = {
    "ATHENA_WORKGROUP_NAME": "test-wg",
    "GLUE_DATABASE_NAME": "test_db",
    "GLUE_TABLE_NAME": "test_tbl",
    "ATHENA_RESULTS_BUCKET_NAME": "test-athena-results",
}


class FakeAthena:
    def __init__(self, rows=None):
        self.rows = rows or [
            {"Data": [
                {"VarCharValue": "line_item_unblended_cost"},
                {"VarCharValue": "line_item_product_code"},
                {"VarCharValue": "line_item_usage_account_id"},
            ]},
            {"Data": [
                {"VarCharValue": "75.50"},
                {"VarCharValue": "AmazonEC2"},
                {"VarCharValue": "112233445566"},
            ]},
        ]

    def start_query_execution(self, **kwargs):
        return {"QueryExecutionId": "q-fixture"}

    def get_query_execution(self, QueryExecutionId):
        return {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}}

    def get_query_results(self, **kwargs):
        return {"ResultSet": {"Rows": self.rows}}


def _set_athena_env():
    os.environ.update(ATHENA_ENV)


def _clear_athena_env():
    for k in ATHENA_ENV:
        os.environ.pop(k, None)


def _make_manifest(bucket="tf2-finops-cur-export-bucket", prefix="finops-cur-export"):
    return json.dumps({
        "assemblyId": "asm-2026-06",
        "reportKeys": [f"{prefix}/finops-export/data/BILLING_PERIOD=2026-06/part.parquet"],
    }).encode("utf-8")


# ── CUR-ready path requires cur_manifest_uri ─────────────────────────────────

def test_normalizer_cur_ready_without_manifest_uri_fails():
    """
    CUR-ready path (telemetry_delay_event absent/false) must fail fast
    when ingestion.details.cur_manifest_uri is not provided.
    """
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    handler.s3_client = finops_common.FakeS3()
    handler.athena_client = FakeAthena()

    event_data = {
        "run_id": "run-no-manifest",
        "correlation_id": "corr-no-manifest",
        "account_id": "112233445566",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        # No ingestion.details.cur_manifest_uri
    }

    with pytest.raises(finops_common.InvalidInputError, match="cur_manifest_uri"):
        handler.handle_request(event_data, None)

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_cur_ready_with_manifest_uri_runs_athena():
    """
    Valid CUR-ready event with cur_manifest_uri triggers Athena query
    and writes .json.gz under ai-input/account_id=....
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"
    manifest_bytes = _make_manifest(bucket=cur_bucket)

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    put_calls = []

    def fake_put(bucket, key, body):
        put_calls.append((bucket, key, body))

    def fake_get(bucket, key):
        # Return manifest when the manifest key is requested
        if "Manifest.json" in key:
            return manifest_bytes
        return b""

    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put,
        get_object_func=fake_get,
    )
    handler.athena_client = FakeAthena()
    handler.ddb_client = None

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    event_data = {
        "run_id": "run-cur2-norm",
        "correlation_id": "corr-cur2-norm",
        "account_id": account_id,
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ingestion": {
            "details": {
                "cur_manifest_uri": manifest_uri,
                "data_source_type": "S3_POINTER",
            }
        },
    }

    resp = handler.handle_request(event_data, None)

    assert resp["status"] == "NORMALIZED"
    details = resp["details"]

    # Verify ai-input/ key was written
    ai_input_writes = [k for _, k, _ in put_calls if k.startswith("ai-input/")]
    assert len(ai_input_writes) == 1
    ai_key = ai_input_writes[0]
    assert f"account_id={account_id}" in ai_key
    assert ai_key.endswith("_input.json.gz")

    # Verify s3_bucket_uri and checksum present
    assert "s3://test-lakehouse/ai-input/" in details["s3_bucket_uri"]
    assert details["s3_object_checksum"]

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_cross_account_report_key_rejected():
    """
    Manifest with a reportKey pointing to a different S3 bucket is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    bad_manifest = json.dumps({
        "assemblyId": "asm-2026-06",
        "reportKeys": ["s3://attacker-bucket/data/part.parquet"],
    }).encode("utf-8")

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    os.environ["CUR_RAW_EXPORT_PREFIX"] = "finops-cur-export"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
        put_object_func=lambda b, k, v: None,
    )
    handler.athena_client = FakeAthena()

    with pytest.raises(finops_common.UnsafeActionError, match="Cross-account"):
        handler.handle_request(
            {
                "run_id": "run-cross-bucket",
                "correlation_id": "corr-cross-bucket",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
                "ingestion": {"details": {"cur_manifest_uri": manifest_uri}},
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_RAW_EXPORT_PREFIX"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_report_key_outside_prefix_rejected():
    """
    Manifest with a reportKey outside CUR_RAW_EXPORT_PREFIX is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    bad_manifest = json.dumps({
        "assemblyId": "asm-2026-06",
        "reportKeys": ["wrong-prefix/data/part.parquet"],
    }).encode("utf-8")

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    os.environ["CUR_RAW_EXPORT_PREFIX"] = "finops-cur-export"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
        put_object_func=lambda b, k, v: None,
    )
    handler.athena_client = FakeAthena()

    with pytest.raises(finops_common.UnsafeActionError, match="CUR_RAW_EXPORT_PREFIX"):
        handler.handle_request(
            {
                "run_id": "run-wrong-prefix",
                "correlation_id": "corr-wrong-prefix",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
                "ingestion": {"details": {"cur_manifest_uri": manifest_uri}},
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_RAW_EXPORT_PREFIX"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_malformed_s3_uri_in_report_key_rejected():
    """
    Manifest with a malformed s3:// URI (no slash after bucket) is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    bad_manifest = json.dumps({
        "assemblyId": "asm-2026-06",
        "reportKeys": ["s3://no-path-here"],
    }).encode("utf-8")

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
        put_object_func=lambda b, k, v: None,
    )
    handler.athena_client = FakeAthena()

    with pytest.raises(finops_common.InvalidInputError, match="Malformed S3 URI"):
        handler.handle_request(
            {
                "run_id": "run-malformed-uri",
                "correlation_id": "corr-malformed-uri",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
                "ingestion": {"details": {"cur_manifest_uri": manifest_uri}},
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_ce_fallback_continues_to_work():
    """
    CE-fallback path (telemetry_delay_event=true / raw_data_uri present)
    still works end-to-end without cur_manifest_uri.
    """
    account_id = "112233445566"
    raw_records = {
        "schema_version": "3.2.0",
        "aws_cur_line_items": [],
        "aws_cost_explorer_daily": [
            {"date": "2026-06-24", "service": "AmazonEC2", "service_code": "AmazonEC2",
             "unblended_cost": 99.0, "linked_account_id": account_id, "region": "ap-southeast-1"}
        ],
        "resource_utilization_metrics": [],
        "quality": {"completeness_score": 0.8},
    }
    gzipped = gzip.compress(json.dumps(raw_records).encode("utf-8"))
    checksum = hashlib.sha256(gzipped).hexdigest()
    raw_uri = f"s3://test-lakehouse/cur/account_id={account_id}/year=2026/month=06/day=24/run-ce_raw.json.gz"

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"

    put_calls = []

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: gzipped,
        put_object_func=lambda b, k, v: put_calls.append(k),
    )

    resp = handler.handle_request(
        {
            "run_id": "run-ce-fb",
            "correlation_id": "corr-ce-fb",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
            "ingestion": {
                "details": {
                    "raw_data_uri": raw_uri,
                    "telemetry_delay_event": True,
                }
            },
        },
        None,
    )

    assert resp["status"] == "NORMALIZED"
    assert resp["details"]["delayed_cur"] is True
    # ai-input/ should be written
    ai_writes = [k for k in put_calls if k.startswith("ai-input/")]
    assert len(ai_writes) == 1

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None
