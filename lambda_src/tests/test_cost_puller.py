import pytest
import os
import json
import gzip
import hashlib
from datetime import datetime
from workers.cost_puller import handler
import finops_common

def test_cost_puller_cur_ready_path():
    # 1. CUR-ready path writes gzipped S3 telemetry and returns READY.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    put_called = []
    def fake_put_object(bucket, key, body):
        put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })
        
    def fake_list_objects(bucket, prefix):
        # Return a list indicating CUR is fresh (modified just now)
        return {
            "Contents": [
                {
                    "Key": "cur/manifest.json",
                    "LastModified": datetime.utcnow()
                }
            ]
        }
        
    handler.s3_client = finops_common.FakeS3(
        put_object_func=fake_put_object,
        list_objects_func=fake_list_objects
    )
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    
    event_data = {
        "run_id": "run-ready",
        "correlation_id": "corr-ready",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    assert resp["raw_data_uri"].startswith("s3://company-cdo-112233-telemetry/cur/account_id=112233/")
    assert resp["details"]["data_source_type"] == "S3_POINTER"
    assert resp["details"]["telemetry_delay_event"] is False
    
    assert len(put_called) == 2 # cur raw AND features
    
    # Verify CUR file content
    cur_bytes = put_called[0]["body"]
    decompressed = gzip.decompress(cur_bytes)
    envelope = json.loads(decompressed.decode("utf-8"))
    
    assert envelope["schema_version"] == "3.2.0"
    assert len(envelope["aws_cur_line_items"]) == 1
    assert envelope["aws_cur_line_items"][0]["line_item_usage_account_id"] == "112233"
    assert envelope["aws_cur_line_items"][0]["usage_density_24h"] == 1.0 # 24.0 / 24.0
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None

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

def test_cost_puller_cur_delayed_no_fallback():
    # 3. CUR delayed without fallback returns CUR_DELAY.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    def fake_list_objects(bucket, prefix):
        return {"Contents": []} # No files, so delayed
        
    # Real CE call fails or fallback is disabled
    os.environ["SYNTHETIC_FALLBACK_ENABLED"] = "false"
    
    handler.s3_client = finops_common.FakeS3(list_objects_func=fake_list_objects)
    handler.ce_client = finops_common.FakeCostExplorer() # returns empty dict, fallback disabled
    
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
    del os.environ["SYNTHETIC_FALLBACK_ENABLED"]
    handler.s3_client = None
    handler.ce_client = None

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

def test_cost_puller_missing_cloudwatch():
    # 6. Missing CloudWatch metrics returns READY with missing_cloudwatch=true.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    def fake_list_objects(bucket, prefix):
        return {"Contents": [{"Key": "cur/manifest.json", "LastModified": datetime.utcnow()}]}
        
    def fake_get_metric_data(**kwargs):
        raise Exception("CloudWatch is down")
        
    handler.s3_client = finops_common.FakeS3(list_objects_func=fake_list_objects)
    handler.cw_client = finops_common.FakeCloudWatch(get_metric_data_func=fake_get_metric_data)
    
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

def test_cost_puller_traffic_fallback():
    # 7. Traffic fallback returns traffic_source=Synthetic.
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-112233-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-112233-telemetry"
    
    def fake_list_objects(bucket, prefix):
        return {"Contents": [{"Key": "cur/manifest.json", "LastModified": datetime.utcnow()}]}
        
    def fake_get_metric_data(**kwargs):
        raise Exception("CloudWatch returns empty or fails for traffic")
        
    handler.s3_client = finops_common.FakeS3(list_objects_func=fake_list_objects)
    handler.cw_client = finops_common.FakeCloudWatch(get_metric_data_func=fake_get_metric_data)
    
    event_data = {
        "run_id": "run-traffic",
        "correlation_id": "corr-traffic",
        "account_id": "112233",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "READY"
    
    # Cleanup
    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.cw_client = None

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
    fake_sts = finops_common.FakeSTS()
    with patch("workers.cost_puller.handler.boto3.Session") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        session = handler.get_cross_account_session(fake_sts, "999999999999", "112233445566")
        
        assert session == mock_session
        mock_session_class.assert_called_once_with(
            aws_access_key_id="fake-access-key",
            aws_secret_access_key="fake-secret-key",
            aws_session_token="fake-session-token"
        )

def test_get_cross_account_session_same_account():
    fake_sts = finops_common.FakeSTS()
    session = handler.get_cross_account_session(fake_sts, "112233445566", "112233445566")
    assert session is None

def test_get_cross_account_session_assume_role_failure():
    def fake_assume_role(**kwargs):
        raise RuntimeError("AccessDenied: Not authorized to assume this role")
    
    fake_sts = finops_common.FakeSTS(assume_role_func=fake_assume_role)
    session = handler.get_cross_account_session(fake_sts, "999999999999", "112233445566")
    assert session is None

def test_get_cross_account_session_programming_error_propagates():
    def fake_assume_role(**kwargs):
        raise KeyError("missing_key")
    
    fake_sts = finops_common.FakeSTS(assume_role_func=fake_assume_role)
    with pytest.raises(KeyError):
        handler.get_cross_account_session(fake_sts, "999999999999", "112233445566")

def test_handle_request_remote_session_override():
    from unittest.mock import patch, MagicMock
    os.environ["LAKEHOUSE_BUCKET_NAME"] = "company-cdo-999999999999-telemetry"
    os.environ["CUR_SOURCE_BUCKET"] = "company-cdo-999999999999-telemetry"

    def fake_get_caller_identity():
        return {"AccountId": "112233445566"}

    fake_sts = finops_common.FakeSTS(
        get_caller_identity_func=fake_get_caller_identity
    )

    mock_session = MagicMock()
    mock_s3 = MagicMock()
    mock_ce = MagicMock()
    mock_cw = MagicMock()

    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "cur/manifest.json",
                "LastModified": datetime.utcnow()
            }
        ]
    }

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
    handler.s3_client = finops_common.FakeS3()
    handler.ce_client = finops_common.FakeCostExplorer()
    handler.cw_client = finops_common.FakeCloudWatch()
    handler.sts_client = fake_sts

    with patch("workers.cost_puller.handler.get_cross_account_session", return_value=mock_session):
        resp = handler.handle_request(event_data, None)

    assert resp["status"] == "READY"
    mock_s3.list_objects_v2.assert_called_with("company-cdo-999999999999-telemetry", "")
    mock_s3.put_object.assert_called()
    mock_cw.get_metric_data.assert_called()

    del os.environ["LAKEHOUSE_BUCKET_NAME"]
    del os.environ["CUR_SOURCE_BUCKET"]
    handler.s3_client = None
    handler.ce_client = None
    handler.cw_client = None
    handler.sts_client = None
