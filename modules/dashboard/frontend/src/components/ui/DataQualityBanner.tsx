import { useState } from "react";
import { AlertTriangle, CheckCircle2, X } from "lucide-react";
import { cn } from "../../lib/utils";
import type { DashboardSummary } from "../../schema";

interface DataQualityBannerProps {
  summary: DashboardSummary;
  lowConfidence: boolean;
}

export function DataQualityBanner({ summary, lowConfidence }: DataQualityBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const isHealthy =
    !summary.containment_locked &&
    !lowConfidence &&
    summary.data_freshness_status === "fresh";

  const messages: string[] = [];
  if (summary.containment_locked) {
    messages.push(`Containment locked: ${summary.lock_reason ?? "policy guard active"}.`);
  }
  if (lowConfidence) {
    messages.push("At least one anomaly has low telemetry confidence.");
  }
  if (!isHealthy) {
    messages.push(`Freshness: ${summary.data_freshness_status ?? "unknown"}.`);
  }

  if (isHealthy) {
    return (
      <div className={cn(
        "flex items-center gap-3 px-4 py-3 mb-5 rounded-lg border",
        "bg-accent-green/8 border-accent-green/25 text-accent-green"
      )}>
        <CheckCircle2 className="w-4 h-4 shrink-0" />
        <span className="text-sm font-medium flex-1">
          Dashboard data is fresh. Workflow state: {summary.workflow_status ?? "normal"}.
        </span>
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 opacity-50 hover:opacity-100 transition-opacity"
          aria-label="Dismiss banner"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className={cn(
      "flex items-start gap-3 px-4 py-3 mb-5 rounded-lg border",
      "bg-accent-amber/8 border-accent-amber/25 text-accent-amber"
    )}>
      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{messages.join(" ")}</p>
        {summary.workflow_status && (
          <p className="text-xs opacity-75 mt-0.5">Workflow: {summary.workflow_status}</p>
        )}
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="shrink-0 opacity-50 hover:opacity-100 transition-opacity mt-0.5"
        aria-label="Dismiss banner"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
