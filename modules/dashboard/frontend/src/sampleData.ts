import type { DashboardSummary } from "./schema";

export const sampleDashboardData: DashboardSummary = {
  dashboard_schema_version: "2026-01",
  environment: "sandbox",
  viewer_role: "finance",
  generated_at: "2026-06-26T09:00:00Z",
  tenant_id: "tenant-demo-finops",
  data_freshness_status: "fresh",
  containment_locked: true,
  lock_reason: "error_budget_exceeded_threshold",
  lock_since: "2026-06-24T08:00:00Z",
  error_budget_remaining_pct: 0.8,
  workflow_status: "dry-run enforced",
  last_successful_run_id: "run-2026-06-26-0900",
  business_context: {
    traffic_source: "ALB",
    traffic_volume: 120000,
    campaign_flag: false,
    load_test_flag: false,
    migration_flag: false
  },
  telemetry_quality: {
    completeness_score: 0.92,
    missing_cloudwatch: false,
    delayed_cur: false
  },
  spend_trend: [
    ["2026-03-29", 812, 790, false],
    ["2026-04-05", 844, 805, false],
    ["2026-04-12", 862, 821, false],
    ["2026-04-19", 905, 836, false],
    ["2026-04-26", 932, 852, false],
    ["2026-05-03", 948, 867, false],
    ["2026-05-10", 973, 882, false],
    ["2026-05-17", 998, 896, false],
    ["2026-05-24", 1036, 910, true],
    ["2026-05-31", 1072, 925, false],
    ["2026-06-07", 1128, 941, false],
    ["2026-06-14", 1216, 958, true],
    ["2026-06-21", 1264, 976, true],
    ["2026-06-26", 1194, 988, false]
  ],
  anomalies: [
    {
      anomaly_id: "ANM-2026-0623A",
      severity: "CRITICAL",
      account_id: "200000000010",
      account_name: "ml-research",
      service: "AmazonEC2",
      squad: "squad-prediction-models",
      owner_tag_status: "valid",
      confidence_score: 0.94,
      data_confidence: "HIGH",
      evidence_window_start: "2026-06-22T00:00:00Z",
      evidence_window_end: "2026-06-23T23:59:59Z",
      cost_delta_usd_per_day: 427.5,
      workflow_status: "pending approval",
      business_context: { traffic_volume: 120000, traffic_source: "ALB" },
      telemetry_quality: { completeness_score: 0.94, missing_cloudwatch: false },
      explanation: "GPU training instances ran continuously above the expected baseline and exceeded the approved experiment window."
    },
    {
      anomaly_id: "ANM-2026-0621B",
      severity: "WARNING",
      account_id: "200000000011",
      account_name: "staging",
      service: "AmazonRDS",
      squad: "central-cdo",
      owner_tag_status: "missing owner",
      confidence_score: 0.76,
      data_confidence: "LOW",
      evidence_window_start: "2026-06-20T00:00:00Z",
      evidence_window_end: "2026-06-21T23:59:59Z",
      cost_delta_usd_per_day: 118.2,
      workflow_status: "alert-only",
      telemetry_quality: { completeness_score: 0.48, missing_cloudwatch: true },
      explanation: "Database spend rose while CloudWatch utilization was incomplete, so the platform stayed in alert-only mode."
    }
  ],
  impacted: [
    { name: "squad-prediction-models", type: "Squad", spend_delta_usd_per_day: 427.5, owner_tag_status: "valid" },
    { name: "AmazonEC2", type: "Service", spend_delta_usd_per_day: 427.5, owner_tag_status: "valid" },
    { name: "ml-research", type: "Account", spend_delta_usd_per_day: 427.5, owner_tag_status: "valid" },
    { name: "central-cdo", type: "Squad", spend_delta_usd_per_day: 118.2, owner_tag_status: "missing owner" }
  ],
  containment: [
    {
      audit_id: "ANM-2026-0623A",
      resource_id: "i-0fbgpu00000004",
      account_id: "200000000010",
      squad: "squad-prediction-models",
      action_type: "tag-for-review",
      execution_mode: "dry-run",
      status: "PENDING_APPROVAL",
      containment_locked: true,
      error_budget_remaining_pct: 0.8,
      audit_record_uri: "s3://company-cdo-200000000010-telemetry/audit/year=2026/month=06/ANM-2026-0623A.json",
      actions_log: [
        { timestamp: "2026-06-23T17:05:46Z", action: "tag-for-review", status: "DRY_RUN_COMPLETED", actor: "finops-ai-engine-role" }
      ]
    }
  ],
  approvals: [
    {
      approval_id: "APR-2026-0623A",
      audit_id: "ANM-2026-0623A",
      environment: "sandbox",
      requested_action: "quota-cap",
      execution_mode: "apply",
      status: "PENDING_APPROVAL",
      owner: "squad-prediction-models",
      justification: "Non-production GPU quota cap needs human approval before apply-mode enforcement.",
      requested_at: "2026-06-23T17:12:00Z"
    }
  ],
  alert_previews: [
    {
      audience: "Finance",
      channel: "SNS or SES",
      anomaly_id: "ANM-2026-0623A",
      summary: "Critical cost spike above $100/day with complete ingestion.",
      data_confidence: "HIGH",
      action_visibility: "No action buttons or CLI commands",
      audit_link_label: "CloudFront audit record"
    },
    {
      audience: "Engineering",
      channel: "Slack digest or Jira ticket",
      anomaly_id: "ANM-2026-0623A",
      summary: "Owner squad receives resource, environment, tag status, and proposed rollback path.",
      data_confidence: "HIGH",
      action_visibility: "Read-only status until action gateway exists",
      audit_link_label: "Authenticated audit link"
    }
  ],
  audit_diffs: [
    {
      audit_id: "ANM-2026-0623A",
      before: ["finops:review absent", "quota unchanged", "owner tag valid"],
      after: ["finops:review=pending", "quota cap proposed", "audit retained 90 days"],
      correlation_id: "corr-uuid-4444-5555-6666",
      idempotency_key: "tenant-uuid-1111-2222-3333:2026-06-22:daily_batch"
    }
  ],
  admin_settings: [
    { name: "Finance group", value: "finops-finance-readonly", status: "read-only" },
    { name: "Engineering group", value: "finops-engineering-operator", status: "operator visibility" },
    { name: "CDO admin group", value: "finops-cdo-admin", status: "admin controls" },
    { name: "Synthetic data visibility", value: "local development only", status: "disabled in production" }
  ]
};
