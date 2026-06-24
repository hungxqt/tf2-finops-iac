# Lambda Go Mismatch Progress

## Status
Completed with validation warning

## Scope
Correction of stale non-Go Lambda references so repository instructions, implementation planning, delivery documentation, and CI match the current Go Lambda codebase:
- IaC agent instructions now describe the Go `lambda_src/` tree.
- The implementation plan now uses Go 1.21, `aws-lambda-go`, `main.go`, `go test ./...`, and `provided.al2023`.
- English and Vietnamese deployment design docs now name Go Lambda unit tests.
- GitHub Actions CI now sets up Go and runs Lambda unit tests from `lambda_src/`.

## Files Changed
- `AGENTS.md` (Updated Lambda skeleton and validation command)
- `IMPLEMENTATION.md` (Updated Lambda language, file names, tests, and runtime guidance)
- `.github/workflows/terraform-ci.yml` (Replaced old test setup with Go setup and `go test ./...`)
- `../tf2-finops-docs/docs/tf2-finops/04_deployment_design.md` (Updated unit and smoke test tooling)
- `../tf2-finops-docs/docs/tf2-finops/04_deployment_design_vi.md` (Updated matching Vietnamese unit and smoke test tooling)
- `docs/progress/lambda_go_mismatch_progress.md` (Created)
- `docs/progress/lambda_go_mismatch_progress_vi.md` (Created)

## Validation Commands
- Run Go unit tests: `cd lambda_src && go test ./...`
- Scan for known obsolete Lambda-language references across project docs and CI workflow files.
- Run general formatting and validation: `.\scripts\validate.ps1`

## Results
- Go unit tests pass successfully.
- Stale-reference scan only reports generic placeholders under `tf2-finops-docs/template-docs/`.
- General validation script completed after Terraform provider metadata was reachable.
- Terraform fmt, Terraform init/validate, Trivy, Checkov, and Go unit test stages completed.
- TFLint reported an existing config compatibility warning: `"module" attribute was removed in v0.54.0. Use "call_module_type" instead`.

## Blockers
None for the Go Lambda mismatch fix.

## Next Step
If strict TFLint pass is required, update `.tflint.hcl` for the installed TFLint version in a separate validation cleanup.
