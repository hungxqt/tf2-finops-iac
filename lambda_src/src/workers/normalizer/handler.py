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

    partition_path = f"year={exec_time.year:04d}/month={exec_time.month:02d}/day={exec_time.day:02d}"
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
        service = rec.get("service", "")
        cost = rec.get("cost", 0.0)
        
        # Validate required cost fields
        if not account_id or not service or cost < 0:
            logger.info("Filtering out invalid cost record: %s", rec)
            continue
            
        owner = rec.get("owner", "")
        if not owner or owner.strip() == "":
            owner = "untagged"
            
        curated_records.append({
            "account_id": account_id,
            "service": service,
            "region": rec.get("region", ""),
            "owner": owner,
            "cost": cost,
            "currency": rec.get("currency", ""),
            "timestamp": rec.get("timestamp", ""),
            "curated_at": datetime.utcnow().isoformat() + "Z"
        })
        
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
