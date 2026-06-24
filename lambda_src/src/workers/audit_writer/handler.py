import os
import logging
import json
from datetime import datetime
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
    if os.environ.get("AUDIT_BUCKET_NAME"):
        return finops_common.RealS3()
    return None

def get_ddb_client():
    global ddb_client
    if ddb_client is not None:
        return ddb_client
    if os.environ.get("AUDIT_TABLE_NAME"):
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

    bucket_name = os.environ.get("AUDIT_BUCKET_NAME", "tf2-finops-audit-bucket")
    table_name = os.environ.get("AUDIT_TABLE_NAME")

    # 1. Infer audit type from the payload structure
    audit_type = "PENDING_APPROVAL"
    if event.containment_error is not None:
        audit_type = "CONTAINMENT_FAILURE"
    elif event.alert_error is not None:
        audit_type = "ALERT_DELIVERY_FAILURE"
    elif event.error is not None:
        audit_type = "WORKFLOW_FAILURE"
    elif event.containment is not None:
        audit_type = "POST_ACTION"
    else:
        env = (event.environment or "").lower()
        if event.account_policy and event.account_policy.environment:
            env = event.account_policy.environment.lower()

        if env == "prod":
            if event.ai:
                mode = (event.ai.recommended_containment_mode or "").lower()
                if mode in ["terminate", "delete", "modify_iam", "apply"]:
                    audit_type = "DENIED"
                else:
                    audit_type = "PRE_ACTION"
            else:
                audit_type = "PRE_ACTION"
        elif env == "sandbox":
            if (event.approval_status or "").lower() == "approved":
                audit_type = "PRE_ACTION"
            else:
                audit_type = "PENDING_APPROVAL"

    audit_key = f"audit/{event.correlation_id}_{audit_type.lower()}.json"
    audit_uri = f"s3://{bucket_name}/{audit_key}"
    audit_id = f"audit-{audit_type.lower()}-{event.correlation_id}"

    # 2. Gather AGENTS-required audit fields
    anomaly_id = "N/A"
    execution_mode = "dry-run"
    target_owner = "engineering"
    
    if event.ai:
        if event.ai.anomaly_id:
            anomaly_id = event.ai.anomaly_id
        if event.ai.recommended_containment_mode:
            execution_mode = event.ai.recommended_containment_mode

    before_state = "anomaly_detected"
    proposed_after_state = "containment_proposed"
    if event.action:
        proposed_after_state = f"containment_{event.action}_proposed"

    applied_after_state = "none"
    if event.containment and event.containment.containment_status:
        applied_after_state = event.containment.containment_status
    elif event.action == "apply":
        applied_after_state = "containment_applied"

    approval_status = event.approval_status or "pending"

    error_details = None
    if event.containment_error is not None:
        error_details = event.containment_error.to_dict()
    elif event.alert_error is not None:
        error_details = event.alert_error.to_dict()
    elif event.error is not None:
        error_details = event.error.to_dict()

    idemp_key = finops_common.idempotency_key(event.account_id, event.cost_period, event.execution_date)

    details = {
        "audit_id": audit_id,
        "audit_uri": audit_uri,
        "audit_type": audit_type,
        "actor": "tf2-finops-orchestrator",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "correlation_id": event.correlation_id,
        "idempotency_key": idemp_key,
        "anomaly_id": anomaly_id,
        "target_owner": target_owner,
        "before_state": before_state,
        "proposed_after_state": proposed_after_state,
        "applied_after_state": applied_after_state,
        "execution_mode": execution_mode,
        "rollback_path": "revert-resource-tags",
        "approval_status": approval_status,
        "retention_location": audit_uri,
        "retention_period": "90 days",
        "error_details": error_details
    }

    audit_bytes = json.dumps(details, indent=2).encode("utf-8")

    # 3. Save JSON document to S3 Object Lock bucket
    s_client = get_s3_client()
    if s_client:
        try:
            logger.info("Writing full audit record to S3: %s", audit_uri)
            s_client.put_object(bucket_name, audit_key, audit_bytes)
        except Exception as e:
            logger.error("S3 PutObject failed: %s", e)
            raise e
    else:
        logger.info("S3 Client not configured, skipping S3 audit record write")

    # 4. Index in DynamoDB
    d_client = get_ddb_client()
    if d_client and table_name:
        try:
            logger.info("Indexing audit record in DynamoDB table %s: audit_id=%s", table_name, audit_id)
            d_client.put_item(table_name, {
                "audit_id": audit_id,
                "correlation_id": event.correlation_id,
                "audit_type": audit_type,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "retention_location": audit_uri,
                "retention_period": "90 days"
            })
        except Exception as e:
            logger.error("DynamoDB PutItem failed: %s", e)
            raise e
    else:
        logger.info("DynamoDB Client or table not present, skipping DynamoDB indexing")

    response = finops_common.create_response("AUDIT_WRITTEN", event.run_id, event.correlation_id, "audit_writer", details)
    response.audit_id = audit_id
    response.audit_uri = audit_uri
    logger.info("Response: %s", response.to_dict())
    return response.to_dict()
