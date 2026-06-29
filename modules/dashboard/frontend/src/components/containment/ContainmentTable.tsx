import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { StatusPill } from "../ui/StatusPill";
import { StatusTimeline } from "./StatusTimeline";
import { EmptyState } from "../ui/EmptyState";
import { cn } from "../../lib/utils";
import type { DashboardSummary, Containment } from "../../schema";

interface ContainmentTableProps {
  summary: DashboardSummary;
}

type Tone = "neutral" | "success" | "warning" | "critical" | "info" | "ai";

function statusTone(s?: string): Tone {
  const v = String(s || "").toLowerCase();
  if (v.includes("approv") || v.includes("complet") || v.includes("done")) return "success";
  if (v.includes("pending")) return "warning";
  if (v.includes("fail") || v.includes("error")) return "critical";
  return "neutral";
}

function budgetClass(pct: number): string {
  if (pct > 50) return "text-accent-green";
  if (pct > 20) return "text-accent-amber";
  return "text-accent-red";
}

const pct = (v: number) =>
  `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(Number(v || 0))}%`;

export function ContainmentTable({ summary }: ContainmentTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (summary.containment.length === 0) {
    return (
      <EmptyState
        title="No containment records"
        detail="Workflow audit summaries have not been published yet."
        className="m-5"
      />
    );
  }

  function toggleRow(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] border-collapse text-sm">
        <thead>
          <tr className="bg-surface-base">
            {["Audit ID", "Resource", "Squad", "Mode", "Status", "Error Budget", "Action Policy"].map((h) => (
              <th key={h} className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-subtle">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {summary.containment.map((item: Containment) => {
            const isExpanded = expandedId === item.audit_id;
            return (
              <>
                <tr
                  key={item.audit_id}
                  onClick={() => toggleRow(item.audit_id)}
                  className={cn(
                    "border-b border-border-subtle/60 cursor-pointer transition-colors duration-100",
                    isExpanded ? "bg-surface-elevated" : "hover:bg-surface-elevated/40"
                  )}
                >
                  <td className="px-4 py-3 align-top">
                    <p className="font-mono text-xs text-accent-cyan">{item.audit_id}</p>
                    {item.audit_record_uri && (
                      <p className="text-[10px] text-text-muted mt-0.5 truncate max-w-[200px]" title={item.audit_record_uri}>
                        {item.audit_record_uri}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <p className="text-xs font-medium text-text-primary">{item.resource_id}</p>
                    <p className="text-[10px] text-text-muted">{item.account_id}</p>
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-text-secondary">{item.squad}</td>
                  <td className="px-4 py-3 align-top">
                    <StatusPill
                      tone={item.execution_mode === "dry-run" ? "warning" : "success"}
                      label={item.execution_mode}
                      size="sm"
                    />
                  </td>
                  <td className="px-4 py-3 align-top">
                    <StatusPill tone={statusTone(item.status)} label={item.status} size="sm" />
                  </td>
                  <td className="px-4 py-3 align-top">
                    <span className={cn("text-sm font-bold", budgetClass(item.error_budget_remaining_pct))}>
                      {pct(item.error_budget_remaining_pct)}
                    </span>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-muted italic">Handled by Step Functions</span>
                      <ChevronDown className={cn("w-3 h-3 text-text-muted transition-transform duration-200", isExpanded && "rotate-180")} />
                    </div>
                  </td>
                </tr>
                {isExpanded && (item.actions_log?.length ?? 0) > 0 && (
                  <tr key={`${item.audit_id}-timeline`}>
                    <td colSpan={7} className="bg-surface-base/80 px-8 pb-3 border-b border-border-subtle">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted pt-3 pb-1">Actions Log</p>
                      <StatusTimeline log={item.actions_log ?? []} />
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
