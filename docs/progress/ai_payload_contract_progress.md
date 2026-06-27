# AI Payload Contract Progress

## Status

Implemented and validated for the Step Functions AI payload contract path.

## Scope

- Updated the Step Functions request builders for `/v1/detect`, `/v1/decide`, and `/v1/verify` while keeping the approved `Step Functions -> VpcAlbCallerLambda -> private internal ALB -> AI Request Lambda` transport.
- Kept `/v1/detect` on the default `S3_POINTER` path and added the missing telemetry contract fields.
- Aligned tenant, correlation, idempotency, timestamp, and payload checksum values between Step Functions parameters, AI request bodies, and VpcAlbCallerLambda validation.
- Normalized AI input payloads from the normalizer so `business_context` is a single account-scoped object and S3 AI input objects include tenant context.
- Hardened VpcAlbCallerLambda local validation for UUID tenant/correlation values, AI idempotency key format, HTTPS ALB base URL shape, and body/top-level context mismatches.

## Files Changed

- `modules/orchestration/statemachine.json`
- `docs/statemachine.json`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/src/workers/vpc_alb_caller/handler.py`
- `lambda_src/src/workers/state/handler.py`
- `lambda_src/tests/fixtures/step_function_payloads.py`
- `lambda_src/tests/test_normalizer.py`
- `lambda_src/tests/test_state.py`
- `lambda_src/tests/test_state_machine.py`
- `lambda_src/tests/test_step_function_payload_contract.py`
- `lambda_src/tests/test_vpc_alb_caller.py`

## Validation Commands

```powershell
python scripts\render-static-asl.py
Push-Location lambda_src; python -m pytest tests/test_vpc_alb_caller.py tests/test_normalizer.py tests/test_state.py tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location
Push-Location lambda_src; python -m pytest; Pop-Location
terraform fmt -check -recursive modules\orchestration
terraform fmt -check -recursive
terraform -chdir=environments\sandbox init -backend=false
terraform -chdir=environments\sandbox validate
trivy config .
checkov -d modules\ai-runtime-lambda -d modules\orchestration --framework terraform
Push-Location lambda_src; python -m pytest tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check
```

## Results

- Static ASL regeneration completed and produced valid JSON.
- Focused Lambda and Step Functions contract tests passed: 108 passed, 1 warning.
- Full Lambda test suite passed: 199 passed, 34 warnings.
- Terraform formatting checks passed.
- Sandbox Terraform init initially could not reach `registry.terraform.io` in the restricted sandbox, then passed with approved network escalation.
- Sandbox Terraform validate passed.
- Scoped Checkov scan for `modules/ai-runtime-lambda` and `modules/orchestration` passed with 110 passed, 0 failed, and 14 skipped checks.
- `trivy config .` completed successfully, but still reports pre-existing findings outside this patch scope.
- Post-regeneration ASL contract tests passed: 80 passed, 1 warning.
- CRLF-aware diff whitespace check passed.

## Blockers

- None for this feature.
- Residual validation noise remains from existing `datetime.utcnow()` deprecation warnings and a pytest cache permission warning.

## Next Step

Run the broader environment validation set before release if this patch is bundled with additional infrastructure changes.
