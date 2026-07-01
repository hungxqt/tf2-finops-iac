import { describe, expect, it } from "vitest";
import { dashboardSummarySchema } from "./schema";

describe("dashboard summary schema", () => {
  it("accepts the 2026 dashboard summary contract", () => {
    const testSummary = {
      dashboard_schema_version: "2026-01",
      environment: "sandbox",
      viewer_role: "finance",
      generated_at: "2026-06-26T09:00:00Z",
      tenant_id: "tenant-demo-finops",
      anomalies: [
        {
          anomaly_id: "ANM-2026-0623A",
          severity: "CRITICAL",
          account_id: "200000000010",
          service: "AmazonEC2",
          confidence_score: 0.94,
          business_context: { traffic_source: "ALB" }
        }
      ]
    };
    const parsed = dashboardSummarySchema.parse(testSummary);

    expect(parsed.dashboard_schema_version).toBe("2026-01");
    expect((parsed.anomalies[0].business_context as Record<string, unknown>).traffic_source).toBe("ALB");
  });

  it("rejects summaries missing critical identity fields", () => {
    expect(() => dashboardSummarySchema.parse({ generated_at: "2026-06-26T09:00:00Z" })).toThrow();
  });
});
