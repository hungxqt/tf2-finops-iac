"""
test_cost_puller_cur2.py — Unit tests for CUR 2.0 / AWS Data Exports deterministic manifest path.
These tests are additive; they do not replace the existing test_cost_puller.py tests.
"""
import pytest
import os
import json
import gzip
from datetime import datetime
from workers.cost_puller import handler
import finops_common


def _fake_sts_for_account(account_id="112233445566"):
    return finops_common.FakeSTS(
        get_caller_identity_func=lambda: {"AccountId": account_id}
    )


def _make_manifest(execution_id="exec-12345", data_files=None, prefix="finops-cur-export"):
    if data_files is None:
        data_files = [f"s3://tf2-finops-cur-export-bucket/{prefix}/finops-export/data/BILLING_PERIOD=2026-06/part-00001.snappy.parquet"]
    return json.dumps({
        "executionId": execution_id,
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2",
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
        "dataFiles": data_files,
    }).encode("utf-8")


def _exports_json(
    account_id="112233445566",
    prefix="finops-cur-export",
    export_name="finops-export",
    allowed_raw_prefix="finops-cur-export",
):
    return json.dumps({
        account_id: {
            "source_account_id": account_id,
            "prefix": prefix,
            "export_name": export_name,
            "allowed_raw_prefix": allowed_raw_prefix,
        }
    })


# ── Deterministic manifest key construction ────────────────────────────────────

def test_build_manifest_key_standard():
    """Build manifest key matches AWS Data Exports layout."""
    key = handler._build_manifest_key("my-prefix", "my-export", "2026-06")
    assert key == "my-prefix/my-export/metadata/BILLING_PERIOD=2026-06/my-export-Manifest.json"


def test_build_manifest_key_no_prefix():
    """When prefix is empty, key starts with export name directly."""
    key = handler._build_manifest_key("", "my-export", "2026-06")
    assert key == "my-export/metadata/BILLING_PERIOD=2026-06/my-export-Manifest.json"


def test_build_manifest_key_strips_slashes():
    """Leading/trailing slashes in prefix and export_name are stripped."""
    key = handler._build_manifest_key("/my-prefix/", "/my-export/", "2026-06")
    assert key == "my-prefix/my-export/metadata/BILLING_PERIOD=2026-06/my-export-Manifest.json"


# ── Billing period resolution ─────────────────────────────────────────────────

def test_resolve_billing_period_from_cost_period():
    class FakeEvent:
        billing_period = None
        cost_period = "2026-06"

    result = handler._resolve_billing_period(FakeEvent(), datetime(2026, 7, 1))
    assert result == "2026-06"


def test_resolve_billing_period_from_billing_period_field():
    class FakeEvent:
        billing_period = "2026-05"
        cost_period = "2026-06"

    result = handler._resolve_billing_period(FakeEvent(), datetime(2026, 7, 1))
    assert result == "2026-05"


def test_resolve_billing_period_falls_back_to_exec_date():
    class FakeEvent:
        billing_period = None
        cost_period = None

    result = handler._resolve_billing_period(FakeEvent(), datetime(2026, 6, 24))
    assert result == "2026-06"


# ── Manifest dataFiles validation ─────────────────────────────────────

def test_validate_data_files_valid():
    """Data files under allowed bucket and prefix, matching billing period, are accepted."""
    finops_common.validate_data_files(
        ["s3://tf2-finops-cur-export-bucket/my-prefix/my-export/data/BILLING_PERIOD=2026-06/part.parquet"],
        allowed_bucket="tf2-finops-cur-export-bucket",
        allowed_prefix="my-prefix",
        billing_period="2026-06",
    )


def test_validate_data_files_outside_prefix():
    """Data files outside the allowed prefix raise UnsafeActionError."""
    with pytest.raises(finops_common.UnsafeActionError, match="outside the allowed prefix"):
        finops_common.validate_data_files(
            ["s3://tf2-finops-cur-export-bucket/some-other-prefix/data/BILLING_PERIOD=2026-06/part.parquet"],
            allowed_bucket="tf2-finops-cur-export-bucket",
            allowed_prefix="my-prefix",
            billing_period="2026-06",
        )


def test_validate_data_files_cross_account_s3_uri():
    """Data files with a different bucket raise UnsafeActionError."""
    with pytest.raises(finops_common.UnsafeActionError, match="Cross-bucket"):
        finops_common.validate_data_files(
            ["s3://other-bucket/my-prefix/data/BILLING_PERIOD=2026-06/part.parquet"],
            allowed_bucket="tf2-finops-cur-export-bucket",
            allowed_prefix="my-prefix",
            billing_period="2026-06",
        )


def test_validate_data_files_wrong_billing_period():
    """Data files with non-matching billing period raise UnsafeActionError."""
    with pytest.raises(finops_common.UnsafeActionError, match="does not match the billing period"):
        finops_common.validate_data_files(
            ["s3://tf2-finops-cur-export-bucket/my-prefix/data/BILLING_PERIOD=2026-05/part.parquet"],
            allowed_bucket="tf2-finops-cur-export-bucket",
            allowed_prefix="my-prefix",
            billing_period="2026-06",
        )


# ── CUR 2.0 READY path (happy path) ──────────────────────────────────────────

def test_cur2_ready_path_returns_ready_with_manifest_metadata():
    """
    With CUR_EXPORTS_JSON configured and manifest key present,
    cost_puller returns READY with cur_manifest_uri, manifest_format, execution_id,
    export_arn, columns, data_files, data_file_count, columns_count, billing_period,
    export_name, source_account_id, and telemetry_delay_event=False.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"
    manifest_bytes = _make_manifest()

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id)

    put_calls = []

    def fake_put(bucket, key, body):
        put_calls.append((bucket, key))

    def fake_head(bucket, key):
        return {"ETag": '"abc123"', "ContentLength": len(manifest_bytes)}

    def fake_get(bucket, key):
        return manifest_bytes

    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put,
        head_object_func=fake_head,
        get_object_func=fake_get,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    resp = handler.handle_request(
        {
            "run_id": "run-cur2",
            "correlation_id": "corr-cur2",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
        },
        None,
    )

    assert resp["status"] == "READY"
    details = resp["details"]
    assert "finops-cur-export-bucket" in details["cur_manifest_uri"]
    assert "BILLING_PERIOD=2026-06" in details["cur_manifest_uri"]
    assert details["manifest_format"] == "DATA_EXPORTS"
    assert details["execution_id"] == "exec-12345"
    assert details["export_arn"] == "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2"
    assert len(details["columns"]) == 9
    assert len(details["data_files"]) == 1
    assert details["data_file_count"] == 1
    assert details["columns_count"] == 9
    assert "assembly_id" not in details
    assert "report_keys" not in details

    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


def test_cur2_manifest_absent_triggers_cur_delay():
    """
    When head_object raises 404, cost_puller falls back to CUR_DELAY/CE path.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id)

    def fake_head_404(bucket, key):
        err = Exception("404 NoSuchKey")
        err.response = {"Error": {"Code": "404", "Message": "Not Found"}}  # type: ignore[attr-defined]
        raise err

    def fake_get_ce(**kwargs):
        return {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-06-24", "End": "2026-06-25"},
                    "Estimated": False,
                    "Groups": [
                        {
                            "Keys": [account_id, "Amazon Elastic Compute Cloud - Compute", "ap-southeast-1"],
                            "Metrics": {"UnblendedCost": {"Amount": "50.00"}},
                        }
                    ],
                }
            ]
        }

    handler.s3_client = finops_common.FakeS3(
        head_object_func=fake_head_404,
        put_object_func=lambda b, k, v: None,
    )
    handler.ce_client = finops_common.FakeCostExplorer(get_cost_and_usage_func=fake_get_ce)
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    resp = handler.handle_request(
        {
            "run_id": "run-cur2-absent",
            "correlation_id": "corr-cur2-absent",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
        },
        None,
    )

    assert resp["status"] == "READY"
    assert resp["details"]["telemetry_delay_event"] is True
    assert resp["details"]["delayed_cur"] is True

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


def test_cur2_report_keys_outside_prefix_rejected():
    """
    Manifest with data files outside the configured allowed_raw_prefix is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    # Manifest with dataFile outside the expected prefix
    bad_manifest = _make_manifest(data_files=["s3://tf2-finops-cur-export-bucket/malicious-prefix/data/BILLING_PERIOD=2026-06/part.parquet"])

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id, allowed_raw_prefix="finops-cur-export")

    def fake_head(bucket, key):
        return {"ETag": '"abc"', "ContentLength": 100}

    handler.s3_client = finops_common.FakeS3(
        head_object_func=fake_head,
        get_object_func=lambda b, k: bad_manifest,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    with pytest.raises(finops_common.UnsafeActionError, match="outside the allowed prefix"):
        handler.handle_request(
            {
                "run_id": "run-bad-prefix",
                "correlation_id": "corr-bad-prefix",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


def test_cur2_bucket_without_account_id_in_name_accepted_when_using_exports_json():
    """
    tf2-finops-cur-export-bucket is accepted even though it does not embed
    the 12-digit account ID, because tenant isolation is enforced by CUR_EXPORTS_JSON
    source_account_id rather than bucket-name embedding.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"
    manifest_bytes = _make_manifest()

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id)

    def fake_head(b, k):
        return {"ETag": '"ok"', "ContentLength": 10}

    handler.s3_client = finops_common.FakeS3(
        head_object_func=fake_head,
        get_object_func=lambda b, k: manifest_bytes,
        put_object_func=lambda b, k, v: None,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    resp = handler.handle_request(
        {
            "run_id": "run-no-acct-in-bucket",
            "correlation_id": "corr-no-acct",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
        },
        None,
    )
    assert resp["status"] == "READY"

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


# ── Edge Case & Legacy Rejection Tests ──────────────────────────────────────────

def test_missing_manifest_fields_fails():
    """Manifest missing executionId, exportArn, columns, or dataFiles fails."""
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id)

    # Missing columns
    bad_manifest = json.dumps({
        "executionId": "exec-12345",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2",
        "dataFiles": ["s3://tf2-finops-cur-export-bucket/finops-cur-export/finops-export/data/BILLING_PERIOD=2026-06/part.parquet"]
    }).encode("utf-8")

    handler.s3_client = finops_common.FakeS3(
        head_object_func=lambda b, k: {"ETag": '"abc"'},
        get_object_func=lambda b, k: bad_manifest,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    with pytest.raises(finops_common.InvalidInputError, match="missing required field"):
        handler.handle_request(
            {
                "run_id": "run-missing-fields",
                "correlation_id": "corr-missing-fields",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


def test_empty_data_files_fails():
    """Manifest with empty dataFiles fails."""
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id)

    bad_manifest = json.dumps({
        "executionId": "exec-12345",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2",
        "columns": [{"name": "col1"}],
        "dataFiles": []
    }).encode("utf-8")

    handler.s3_client = finops_common.FakeS3(
        head_object_func=lambda b, k: {"ETag": '"abc"'},
        get_object_func=lambda b, k: bad_manifest,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    with pytest.raises(finops_common.InvalidInputError, match="must be a non-empty list"):
        handler.handle_request(
            {
                "run_id": "run-empty-data-files",
                "correlation_id": "corr-empty-data-files",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


def test_legacy_manifest_fails():
    """Legacy assemblyId/reportKeys manifest fails."""
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id)

    legacy_manifest = json.dumps({
        "assemblyId": "cur2-asm-2026-06",
        "reportKeys": ["finops-cur-export/finops-export/data/BILLING_PERIOD=2026-06/part.parquet"],
    }).encode("utf-8")

    handler.s3_client = finops_common.FakeS3(
        head_object_func=lambda b, k: {"ETag": '"abc"'},
        get_object_func=lambda b, k: legacy_manifest,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    with pytest.raises(finops_common.InvalidInputError, match="Legacy CUR manifest format.*is not supported"):
        handler.handle_request(
            {
                "run_id": "run-legacy",
                "correlation_id": "corr-legacy",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
            },
            None,
        )

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


def test_build_manifest_key_member_account():
    """Build manifest key matches AWS Data Exports layout for member account prefix."""
    key = handler._build_manifest_key("336805808730", "accountCUR", "2026-06")
    assert key == "336805808730/accountCUR/metadata/BILLING_PERIOD=2026-06/accountCUR-Manifest.json"


def test_cur2_multi_account_configured_bucket():
    """
    Cost puller parses multi-account CUR_EXPORTS_JSON,
    validates dataFiles against custom bucket (tf2-finops-cur-export-bucket-2),
    verifies allowed_raw_prefix and details structure,
    and returns READY.
    """
    account_id = "336805808730"
    cur_bucket = "tf2-finops-cur-export-bucket-2"
    
    # Prefix is configured as "336805808730/accountCUR" via allowed_raw_prefix
    data_files = [
        f"s3://{cur_bucket}/{account_id}/accountCUR/data/BILLING_PERIOD=2026-06/part-00001.snappy.parquet"
    ]
    manifest_bytes = _make_manifest(data_files=data_files)

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    
    # Setup multi-account config
    os.environ["CUR_EXPORTS_JSON"] = json.dumps({
        account_id: {
            "source_account_id": account_id,
            "prefix": account_id,
            "export_name": "accountCUR",
            "allowed_raw_prefix": f"{account_id}/accountCUR"
        },
        "123456789012": {
            "source_account_id": "123456789012",
            "prefix": "123456789012",
            "export_name": "accountCUR",
            "allowed_raw_prefix": "123456789012/accountCUR"
        }
    })

    def fake_head(bucket, key):
        return {"ETag": '"abc12345"', "ContentLength": len(manifest_bytes)}

    def fake_get(bucket, key):
        return manifest_bytes

    handler.s3_client = finops_common.FakeS3(
        head_object_func=fake_head,
        get_object_func=fake_get,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    resp = handler.handle_request(
        {
            "run_id": "run-multi-acc",
            "correlation_id": "corr-multi-acc",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
        },
        None,
    )

    assert resp["status"] == "READY"
    details = resp["details"]
    assert details["cur_manifest_uri"] == f"s3://{cur_bucket}/{account_id}/accountCUR/metadata/BILLING_PERIOD=2026-06/accountCUR-Manifest.json"
    assert details["allowed_raw_prefix"] == f"{account_id}/accountCUR"
    assert details["export_name"] == "accountCUR"
    assert details["source_account_id"] == account_id

    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.sts_client = None


def test_cur2_rejection_unconfigured_account():
    """Cost puller rejects requests when the event account is not configured in CUR_EXPORTS_JSON."""
    account_id = "999999999999"
    cur_bucket = "tf2-finops-cur-export-bucket-2"

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = json.dumps({
        "123456789012": {
            "source_account_id": "123456789012",
            "prefix": "123456789012",
            "export_name": "accountCUR",
            "allowed_raw_prefix": "123456789012/accountCUR"
        }
    })

    handler.sts_client = _fake_sts_for_account(account_id)

    with pytest.raises(finops_common.ConfigMissingError, match="is not configured in CUR_EXPORTS_JSON"):
        handler.handle_request(
            {
                "run_id": "run-unconfig",
                "correlation_id": "corr-unconfig",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
            },
            None,
        )

    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.sts_client = None


def test_cost_puller_rejects_missing_required_column():
    """Cost puller rejects a Data Exports manifest missing resource_tags_user_environment."""
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    # Manifest missing "resource_tags_user_environment"
    bad_manifest = json.dumps({
        "executionId": "exec-12345",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:112233445566:export/cur2",
        "columns": [
            {"name": "bill_billing_period_start_date", "type": "timestamp"},
            {"name": "line_item_usage_start_date", "type": "timestamp"},
            {"name": "line_item_usage_account_id", "type": "string"},
            {"name": "line_item_product_code", "type": "string"},
            {"name": "line_item_usage_type", "type": "string"},
            {"name": "line_item_usage_amount", "type": "double"},
            {"name": "pricing_unit", "type": "string"},
            {"name": "line_item_unblended_cost", "type": "double"},
            # missing resource_tags_user_environment
        ],
        "dataFiles": [f"s3://{cur_bucket}/finops-cur-export/finops-export/data/BILLING_PERIOD=2026-06/part-00001.snappy.parquet"],
    }).encode("utf-8")

    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = cur_bucket
    os.environ["CUR_EXPORTS_JSON"] = _exports_json(account_id=account_id)

    def fake_head(bucket, key):
        return {"ETag": '"abc123"', "ContentLength": len(bad_manifest)}

    def fake_get(bucket, key):
        return bad_manifest

    handler.s3_client = finops_common.FakeS3(
        head_object_func=fake_head,
        get_object_func=fake_get,
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account(account_id)

    with pytest.raises(finops_common.ContractMismatchError, match="Required columns missing from CUR manifest.*resource_tags_user_environment"):
        handler.handle_request(
            {
                "run_id": "run-bad-columns",
                "correlation_id": "corr-bad-columns",
                "account_id": account_id,
                "cost_period": "2026-06",
                "execution_date": "2026-06-24",
            },
            None,
        )

    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.ce_client = None
    handler.cw_client = None
    handler.sts_client = None


