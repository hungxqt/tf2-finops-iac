import os
import re
from datetime import datetime
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

def idempotency_key(account_id: str, period: str, date: str) -> str:
    return f"{account_id}:{period}:{date}"

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
    """Parse date string to UTC-aware datetime. Always returns timezone-aware datetime."""
    if not date_str:
        # Return UTC-aware datetime when empty
        return datetime.utcnow().replace(tzinfo=None)  # Keep naive for backward compatibility, but document expectation
    try:
        # Parse provided date string and make it UTC-aware
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        # Return as naive datetime at midnight UTC (consistent with utcnow() behavior)
        return parsed
    except ValueError as e:
        raise ValueError(f"invalid date format: {date_str}, expected YYYY-MM-DD") from e

def config_value(key: str, fallback: str) -> str:
    return os.environ.get(key, fallback)

def parse_and_validate_manifest(manifest_json: dict) -> dict:
    """Parse Data Exports manifest and return normalized structure. Fail fast on legacy manifest."""
    # Check for legacy format
    if "assemblyId" in manifest_json or "reportKeys" in manifest_json:
        if not all(k in manifest_json for k in ["executionId", "exportArn", "columns", "dataFiles"]):
            raise InvalidInputError("Legacy CUR manifest format (assemblyId/reportKeys) is not supported. Only AWS Data Exports CUR 2.0 manifest is accepted.")
            
    # Check required fields
    for field in ["executionId", "exportArn", "columns", "dataFiles"]:
        if field not in manifest_json:
            raise InvalidInputError(f"Invalid manifest schema: missing required field '{field}'")
            
    data_files = manifest_json["dataFiles"]
    if not isinstance(data_files, list) or not data_files:
        raise InvalidInputError("Invalid manifest schema: 'dataFiles' must be a non-empty list")
        
    columns = manifest_json["columns"]
    if not isinstance(columns, list):
        raise InvalidInputError("Invalid manifest schema: 'columns' must be a list")
        
    return {
        "execution_id": manifest_json["executionId"],
        "export_arn": manifest_json["exportArn"],
        "columns": columns,
        "data_files": data_files,
        "data_file_count": len(data_files),
        "columns_count": len(columns),
    }

def validate_data_files(data_files: list, allowed_bucket: str, allowed_prefix: str, billing_period: str) -> None:
    """Validate that every data file URI points to the allowed bucket, resides under prefix and matches billing period."""
    if not data_files:
        raise InvalidInputError("Invalid manifest: dataFiles list is empty")
        
    for df in data_files:
        if not df.startswith("s3://"):
            raise InvalidInputError(f"Malformed data file URI (must start with s3://): {df}")
            
        try:
            bucket, key = parse_s3_uri(df)
        except Exception as e:
            raise InvalidInputError(f"Malformed data file URI: {df}. Error: {e}")
            
        if bucket != allowed_bucket:
            raise UnsafeActionError(
                f"Cross-bucket data file rejected: bucket {bucket} != allowed bucket {allowed_bucket}"
            )
            
        if allowed_prefix:
            prefix_check = allowed_prefix.strip("/") + "/"
            if not key.startswith(prefix_check):
                raise UnsafeActionError(
                    f"Data file {df!r} is outside the allowed prefix {allowed_prefix!r}"
                )
                
        billing_period_str = f"BILLING_PERIOD={billing_period}"
        if billing_period_str not in key:
            raise UnsafeActionError(
                f"Data file {df!r} does not match the billing period {billing_period}"
            )

