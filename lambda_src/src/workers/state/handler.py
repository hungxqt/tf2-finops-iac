import os
import logging
from datetime import datetime
from typing import Any
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb_client = None

def get_ddb_client():
    global ddb_client
    if ddb_client is not None:
        return ddb_client
    if os.environ.get("RUN_STATE_TABLE_NAME"):
        return finops_common.RealDynamoDB()
    return None

def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))
    
    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    operation = event_data.get("operation") or event_data.get("action") or ""
    
    status = "NEW"
    table_name = os.environ.get("RUN_STATE_TABLE_NAME")
    idempotency_key = finops_common.idempotency_key(event.account_id, event.cost_period, event.execution_date)
    
    client = get_ddb_client()
    
    if client and table_name:
        op = operation.lower()
        if op == "check":
            try:
                item = client.get_item(table_name, {"idempotency_key": idempotency_key})
                if not item:
                    # Fresh run: conditionally write IN_PROGRESS but status is NEW
                    client.put_item(table_name, {
                        "idempotency_key": idempotency_key,
                        "status": "IN_PROGRESS",
                        "run_id": event.run_id,
                        "correlation_id": event.correlation_id,
                        "updated_at": datetime.utcnow().isoformat() + "Z"
                    })
                    status = "NEW"
                else:
                    status = item.get("status", "IN_PROGRESS")
            except Exception as e:
                logger.error("DynamoDB check operation failed: %s", e)
                raise e
        elif op == "complete":
            try:
                client.put_item(table_name, {
                    "idempotency_key": idempotency_key,
                    "status": "COMPLETED",
                    "run_id": event.run_id,
                    "correlation_id": event.correlation_id,
                    "updated_at": datetime.utcnow().isoformat() + "Z"
                })
                status = "COMPLETED"
            except Exception as e:
                logger.error("DynamoDB complete operation failed: %s", e)
                raise e
        elif op == "failed":
            try:
                client.put_item(table_name, {
                    "idempotency_key": idempotency_key,
                    "status": "FAILED",
                    "run_id": event.run_id,
                    "correlation_id": event.correlation_id,
                    "updated_at": datetime.utcnow().isoformat() + "Z"
                })
                status = "FAILED"
            except Exception as e:
                logger.error("DynamoDB failed operation failed: %s", e)
                raise e
        else:
            status = "NEW"
    else:
        # Simulation fallback mode
        op = operation.lower()
        if op == "check":
            if "state" in event_data:
                status = "COMPLETED"
            else:
                status = "NEW"
        elif op == "complete":
            status = "COMPLETED"
        elif op == "failed":
            status = "FAILED"
        else:
            if "state" in event_data:
                status = "COMPLETED"
            if event_data.get("requested_state_status"):
                status = event_data["requested_state_status"]

    details = {
        "account_id": event.account_id,
        "cost_period": event.cost_period,
        "execution_date": event.execution_date,
        "idempotency_key": idempotency_key
    }
    
    response = finops_common.create_response(status, event.run_id, event.correlation_id, "state", details)
    logger.info("Response: %s", response.to_dict())
    return response.to_dict()
