# AGENTS.md Contract Alignment Progress

## Status
Completed

## Scope
Update AGENTS.md to align with the active `docs/tf2-finops` architecture and contracts, resolving contradictions and detailing logical endpoint mapping, storage/state caches, SQS use, telemetry ingestion modes, and dashboard targets.

## Files Changed
- [AGENTS.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/AGENTS.md) (Modified)

## Validation Commands
- Run git diff check: `git diff --check -- AGENTS.md`
- Grep for required terms:
  `rg -n "finops-idempotency|finops-rollback-cache|company-cdo-|S3_POINTER|RAW_JSON|SigV4|/v1/detect|/v1/decide|/v1/verify|/v1/status|/v1/audit" AGENTS.md`
- Grep for stale/superseded terms check:
  `rg -n "Private API Gateway|ECS Cluster|Fargate capacity|Argo CD|Kubernetes|primary detection polling|/v1/status.*detection" AGENTS.md`

## Results
- Non-apply checks passed successfully.
- Diff checks passed cleanly.
- Required contract terms and semantics are correctly updated in AGENTS.md.
- Stale platform terms are correctly contextualized as stale/superseded wording.

## Blockers
None

## Next Step
Maintain standard module verification workflows during future updates.
