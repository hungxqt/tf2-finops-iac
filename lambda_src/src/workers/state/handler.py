import os
import logging
import uuid
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
    
    operation = event_data.get("operation") or event_data.get("action") or ""
    op = operation.lower()
    
    if op == "prepare":
        payload = event_data.get("input")
        if not isinstance(payload, dict):
            payload = event_data
            
        run_id = payload.get("run_id") or event_data.get("run_id") or f"run-{uuid.uuid4()}"
        correlation_id = payload.get("correlation_id") or event_data.get("correlation_id") or run_id
        execution_date = payload.get("execution_date") or event_data.get("execution_date") or datetime.utcnow().strftime("%Y-%m-%d")
        cost_period = payload.get("cost_period") or event_data.get("cost_period") or execution_date[:7]
        tenant_id = payload.get("tenant_id") or payload.get("account_id") or event_data.get("tenant_id") or event_data.get("account_id") or "tenant-default"
        
        is_ad_hoc = False
        if "is_ad_hoc" in payload:
            is_ad_hoc = bool(payload["is_ad_hoc"])
        elif "is_ad_hoc" in event_data:
            is_ad_hoc = bool(event_data["is_ad_hoc"])
        elif payload.get("action") == "ad-hoc" or event_data.get("action") == "ad-hoc":
            is_ad_hoc = True
            
        ai_contract_version = event_data.get("ai_contract_version") or payload.get("ai_contract_version") or "v1"
        
        cur_retry = payload.get("cur_retry") or event_data.get("cur_retry") or {"count": 0, "max": 4}
        ai_retry = payload.get("ai_retry") or event_data.get("ai_retry") or {"count": 0, "max": 6}
        
        details = {
            "run_id": run_id,
            "correlation_id": correlation_id,
            "execution_date": execution_date,
            "cost_period": cost_period,
            "tenant_id": tenant_id,
            "is_ad_hoc": is_ad_hoc,
            "ai_contract_version": ai_contract_version,
            "cur_retry": cur_retry,
            "ai_retry": ai_retry,
            "force_dry_run": False,
            "account_id": event_data.get("account_id", "")
        }
        
        response = finops_common.create_response("OK", run_id, correlation_id, "state", details)
        response.tenant_id = tenant_id
        response.is_ad_hoc = is_ad_hoc
        response.force_dry_run = False
        
        resp_dict = response.to_dict()
        resp_dict.update(details)
        logger.info("Response: %s", resp_dict)
        return resp_dict

    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    if op == "check_quota":
        is_ad_hoc = event_data.get("is_ad_hoc") or False
        tenant_id = event_data.get("tenant_id") or "tenant-default"
        execution_date = event_data.get("execution_date") or datetime.utcnow().strftime("%Y-%m-%d")
        
        status = "OK"
        client = get_ddb_client()
        table_name = os.environ.get("RUN_STATE_TABLE_NAME")
        
        if is_ad_hoc:
            quota_key = f"quota:{tenant_id}:{execution_date}"
            if client and table_name:
                try:
                    item = client.get_item(table_name, {"idempotency_key": quota_key})
                    count = 0
                    if item:
                        count = int(item.get("count", 0))
                    if count >= 5:
                        logger.warning("Ad-hoc quota exceeded for tenant %s", tenant_id)
                        status = "QUOTA_EXCEEDED"
                    else:
                        client.put_item(table_name, {
                            "idempotency_key": quota_key,
                            "count": count + 1,
                            "updated_at": datetime.utcnow().isoformat() + "Z"
                        })
                except Exception as e:
                    logger.error("DynamoDB quota check failed: %s", e)
                    raise e
            else:
                if event_data.get("simulate_quota_exceeded"):
                    status = "QUOTA_EXCEEDED"
        
        response = finops_common.create_response(status, event.run_id, event.correlation_id, "state", {"is_ad_hoc": is_ad_hoc})
        response.tenant_id = tenant_id
        response.is_ad_hoc = is_ad_hoc
        response.force_dry_run = event_data.get("force_dry_run") or False
        
        resp_dict = response.to_dict()
        resp_dict.update({
            "tenant_id": tenant_id,
            "is_ad_hoc": is_ad_hoc,
            "force_dry_run": response.force_dry_run
        })
        logger.info("Response: %s", resp_dict)
        return resp_dict

    elif op == "check_error_budget":
        budget_table = os.environ.get("ERROR_BUDGET_TABLE_NAME")
        locked = False
        tenant_id = event_data.get("tenant_id") or "tenant-default"
        client = get_ddb_client()
        
        if client and budget_table:
            try:
                item = client.get_item(budget_table, {"tenant_id": tenant_id})
                if item:
                    locked = item.get("locked") is True or item.get("status") == "LOCKED"
            except Exception as e:
                logger.error("DynamoDB error budget check failed: %s", e)
                raise e
        else:
            locked = bool(event_data.get("simulate_error_budget_locked", False))
            
        status = "LOCKED" if locked else "OK"
        force_dry_run = locked or bool(event_data.get("force_dry_run", False))
        
        response = finops_common.create_response(status, event.run_id, event.correlation_id, "state", {"locked": locked})
        response.tenant_id = tenant_id
        response.is_ad_hoc = event_data.get("is_ad_hoc") or False
        response.force_dry_run = force_dry_run
        
        resp_dict = response.to_dict()
        resp_dict.update({
            "tenant_id": tenant_id,
            "is_ad_hoc": response.is_ad_hoc,
            "force_dry_run": force_dry_run,
            "locked": locked
        })
        logger.info("Response: %s", resp_dict)
        return resp_dict

    status = "NEW"
    table_name = os.environ.get("RUN_STATE_TABLE_NAME")
    idempotency_key = finops_common.idempotency_key(event.account_id, event.cost_period, event.execution_date)
    
    client = get_ddb_client()
    
    if client and table_name:
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
    response.tenant_id = event_data.get("tenant_id") or (event.account_id and str(uuid.uuid5(uuid.NAMESPACE_DNS, event.account_id))) or "tenant-default"
    response.is_ad_hoc = event_data.get("is_ad_hoc") or False
    response.force_dry_run = event_data.get("force_dry_run") or False
    
    resp_dict = response.to_dict()
    resp_dict.update({
        "tenant_id": response.tenant_id,
        "is_ad_hoc": response.is_ad_hoc,
        "force_dry_run": response.force_dry_run
    })
    
    logger.info("Response: %s", resp_dict)
    return resp_dict
