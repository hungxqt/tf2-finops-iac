import os
import io
import json
import gzip
import logging
from datetime import datetime, timezone
from typing import Any
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = None
ddb_client = None


def get_s3_client():
    global s3_client
    if s3_client is not None:
        return s3_client
    if os.environ.get("LAKEHOUSE_BUCKET_NAME"):
        return finops_common.RealS3()
    return None


def get_ddb_client():
    global ddb_client
    if ddb_client is not None:
        return ddb_client
    if os.environ.get("RUN_STATE_TABLE_NAME"):
        return finops_common.RealDynamoDB()
    return None


def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))

    operation = (event_data.get("operation") or "").lower()

    # ── fail_contract_check: record contract version mismatch ──────────
    if operation == "fail_contract_check":
        table_name = os.environ.get("RUN_STATE_TABLE_NAME")
        client = get_ddb_client()
        if client and table_name:
            idempotency_key = finops_common.idempotency_key(
                event_data.get("account_id", ""),
                event_data.get("cost_period", ""),
                event_data.get("execution_date", ""),
            )
            try:
                client.put_item(table_name, {
                    "idempotency_key": idempotency_key,
                    "status": "FAILED_CONTRACT_CHECK",
                    "run_id": event_data.get("run_id", ""),
                    "correlation_id": event_data.get("correlation_id", ""),
                    "failure_code": "CONTRACT_MISMATCH",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                status = "FAILED_CONTRACT_CHECK"
            except Exception as e:
                logger.error("DynamoDB fail_contract_check write failed: %s", e)
                raise e
        else:
            status = "FAILED_CONTRACT_CHECK"

        details = {
            "account_id": event_data.get("account_id", ""),
            "cost_period": event_data.get("cost_period", ""),
            "execution_date": event_data.get("execution_date", ""),
            "failure_code": "CONTRACT_MISMATCH",
        }
        response = finops_common.create_response(
            status,
            event_data.get("run_id", ""),
            event_data.get("correlation_id", ""),
            "normalizer",
            details,
        )
        logger.info("Response: %s", response.to_dict())
        return response.to_dict()

    # ── Normal path: validate event ────────────────────────────────────
    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    bucket_name = os.environ.get("LAKEHOUSE_BUCKET_NAME", "tf2-finops-lakehouse-bucket")

    try:
        exec_time = finops_common.parse_date(event.execution_date)
    except Exception as e:
        logger.error("Invalid execution date: %s", e)
        raise e

    partition_path = (
        f"account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}"
    )
    curated_key = f"cost/curated/{partition_path}/{event.run_id}_curated.parquet"
    curated_data_uri = f"s3://{bucket_name}/{curated_key}"

    # 1. Read raw S3 cost data ──────────────────────────────────────────
    raw_uri = ""
    if event.ingestion and event.ingestion.raw_data_uri:
        raw_uri = event.ingestion.raw_data_uri

    client = get_s3_client()
    raw_data = b""
    if client and raw_uri:
        try:
            logger.info("Reading raw cost data from: %s", raw_uri)
            s3_bucket, s3_key = finops_common.parse_s3_uri(raw_uri)
            raw_data = client.get_object(s3_bucket, s3_key)
        except Exception as e:
            logger.error("Failed to read raw cost data from S3: %s", e)
            raise e
    else:
        # Mock local fallback raw cost data
        logger.info("S3 Client or Raw URI not present, using default raw data mockup")
        default_records = [
            {
                "account_id": event.account_id,
                "service": "AmazonEC2",
                "region": "ap-southeast-1",
                "owner": "",  # Untagged
                "cost": 150.00,
                "currency": "USD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        raw_data = json.dumps(default_records).encode("utf-8")

    # 2. Parse and decompress ───────────────────────────────────────────
    try:
        decompressed_data = raw_data
        if decompressed_data.startswith(b"\x1f\x8b"):
            decompressed_data = gzip.decompress(decompressed_data)
        raw_records = json.loads(decompressed_data.decode("utf-8"))
    except Exception as e:
        logger.error("Failed to parse raw cost records JSON: %s", e)
        raise e

    # 3. Extract envelope quality + choose records to normalise ─────────
    envelope_quality = {}
    if isinstance(raw_records, dict):
        envelope_quality = raw_records.get("quality", {})
        if raw_records.get("aws_cur_line_items"):
            records_to_normalize = raw_records["aws_cur_line_items"]
        elif raw_records.get("aws_cost_explorer_daily"):
            records_to_normalize = raw_records["aws_cost_explorer_daily"]
        else:
            records_to_normalize = []
    else:
        records_to_normalize = raw_records

    # 4. Resolve telemetry quality flags ────────────────────────────────
    completeness_score = float(
        event_data.get("completeness_score")
        or event_data.get("telemetry_quality")
        or envelope_quality.get("completeness_score")
        or 1.0
    )
    delayed_cur = bool(
        event_data.get("delayed_cur") or envelope_quality.get("delayed_cur") or False
    )
    stale_cost_explorer = bool(
        event_data.get("stale_cost_explorer")
        or envelope_quality.get("stale_cost_explorer")
        or False
    )
    missing_cloudwatch = bool(
        event_data.get("missing_cloudwatch")
        or envelope_quality.get("missing_cloudwatch")
        or False
    )
    estimated_billing = bool(
        event_data.get("estimated_billing")
        or envelope_quality.get("estimated_billing")
        or False
    )

    # 5. Normalise records ──────────────────────────────────────────────
    curated_records = []
    for rec in records_to_normalize:
        account_id = (
            rec.get("account_id")
            or rec.get("line_item_usage_account_id")
            or rec.get("linked_account_id")
            or ""
        )
        cost = float(
            rec.get("cost")
            or rec.get("line_item_unblended_cost")
            or rec.get("unblended_cost")
            or 0.0
        )

        service = (
            rec.get("service")
            or rec.get("line_item_product_code")
            or rec.get("service_code")
            or ""
        )
        if not account_id or not service or cost < 0:
            logger.info("Filtering out invalid cost record: %s", rec)
            continue

        owner = rec.get("owner") or rec.get("resource_tags_user_owner") or ""
        if not owner or owner.strip() == "":
            owner = "untagged"

        squad = (
            rec.get("squad")
            or rec.get("team")
            or rec.get("resource_tags_user_team")
            or "untagged"
        )
        cost_center = (
            rec.get("cost_center")
            or rec.get("resource_tags_user_cost_center")
            or "untagged"
        )
        region = rec.get("region") or rec.get("product_region_code") or ""
        resource_id = rec.get("resource_id") or rec.get("line_item_resource_id") or ""
        currency = rec.get("currency") or rec.get("line_item_currency_code") or "USD"
        timestamp = (
            rec.get("timestamp")
            or rec.get("line_item_usage_start_date")
            or rec.get("date")
            or ""
        )

        curated_records.append({
            # Original fields for backward compatibility
            "account_id": account_id,
            "service": service,
            "region": region,
            "owner": owner,
            "cost": cost,
            "currency": currency,
            "timestamp": timestamp,
            "curated_at": datetime.now(timezone.utc).isoformat(),
            # Formally required cost fields
            "unblended_cost": cost,
            "service_code": service,
            "resource_id": resource_id,
            "squad": squad,
            "cost_center": cost_center,
            "schema_version": "3.2.0",
            "correlation_id": event.correlation_id,
            "idempotency_key": event_data.get("idempotency_key") or event.correlation_id,
            "quality_score": completeness_score,
        })

    # 6. Serialise to Parquet (fallback JSON) ───────────────────────────
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(curated_records)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        curated_data = buf.getvalue()
        logger.info("Successfully generated Parquet bytes: %d bytes", len(curated_data))
    except Exception as e:
        logger.error(
            "Failed to write Parquet using pyarrow: %s. Falling back to JSON bytes.", e
        )
        curated_data = json.dumps(curated_records).encode("utf-8")

    # 7. Write to S3 curated folder ─────────────────────────────────────
    if client:
        try:
            logger.info("Writing curated cost data to S3: %s", curated_data_uri)
            client.put_object(bucket_name, curated_key, curated_data)
        except Exception as e:
            logger.error("Failed to write curated cost to S3: %s", e)
            raise e
    else:
        logger.info("S3 Client not configured, skipping curated S3 write")

    details = {
        "curated_data_uri": curated_data_uri,
        "schema": "finops-cost-window-v1",
        "partition_keys": ["account_id", "year", "month"],
        "completeness_score": completeness_score,
        "delayed_cur": delayed_cur,
        "stale_cost_explorer": stale_cost_explorer,
        "missing_cloudwatch": missing_cloudwatch,
        "estimated_billing": estimated_billing,
    }

    response = finops_common.create_response(
        "NORMALIZED", event.run_id, event.correlation_id, "normalizer", details
    )
    response.curated_data_uri = curated_data_uri
    response.telemetry_quality = completeness_score
    logger.info("Response: %s", response.to_dict())
    return response.to_dict()
