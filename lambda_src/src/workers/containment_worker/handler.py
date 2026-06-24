import logging
from typing import Any
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))
    
    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    # 1. Determine environment
    env = (event.environment or "").lower()
    if event.account_policy and event.account_policy.environment:
        env = event.account_policy.environment.lower()

    # 2. Determine requested action
    requested_action = (event.action or "").lower()
    if not requested_action:
        requested_action = "dry-run"

    # 3. Enforce policy: Deny terminate, delete, modify_iam across all environments
    if requested_action in ["terminate", "delete", "modify_iam"]:
        logger.warning("Action '%s' is destructive and strictly denied by containment policy.", requested_action)
        details = {
            "requested_action": requested_action,
            "execution_mode": "denied",
            "containment_status": "denied",
            "message": f"Action '{requested_action}' is denied by containment policy."
        }
        response = finops_common.create_response("DENIED", event.run_id, event.correlation_id, "containment_worker", details)
        response.execution_mode = "denied"
        response.containment_status = "denied"
        return response.to_dict()

    # 4. Determine execution mode based on environment rules
    if env == "prod":
        # Prod only allows tag, suggest, or dry-run
        if requested_action in ["tag", "suggest", "dry-run"]:
            execution_mode = requested_action
        else:
            logger.info("Action '%s' is not allowed in production. Overriding to dry-run.", requested_action)
            execution_mode = "dry-run"
    else:
        # Non-prod (sandbox/staging) requires approval status == approved to allow apply
        if requested_action == "apply":
            approval = (event.approval_status or "").lower()
            if approval == "approved":
                execution_mode = "apply"
            else:
                logger.info("Apply action in non-prod environment '%s' requires explicit approval. Overriding to dry-run.", env)
                execution_mode = "dry-run"
        else:
            execution_mode = requested_action

    # 5. Establish containment status
    containment_status = "applied"
    if execution_mode == "dry-run":
        containment_status = "executed_dry_run"
    elif execution_mode == "tag":
        containment_status = "tag_applied"
    elif execution_mode == "suggest":
        containment_status = "suggest_applied"

    details = {
        "requested_action": requested_action,
        "execution_mode": execution_mode,
        "containment_status": containment_status,
        "message": f"Containment evaluated with mode '{execution_mode}'"
    }

    response = finops_common.create_response("CONTAINMENT_EVALUATED", event.run_id, event.correlation_id, "containment_worker", details)
    response.execution_mode = execution_mode
    response.containment_status = containment_status
    logger.info("Response: %s", response.to_dict())
    return response.to_dict()
