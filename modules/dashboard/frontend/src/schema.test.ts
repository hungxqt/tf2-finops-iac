import { describe, expect, it } from "vitest";
import { dashboardSummarySchema } from "./schema";
import { sampleDashboardData } from "./sampleData";

describe("dashboard summary schema", () => {
  it("accepts the 2026 dashboard summary contract", () => {
    const parsed = dashboardSummarySchema.parse(sampleDashboardData);

    expect(parsed.dashboard_schema_version).toBe("2026-01");
    expect(parsed.anomalies[0].business_context?.traffic_source).toBe("ALB");
  });

  it("rejects summaries missing critical identity fields", () => {
    expect(() => dashboardSummarySchema.parse({ generated_at: "2026-06-26T09:00:00Z" })).toThrow();
  });
});
