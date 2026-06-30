import pytest
import os
import uuid
from workers.state import handler
import finops_common


def expected_tenant_id(account_id):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tf2-finops:{account_id}"))

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
    assert resp["tenant_id"] == expected_tenant_id("123456")
    uuid.UUID(resp["correlation_id"])
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
    assert resp["tenant_id"] == expected_tenant_id("999888")
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


def test_state_prepare_scheduled_multi_account():
    event_data = {
        "operation": "prepare",
        "input": {
            "management_account_id": "111111111111",
            "analysis_targets": ["222222222222", "333333333333"],
            "trigger_type": "scheduled",
            "is_ad_hoc": False
        }
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["management_account_id"] == "111111111111"
    assert resp["analysis_targets"] == [
        {"account_id": "222222222222", "tenant_id": handler._default_tenant_id("222222222222")},
        {"account_id": "333333333333", "tenant_id": handler._default_tenant_id("333333333333")}
    ]
    assert resp["account_id"] == "111111111111"
    assert resp["is_ad_hoc"] is False

def test_state_prepare_manual_fallback():
    event_data = {
        "operation": "prepare",
        "input": {
            "account_id": "444444444444",
            "is_ad_hoc": True
        }
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["management_account_id"] == "444444444444"
    assert resp["analysis_targets"] == [{"account_id": "444444444444", "tenant_id": resp["tenant_id"]}]
    assert resp["account_id"] == "444444444444"
    assert resp["is_ad_hoc"] is True

def test_state_prepare_legacy_double_wrapped():
    event_data = {
        "operation": "prepare",
        "input": {
            "operation": "prepare",
            "input": {
                "management_account_id": "093490087544",
                "analysis_targets": ["336805808730"],
                "trigger_type": "scheduled",
                "is_ad_hoc": False
            }
        }
    }
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["management_account_id"] == "093490087544"
    assert resp["analysis_targets"] == [{"account_id": "336805808730", "tenant_id": handler._default_tenant_id("336805808730")}]
    assert resp["account_id"] == "093490087544"
    assert resp["is_ad_hoc"] is False

def test_state_prepare_scheduled_missing_targets_fails():
    event_data = {
        "operation": "prepare",
        "input": {
            "management_account_id": "111111111111",
            "analysis_targets": [],
            "trigger_type": "scheduled"
        }
    }
    with pytest.raises(ValueError, match="Scheduled run contains no analysis targets"):
        handler.handle_request(event_data, None)



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
    # 1. Budget locked (simulation)
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
    # New fields must be present
    assert "containment_status" in resp
    assert "rollback_rate_30d_pct" in resp
    assert "lock_threshold_pct" in resp

    # 2. Budget OK
    event_data["simulate_error_budget_locked"] = False
    resp2 = handler.handle_request(event_data, None)
    assert resp2["status"] == "OK"
    assert resp2["locked"] is False
    assert resp2["force_dry_run"] is False


def test_state_error_budget_real_dynamodb_lookup():
    """check_error_budget reads the real DynamoDB error budget table when configured."""
    os.environ["ERROR_BUDGET_TABLE_NAME"] = "finops-error-budget-test"
    # Reuse the run_state table env to trigger real DDB client mode in get_ddb_client
    os.environ["RUN_STATE_TABLE_NAME"] = "finops-run-state-test"

    db_items = {}

    def fake_get_item(table_name, key):
        return db_items.get(key.get("tenant_id"))

    handler.ddb_client = finops_common.FakeDynamoDB(
        get_item_func=fake_get_item,
        put_item_func=lambda table, item: None
    )

    event_data = {
        "run_id": "run-budget-1",
        "correlation_id": "corr-budget-1",
        "cost_period": "2026-06",
        "operation": "check_error_budget",
        "tenant_id": "budget-tenant-1",
    }

    # 1. No item in table → budget OK
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "OK"
    assert resp["locked"] is False
    assert resp["rollback_rate_30d_pct"] == 0.0

    # 2. Item present with locked=True
    db_items["budget-tenant-1"] = {
        "tenant_id": "budget-tenant-1",
        "locked": True,
        "containment_status": "LOCKED",
        "rollback_rate_30d_pct": 5.0,
    }
    resp2 = handler.handle_request(event_data, None)
    assert resp2["status"] == "LOCKED"
    assert resp2["locked"] is True
    assert resp2["containment_status"] == "LOCKED"
    assert resp2["rollback_rate_30d_pct"] == 5.0
    assert resp2["force_dry_run"] is True

    del os.environ["ERROR_BUDGET_TABLE_NAME"]
    del os.environ["RUN_STATE_TABLE_NAME"]
    handler.ddb_client = None


def test_state_error_budget_prod_threshold_triggers_lock():
    """For prod environment, rollback_rate >= 1% triggers automatic lock."""
    os.environ["ERROR_BUDGET_TABLE_NAME"] = "finops-error-budget-test"
    os.environ["RUN_STATE_TABLE_NAME"] = "finops-run-state-test"
    os.environ["ENVIRONMENT"] = "prod"

    def fake_get_item(table_name, key):
        return {
            "tenant_id": "tenant-prod",
            "locked": False,           # not pre-locked
            "rollback_rate_30d_pct": 1.5,  # exceeds 1% threshold
            "containment_status": "ELEVATED",
        }

    handler.ddb_client = finops_common.FakeDynamoDB(
        get_item_func=fake_get_item,
        put_item_func=lambda table, item: None
    )

    event_data = {
        "run_id": "run-prod",
        "correlation_id": "corr-prod",
        "cost_period": "2026-06",
        "operation": "check_error_budget",
        "tenant_id": "tenant-prod",
    }
    resp = handler.handle_request(event_data, None)
    assert resp["locked"] is True, "prod: rollback_rate >= 1% must trigger lock"
    assert resp["lock_threshold_pct"] == 1.0
    assert resp["force_dry_run"] is True

    del os.environ["ENVIRONMENT"]
    del os.environ["ERROR_BUDGET_TABLE_NAME"]
    del os.environ["RUN_STATE_TABLE_NAME"]
    handler.ddb_client = None


def test_state_error_budget_staging_threshold():
    """For staging environment, rollback_rate >= 10% triggers automatic lock."""
    os.environ["ERROR_BUDGET_TABLE_NAME"] = "finops-error-budget-staging"
    os.environ["RUN_STATE_TABLE_NAME"] = "finops-run-state-staging"
    os.environ["ENVIRONMENT"] = "staging"

    def fake_get_item(table_name, key):
        return {
            "tenant_id": "tenant-staging",
            "locked": False,
            "rollback_rate_30d_pct": 9.9,  # below threshold
            "containment_status": "OK",
        }

    handler.ddb_client = finops_common.FakeDynamoDB(
        get_item_func=fake_get_item,
        put_item_func=lambda table, item: None
    )

    event_data = {
        "run_id": "run-stg",
        "correlation_id": "corr-stg",
        "cost_period": "2026-06",
        "operation": "check_error_budget",
        "tenant_id": "tenant-staging",
    }
    resp = handler.handle_request(event_data, None)
    assert resp["locked"] is False, "staging: rollback_rate < 10% must not trigger lock"
    assert resp["lock_threshold_pct"] == 10.0

    del os.environ["ENVIRONMENT"]
    del os.environ["ERROR_BUDGET_TABLE_NAME"]
    del os.environ["RUN_STATE_TABLE_NAME"]
    handler.ddb_client = None


def test_state_error_budget_sandbox_no_automatic_lock():
    """For sandbox/dev environment, threshold is None and no automatic lock is applied."""
    os.environ["ERROR_BUDGET_TABLE_NAME"] = "finops-error-budget-sandbox"
    os.environ["RUN_STATE_TABLE_NAME"] = "finops-run-state-sandbox"
    os.environ["ENVIRONMENT"] = "sandbox"

    def fake_get_item(table_name, key):
        return {
            "tenant_id": "tenant-sbx",
            "locked": False,
            "rollback_rate_30d_pct": 99.0,  # very high but sandbox has no automatic lock
            "containment_status": "OK",
        }

    handler.ddb_client = finops_common.FakeDynamoDB(
        get_item_func=fake_get_item,
        put_item_func=lambda table, item: None
    )

    event_data = {
        "run_id": "run-sbx",
        "correlation_id": "corr-sbx",
        "cost_period": "2026-06",
        "operation": "check_error_budget",
        "tenant_id": "tenant-sbx",
    }
    resp = handler.handle_request(event_data, None)
    assert resp["locked"] is False, "sandbox: automatic lock must not be applied regardless of rate"
    assert resp["lock_threshold_pct"] is None

    del os.environ["ENVIRONMENT"]
    del os.environ["ERROR_BUDGET_TABLE_NAME"]
    del os.environ["RUN_STATE_TABLE_NAME"]
    handler.ddb_client = None


def test_state_prepare_propagation_details():
    # 1. State Lambda scheduled multi-account prepare returns each target with deterministic per-account tenant_id.
    event_data_multi = {
        "operation": "prepare",
        "input": {
            "management_account_id": "111111111111",
            "analysis_targets": ["222222222222", "333333333333"],
            "trigger_type": "scheduled",
            "is_ad_hoc": False
        }
    }
    resp_multi = handler.handle_request(event_data_multi, None)
    assert resp_multi["status"] == "OK"
    targets = resp_multi["analysis_targets"]
    assert len(targets) == 2
    assert targets[0]["account_id"] == "222222222222"
    assert targets[0]["tenant_id"] == handler._default_tenant_id("222222222222")
    assert targets[1]["account_id"] == "333333333333"
    assert targets[1]["tenant_id"] == handler._default_tenant_id("333333333333")

    # 2. Manual single-account fallback still gets one target with matching tenant_id.
    event_data_manual = {
        "operation": "prepare",
        "input": {
            "account_id": "444444444444",
            "tenant_id": "my-special-tenant",
            "is_ad_hoc": True
        }
    }
    resp_manual = handler.handle_request(event_data_manual, None)
    assert resp_manual["status"] == "OK"
    assert resp_manual["tenant_id"] == "my-special-tenant"
    assert resp_manual["analysis_targets"] == [{"account_id": "444444444444", "tenant_id": "my-special-tenant"}]

    # 3. Explicit target-level tenant_id is preserved.
    event_data_explicit = {
        "operation": "prepare",
        "input": {
            "management_account_id": "111111111111",
            "analysis_targets": [
                {"account_id": "222222222222", "tenant_id": "explicit-tenant-2"},
                "333333333333"
            ],
            "trigger_type": "scheduled",
            "is_ad_hoc": False
        }
    }
    resp_explicit = handler.handle_request(event_data_explicit, None)
    assert resp_explicit["status"] == "OK"
    explicit_targets = resp_explicit["analysis_targets"]
    assert len(explicit_targets) == 2
    assert explicit_targets[0]["account_id"] == "222222222222"
    assert explicit_targets[0]["tenant_id"] == "explicit-tenant-2"
    assert explicit_targets[1]["account_id"] == "333333333333"
    assert explicit_targets[1]["tenant_id"] == handler._default_tenant_id("333333333333")


def test_state_adhoc_run_state_key_uniqueness():
    os.environ["RUN_STATE_TABLE_NAME"] = "test-run-state-table"
    
    put_called = []
    
    def fake_get_item(table_name, key):
        return None
        
    def fake_put_item(table_name, item):
        put_called.append(item)
        
    # Assign fake DynamoDB client
    handler.ddb_client = finops_common.FakeDynamoDB(
        get_item_func=fake_get_item,
        put_item_func=fake_put_item
    )

    # Ad-hoc run 1
    event_data_1 = {
        "run_id": "run-adhoc-1",
        "correlation_id": "corr-adhoc-1",
        "account_id": "123456",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "operation": "check",
        "is_ad_hoc": True
    }
    resp1 = handler.handle_request(event_data_1, None)
    assert resp1["status"] == "NEW"
    assert len(put_called) == 1
    key1 = put_called[0]["idempotency_key"]
    assert "run-adhoc-1" in key1
    
    # Ad-hoc run 2 on same day
    event_data_2 = event_data_1.copy()
    event_data_2["run_id"] = "run-adhoc-2"
    resp2 = handler.handle_request(event_data_2, None)
    assert resp2["status"] == "NEW"
    assert len(put_called) == 2
    key2 = put_called[1]["idempotency_key"]
    assert "run-adhoc-2" in key2
    assert key1 != key2

    del os.environ["RUN_STATE_TABLE_NAME"]
    handler.ddb_client = None

