import pytest
import os
import json
import gzip
import hashlib
from datetime import datetime
from workers.cost_puller import handler
import finops_common


def _fake_sts_for_account(account_id="112233"):
    return finops_common.FakeSTS(
        get_caller_identity_func=lambda: {"Account": account_id}
    )


def _fake_manifest_bytes():
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
        "dataFiles": ["s3://tf2-finops-cur-export-bucket/cur/manifest/data/BILLING_PERIOD=2026-06/part.parquet"]
    }).encode("utf-8")


def test_cost_puller_cur_ready_path():
    # 1. CUR-ready path writes gzipped S3 telemetry and returns READY.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    
    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })
        
    def fake_head_object(bucket, key):
        return {"ETag": '"abc123"'}

    def fake_get_object(bucket, key):
        return _fake_manifest_bytes()
        
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object,
        get_object_func=fake_get_object,
        head_object_func=fake_head_object
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account()
    
    event_data = {
        "run_id": "run-ready",
        "correlation_id": "corr-ready",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    assert "raw_data_uri" not in resp or not resp.get("raw_data_uri")
    assert resp["details"]["data_source_type"] == "S3_POINTER"
    assert resp["details"]["delayed_cur"] is False
    assert resp["details"]["cur_manifest_uri"] == "s3://tf2-finops-cur-export-bucket/cur/manifest/metadata/BILLING_PERIOD=2026-06/manifest-Manifest.json"
    
    assert len(put_called) == 1 # features only
    
    # Verify features file content
    feat_bytes = put_called[0]["body"]
    decompressed = gzip.decompress(feat_bytes)
    envelope = json.loads(decompressed.decode("utf-8"))
    
    assert "resource_utilization_metrics" in envelope
    assert "business_context" in envelope
    assert envelope["business_context"][0]["linked_account_id"] == "112233"
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.sts_client = None

def test_cost_puller_cur_delayed_ce_fallback():
    # 2. CUR delayed over 36 hours with CE fallback returns READY plus delay and mismatch metadata.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({"bucket": bucket, "key": key, "body": body})
        
    def fake_list_objects(bucket, prefix):
        # Return manifest modified 48 hours ago (> 36 hours threshold)
        from datetime import timedelta
        return {
            "Contents": [
                {
                    "Key": "cur/manifest.json",
                    "LastModified": datetime.utcnow() - timedelta(hours=48)
                }
            ]
        }
        
    def fake_get_cost_and_usage(**kwargs):
        return {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-06-24", "End": "2026-06-25"},
                    "Estimated": True,
                    "Groups": [
                        {
                            "Keys": ["112233", "Amazon Elastic Compute Cloud - Compute", "ap-southeast-1"],
                            "Metrics": {"UnblendedCost": {"Amount": "200.00"}}
                        }
                    ]
                }
            ]
        }
        
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object,
        list_objects_func=fake_list_objects
    )
    handler.ce_client = finops_common.FakeCostExplorer(
        get_cost_and_usage_func=fake_get_cost_and_usage
    )
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = _fake_sts_for_account()
    
    event_data = {
        "run_id": "run-delayed",
        "correlation_id": "corr-delayed",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    assert resp["details"]["telemetry_delay_event"] is True
    assert resp["details"]["delayed_cur"] is True
    assert resp["details"]["estimated_billing"] is True
    assert resp["details"]["current_ce_cost_gap_usd"] == 200.00
    assert "AmazonEC2" in resp["details"]["missing_resources"]
    assert resp["details"]["comparison_window"]["start_date"] == "2026-06-24"
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.ce_client = None
    handler.sts_client = None

def test_cost_puller_cur_delayed_no_fallback():
    # 3. CUR delayed without fallback returns CUR_DELAY.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    def fake_list_objects(bucket, prefix):
        return {"Contents": []} # No files, so delayed
    
    handler.s3_client = finops_common.FakeS3(list_objects_func=fake_list_objects)
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.sts_client = _fake_sts_for_account()
    
    event_data = {
        "run_id": "run-no-fallback",
        "correlation_id": "corr-no-fallback",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CUR_DELAY"
    assert resp["details"]["delayed_cur"] is True
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.ce_client = None
    handler.sts_client = None

def test_cost_puller_ce_throttled_no_cache():
    # 4. CE throttled without cache returns CE_THROTTLED.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    def fake_list_objects(bucket, prefix):
        # If prefix is cur/account_id=..., it's searching for cache. Return empty to simulate no cache.
        # If prefix is cur/source_prefix, it's checking CUR freshness. Return delayed.
        from datetime import timedelta
        if "account_id=" in prefix:
            return {"Contents": []}
        return {
            "Contents": [
                {
                    "Key": "cur/manifest.json",
                    "LastModified": datetime.utcnow() - timedelta(hours=48)
                }
            ]
        }
        
    def fake_get_cost_and_usage(**kwargs):
        raise Exception("Rate limit exceeded: ThrottlingException")
        
    handler.s3_client = finops_common.FakeS3(list_objects_func=fake_list_objects)
    handler.ce_client = finops_common.FakeCostExplorer(get_cost_and_usage_func=fake_get_cost_and_usage)
    handler.sts_client = _fake_sts_for_account()
    
    event_data = {
        "run_id": "run-throttled",
        "correlation_id": "corr-throttled",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CE_THROTTLED"
    assert resp["details"]["stale_cost_explorer"] is True
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.ce_client = None
    handler.sts_client = None

def test_cost_puller_ce_throttled_with_cache():
    # 5. CE throttled with cached fallback returns READY with stale flag.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    cached_envelope = {
        "schema_version": "3.2.0",
        "aws_cur_line_items": [],
        "aws_cost_explorer_daily": [{"date": "2026-06-24", "unblended_cost": 150.00}],
        "quality": {"estimated_billing": True, "missing_cloudwatch": True}
    }
    cached_bytes = gzip.compress(json.dumps(cached_envelope).encode("utf-8"))
    
    def fake_list_objects(bucket, prefix):
        from datetime import timedelta
        # Both cache checking and CUR delay check
        if "account_id=" in prefix:
            return {
                "Contents": [
                    {
                        "Key": f"{prefix}cached_file.json.gz",
                        "LastModified": datetime.utcnow() - timedelta(hours=1)
                    }
                ]
            }
        return {
            "Contents": [
                {
                    "Key": "cur/manifest.json",
                    "LastModified": datetime.utcnow() - timedelta(hours=48)
                }
            ]
        }
        
    def fake_get_object(bucket, key):
        return cached_bytes
        
    def fake_get_cost_and_usage(**kwargs):
        raise Exception("Rate limit exceeded: ThrottlingException")
        
    handler.s3_client = finops_common.FakeS3(
        list_objects_func=fake_list_objects,
        get_object_func=fake_get_object
    )
    handler.ce_client = finops_common.FakeCostExplorer(get_cost_and_usage_func=fake_get_cost_and_usage)
    handler.sts_client = _fake_sts_for_account()
    
    event_data = {
        "run_id": "run-throttled-cache",
        "correlation_id": "corr-throttled-cache",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    assert resp["details"]["stale_cost_explorer"] is True
    assert resp["details"]["estimated_billing"] is True
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.ce_client = None
    handler.sts_client = None

def test_cost_puller_missing_cloudwatch():
    # 6. Missing CloudWatch metrics returns READY with missing_cloudwatch=true.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    
    def fake_head_object(bucket, key):
        return {"ETag": '"abc123"'}

    def fake_get_object(bucket, key):
        return _fake_manifest_bytes()
        
    def fake_get_metric_data(**kwargs):
        raise Exception("CloudWatch is down")
        
    handler.s3_client = finops_common.FakeS3(
        head_object_func=fake_head_object,
        get_object_func=fake_get_object,
    )
    handler.cw_client = finops_common.FakeCloudWatch(get_metric_data_func=fake_get_metric_data)
    handler.sts_client = _fake_sts_for_account()
    
    event_data = {
        "run_id": "run-missing-cw",
        "correlation_id": "corr-missing-cw",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    assert resp["details"]["missing_cloudwatch"] is True
    assert resp["details"]["completeness_score"] == 0.5 # 1.0 * 0.5
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.cw_client = None
    handler.sts_client = None


def test_cost_puller_traffic_fallback():
    # 7. Missing traffic metrics mark CloudWatch as missing without synthetic traffic.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    
    def fake_head_object(bucket, key):
        return {"ETag": '"abc123"'}

    def fake_get_object(bucket, key):
        return _fake_manifest_bytes()
        
    def fake_get_metric_data(**kwargs):
        raise Exception("CloudWatch returns empty or fails for traffic")
        
    handler.s3_client = finops_common.FakeS3(
        head_object_func=fake_head_object,
        get_object_func=fake_get_object,
    )
    handler.cw_client = finops_common.FakeCloudWatch(get_metric_data_func=fake_get_metric_data)
    handler.sts_client = _fake_sts_for_account()
    
    event_data = {
        "run_id": "run-traffic",
        "correlation_id": "corr-traffic",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    context = resp["details"]["business_context"][0]
    assert context["traffic_source"] == "ALB"
    assert context["traffic_volume"] == 0.0
    assert resp["details"]["missing_cloudwatch"] is True
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.cw_client = None
    handler.sts_client = None

def test_cost_puller_unsafe_cross_tenant_paths():
    # 8. Bucket/account validation rejects unsafe or cross-tenant source paths.
    handler.s3_client = finops_common.FakeS3()
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = finops_common.FakeSTS()
    
    event_data = {
        "run_id": "run-unsafe",
        "correlation_id": "corr-unsafe",
        "account_id": "112233445566",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    # 8a: Cross-tenant bucket name mismatch
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-999999999999-telemetry" # 999999999999 does not match 112233445566
    with pytest.raises(finops_common.UnsafeActionError) as exc:
        handler.handle_request(event_data, None)
    assert "Cross-tenant" in str(exc.value)
    
    # 8b: Path traversal
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233445566-telemetry/../../etc"
    with pytest.raises(finops_common.UnsafeActionError) as exc:
        handler.handle_request(event_data, None)
    assert "Unsafe bucket name" in str(exc.value)
    
    # Cleanup
    if "LAKEHOUSE_BUCKET_NAME" in os.environ:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
    handler.s3_client = None
    handler.ce_client = None
    handler.cw_client = None
    handler.sts_client = None

def test_get_cross_account_session_success():
    from unittest.mock import patch, MagicMock
    fake_sts = finops_common.FakeSTS(
        assume_role_func=lambda **kwargs: {
            "Credentials": {
                "AccessKeyId": "fixture-access-key",
                "SecretAccessKey": "fixture-secret-key",
                "SessionToken": "fixture-session-token",
            }
        }
    )
    with patch("workers.cost_puller.handler.boto3.Session") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        session = handler.get_cross_account_session(fake_sts, "999999999999", "112233445566")
        
        assert session == mock_session
        mock_session_class.assert_called_once_with(
            aws_access_key_id="fixture-access-key",
            aws_secret_access_key="fixture-secret-key",
            aws_session_token="fixture-session-token",
            region_name="ap-southeast-1",
        )

def test_get_cross_account_session_same_account():
    fake_sts = finops_common.FakeSTS()
    session = handler.get_cross_account_session(fake_sts, "112233445566", "112233445566")
    assert session is None

def test_get_cross_account_session_assume_role_failure():
    def fake_assume_role(**kwargs):
        raise RuntimeError("AccessDenied: Not authorized to assume this role")
    
    fake_sts = finops_common.FakeSTS(assume_role_func=fake_assume_role)
    with pytest.raises(handler.TelemetryAuthError) as exc_info:
        handler.get_cross_account_session(fake_sts, "999999999999", "112233445566")
    assert "Failed to assume role" in str(exc_info.value)

def test_get_cross_account_session_programming_error_propagates():
    def fake_assume_role(**kwargs):
        raise KeyError("missing_key")
    
    fake_sts = finops_common.FakeSTS(assume_role_func=fake_assume_role)
    with pytest.raises(KeyError):
        handler.get_cross_account_session(fake_sts, "999999999999", "112233445566")

def test_handle_request_remote_session_override():
    from unittest.mock import patch, MagicMock
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-999999999999-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    os.environ["CUR_EXPORTS_JSON"] = json.dumps({
        "999999999999": {
            "source_account_id": "999999999999",
            "prefix": "cur",
            "export_name": "manifest",
            "allowed_raw_prefix": "cur"
        }
    })

    def fake_get_caller_identity():
        return {"Account": "112233445566"}

    fake_sts = finops_common.FakeSTS(
        get_caller_identity_func=fake_get_caller_identity
    )

    mock_session = MagicMock()
    mock_s3 = MagicMock()
    mock_ce = MagicMock()
    mock_cw = MagicMock()

    mock_s3.head_object.return_value = {
        "ETag": '"abc123"',
        "ContentLength": 100
    }
    
    # Remote manifest has different account in ARN
    remote_manifest = json.dumps({
        "executionId": "exec-remote",
        "exportArn": "arn:aws:bcm-data-exports:us-east-1:999999999999:export/cur2",
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
        "dataFiles": ["s3://tf2-finops-cur-export-bucket/cur/manifest/data/BILLING_PERIOD=2026-06/part.parquet"]
    }).encode("utf-8")
    
    mock_s3.get_object.return_value = remote_manifest

    def mock_client(service_name):
        if service_name == "s3":
            return mock_s3
        elif service_name == "ce":
            return mock_ce
        elif service_name == "cloudwatch":
            return mock_cw
        return None

    mock_session.client.side_effect = mock_client

    event_data = {
        "run_id": "run-remote-override",
        "correlation_id": "corr-remote-override",
        "account_id": "999999999999",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }

    # Set all global clients to prevent Real* classes (which need boto3) from being created
    handler.s3_client = mock_s3
    handler.ce_client = finops_common.FakeCostExplorer()
    source_cw_mock = MagicMock()
    handler.cw_client = source_cw_mock
    handler.sts_client = fake_sts

    with patch("workers.cost_puller.handler.get_cross_account_session", return_value=mock_session):
        resp = handler.handle_request(event_data, None)

    assert resp["status"] == "READY"
    mock_s3.head_object.assert_called_with("tf2-finops-cur-export-bucket", "cur/manifest/metadata/BILLING_PERIOD=2026-06/manifest-Manifest.json")
    mock_s3.put_object.assert_called()
    mock_cw.get_metric_data.assert_called()
    source_cw_mock.get_metric_data.assert_not_called()

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.ce_client = None
    handler.cw_client = None
    handler.sts_client = None


# ---------------------------------------------------------------------------
# STS Cross-Account Tenant Binding Tests (Blocker 4)
# ---------------------------------------------------------------------------

def test_cost_puller_assume_role_passes_external_id_and_tags():
    """get_cross_account_session must pass ExternalId, Tags, and TransitiveTagKeys to assume_role."""
    assume_calls = []

    def fake_assume_role(**kwargs):
        assume_calls.append(kwargs)
        return {
            "Credentials": {
                "AccessKeyId": "AKID",
                "SecretAccessKey": "SECRET",
                "SessionToken": "TOKEN",
            }
        }

    fake_sts = finops_common.FakeSTS(
        get_caller_identity_func=lambda: {"Account": "111111111111"},
        assume_role_func=fake_assume_role,
    )

    session = handler.get_cross_account_session(
        fake_sts,
        account_id="999999999999",
        current_account_id="111111111111",
        tenant_id="abc-tenant-id",
    )

    assert len(assume_calls) == 1, "assume_role should be called exactly once"
    call_kwargs = assume_calls[0]
    assert call_kwargs["ExternalId"] == "abc-tenant-id", "ExternalId must be tenant_id"
    assert {"Key": "tenant_id", "Value": "abc-tenant-id"} in call_kwargs["Tags"], (
        "Tags must contain {Key='tenant_id', Value=tenant_id}"
    )
    assert "tenant_id" in call_kwargs["TransitiveTagKeys"], (
        "TransitiveTagKeys must include 'tenant_id'"
    )


def test_cost_puller_assume_role_no_extra_params_when_tenant_id_empty():
    """get_cross_account_session must not send ExternalId/Tags when tenant_id is empty."""
    assume_calls = []

    def fake_assume_role(**kwargs):
        assume_calls.append(kwargs)
        return {
            "Credentials": {
                "AccessKeyId": "AKID",
                "SecretAccessKey": "SECRET",
                "SessionToken": "TOKEN",
            }
        }

    fake_sts = finops_common.FakeSTS(
        get_caller_identity_func=lambda: {"Account": "111111111111"},
        assume_role_func=fake_assume_role,
    )

    handler.get_cross_account_session(
        fake_sts,
        account_id="999999999999",
        current_account_id="111111111111",
        tenant_id="",  # empty tenant_id
    )

    assert len(assume_calls) == 1
    call_kwargs = assume_calls[0]
    assert "ExternalId" not in call_kwargs, "ExternalId must not be sent when tenant_id is empty"
    assert "Tags" not in call_kwargs, "Tags must not be sent when tenant_id is empty"
    assert "TransitiveTagKeys" not in call_kwargs, "TransitiveTagKeys must not be sent when tenant_id is empty"


def test_cost_puller_assume_role_uses_telemetry_member_role_name_env():
    """get_cross_account_session must use TELEMETRY_MEMBER_ROLE_NAME env var, not hardcoded role."""
    os.environ["TELEMETRY_MEMBER_ROLE_NAME"] = "custom-telemetry-role"
    assume_calls = []

    def fake_assume_role(**kwargs):
        assume_calls.append(kwargs)
        return {
            "Credentials": {
                "AccessKeyId": "AKID",
                "SecretAccessKey": "SECRET",
                "SessionToken": "TOKEN",
            }
        }

    fake_sts = finops_common.FakeSTS(
        get_caller_identity_func=lambda: {"Account": "111111111111"},
        assume_role_func=fake_assume_role,
    )

    handler.get_cross_account_session(
        fake_sts,
        account_id="999999999999",
        current_account_id="111111111111",
        tenant_id="t-123",
    )

    assert len(assume_calls) == 1
    role_arn = assume_calls[0]["RoleArn"]
    assert "custom-telemetry-role" in role_arn, (
        f"RoleArn must use TELEMETRY_MEMBER_ROLE_NAME; got: {role_arn}"
    )
    assert "cdo-telemetry-ingestion-role" not in role_arn, (
        "RoleArn must not use the hardcoded default role name"
    )

    del os.environ["TELEMETRY_MEMBER_ROLE_NAME"]


def test_cost_puller_ce_fallback_two_dimensions():
    """
    CE fallback path calls GetCostAndUsage using only LINKED_ACCOUNT and SERVICE,
    and returns region set to 'global' in normalized fallback records.
    """
    account_id = "112233"
    os.environ["LAKEHOUSE_BUCKET_NAME"] = f"tf2-finops-{account_id}-lakehouse"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    os.environ["CUR_EXPORTS_JSON"] = json.dumps({
        account_id: {
            "source_account_id": account_id,
            "prefix": "finops-cur-export",
            "export_name": "finops-export",
            "allowed_raw_prefix": "finops-cur-export",
        }
    })

    captured_kwargs = []

    def fake_get_cost_and_usage(**kwargs):
        captured_kwargs.append(kwargs)
        return {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-06-24", "End": "2026-06-25"},
                    "Estimated": False,
                    "Groups": [
                        {
                            "Keys": [account_id, "Amazon Elastic Compute Cloud - Compute"],
                            "Metrics": {"UnblendedCost": {"Amount": "150.00"}}
                        }
                    ]
                }
            ]
        }

    put_calls = []
    def fake_put_object(bucket, key, body):
        put_calls.append((bucket, key, body))

    # Without head_object_func, FakeS3 will raise 404 NoSuchKey by default
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object
    )
    handler.ce_client = finops_common.FakeCostExplorer(
        get_cost_and_usage_func=fake_get_cost_and_usage
    )
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = finops_common.FakeSTS(
        get_caller_identity_func=lambda: {"Account": account_id}
    )

    resp = handler.handle_request(
        {
            "run_id": "run-ce-fallback-2d",
            "correlation_id": "corr-ce-fallback-2d",
            "account_id": account_id,
            "cost_period": "2026-06",
            "execution_date": "2026-06-24",
        },
        None,
    )

    assert resp["status"] == "READY"
    
    # Prove only 2 GroupBy dimensions are used
    assert len(captured_kwargs) == 1
    group_by = captured_kwargs[0]["GroupBy"]
    assert len(group_by) == 2
    assert {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"} in group_by
    assert {"Type": "DIMENSION", "Key": "SERVICE"} in group_by
    assert {"Type": "DIMENSION", "Key": "REGION"} not in group_by

    # Prove region is normalized to 'global'
    raw_telemetry_put = [k for b, k, v in put_calls if k.startswith("cur/")]
    assert len(raw_telemetry_put) == 1
    raw_data_body = put_calls[0][2]
    if raw_data_body.startswith(b'\x1f\x8b'):
        raw_data_body = gzip.decompress(raw_data_body)
    raw_json = json.loads(raw_data_body.decode("utf-8"))
    
    ce_daily_records = raw_json.get("aws_cost_explorer_daily", [])
    assert len(ce_daily_records) == 1
    assert ce_daily_records[0]["region"] == "global"

    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    del os.environ["CUR_EXPORTS_JSON"]
    handler.s3_client = None
    handler.ce_client = None
    handler.cw_client = None
    handler.sts_client = None


def test_handle_request_cross_account_assume_role_failure():
    from unittest.mock import MagicMock
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-999999999999-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "tf2-finops-cur-export-bucket"
    os.environ["CUR_EXPORTS_JSON"] = json.dumps({
        "999999999999": {
            "source_account_id": "999999999999",
            "prefix": "cur",
            "export_name": "manifest",
            "allowed_raw_prefix": "cur"
        }
    })

    def fake_get_caller_identity():
        return {"Account": "112233445566"}

    def fake_assume_role(**kwargs):
        raise RuntimeError("AccessDenied: Not authorized to assume this role")

    fake_sts = finops_common.FakeSTS(
        get_caller_identity_func=fake_get_caller_identity,
        assume_role_func=fake_assume_role
    )

    # Mock clients to verify they aren't used for queries
    mock_s3 = MagicMock()
    mock_ce = MagicMock()
    mock_cw = MagicMock()

    handler.s3_client = mock_s3
    handler.ce_client = mock_ce
    handler.cw_client = mock_cw
    handler.sts_client = fake_sts

    event_data = {
        "run_id": "run-fail-closed",
        "correlation_id": "corr-fail-closed",
        "account_id": "999999999999",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }

    try:
        resp = handler.handle_request(event_data, None)
        assert resp["status"] == "TELEMETRY_AUTH_FAILED"
        assert resp["details"]["target_account_id"] == "999999999999"
        assert resp["details"]["current_account_id"] == "112233445566"
        assert resp["details"]["role_name"] == "cdo-telemetry-ingestion-role"
        assert resp["details"]["delayed_cur"] is True
        assert resp["details"]["fail_closed"] is True

        # Verify that S3/CE/CW were NOT called (fail closed)
        mock_ce.get_cost_and_usage.assert_not_called()
        mock_cw.get_metric_data.assert_not_called()
        mock_s3.list_objects_v2.assert_not_called()
    finally:
        del os.environ["LAKEHOUSE_BUCKET_NAME"]
        del os.environ["CUR_SOURCE_BUCKET"]
        del os.environ["CUR_EXPORTS_JSON"]
        handler.s3_client = None
        handler.ce_client = None
        handler.cw_client = None
        handler.sts_client = None

