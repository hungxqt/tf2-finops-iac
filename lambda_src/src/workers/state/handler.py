import logging
import os
import re
import uuid
from datetime import timedelta
from typing import Any

import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb_client = None

ACCOUNT_ID_RE = re.compile(r"^[0-9]{12}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
CONTRACT_VERSION_RE = re.compile(r"^v?[0-9]+(\.[0-9]+){0,2}$")
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


def get_ddb_client():
    global ddb_client
    if ddb_client is not None:
        return ddb_client
    if os.environ.get("RUN_STATE_TABLE_NAME"):
        return finops_common.RealDynamoDB()
    return None


def _now_iso() -> str:
    return finops_common.iso_utc_now()


def _ttl_expiry(days: int = 1) -> int:
    return int((finops_common.utc_now() + timedelta(days=days)).timestamp())


def _tenant_id(payload: dict) -> str:
    tenant_id = payload.get("tenant_id")
    if tenant_id:
        return tenant_id
    account_id = payload.get("account_id") or "tenant-default"
    return finops_common.deterministic_tenant_id(str(account_id))


def _batch_type(payload: dict) -> str:
    if payload.get("batch_type"):
        return str(payload["batch_type"])
    if payload.get("is_ad_hoc") or payload.get("trigger_type") == "ad-hoc" or payload.get("action") == "ad-hoc":
        return "ad-hoc"
    return "daily-batch"


def _billing_period_date(payload: dict) -> str:
    return payload.get("billing_period_date") or payload.get("execution_date") or finops_common.utc_now().strftime("%Y-%m-%d")


def _build_idempotency_key(payload: dict) -> str:
    return payload.get("idempotency_key") or finops_common.idempotency_key(
        _tenant_id(payload),
        _billing_period_date(payload),
        _batch_type(payload),
    )


def _validate_contract_fields(payload: dict) -> None:
    account_id = payload.get("account_id")
    if account_id and not ACCOUNT_ID_RE.match(str(account_id)):
        raise ValueError("invalid account_id: expected 12 digits")

    payload_sha256 = payload.get("payload_sha256")
    if payload_sha256 and not SHA256_RE.match(str(payload_sha256)):
        raise ValueError("invalid payload_sha256: expected lowercase SHA-256 hex")

    version = payload.get("ai_contract_version") or payload.get("source_data_version")
    if version and not CONTRACT_VERSION_RE.match(str(version)):
        raise ValueError("invalid contract version")


def _state_response(status: str, event: finops_common.Event, details: dict, payload: dict) -> dict:
    response = finops_common.create_response(status, event.run_id, event.correlation_id, "state", details)
    response.tenant_id = _tenant_id(payload)
    response.is_ad_hoc = bool(payload.get("is_ad_hoc", False))
    response.force_dry_run = bool(payload.get("force_dry_run", False))
    if payload.get("payload_sha256"):
        response.payload_sha256 = payload["payload_sha256"]
    if payload.get("request_timestamp"):
        response.request_timestamp = payload["request_timestamp"]

    resp_dict = response.to_dict()
    resp_dict.update({
        "tenant_id": response.tenant_id,
        "is_ad_hoc": response.is_ad_hoc,
        "force_dry_run": response.force_dry_run,
    })
    return resp_dict


def _write_run_state(client, table_name: str, item: dict) -> None:
    try:
        client.put_item(table_name, item, condition_expression="attribute_not_exists(idempotency_key)")
    except TypeError:
        client.put_item(table_name, item)


def _is_conditional_check_failed(error: Exception) -> bool:
    response = getattr(error, "response", {})
    code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
    return code == "ConditionalCheckFailedException" or "ConditionalCheckFailedException" in str(error)


def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))

    operation = event_data.get("operation") or event_data.get("action") or ""
    op = operation.lower()

    if op == "prepare":
        payload = event_data.get("input")
        if not isinstance(payload, dict):
            payload = event_data

        execution_date = payload.get("execution_date") or event_data.get("execution_date") or finops_common.utc_now().strftime("%Y-%m-%d")
        cost_period = payload.get("cost_period") or event_data.get("cost_period") or execution_date[:7]
        account_id = payload.get("account_id") or event_data.get("account_id") or ""
        tenant_id = _tenant_id({**event_data, **payload})
        run_id = payload.get("run_id") or event_data.get("run_id") or f"run-{uuid.uuid4()}"
        correlation_id = payload.get("correlation_id") or event_data.get("correlation_id") or run_id
        is_ad_hoc = bool(payload.get("is_ad_hoc") or event_data.get("is_ad_hoc") or payload.get("action") == "ad-hoc" or event_data.get("action") == "ad-hoc")
        merged = {**event_data, **payload, "tenant_id": tenant_id, "execution_date": execution_date, "is_ad_hoc": is_ad_hoc}

        details = {
            "run_id": run_id,
            "correlation_id": correlation_id,
            "execution_date": execution_date,
            "billing_period_date": _billing_period_date(merged),
            "cost_period": cost_period,
            "tenant_id": tenant_id,
            "account_id": account_id,
            "is_ad_hoc": is_ad_hoc,
            "batch_type": _batch_type(merged),
            "idempotency_key": _build_idempotency_key(merged),
            "ai_contract_version": event_data.get("ai_contract_version") or payload.get("ai_contract_version") or "v1",
            "cur_retry": payload.get("cur_retry") or event_data.get("cur_retry") or {"count": 0, "max": 4},
            "ai_retry": payload.get("ai_retry") or event_data.get("ai_retry") or {"count": 0, "max": 6},
            "force_dry_run": False,
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
        _validate_contract_fields(event_data)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    if op == "check_quota":
        is_ad_hoc = bool(event_data.get("is_ad_hoc", False))
        tenant_id = _tenant_id(event_data)
        execution_date = _billing_period_date(event_data)
        status = "OK"
        client = get_ddb_client()
        table_name = os.environ.get("RUN_STATE_TABLE_NAME")

        if is_ad_hoc:
            quota_key = f"quota:{tenant_id}:{execution_date}"
            if client and table_name:
                item = client.get_item(table_name, {"idempotency_key": quota_key})
                count = int(item.get("count", 0)) if item else 0
                if count >= 5:
                    logger.warning("Ad-hoc quota exceeded for tenant %s", tenant_id)
                    status = "QUOTA_EXCEEDED"
                else:
                    client.put_item(table_name, {
                        "idempotency_key": quota_key,
                        "count": count + 1,
                        "status": "QUOTA_TRACKING",
                        "tenant_id": tenant_id,
                        "updated_at": _now_iso(),
                        "ttl_expiry": _ttl_expiry(),
                    })
            elif event_data.get("simulate_quota_exceeded"):
                status = "QUOTA_EXCEEDED"

        return _state_response(status, event, {"is_ad_hoc": is_ad_hoc}, {**event_data, "tenant_id": tenant_id, "is_ad_hoc": is_ad_hoc})

    if op == "check_error_budget":
        budget_table = os.environ.get("ERROR_BUDGET_TABLE_NAME")
        tenant_id = _tenant_id(event_data)
        locked = False
        client = get_ddb_client()

        if client and budget_table:
            item = client.get_item(budget_table, {"tenant_id": tenant_id})
            if item:
                locked = item.get("locked") is True or item.get("status") == "LOCKED"
        else:
            locked = bool(event_data.get("simulate_error_budget_locked", False))

        payload = {**event_data, "tenant_id": tenant_id, "force_dry_run": locked or bool(event_data.get("force_dry_run", False))}
        resp = _state_response("LOCKED" if locked else "OK", event, {"locked": locked}, payload)
        resp["locked"] = locked
        resp["force_dry_run"] = payload["force_dry_run"]
        return resp

    table_name = os.environ.get("RUN_STATE_TABLE_NAME")
    idempotency_key = _build_idempotency_key(event_data)
    payload_sha256 = event_data.get("payload_sha256", "")
    client = get_ddb_client()
    status = "NEW"
    existing = None

    if client and table_name:
        existing = client.get_item(table_name, {"idempotency_key": idempotency_key})

        if op == "check":
            if existing:
                existing_hash = existing.get("payload_sha256")
                if existing_hash and payload_sha256 and existing_hash != payload_sha256:
                    status = "ERR_IDEMPOTENCY_MISMATCH"
                else:
                    status = existing.get("status", "IN_PROGRESS")
            else:
                item = {
                    "idempotency_key": idempotency_key,
                    "payload_sha256": payload_sha256,
                    "status": "IN_PROGRESS",
                    "run_id": event.run_id,
                    "correlation_id": event.correlation_id,
                    "tenant_id": _tenant_id(event_data),
                    "billing_period_date": _billing_period_date(event_data),
                    "batch_type": _batch_type(event_data),
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                    "ttl_expiry": _ttl_expiry(),
                }
                try:
                    _write_run_state(client, table_name, item)
                    status = "NEW"
                except Exception as e:
                    if not _is_conditional_check_failed(e):
                        raise
                    existing = client.get_item(table_name, {"idempotency_key": idempotency_key}) or {}
                    existing_hash = existing.get("payload_sha256")
                    if existing_hash and payload_sha256 and existing_hash != payload_sha256:
                        status = "ERR_IDEMPOTENCY_MISMATCH"
                    else:
                        status = existing.get("status", "IN_PROGRESS")
        elif op in {"complete", "failed", "fail_contract_check"}:
            status = {
                "complete": "COMPLETED",
                "failed": "FAILED",
                "fail_contract_check": "FAILED_CONTRACT_CHECK",
            }[op]
            item = {
                "idempotency_key": idempotency_key,
                "payload_sha256": payload_sha256 or (existing or {}).get("payload_sha256", ""),
                "status": status,
                "run_id": event.run_id,
                "correlation_id": event.correlation_id,
                "tenant_id": _tenant_id(event_data),
                "billing_period_date": _billing_period_date(event_data),
                "batch_type": _batch_type(event_data),
                "created_at": (existing or {}).get("created_at", _now_iso()),
                "updated_at": _now_iso(),
                "ttl_expiry": (existing or {}).get("ttl_expiry", _ttl_expiry()),
            }
            if event_data.get("failure_code"):
                item["failure_code"] = event_data["failure_code"]
            client.put_item(table_name, item)
    else:
        if op == "check":
            status = "COMPLETED" if "state" in event_data else "NEW"
        elif op == "complete":
            status = "COMPLETED"
        elif op == "failed":
            status = "FAILED"
        elif op == "fail_contract_check":
            status = "FAILED_CONTRACT_CHECK"
        elif event_data.get("requested_state_status"):
            status = event_data["requested_state_status"]

    details = {
        "account_id": event.account_id,
        "cost_period": event.cost_period,
        "execution_date": event.execution_date,
        "billing_period_date": _billing_period_date(event_data),
        "batch_type": _batch_type(event_data),
        "idempotency_key": idempotency_key,
        "ttl_expiry": (existing or {}).get("ttl_expiry") if existing else None,
    }
    if payload_sha256:
        details["payload_sha256"] = payload_sha256
    if event_data.get("failure_code"):
        details["failure_code"] = event_data["failure_code"]

    resp = _state_response(status, event, details, event_data)
    logger.info("Response: %s", resp)
    return resp