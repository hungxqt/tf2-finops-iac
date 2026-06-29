import { StatusPill } from "../ui/StatusPill";
import type { DashboardSummary } from "../../schema";

type AlertPreviewItem = DashboardSummary["alert_previews"][number];
type Tone = "neutral" | "success" | "warning" | "critical" | "info" | "ai";

interface AlertPreviewCardProps {
  item: AlertPreviewItem;
}

function audienceTone(audience: string): Tone {
  const a = audience.toLowerCase();
  if (a === "finance")     return "success";
  if (a === "engineering") return "ai";
  return "neutral";
}

function confidenceLabel(value?: string): string {
  const v = String(value || "").toUpperCase();
  if (v === "HIGH") return "Complete telemetry";
  if (v === "LOW")  return "Telemetry gap";
  return "Unknown confidence";
}

export function AlertPreviewCard({ item }: AlertPreviewCardProps) {
  return (
    <div className="bg-surface-panel border border-border-subtle rounded-lg p-4 hover:border-border-strong transition-colors duration-150 space-y-3">
      {/* Audience + channel */}
      <div className="flex items-center gap-2 flex-wrap">
        <StatusPill tone={audienceTone(item.audience)} label={item.audience} />
        <span className="text-sm text-text-secondary">{item.channel}</span>
      </div>

      {/* Summary */}
      <p className="text-sm text-text-primary leading-relaxed">{item.summary}</p>

      {/* Footer meta */}
      <div className="flex items-center gap-2 flex-wrap pt-1 border-t border-border-subtle">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] text-text-muted border border-border-subtle bg-surface-elevated">
          {confidenceLabel(item.data_confidence)}
        </span>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] text-text-muted border border-border-subtle bg-surface-elevated">
          {item.action_visibility}
        </span>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] text-text-muted border border-border-subtle bg-surface-elevated">
          {item.audit_link_label}
        </span>
      </div>
    </div>
  );
}
