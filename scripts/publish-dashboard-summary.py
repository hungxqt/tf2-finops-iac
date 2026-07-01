#!/usr/bin/env python3
"""Build and publish the static dashboard summary JSON.

The CloudFront dashboard is intentionally static: it reads one precomputed
JSON document from the dashboard data bucket. This script materializes that
document from the live lakehouse/Athena and DynamoDB state, then uploads it to
S3.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import time
from collections import defaultdict
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError


DEFAULT_REGION = "ap-southeast-1"
DEFAULT_ENVIRONMENT = "sandbox"
DEFAULT_PROJECT = "tf2-finops"
DEFAULT_DATABASE = "tf2-finops_sandbox_database"
DEFAULT_WORKGROUP = "tf2-finops-sandbox-workgroup"
DEFAULT_ATHENA_RESULTS_BUCKET = "tf2-finops-sandbox-athena-results"
DEFAULT_LAKEHOUSE_BUCKET = "tf2-finops-sandbox-lakehouse-bucket"
DEFAULT_DASHBOARD_BUCKET = "tf2-finops-sandbox-dashboard-data"
DEFAULT_DASHBOARD_KEY = "summaries/dashboard-summary.json"
DEFAULT_TENANT_ID = "tf2-finops-sandbox"


def get_caller_account_id(region: str = DEFAULT_REGION) -> str:
    """Resolve the current AWS account ID dynamically via STS."""
    try:
        sts = boto3.client("sts", region_name=region)
        return sts.get_caller_identity()["Account"]
    except Exception as exc:
        raise RuntimeError(f"Could not resolve account ID via STS: {exc}") from exc


ddb_deserializer = TypeDeserializer()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def decimal_default(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def clean_number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_date(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return text[:10]


def run_athena_query(
    athena: Any,
    *,
    database: str,
    workgroup: str,
    output_bucket: str,
    query: str,
    timeout_seconds: int,
) -> list[dict[str, str]]:
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": f"s3://{output_bucket}/dashboard-summary/"},
        WorkGroup=workgroup,
    )
    query_id = response["QueryExecutionId"]
    deadline = time.time() + timeout_seconds

    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            break
        if state in {"FAILED", "CANCELLED"}:
            reason = status.get("StateChangeReason", "Unknown")
            raise RuntimeError(f"Athena query {query_id} {state}: {reason}")
        if time.time() >= deadline:
            raise TimeoutError(f"Athena query {query_id} timed out after {timeout_seconds}s")
        time.sleep(1)

    rows: list[dict[str, str]] = []
    headers: list[str] = []
    next_token = None
    while True:
        kwargs = {"QueryExecutionId": query_id}
        if next_token:
            kwargs["NextToken"] = next_token
        page = athena.get_query_results(**kwargs)
        raw_rows = page["ResultSet"]["Rows"]
        start = 0
        if not headers and raw_rows:
            headers = [cell.get("VarCharValue", "") for cell in raw_rows[0].get("Data", [])]
            start = 1
        for row in raw_rows[start:]:
            values = [cell.get("VarCharValue", "") for cell in row.get("Data", [])]
            rows.append({headers[idx]: value for idx, value in enumerate(values) if idx < len(headers)})
        next_token = page.get("NextToken")
        if not next_token:
            return rows


def athena_or_empty(label: str, fn: Any) -> list[dict[str, str]]:
    try:
        return fn()
    except Exception as exc:
        print(f"[warn] {label} query failed: {exc}")
        return []


def build_spend_trend(rows: list[dict[str, str]]) -> list[list[Any]]:
    ordered = []
    values = [clean_number(row.get("actual_cost")) for row in rows]
    for idx, row in enumerate(rows):
        day = parse_date(row.get("day"))
        actual = clean_number(row.get("actual_cost"))
        prior = values[max(0, idx - 7):idx]
        if prior:
            baseline = sum(prior) / len(prior)
        else:
            baseline = actual
        is_anomaly = bool(baseline > 0 and actual > baseline * 1.5 and actual - baseline >= 1.0)
        ordered.append([day, round(actual, 6), round(baseline, 6), is_anomaly])
    return ordered


def build_impacted(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    impacted = []
    for row in rows:
        name = row.get("name") or "unknown"
        item_type = row.get("type") or "Service"
        total = clean_number(row.get("spend_delta_usd_per_day"))
        owner_status = row.get("owner_tag_status") or "unknown"
        impacted.append({
            "name": name,
            "type": item_type,
            "spend_delta_usd_per_day": round(total, 6),
            "owner_tag_status": owner_status,
        })
    return impacted


def _read_parquet_bytes(body: bytes) -> list[dict[str, Any]]:
    """Read a Parquet file from raw bytes using pyarrow, returns list of dicts."""
    try:
        import io
        import pyarrow.parquet as pq
        table = pq.read_table(io.BytesIO(body))
        return table.to_pylist()
    except ImportError:
        return []
    except Exception as exc:
        print(f"[warn] pyarrow failed to read parquet: {exc}")
        return []


def load_curated_cost_rows_from_s3(
    s3: Any,
    *,
    lakehouse_bucket: str,
    account_id: str,
    max_objects: int,
) -> list[dict[str, Any]]:
    """Read curated cost rows directly from S3.

    Scans ALL account_id= partition prefixes (not just the payer account) so
    that data written under synthetic or legacy account IDs is also included.
    Supports both real Parquet (via pyarrow) and JSON fallback formats.
    """
    # Discover all account_id= partition prefixes under cost/curated/
    paginator = s3.get_paginator("list_objects_v2")
    prefixes_to_scan: list[str] = []
    try:
        resp = s3.list_objects_v2(Bucket=lakehouse_bucket, Prefix="cost/curated/", Delimiter="/")
        for cp in resp.get("CommonPrefixes", []):
            prefixes_to_scan.append(cp["Prefix"])
    except Exception:
        pass
    # Always include the explicit payer account prefix as fallback
    explicit = f"cost/curated/account_id={account_id}/"
    if not prefixes_to_scan:
        prefixes_to_scan = [explicit]

    objects: list[dict[str, Any]] = []
    for prefix in prefixes_to_scan:
        for page in paginator.paginate(Bucket=lakehouse_bucket, Prefix=prefix):
            objects.extend(page.get("Contents", []))

    objects.sort(key=lambda obj: obj.get("LastModified", dt.datetime.min.replace(tzinfo=dt.timezone.utc)), reverse=True)

    rows: list[dict[str, Any]] = []
    for obj in objects[:max_objects]:
        key = obj["Key"]
        try:
            body = s3.get_object(Bucket=lakehouse_bucket, Key=key)["Body"].read()
        except Exception as exc:
            print(f"[warn] failed reading s3://{lakehouse_bucket}/{key}: {exc}")
            continue
        if body.startswith(b"PAR1"):
            parquet_rows = _read_parquet_bytes(body)
            if parquet_rows:
                rows.extend(parquet_rows)
            else:
                print(f"[warn] skipping unreadable Parquet (pyarrow not available or failed): s3://{lakehouse_bucket}/{key}")
            continue
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            print(f"[warn] skipping non-JSON curated object s3://{lakehouse_bucket}/{key}: {exc}")
            continue
        if isinstance(payload, list):
            rows.extend([row for row in payload if isinstance(row, dict)])
        elif isinstance(payload, dict):
            candidate = payload.get("records") or payload.get("items") or payload.get("data")
            if isinstance(candidate, list):
                rows.extend([row for row in candidate if isinstance(row, dict)])
    return rows


def build_spend_rows_from_cost_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    daily: dict[str, float] = defaultdict(float)
    for record in records:
        day = parse_date(record.get("timestamp") or record.get("date") or record.get("line_item_usage_start_date"))
        if not day:
            continue
        daily[day] += clean_number(
            record.get("unblended_cost")
            if record.get("unblended_cost") is not None
            else record.get("cost")
        )
    return [{"day": day, "actual_cost": str(total)} for day, total in sorted(daily.items())]


def build_impacted_rows_from_cost_records(records: list[dict[str, Any]], lookback_days: int) -> list[dict[str, str]]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    owner_status: dict[tuple[str, str], str] = {}
    for record in records:
        cost = clean_number(
            record.get("unblended_cost")
            if record.get("unblended_cost") is not None
            else record.get("cost")
        )
        owner = str(record.get("owner") or record.get("resource_tags_user_owner") or "untagged")
        status = "missing owner" if owner == "untagged" else "valid"
        service = str(record.get("service") or record.get("service_code") or "unknown")
        squad = str(record.get("squad") or record.get("team") or "unassigned")
        for key in (("Service", service), ("Squad", squad)):
            totals[key] += cost
            if owner_status.get(key) != "missing owner":
                owner_status[key] = status

    rows = []
    divisor = max(lookback_days, 1)
    for (item_type, name), total in totals.items():
        rows.append({
            "name": name,
            "type": item_type,
            "spend_delta_usd_per_day": str(total / divisor),
            "owner_tag_status": owner_status.get((item_type, name), "unknown"),
        })
    rows.sort(key=lambda row: clean_number(row["spend_delta_usd_per_day"]), reverse=True)
    return rows[:20]


def deserialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: ddb_deserializer.deserialize(value) for key, value in item.items()}


def scan_table(dynamodb: Any, table_name: str, limit: int) -> list[dict[str, Any]]:
    try:
        response = dynamodb.scan(TableName=table_name, Limit=limit)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            print(f"[warn] DynamoDB table not found: {table_name}")
            return []
        raise
    return [deserialize_item(item) for item in response.get("Items", [])]


def build_anomalies(anomaly_items: list[dict[str, Any]], dashboard_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in anomaly_items + dashboard_items:
        anomaly_id = str(item.get("anomaly_id") or item.get("view_id") or "")
        if not anomaly_id:
            continue
        merged.setdefault(anomaly_id, {}).update(item)

    anomalies = []
    for anomaly_id, item in merged.items():
        cost_delta = clean_number(
            item.get("cost_delta_usd_per_day")
            or item.get("spend_delta_usd_per_day")
            or item.get("cost_delta")
        )
        anomalies.append({
            "anomaly_id": anomaly_id,
            "severity": str(item.get("severity") or "INFO").upper(),
            "account_id": str(item.get("account_id") or args.account_id),
            "account_name": str(item.get("account_name") or item.get("environment") or "Unknown account"),
            "service": str(item.get("service") or item.get("service_code") or item.get("anomaly_type") or "unknown"),
            "squad": str(item.get("squad") or item.get("owner") or "unassigned"),
            "owner_tag_status": str(item.get("owner_tag_status") or "unknown"),
            "confidence_score": clean_number(item.get("confidence_score") or item.get("confidence"), 0.0),
            "data_confidence": str(item.get("data_confidence") or "UNKNOWN"),
            "evidence_window_start": str(item.get("evidence_window_start") or item.get("created_at") or ""),
            "evidence_window_end": str(item.get("evidence_window_end") or item.get("updated_at") or ""),
            "cost_delta_usd_per_day": round(cost_delta, 6),
            "explanation": str(item.get("explanation") or "No model explanation was published."),
            "business_context": item.get("business_context") if isinstance(item.get("business_context"), dict) else {},
            "telemetry_quality": item.get("telemetry_quality") if isinstance(item.get("telemetry_quality"), dict) else {},
            "workflow_status": str(item.get("workflow_status") or item.get("status") or "published"),
        })
    anomalies.sort(key=lambda row: row["cost_delta_usd_per_day"], reverse=True)
    return anomalies[:50]


def build_containment(audit_items: list[dict[str, Any]], dashboard_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = audit_items + dashboard_items
    containment = []
    for item in items:
        audit_id = str(item.get("audit_id") or item.get("audit_record_id") or item.get("anomaly_id") or "")
        if not audit_id:
            continue
        timestamp = str(item.get("timestamp") or item.get("updated_at") or "")
        action = str(item.get("requested_action") or item.get("action_type") or item.get("execution_mode_applied") or "review")
        status = str(item.get("status") or "UNKNOWN")
        containment.append({
            "audit_id": audit_id,
            "resource_id": str(item.get("resource_id") or "N/A"),
            "account_id": str(item.get("account_id") or args.account_id),
            "squad": str(item.get("squad") or item.get("owner") or "unassigned"),
            "action_type": action,
            "execution_mode": str(item.get("execution_mode") or item.get("execution_mode_applied") or "dry-run"),
            "status": status,
            "containment_locked": bool(item.get("containment_locked") or False),
            "error_budget_remaining_pct": clean_number(item.get("error_budget_remaining_pct"), 100.0),
            "audit_record_uri": str(item.get("audit_record_uri") or item.get("audit_record_s3_uri") or item.get("retention_location") or ""),
            "actions_log": [{
                "timestamp": timestamp,
                "action": action,
                "status": status,
                "actor": str(item.get("actor") or "tf2-finops-orchestrator"),
            }],
        })
    containment.sort(key=lambda row: row["actions_log"][0].get("timestamp") or "", reverse=True)
    return containment[:50]


def build_audit_diffs(containment: list[dict[str, Any]], audit_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("audit_id") or item.get("audit_record_id") or item.get("anomaly_id")): item for item in audit_items}
    diffs = []
    for item in containment:
        audit_id = item["audit_id"]
        source = by_id.get(audit_id, {})
        before = source.get("before")
        after = source.get("after")
        if not isinstance(before, list):
            before = [str(source.get("before_state") or "anomaly_detected")]
        if not isinstance(after, list):
            after = [str(source.get("after_state") or source.get("applied_after_state") or item["status"])]
        diffs.append({
            "audit_id": audit_id,
            "before": [str(value) for value in before],
            "after": [str(value) for value in after],
            "correlation_id": str(source.get("correlation_id") or "unknown"),
            "idempotency_key": str(source.get("idempotency_key") or "unknown"),
        })
    return diffs[:50]


def build_alert_previews(anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previews = []
    for anomaly in anomalies[:5]:
        summary = (
            f"{anomaly['severity']} cost signal for {anomaly['service']} "
            f"delta ${anomaly['cost_delta_usd_per_day']:.2f}/day."
        )
        previews.append({
            "audience": "Finance",
            "channel": "SNS",
            "anomaly_id": anomaly["anomaly_id"],
            "summary": summary,
            "data_confidence": anomaly["data_confidence"],
            "action_visibility": "Read-only",
            "audit_link_label": "Audit record",
        })
        previews.append({
            "audience": "Engineering",
            "channel": "SNS",
            "anomaly_id": anomaly["anomaly_id"],
            "summary": f"Review {anomaly['account_id']} / {anomaly['squad']} for {anomaly['service']} spend.",
            "data_confidence": anomaly["data_confidence"],
            "action_visibility": "Read-only",
            "audit_link_label": "Audit record",
        })
    return previews


def latest_run_id(run_state_items: list[dict[str, Any]]) -> str:
    if not run_state_items:
        return "unknown"
    sorted_items = sorted(
        run_state_items,
        key=lambda item: str(item.get("updated_at") or item.get("created_at") or item.get("execution_date") or ""),
        reverse=True,
    )
    return str(sorted_items[0].get("run_id") or sorted_items[0].get("idempotency_key") or "unknown")


def publish_summary(args: argparse.Namespace) -> dict[str, Any]:
    session = boto3.Session(region_name=args.region)
    athena = session.client("athena")
    dynamodb = session.client("dynamodb")
    s3 = session.client("s3")

    spend_rows = athena_or_empty(
        "spend_trend",
        lambda: run_athena_query(
            athena,
            database=args.database,
            workgroup=args.workgroup,
            output_bucket=args.athena_results_bucket,
            timeout_seconds=args.athena_timeout_seconds,
            query=f"""
SELECT
  substr(timestamp, 1, 10) AS day,
  sum(coalesce(unblended_cost, cost, 0)) AS actual_cost
FROM "{args.database}"."cur_data"
WHERE account_id = '{args.account_id}'
  AND year >= year(current_date - interval '{args.lookback_days}' day)
GROUP BY substr(timestamp, 1, 10)
HAVING substr(timestamp, 1, 10) <> ''
ORDER BY day ASC
""",
        ),
    )
    impacted_rows = athena_or_empty(
        "impacted",
        lambda: run_athena_query(
            athena,
            database=args.database,
            workgroup=args.workgroup,
            output_bucket=args.athena_results_bucket,
            timeout_seconds=args.athena_timeout_seconds,
            query=f"""
WITH base AS (
  SELECT
    service,
    account_id,
    coalesce(nullif(squad, ''), 'unassigned') AS squad,
    coalesce(nullif(owner, ''), 'untagged') AS owner,
    coalesce(unblended_cost, cost, 0) AS cost
  FROM "{args.database}"."cur_data"
  WHERE account_id = '{args.account_id}'
    AND year >= year(current_date - interval '{args.lookback_days}' day)
)
SELECT service AS name, 'Service' AS type, sum(cost) / greatest({args.lookback_days}, 1) AS spend_delta_usd_per_day,
       CASE WHEN min(owner) = 'untagged' THEN 'missing owner' ELSE 'valid' END AS owner_tag_status
FROM base
GROUP BY service
UNION ALL
SELECT squad AS name, 'Squad' AS type, sum(cost) / greatest({args.lookback_days}, 1) AS spend_delta_usd_per_day,
       CASE WHEN min(owner) = 'untagged' THEN 'missing owner' ELSE 'valid' END AS owner_tag_status
FROM base
GROUP BY squad
ORDER BY spend_delta_usd_per_day DESC
LIMIT 20
""",
        ),
    )

    if not spend_rows or not impacted_rows:
        cost_records = load_curated_cost_rows_from_s3(
            s3,
            lakehouse_bucket=args.lakehouse_bucket,
            account_id=args.account_id,
            max_objects=args.max_curated_objects,
        )
        if cost_records:
            print(f"[info] loaded {len(cost_records)} curated cost rows directly from S3 fallback")
        if not spend_rows:
            spend_rows = build_spend_rows_from_cost_records(cost_records)
        if not impacted_rows:
            impacted_rows = build_impacted_rows_from_cost_records(cost_records, args.lookback_days)

    anomaly_items = scan_table(dynamodb, args.anomaly_table, args.scan_limit)
    audit_items = scan_table(dynamodb, args.audit_table, args.scan_limit)
    dashboard_items = scan_table(dynamodb, args.dashboard_views_table, args.scan_limit)
    run_state_items = scan_table(dynamodb, args.run_state_table, args.scan_limit)

    spend_trend = build_spend_trend(spend_rows)
    impacted = build_impacted(impacted_rows)
    anomalies = build_anomalies(anomaly_items, dashboard_items)
    containment = build_containment(audit_items, dashboard_items)
    audit_diffs = build_audit_diffs(containment, audit_items)

    latest_spend_date = spend_trend[-1][0] if spend_trend else ""
    freshness = "fresh" if latest_spend_date else "unknown"
    total_spend = sum(row[1] for row in spend_trend)
    summary = {
        "dashboard_schema_version": "2026-01",
        "environment": args.environment,
        "viewer_role": args.viewer_role,
        "generated_at": iso_now(),
        "tenant_id": args.tenant_id,
        "data_freshness_status": freshness,
        "containment_locked": False,
        "error_budget_remaining_pct": 100,
        "workflow_status": "READY" if latest_spend_date else "NO_SUMMARY_SOURCE_ROWS",
        "last_successful_run_id": latest_run_id(run_state_items),
        "business_context": {
            "source": "athena_curated_cost",
            "account_id": args.account_id,
            "latest_spend_date": latest_spend_date,
            "lookback_days": args.lookback_days,
        },
        "telemetry_quality": {
            "summary_source": "Athena cur_data + DynamoDB operational tables",
            "curated_spend_rows": len(spend_rows),
            "anomaly_records": len(anomaly_items),
            "audit_records": len(audit_items),
            "dashboard_cache_records": len(dashboard_items),
            "total_spend_usd": round(total_spend, 6),
        },
        "spend_trend": spend_trend,
        "anomalies": anomalies,
        "impacted": impacted,
        "containment": containment,
        "approvals": [],
        "alert_previews": build_alert_previews(anomalies),
        "audit_diffs": audit_diffs,
        "admin_settings": [
            {"name": "Cognito user pool", "value": args.cognito_user_pool_id, "status": "admin"},
            {"name": "CloudFront distribution", "value": args.cloudfront_distribution_id, "status": "read-only"},
            {"name": "Dashboard data source", "value": f"s3://{args.dashboard_bucket}/{args.dashboard_key}", "status": "materialized"},
            {"name": "Athena workgroup", "value": args.workgroup, "status": "read-only"},
        ],
    }

    body = json.dumps(summary, indent=2, default=decimal_default).encode("utf-8")
    if args.dry_run:
        print(body.decode("utf-8"))
    else:
        s3.put_object(
            Bucket=args.dashboard_bucket,
            Key=args.dashboard_key,
            Body=body,
            ContentType="application/json",
            CacheControl="no-store, max-age=0",
        )
        print(f"Published {len(body)} bytes to s3://{args.dashboard_bucket}/{args.dashboard_key}")
        if args.cloudfront_distribution_id and args.invalidate_cloudfront:
            cf = session.client("cloudfront", region_name="us-east-1")
            invalidation = cf.create_invalidation(
                DistributionId=args.cloudfront_distribution_id,
                InvalidationBatch={
                    "Paths": {
                        "Quantity": 1,
                        "Items": ["/" + args.dashboard_key],
                    },
                    "CallerReference": f"dashboard-summary-{int(time.time())}",
                },
            )
            invalidation_id = invalidation["Invalidation"]["Id"]
            print(f"Created CloudFront invalidation {invalidation_id}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--project-name", default=DEFAULT_PROJECT)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--viewer-role", default="cdo")
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--workgroup", default=DEFAULT_WORKGROUP)
    parser.add_argument("--athena-results-bucket", default=DEFAULT_ATHENA_RESULTS_BUCKET)
    parser.add_argument("--lakehouse-bucket", default=DEFAULT_LAKEHOUSE_BUCKET)
    parser.add_argument("--dashboard-bucket", default=DEFAULT_DASHBOARD_BUCKET)
    parser.add_argument("--dashboard-key", default=DEFAULT_DASHBOARD_KEY)
    parser.add_argument("--run-state-table", default="tf2-finops-sandbox-run-state")
    parser.add_argument("--anomaly-table", default="tf2-finops-sandbox-anomaly")
    parser.add_argument("--audit-table", default="tf2-finops-sandbox-containment-audit")
    parser.add_argument("--dashboard-views-table", default="tf2-finops-sandbox-dashboard-views")
    parser.add_argument("--cognito-user-pool-id", default="ap-southeast-1_NO5o6jadD")
    parser.add_argument("--cloudfront-distribution-id", default="E26YBZ92YVN6PO")
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--max-curated-objects", type=int, default=200)
    parser.add_argument("--scan-limit", type=int, default=100)
    parser.add_argument("--athena-timeout-seconds", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--invalidate-cloudfront", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # Auto-resolve account ID via STS if not explicitly provided
    if not args.account_id:
        args.account_id = get_caller_account_id(args.region)
        print(f"[info] Resolved account ID via STS: {args.account_id}")
    publish_summary(args)
