import pytest
import os
import re
import json
import hashlib
import urllib.error
import socket
from unittest.mock import patch, MagicMock
from botocore.credentials import Credentials
from workers.vpc_alb_caller import handler
from finops_common.utils import (
    ConfigMissingError,
    InvalidInputError,
    ServiceUnavailableError,
    ContractMismatchError,
    TimeoutError
)

VALID_TENANT_ID = "11111111-1111-4111-8111-111111111111"
VALID_CORRELATION_ID = "22222222-2222-4222-8222-222222222222"
VALID_IDEMPOTENCY_KEY = f"{VALID_TENANT_ID}:2026-06-26:daily"


def valid_ai_event(**overrides):
    event = {
        "path": "/v1/detect",
        "method": "POST",
        "tenant_id": VALID_TENANT_ID,
        "correlation_id": VALID_CORRELATION_ID,
        "idempotency_key": VALID_IDEMPOTENCY_KEY,
        "body": {
            "data_source_type": "RAW_JSON",
            "tenant_id": VALID_TENANT_ID,
            "correlation_id": VALID_CORRELATION_ID,
            "idempotency_key": VALID_IDEMPOTENCY_KEY,
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
    event.update(overrides)
    return event


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("ALB_BASE_URL", "https://internal-ai-alb.us-east-1.elb.amazonaws.com")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("SIGV4_SERVICE_NAME", "ai-engine")
    # Allow unsigned by default so basic tests work without real AWS creds in CI.
    # Individual tests that probe credential enforcement must override this env var.
    monkeypatch.setenv("ALLOW_UNSIGNED_AI_REQUESTS", "true")


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_happy_path(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true, "anomalies_detected": false, "data_confidence": "HIGH", "anomalies_list": []}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    event_data = valid_ai_event()
    resp = handler.handle_request(event_data, None)
    assert resp["success"] is True
    assert resp["anomalies_detected"] is False


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_sends_signed_contract_headers(mock_urlopen, monkeypatch):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    class FakeSession:
        def get_credentials(self):
            return Credentials("AKIDEXAMPLE", "SECRETEXAMPLE")

    monkeypatch.setattr(handler.botocore.session, "get_session", lambda: FakeSession())

    event_data = valid_ai_event()
    event_data["body"] = {**event_data["body"], "dry_run_mode": False, "dry_run": True}

    handler.handle_request(event_data, None)

    request = mock_urlopen.call_args.args[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["content-type"] == "application/json"
    assert headers["accept"] == "application/json"
    assert headers["x-tenant-id"] == VALID_TENANT_ID
    assert headers["x-idempotency-key"] == VALID_IDEMPOTENCY_KEY
    assert headers["x-correlation-id"] == VALID_CORRELATION_ID
    assert headers["x-payload-sha256"] == hashlib.sha256(request.data).hexdigest()
    assert headers["x-dry-run-mode"] == "false"
    assert "authorization" in headers


def test_vpc_alb_caller_invalid_inputs():
    with pytest.raises(InvalidInputError, match="URL override or host override detected"):
        handler.handle_request({"path": "https://malicious-host.com/v1/detect"}, None)

    with pytest.raises(InvalidInputError, match="URL override or host override detected"):
        handler.handle_request({"path": "http://127.0.0.1/v1/detect"}, None)

    with pytest.raises(InvalidInputError, match="Path traversal or duplicate slashes detected"):
        handler.handle_request({"path": "/v1/detect/../../something"}, None)

    with pytest.raises(InvalidInputError, match="Path traversal or duplicate slashes detected"):
        handler.handle_request({"path": "/v1//detect"}, None)

    with pytest.raises(InvalidInputError, match="Disallowed path input"):
        handler.handle_request({"path": "/v1/detect/unauthorized"}, None)

    with pytest.raises(InvalidInputError, match="tenant_id parameter is required"):
        handler.handle_request({"path": "/v1/detect", "idempotency_key": "some-key"}, None)

    with pytest.raises(InvalidInputError, match="idempotency_key parameter is required"):
        handler.handle_request({"path": "/v1/detect", "tenant_id": VALID_TENANT_ID}, None)

    with pytest.raises(InvalidInputError, match="correlation_id parameter is required"):
        handler.handle_request({
            "path": "/v1/detect",
            "tenant_id": VALID_TENANT_ID,
            "idempotency_key": VALID_IDEMPOTENCY_KEY,
        }, None)


def test_vpc_alb_caller_rejects_malformed_ai_context():
    with pytest.raises(InvalidInputError, match="tenant_id must be a UUID"):
        handler.handle_request(valid_ai_event(tenant_id="tenant-123"), None)

    with pytest.raises(InvalidInputError, match="correlation_id must be a UUID"):
        handler.handle_request(valid_ai_event(correlation_id="corr-456"), None)

    with pytest.raises(InvalidInputError, match="idempotency_key must match"):
        handler.handle_request(valid_ai_event(idempotency_key="key-123"), None)

    with pytest.raises(InvalidInputError, match="tenant prefix must match"):
        handler.handle_request(
            valid_ai_event(
                idempotency_key="33333333-3333-4333-8333-333333333333:2026-06-26:daily"
            ),
            None,
        )

    body_mismatch = valid_ai_event()
    body_mismatch["body"] = {**body_mismatch["body"], "correlation_id": "33333333-3333-4333-8333-333333333333"}
    with pytest.raises(InvalidInputError, match="body.correlation_id"):
        handler.handle_request(body_mismatch, None)


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_health_check_happy_path(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"status": "healthy"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    event_data = {"path": "/health", "method": "GET"}
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "healthy"


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_timeout(mock_urlopen):
    """Timeout on AI path (/v1/detect) must return a normalized ERR_LLM_TIMEOUT envelope."""
    mock_urlopen.side_effect = socket.timeout("Connection timed out")
    event_data = valid_ai_event()
    result = handler.handle_request(event_data, None)
    assert result.get("ai_error") is True, "Timeout must return normalized AI error envelope"
    assert result["error_code"] == "ERR_LLM_TIMEOUT"
    assert result["unavailable"] is True
    assert result["retryable"] is False


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_http_429(mock_urlopen):
    """HTTP 429 on AI path must return normalized ERR_RATE_LIMITED envelope (not raise)."""
    fp = MagicMock()
    fp.read.return_value = b"Rate limit exceeded"
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://internal-ai-alb.us-east-1.elb.amazonaws.com/v1/detect",
        429, "Too Many Requests", {}, fp
    )
    event_data = valid_ai_event()
    result = handler.handle_request(event_data, None)
    assert result.get("ai_error") is True
    assert result["http_status"] == 429
    assert result["error_code"] == "ERR_RATE_LIMITED"
    assert result["retryable"] is True


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_http_503(mock_urlopen):
    """HTTP 503 on AI path must return normalized ERR_SERVICE_DOWN envelope (not raise)."""
    fp = MagicMock()
    fp.read.return_value = b"Service Unavailable"
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://internal-ai-alb.us-east-1.elb.amazonaws.com/v1/detect",
        503, "Service Unavailable", {}, fp
    )
    event_data = valid_ai_event()
    result = handler.handle_request(event_data, None)
    assert result.get("ai_error") is True
    assert result["http_status"] == 503
    assert result["error_code"] == "ERR_SERVICE_DOWN"
    assert result["unavailable"] is True


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_http_401(mock_urlopen):
    """HTTP 401 on AI path must return normalized ERR_AUTH_FAILED envelope (not raise)."""
    fp = MagicMock()
    fp.read.return_value = b"Auth failed"
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://internal-ai-alb.us-east-1.elb.amazonaws.com/v1/detect",
        401, "Unauthorized", {}, fp
    )
    event_data = valid_ai_event()
    result = handler.handle_request(event_data, None)
    assert result.get("ai_error") is True
    assert result["http_status"] == 401
    assert result["error_code"] == "ERR_AUTH_FAILED"
    assert result["retryable"] is True  # auth failure is retryable (credentials may be refreshed)
    assert result["non_retryable"] is False


@patch("urllib.request.urlopen")
def test_vpc_alb_caller_invalid_json_response(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'not-a-valid-json'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    event_data = valid_ai_event()
    with pytest.raises(ContractMismatchError, match="Response is not valid JSON"):
        handler.handle_request(event_data, None)


@patch("urllib.request.urlopen")
def test_sandbox_s3_pointer_injects_rds_metrics_only(mock_urlopen, monkeypatch):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    monkeypatch.setenv("ENVIRONMENT", "sandbox")

    rewritten_payload = {
        "execution_date": "2026-03-20",
        "resource_utilization_metrics": [
            {"resource_id": "i-0123456789abcdef0", "cpu_utilization": 1.0},
            {"resource_id": "arn:aws:rds:ap-southeast-1:336805808730:db:orphan-db", "cpu_utilization": 2.0},
            {"resource_id": "RDS:db-nonprod-01", "cpu_utilization": 3.0},
            {"resource_id": "arn:aws:lambda:ap-southeast-1:336805808730:function:x", "cpu_utilization": 4.0},
        ],
    }

    class FakeS3Client:
        def __init__(self):
            self.put_calls = []

        def get_object(self, Bucket, Key):
            if Key == "path/input.json":
                body = MagicMock()
                body.read.return_value = json.dumps(rewritten_payload).encode("utf-8")
                return {"Body": body}
            raise Exception("not found")

        def put_object(self, **kwargs):
            self.put_calls.append(kwargs)
            return {}

    fake_s3 = FakeS3Client()
    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: fake_s3)

    event_data = valid_ai_event()
    event_data["body"] = {
        **event_data["body"],
        "data_source_type": "S3_POINTER",
        "account_id": "336805808730",
        "s3_bucket_uri": "s3://source-bucket/path/input.json",
        "resource_utilization_metrics": [],
    }

    handler.handle_request(event_data, None)

    request = mock_urlopen.call_args.args[0]
    sent_body = json.loads(request.data.decode("utf-8"))
    sent_metrics = sent_body.get("resource_utilization_metrics", [])
    sent_ids = [m.get("resource_id", "") for m in sent_metrics]

    assert len(sent_metrics) == 2
    assert all("rds" in rid.lower() for rid in sent_ids)
    assert any("orphan-db" in rid for rid in sent_ids)


@patch("urllib.request.urlopen")
def test_sandbox_s3_pointer_does_not_override_existing_metrics(mock_urlopen, monkeypatch):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    monkeypatch.setenv("ENVIRONMENT", "sandbox")

    rewritten_payload = {
        "execution_date": "2026-03-20",
        "resource_utilization_metrics": [
            {"resource_id": "arn:aws:rds:ap-southeast-1:336805808730:db:orphan-db", "cpu_utilization": 2.0},
        ],
    }

    class FakeS3Client:
        def get_object(self, Bucket, Key):
            if Key == "path/input.json":
                body = MagicMock()
                body.read.return_value = json.dumps(rewritten_payload).encode("utf-8")
                return {"Body": body}
            raise Exception("not found")

        def put_object(self, **kwargs):
            return {}

    fake_s3 = FakeS3Client()
    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: fake_s3)

    existing_metrics = [{"resource_id": "keep-this", "cpu_utilization": 9.9}]
    event_data = valid_ai_event()
    event_data["body"] = {
        **event_data["body"],
        "data_source_type": "S3_POINTER",
        "account_id": "336805808730",
        "s3_bucket_uri": "s3://source-bucket/path/input.json",
        "resource_utilization_metrics": existing_metrics,
    }

    handler.handle_request(event_data, None)

    request = mock_urlopen.call_args.args[0]
    sent_body = json.loads(request.data.decode("utf-8"))
    assert sent_body.get("resource_utilization_metrics") == existing_metrics


@patch("urllib.request.urlopen")
def test_detect_s3_pointer_hydrates_rds_metrics_outside_sandbox(mock_urlopen, monkeypatch):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    monkeypatch.setenv("ENVIRONMENT", "prod")

    payload = {
        "resource_utilization_metrics": [
            {"resource_id": "i-abc", "cpu_utilization": 10.0},
            {"resource_id": "arn:aws:rds:ap-southeast-1:111111111111:db:rds-prod-1", "cpu_utilization": 2.2},
            {"resource_id": "RDS:db-prod-2", "cpu_utilization": 1.1},
        ]
    }

    class FakeS3Client:
        def get_object(self, Bucket, Key):
            assert Bucket == "tf2-finops-sandbox-lakehouse-bucket"
            assert Key == "ai-input/path/input.json.gz"
            import gzip
            body = MagicMock()
            body.read.return_value = gzip.compress(json.dumps(payload).encode("utf-8"))
            return {"Body": body}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: FakeS3Client())

    event_data = valid_ai_event()
    event_data["body"] = {
        **event_data["body"],
        "data_source_type": "S3_POINTER",
        "s3_bucket_uri": "s3://tf2-finops-sandbox-lakehouse-bucket/ai-input/path/input.json.gz",
        "resource_utilization_metrics": [],
    }

    handler.handle_request(event_data, None)

    request = mock_urlopen.call_args.args[0]
    sent_body = json.loads(request.data.decode("utf-8"))
    sent_metrics = sent_body.get("resource_utilization_metrics", [])
    assert len(sent_metrics) == 2
    assert all("rds" in str(m.get("resource_id", "")).lower() for m in sent_metrics)


@patch("urllib.request.urlopen")
def test_detect_s3_pointer_invalid_uri_keeps_empty_metrics(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    event_data = valid_ai_event()
    event_data["body"] = {
        **event_data["body"],
        "data_source_type": "S3_POINTER",
        "s3_bucket_uri": "not-a-s3-uri",
        "resource_utilization_metrics": [],
    }

    handler.handle_request(event_data, None)

    request = mock_urlopen.call_args.args[0]
    sent_body = json.loads(request.data.decode("utf-8"))
    assert sent_body.get("resource_utilization_metrics") == []


# ---------------------------------------------------------------------------
# Request Integrity Header Tests (Section 3 blockers)
# ---------------------------------------------------------------------------

class TestRequestIntegrityHeaders:
    """Assert X-Request-Timestamp, X-Payload-SHA256, and Authorization are enforced."""

    @patch("urllib.request.urlopen")
    def test_x_request_timestamp_present_and_rfc3339(self, mock_urlopen, monkeypatch):
        """X-Request-Timestamp must be present and conform to RFC3339/ISO8601 UTC format."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        class FakeSession:
            def get_credentials(self):
                return Credentials("AKIDEXAMPLE", "SECRETEXAMPLE")

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: FakeSession())
        handler.handle_request(valid_ai_event(), None)

        request = mock_urlopen.call_args.args[0]
        headers = {k.lower(): v for k, v in request.header_items()}

        assert "x-request-timestamp" in headers, "X-Request-Timestamp header must be present"
        ts = headers["x-request-timestamp"]
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        assert pattern.match(ts), (
            f"X-Request-Timestamp '{ts}' must be RFC3339 UTC format YYYY-MM-DDTHH:MM:SSZ"
        )

    @patch("urllib.request.urlopen")
    def test_x_payload_sha256_matches_exact_outbound_bytes(self, mock_urlopen, monkeypatch):
        """X-Payload-SHA256 must exactly match the SHA256 of the bytes sent over the wire."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        class FakeSession:
            def get_credentials(self):
                return Credentials("AKIDEXAMPLE", "SECRETEXAMPLE")

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: FakeSession())
        handler.handle_request(valid_ai_event(), None)

        request = mock_urlopen.call_args.args[0]
        headers = {k.lower(): v for k, v in request.header_items()}

        assert "x-payload-sha256" in headers, "X-Payload-SHA256 header must be present"
        expected_hash = hashlib.sha256(request.data).hexdigest()
        assert headers["x-payload-sha256"] == expected_hash, (
            "X-Payload-SHA256 must match SHA256 of the exact bytes sent in the request body"
        )

    @patch("urllib.request.urlopen")
    def test_authorization_header_present_when_credentials_exist(self, mock_urlopen, monkeypatch):
        """Authorization (SigV4) header must be present when AWS credentials are available."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        class FakeSession:
            def get_credentials(self):
                return Credentials("AKIDEXAMPLE", "SECRETEXAMPLE")

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: FakeSession())
        handler.handle_request(valid_ai_event(), None)

        request = mock_urlopen.call_args.args[0]
        headers = {k.lower(): v for k, v in request.header_items()}

        assert "authorization" in headers, (
            "Authorization header (SigV4) must be present when AWS credentials are available"
        )
        assert headers["authorization"].startswith("AWS4-HMAC-SHA256"), (
            "Authorization header must use AWS SigV4 (AWS4-HMAC-SHA256) scheme"
        )


# ---------------------------------------------------------------------------
# Credential Fail-Closed Tests (ALLOW_UNSIGNED_AI_REQUESTS enforcement)
# ---------------------------------------------------------------------------

class TestCredentialFailClosed:
    """Assert vpc_alb_caller fails closed when AWS credentials are absent for AI paths."""

    def test_missing_credentials_fail_closed_on_detect(self, monkeypatch):
        """Missing AWS credentials on /v1/detect must raise ConfigMissingError (fail-closed)."""
        monkeypatch.setenv("ALLOW_UNSIGNED_AI_REQUESTS", "false")

        class NoCredSession:
            def get_credentials(self):
                return None

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: NoCredSession())

        with pytest.raises(ConfigMissingError, match="Fail-closed: refusing to send unsigned request"):
            handler.handle_request(valid_ai_event(), None)

    def test_missing_credentials_fail_closed_on_decide(self, monkeypatch):
        """Missing AWS credentials on /v1/decide must raise ConfigMissingError (fail-closed)."""
        monkeypatch.setenv("ALLOW_UNSIGNED_AI_REQUESTS", "false")

        class NoCredSession:
            def get_credentials(self):
                return None

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: NoCredSession())

        idem_key = f"{VALID_TENANT_ID}:2026-06-26:decide"
        event = valid_ai_event(
            path="/v1/decide",
            idempotency_key=idem_key,
        )
        event["body"] = {**event["body"], "idempotency_key": idem_key}

        with pytest.raises(ConfigMissingError, match="Fail-closed"):
            handler.handle_request(event, None)

    def test_missing_credentials_fail_closed_on_verify(self, monkeypatch):
        """Missing AWS credentials on /v1/verify must raise ConfigMissingError (fail-closed)."""
        monkeypatch.setenv("ALLOW_UNSIGNED_AI_REQUESTS", "false")

        class NoCredSession:
            def get_credentials(self):
                return None

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: NoCredSession())

        idem_key = f"{VALID_TENANT_ID}:2026-06-26:verify"
        event = valid_ai_event(
            path="/v1/verify",
            idempotency_key=idem_key,
        )
        event["body"] = {**event["body"], "idempotency_key": idem_key}

        with pytest.raises(ConfigMissingError, match="Fail-closed"):
            handler.handle_request(event, None)

    @patch("urllib.request.urlopen")
    def test_missing_credentials_allowed_on_health(self, mock_urlopen, monkeypatch):
        """/health must not fail-closed even when credentials are absent."""
        monkeypatch.setenv("ALLOW_UNSIGNED_AI_REQUESTS", "false")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "healthy"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        class NoCredSession:
            def get_credentials(self):
                return None

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: NoCredSession())

        resp = handler.handle_request({"path": "/health", "method": "GET"}, None)
        assert resp["status"] == "healthy"

    @patch("urllib.request.urlopen")
    def test_allow_unsigned_override_bypasses_fail_closed(self, mock_urlopen, monkeypatch):
        """ALLOW_UNSIGNED_AI_REQUESTS=true must bypass the fail-closed guard (unit test stub only)."""
        monkeypatch.setenv("ALLOW_UNSIGNED_AI_REQUESTS", "true")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        class NoCredSession:
            def get_credentials(self):
                return None

        monkeypatch.setattr(handler.botocore.session, "get_session", lambda: NoCredSession())

        result = handler.handle_request(valid_ai_event(), None)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Static IAM Policy Tests
# ---------------------------------------------------------------------------

class TestStaticIAMPolicyDefinition:
    """Static checks that confirm the vpc_alb_caller idempotency policy is defined in Terraform."""

    def _read_iam_main_tf(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        iam_main_tf = os.path.join(base_dir, "modules/iam/main.tf")
        assert os.path.exists(iam_main_tf), f"modules/iam/main.tf not found at {iam_main_tf}"
        with open(iam_main_tf, "r", encoding="utf-8") as f:
            return f.read()

    def _read_iam_outputs_tf(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        iam_outputs_tf = os.path.join(base_dir, "modules/iam/outputs.tf")
        assert os.path.exists(iam_outputs_tf), f"modules/iam/outputs.tf not found at {iam_outputs_tf}"
        with open(iam_outputs_tf, "r", encoding="utf-8") as f:
            return f.read()

    def _read_iam_variables_tf(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        iam_vars_tf = os.path.join(base_dir, "modules/iam/variables.tf")
        assert os.path.exists(iam_vars_tf), f"modules/iam/variables.tf not found at {iam_vars_tf}"
        with open(iam_vars_tf, "r", encoding="utf-8") as f:
            return f.read()

    def test_vpc_alb_caller_idempotency_policy_resource_exists(self):
        """modules/iam/main.tf must define aws_iam_role_policy.vpc_alb_caller_idempotency."""
        content = self._read_iam_main_tf()
        assert 'resource "aws_iam_role_policy" "vpc_alb_caller_idempotency"' in content, (
            "modules/iam/main.tf must define aws_iam_role_policy.vpc_alb_caller_idempotency"
        )

    def test_vpc_alb_caller_idempotency_policy_scoped_to_correct_actions(self):
        """The vpc_alb_caller idempotency policy must allow GetItem, PutItem, UpdateItem."""
        content = self._read_iam_main_tf()
        policy_block_match = re.search(
            r'data "aws_iam_policy_document" "vpc_alb_caller_idempotency".*?(?=\nresource\s|\ndata\s)',
            content, re.DOTALL
        )
        assert policy_block_match, (
            "modules/iam/main.tf must define data.aws_iam_policy_document.vpc_alb_caller_idempotency"
        )
        policy_block = policy_block_match.group(0)
        for action in ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]:
            assert action in policy_block, (
                f"vpc_alb_caller idempotency policy must include {action}"
            )

    def test_vpc_alb_caller_idempotency_policy_not_wildcard_resource(self):
        """The vpc_alb_caller idempotency policy must NOT use wildcard (*) resources."""
        content = self._read_iam_main_tf()
        policy_block_match = re.search(
            r'data "aws_iam_policy_document" "vpc_alb_caller_idempotency".*?(?=\nresource\s|\ndata\s)',
            content, re.DOTALL
        )
        assert policy_block_match, "vpc_alb_caller_idempotency policy document not found"
        policy_block = policy_block_match.group(0)
        assert 'var.ai_payload_idempotency_table_arn' in policy_block, (
            "vpc_alb_caller idempotency policy must be scoped to var.ai_payload_idempotency_table_arn"
        )
        assert 'resources = ["*"]' not in policy_block, (
            "vpc_alb_caller idempotency policy must NOT use wildcard resource"
        )

    def test_lambda_role_arns_depends_on_vpc_alb_caller_idempotency(self):
        """lambda_role_arns output must depend on aws_iam_role_policy.vpc_alb_caller_idempotency."""
        content = self._read_iam_outputs_tf()
        assert "aws_iam_role_policy.vpc_alb_caller_idempotency" in content, (
            "modules/iam/outputs.tf lambda_role_arns depends_on must include "
            "aws_iam_role_policy.vpc_alb_caller_idempotency"
        )

    def test_ai_payload_idempotency_table_arn_variable_exists(self):
        """modules/iam/variables.tf must declare the ai_payload_idempotency_table_arn variable."""
        content = self._read_iam_variables_tf()
        assert 'variable "ai_payload_idempotency_table_arn"' in content, (
            "modules/iam/variables.tf must declare variable ai_payload_idempotency_table_arn"
        )

    def test_environments_wire_ai_payload_idempotency_table_arn(self):
        """All three environment main.tf files must pass ai_payload_idempotency_table_arn to module.iam."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        for env in ["sandbox", "staging", "prod"]:
            env_main = os.path.join(base_dir, f"environments/{env}/main.tf")
            assert os.path.exists(env_main), f"environments/{env}/main.tf not found"
            with open(env_main, "r", encoding="utf-8") as f:
                content = f.read()
            assert "ai_payload_idempotency_table_arn" in content, (
                f"environments/{env}/main.tf must pass ai_payload_idempotency_table_arn to module.iam"
            )


# ---------------------------------------------------------------------------
# Idempotency hot-path tests
# ---------------------------------------------------------------------------

class TestIdempotencyHotPath:
    """Tests for DynamoDB-backed contract idempotency enforcement."""

    @pytest.fixture(autouse=True)
    def _set_table_env(self, monkeypatch):
        monkeypatch.setenv("IDEMPOTENCY_TABLE_NAME", "finops-idempotency-sandbox")

    def _make_ddb_client(self, items=None, raise_conditional_check=False, put_side_effect=None):
        """Build a minimal mock DynamoDB client."""
        ddb = MagicMock()
        ConditionalCheckFailed = type("ConditionalCheckFailedException", (Exception,), {})
        ddb.exceptions.ConditionalCheckFailedException = ConditionalCheckFailed

        if put_side_effect is not None:
            ddb.put_item.side_effect = put_side_effect
        elif raise_conditional_check:
            ddb.put_item.side_effect = ConditionalCheckFailed()
        else:
            ddb.put_item.return_value = {}

        if items is not None:
            ddb.get_item.return_value = {"Item": items}
        else:
            ddb.get_item.return_value = {"Item": None}
        return ddb

    @patch("urllib.request.urlopen")
    def test_idempotency_slot_claimed_on_first_call(self, mock_urlopen, monkeypatch):
        """First call: PutItem should claim IN_PROGRESS slot and execute HTTP request."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true, "anomalies_detected": false}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        ddb = self._make_ddb_client()
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        event = valid_ai_event()
        result = handler.handle_request(event, None)
        assert result["success"] is True
        ddb.put_item.assert_called_once()
        call_kw = ddb.put_item.call_args[1]
        assert call_kw["ConditionExpression"] == "attribute_not_exists(idempotency_key)"
        assert call_kw["Item"]["status"]["S"] == "IN_PROGRESS"
        ddb.update_item.assert_called_once()
        assert "COMPLETED" in str(ddb.update_item.call_args)

    @patch("urllib.request.urlopen")
    def test_idempotency_cache_hit_returns_without_http_call(self, mock_urlopen, monkeypatch):
        """Duplicate call with COMPLETED record returns cached response without HTTP."""
        import json as _json
        cached = {"success": True, "anomalies_detected": False, "from_cache": True}
        ddb = self._make_ddb_client(
            items={
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "COMPLETED"},
                "payload_sha256": {"S": "some-hash"},
                "response_cache": {"S": _json.dumps(cached)},
            },
            raise_conditional_check=True,
        )
        import hashlib as _hl
        event = valid_ai_event()
        body_bytes = _json.dumps(event["body"]).encode("utf-8")
        correct_hash = _hl.sha256(body_bytes).hexdigest()
        ddb.get_item.return_value = {
            "Item": {
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "COMPLETED"},
                "payload_sha256": {"S": correct_hash},
                "response_cache": {"S": _json.dumps(cached)},
            }
        }
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        result = handler.handle_request(event, None)
        assert result["from_cache"] is True
        mock_urlopen.assert_not_called()

    def test_idempotency_hash_mismatch_raises_contract_error(self, monkeypatch):
        """Hash mismatch on existing record must raise ContractMismatchError (fail-closed)."""
        import hashlib as _hl, json as _json
        event = valid_ai_event()
        body_bytes = _json.dumps(event["body"]).encode("utf-8")
        wrong_hash = "0" * 64

        ddb = self._make_ddb_client(
            items={
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "COMPLETED"},
                "payload_sha256": {"S": wrong_hash},
                "response_cache": {"S": "{}"},
            },
            raise_conditional_check=True,
        )
        ddb.get_item.return_value = {
            "Item": {
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "COMPLETED"},
                "payload_sha256": {"S": wrong_hash},
                "response_cache": {"S": "{}"},
            }
        }
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        with pytest.raises(ContractMismatchError, match="hash mismatch"):
            handler.handle_request(event, None)

    def test_idempotency_concurrent_in_progress_fails_closed(self, monkeypatch):
        """Concurrent IN_PROGRESS record must raise ServiceUnavailableError (fail-closed)."""
        import hashlib as _hl, json as _json
        event = valid_ai_event()
        body_bytes = _json.dumps(event["body"]).encode("utf-8")
        correct_hash = _hl.sha256(body_bytes).hexdigest()

        ddb = self._make_ddb_client(
            items={
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "IN_PROGRESS"},
                "payload_sha256": {"S": correct_hash},
                "response_cache": {"S": handler._NO_CACHE},
            },
            raise_conditional_check=True,
        )
        ddb.get_item.return_value = {
            "Item": {
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "IN_PROGRESS"},
                "payload_sha256": {"S": correct_hash},
                "response_cache": {"S": handler._NO_CACHE},
            }
        }
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        with pytest.raises(ServiceUnavailableError, match="IN_PROGRESS"):
            handler.handle_request(event, None)

    @patch("urllib.request.urlopen")
    def test_idempotency_http_error_marks_error_state(self, mock_urlopen, monkeypatch):
        """AI Engine HTTP error must mark idempotency record ERROR without DeleteItem.
        The handler now returns a normalized envelope for AI-path HTTP errors (not raises),
        but idempotency state must still be marked ERROR."""
        fp = MagicMock()
        fp.read.return_value = b"Service Unavailable"
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://internal-ai-alb.us-east-1.elb.amazonaws.com/v1/detect",
            503, "Service Unavailable", {}, fp
        )
        ddb = self._make_ddb_client()
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        event = valid_ai_event()
        # Handler returns normalized envelope (not raises) for AI-path HTTP errors
        result = handler.handle_request(event, None)
        assert result.get("ai_error") is True, "Should return normalized AI error envelope"
        assert result["error_code"] == "ERR_SERVICE_DOWN"

        # Idempotency record must still be marked ERROR
        ddb.update_item.assert_called_once()
        assert not ddb.delete_item.called
        assert "ERROR" in str(ddb.update_item.call_args)

    def test_idempotency_inactive_when_table_not_configured(self, monkeypatch):
        """If IDEMPOTENCY_TABLE_NAME is empty, idempotency is skipped without error."""
        monkeypatch.delenv("IDEMPOTENCY_TABLE_NAME", raising=False)
        ddb, _ = handler._get_ddb_client()
        assert ddb is None

    @patch("urllib.request.urlopen")
    def test_idempotency_slot_claimed_writes_response_body_not_response_cache(self, mock_urlopen, monkeypatch):
        """PutItem for new slot must use 'response_body' attribute, not 'response_cache'."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        ddb = self._make_ddb_client()
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        handler.handle_request(valid_ai_event(), None)

        put_call_kw = ddb.put_item.call_args[1]
        assert "response_body" in put_call_kw["Item"], (
            "initial PutItem must write 'response_body', not 'response_cache'"
        )
        assert "response_cache" not in put_call_kw["Item"], (
            "initial PutItem must not write legacy 'response_cache'"
        )

    @patch("urllib.request.urlopen")
    def test_idempotency_completed_reads_response_body_first(self, mock_urlopen, monkeypatch):
        """COMPLETED records should be returned using 'response_body' attribute."""
        import json as _json, hashlib as _hl
        cached = {"success": True, "from_body": True}
        event = valid_ai_event()
        body_bytes = _json.dumps(event["body"]).encode("utf-8")
        correct_hash = _hl.sha256(body_bytes).hexdigest()

        ddb = self._make_ddb_client(raise_conditional_check=True)
        ddb.get_item.return_value = {
            "Item": {
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "COMPLETED"},
                "payload_sha256": {"S": correct_hash},
                "response_body": {"S": _json.dumps(cached)},
            }
        }
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        result = handler.handle_request(event, None)
        assert result["from_body"] is True
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_idempotency_fallback_reads_legacy_response_cache(self, mock_urlopen, monkeypatch):
        """Legacy records with only 'response_cache' must still be served correctly."""
        import json as _json, hashlib as _hl
        cached = {"success": True, "legacy_cache": True}
        event = valid_ai_event()
        body_bytes = _json.dumps(event["body"]).encode("utf-8")
        correct_hash = _hl.sha256(body_bytes).hexdigest()

        ddb = self._make_ddb_client(raise_conditional_check=True)
        ddb.get_item.return_value = {
            "Item": {
                "idempotency_key": {"S": VALID_IDEMPOTENCY_KEY},
                "status": {"S": "COMPLETED"},
                "payload_sha256": {"S": correct_hash},
                # Only the legacy attribute – no response_body key present
                "response_cache": {"S": _json.dumps(cached)},
            }
        }
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        result = handler.handle_request(event, None)
        assert result["legacy_cache"] is True
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_idempotency_mark_completed_uses_response_body_attribute(self, mock_urlopen, monkeypatch):
        """UpdateExpression for COMPLETED idempotency must set 'response_body', not 'response_cache'."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        ddb = self._make_ddb_client()
        import boto3
        monkeypatch.setattr("boto3.client", lambda *a, **k: ddb)

        handler.handle_request(valid_ai_event(), None)

        update_call_kw = ddb.update_item.call_args[1]
        assert "response_body" in update_call_kw["UpdateExpression"], (
            "COMPLETED update must use 'response_body' in UpdateExpression"
        )
        assert "response_cache" not in update_call_kw["UpdateExpression"], (
            "COMPLETED update must not reference legacy 'response_cache'"
        )


# ---------------------------------------------------------------------------
# Static WAF Assertions
# ---------------------------------------------------------------------------

class TestStaticWAFPolicy:
    """Static checks that confirm the WAF uses CUSTOM_KEYS tenant-rate-limit rules."""

    def _read_ai_runtime_main_tf(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        tf_path = os.path.join(base_dir, "modules/ai-runtime-lambda/main.tf")
        assert os.path.exists(tf_path), f"modules/ai-runtime-lambda/main.tf not found at {tf_path}"
        with open(tf_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_waf_uses_custom_keys_aggregate_type(self):
        """WAF tenant rate rule must use aggregate_key_type = CUSTOM_KEYS."""
        content = self._read_ai_runtime_main_tf()
        assert 'aggregate_key_type    = "CUSTOM_KEYS"' in content or \
               'aggregate_key_type = "CUSTOM_KEYS"' in content, (
            "WAF TenantRateLimit rule must use aggregate_key_type = CUSTOM_KEYS"
        )

    def test_waf_uses_x_tenant_id_header_custom_key(self):
        """WAF custom key must aggregate on x-tenant-id header."""
        content = self._read_ai_runtime_main_tf()
        assert 'name = "x-tenant-id"' in content, (
            "WAF custom_keys must aggregate on x-tenant-id header"
        )

    def test_waf_tenant_rate_limit_is_100(self):
        """WAF tenant rate limit must be 100 requests per window."""
        content = self._read_ai_runtime_main_tf()
        assert "limit                 = 100" in content or "limit = 100" in content, (
            "WAF TenantRateLimit limit must be 100"
        )

    def test_waf_evaluation_window_is_60_seconds(self):
        """WAF evaluation window must be 60 seconds."""
        content = self._read_ai_runtime_main_tf()
        assert "evaluation_window_sec = 60" in content, (
            "WAF TenantRateLimit evaluation_window_sec must be 60"
        )

    def test_waf_blocks_requests_missing_tenant_id(self):
        """WAF must have a rule that blocks /v1/ requests missing X-Tenant-Id header."""
        content = self._read_ai_runtime_main_tf()
        assert "BlockMissingTenantId" in content or "x-tenant-id" in content, (
            "WAF must include a rule blocking /v1/ requests without X-Tenant-Id"
        )

    def test_ai_runtime_lambda_has_s3_pointer_read_variables(self):
        """modules/ai-runtime-lambda/variables.tf must declare S3 pointer input variables."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        vars_path = os.path.join(base_dir, "modules/ai-runtime-lambda/variables.tf")
        with open(vars_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert 'variable "ai_request_s3_pointer_bucket_arn"' in content, (
            "modules/ai-runtime-lambda/variables.tf must declare ai_request_s3_pointer_bucket_arn"
        )
        assert 'variable "ai_request_s3_pointer_prefixes"' in content, (
            "modules/ai-runtime-lambda/variables.tf must declare ai_request_s3_pointer_prefixes"
        )


def test_vpc_alb_caller_alb_base_url_scheme_validation(monkeypatch):
    """Test ALB_BASE_URL scheme validation and ALLOW_INSECURE_ALB_HTTP environment flag."""
    # 1. By default, HTTPS URL should pass validation
    assert handler.validate_alb_base_url("https://internal-ai-alb.us-east-1.elb.amazonaws.com") == "https://internal-ai-alb.us-east-1.elb.amazonaws.com"

    # 2. By default, HTTP URL should fail validation
    with pytest.raises(ConfigMissingError, match="ALB_BASE_URL must be an HTTPS URL"):
        handler.validate_alb_base_url("http://internal-ai-alb.us-east-1.elb.amazonaws.com")

    # 3. If ALLOW_INSECURE_ALB_HTTP is set to true, HTTP URL should pass validation
    monkeypatch.setenv("ALLOW_INSECURE_ALB_HTTP", "true")
    assert handler.validate_alb_base_url("http://internal-ai-alb.us-east-1.elb.amazonaws.com") == "http://internal-ai-alb.us-east-1.elb.amazonaws.com"
    # HTTPS should still pass
    assert handler.validate_alb_base_url("https://internal-ai-alb.us-east-1.elb.amazonaws.com") == "https://internal-ai-alb.us-east-1.elb.amazonaws.com"

    # 4. Invalid URLs (e.g. including a path) should still fail
    with pytest.raises(ConfigMissingError, match="ALB_BASE_URL must not include a path"):
        handler.validate_alb_base_url("http://internal-ai-alb.us-east-1.elb.amazonaws.com/v1")


def test_vpc_alb_caller_adhoc_key_validation():
    # 1. Valid adhoc key format (with suffix safe-run-id) should pass validation
    valid_key = f"{VALID_TENANT_ID}:2026-06-26:adhoc-run-12345"
    # Should not raise exception
    handler.validate_ai_context(
        path="/v1/detect",
        tenant_id=VALID_TENANT_ID,
        correlation_id=VALID_CORRELATION_ID,
        idempotency_key=valid_key,
        body={"idempotency_key": valid_key, "tenant_id": VALID_TENANT_ID, "correlation_id": VALID_CORRELATION_ID}
    )

    # 2. Cross-tenant adhoc key should raise InvalidInputError
    cross_tenant_id = "00000000-0000-0000-0000-000000000000"
    cross_key = f"{cross_tenant_id}:2026-06-26:adhoc-run-12345"
    with pytest.raises(InvalidInputError, match="idempotency_key tenant prefix must match tenant_id"):
        handler.validate_ai_context(
            path="/v1/detect",
            tenant_id=VALID_TENANT_ID,
            correlation_id=VALID_CORRELATION_ID,
            idempotency_key=cross_key,
            body={"idempotency_key": cross_key, "tenant_id": VALID_TENANT_ID, "correlation_id": VALID_CORRELATION_ID}
        )

    # 3. Malformed adhoc key (e.g. invalid date or invalid suffix format) should raise InvalidInputError
    malformed_key = f"{VALID_TENANT_ID}:2026-XX-26:adhoc-run-12345"
    with pytest.raises(InvalidInputError, match="idempotency_key must match"):
        handler.validate_ai_context(
            path="/v1/detect",
            tenant_id=VALID_TENANT_ID,
            correlation_id=VALID_CORRELATION_ID,
            idempotency_key=malformed_key,
            body={"idempotency_key": malformed_key, "tenant_id": VALID_TENANT_ID, "correlation_id": VALID_CORRELATION_ID}
        )

