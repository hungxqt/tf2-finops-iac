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

    assert "TF2 FinOps Watch Dashboard" in index
    assert "Manual Approval" in app
    assert "Alert Routing" in app
    assert "Audit Diff" in app
    assert "Access Settings" in app
    assert "Read-only first" in app
    assert "Handled by Step Functions" in app
    assert "/v1/" not in app
    assert "rollback_script" not in app.lower()
    assert "aws cli" not in app.lower()


def test_dashboard_frontend_source_exists():
    frontend = DASHBOARD_MODULE / "frontend"

    assert (frontend / "package.json").exists()
    assert (frontend / "vite.config.ts").exists()
    assert (frontend / "src" / "App.tsx").exists()
    assert (frontend / "src" / "schema.ts").exists()
