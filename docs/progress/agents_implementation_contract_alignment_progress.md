# Agents Implementation Contract Alignment Progress

## Status
Completed

## Scope
Update `AGENTS.md` and `IMPLEMENTATION.md` so future work follows the current `docs/contracts/**` and `docs/tf2-finops/**` contract baseline: Terraform-owned AWS platform IaC, Lambda container AI Engine behind a private internal ALB, synchronous `/v1/detect`, no detection SQS/polling loop, CDO-owned rollback execution, and S3 + CloudFront + Cognito dashboard defaults. Also update developer guides for updated handoff and validation details.

## Files Changed
- [AGENTS.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/AGENTS.md)
- [IMPLEMENTATION.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/IMPLEMENTATION.md)
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md)
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md)

## Validation Commands
```powershell
# Grep for new terms to ensure they are documented as active requirements
rg -n "vpc_alb_caller|private internal ALB|S3_POINTER|RAW_JSON|finops-idempotency|finops-rollback-cache|rollback_payload.boto3_equivalent|data_confidence|use_lockfile" AGENTS.md IMPLEMENTATION.md

# Grep for old/stale terms to ensure they do not appear as active requirements
rg -n "ai_client|SQS detection queue|DynamoDB result-polling|Function URL|Private API Gateway|ECS Cluster|Fargate capacity" AGENTS.md IMPLEMENTATION.md
```

## Results
- Grep queries confirm that all active requirements specify the synchronous private ALB path utilizing `vpc_alb_caller`, with `finops-idempotency` and `finops-rollback-cache` correctly documented.
- No stale terms (`ai_client` or `SQS detection queue` / polling loops) appear as active requirements; they are only mentioned in conflict handling notes as reference/superseded wording.
- Guide files `docs/GUIDES.md` and `docs/GUIDES_vi.md` are updated with the matching handoff and checkov validation details.
- No infrastructure validation was required for this documentation-only change.

## Blockers
None

## Next Step
Proceed with implementation tasks using the aligned backlog.
