import os
import logging
import json
from datetime import datetime
from typing import Any
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = None

def get_s3_client():
    global s3_client
    if s3_client is not None:
        return s3_client
    if os.environ.get("LAKEHOUSE_BUCKET_NAME"):
        return finops_common.RealS3()
    return None

def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))
    
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

    partition_path = f"account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}"
    curated_key = f"cost/curated/{partition_path}/{event.run_id}_curated.parquet"
    curated_data_uri = f"s3://{bucket_name}/{curated_key}"
    
    completeness_score = float(event_data.get("completeness_score") or event_data.get("telemetry_quality") or 1.0)
    delayed_cur = bool(event_data.get("delayed_cur") or False)
    stale_cost_explorer = bool(event_data.get("stale_cost_explorer") or False)
    missing_cloudwatch = bool(event_data.get("missing_cloudwatch") or False)
    estimated_billing = bool(event_data.get("estimated_billing") or False)
    
    details = {
        "curated_data_uri": curated_data_uri,
        "schema": "finops-cost-window-v1",
        "partition_keys": ["account_id", "year", "month"],
        "completeness_score": completeness_score,
        "delayed_cur": delayed_cur,
        "stale_cost_explorer": stale_cost_explorer,
        "missing_cloudwatch": missing_cloudwatch,
        "estimated_billing": estimated_billing
    }
    
    # 2. Read raw S3 cost file
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
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        ]
        raw_data = json.dumps(default_records).encode("utf-8")

    # 3. Parse and normalize cost data
    try:
        raw_records = json.loads(raw_data.decode("utf-8"))
    except Exception as e:
        logger.error("Failed to parse raw cost records JSON: %s", e)
        raise e
        
    curated_records = []
    for rec in raw_records:
        account_id = rec.get("account_id", "")
        cost = float(rec.get("cost") or rec.get("line_item_unblended_cost") or 0.0)
        
        # Validate required cost fields
        service = rec.get("service") or rec.get("line_item_product_code") or ""
        if not account_id or not service or cost < 0:
            logger.info("Filtering out invalid cost record: %s", rec)
            continue
            
        owner = rec.get("owner") or rec.get("resource_tags_user_owner") or ""
        if not owner or owner.strip() == "":
            owner = "untagged"
            
        squad = rec.get("squad") or rec.get("team") or rec.get("resource_tags_user_team") or "untagged"
        cost_center = rec.get("cost_center") or rec.get("resource_tags_user_cost_center") or "untagged"
        region = rec.get("region") or rec.get("product_region_code") or ""
        resource_id = rec.get("resource_id") or rec.get("line_item_resource_id") or ""
        currency = rec.get("currency") or rec.get("line_item_currency_code") or "USD"
        timestamp = rec.get("timestamp") or rec.get("line_item_usage_start_date") or ""
            
        curated_records.append({
            # Original fields for backward compatibility
            "account_id": account_id,
            "service": service,
            "region": region,
            "owner": owner,
            "cost": cost,
            "currency": currency,
            "timestamp": timestamp,
            "curated_at": datetime.utcnow().isoformat() + "Z",
            
            # Formally required/documented cost fields
            "unblended_cost": cost,
            "service_code": service,
            "resource_id": resource_id,
            "squad": squad,
            "cost_center": cost_center,
            "schema_version": "3.2.0",
            "correlation_id": event.correlation_id,
            "idempotency_key": event_data.get("idempotency_key") or event.correlation_id,
            "quality_score": completeness_score
        })
        
    # Write to Parquet format using pyarrow
    import io
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        
        table = pa.Table.from_pylist(curated_records)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        curated_data = buf.getvalue()
        logger.info("Successfully generated Parquet bytes: %d bytes", len(curated_data))
    except Exception as e:
        logger.error("Failed to write Parquet using pyarrow: %s. Falling back to JSON bytes.", e)
        curated_data = json.dumps(curated_records).encode("utf-8")
    
    # 4. Save to S3 curated folder
    if client:
        try:
            logger.info("Writing curated cost data to S3: %s", curated_data_uri)
            client.put_object(bucket_name, curated_key, curated_data)
        except Exception as e:
            logger.error("Failed to write curated cost to S3: %s", e)
            raise e
    else:
        logger.info("S3 Client not configured, skipping curated S3 write")
        
    response = finops_common.create_response("NORMALIZED", event.run_id, event.correlation_id, "normalizer", details)
    response.curated_data_uri = curated_data_uri
    response.telemetry_quality = completeness_score
    logger.info("Response: %s", response.to_dict())
    return response.to_dict()

