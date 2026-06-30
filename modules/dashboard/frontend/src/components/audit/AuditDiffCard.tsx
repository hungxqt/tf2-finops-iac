import { DiffTag } from "./DiffTag";
import type { DashboardSummary } from "../../schema";

type AuditDiffItem = DashboardSummary["audit_diffs"][number];

interface AuditDiffCardProps {
  item: AuditDiffItem;
}

export function AuditDiffCard({ item }: AuditDiffCardProps) {
  return (
    <div className="bg-surface-panel border border-border-subtle rounded-lg p-4 hover:border-border-strong transition-colors duration-150 space-y-3">
      {/* Header */}
      <div>
        <p className="font-mono text-sm font-semibold text-text-primary">{item.audit_id}</p>
        <div className="flex items-center gap-4 mt-1">
          <span className="font-mono text-[10px] text-text-muted">corr: {item.correlation_id}</span>
          <span className="font-mono text-[10px] text-text-muted">idem: {item.idempotency_key}</span>
        </div>
      </div>

      {/* Diff columns */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-accent-red/70 mb-2">Before</p>
          <div className="flex flex-wrap gap-1.5">
            {item.before.length > 0
              ? item.before.map((v) => <DiffTag key={v} value={v} tone="removed" />)
              : <span className="text-xs text-text-muted italic">No records</span>
            }
          </div>
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-accent-green/70 mb-2">After</p>
          <div className="flex flex-wrap gap-1.5">
            {item.after.length > 0
              ? item.after.map((v) => <DiffTag key={v} value={v} tone="added" />)
              : <span className="text-xs text-text-muted italic">No records</span>
            }
          </div>
        </div>
      </div>
    </div>
  );
}
