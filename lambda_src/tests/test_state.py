import pytest
import os
from workers.state import handler
import finops_common

def test_state_simulation_check():
    # Simulation mode check without PRIOR state
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
        "operation": "check"
    }
    
    # Ensure client is cleared
    handler.ddb_client = None
    if "RUN_STATE_TABLE_NAME" in os.environ:
        del os.environ["RUN_STATE_TABLE_NAME"]
        
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "NEW"

    # Simulation mode check with PRIOR state
    event_data_with_prior = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
        "operation": "check",
        "state": {
            "status": "COMPLETED",
            "run_id": "run-1",
            "correlation_id": "corr-1",
            "worker": "state",
            "details": {}
        }
    }
    resp = handler.handle_request(event_data_with_prior, None)
    assert resp["status"] == "COMPLETED"

def test_state_db_check_fresh_and_duplicate():
    os.environ["RUN_STATE_TABLE_NAME"] = "test-run-state-table"
    
    db_items = {}
    put_called = []
    
    def fake_get_item(table_name, key):
        return db_items.get(key["idempotency_key"])
        
    def fake_put_item(table_name, item):
        put_called.append(item)
        db_items[item["idempotency_key"]] = item

    # Assign fake DynamoDB client
    handler.ddb_client = finops_common.FakeDynamoDB(
        get_item_func=fake_get_item,
        put_item_func=fake_put_item
    )

    event_data = {
        "run_id": "run-100",
        "correlation_id": "corr-100",
        "account_id": "123456",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "operation": "check"
    }

    # 1. Fresh check
    resp1 = handler.handle_request(event_data, None)
    assert resp1["status"] == "NEW"
    assert len(put_called) == 1
    assert put_called[0]["status"] == "IN_PROGRESS"

    # 2. Duplicate check when IN_PROGRESS
    resp2 = handler.handle_request(event_data, None)
    assert resp2["status"] == "IN_PROGRESS"

    # 3. Complete operation
    event_data_complete = event_data.copy()
    event_data_complete["operation"] = "complete"
    resp3 = handler.handle_request(event_data_complete, None)
    assert resp3["status"] == "COMPLETED"
    
    # 4. Duplicate check when COMPLETED
    event_data_check = event_data.copy()
    event_data_check["operation"] = "check"
    resp4 = handler.handle_request(event_data_check, None)
    assert resp4["status"] == "COMPLETED"

    # 5. Failed operation
    event_data_failed = event_data.copy()
    event_data_failed["operation"] = "failed"
    resp5 = handler.handle_request(event_data_failed, None)
    assert resp5["status"] == "FAILED"

    # Clean up
    del os.environ["RUN_STATE_TABLE_NAME"]
    handler.ddb_client = None


def test_state_prepare_run_context():
    event_data = {
        "account_id": "123456",
        "operation": "prepare",
        "is_ad_hoc": True,
        "ai_contract_version": "v2"
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["tenant_id"] == "123456"
    assert resp["is_ad_hoc"] is True
    assert resp["ai_contract_version"] == "v2"
    assert "run_id" in resp
    assert "correlation_id" in resp
    assert resp["force_dry_run"] is False
    assert resp["cur_retry"]["max"] == 4
    assert resp["ai_retry"]["max"] == 6
    assert resp["ce_retry"]["max"] == 3

def test_state_prepare_nested_input():
    event_data = {
        "operation": "prepare",
        "input": {
            "account_id": "999888",
            "is_ad_hoc": True
        },
        "ai_contract_version": "v1.0"
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["tenant_id"] == "999888"
    assert resp["is_ad_hoc"] is True
    assert resp["ai_contract_version"] == "v1.0"
    assert resp["ce_retry"]["max"] == 3

def test_state_prepare_defaulting():
    event_data = {
        "operation": "prepare",
        "input": {
            "account_id": "999888"
        }
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["is_ad_hoc"] is False  # Defaults to False


def test_state_check_quota():
    # 1. Quota ok
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
        "operation": "check_quota",
        "is_ad_hoc": True,
        "tenant_id": "tenant-1"
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"

    # 2. Quota exceeded
    event_data_exceeded = event_data.copy()
    event_data_exceeded["simulate_quota_exceeded"] = True
    resp2 = handler.handle_request(event_data_exceeded, None)
    assert resp2["status"] == "QUOTA_EXCEEDED"


def test_state_check_error_budget():
    # 1. Budget locked
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
        "operation": "check_error_budget",
        "tenant_id": "tenant-1",
        "simulate_error_budget_locked": True
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "LOCKED"
    assert resp["locked"] is True
    assert resp["force_dry_run"] is True

    # 2. Budget OK
    event_data["simulate_error_budget_locked"] = False
    resp2 = handler.handle_request(event_data, None)
    assert resp2["status"] == "OK"
    assert resp2["locked"] is False
    assert resp2["force_dry_run"] is False

