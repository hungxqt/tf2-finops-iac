import { StatusPill } from "../ui/StatusPill";
import { EmptyState } from "../ui/EmptyState";
import type { DashboardSummary } from "../../schema";

interface AdminSettingsProps {
  summary: DashboardSummary;
}

type Tone = "neutral" | "success" | "warning" | "critical" | "info" | "ai";

function settingTone(status: string): Tone {
  const s = status.toLowerCase();
  if (s.includes("read-only") || s.includes("readonly")) return "success";
  if (s.includes("admin"))    return "info";
  if (s.includes("disabled")) return "warning";
  if (s.includes("operator")) return "ai";
  return "neutral";
}

export function AdminSettings({ summary }: AdminSettingsProps) {
  if (summary.admin_settings.length === 0) {
    return <EmptyState title="No admin settings" detail="Access settings have not been published." />;
  }

  return (
    <div className="divide-y divide-border-subtle">
      {summary.admin_settings.map((item) => (
        <div key={item.name} className="flex items-center justify-between gap-4 px-1 py-3.5 hover:bg-surface-elevated/30 transition-colors rounded">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text-primary">{item.name}</p>
            <p className="text-xs text-text-secondary mt-0.5 font-mono">{item.value}</p>
          </div>
          <StatusPill tone={settingTone(item.status)} label={item.status} size="sm" />
        </div>
      ))}
    </div>
  );
}
