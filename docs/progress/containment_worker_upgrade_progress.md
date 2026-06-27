# Containment Worker Upgrade Progress

## Status
Completed — all code migrated, Terraform updated, 51 new tests passing.

## Scope
Replace the existing stub `lambda_src/src/workers/containment_worker/handler.py` with the
production-grade implementation from `containment-lambda/`. The new implementation adds:

- Hard boundary enforcement (`policy/boundary.py`): prod environments, `data_confidence=LOW`, and
  `approval_status=denied` are handled before any AWS call is made.
- Cross-account `sts:AssumeRole` into member accounts (`aws/session.py`).
- Before-state resource read (`aws/resource_reader.py`).
- Pre-action rollback payload caching to DynamoDB `finops-rollback-cache` (`audit/dynamo_cache.py`).
- Pre-action and post-action audit records written to S3 with Object Lock
  (`audit/s3_audit.py`).
- Action dispatch for `dry-run`, `tag`, `suggest`, and `apply` modes
  (`actions/dry_run.py`, `actions/tagger.py`, `actions/suggester.py`, `actions/stopper.py`).
- DynamoDB Dashboard Cache update after each run (`audit/dynamo_cache.py`).
- Full `ContainmentOutput` schema returned to Step Functions.

Out of scope:
- AI Engine calls (handled upstream by `vpc_alb_caller`).
- Alert routing (handled by `router`).
- Dashboard rendering.

## Files Changed

### Pre-integration (this step)
- [docs/progress/containment_worker_upgrade_progress.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/progress/containment_worker_upgrade_progress.md) (Created)
- [docs/progress/containment_worker_upgrade_progress_vi.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/progress/containment_worker_upgrade_progress_vi.md) (Created)
- [lambda_src/requirements-dev.txt](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/lambda_src/requirements-dev.txt) (Updated — added `moto[ec2,rds,s3,dynamodb,sts]>=5.0.0`)
- [docs/GUIDES.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/GUIDES.md) (Updated — added containment worker testing section)
- [docs/GUIDES_vi.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/GUIDES_vi.md) (Updated — added containment worker testing section)

### Integration (next step — not yet applied)
- `lambda_src/src/workers/containment_worker/handler.py` (Replace stub with production handler)
- `lambda_src/src/workers/containment_worker/executor.py` (New)
- `lambda_src/src/workers/containment_worker/model/` (New — `input.py`, `output.py`)
- `lambda_src/src/workers/containment_worker/policy/` (New — `boundary.py`, `confidence_guard.py`)
- `lambda_src/src/workers/containment_worker/actions/` (New — `dry_run.py`, `tagger.py`, `suggester.py`, `stopper.py`, `rollback.py`)
- `lambda_src/src/workers/containment_worker/audit/` (New — `s3_audit.py`, `dynamo_cache.py`)
- `lambda_src/src/workers/containment_worker/aws/` (New — `session.py`, `resource_reader.py`)
- `lambda_src/tests/test_containment_worker.py` (Replace — new moto-based tests)
- `modules/compute-lambda/main.tf` (Update — add env vars and increase timeout for `containment_worker`)
- `modules/iam/main.tf` (Update — add `sts:AssumeRole`, `s3:PutObject` audit, DynamoDB rollback-cache + dashboard-cache, and `secretsmanager:GetSecretValue` to `containment_worker` role)

## Validation Commands

```powershell
# Run full test suite (requires moto installed)
Push-Location lambda_src; python -m pytest; Pop-Location

# Run only containment boundary tests (no AWS mocking needed)
Push-Location lambda_src; python -m pytest tests/test_containment_worker.py -v -k "boundary"; Pop-Location

# Run only containment audit tests (requires moto)
Push-Location lambda_src; python -m pytest tests/test_containment_worker.py -v -k "audit"; Pop-Location

# Terraform validation after Terraform changes
terraform fmt -check -recursive modules/compute-lambda modules/iam
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Security scans
checkov -d modules/iam --framework terraform
trivy config modules/iam modules/compute-lambda
```

## Results
- `lambda_src/requirements-dev.txt`: updated — `moto[ec2,rds,s3,dynamodb,sts]>=5.0.0` added.
- `docs/GUIDES.md` and `docs/GUIDES_vi.md`: updated — containment worker local testing section added.
- Progress files created (this file and Vietnamese pair).
- Code migration: **completed** — all subpackages migrated into `lambda_src/src/workers/containment_worker/`.
- `lambda_src/tests/test_containment_worker.py`: replaced with 51 moto-based tests.
- `modules/compute-lambda/main.tf`: `containment_worker` timeout increased to 120s, env vars `ROLLBACK_CACHE_TABLE`, `DASHBOARD_CACHE_TABLE`, `AUDIT_BUCKET_NAME` added.
- `modules/iam/main.tf`: `containment_worker` IAM policy expanded with `sts:AssumeRole`, `s3:PutObject` (audit), `dynamodb:PutItem`/`GetItem` (rollback-cache + dashboard-cache), `secretsmanager:GetSecretValue`.
- `terraform fmt -check -recursive modules/compute-lambda modules/iam`: **PASS**.
- pytest (containment only): **51 passed in 2.18s**.
- pytest (full suite): **103 passed, 2 pre-existing failures** (`test_normalizer` — `pyarrow` not installed locally, pre-existing issue unrelated to this change).

## Blockers
None.

## Next Step
Run full Terraform validate across all environments after packaging lambdas (`.\scripts\package-lambdas.ps1`), then deploy to sandbox for live end-to-end testing using test events in `containment-lambda/test-events/`.
