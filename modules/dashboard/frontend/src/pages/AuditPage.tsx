import { FileSearch } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { PanelCard } from "../components/ui/PanelCard";
import { EmptyState } from "../components/ui/EmptyState";
import { AuditDiffCard } from "../components/audit/AuditDiffCard";
import type { DashboardSummary } from "../schema";

interface AuditPageProps {
  summary: DashboardSummary;
}

export function AuditPage({ summary }: AuditPageProps) {
  return (
    <PageContainer>
      <PanelCard
        icon={<FileSearch />}
        title="Audit Evidence Diffs"
        description="Before and after containment state without raw JSON or command payloads."
      >
        {summary.audit_diffs.length === 0 ? (
          <EmptyState title="No audit diffs" detail="No before/after summaries were published." />
        ) : (
          <div className="space-y-4">
            {summary.audit_diffs.map((item) => (
              <AuditDiffCard key={item.audit_id} item={item} />
            ))}
          </div>
        )}
      </PanelCard>
    </PageContainer>
  );
}
