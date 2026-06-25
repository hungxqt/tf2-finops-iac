import pytest
import os
import json
import urllib.error
import socket
from unittest.mock import patch, MagicMock
from workers.vpc_alb_caller import handler
from finops_common.utils import (
    ConfigMissingError,
    InvalidInputError,
    ServiceUnavailableError,
    ContractMismatchError,
    TimeoutError
)

@pytest.fixture(autouse=True)
def setup_env():
    # Save current env
    old_alb = os.environ.get("ALB_BASE_URL")
    old_region = os.environ.get("AWS_REGION")
    old_service = os.environ.get("SIGV4_SERVICE_NAME")
    
    # Set default values for tests
    os.environ["ALB_BASE_URL"] = "https://internal-ai-alb.us-east-1.elb.amazonaws.com"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["SIGV4_SERVICE_NAME"] = "ai-engine"
    
    yield
    
    # Restore
    if old_alb:
        os.environ["ALB_BASE_URL"] = old_alb
    else:
        os.environ.pop("ALB_BASE_URL", None)
        
    if old_region:
        os.environ["AWS_REGION"] = old_region
    else:
        os.environ.pop("AWS_REGION", None)
        
    if old_service:
        os.environ["SIGV4_SERVICE_NAME"] = old_service
    else:
        os.environ.pop("SIGV4_SERVICE_NAME", None)

@patch("urllib.request.urlopen")
def test_vpc_alb_caller_happy_path(mock_urlopen):
    # Mock response from ALB
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true, "anomalies_detected": false, "data_confidence": "HIGH", "anomalies_list": []}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    event_data = {
        "path": "/v1/detect",
        "method": "POST",
        "tenant_id": "tenant-123",
        "correlation_id": "corr-456",
        "idempotency_key": "tenant-123:2026-06-26:daily",
        "body": {
            "data_source_type": "RAW_JSON",
            "business_context": {
                "linked_account_id": "123456789012",
                "traffic_volume": 5000,
                "traffic_source": "ALB",
                "campaign_flag": False,
                "load_test_flag": False,
                "migration_flag": False
            }
        }
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["success"] is True
    assert resp["anomalies_detected"] is False

def test_vpc_alb_caller_invalid_inputs():
    # URL/host override rejection
    with pytest.raises(InvalidInputError, match="URL override or host override detected"):
        handler.handle_request({"path": "https://malicious-host.com/v1/detect"}, None)
        
    with pytest.raises(InvalidInputError, match="URL override or host override detected"):
        handler.handle_request({"path": "http://127.0.0.1/v1/detect"}, None)
        
    # Path traversal rejection
    with pytest.raises(InvalidInputError, match="Path traversal or duplicate slashes detected"):
        handler.handle_request({"path": "/v1/detect/../../something"}, None)
        
    with pytest.raises(InvalidInputError, match="Path traversal or duplicate slashes detected"):
        handler.handle_request({"path": "/v1//detect"}, None)
        
    # Disallowed path rejection
    with pytest.raises(InvalidInputError, match="Disallowed path input"):
        handler.handle_request({"path": "/v1/detect/unauthorized"}, None)
        
    # Missing tenant_id/idempotency_key for non-health paths
    with pytest.raises(InvalidInputError, match="tenant_id parameter is required"):
        handler.handle_request({"path": "/v1/detect", "idempotency_key": "some-key"}, None)
        
    with pytest.raises(InvalidInputError, match="idempotency_key parameter is required"):
        handler.handle_request({"path": "/v1/detect", "tenant_id": "tenant-123"}, None)

@patch("urllib.request.urlopen")
def test_vpc_alb_caller_health_check_happy_path(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"status": "healthy"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # /health path should succeed without tenant_id or idempotency_key
    event_data = {
        "path": "/health",
        "method": "GET"
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "healthy"

@patch("urllib.request.urlopen")
def test_vpc_alb_caller_timeout(mock_urlopen):
    # Simulate network timeout
    mock_urlopen.side_effect = socket.timeout("Connection timed out")
    
    event_data = {
        "path": "/v1/detect",
        "tenant_id": "tenant-123",
        "idempotency_key": "key-123"
    }
    
    with pytest.raises(TimeoutError, match="Connection to AI Engine timed out"):
        handler.handle_request(event_data, None)

@patch("urllib.request.urlopen")
def test_vpc_alb_caller_http_429(mock_urlopen):
    # Simulate 429 Too Many Requests
    fp = MagicMock()
    fp.read.return_value = b"Rate limit exceeded"
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://internal-ai-alb.us-east-1.elb.amazonaws.com/v1/detect",
        429, "Too Many Requests", {}, fp
    )
    
    event_data = {
        "path": "/v1/detect",
        "tenant_id": "tenant-123",
        "idempotency_key": "key-123"
    }
    
    with pytest.raises(ServiceUnavailableError, match="AI Engine rate limit exceeded"):
        handler.handle_request(event_data, None)

@patch("urllib.request.urlopen")
def test_vpc_alb_caller_http_503(mock_urlopen):
    # Simulate 503 Service Unavailable
    fp = MagicMock()
    fp.read.return_value = b"Service Unavailable"
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://internal-ai-alb.us-east-1.elb.amazonaws.com/v1/detect",
        503, "Service Unavailable", {}, fp
    )
    
    event_data = {
        "path": "/v1/detect",
        "tenant_id": "tenant-123",
        "idempotency_key": "key-123"
    }
    
    with pytest.raises(ServiceUnavailableError, match="AI Engine gateway/service unavailable"):
        handler.handle_request(event_data, None)

@patch("urllib.request.urlopen")
def test_vpc_alb_caller_http_401(mock_urlopen):
    # Simulate 401 Unauthorized
    fp = MagicMock()
    fp.read.return_value = b"Auth failed"
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://internal-ai-alb.us-east-1.elb.amazonaws.com/v1/detect",
        401, "Unauthorized", {}, fp
    )
    
    event_data = {
        "path": "/v1/detect",
        "tenant_id": "tenant-123",
        "idempotency_key": "key-123"
    }
    
    with pytest.raises(ContractMismatchError, match="AI Engine authentication/authorization failure"):
        handler.handle_request(event_data, None)

@patch("urllib.request.urlopen")
def test_vpc_alb_caller_invalid_json_response(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'not-a-valid-json'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    event_data = {
        "path": "/v1/detect",
        "tenant_id": "tenant-123",
        "idempotency_key": "key-123"
    }
    
    with pytest.raises(ContractMismatchError, match="Response is not valid JSON"):
        handler.handle_request(event_data, None)
