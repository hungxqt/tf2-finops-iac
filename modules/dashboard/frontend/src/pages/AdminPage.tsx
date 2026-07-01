import { Settings } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { PanelCard } from "../components/ui/PanelCard";
import { AdminSettings } from "../components/admin/AdminSettings";
import type { DashboardSummary } from "../schema";

interface AdminPageProps {
  summary: DashboardSummary;
}

export function AdminPage({ summary }: AdminPageProps) {
  return (
    <PageContainer>
      <PanelCard
        icon={<Settings />}
        title="Access Settings"
        description="Cognito groups and visibility policy for CDO admins."
      >
        <AdminSettings summary={summary} />
      </PanelCard>
    </PageContainer>
  );
}
