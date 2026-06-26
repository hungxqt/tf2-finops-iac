import os

import pytest

import finops_common
from workers.state import handler

VALID_HASH = "a" * 64
OTHER_HASH = "b" * 64


def reset_handler(monkeypatch):
    handler.ddb_client = None
    monkeypatch.delenv("RUN_STATE_TABLE_NAME", raising=False)
    monkeypatch.delenv("ERROR_BUDGET_TABLE_NAME", raising=False)


def base_event(**overrides):
    event = {
        "run_id": "run-100",
        "correlation_id": "corr-100",
        "account_id": "123456789012",
        "tenant_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "source_data_version": "v3.2.0",
        "ai_contract_version": "v1.4.0",
        "payload_sha256": VALID_HASH,
    }
    event.update(overrides)
    return event


def test_state_simulation_check(monkeypatch):
    reset_handler(monkeypatch)

    resp = handler.handle_request(base_event(operation="check"), None)
    assert resp["status"] == "NEW"

    resp = handler.handle_request(base_event(operation="check", state={"status": "COMPLETED"}), None)
    assert resp["status"] == "COMPLETED"


def test_state_db_check_fresh_duplicate_complete_failed_and_contract_failure(monkeypatch):
    monkeypatch.setenv("RUN_STATE_TABLE_NAME", "finops-idempotency-sandbox")
    db = finops_common.FakeDynamoDB()
    handler.ddb_client = db

    event_data = base_event(operation="check")

    resp1 = handler.handle_request(event_data, None)
    assert resp1["status"] == "NEW"
    assert resp1["details"]["idempotency_key"] == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d:2026-06-24:daily-batch"

    item = db.get_item("finops-idempotency-sandbox", {"idempotency_key": resp1["details"]["idempotency_key"]})
    assert item["status"] == "IN_PROGRESS"
    assert item["payload_sha256"] == VALID_HASH
    assert item["ttl_expiry"] > 0
    assert item["batch_type"] == "daily-batch"

    resp2 = handler.handle_request(event_data, None)
    assert resp2["status"] == "IN_PROGRESS"

    mismatch = base_event(operation="check", payload_sha256=OTHER_HASH)
    resp_mismatch = handler.handle_request(mismatch, None)
    assert resp_mismatch["status"] == "ERR_IDEMPOTENCY_MISMATCH"

    resp3 = handler.handle_request(base_event(operation="complete"), None)
    assert resp3["status"] == "COMPLETED"

    resp4 = handler.handle_request(base_event(operation="check"), None)
    assert resp4["status"] == "COMPLETED"

    resp5 = handler.handle_request(base_event(operation="failed", failure_code="ERR_SERVICE_DOWN"), None)
    assert resp5["status"] == "FAILED"
    assert resp5["details"]["failure_code"] == "ERR_SERVICE_DOWN"

    resp6 = handler.handle_request(base_event(operation="fail_contract_check", failure_code="ERR_INVALID_SCHEMA"), None)
    assert resp6["status"] == "FAILED_CONTRACT_CHECK"


def test_state_conditional_write_race_returns_existing_status(monkeypatch):
    monkeypatch.setenv("RUN_STATE_TABLE_NAME", "finops-idempotency-sandbox")
    db = finops_common.FakeDynamoDB()
    event_data = base_event(operation="check")
    idempotency_key = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d:2026-06-24:daily-batch"

    def race_put(table_name, item):
        db.items.setdefault(table_name, {})[idempotency_key] = {
            **item,
            "status": "IN_PROGRESS",
            "payload_sha256": VALID_HASH,
        }
        raise ValueError("ConditionalCheckFailedException")

    db.put_item_func = race_put
    handler.ddb_client = db

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "IN_PROGRESS"


def test_fake_dynamodb_isolates_items_by_table():
    db = finops_common.FakeDynamoDB()
    tenant_id = base_event()["tenant_id"]

    db.put_item("error-budget", {"tenant_id": tenant_id, "status": "LOCKED"})

    assert db.get_item("error-budget", {"tenant_id": tenant_id})["status"] == "LOCKED"
    assert db.get_item("finops-idempotency-sandbox", {"idempotency_key": tenant_id}) is None


def test_state_prepare_run_context():
    event_data = {
        "account_id": "123456789012",
        "operation": "prepare",
        "is_ad_hoc": True,
        "ai_contract_version": "v1.4.0",
        "execution_date": "2026-06-24",
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["tenant_id"] == finops_common.deterministic_tenant_id("123456789012")
    assert resp["is_ad_hoc"] is True
    assert resp["batch_type"] == "ad-hoc"
    assert resp["idempotency_key"].endswith(":2026-06-24:ad-hoc")
    assert resp["ai_contract_version"] == "v1.4.0"
    assert "run_id" in resp
    assert "correlation_id" in resp
    assert resp["force_dry_run"] is False
    assert resp["cur_retry"]["max"] == 4
    assert resp["ai_retry"]["max"] == 6


def test_state_prepare_nested_input():
    event_data = {
        "operation": "prepare",
        "input": {
            "account_id": "999888777666",
            "is_ad_hoc": True,
            "execution_date": "2026-06-24",
        },
        "ai_contract_version": "v1.4.0",
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["tenant_id"] == finops_common.deterministic_tenant_id("999888777666")
    assert resp["is_ad_hoc"] is True
    assert resp["ai_contract_version"] == "v1.4.0"


def test_state_prepare_defaulting():
    resp = handler.handle_request({"operation": "prepare", "input": {"account_id": "999888777666"}}, None)
    assert resp["status"] == "OK"
    assert resp["is_ad_hoc"] is False


def test_state_check_quota_enforces_five_ad_hoc_runs_per_tenant_day(monkeypatch):
    monkeypatch.setenv("RUN_STATE_TABLE_NAME", "finops-idempotency-sandbox")
    handler.ddb_client = finops_common.FakeDynamoDB()

    event_data = base_event(operation="check_quota", is_ad_hoc=True)
    for _ in range(5):
        resp = handler.handle_request(event_data, None)
        assert resp["status"] == "OK"

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "QUOTA_EXCEEDED"


def test_state_check_error_budget_reads_table_and_forces_dry_run(monkeypatch):
    monkeypatch.setenv("RUN_STATE_TABLE_NAME", "finops-idempotency-sandbox")
    monkeypatch.setenv("ERROR_BUDGET_TABLE_NAME", "finops-sandbox-error-budget")
    db = finops_common.FakeDynamoDB()
    tenant_id = base_event()["tenant_id"]
    db.put_item("finops-sandbox-error-budget", {"tenant_id": tenant_id, "status": "LOCKED"})
    handler.ddb_client = db

    resp = handler.handle_request(base_event(operation="check_error_budget"), None)
    assert resp["status"] == "LOCKED"
    assert resp["locked"] is True
    assert resp["force_dry_run"] is True


def test_state_check_error_budget_simulation(monkeypatch):
    reset_handler(monkeypatch)
    resp = handler.handle_request(base_event(operation="check_error_budget", simulate_error_budget_locked=True), None)
    assert resp["status"] == "LOCKED"
    assert resp["locked"] is True
    assert resp["force_dry_run"] is True

    resp2 = handler.handle_request(base_event(operation="check_error_budget", simulate_error_budget_locked=False), None)
    assert resp2["status"] == "OK"
    assert resp2["locked"] is False
    assert resp2["force_dry_run"] is False


def test_state_rejects_invalid_schema_fields(monkeypatch):
    reset_handler(monkeypatch)
    with pytest.raises(ValueError, match="invalid account_id"):
        handler.handle_request(base_event(operation="check", account_id="123456"), None)

    with pytest.raises(ValueError, match="invalid payload_sha256"):
        handler.handle_request(base_event(operation="check", payload_sha256="not-a-hash"), None)

    with pytest.raises(ValueError, match="invalid contract version"):
        handler.handle_request(base_event(operation="check", ai_contract_version="latest"), None)