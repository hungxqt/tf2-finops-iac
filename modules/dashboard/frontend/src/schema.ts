import { z } from "zod";

export const runtimeConfigSchema = z.object({
  aws_region: z.string().optional(),
  user_pool_id: z.string().optional(),
  user_pool_client_id: z.string().optional(),
  identity_pool_id: z.string().optional(),
  hosted_ui_domain: z.string().optional(),
  data_bucket_name: z.string().optional(),
  data_prefix: z.string().default("summaries/"),
  cloudfront_domain: z.string().optional(),
  /** URL of the backend API Gateway endpoint that starts an ad-hoc Step Functions execution. */
  trigger_api_url: z.string().optional()
});

const spendTrendRowSchema = z.tuple([
  z.string(),
  z.coerce.number(),
  z.coerce.number(),
  z.boolean()
]);

const anomalySchema = z.object({
  anomaly_id: z.string(),
  severity: z.string(),
  account_id: z.string(),
  account_name: z.string().optional().default("Unknown account"),
  service: z.string(),
  squad: z.string().optional().default("unassigned"),
  owner_tag_status: z.string().optional().default("unknown"),
  confidence_score: z.coerce.number().min(0).max(1).default(0),
  data_confidence: z.string().optional().default("UNKNOWN"),
  evidence_window_start: z.string().optional(),
  evidence_window_end: z.string().optional(),
  cost_delta_usd_per_day: z.coerce.number().default(0),
  explanation: z.string().optional().default("No model explanation was published."),
  business_context: z.record(z.unknown()).optional(),
  telemetry_quality: z.record(z.unknown()).optional(),
  workflow_status: z.string().optional()
});

const impactedSchema = z.object({
  name: z.string(),
  type: z.string(),
  spend_delta_usd_per_day: z.coerce.number().default(0),
  owner_tag_status: z.string().optional().default("unknown")
});

const containmentSchema = z.object({
  audit_id: z.string(),
  resource_id: z.string(),
  account_id: z.string(),
  squad: z.string().optional().default("unassigned"),
  action_type: z.string().optional().default("review"),
  execution_mode: z.string().optional().default("dry-run"),
  status: z.string().optional().default("UNKNOWN"),
  containment_locked: z.boolean().optional().default(false),
  error_budget_remaining_pct: z.coerce.number().default(0),
  audit_record_uri: z.string().optional(),
  actions_log: z.array(z.object({
    timestamp: z.string().optional(),
    action: z.string().optional(),
    status: z.string().optional(),
    actor: z.string().optional()
  })).optional().default([])
});

const approvalSchema = z.object({
  approval_id: z.string(),
  audit_id: z.string(),
  environment: z.string(),
  requested_action: z.string(),
  execution_mode: z.string(),
  status: z.string(),
  owner: z.string().optional().default("unassigned"),
  justification: z.string().optional().default("No justification was published."),
  requested_at: z.string().optional()
});

const alertPreviewSchema = z.object({
  audience: z.string(),
  channel: z.string(),
  anomaly_id: z.string().optional(),
  summary: z.string(),
  data_confidence: z.string().optional().default("UNKNOWN"),
  action_visibility: z.string().optional().default("Read-only"),
  audit_link_label: z.string().optional().default("Audit record")
});

const auditDiffSchema = z.object({
  audit_id: z.string(),
  before: z.array(z.string()).optional().default([]),
  after: z.array(z.string()).optional().default([]),
  correlation_id: z.string().optional().default("unknown"),
  idempotency_key: z.string().optional().default("unknown")
});

const adminSettingSchema = z.object({
  name: z.string(),
  value: z.string(),
  status: z.string()
});

export const dashboardSummarySchema = z.object({
  dashboard_schema_version: z.string().optional().default("legacy"),
  environment: z.string(),
  viewer_role: z.string().optional().default("finance"),
  generated_at: z.string(),
  tenant_id: z.string().optional(),
  data_freshness_status: z.string().optional().default("UNKNOWN"),
  containment_locked: z.boolean().optional().default(false),
  lock_reason: z.string().optional(),
  lock_since: z.string().optional(),
  error_budget_remaining_pct: z.coerce.number().default(100),
  workflow_status: z.string().optional(),
  last_successful_run_id: z.string().optional(),
  business_context: z.record(z.unknown()).optional(),
  telemetry_quality: z.record(z.unknown()).optional(),
  spend_trend: z.array(spendTrendRowSchema).default([]),
  anomalies: z.array(anomalySchema).default([]),
  impacted: z.array(impactedSchema).default([]),
  containment: z.array(containmentSchema).default([]),
  approvals: z.array(approvalSchema).default([]),
  alert_previews: z.array(alertPreviewSchema).default([]),
  audit_diffs: z.array(auditDiffSchema).default([]),
  admin_settings: z.array(adminSettingSchema).default([]),
  /**
   * How many ad-hoc manual-trigger runs the current tenant has used today.
   * Published by the dashboard-summary writer from the DynamoDB quota counter.
   * Frontend uses this to render the quota badge (used / 5) and disable the
   * button when the limit is reached.
   */
  ad_hoc_quota_used: z.coerce.number().int().min(0).max(5).default(0)
});

export type RuntimeConfig = z.infer<typeof runtimeConfigSchema>;
export type DashboardSummary = z.infer<typeof dashboardSummarySchema>;
export type Anomaly = DashboardSummary["anomalies"][number];
export type Containment = DashboardSummary["containment"][number];
