import pytest
import os
import json
from workers.ai_client import handler
import finops_common

def test_ai_client_simulations():
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
    }

    # Test simulate-timeout
    event_data["action"] = "simulate-timeout"
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "TIMEOUT"
    assert resp["required_fields_valid"] is False

    # Test simulate-unavailable
    event_data["action"] = "simulate-unavailable"
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "UNAVAILABLE"

    # Test simulate-mismatch
    event_data["action"] = "simulate-mismatch"
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CONTRACT_MISMATCH"

    # Test simulate-no-anomaly
    event_data["action"] = "simulate-no-anomaly"
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["anomaly_found"] is False

    # Test simulate-unsafe
    event_data["action"] = "simulate-unsafe"
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["anomaly_found"] is True
    assert resp["recommended_containment_mode"] == "terminate"

def test_ai_client_missing_config_fails_closed():
    # Ensure config is missing
    for var in ["AI_ENGINE_ENDPOINT_URL", "AI_ENGINE_SECRET_NAME", "AI_ENGINE_CONTRACT_VERSION"]:
        if var in os.environ:
            del os.environ[var]
            
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "UNAVAILABLE"
    assert resp["required_fields_valid"] is False
    assert resp["anomaly_found"] is False

def test_ai_client_non_https_fails_closed():
    os.environ["AI_ENGINE_ENDPOINT_URL"] = "http://my-ai-engine.internal"
    os.environ["AI_ENGINE_SECRET_NAME"] = "my-secret"
    os.environ["AI_ENGINE_CONTRACT_VERSION"] = "v1"
    os.environ["AI_ENGINE_ALLOWED_HOSTS"] = "my-ai-engine.internal"
    
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CONTRACT_MISMATCH"
    assert resp["required_fields_valid"] is False

def test_ai_client_disallowed_host_fails_closed():
    os.environ["AI_ENGINE_ENDPOINT_URL"] = "https://untrusted-host.com"
    os.environ["AI_ENGINE_SECRET_NAME"] = "my-secret"
    os.environ["AI_ENGINE_CONTRACT_VERSION"] = "v1"
    os.environ["AI_ENGINE_ALLOWED_HOSTS"] = "my-ai-engine.internal"
    
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "UNAVAILABLE"
    assert resp["required_fields_valid"] is False

def test_ai_client_mismatch_contract_version_fails_closed():
    os.environ["AI_ENGINE_ENDPOINT_URL"] = "https://my-ai-engine.internal"
    os.environ["AI_ENGINE_SECRET_NAME"] = "my-secret"
    os.environ["AI_ENGINE_CONTRACT_VERSION"] = "v1"
    os.environ["AI_ENGINE_ALLOWED_HOSTS"] = "my-ai-engine.internal"
    
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
        "source_data_version": "v2" # Version mismatch
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CONTRACT_MISMATCH"

def test_ai_client_secrets_manager_unavailable():
    os.environ["AI_ENGINE_ENDPOINT_URL"] = "https://my-ai-engine.internal"
    os.environ["AI_ENGINE_SECRET_NAME"] = "my-secret"
    os.environ["AI_ENGINE_CONTRACT_VERSION"] = "v1"
    os.environ["AI_ENGINE_ALLOWED_HOSTS"] = "my-ai-engine.internal"
    handler.secrets_client = None

    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "UNAVAILABLE"

def test_ai_client_http_post_success_and_failures():
    os.environ["AI_ENGINE_ENDPOINT_URL"] = "https://my-ai-engine.internal"
    os.environ["AI_ENGINE_SECRET_NAME"] = "my-secret"
    os.environ["AI_ENGINE_CONTRACT_VERSION"] = "v1"
    os.environ["AI_ENGINE_ALLOWED_HOSTS"] = "my-ai-engine.internal"
    
    handler.secrets_client = finops_common.FakeSecretsManager(
        get_secret_value_func=lambda secret_id: "my-bearer-token"
    )

    event_data = {
        "run_id": "run-10",
        "correlation_id": "corr-10",
        "cost_period": "2026-06",
        "environment": "sandbox"
    }

    # 1. Success case (anomaly found)
    handler.http_client = handler.FakeHTTPClient(
        post_func=lambda url, headers, body, timeout: (
            200,
            b'{"anomaly_found": true, "severity": "critical", "confidence": 0.99, "recommended_containment_mode": "apply", "anomaly_id": "ANOM-123"}'
        )
    )
    resp1 = handler.handle_request(event_data, None)
    assert resp1["status"] == "OK"
    assert resp1["anomaly_found"] is True
    assert resp1["recommended_containment_mode"] == "apply"
    assert resp1["anomaly_id"] == "ANOM-123"
    assert resp1["severity"] == "critical"
    assert resp1["confidence"] == 0.99

    # 2. HTTP timeout mapping
    def fake_post_timeout(*args, **kwargs):
        raise TimeoutError("connection timed out")
        
    handler.http_client = handler.FakeHTTPClient(post_func=fake_post_timeout)
    resp2 = handler.handle_request(event_data, None)
    assert resp2["status"] == "TIMEOUT"
    assert resp2["anomaly_found"] is False

    # 3. HTTP 500 error mapping
    handler.http_client = handler.FakeHTTPClient(
        post_func=lambda *args, **kwargs: (500, b"Internal server error")
    )
    resp3 = handler.handle_request(event_data, None)
    assert resp3["status"] == "UNAVAILABLE"

    # 4. Schema validation failure
    handler.http_client = handler.FakeHTTPClient(
        post_func=lambda *args, **kwargs: (200, b'{"some_field": true}')
    )
    resp4 = handler.handle_request(event_data, None)
    assert resp4["status"] == "CONTRACT_MISMATCH"

    # 5. Unsafe recommendation in production environment fails closed
    event_data_prod = event_data.copy()
    event_data_prod["environment"] = "prod"
    
    handler.http_client = handler.FakeHTTPClient(
        post_func=lambda *args, **kwargs: (
            200,
            b'{"anomaly_found": true, "severity": "critical", "confidence": 0.99, "recommended_containment_mode": "terminate", "anomaly_id": "ANOM-123"}'
        )
    )
    resp5 = handler.handle_request(event_data_prod, None)
    assert resp5["status"] == "CONTRACT_MISMATCH"
    assert resp5["anomaly_found"] is False

    # Clean up
    for var in ["AI_ENGINE_ENDPOINT_URL", "AI_ENGINE_SECRET_NAME", "AI_ENGINE_CONTRACT_VERSION", "AI_ENGINE_ALLOWED_HOSTS"]:
        if var in os.environ:
            del os.environ[var]
    handler.secrets_client = None
    handler.http_client = handler.RealHTTPClient()
