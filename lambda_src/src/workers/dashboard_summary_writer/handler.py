"""Lambda adapter for the shared dashboard summary materializer."""

from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _integer(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _build_args() -> SimpleNamespace:
    """Translate Lambda environment variables to the existing script contract."""
    return SimpleNamespace(
        region=os.environ.get("AWS_REGION", "ap-southeast-1"),
        environment=_required("ENVIRONMENT"),
        project_name=_required("PROJECT_NAME"),
        tenant_id=_required("TENANT_ID"),
        viewer_role=os.environ.get("DASHBOARD_VIEWER_ROLE", "cdo"),
        account_id=_required("DASHBOARD_ACCOUNT_ID"),
        database=_required("GLUE_DATABASE_NAME"),
        workgroup=_required("ATHENA_WORKGROUP_NAME"),
        athena_results_bucket=_required("ATHENA_RESULTS_BUCKET_NAME"),
        lakehouse_bucket=_required("LAKEHOUSE_BUCKET_NAME"),
        dashboard_bucket=_required("DASHBOARD_DATA_BUCKET"),
        dashboard_key=os.environ.get(
            "DASHBOARD_SUMMARY_KEY", "summaries/dashboard-summary.json"
        ),
        run_state_table=_required("RUN_STATE_TABLE_NAME"),
        anomaly_table=_required("ANOMALY_TABLE_NAME"),
        audit_table=_required("AUDIT_TABLE_NAME"),
        dashboard_views_table=_required("DASHBOARD_VIEWS_TABLE_NAME"),
        cognito_user_pool_id="",
        cloudfront_distribution_id="",
        lookback_days=_integer("DASHBOARD_LOOKBACK_DAYS", 90),
        max_curated_objects=_integer("DASHBOARD_MAX_CURATED_OBJECTS", 200),
        scan_limit=_integer("DASHBOARD_SCAN_LIMIT", 100),
        athena_timeout_seconds=_integer("ATHENA_TIMEOUT_SECONDS", 90),
        dry_run=False,
        invalidate_cloudfront=False,
    )


def handle_request(event_data: dict[str, Any], context: Any) -> dict[str, Any]:
    # Packaging copies scripts/publish-dashboard-summary.py into the ZIP under
    # this import-safe module name.
    from dashboard_summary_publish import publish_summary

    summary = publish_summary(_build_args())
    detail = event_data.get("detail", {}) if isinstance(event_data, dict) else {}
    logger.info(
        "Dashboard summary published after workflow completion",
        extra={
            "execution_arn": detail.get("executionArn"),
            "state_machine_arn": detail.get("stateMachineArn"),
            "generated_at": summary.get("generated_at"),
        },
    )
    return {
        "status": "PUBLISHED",
        "generated_at": summary.get("generated_at"),
        "last_successful_run_id": summary.get("last_successful_run_id"),
    }
