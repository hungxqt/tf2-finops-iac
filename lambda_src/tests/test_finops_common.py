import pytest
from datetime import datetime
import finops_common

def test_validate_event_valid():
    evt_dict = {
        "run_id": "run-123",
        "correlation_id": "corr-456",
        "cost_period": "2026-06",
        "environment": "sandbox",
        "source_data_version": "v1"
    }
    evt = finops_common.Event.from_dict(evt_dict)
    # Should not raise
    finops_common.validate_event(evt)

def test_validate_event_state_machine_input():
    evt_dict = {
        "run_id": "manual-test-001",
        "account_id": "123456789012",
        "billing_period": "2026-06",
        "execution_date": "2026-06-23",
        "environment": "sandbox",
        "ai_contract_version": "v1"
    }
    evt = finops_common.Event.from_dict(evt_dict)
    finops_common.validate_event(evt)
    assert evt.cost_period == "2026-06"
    assert evt.correlation_id == "manual-test-001"
    assert evt.source_data_version == "v1"

def test_validate_event_missing_fields():
    evt = finops_common.Event(run_id="run-123")
    with pytest.raises(ValueError, match="missing required event field"):
        finops_common.validate_event(evt)

def test_create_response():
    details = {"key": "value"}
    resp = finops_common.create_response("success", "run-123", "corr-456", "test_worker", details)
    assert resp.status == "success"
    assert resp.run_id == "run-123"
    assert resp.correlation_id == "corr-456"
    assert resp.worker == "test_worker"
    assert resp.details["key"] == "value"

def test_parse_s3_uri():
    bucket, key = finops_common.parse_s3_uri("s3://my-bucket/path/to/object")
    assert bucket == "my-bucket"
    assert key == "path/to/object"

    with pytest.raises(ValueError):
        finops_common.parse_s3_uri("https://my-bucket/path")

def test_idempotency_key():
    key = finops_common.idempotency_key("123456", "2026-06", "2026-06-24")
    assert key == "123456:2026-06:2026-06-24"

def test_redact_sensitive_info():
    msg = "My secret token: token=abcdefghijklmnopqrstuvwxyz12345"
    redacted = finops_common.redact_sensitive_info(msg)
    assert "[REDACTED]" in redacted
    assert "abcdefghijkl" not in redacted

    msg2 = "The secret arn: arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret"
    redacted2 = finops_common.redact_sensitive_info(msg2)
    assert "[REDACTED_SECRET_ARN]" in redacted2

def test_parse_date():
    dt = finops_common.parse_date("2026-06-24")
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 24

    with pytest.raises(ValueError):
        finops_common.parse_date("invalid-date")


def test_dynamodb_client_signatures():
    import inspect
    from finops_common import DynamoDBClient, RealDynamoDB, FakeDynamoDB

    base_sig = inspect.signature(DynamoDBClient.put_item)
    real_sig = inspect.signature(RealDynamoDB.put_item)
    fake_sig = inspect.signature(FakeDynamoDB.put_item)

    # Check that they all have the same parameters
    assert list(base_sig.parameters.keys()) == ["self", "table_name", "item", "condition_expression"]
    assert list(real_sig.parameters.keys()) == ["self", "table_name", "item", "condition_expression"]
    assert list(fake_sig.parameters.keys()) == ["self", "table_name", "item", "condition_expression"]

    # Verify that condition_expression is optional and defaults to None
    assert base_sig.parameters["condition_expression"].default is None
    assert real_sig.parameters["condition_expression"].default is None
    assert fake_sig.parameters["condition_expression"].default is None

