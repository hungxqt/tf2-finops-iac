import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb_client = None


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_tenant_id(account_id: str) -> str:
    if account_id:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tf2-finops:{account_id}"))
    return str(uuid.uuid4())

def get_ddb_client():
    global ddb_client
    if ddb_client is not None:
        return ddb_client
    if os.environ.get("RUN_STATE_TABLE_NAME"):
        return finops_common.RealDynamoDB()
    return None

def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))
    
    # Unwrap one legacy nested wrapper if present:
    # { "operation": "prepare", "input": { "operation": "prepare", "input": { ... } } }
    if isinstance(event_data, dict):
        outer_op = (event_data.get("operation") or event_data.get("action") or "").lower()
        outer_input = event_data.get("input")
        if outer_op == "prepare" and isinstance(outer_input, dict):
            inner_op = (outer_input.get("operation") or outer_input.get("action") or "").lower()
            inner_input = outer_input.get("input")
            if inner_op == "prepare" and isinstance(inner_input, dict):
                logger.info("Detected legacy double-wrapped payload, unwrapping one level.")
                event_data = outer_input

    operation = event_data.get("operation") or event_data.get("action") or ""
    op = operation.lower()
    
    if op == "prepare":
        payload = event_data.get("input")
        if not isinstance(payload, dict):
            payload = event_data
            
        account_id = payload.get("account_id") or event_data.get("account_id") or ""
        management_account_id = payload.get("management_account_id") or event_data.get("management_account_id") or ""
        run_id = payload.get("run_id") or event_data.get("run_id") or f"run-{uuid.uuid4()}"
        correlation_id = payload.get("correlation_id") or event_data.get("correlation_id") or str(uuid.uuid4())
        execution_date = payload.get("execution_date") or event_data.get("execution_date") or _utc_date()
        cost_period = payload.get("cost_period") or event_data.get("cost_period") or execution_date[:7]
        
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
        ce_retry = payload.get("ce_retry") or event_data.get("ce_retry") or {"count": 0, "max": 3}
        
        # Schedulers / manual targets
        analysis_targets = payload.get("analysis_targets") or event_data.get("analysis_targets")
        
        is_manual_fallback = False
        # Manual run fallback
        if not analysis_targets:
            if account_id:
                analysis_targets = [{"account_id": account_id}]
                is_manual_fallback = True
                if not management_account_id:
                    management_account_id = account_id
            else:
                analysis_targets = []

        # Get first target account id safely
        first_target_acc = ""
        if analysis_targets:
            first_tgt = analysis_targets[0]
            if isinstance(first_tgt, dict):
                first_target_acc = first_tgt.get("account_id") or ""
            else:
                first_target_acc = str(first_tgt)

        tenant_id_account = account_id or management_account_id or first_target_acc
        tenant_id = payload.get("tenant_id") or event_data.get("tenant_id") or _default_tenant_id(tenant_id_account)

        # Normalize to list of dicts with account_id and tenant_id
        normalized_targets = []
        for target in analysis_targets:
            if isinstance(target, dict):
                new_tgt = target.copy()
                acc_id = new_tgt.get("account_id")
                if not acc_id:
                    acc_id = ""
                new_tgt["account_id"] = acc_id
                
                # Check for explicit target-level tenant_id, or fallback
                tgt_tenant = new_tgt.get("tenant_id")
                if not tgt_tenant:
                    if is_manual_fallback:
                        # Matches the root tenant_id
                        tgt_tenant = tenant_id
                    else:
                        tgt_tenant = _default_tenant_id(acc_id)
                new_tgt["tenant_id"] = tgt_tenant
                normalized_targets.append(new_tgt)
            elif isinstance(target, str):
                normalized_targets.append({
                    "account_id": target,
                    "tenant_id": _default_tenant_id(target)
                })
            else:
                acc_str = str(target)
                normalized_targets.append({
                    "account_id": acc_str,
                    "tenant_id": _default_tenant_id(acc_str)
                })
        analysis_targets = normalized_targets

        # Validate that scheduled runs contain at least one analysis target.
        # Scheduled run check: is_ad_hoc is False, or trigger_type is scheduled, or similar
        trigger_type = payload.get("trigger_type") or event_data.get("trigger_type") or ""
        is_scheduled = (trigger_type == "scheduled") or (not is_ad_hoc and not account_id)
        
        if is_scheduled and not analysis_targets:
            raise ValueError("Scheduled run contains no analysis targets")
            
        if not analysis_targets:
            raise ValueError("No analysis targets or account_id provided for execution")
        
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
            "ce_retry": ce_retry,
            "force_dry_run": False,
            "account_id": account_id or management_account_id,
            "management_account_id": management_account_id,
            "analysis_targets": analysis_targets
        }
        
        response = finops_common.create_response("OK", run_id, correlation_id, "state", details)
        response.tenant_id = tenant_id
        response.is_ad_hoc = is_ad_hoc
        response.force_dry_run = False
        
        resp_dict = response.to_dict()
        resp_dict.update(details)
        logger.info("Response: %s", resp_dict)
        return resp_dict

    if op == "summarize_anomaly_results":
        processed = event_data.get("processed_anomaly_results", [])
        run_id = event_data.get("run_id", "")
        correlation_id = event_data.get("correlation_id", "")

        counts = {}
        failed_anomaly_ids = []
        for item in (processed or []):
            status = item.get("status", "UNKNOWN")
            counts[status] = counts.get(status, 0) + 1
            if status == "PLATFORM_FAILED":
                failed_anomaly_ids.append(item.get("anomaly_id", "unknown"))

        # Mark parent run failed only when platform failures prevent durable audit/status evidence.
        # AI_FAIL_CLOSED is handled inside the Map and does not fail the parent run.
        has_platform_failure = counts.get("PLATFORM_FAILED", 0) > 0
        workflow_status = "FAILED" if has_platform_failure else "COMPLETE"

        result = {
            "workflow_status": workflow_status,
            "counts": counts,
            "total": len(processed or []),
            "failed_anomaly_ids": failed_anomaly_ids,
            "run_id": run_id,
            "correlation_id": correlation_id,
        }
        logger.info("Anomaly summary: %s", result)
        return result

    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    if op == "check_quota":
        is_ad_hoc = event_data.get("is_ad_hoc") or False
        tenant_id = event_data.get("tenant_id") or _default_tenant_id(event.account_id)
        execution_date = event_data.get("execution_date") or _utc_date()
        
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
                            "updated_at": _utc_timestamp()
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
        tenant_id = event_data.get("tenant_id") or _default_tenant_id(event.account_id)
        client = get_ddb_client()

        # Contract §3.3: environment-based lock thresholds
        # prod / prod-* → 1%;  staging → 10%;  sandbox/dev → no automatic lock
        env = os.environ.get("ENVIRONMENT", "").lower()
        if env == "prod" or env.startswith("prod-"):
            lock_threshold_pct = 1.0
        elif env == "staging":
            lock_threshold_pct = 10.0
        else:
            # sandbox / dev – automatic lock disabled; threshold is informational only
            lock_threshold_pct = None

        rollback_rate_30d_pct = 0.0
        containment_status = "OK"

        if client and budget_table:
            try:
                item = client.get_item(budget_table, {"tenant_id": tenant_id})
                if item:
                    # Accept both a pre-computed locked flag and a raw rollback rate
                    locked = item.get("locked") is True or item.get("status") == "LOCKED"
                    rollback_rate_30d_pct = float(item.get("rollback_rate_30d_pct", 0.0))
                    containment_status = item.get("containment_status", "OK")
                    # Apply threshold-based lock when the table does not set locked directly
                    if not locked and lock_threshold_pct is not None:
                        locked = rollback_rate_30d_pct >= lock_threshold_pct
            except Exception as e:
                logger.error("DynamoDB error budget check failed: %s", e)
                raise e
        else:
            # Simulation fallback for unit tests
            locked = bool(event_data.get("simulate_error_budget_locked", False))
            rollback_rate_30d_pct = float(event_data.get("simulate_rollback_rate_30d_pct", 0.0))
            containment_status = "LOCKED" if locked else "OK"

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
            "locked": locked,
            "containment_status": containment_status,
            "rollback_rate_30d_pct": rollback_rate_30d_pct,
            "lock_threshold_pct": lock_threshold_pct,
        })
        logger.info("Response: %s", resp_dict)
        return resp_dict

    status = "NEW"
    table_name = os.environ.get("RUN_STATE_TABLE_NAME")
    if event.is_ad_hoc:
        idempotency_key = f"{event.account_id}:{event.cost_period}:{event.execution_date}:{event.run_id}"
    else:
        idempotency_key = finops_common.idempotency_key(event.account_id, event.cost_period, event.execution_date)
    
    client = get_ddb_client()
    
    if client and table_name:
        if op == "check":
            try:
                item = client.get_item(table_name, {"idempotency_key": idempotency_key})
                if not item:
                    # Fresh run: conditionally write IN_PROGRESS but status is NEW
                    try:
                        client.put_item(table_name, {
                            "idempotency_key": idempotency_key,
                            "status": "IN_PROGRESS",
                            "run_id": event.run_id,
                            "correlation_id": event.correlation_id,
                            "updated_at": _utc_timestamp()
                        }, condition_expression="attribute_not_exists(idempotency_key)")
                        status = "NEW"
                    except Exception as conditional_error:
                        # Race condition: another invocation won the lock
                        # Retrieve and return the existing status instead of failing
                        if "ConditionalCheckFailed" in str(conditional_error) or "ConditionalCheckFailedException" in str(conditional_error):
                            logger.info("Idempotency lock already acquired by another invocation, retrieving existing status")
                            existing_item = client.get_item(table_name, {"idempotency_key": idempotency_key})
                            status = existing_item.get("status", "IN_PROGRESS") if existing_item else "IN_PROGRESS"
                        else:
                            raise conditional_error
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
                    "updated_at": _utc_timestamp()
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
                    "updated_at": _utc_timestamp()
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
    response.tenant_id = event_data.get("tenant_id") or _default_tenant_id(event.account_id)
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
