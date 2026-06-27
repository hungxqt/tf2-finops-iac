from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_MODULE = REPO_ROOT / "modules" / "dashboard"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_terraform_does_not_publish_frontend_static_assets():
    main_tf = read(DASHBOARD_MODULE / "main.tf")

    assert 'resource "aws_s3_object" "runtime_config"' in main_tf
    assert 'resource "aws_s3_object" "static_assets"' not in main_tf
    assert "static_assets = {" not in main_tf
    assert "resources/index.html" not in main_tf
    assert "resources/assets/styles.css" not in main_tf
    assert "resources/assets/app.js" not in main_tf


def test_dashboard_ui_covers_doc06_operational_surfaces():
    index = read(DASHBOARD_MODULE / "resources" / "index.html")
    app = read(DASHBOARD_MODULE / "resources" / "assets" / "app.js")

    assert "Manual Approval" in index
    assert "Alert Routing" in index
    assert "Audit Diff" in index
    assert "Access Settings" in index
    assert "renderApprovals" in app
    assert "renderAlertPreviews" in app
    assert "renderAuditDiffs" in app
    assert "renderAdminSettings" in app
    assert "/v1/verify" in app
    assert "/v1/audit/" in app
    assert "rollback_script" not in app.lower()
    assert "aws cli" not in app.lower()
