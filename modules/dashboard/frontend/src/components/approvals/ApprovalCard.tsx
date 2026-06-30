import { LockKeyhole } from "lucide-react";
import { StatusPill } from "../ui/StatusPill";
import type { DashboardSummary } from "../../schema";

type ApprovalItem = DashboardSummary["approvals"][number];

interface ApprovalCardProps {
  item: ApprovalItem;
}

function formatTs(ts?: string): string {
  if (!ts) return "";
  return new Date(ts).toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function ApprovalCard({ item }: ApprovalCardProps) {
  return (
    <div className="bg-surface-panel border border-border-subtle rounded-lg p-4 hover:border-border-strong transition-colors duration-150 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] text-text-muted">{item.approval_id}</p>
          <p className="text-sm font-semibold text-text-primary mt-0.5">{item.audit_id}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusPill tone="neutral" label={item.environment} size="sm" />
          <StatusPill tone="warning" label={item.status} size="sm" dot />
        </div>
      </div>

      {/* Justification */}
      <p className="text-sm text-text-secondary italic leading-relaxed">"{item.justification}"</p>

      {/* Footer */}
      <div className="flex items-center justify-between gap-3 pt-1 border-t border-border-subtle">
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">Owner: <span className="text-text-secondary font-medium">{item.owner}</span></span>
          <StatusPill tone={item.execution_mode === "apply" ? "critical" : "warning"} label={item.execution_mode} size="sm" />
        </div>
        {item.requested_at && (
          <span className="text-[10px] text-text-muted">{formatTs(item.requested_at)}</span>
        )}
      </div>

      {/* Readonly notice */}
      <div className="flex items-center gap-1.5 text-[10px] text-text-muted italic">
        <LockKeyhole className="w-3 h-3" />
        Read-only: approval action is not exposed from the static dashboard.
      </div>
    </div>
  );
}
