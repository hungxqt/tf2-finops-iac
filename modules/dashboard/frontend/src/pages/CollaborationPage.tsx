import { Clock3, Users } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { PanelCard } from "../components/ui/PanelCard";
import { EmptyState } from "../components/ui/EmptyState";
import { ApprovalCard } from "../components/approvals/ApprovalCard";
import { AlertPreviewCard } from "../components/approvals/AlertPreviewCard";
import type { DashboardSummary } from "../schema";

interface CollaborationPageProps {
  summary: DashboardSummary;
}

export function CollaborationPage({ summary }: CollaborationPageProps) {
  return (
    <PageContainer>
      <div className="grid grid-cols-2 gap-4 max-lg:grid-cols-1">
        {/* Manual Approvals */}
        <PanelCard
          icon={<Clock3 />}
          title="Manual Approval Intent"
          description="Human-review queue shown without mutating controls."
        >
          {summary.approvals.length === 0 ? (
            <EmptyState title="No approval intent" detail="No non-production apply-mode actions are waiting for human review." />
          ) : (
            <div className="space-y-3">
              {summary.approvals.map((item) => (
                <ApprovalCard key={item.approval_id} item={item} />
              ))}
            </div>
          )}
        </PanelCard>

        {/* Alert Routing */}
        <PanelCard
          icon={<Users />}
          title="Alert Routing Preview"
          description="Finance and Engineering notification previews."
        >
          {summary.alert_previews.length === 0 ? (
            <EmptyState title="No alert previews" detail="Alert routing summaries have not been published yet." />
          ) : (
            <div className="space-y-3">
              {summary.alert_previews.map((item, i) => (
                <AlertPreviewCard key={`${item.audience}-${item.anomaly_id}-${i}`} item={item} />
              ))}
            </div>
          )}
        </PanelCard>
      </div>
    </PageContainer>
  );
}
