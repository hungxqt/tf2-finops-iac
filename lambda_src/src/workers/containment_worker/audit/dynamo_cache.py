"""
dynamo_cache.py — Update DynamoDB Dashboard Cache and Rollback Cache.

DynamoDB is a read-cache for the Finance Dashboard — best-effort, not authoritative.
S3 Object Lock is the authoritative audit store.

If DynamoDB write fails → log warning, do NOT block containment flow.
Per 02_infra_design.md §1.4: ContLambda → Update view cache → DynamoDB Dashboard Cache
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def update_dashboard_cache(
    session: boto3.Session,
    table_name: str,
    anomaly_id: str,
    run_id: str,
    correlation_id: str,
    resource_id: str,
    account_id: str,
    environment: str,
    execution_mode_applied: str,
    status: str,
    audit_record_id: str,
    audit_record_s3_uri: str,
    severity: str = "medium",
    anomaly_type: str = "",
    explanation: str = "",
) -> bool:
    """
    Upsert containment summary into DynamoDB Dashboard Cache.

    Finance Dashboard reads from this table to display:
    - Which anomalies have been handled
    - Which execution mode was applied
    - Link to the S3 audit record

    Returns:
        True if successful, False if failed (non-blocking)
    """
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(table_name)

    item = {
        "anomaly_id": anomaly_id,
        "run_id": run_id,
        "correlation_id": correlation_id,
        "resource_id": resource_id,
        "account_id": account_id,
        "environment": environment,
        "execution_mode_applied": execution_mode_applied,
        "status": status,
        "audit_record_id": audit_record_id,
        "audit_record_s3_uri": audit_record_s3_uri,
        "severity": severity,
        "anomaly_type": anomaly_type,
        "explanation": explanation,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    try:
        table.put_item(Item=item)
        logger.info(
            "dashboard cache updated",
            extra={"anomaly_id": anomaly_id, "table": table_name, "status": status},
        )
        return True

    except ClientError as exc:
        # Best-effort — do not block containment
        logger.warning(
            "dashboard cache update failed (non-blocking)",
            extra={"anomaly_id": anomaly_id, "table": table_name, "error": str(exc)},
        )
        return False


def cache_rollback_payload(
    session: boto3.Session,
    rollback_cache_table: str,
    anomaly_id: str,
    correlation_id: str,
    rollback_payload: dict[str, Any],
    ttl_days: int = 90,
) -> bool:
    """
    Cache rollback_payload.boto3_equivalent into finops-rollback-cache.

    Called IMMEDIATELY after receiving DecideResponse — before executing action.
    Ensures rollback independence from AI Engine availability.

    Per deployment-contract.md §CDO Rollback Cache:
    TTL = 90 days (matches audit retention)

    Returns:
        True if successful, False if failed (non-blocking)
    """
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(rollback_cache_table)

    ttl_epoch = int(time.time()) + (ttl_days * 86400)

    item = {
        "anomaly_id": anomaly_id,
        "correlation_id": correlation_id,
        "boto3_equivalent": rollback_payload,
        "cached_at": datetime.now(tz=timezone.utc).isoformat(),
        "ttl_epoch": ttl_epoch,
    }

    try:
        table.put_item(Item=item)
        logger.info(
            "rollback payload cached",
            extra={
                "anomaly_id": anomaly_id,
                "table": rollback_cache_table,
                "ttl_days": ttl_days,
            },
        )
        return True

    except ClientError as exc:
        logger.warning(
            "rollback cache write failed (non-blocking)",
            extra={
                "anomaly_id": anomaly_id,
                "table": rollback_cache_table,
                "error": str(exc),
            },
        )
        return False
