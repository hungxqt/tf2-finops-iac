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
  return (
    <PageContainer>
      <PanelCard
        icon={<LockKeyhole />}
        title="Containment & Audit"
        description="Read-only workflow state. Real Verify, Rollback, and Approval actions require a backend action gateway."
        aside={<StatusPill tone="neutral" label="Read-only first" />}
        noPadding
      >
        <ContainmentTable summary={summary} />
      </PanelCard>
    </PageContainer>
  );
}
