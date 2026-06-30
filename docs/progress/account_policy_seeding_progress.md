# Account Policy Seeding Progress

## Status
COMPLETED

## Scope
Documentation-only implementation of the bilingual operator document for seeding the DynamoDB `account-policy` table before running or enabling the Orchestrator Step Functions workflow.

## Files Changed
| File | Action | Purpose |
| --- | --- | --- |
| [ACCOUNT_POLICY_SEEDING.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING.md) | Created | Detailed English operator seeding guide with PowerShell AWS CLI commands. |
| [ACCOUNT_POLICY_SEEDING_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING_vi.md) | Created | Detailed Vietnamese operator seeding guide translating prose but retaining technical parameters. |
| [GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md) | Modified | Added operator workflow link under Section 3 (Post-Deployment GitOps Handoff). |
| [GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md) | Modified | Added Vietnamese operator workflow link under Section 3 (Post-Deployment GitOps Handoff). |

## Validation Commands
```powershell
# Validate documentation consistency & references
rg -n "ACCOUNT_POLICY_SEEDING|account-policy|LoadAccountPolicy|scheduler_enabled" docs
```

## Results
- The new bilingual seeding guides successfully document the DynamoDB item shape used by the `LoadAccountPolicy` step (`account_id` and `environment`).
- Detailed PowerShell sequences for describing the table, idempotently writing a item with condition checks (`attribute_not_exists(account_id)`), consistent read verification, and correction updates are provided.
- Troubleshooting notes regarding JSONPath extraction failure (`$.Item.account_id.S` not found) and alignment between executing account IDs and seeded records are included.
- Guides have been linked correctly in English and Vietnamese developer guides.
- Command validation was executed using Ripgrep to verify search paths and query occurrences across the documentation folder.

## Blockers
None.

## Next Step
Operators to follow [ACCOUNT_POLICY_SEEDING.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING.md) to seed their target AWS accounts prior to enabling `scheduler_enabled = true` or triggering the Step Functions state machines manually.
