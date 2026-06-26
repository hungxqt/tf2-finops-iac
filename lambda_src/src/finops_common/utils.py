import os
import re
import uuid
from datetime import datetime, timezone
from typing import Tuple

class ConfigMissingError(Exception):
    pass

class InvalidInputError(Exception):
    pass

class ServiceUnavailableError(Exception):
    pass

class ContractMismatchError(Exception):
    pass

class TimeoutError(Exception):
    pass

class UnsafeActionError(Exception):
    pass

def parse_s3_uri(uri: str) -> Tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"invalid S3 URI: {uri}")
    trimmed = uri[5:]
    parts = trimmed.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"invalid S3 URI: {uri}")
    return parts[0], parts[1]

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def iso_utc_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")

def deterministic_tenant_id(account_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, account_id or "tenant-default"))

def idempotency_key(tenant_id: str, billing_period_date: str, batch_type: str) -> str:
    return f"{tenant_id}:{billing_period_date}:{batch_type}"

def redact_sensitive_info(message: str) -> str:
    # Redact credentials/secrets/tokens patterns
    re_secret_key = re.compile(
        r'(?i)(aws_secret_access_key|secret_key|secret|password|auth|token|key|api_key|webhook_url)["\'\s:=]+[a-zA-Z0-9/\+=_\-]{16,}'
    )

    def replace_match(match):
        m = match.group(0)
        # Find prefix index like : = " '
        idx = -1
        for char in [':', '=', '"', "'"]:
            pos = m.find(char)
            if pos != -1 and (idx == -1 or pos < idx):
                idx = pos
        if idx != -1:
            return m[:idx+1] + " [REDACTED]"
        return "[REDACTED]"

    redacted = re_secret_key.sub(replace_match, message)

    # Redact full secrets manager ARNs
    re_arn_secrets = re.compile(
        r'arn:aws:secretsmanager:[a-z0-9-]+:\d{12}:secret:[a-zA-Z0-9/_+=.@-]+'
    )
    redacted = re_arn_secrets.sub("[REDACTED_SECRET_ARN]", redacted)

    return redacted

def parse_date(date_str: str) -> datetime:
    if not date_str:
        return utc_now()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"invalid date format: {date_str}, expected YYYY-MM-DD") from e

def config_value(key: str, fallback: str) -> str:
    return os.environ.get(key, fallback)