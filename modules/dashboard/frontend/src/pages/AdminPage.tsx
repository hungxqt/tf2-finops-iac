import { Settings } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { PanelCard } from "../components/ui/PanelCard";
import { EmptyState } from "../components/ui/EmptyState";
import { AdminSettings } from "../components/admin/AdminSettings";
import type { DashboardSummary } from "../schema";

interface AdminPageProps {
  summary: DashboardSummary;
}

function isAdmin(role: string): boolean {
  return ["admin", "cdo"].includes(role.toLowerCase());
}

export function AdminPage({ summary }: AdminPageProps) {
  const canAccess = isAdmin(summary.viewer_role);

  return (
    <PageContainer>
      <PanelCard
        icon={<Settings />}
        title="Access Settings"
        description="Cognito groups and visibility policy for CDO admins."
      >
        {canAccess ? (
          <AdminSettings summary={summary} />
        ) : (
          <EmptyState
            title="Restricted view"
            detail="Finance and Engineering roles see operational state, not access management controls. Request CDO admin access if needed."
          />
        )}
      </PanelCard>
    </PageContainer>
  );
}
