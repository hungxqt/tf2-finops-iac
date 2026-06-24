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
    raw_data_key = f"cost/raw/{partition_path}/{event.run_id}_raw.json"
    raw_data_uri = f"s3://{bucket_name}/{raw_data_key}"
    
    details = {
        "raw_data_uri": raw_data_uri,
        "account_id": event.account_id,
        "cost_period": event.cost_period
    }
    
    status = "READY"
    action = event.action.lower() if event.action else ""
    
    # Handle simulation overrides
    if action == "simulate-cur-delay":
        status = "CUR_DELAY"
        details["error"] = "Billing reports (CUR) not yet exported to S3."
        response = finops_common.create_response(status, event.run_id, event.correlation_id, "cost_puller", details)
        return response.to_dict()
    elif action == "simulate-ce-throttled":
        status = "CE_THROTTLED"
        details["error"] = "Cost Explorer API request rate limit exceeded."
        response = finops_common.create_response(status, event.run_id, event.correlation_id, "cost_puller", details)
        return response.to_dict()
        
    # Ingestion logic (live mode vs synthetic mode)
    synthetic_records = [
        {
            "account_id": event.account_id,
            "service": "AmazonEC2",
            "region": "ap-southeast-1",
            "owner": "Engineering",
            "cost": 150.00,
            "currency": "USD",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    ]
    raw_data = json.dumps(synthetic_records).encode("utf-8")
    
    client = get_s3_client()
    if client:
        try:
            logger.info("Writing raw cost data to S3: %s", raw_data_uri)
            client.put_object(bucket_name, raw_data_key, raw_data)
        except Exception as e:
            logger.error("Failed to write to S3: %s", e)
            raise e
    else:
        logger.info("S3 Client not configured, skipping S3 write (local execution)")
        
    response = finops_common.create_response(status, event.run_id, event.correlation_id, "cost_puller", details)
    response.raw_data_uri = raw_data_uri
    logger.info("Response: %s", response.to_dict())
    return response.to_dict()
