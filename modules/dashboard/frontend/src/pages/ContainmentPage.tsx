import { useMemo } from "react";
import { LockKeyhole } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { PanelCard } from "../components/ui/PanelCard";
import { StatusPill } from "../components/ui/StatusPill";
import { ContainmentTable } from "../components/containment/ContainmentTable";
import type { DashboardSummary } from "../schema";

interface ContainmentPageProps {
  summary: DashboardSummary;
}

export function ContainmentPage({ summary }: ContainmentPageProps) {
  const csvData = useMemo<string[][]>(() => {
    const header = ["Audit ID", "Resource", "Account", "Squad", "Mode", "Status", "Error Budget", "Action"];
    const rows = summary.containment.map((c) => [
      c.audit_id,
      c.resource_id,
      c.account_id,
      c.squad ?? "",
      c.execution_mode ?? "",
      c.status ?? "",
      String(c.error_budget_remaining_pct),
      c.action_type ?? "",
    ]);
    return [header, ...rows];
  }, [summary.containment]);
  return (
    <PageContainer>
      <PanelCard
        icon={<LockKeyhole />}
        title="Containment & Audit"
        description="Read-only workflow state. Real Verify, Rollback, and Approval actions require a backend action gateway."
        aside={<StatusPill tone="neutral" label="Read-only first" />}
        noPadding
        csvData={csvData}
        csvFilename="containment-audit"
      >
        <ContainmentTable summary={summary} />
      </PanelCard>
    </PageContainer>
  );
}
