import { cn } from "../../lib/utils";
import type { DashboardSummary } from "../../schema";

interface TopbarProps {
  title: string;
  summary: DashboardSummary;
}

function freshnessTone(status: string): string {
  const s = status?.toLowerCase();
  if (s === "fresh") return "success";
  if (s === "stale" || s === "unknown") return "warning";
  return "neutral";
}

function pillClass(tone: string): string {
  switch (tone) {
    case "success": return "bg-accent-green/10 text-accent-green border-accent-green/30";
    case "warning": return "bg-accent-amber/10 text-accent-amber border-accent-amber/30";
    case "critical": return "bg-accent-red/10 text-accent-red border-accent-red/30";
    case "info":    return "bg-accent-blue/10 text-accent-blue border-accent-blue/30";
    default:        return "bg-surface-elevated text-text-secondary border-border-subtle";
  }
}

function formatTs(ts?: string): string {
  if (!ts) return "not published";
  return new Date(ts).toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function Topbar({ title, summary }: TopbarProps) {
  const isLocked = summary.containment_locked;

  return (
    <header className="h-14 shrink-0 flex items-center justify-between gap-4 px-6 bg-surface-panel/80 border-b border-border-subtle backdrop-blur-sm sticky top-0 z-10">
      {/* Left: page title */}
      <div className="flex items-center gap-3 min-w-0">
        {isLocked && (
          <span className="shrink-0 w-2 h-2 rounded-full bg-accent-amber animate-pulse-dot" title="Containment locked" />
        )}
        <h1 className="text-base font-semibold text-text-primary truncate">{title}</h1>
      </div>

      {/* Right: meta pills */}
      <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
        <span className={cn("inline-flex items-center px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border", pillClass("neutral"))}>
          {summary.environment}
        </span>
        <span className={cn("inline-flex items-center px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border", pillClass("info"))}>
          {summary.viewer_role}
        </span>
        <span className={cn("inline-flex items-center px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border", pillClass(freshnessTone(summary.data_freshness_status || "")))}>
          {summary.data_freshness_status || "unknown"}
        </span>
        <span className="text-[11px] text-text-muted hidden sm:inline">
          {formatTs(summary.generated_at)}
        </span>
      </div>
    </header>
  );
}
