# GitOps Khanh Progress

## Status

Created a parallel GitOps workflow set with `khanh-*` names. Existing workflows were not modified.

## Scope

The workflow set covers pull request validation, plan-artifact apply, and scheduled drift detection for sandbox, staging, and prod.

## Files Changed

- `.github/workflows/khanh-terraform-ci.yml`
- `.github/workflows/khanh-terraform-apply.yml`
- `.github/workflows/khanh-drift-detection.yml`
- `docs/GUIDES_khanh.md`
- `docs/GUIDES_khanh_vi.md`
- `docs/progress/gitops_khanh_progress.md`
- `docs/progress/gitops_khanh_progress_vi.md`

## Validation Commands

```powershell
git diff --check -- .github/workflows/khanh-terraform-ci.yml .github/workflows/khanh-terraform-apply.yml .github/workflows/khanh-drift-detection.yml docs/GUIDES_khanh.md docs/GUIDES_khanh_vi.md
```

## Results

Whitespace validation passed. Full workflow execution was not run because GitHub Actions workflows must run in GitHub with configured OIDC role and repository variables.

## Blockers

The existing repository has a Terraform formatting issue in `modules/lakehouse/lakehouse.tftest.hcl`; the new CI keeps `terraform fmt -check -recursive` as a hard gate, so that existing issue must be fixed before the new CI can pass.

## Next Step

Configure the `KHANH_*` GitHub variables, configure `KHANH_AWS_ROLE_TO_ASSUME`, and run `Khanh GitOps CI` or `Khanh GitOps Apply` from GitHub Actions.
