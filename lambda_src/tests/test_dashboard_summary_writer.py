import sys
from types import ModuleType
from pathlib import Path

from workers.dashboard_summary_writer import handler

REPO_ROOT = Path(__file__).resolve().parents[2]


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
