# Human Feedback Progress

## Status

Implemented and validated with scoped checks.

## Scope

Added an asynchronous human feedback workflow separate from the daily FinOps detection workflow. The workflow validates telemetry-contract section 15 fields, calls AI Engine `POST /v1/feedback` through `VpcAlbCallerLambda`, and writes audit evidence for successful delivery, failed delivery, or invalid payloads.

## Files Changed

- `modules/orchestration/feedback_statemachine.json`
- `modules/orchestration/main.tf`
- `modules/orchestration/outputs.tf`
- `environments/sandbox/outputs.tf`
- `environments/staging/outputs.tf`
- `environments/prod/outputs.tf`
- `docs/feedback-statemachine.json`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`
- `scripts/render-static-asl.py`
- `scripts/_gen_docs_sm.py`
- `lambda_src/tests/test_human_feedback_workflow.py`
- `docs/progress/human_feedback_progress.md`
- `docs/progress/human_feedback_progress_vi.md`

## Validation Commands

- `python scripts/render-static-asl.py`
- `Push-Location lambda_src; python -m pytest -q tests/test_human_feedback_workflow.py tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location`
- `terraform fmt -check -recursive modules/orchestration environments/sandbox environments/staging environments/prod`
- `terraform -chdir=environments/sandbox init -backend=false`
- `terraform -chdir=environments/sandbox validate`
- Attempted: `trivy config modules/orchestration`
- Attempted: `checkov -d modules/orchestration --framework terraform`

## Results

- Rendered `docs/statemachine.json` and `docs/feedback-statemachine.json` successfully.
- Scoped pytest passed: 145 passed.
- Terraform format check passed.
- Sandbox Terraform init with `-backend=false` passed.
- Sandbox Terraform validate passed.
- `trivy` and `checkov` could not run because the commands are not installed or not available in PATH.

## Blockers

`trivy` and `checkov` are not installed or not available in PATH in this environment.

## Next Step

Install or expose `trivy` and `checkov` in PATH, then run the scoped security scans before promotion.
