import os
import re
import json
import logging
import hashlib
import urllib.request
import urllib.error
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any, Dict, Optional

import botocore.session
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth

import finops_common
from finops_common.utils import (
    ConfigMissingError,
    InvalidInputError,
    ServiceUnavailableError,
    ContractMismatchError,
    TimeoutError
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Allowed paths pattern list matching requirements
ALLOWED_PATH_PATTERNS = [
    r"^/v1/detect$",
    r"^/v1/decide$",
    r"^/v1/verify$",
    r"^/v1/status/[a-zA-Z0-9_\-]+$",
    r"^/v1/audit/[a-zA-Z0-9_\-]+$",
    r"^/v1/audit/[a-zA-Z0-9_\-]+/rollback$",
    r"^/health$"
]

def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Sanitize headers for secure logging (redacts Authorization and Security Tokens)."""
    sanitized = {}
    for k, v in headers.items():
        k_lower = k.lower()
        if k_lower in ["authorization", "x-amz-security-token"]:
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = v
    return sanitized

def validate_path(path: str) -> str:
    """Validate path against allowed path list, host overrides, and path traversal."""
    if not path:
        raise InvalidInputError("Path parameter is required")

    # Reject absolute URLs to prevent host overrides
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc:
        raise InvalidInputError("URL override or host override detected")

    path_only = parsed.path

    # Reject path traversal patterns
    if ".." in path_only or "//" in path_only:
        raise InvalidInputError("Path traversal or duplicate slashes detected")

    # Match path against allowlisted regex patterns
    is_allowed = False
    for pattern in ALLOWED_PATH_PATTERNS:
        if re.match(pattern, path_only):
            is_allowed = True
            break

    if not is_allowed:
        raise InvalidInputError(f"Disallowed path input: {path}")

    return path_only

def handle_request(event_data: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for VpcAlbCallerLambda.
    Invokes the private internal ALB for AI Engine requests using SigV4 signing.
    """
    # Sanitize and log incoming event metadata, avoiding body logging if sensitive
    sanitized_event = {k: v for k, v in event_data.items() if k != "body"}
    logger.info("Received event parameters (excluding body): %s", sanitized_event)

    # 1. Retrieve config and inputs
    alb_base_url = os.environ.get("ALB_BASE_URL", "").rstrip("/")
    if not alb_base_url:
        raise ConfigMissingError("ALB_BASE_URL environment variable is missing")

    sigv4_service = os.environ.get("SIGV4_SERVICE_NAME", "ai-engine")
    region = os.environ.get("AWS_REGION", "us-east-1")
    timeout = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "60"))

    path = event_data.get("path")
    method = event_data.get("method", "POST").upper()
    body = event_data.get("body")
    tenant_id = event_data.get("tenant_id", "")
    correlation_id = event_data.get("correlation_id", "")
    idempotency_key = event_data.get("idempotency_key", "")

    # 2. Validate path input (safeguard against path traversal, URL/host override, disallowed paths)
    validated_path = validate_path(path)
    final_url = f"{alb_base_url}{validated_path}"

    # 3. Payload processing
    body_bytes = b""
    if body is not None:
        if isinstance(body, (dict, list)):
            body_bytes = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body_bytes = body.encode("utf-8")
        elif isinstance(body, bytes):
            body_bytes = body
        else:
            raise InvalidInputError("Invalid body type")

    # Compute payload SHA256
    payload_hash = hashlib.sha256(body_bytes).hexdigest()

    # Determine dry-run mode value for headers
    dry_run_val = event_data.get("dry_run_mode") or event_data.get("force_dry_run")
    if dry_run_val is None and isinstance(body, dict):
        dry_run_val = body.get("dry_run_mode") or body.get("dry_run")
    dry_run_header = "true" if (dry_run_val is True or str(dry_run_val).lower() == "true") else "false"

    # Timestamp in ISO8601 UTC format (RFC3339 compatible)
    request_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 4. Construct HTTP headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Populate contract-required headers for endpoints except /health
    if validated_path != "/health":
        if not tenant_id:
            raise InvalidInputError("tenant_id parameter is required for AI API requests")
        if not idempotency_key:
            raise InvalidInputError("idempotency_key parameter is required for AI API requests")
        
        headers.update({
            "X-Tenant-Id": tenant_id,
            "X-Idempotency-Key": idempotency_key,
            "X-Correlation-Id": correlation_id,
            "X-Payload-SHA256": payload_hash,
            "X-Request-Timestamp": request_timestamp,
            "X-Dry-Run-Mode": dry_run_header,
        })

    # 5. Sign the request using AWS SigV4
    session = botocore.session.get_session()
    credentials = session.get_credentials()
    
    signed_headers = headers.copy()
    if credentials:
        # Use botocore's internal tools to construct and sign the request
        aws_request = AWSRequest(method=method, url=final_url, data=body_bytes, headers=headers)
        signer = SigV4Auth(credentials, sigv4_service, region)
        signer.add_auth(aws_request)
        signed_headers = dict(aws_request.headers.items())
    else:
        logger.warning("AWS Credentials not found. Skipping SigV4 signing (local/testing fallback).")

    # 6. Execute the HTTP request using urllib
    req = urllib.request.Request(
        url=final_url,
        data=body_bytes if method in ["POST", "PUT", "PATCH"] else None,
        headers=signed_headers,
        method=method
    )

    logger.info("Sending %s request to %s (headers: %s)", method, final_url, sanitize_headers(signed_headers))

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
            response_body = response.read().decode("utf-8")
            logger.info("Received response with status code %d", status_code)

            try:
                resp_json = json.loads(response_body)
                return resp_json
            except json.JSONDecodeError as jde:
                logger.error("JSON decode error on response: %s", jde)
                raise ContractMismatchError(f"Response is not valid JSON: {jde}")

    except urllib.error.HTTPError as he:
        status_code = he.code
        error_body = he.read().decode("utf-8")
        logger.error("HTTP error from ALB: status_code=%d, body=%s", status_code, error_body)
        
        # Classify and map errors to enforce fail-closed status in Step Functions
        if status_code == 429:
            raise ServiceUnavailableError(f"AI Engine rate limit exceeded (429): {error_body}")
        elif status_code in [502, 503, 504]:
            raise ServiceUnavailableError(f"AI Engine gateway/service unavailable ({status_code}): {error_body}")
        elif status_code in [401, 403]:
            raise ContractMismatchError(f"AI Engine authentication/authorization failure ({status_code}): {error_body}")
        else:
            raise ContractMismatchError(f"AI Engine returned non-2xx status ({status_code}): {error_body}")

    except (urllib.error.URLError, socket.timeout) as ue:
        # Check if it was a socket timeout
        reason = getattr(ue, 'reason', None)
        if isinstance(ue, socket.timeout) or (reason and isinstance(reason, socket.timeout)) or "timed out" in str(ue):
            logger.error("Request timed out: %s", ue)
            raise TimeoutError(f"Connection to AI Engine timed out: {ue}")
        
        logger.error("Network connection error: %s", ue)
        raise ServiceUnavailableError(f"Unable to connect to AI Engine: {ue}")
