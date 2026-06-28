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


def _make_manifest(assembly_id="cur2-asm-2026-06", report_keys=None, prefix="finops-cur-export"):
    if report_keys is None:
        report_keys = [f"{prefix}/finops-export/data/BILLING_PERIOD=2026-06/part-00001.snappy.parquet"]
    return json.dumps({
        "assemblyId": assembly_id,
        "reportKeys": report_keys,
        "billingPeriod": "2026-06",
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


# ── Manifest reportKey prefix validation ─────────────────────────────────────

def test_validate_manifest_report_keys_valid():
    """Report keys under allowed prefix are accepted."""
    handler._validate_manifest_report_keys(
        ["my-prefix/my-export/data/part.parquet"],
        allowed_prefix="my-prefix",
        cur_bucket="tf2-finops-cur-export-bucket",
    )


def test_validate_manifest_report_keys_outside_prefix():
    """Report keys outside the allowed prefix raise UnsafeActionError."""
    with pytest.raises(finops_common.UnsafeActionError, match="outside the allowed prefix"):
        handler._validate_manifest_report_keys(
            ["some-other-prefix/data/part.parquet"],
            allowed_prefix="my-prefix",
            cur_bucket="tf2-finops-cur-export-bucket",
        )


def test_validate_manifest_report_keys_cross_account_s3_uri():
    """Report keys with a different bucket in s3:// URI raise UnsafeActionError."""
    with pytest.raises(finops_common.UnsafeActionError, match="Cross-account"):
        handler._validate_manifest_report_keys(
            ["s3://other-bucket/my-prefix/data/part.parquet"],
            allowed_prefix="my-prefix",
            cur_bucket="tf2-finops-cur-export-bucket",
        )


def test_validate_manifest_report_keys_no_prefix_check():
    """When allowed_prefix is empty, no prefix check is applied."""
    # Should not raise
    handler._validate_manifest_report_keys(
        ["anything/data/part.parquet"],
        allowed_prefix="",
        cur_bucket="tf2-finops-cur-export-bucket",
    )


# ── CUR 2.0 READY path (happy path) ──────────────────────────────────────────

def test_cur2_ready_path_returns_ready_with_manifest_metadata():
    """
    With CUR_EXPORTS_JSON configured and manifest key present,
    cost_puller returns READY with cur_manifest_uri, assembly_id, billing_period,
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
    assert details["assembly_id"] == "cur2-asm-2026-06"
    assert details["billing_period"] == "2026-06"
    assert details["export_name"] == "finops-export"
    assert details["source_account_id"] == account_id
    assert details["telemetry_delay_event"] is False
    assert details["delayed_cur"] is False

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
    Manifest with report keys outside the configured allowed_raw_prefix is rejected.
    """
    account_id = "112233445566"
    cur_bucket = "tf2-finops-cur-export-bucket"

    # Manifest with reportKey outside the expected prefix
    bad_manifest = json.dumps({
        "assemblyId": "cur2-asm-2026-06",
        "reportKeys": ["malicious-prefix/data/part.parquet"],
    }).encode("utf-8")

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
    # Note: bucket name does NOT contain account_id
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

    # Must NOT raise UnsafeActionError about cross-tenant bucket
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
