import pytest
import os
from workers.router import handler
import finops_common

def test_router_without_anomaly():
    # If AI has not found an anomaly, alerts are not delivered
    event_data = {
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "cost_period": "2026-06",
        "ai": {
            "status": "OK",
            "run_id": "run-1",
            "correlation_id": "corr-1",
            "worker": "ai_client",
            "anomaly_found": False,
            "details": {}
        }
    }
    
    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "ROUTED"
    assert resp["route_target"] == "engineering"
    
    finance = resp["details"]["finance_route"]
    engineering = resp["details"]["engineering_route"]
    
    assert finance["deliver"] is False
    assert engineering["deliver"] is False

def test_router_with_critical_anomaly():
    os.environ["ROUTING_STATE_TABLE_NAME"] = "test-routing-table"
    
    put_called = []
    def fake_put_item(table_name, item):
        put_called.append(item)
        
    handler.ddb_client = finops_common.FakeDynamoDB(put_item_func=fake_put_item)

    event_data = {
        "run_id": "run-2",
        "correlation_id": "corr-2",
        "account_id": "123456",
        "cost_period": "2026-06",
        "execution_date": "2026-06-24",
        "ai": {
            "status": "OK",
            "run_id": "run-2",
            "correlation_id": "corr-2",
            "worker": "ai_client",
            "anomaly_found": True,
            "anomaly_id": "ANOM-CRIT-999",
            "severity": "critical",
            "confidence": 0.98,
            "details": {}
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "ROUTED"
    assert resp["route_target"] == "engineering"

    finance = resp["details"]["finance_route"]
    engineering = resp["details"]["engineering_route"]

    # Critical anomaly routes to BOTH with delivery enabled
    assert finance["deliver"] is True
    assert finance["action_required"] is True
    assert "CRITICAL ALERT" in finance["summary"]
    # Verify no raw sensitive data or evidence is in the message
    assert "ANOM-CRIT-999" in finance["message"]
    assert "evidence" not in finance["message"]

    assert engineering["deliver"] is True
    assert engineering["action_required"] is True
    assert "CRITICAL CONTAINMENT" in engineering["summary"]
    assert "ANOM-CRIT-999" in engineering["message"]

    # Verify optional DB persistence was called
    assert len(put_called) == 1
    assert put_called[0]["run_id"] == "run-2"
    assert put_called[0]["finance_deliver"] is True
    assert put_called[0]["eng_deliver"] is True
    assert put_called[0]["route_target"] == "engineering"

    # Clean up
    del os.environ["ROUTING_STATE_TABLE_NAME"]
    handler.ddb_client = None

def test_router_with_medium_anomaly():
    event_data = {
        "run_id": "run-3",
        "correlation_id": "corr-3",
        "cost_period": "2026-06",
        "ai": {
            "status": "OK",
            "run_id": "run-3",
            "correlation_id": "corr-3",
            "worker": "ai_client",
            "anomaly_found": True,
            "anomaly_id": "ANOM-MED-555",
            "severity": "medium",
            "confidence": 0.75,
            "details": {}
        }
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "ROUTED"
    # Medium severity anomaly routes target to finance only
    assert resp["route_target"] == "finance"

    finance = resp["details"]["finance_route"]
    engineering = resp["details"]["engineering_route"]

    assert finance["deliver"] is True
    assert finance["action_required"] is False
    
    assert engineering["deliver"] is False
