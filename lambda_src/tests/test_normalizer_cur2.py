"""
test_normalizer_cur2.py — Unit tests for the normalizer CUR 2.0 manifest-URI requirements
and dataFiles validation.
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
        self.captured_queries = []

    def start_query_execution(self, **kwargs):
        self.captured_queries.append(kwargs.get("QueryString", ""))
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


def _make_manifest(bucket="tf2-finops-cur-export-bucket", prefix="finops-cur-export", data_files=None, columns=None):
    if data_files is None:
        data_files = [f"s3://{bucket}/{prefix}/finops-export/data/BILLING_PERIOD=2026-06/part.parquet"]
    if columns is None:
        columns = [
            {"name": "bill_billing_period_start_date", "type": "timestamp"},
            {"name": "line_item_usage_start_date", "type": "timestamp"},
            {"name": "line_item_usage_account_id", "type": "string"},
            {"name": "line_item_product_code", "type": "string"},
            {"name": "line_item_usage_type", "type": "string"},
            {"name": "line_item_usage_amount", "type": "double"},
            {"name": "pricing_unit", "type": "string"},
            {"name": "line_item_unblended_cost", "type": "double"},
            {"name": "resource_tags_user_environment", "type": "string"},
        ]
    return json.dumps({
        "executionId": "exec-123",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2",
        "columns": columns,
        "dataFiles": data_files,
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

    ai_input_writes = [k for _, k, _ in put_calls if k.startswith("ai-input/")]
    assert len(ai_input_writes) == 1
    ai_key = ai_input_writes[0]
    assert f"account_id={account_id}" in ai_key
    assert ai_key.endswith("_input.json.gz")

    assert "s3://test-lakehouse/ai-input/" in details["s3_bucket_uri"]
    assert details["s3_object_checksum"]

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_cross_account_data_file_rejected():
    """
    Manifest with a dataFile pointing to a different S3 bucket is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    bad_manifest = _make_manifest(bucket="attacker-bucket")

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    os.environ["CUR_RAW_EXPORT_PREFIX"] = "finops-cur-export"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
        put_object_func=lambda b, k, v: None,
    )
    handler.athena_client = FakeAthena()

    with pytest.raises(finops_common.UnsafeActionError, match="Cross-bucket"):
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


def test_normalizer_data_file_outside_prefix_rejected():
    """
    Manifest with a dataFile outside CUR_RAW_EXPORT_PREFIX is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    bad_manifest = _make_manifest(data_files=["s3://tf2-finops-cur-export-bucket/wrong-prefix/data/BILLING_PERIOD=2026-06/part.parquet"])

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    os.environ["CUR_RAW_EXPORT_PREFIX"] = "finops-cur-export"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
        put_object_func=lambda b, k, v: None,
    )
    handler.athena_client = FakeAthena()

    with pytest.raises(finops_common.UnsafeActionError, match="outside the allowed prefix"):
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


def test_normalizer_malformed_s3_uri_in_data_file_rejected():
    """
    Manifest with a malformed s3:// URI in dataFiles is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    bad_manifest = _make_manifest(data_files=["s3://no-path-here"])

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
        put_object_func=lambda b, k, v: None,
    )
    handler.athena_client = FakeAthena()

    with pytest.raises(finops_common.InvalidInputError, match="Malformed data file URI"):
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
    ai_writes = [k for k in put_calls if k.startswith("ai-input/")]
    assert len(ai_writes) == 1

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None


def test_normalizer_legacy_manifest_rejected():
    """Legacy assemblyId/reportKeys manifests are rejected before running Athena."""
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    legacy_manifest = json.dumps({
        "assemblyId": "asm-12345",
        "reportKeys": ["part.parquet"]
    }).encode("utf-8")

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: legacy_manifest,
    )
    handler.athena_client = FakeAthena()

    with pytest.raises(finops_common.InvalidInputError, match="Legacy CUR manifest format.*is not supported"):
        handler.handle_request(
            {
                "run_id": "run-legacy",
                "correlation_id": "corr-legacy",
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


def test_normalizer_dynamic_query_construction():
    """Athena query uses only columns available in the manifest, fallback to NULL for missing optional ones."""
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    # Only provide the mandatory columns in manifest
    manifest_bytes = _make_manifest(
        bucket=cur_bucket,
        columns=[
            {"name": "line_item_usage_start_date", "type": "timestamp"},
            {"name": "line_item_usage_account_id", "type": "string"},
            {"name": "line_item_product_code", "type": "string"},
            {"name": "line_item_usage_type", "type": "string"},
            {"name": "line_item_usage_amount", "type": "double"},
            {"name": "pricing_unit", "type": "string"},
            {"name": "line_item_unblended_cost", "type": "double"},
            {"name": "resource_tags_user_environment", "type": "string"},
        ]
    )

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: manifest_bytes,
        put_object_func=lambda b, k, v: None,
    )
    fake_ath = FakeAthena()
    handler.athena_client = fake_ath

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    resp = handler.handle_request(
        {
            "run_id": "run-dynamic-sql",
            "correlation_id": "corr-dynamic-sql",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
            "ingestion": {"details": {"cur_manifest_uri": manifest_uri}},
        },
        None,
    )

    assert resp["status"] == "NORMALIZED"
    assert len(fake_ath.captured_queries) == 1
    query_str = fake_ath.captured_queries[0]

    # Verify that optional columns not in the manifest are queried as NULL AS ...
    assert "NULL AS bill_billing_period_start_date" in query_str
    assert "NULL AS bill_payer_account_id" in query_str
    assert "NULL AS resource_tags_user_owner" in query_str
    assert "NULL AS resource_tags_user_team" in query_str

    # Verify that mandatory columns are queried directly
    assert "line_item_usage_start_date" in query_str
    assert "line_item_unblended_cost" in query_str

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_member_account_prefix_accepted():
    """
    Normalizer accepts manifest containing dataFiles with member-account prefix
    matching ingestion.details.allowed_raw_prefix and manifest S3 URI bucket,
    while rejecting other prefixes.
    """
    account_id = "336805808730"
    cur_bucket = "tf2-finops-cur-export-bucket-2"

    # Valid manifest with custom bucket and member-account prefix
    valid_manifest = _make_manifest(
        bucket=cur_bucket,
        prefix=f"{account_id}/accountCUR",
        data_files=[f"s3://{cur_bucket}/{account_id}/accountCUR/data/BILLING_PERIOD=2026-06/part.parquet"]
    )

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    # Even if CUR_RAW_EXPORT_PREFIX env is set differently, the ingestion details should override it
    os.environ["CUR_RAW_EXPORT_PREFIX"] = "some-other-prefix"
    _set_athena_env()

    manifest_uri = f"s3://{cur_bucket}/{account_id}/accountCUR/metadata/BILLING_PERIOD=2026-06/accountCUR-Manifest.json"

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: valid_manifest,
        put_object_func=lambda b, k, v: None,
    )
    handler.athena_client = FakeAthena()

    # Proves it accepts matching prefix
    resp = handler.handle_request(
        {
            "run_id": "run-member-prefix-ok",
            "correlation_id": "corr-member-prefix-ok",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
            "ingestion": {
                "details": {
                    "cur_manifest_uri": manifest_uri,
                    "allowed_raw_prefix": f"{account_id}/accountCUR"
                }
            },
        },
        None,
    )
    assert resp["status"] == "NORMALIZED"

    # Proves it rejects mismatching prefix (attacker)
    bad_manifest = _make_manifest(
        bucket=cur_bucket,
        prefix=f"999999999999/accountCUR",
        data_files=[f"s3://{cur_bucket}/999999999999/accountCUR/data/BILLING_PERIOD=2026-06/part.parquet"]
    )
    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
    )

    with pytest.raises(finops_common.UnsafeActionError, match="outside the allowed prefix"):
        handler.handle_request(
            {
                "run_id": "run-member-prefix-bad",
                "correlation_id": "corr-member-prefix-bad",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
                "ingestion": {
                    "details": {
                        "cur_manifest_uri": manifest_uri,
                        "allowed_raw_prefix": f"{account_id}/accountCUR"
                    }
                },
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_RAW_EXPORT_PREFIX"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_normalizer_rejects_missing_column_manifest():
    """Normalizer rejects a manifest missing resource_tags_user_environment before starting Athena."""
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"
    bad_columns = [
        {"name": "bill_billing_period_start_date", "type": "timestamp"},
        {"name": "line_item_usage_start_date", "type": "timestamp"},
        {"name": "line_item_usage_account_id", "type": "string"},
        {"name": "line_item_product_code", "type": "string"},
        {"name": "line_item_usage_type", "type": "string"},
        {"name": "line_item_usage_amount", "type": "double"},
        {"name": "pricing_unit", "type": "string"},
        {"name": "line_item_unblended_cost", "type": "double"},
        # missing resource_tags_user_environment
    ]
    bad_manifest = _make_manifest(bucket=cur_bucket, columns=bad_columns)

    os.environ["LAKEHOUSE_BUCKET_NAME"] = "test-lakehouse"
    _set_athena_env()

    handler.s3_client = finops_common.FakeS3(
        get_object_func=lambda b, k: bad_manifest,
    )
    handler.athena_client = FakeAthena()

    manifest_uri = f"s3://{cur_bucket}/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json"

    event_data = {
        "run_id": "run-cur2-norm-bad",
        "correlation_id": "corr-cur2-norm-bad",
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

    with pytest.raises(finops_common.ContractMismatchError, match="Required columns missing from CUR manifest.*resource_tags_user_environment"):
        handler.handle_request(event_data, None)

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    _clear_athena_env()
    handler.s3_client = None
    handler.athena_client = None


def test_build_dynamic_select_fields_valid_and_optional_columns():
    """A valid manifest containing the required columns builds the expected dynamic SELECT,
    while missing optional columns become NULL AS ...
    """
    # Valid but missing optional columns: resource_tags_user_owner, resource_tags_user_team
    manifest_cols = [
        {"name": "line_item_usage_start_date"},
        {"name": "line_item_usage_account_id"},
        {"name": "line_item_product_code"},
        {"name": "line_item_usage_type"},
        {"name": "line_item_usage_amount"},
        {"name": "pricing_unit"},
        {"name": "line_item_unblended_cost"},
        {"name": "resource_tags_user_environment"},
        {"name": "bill_billing_period_start_date"},
        {"name": "line_item_resource_id"}
    ]
    select_sql = handler.build_dynamic_select_fields(manifest_cols)

    # Required/present columns
    assert "line_item_usage_start_date" in select_sql
    assert "line_item_usage_account_id" in select_sql
    assert "line_item_product_code" in select_sql
    assert "line_item_resource_id" in select_sql

    # Missing optional columns mapped to NULL AS ...
    assert "NULL AS resource_tags_user_owner" in select_sql
    assert "NULL AS resource_tags_user_team" in select_sql
    assert "NULL AS resource_tags_user_cost_center" in select_sql


