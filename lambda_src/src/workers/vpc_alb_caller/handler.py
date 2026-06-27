import os
import re
import json
import time
import logging
import hashlib
import urllib.request
import urllib.error
import socket
import uuid
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

AI_PAYLOAD_PATHS = {"/v1/detect", "/v1/decide", "/v1/verify"}
AI_IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^([a-fA-F0-9-]{36}):([0-9]{4}-[0-9]{2}-[0-9]{2}):(daily|adhoc|decide|verify)$"
)

# TTL for idempotency records: 24 hours in seconds
_IDEMPOTENCY_TTL_SECONDS = 24 * 3600

# Sentinel string that marks IN_PROGRESS entries where response_body is not yet set.
# Must not be valid JSON so it can never collide with a real API response.
_NO_CACHE = "__NO_CACHE__"


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


def validate_alb_base_url(alb_base_url: str) -> str:
    parsed = urlparse(alb_base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigMissingError("ALB_BASE_URL must be an HTTPS URL with a host")
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        raise ConfigMissingError("ALB_BASE_URL must not include a path, query, or fragment")
    return f"{parsed.scheme}://{parsed.netloc}"


def validate_uuid(value: str, field_name: str) -> None:
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise InvalidInputError(f"{field_name} must be a UUID") from exc


def validate_ai_context(path: str, tenant_id: str, correlation_id: str, idempotency_key: str, body: Any) -> None:
    if path not in AI_PAYLOAD_PATHS:
        return

    validate_uuid(tenant_id, "tenant_id")
    validate_uuid(correlation_id, "correlation_id")

    match = AI_IDEMPOTENCY_KEY_PATTERN.match(idempotency_key)
    if not match:
        raise InvalidInputError(
            "idempotency_key must match tenant_id:YYYY-MM-DD:daily|adhoc|decide|verify"
        )
    idempotency_tenant = match.group(1)
    validate_uuid(idempotency_tenant, "idempotency_key tenant prefix")
    if idempotency_tenant.lower() != tenant_id.lower():
        raise InvalidInputError("idempotency_key tenant prefix must match tenant_id")

    if isinstance(body, dict):
        for key, expected in {
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
        }.items():
            if key in body and str(body[key]) != str(expected):
                raise InvalidInputError(f"body.{key} must match top-level {key}")


# ---------------------------------------------------------------------------
# Idempotency helpers (DynamoDB hot path)
# ---------------------------------------------------------------------------

def _get_ddb_client():
    """Return a boto3 DynamoDB client, or None if not configured."""
    table_name = os.environ.get("IDEMPOTENCY_TABLE_NAME", "")
    if not table_name:
        return None, ""
    try:
        import boto3
        client = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        return client, table_name
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to initialise DynamoDB client for idempotency: %s", exc)
        return None, ""


def _idempotency_check_or_claim(
    ddb, table_name: str, idempotency_key: str, payload_sha256: str
) -> Optional[Dict[str, Any]]:
    """
    Attempt to claim an idempotency slot for this (idempotency_key, payload_sha256) pair.

    Returns:
        None  – slot claimed successfully (caller must execute the AI request).
        dict  – a cached response dict from a prior completed call with the same hash.

    Raises:
        ContractMismatchError – hash mismatch on an existing IN_PROGRESS or COMPLETED record.
        ServiceUnavailableError – concurrent IN_PROGRESS detected for same key.
    """
    now = int(time.time())
    ttl_expiry = now + _IDEMPOTENCY_TTL_SECONDS
    created_at = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Try conditional PutItem to claim the slot (only if item does not exist).
    try:
        ddb.put_item(
            TableName=table_name,
            Item={
                "idempotency_key": {"S": idempotency_key},
                "status": {"S": "IN_PROGRESS"},
                "payload_sha256": {"S": payload_sha256},
                "created_at": {"S": created_at},
                "ttl_expiry": {"N": str(ttl_expiry)},
                "response_body": {"S": _NO_CACHE},
            },
            ConditionExpression="attribute_not_exists(idempotency_key)",
        )
        logger.info("Idempotency slot claimed for key=%s", idempotency_key)
        return None  # slot acquired; caller proceeds with HTTP request

    except ddb.exceptions.ConditionalCheckFailedException:
        pass  # slot already exists – read it

    # Read the existing record.
    resp = ddb.get_item(
        TableName=table_name,
        Key={"idempotency_key": {"S": idempotency_key}},
        ConsistentRead=True,
    )
    item = resp.get("Item")
    if not item:
        # Race: item expired between put and get – treat as fresh slot.
        logger.warning("Idempotency item disappeared after conflict; proceeding as fresh call.")
        return None

    existing_hash = item.get("payload_sha256", {}).get("S", "")
    existing_status = item.get("status", {}).get("S", "")
    # Read response_body first (new attribute name); fall back to legacy response_cache
    # for records written by older Lambda deployments within their 24-hour TTL window.
    response_body_raw = (
        item.get("response_body", {}).get("S")
        or item.get("response_cache", {}).get("S", _NO_CACHE)
    )

    if existing_hash and existing_hash != payload_sha256:
        logger.error(
            "Idempotency hash mismatch for key=%s: stored=%s, incoming=%s",
            idempotency_key, existing_hash, payload_sha256,
        )
        raise ContractMismatchError(
            f"Idempotency key conflict: payload hash mismatch for key {idempotency_key!r}. "
            "Fail-closed to prevent cross-payload collision."
        )

    if existing_status == "IN_PROGRESS":
        logger.warning("Concurrent IN_PROGRESS detected for key=%s; failing closed.", idempotency_key)
        raise ServiceUnavailableError(
            f"Idempotency key {idempotency_key!r} is currently IN_PROGRESS. "
            "Concurrent call rejected to preserve idempotency."
        )

    if existing_status == "COMPLETED" and response_body_raw and response_body_raw != _NO_CACHE:
        logger.info("Returning cached COMPLETED response for key=%s", idempotency_key)
        try:
            return json.loads(response_body_raw)
        except json.JSONDecodeError:
            logger.warning("Cached response for key=%s is not valid JSON; re-executing.", idempotency_key)
            return None

    # ERROR or unknown state – re-execute (fail-safe: don't block recovery).
    logger.info("Idempotency record for key=%s has status=%s; re-executing.", idempotency_key, existing_status)
    return None


def _idempotency_mark_completed(
    ddb, table_name: str, idempotency_key: str, response: Dict[str, Any]
) -> None:
    """Update the idempotency record to COMPLETED with a sanitized response cache."""
    try:
        # Sanitize: keep only safe scalar fields from AI response (avoid leaking PII-like data).
        safe_fields = {k: v for k, v in response.items() if k not in ("data", "raw_payload")}
        cache_str = json.dumps(safe_fields)
        ddb.update_item(
            TableName=table_name,
            Key={"idempotency_key": {"S": idempotency_key}},
            UpdateExpression="SET #s = :s, response_body = :r",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": {"S": "COMPLETED"},
                ":r": {"S": cache_str},
            },
        )
    except Exception as exc:  # pragma: no cover – best-effort
        logger.warning("Failed to mark idempotency COMPLETED for key=%s: %s", idempotency_key, exc)


def _idempotency_mark_error(
    ddb, table_name: str, idempotency_key: str, error_msg: str
) -> None:
    """Update the idempotency record to ERROR with a sanitized error cache."""
    try:
        error_cache = json.dumps({"error": error_msg[:500]})  # bounded, no stack traces
        ddb.update_item(
            TableName=table_name,
            Key={"idempotency_key": {"S": idempotency_key}},
            UpdateExpression="SET #s = :s, response_body = :r",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": {"S": "ERROR"},
                ":r": {"S": error_cache},
            },
        )
    except Exception as exc:  # pragma: no cover – best-effort
        logger.warning("Failed to mark idempotency ERROR for key=%s: %s", idempotency_key, exc)


def handle_request(event_data: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for VpcAlbCallerLambda.
    Invokes the private internal ALB for AI Engine requests using SigV4 signing.
    Enforces contract idempotency for /v1/detect, /v1/decide, and /v1/verify.
    """
    # Sanitize and log incoming event metadata, avoiding body logging if sensitive
    sanitized_event = {k: v for k, v in event_data.items() if k != "body"}
    logger.info("Received event parameters (excluding body): %s", sanitized_event)

    # 1. Retrieve config and inputs
    alb_base_url = os.environ.get("ALB_BASE_URL", "").rstrip("/")
    if not alb_base_url:
        raise ConfigMissingError("ALB_BASE_URL environment variable is missing")
    alb_base_url = validate_alb_base_url(alb_base_url)

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
    dry_run_val = event_data.get("dry_run_mode")
    if dry_run_val is None:
        dry_run_val = event_data.get("force_dry_run")
    if dry_run_val is None and isinstance(body, dict):
        dry_run_val = body.get("dry_run_mode")
        if dry_run_val is None:
            dry_run_val = body.get("dry_run")
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
        if not correlation_id:
            raise InvalidInputError("correlation_id parameter is required for AI API requests")
        validate_ai_context(validated_path, tenant_id, correlation_id, idempotency_key, body)

        headers.update({
            "X-Tenant-Id": tenant_id,
            "X-Idempotency-Key": idempotency_key,
            "X-Correlation-Id": correlation_id,
            "X-Payload-SHA256": payload_hash,
            "X-Request-Timestamp": request_timestamp,
            "X-Dry-Run-Mode": dry_run_header,
        })

    # 5. Contract idempotency enforcement for AI payload paths
    ddb, idempotency_table = _get_ddb_client()
    idempotency_active = (
        ddb is not None
        and idempotency_table
        and validated_path in AI_PAYLOAD_PATHS
        and idempotency_key
    )

    if idempotency_active:
        cached = _idempotency_check_or_claim(ddb, idempotency_table, idempotency_key, payload_hash)
        if cached is not None:
            logger.info("Idempotency cache hit for key=%s; returning cached response.", idempotency_key)
            return cached

    # 6. Sign the request using AWS SigV4
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
        # Fail closed: missing credentials on AI payload paths is a security violation.
        # Only allow unsigned requests when ALLOW_UNSIGNED_AI_REQUESTS=true is explicitly set
        # (e.g. unit tests / local stubs – never set this in Terraform environment variables).
        allow_unsigned = os.environ.get("ALLOW_UNSIGNED_AI_REQUESTS", "false").lower() == "true"
        if validated_path in AI_PAYLOAD_PATHS and not allow_unsigned:
            raise ConfigMissingError(
                "AWS credentials not available for SigV4 signing and ALLOW_UNSIGNED_AI_REQUESTS is not set. "
                "Fail-closed: refusing to send unsigned request to AI Engine path "
                f"'{validated_path}'. Check Lambda execution role and VPC endpoint configuration."
            )
        logger.warning(
            "AWS credentials not found. Proceeding without SigV4 signing "
            "(ALLOW_UNSIGNED_AI_REQUESTS=true or non-AI-payload path)."
        )


    # 7. Execute the HTTP request using urllib
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
            except json.JSONDecodeError as jde:
                logger.error("JSON decode error on response: %s", jde)
                if idempotency_active:
                    _idempotency_mark_error(ddb, idempotency_table, idempotency_key, str(jde))
                raise ContractMismatchError(f"Response is not valid JSON: {jde}")

            if idempotency_active:
                _idempotency_mark_completed(ddb, idempotency_table, idempotency_key, resp_json)

            return resp_json

    except urllib.error.HTTPError as he:
        status_code = he.code
        error_body = he.read().decode("utf-8")
        logger.error("HTTP error from ALB: status_code=%d, body=%s", status_code, error_body)

        error_msg = f"status={status_code}"
        if idempotency_active:
            _idempotency_mark_error(ddb, idempotency_table, idempotency_key, error_msg)

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
            if idempotency_active:
                _idempotency_mark_error(ddb, idempotency_table, idempotency_key, "timeout")
            raise TimeoutError(f"Connection to AI Engine timed out: {ue}")

        logger.error("Network connection error: %s", ue)
        if idempotency_active:
            _idempotency_mark_error(ddb, idempotency_table, idempotency_key, str(ue)[:200])
        raise ServiceUnavailableError(f"Unable to connect to AI Engine: {ue}")
