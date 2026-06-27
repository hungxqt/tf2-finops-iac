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

SAFE_CONTAINMENT_ACTIONS = {"dry-run", "dry_run", "tag", "suggest", "tag-for-review"}
UNSAFE_CONTAINMENT_ACTIONS = {
    "terminate",
    "delete",
    "modify_iam",
    "apply",
    "auto-shutdown",
    "quota-cap",
    "time-gated-countdown",
}
PROD_ENVIRONMENTS = {"prod", "prod-core", "prod-payments"}

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

def _first_anomaly(raw_event: dict) -> dict:
    anomalies = raw_event.get("ai_detect_response", {}).get("anomalies_list", [])
    if isinstance(anomalies, list) and anomalies:
        first = anomalies[0]
        if isinstance(first, dict):
            return first
    return {}

def _first_action_plan(raw_event: dict) -> dict:
    action_plan = raw_event.get("ai_decide_response", {}).get("action_plan", [])
    if isinstance(action_plan, list) and action_plan:
        first = action_plan[0]
        if isinstance(first, dict):
            return first
    return {}

def _effective_environment(event: finops_common.Event) -> str:
    env = (event.environment or "").lower()
    if event.account_policy and event.account_policy.environment:
        env = event.account_policy.environment.lower()
    return env

def _requested_action(event: finops_common.Event, raw_event: dict) -> str:
    if event.action:
        return event.action
    if event.ai and event.ai.recommended_containment_mode:
        return event.ai.recommended_containment_mode
    action_plan = _first_action_plan(raw_event)
    return action_plan.get("action", "")

def _denial_reason(event: finops_common.Event, env: str, action: str) -> str:
    normalized_action = (action or "").lower()
    if (event.approval_status or "").lower() == "denied":
        return "approval_denied"
    if event.force_dry_run and normalized_action not in SAFE_CONTAINMENT_ACTIONS:
        return "forced_dry_run"
    if env in PROD_ENVIRONMENTS and normalized_action in UNSAFE_CONTAINMENT_ACTIONS:
        return "prod_unsafe_action"
    return ""

def _infer_audit_type(event: finops_common.Event, env: str, action: str, denial_reason: str) -> str:
    if event.containment_error is not None:
        return "CONTAINMENT_FAILURE"
    if event.alert_error is not None:
        return "ALERT_DELIVERY_FAILURE"
    if event.error is not None or action in {"fail-closed", "fail-closed-cur-delay"}:
        return "WORKFLOW_FAILURE"
    if event.containment is not None:
        return "POST_ACTION"
    if denial_reason:
        return "DENIED"
    if env == "sandbox":
        if (event.approval_status or "").lower() == "approved":
            return "PRE_ACTION"
        return "PENDING_APPROVAL"
    if env in PROD_ENVIRONMENTS:
        return "PRE_ACTION"
    return "PENDING_APPROVAL"

def _execution_mode(event: finops_common.Event, audit_type: str, action: str) -> str:
    if audit_type == "WORKFLOW_FAILURE":
        return "dry-run"
    if audit_type == "DENIED":
        if event.force_dry_run:
            return "dry-run"
        return "denied"
    if event.containment and event.containment.execution_mode:
        return event.containment.execution_mode
    normalized_action = (action or "").lower()
    if normalized_action in {"dry-run", "dry_run"}:
        return "dry-run"
    if normalized_action in {"tag", "tag-for-review"}:
        return "tag"
    if normalized_action == "suggest":
        return "suggest"
    if (event.approval_status or "").lower() == "approved":
        return "apply"
    return "dry-run"

def _resource_context(event: finops_common.Event, raw_event: dict) -> tuple[str, str]:
    resource_id = "N/A"
    owner = "untagged"
    anomaly = _first_anomaly(raw_event)

    if anomaly:
        resource_id = (
            anomaly.get("resource_id")
            or anomaly.get("line_item_resource_id")
            or resource_id
        )
        owner = (
            anomaly.get("owner")
            or anomaly.get("resource_owner")
            or anomaly.get("resource_tags_user_owner")
            or owner
        )

    if event.ai and event.ai.details:
        resource_id = event.ai.details.get("resource_id") or event.ai.details.get("line_item_resource_id") or resource_id
        owner = event.ai.details.get("owner") or event.ai.details.get("resource_tags_user_owner") or owner
    if event.containment and event.containment.details:
        resource_id = event.containment.details.get("resource_id") or event.containment.details.get("line_item_resource_id") or resource_id
        owner = event.containment.details.get("owner") or event.containment.details.get("resource_tags_user_owner") or owner
    return resource_id, owner

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

    env = _effective_environment(event)
    requested_action = _requested_action(event, event_data)
    denial_reason = _denial_reason(event, env, requested_action)
    audit_type = _infer_audit_type(event, env, requested_action, denial_reason)

    audit_id = f"audit-{audit_type.lower()}-{event.correlation_id}"

    try:
        exec_time = finops_common.parse_date(event.execution_date)
    except Exception:
        exec_time = datetime.utcnow()

    year_str = f"{exec_time.year:04d}"
    month_str = f"{exec_time.month:02d}"

    audit_key = f"audit/account_id={event.account_id}/year={year_str}/month={month_str}/{audit_id}.json"
    audit_uri = f"s3://{bucket_name}/{audit_key}"

    # 2. Gather AGENTS-required audit fields
    anomaly_id = "N/A"
    if event.ai:
        if event.ai.anomaly_id:
            anomaly_id = event.ai.anomaly_id

    anomaly = _first_anomaly(event_data)
    if anomaly and anomaly.get("anomaly_id"):
        anomaly_id = anomaly["anomaly_id"]

    execution_mode = _execution_mode(event, audit_type, requested_action)
    resource_id, owner = _resource_context(event, event_data)

    before_state = "anomaly_detected"
    proposed_after_state = "containment_proposed"
    if audit_type == "DENIED":
        proposed_after_state = "containment_denied"
    elif audit_type == "WORKFLOW_FAILURE":
        proposed_after_state = "workflow_failed_closed"
    elif requested_action:
        proposed_after_state = f"containment_{requested_action}_proposed"

    applied_after_state = "none"
    if event.containment and event.containment.containment_status:
        applied_after_state = event.containment.containment_status
    elif event.containment and event.containment.status:
        applied_after_state = event.containment.status
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

    # Calculate numeric audit score based on severity/confidence/quality
    audit_score = 1.0
    if event.ai and event.ai.confidence is not None:
        audit_score = float(event.ai.confidence)
    elif event.telemetry_quality is not None:
        audit_score = float(event.telemetry_quality)

    details = {
        "audit_id": audit_id,
        "audit_uri": audit_uri,
        "audit_type": audit_type,
        "actor": "tf2-finops-orchestrator",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "correlation_id": event.correlation_id,
        "tenant_id": event.tenant_id,
        "idempotency_key": idemp_key,
        "anomaly_id": anomaly_id,
        "account_id": event.account_id,
        "environment": env,
        "resource_id": resource_id,
        "owner": owner,
        "target_owner": owner,
        "before_state": before_state,
        "proposed_after_state": proposed_after_state,
        "applied_after_state": applied_after_state,
        "after_state": applied_after_state,
        "execution_mode": execution_mode,
        "requested_action": requested_action,
        "denial_reason": denial_reason,
        "force_dry_run": event.force_dry_run,
        "rollback_path": "revert-resource-tags",
        "approval_status": approval_status,
        "retention_location": audit_uri,
        "retention_period": "90 days",
        "audit_score": audit_score,
        "numeric_audit_score": audit_score,
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
                "tenant_id": event.tenant_id,
                "account_id": event.account_id,
                "environment": env,
                "audit_type": audit_type,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "idempotency_key": idemp_key,
                "anomaly_id": anomaly_id,
                "execution_mode": execution_mode,
                "requested_action": requested_action,
                "denial_reason": denial_reason,
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
