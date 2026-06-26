# Dashboard Infrastructure Progress

## Status
Completed (Security Hardened)

## Scope
Remediation and security hardening of the Finance dashboard hosting, API routing, and data access infrastructure using an AWS-native S3, CloudFront VPC Origin, Cognito PKCE, and Lambda@Edge setup.

## Files Changed
* `modules/dashboard/main.tf` (Modified)
* `modules/dashboard/variables.tf` (Modified)
* `modules/dashboard/outputs.tf` (Modified)
* `modules/dashboard/versions.tf` (Modified)
* `modules/dashboard/README.md` (Modified)
* `modules/ai-runtime-lambda/main.tf` (Modified)
* `environments/sandbox/main.tf` (Modified)
* `environments/staging/main.tf` (Modified)
* `environments/prod/main.tf` (Modified)
* `lambda_src/edge/dashboard_auth/viewer_auth.py` (Created)
* `lambda_src/edge/dashboard_auth/origin_sigv4.py` (Created)
* `lambda_src/tests/test_dashboard_infrastructure.py` (Created)
* `scripts/package-lambdas.ps1` (Modified)

## Validation Commands
```powershell
terraform fmt -check -recursive modules/dashboard modules/ai-runtime-lambda environments/sandbox environments/staging environments/prod
powershell -ExecutionPolicy Bypass -File ./scripts/package-lambdas.ps1
cd lambda_src
python -m pytest tests/test_dashboard_infrastructure.py
```

## Results
* Authentication bypass and insecure OAuth flow fixed: Removed implicit flow; Cognito Code + PKCE flow is enforced at the CloudFront edge via Lambda@Edge.
* S3 data and API routes are secured under CloudFront edge authentication (viewer-request auth checks cookies and validates claims/UserInfo against Cognito).
* Private origin ALB reached via CloudFront VPC Origin, disabling cache for `/v1/*` routes and stripping Cognito cookies before forwarding.
* S3 replication hardened: Enabled KMS source selection and destination KMS key encryption for assets and data replica buckets.
* Sandbox asset bucket teardown blast radius resolved using `force_destroy = var.destroyable`.
* Terraform provider drift resolved: updated module version constraints to require AWS provider >= 5.100.
* Formatting and validation pass recursively.
* All 7 regression test assertions pass in pytest.

## Blockers
None

## Next Step
Continue to verify the orchestration state machine run states and AI API fallbacks.
