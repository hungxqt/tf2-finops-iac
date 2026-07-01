# Manual Report Trigger Progress

## Status

Implemented and validated (typecheck passed, 3/3 Vitest tests passed).

## Scope

Added a "Run report now" button to the dashboard Topbar that allows CDO/admin/engineering
roles to manually trigger an ad-hoc FinOps detection run. The button enforces the
existing per-tenant daily quota of 5 ad-hoc runs, which is already wired in the
Step Functions state machine (`CheckAdHocQuota` state) and the `state/handler.py`
Lambda (`check_quota` operation).

## What Was Already in Place (Not Changed)

- `state/handler.py` – `check_quota` operation enforces 5-run daily quota via DynamoDB.
- `docs/statemachine.json` – `CheckAdHocQuotaDecision` → `CheckAdHocQuota` →
  `EvaluateAdHocQuota` → `SetQuotaExceededError` flow fully wired.
- `docs/MANUAL_STEP_FUNCTIONS_EXECUTION.md` – operator runbook for CLI-based ad-hoc runs.

## Files Changed

- `modules/dashboard/frontend/src/schema.ts`
  - Added `trigger_api_url` (optional) to `runtimeConfigSchema`.
  - Added `ad_hoc_quota_used` (int 0-5, default 0) to `dashboardSummarySchema`.
- `modules/dashboard/frontend/src/sampleData.ts`
  - Added `ad_hoc_quota_used: 2` to sample data for local dev demonstration.
- `modules/dashboard/frontend/src/data.ts`
  - Added `triggerAdHocRun(tenantId, accountId)` function that POSTs to
    `trigger_api_url` from runtime config. Falls back to a 1.5s simulation
    in local dev when no URL is configured.
- `modules/dashboard/frontend/src/components/ui/ManualTriggerButton.tsx` (NEW)
  - Self-contained "Run report now" button component with:
    - Quota badge (e.g. "2/5") showing daily usage.
    - Confirmation dialog with remaining-runs warning.
    - Loading spinner while waiting for the backend.
    - Success toast showing the execution ARN.
    - Quota-exceeded warning banner.
    - Error banner for unexpected failures.
    - Button disables when quota is exhausted.
- `modules/dashboard/frontend/src/components/layout/Topbar.tsx`
  - Imported `ManualTriggerButton`.
  - Added `canTrigger()` role gate (admin, cdo, engineering see the button;
    finance-readonly does not).
  - Rendered the button in the Topbar right section beside the meta pills.

## Backend Wiring (Terraform – Not Yet Implemented)

The frontend calls `trigger_api_url` from the runtime config. This URL must point
to an API Gateway endpoint (or Lambda Function URL behind CloudFront) that:

1. Accepts POST with `{ is_ad_hoc: true, tenant_id?, account_id? }`.
2. Calls `StepFunctions:StartExecution` with the state machine ARN and the body
   as the input JSON (with `is_ad_hoc: true`).
3. Returns `{ execution_arn: "..." }` on success, or an error with a descriptive
   `message` field (e.g. "Tenant ad hoc run quota limit of 5 runs per day exceeded.")
   so the button can surface it.

The `trigger_api_url` must be emitted from Terraform as part of the dashboard
runtime config (`dashboard_runtime_config.json`) published to the S3 data bucket.

## Validation Commands

```powershell
# TypeScript type check
npm run typecheck

# Vitest unit tests
npm run test

# Dev server (visual check of button in browser at http://127.0.0.1:5173)
npm run dev
```

## Results

- `npm run typecheck` (tsc -b): PASSED — 0 errors.
- `npm run test` (Vitest): PASSED — 3/3 tests (src/schema.test.ts 2 tests,
  src/App.test.tsx 1 test).
- Visual inspection via dev server: pending manual run.

## Blockers

- `node_modules` not present in the frontend directory; `npm install` is running.
- Terraform backend Lambda + API Gateway for `trigger_api_url` is not yet
  implemented. The button simulates a trigger in local dev mode.

## Next Step

1. Wait for `npm install` to complete.
2. Run `npm run typecheck` and `npm run test` to confirm zero errors.
3. Implement the Terraform-side trigger Lambda (thin wrapper calling
   `StepFunctions:StartExecution`) and wire `trigger_api_url` into the dashboard
   runtime config output.
4. Update progress file once validation passes.
