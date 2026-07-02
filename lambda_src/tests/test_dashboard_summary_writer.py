import argparse
import importlib.util
import sys
from types import ModuleType
from pathlib import Path

import pytest

from workers.dashboard_summary_writer import handler

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_publisher():
    path = REPO_ROOT / "scripts" / "publish-dashboard-summary.py"
    spec = importlib.util.spec_from_file_location("dashboard_summary_publish_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _set_env(monkeypatch):
    values = {
        "ENVIRONMENT": "sandbox",
        "PROJECT_NAME": "tf2-finops",
        "TENANT_ID": "tf2-finops-sandbox",
        "DASHBOARD_ACCOUNT_ID": "336805808730",
        "GLUE_DATABASE_NAME": "tf2-finops_sandbox_database",
        "ATHENA_WORKGROUP_NAME": "tf2-finops-sandbox-workgroup",
        "ATHENA_RESULTS_BUCKET_NAME": "athena-results",
        "LAKEHOUSE_BUCKET_NAME": "lakehouse",
        "DASHBOARD_DATA_BUCKET": "dashboard-data",
        "RUN_STATE_TABLE_NAME": "run-state",
        "ANOMALY_TABLE_NAME": "anomaly",
        "AUDIT_TABLE_NAME": "audit",
        "DASHBOARD_VIEWS_TABLE_NAME": "dashboard-views",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_build_args_matches_manual_publisher_contract(monkeypatch):
    _set_env(monkeypatch)

    args = handler._build_args()

    assert args.account_id == "336805808730"
    assert args.dashboard_key == "summaries/dashboard-summary.json"
    assert args.lookback_days == 90
    assert args.dry_run is False
    assert args.invalidate_cloudfront is False


def test_handler_delegates_to_shared_materializer(monkeypatch):
    _set_env(monkeypatch)
    captured = {}
    materializer = ModuleType("dashboard_summary_publish")

    def publish_summary(args):
        captured["args"] = args
        return {
            "generated_at": "2026-07-01T04:00:00Z",
            "last_successful_run_id": "run-123",
        }

    materializer.publish_summary = publish_summary
    monkeypatch.setitem(sys.modules, "dashboard_summary_publish", materializer)

    result = handler.handle_request(
        {"detail": {"executionArn": "arn:aws:states:execution/example"}},
        None,
    )

    assert captured["args"].dashboard_bucket == "dashboard-data"
    assert result == {
        "status": "PUBLISHED",
        "generated_at": "2026-07-01T04:00:00Z",
        "last_successful_run_id": "run-123",
    }


def test_packaging_includes_shared_manual_publisher():
    packaging = (REPO_ROOT / "scripts" / "package-lambdas.ps1").read_text()

    assert '$worker -eq "dashboard_summary_writer"' in packaging
    assert '"publish-dashboard-summary.py"' in packaging
    assert '"dashboard_summary_publish.py"' in packaging


def test_eventbridge_triggers_writer_only_after_success():
    orchestration = (
        REPO_ROOT / "modules" / "orchestration" / "main.tf"
    ).read_text()

    assert 'resource "aws_cloudwatch_event_rule" "dashboard_summary_after_success"' in orchestration
    assert 'status          = ["SUCCEEDED"]' in orchestration
    assert 'var.lambda_function_arns["dashboard_summary_writer"]' in orchestration
    assert 'resource "aws_lambda_permission" "dashboard_summary_from_eventbridge"' in orchestration


def test_spend_fallback_keeps_only_latest_run_per_account_and_day():
    publisher = _load_publisher()
    records = [
        {
            "account_id": "123",
            "timestamp": "2026-03-01T00:00:00Z",
            "idempotency_key": "old-run",
            "curated_at": "2026-07-01T10:00:00Z",
            "cost": 100,
        },
        {
            "account_id": "123",
            "timestamp": "2026-03-01T00:00:00Z",
            "idempotency_key": "new-run",
            "curated_at": "2026-07-01T11:00:00Z",
            "cost": 40,
        },
        {
            "account_id": "123",
            "timestamp": "2026-03-01T01:00:00Z",
            "idempotency_key": "new-run",
            "curated_at": "2026-07-01T11:00:01Z",
            "cost": 2,
        },
    ]

    assert publisher.build_spend_rows_from_cost_records(records) == [
        {"day": "2026-03-01", "actual_cost": "42.0"}
    ]


def test_athena_query_ranks_latest_execution_per_account_and_day():
    publisher = _load_publisher()
    args = argparse.Namespace(
        database="finops",
        account_id="123",
        lookback_days=90,
    )

    query = publisher.curated_cost_cte(args)

    assert "PARTITION BY account_id, usage_day" in query
    assert "ORDER BY execution_updated_at DESC, execution_id DESC" in query
    assert "WHERE ranked_executions.execution_rank = 1" in query


def test_empty_spend_does_not_overwrite_existing_snapshot(monkeypatch):
    publisher = _load_publisher()

    class FakeS3:
        def __init__(self):
            self.put_calls = []

        def get_paginator(self, _name):
            class EmptyPaginator:
                def paginate(self, **_kwargs):
                    return [{"Contents": []}]

            return EmptyPaginator()

        def put_object(self, **kwargs):
            self.put_calls.append(kwargs)

    fake_s3 = FakeS3()

    class FakeSession:
        def client(self, name, **_kwargs):
            if name == "s3":
                return fake_s3
            return object()

    monkeypatch.setattr(publisher.boto3, "Session", lambda **_kwargs: FakeSession())
    monkeypatch.setattr(publisher, "athena_or_empty", lambda *_args, **_kwargs: [])
    args = argparse.Namespace(
        region="ap-southeast-1",
        database="finops",
        workgroup="primary",
        athena_results_bucket="results",
        athena_timeout_seconds=1,
        account_id="123",
        lookback_days=90,
        lakehouse_bucket="lakehouse",
        max_curated_objects=10,
    )

    with pytest.raises(RuntimeError, match="preserving the existing dashboard snapshot"):
        publisher.publish_summary(args)

    assert fake_s3.put_calls == []
