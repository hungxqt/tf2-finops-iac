import os
import logging
from typing import Any
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb_client = None

def get_ddb_client():
    global ddb_client
    if ddb_client is not None:
        return ddb_client
    if os.environ.get("ROUTING_STATE_TABLE_NAME"):
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

    finance_route = {
        "channel": "sns-finance",
        "action_required": False,
        "summary": "Daily FinOps spend digest - normal",
        "deliver": False,
        "subject": "",
        "message": ""
    }

    engineering_route = {
        "channel": "sns-engineering",
        "action_required": False,
        "summary": "Daily FinOps infrastructure report - no critical anomalies",
        "deliver": False,
        "subject": "",
        "message": ""
    }

    route_target = "engineering"

    if event.ai and event.ai.anomaly_found:
        severity = (event.ai.severity or "").lower()
        anomaly_id = event.ai.anomaly_id or "UNKNOWN"

        if severity in ["critical", "high"]:
            finance_route["action_required"] = True
            finance_route["summary"] = f"CRITICAL ALERT: Cost anomaly detected (ID: {anomaly_id}, severity: {severity})"
            finance_route["deliver"] = True
            finance_route["subject"] = "Critical FinOps Alert: Cost Anomaly Detected"
            finance_route["message"] = f"Critical FinOps cost anomaly detected. Anomaly ID: {anomaly_id}, Severity: {severity}, Run ID: {event.run_id}. Immediate review is required."

            engineering_route["action_required"] = True
            engineering_route["summary"] = f"CRITICAL CONTAINMENT: Resource anomaly detected (ID: {anomaly_id}, severity: {severity})"
            engineering_route["deliver"] = True
            engineering_route["subject"] = "Critical FinOps Containment: Engineering Action Required"
            engineering_route["message"] = f"Critical resource anomaly detected. Anomaly ID: {anomaly_id}, Severity: {severity}, Run ID: {event.run_id}. Containment action evaluation will begin."
            route_target = "engineering"
        else:
            finance_route["summary"] = f"Alert: Cost anomaly detected (ID: {anomaly_id}, severity: {severity})"
            finance_route["deliver"] = True
            finance_route["subject"] = "FinOps Alert: Cost Anomaly Detected"
            finance_route["message"] = f"FinOps cost anomaly detected. Anomaly ID: {anomaly_id}, Severity: {severity}, Run ID: {event.run_id}."

            engineering_route["summary"] = f"Report: Cost anomaly detected (ID: {anomaly_id}, severity: {severity})"
            engineering_route["deliver"] = False
            route_target = "finance"

    # Optionally persist routing state
    table_name = os.environ.get("ROUTING_STATE_TABLE_NAME")
    client = get_ddb_client()
    if client and table_name:
        idempotency_key = finops_common.idempotency_key(event.account_id, event.cost_period, event.execution_date)
        try:
            logger.info("Persisting routing state to table %s: key=%s", table_name, idempotency_key)
            client.put_item(table_name, {
                "idempotency_key": idempotency_key,
                "run_id": event.run_id,
                "correlation_id": event.correlation_id,
                "finance_deliver": finance_route["deliver"],
                "eng_deliver": engineering_route["deliver"],
                "route_target": route_target,
                "created_at": finops_common.iso_utc_now()
            })
        except Exception as e:
            logger.warning("DynamoDB save routing state failed (non-blocking): %s", e)

    details = {
        "finance_route": finance_route,
        "engineering_route": engineering_route
    }

    response = finops_common.create_response("ROUTED", event.run_id, event.correlation_id, "router", details)
    response.route_target = route_target
    logger.info("Response: %s", response.to_dict())
    return response.to_dict()
