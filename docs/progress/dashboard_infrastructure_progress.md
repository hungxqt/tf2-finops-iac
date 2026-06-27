# Dashboard Infrastructure Progress

## Status
Completed (Security Hardened; Frontend Publish Decoupled)

## Scope
Remediation and security hardening of the Finance dashboard hosting, API routing, and data access infrastructure using an AWS-native S3, CloudFront VPC Origin, Cognito PKCE, and Lambda@Edge setup. The latest update rolls back Terraform-managed frontend asset publishing so the UI shell is built and uploaded independently while Terraform keeps emitting only `dashboard_runtime_config.json`.

## Files Changed
* `modules/dashboard/main.tf` (Modified)
* `modules/dashboard/variables.tf` (Modified)
* `modules/dashboard/outputs.tf` (Modified)
* `modules/dashboard/versions.tf` (Modified)
* `modules/dashboard/README.md` (Modified)
* `modules/dashboard/resources/README.md` (Created)
* `modules/dashboard/resources/assets/styles.css` (Modified)
* `modules/dashboard/resources/assets/app.js` (Modified)
* `modules/dashboard/resources/index.html` (Modified)
* `docs/GUIDES.md` (Modified)
* `docs/GUIDES_vi.md` (Modified)
* `modules/ai-runtime-lambda/main.tf` (Modified)
* `environments/sandbox/main.tf` (Modified)
* `environments/staging/main.tf` (Modified)
* `environments/prod/main.tf` (Modified)
* `lambda_src/edge/dashboard_auth/viewer_auth.py` (Created)
* `lambda_src/edge/dashboard_auth/origin_sigv4.py` (Created)
* `lambda_src/tests/test_dashboard_infrastructure.py` (Created)
* `lambda_src/tests/test_dashboard_static_assets.py` (Created)
* `scripts/package-lambdas.ps1` (Modified)

## Validation Commands
```powershell
terraform fmt -check -recursive modules/dashboard modules/ai-runtime-lambda environments/sandbox environments/staging environments/prod
powershell -ExecutionPolicy Bypass -File ./scripts/package-lambdas.ps1
cd lambda_src
python -m pytest tests/test_dashboard_infrastructure.py
python -m py_compile lambda_src\edge\dashboard_auth\viewer_auth.py lambda_src\edge\dashboard_auth\origin_sigv4.py
terraform fmt -check -recursive modules/dashboard
terraform -chdir=environments/prod validate
cd lambda_src
python -m pytest
cd lambda_src
python -m pytest tests/test_dashboard_static_assets.py
terraform fmt -check -recursive modules/dashboard
terraform -chdir=environments/prod validate
```

## Results
* Authentication bypass and insecure OAuth flow fixed: Removed implicit flow; Cognito Code + PKCE flow is enforced at the CloudFront edge via Lambda@Edge.
* S3 data and API routes are secured under CloudFront edge authentication (viewer-request auth checks cookies and validates claims/UserInfo against Cognito).
* Private origin ALB reached via CloudFront VPC Origin, disabling cache for `/v1/*` routes and stripping Cognito cookies before forwarding.
* S3 replication hardened: Enabled KMS source selection and destination KMS key encryption for assets and data replica buckets.
* Sandbox asset bucket teardown blast radius resolved using `force_destroy = var.destroyable`.
* Terraform provider drift resolved: updated module version constraints to require AWS provider >= 5.100.
* Lambda@Edge auth cookies hardened: access and ID token cookies now use `Secure`, `HttpOnly`, `SameSite=Strict`, and bounded `Max-Age`.
* OAuth callback CSRF protection hardened: state now carries a nonce and sanitized redirect path, with callback validation against a short-lived `Cognito-CSRF-Nonce` cookie.
* PKCE and CSRF transient cookies use short lifetimes and `SameSite=Lax` so the Cognito hosted UI redirect can complete while session cookies remain `SameSite=Strict`.
* Formatting and validation pass recursively.
* All 7 regression test assertions pass in pytest.
* `python -m py_compile` for both Lambda@Edge handlers passed.
* Full `python -m pytest` currently reports 57 passed and 2 failed because `pyarrow` is not installed in the local Python environment; the failures are in normalizer Parquet tests and are unrelated to dashboard auth.
* Terraform-managed frontend asset publishing was removed from `modules/dashboard/main.tf`; static UI files are now an independent handoff outside Terraform-managed S3 object resources.
* The `aws_s3_object.runtime_config` resource remains in place for non-secret runtime discovery.
* Dashboard guide handoff updated: frontend assets must be built/uploaded independently, and generated JSON summaries should be published under the configured prefix such as `summaries/`.
* Frontend resources README added to document UI shell structure, independent upload, runtime config, summary schema, and operator action behavior.
* Dashboard UI now includes doc-06 operational surfaces for Manual Approval, Alert Routing previews, Audit Diff, and Access Settings while preserving Finance read-only restrictions and hiding raw rollback/CLI payloads.
* Frontend validation passed: `node --check modules\dashboard\resources\assets\app.js` and `python -m pytest -p no:cacheprovider tests/test_dashboard_static_assets.py`.

## Blockers
Local full Lambda test execution needs `pyarrow` installed to pass the normalizer Parquet assertions.

## Next Step
Install the Lambda test dependencies that include `pyarrow`, rerun full `python -m pytest`, then continue to verify the orchestration state machine run states and AI API fallbacks.

