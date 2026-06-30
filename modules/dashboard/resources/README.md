# Dashboard Static Handoff

This directory is the deployable static asset handoff for the TF2 FinOps Watch dashboard.

The dashboard source now lives in `modules/dashboard/frontend/` and is built with React, Vite, and TypeScript. The Vite build writes deterministic output into this directory so the existing S3 + CloudFront upload workflow remains unchanged:

```text
resources/
|-- index.html
|-- README.md
`-- assets/
    |-- app.js
    `-- styles.css
```

Terraform does not publish these UI files to S3. Terraform only provisions the dashboard hosting/data infrastructure and writes the non-secret `dashboard_runtime_config.json` object into the asset bucket.

## Build

From `modules/dashboard/frontend/`:

```powershell
npm install
npm run typecheck
npm run lint
npm test
npm run build
```

After `npm run build`, upload the contents of `modules/dashboard/resources/` to the dashboard asset bucket output by Terraform. Access the dashboard through CloudFront, not directly through S3.

## Runtime Data Flow

The frontend loads:

```text
/dashboard_runtime_config.json
${data_prefix}dashboard-summary.json
```

The default data prefix is:

```text
summaries/
```

Production behavior is intentionally strict: invalid or missing `dashboard-summary.json` shows a data contract error instead of silently falling back to sample data. Sample data is only used in local Vite development mode.

## Summary Schema

The dashboard expects the existing materialized summary shape plus optional 2026 fields:

```json
{
  "dashboard_schema_version": "2026-01",
  "environment": "<environment>",
  "viewer_role": "<finance|engineering|cdo|admin>",
  "generated_at": "<ISO-8601 timestamp>",
  "tenant_id": "<tenant id>",
  "data_freshness_status": "<fresh|stale|unknown>",
  "containment_locked": false,
  "lock_reason": "<optional policy reason>",
  "error_budget_remaining_pct": 100,
  "workflow_status": "<workflow status>",
  "last_successful_run_id": "<run id>",
  "business_context": {},
  "telemetry_quality": {},
  "spend_trend": [["<YYYY-MM-DD>", 0, 0, false]],
  "anomalies": [],
  "impacted": [],
  "containment": [],
  "approvals": [],
  "alert_previews": [],
  "audit_diffs": [],
  "admin_settings": []
}
```

Missing `dashboard_schema_version` is treated as a legacy summary, but critical identity fields such as `environment` and `generated_at` are required.

## Read-Only Action Policy

The dashboard is read-only first. It does not call `/v1/*` endpoints because the CloudFront dashboard distribution does not proxy those action APIs.

Finance, Engineering, and CDO users can see anomaly status, containment state, approval intent, audit diffs, and access metadata according to their role. Real Verify, Rollback, and Approval mutations require a future backend action gateway.
