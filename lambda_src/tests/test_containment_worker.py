import pytest
from workers.containment_worker import handler
import finops_common

def test_prod_containment_forces_dry_run():
    event_data = {
        "run_id": "run-prod",
        "correlation_id": "corr-prod",
        "cost_period": "2026-06",
        "environment": "prod",
        "action": "apply"
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CONTAINMENT_EVALUATED"
    assert resp["details"]["execution_mode"] == "dry-run"
    assert resp["details"]["containment_status"] == "executed_dry_run"

def test_sandbox_containment_allows_apply():
    event_data = {
        "run_id": "run-sandbox",
        "correlation_id": "corr-sandbox",
        "cost_period": "2026-06",
        "environment": "sandbox",
        "approval_status": "approved",
        "action": "apply"
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CONTAINMENT_EVALUATED"
    assert resp["details"]["execution_mode"] == "apply"
    assert resp["details"]["containment_status"] == "applied"

def test_sandbox_containment_without_approval_defaults_to_dry_run():
    event_data = {
        "run_id": "run-sandbox",
        "correlation_id": "corr-sandbox",
        "cost_period": "2026-06",
        "environment": "sandbox",
        "approval_status": "pending",
        "action": "apply"
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "CONTAINMENT_EVALUATED"
    assert resp["details"]["execution_mode"] == "dry-run"
    assert resp["details"]["containment_status"] == "executed_dry_run"

def test_containment_denied_destructive_actions():
    destructive_actions = ["terminate", "delete", "modify_iam"]

    for action in destructive_actions:
        event_data = {
            "run_id": "run-sandbox",
            "correlation_id": "corr-sandbox",
            "cost_period": "2026-06",
            "environment": "sandbox",
            "approval_status": "approved",
            "action": action
        }

        resp = handler.handle_request(event_data, None)
        assert resp["status"] == "DENIED"
        assert resp["execution_mode"] == "denied"
        assert resp["containment_status"] == "denied"

def test_prod_containment_allows_tag_or_suggest():
    allowed_actions = ["tag", "suggest", "dry-run"]

    for action in allowed_actions:
        event_data = {
            "run_id": "run-prod",
            "correlation_id": "corr-prod",
            "cost_period": "2026-06",
            "environment": "prod",
            "action": action
        }

        resp = handler.handle_request(event_data, None)
        assert resp["status"] == "CONTAINMENT_EVALUATED"
        assert resp["details"]["execution_mode"] == action
