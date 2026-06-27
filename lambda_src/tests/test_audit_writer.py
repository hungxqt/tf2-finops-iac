import pytest
import os
import json
from workers.audit_writer import handler
import finops_common

def test_audit_writer_s3_and_dynamodb_integration():
    os.environ["AUDIT_BUCKET_NAME"] = "my-test-audit-bucket"
    os.environ["AUDIT_TABLE_NAME"] = "my-test-audit-table"

    s3_put_called = []
    ddb_put_called = []

    def fake_s3_put(bucket, key, body):
        s3_put_called.append({
            "bucket": bucket,
            "key": key,
            "body": body
        })

    def fake_ddb_put(table, item):
        ddb_put_called.append({
            "table": table,
            "item": item
        })

    handler.s3_client = finops_common.FakeS3(put_object_func=fake_s3_put)
    handler.ddb_client = finops_common.FakeDynamoDB(put_item_func=fake_ddb_put)

    event_data = {
        "run_id": "run-123",
        "correlation_id": "corr-456",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-23",
        "environment": "sandbox",
        "approval_status": "pending",
        "telemetry_quality": 1.0
    }

    resp = handler.handle_request(event_data, None)
    assert resp["status"] == "AUDIT_WRITTEN"
    assert resp["audit_id"] == "audit-pending_approval-corr-456"
    assert resp["audit_uri"] == "s3://my-test-audit-bucket/audit/account_id=123456789012/year=2026/month=06/audit-pending_approval-corr-456.json"

    # Assert S3 put
    assert len(s3_put_called) == 1
    assert s3_put_called[0]["bucket"] == "my-test-audit-bucket"
    assert s3_put_called[0]["key"] == "audit/account_id=123456789012/year=2026/month=06/audit-pending_approval-corr-456.json"
    
    body = json.loads(s3_put_called[0]["body"].decode("utf-8"))
    assert body["audit_id"] == "audit-pending_approval-corr-456"
    assert body["correlation_id"] == "corr-456"
    assert body["actor"] == "tf2-finops-orchestrator"
    assert body["retention_period"] == "90 days"
    assert body["rollback_path"] == "revert-resource-tags"
    assert body["approval_status"] == "pending"
    assert body["account_id"] == "123456789012"
    assert body["resource_id"] == "N/A"
    assert body["owner"] == "untagged"
    assert body["target_owner"] == "untagged"
    assert body["audit_score"] == 1.0
    assert body["numeric_audit_score"] == 1.0

    # Assert DynamoDB index
    assert len(ddb_put_called) == 1
    assert ddb_put_called[0]["table"] == "my-test-audit-table"
    assert ddb_put_called[0]["item"]["audit_id"] == "audit-pending_approval-corr-456"
    assert ddb_put_called[0]["item"]["correlation_id"] == "corr-456"
    assert ddb_put_called[0]["item"]["audit_type"] == "PENDING_APPROVAL"

    # Clean up
    del os.environ["AUDIT_BUCKET_NAME"]
    del os.environ["AUDIT_TABLE_NAME"]
    handler.s3_client = None
    handler.ddb_client = None

def test_audit_writer_sandbox_applied():
    handler.s3_client = None
    handler.ddb_client = None

    event_data = {
        "run_id": "run-123",
        "correlation_id": "corr-456",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-23",
        "environment": "sandbox",
        "action": "apply"
    }

    resp = handler.handle_request(event_data, None)
    assert resp["details"]["applied_after_state"] == "containment_applied"

def test_audit_writer_fail_closed_payload_records_workflow_failure():
    handler.s3_client = None
    handler.ddb_client = None

    event_data = {
        "run_id": "run-fail-closed",
        "correlation_id": "corr-fail-closed",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-26",
        "tenant_id": "tenant-123",
        "environment": "sandbox",
        "action": "fail-closed",
        "error": {
            "Error": "AIEngineFailClosed",
            "Cause": "AI Engine returned an unsuccessful or low-confidence detection response."
        }
    }

    resp = handler.handle_request(event_data, None)
    details = resp["details"]
    assert resp["status"] == "AUDIT_WRITTEN"
    assert details["audit_type"] == "WORKFLOW_FAILURE"
    assert details["idempotency_key"] == "123456789012:2026-06:2026-06-26"
    assert details["account_id"] == "123456789012"
    assert details["execution_mode"] == "dry-run"
    assert details["proposed_after_state"] == "workflow_failed_closed"
    assert details["error_details"]["Error"] == "AIEngineFailClosed"

def test_audit_writer_workflow_denies_prod_unsafe_action():
    handler.s3_client = None
    handler.ddb_client = None

    event_data = {
        "run_id": "run-prod-denied",
        "correlation_id": "corr-prod-denied",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-26",
        "tenant_id": "tenant-123",
        "environment": "prod",
        "account_policy": {
            "account_id": "123456789012",
            "environment": "prod"
        },
        "approval_status": "approved",
        "force_dry_run": False,
        "ai": {
            "status": "AI_DECISION_READY",
            "run_id": "run-prod-denied",
            "correlation_id": "corr-prod-denied",
            "worker": "vpc_alb_caller",
            "recommended_containment_mode": "auto-shutdown",
            "anomaly_id": "ANM-2026-0626A",
            "confidence_score": 0.91
        },
        "ai_detect_response": {
            "success": True,
            "anomalies_detected": True,
            "data_confidence": "HIGH",
            "anomalies_list": [
                {
                    "anomaly_id": "ANM-2026-0626A",
                    "resource_id": "i-produnsafe",
                    "resource_owner": "team-payments",
                    "severity": "HIGH",
                    "confidence_score": 0.91
                }
            ]
        }
    }

    resp = handler.handle_request(event_data, None)
    details = resp["details"]
    assert details["audit_type"] == "DENIED"
    assert details["execution_mode"] == "denied"
    assert details["requested_action"] == "auto-shutdown"
    assert details["denial_reason"] == "prod_unsafe_action"
    assert details["proposed_after_state"] == "containment_denied"
    assert details["resource_id"] == "i-produnsafe"
    assert details["target_owner"] == "team-payments"
    assert details["tenant_id"] == "tenant-123"

def test_audit_writer_workflow_denies_forced_dry_run_unsafe_action():
    handler.s3_client = None
    handler.ddb_client = None

    event_data = {
        "run_id": "run-quality-denied",
        "correlation_id": "corr-quality-denied",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-26",
        "tenant_id": "tenant-123",
        "environment": "sandbox",
        "account_policy": {
            "account_id": "123456789012",
            "environment": "sandbox"
        },
        "approval_status": "approved",
        "force_dry_run": True,
        "ai": {
            "status": "AI_DECISION_READY",
            "run_id": "run-quality-denied",
            "correlation_id": "corr-quality-denied",
            "worker": "vpc_alb_caller",
            "recommended_containment_mode": "auto-shutdown",
            "anomaly_id": "ANM-2026-0626B",
            "confidence_score": 0.88
        },
        "ai_detect_response": {
            "success": True,
            "anomalies_detected": True,
            "data_confidence": "HIGH",
            "anomalies_list": [
                {
                    "anomaly_id": "ANM-2026-0626B",
                    "resource_id": "i-lowquality",
                    "resource_owner": "team-ml",
                    "severity": "HIGH",
                    "confidence_score": 0.88
                }
            ]
        }
    }

    resp = handler.handle_request(event_data, None)
    details = resp["details"]
    assert details["audit_type"] == "DENIED"
    assert details["execution_mode"] == "dry-run"
    assert details["denial_reason"] == "forced_dry_run"
    assert details["force_dry_run"] is True
    assert details["requested_action"] == "auto-shutdown"

def test_audit_writer_post_action_reads_containment_output_status():
    handler.s3_client = None
    handler.ddb_client = None

    event_data = {
        "run_id": "run-post",
        "correlation_id": "corr-post",
        "account_id": "123456789012",
        "cost_period": "2026-06",
        "execution_date": "2026-06-26",
        "tenant_id": "tenant-123",
        "environment": "sandbox",
        "approval_status": "approved",
        "ai": {
            "status": "AI_DECISION_READY",
            "run_id": "run-post",
            "correlation_id": "corr-post",
            "worker": "vpc_alb_caller",
            "recommended_containment_mode": "tag-for-review",
            "anomaly_id": "ANM-2026-0626C",
            "confidence_score": 0.9
        },
        "containment": {
            "run_id": "run-post",
            "anomaly_id": "ANM-2026-0626C",
            "correlation_id": "corr-post",
            "status": "completed",
            "execution_mode_applied": "tag"
        }
    }

    resp = handler.handle_request(event_data, None)
    details = resp["details"]
    assert details["audit_type"] == "POST_ACTION"
    assert details["execution_mode"] == "tag"
    assert details["applied_after_state"] == "completed"

def test_audit_writer_audit_type_inference():
    handler.s3_client = None
    handler.ddb_client = None

    tests = [
        {
            "name": "Containment Error",
            "event": {
                "run_id": "run-1",
                "correlation_id": "corr-1",
                "cost_period": "2026-06",
                "containment_error": {"Error": "ContainmentFailed", "Cause": "policy limit"}
            },
            "expected": "CONTAINMENT_FAILURE"
        },
        {
            "name": "Alert Error",
            "event": {
                "run_id": "run-2",
                "correlation_id": "corr-2",
                "cost_period": "2026-06",
                "alert_error": {"Error": "SNSAlertFailed", "Cause": "SNS unavailable"}
            },
            "expected": "ALERT_DELIVERY_FAILURE"
        },
        {
            "name": "Workflow Error",
            "event": {
                "run_id": "run-3",
                "correlation_id": "corr-3",
                "cost_period": "2026-06",
                "error": {"Error": "TaskError", "Cause": "Lambda failed"}
            },
            "expected": "WORKFLOW_FAILURE"
        }
    ]

    for tt in tests:
        resp = handler.handle_request(tt["event"], None)
        assert resp["details"]["audit_type"] == tt["expected"]
