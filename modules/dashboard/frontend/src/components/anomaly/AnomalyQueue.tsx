import { cn } from "../../lib/utils";
import { StatusPill } from "../ui/StatusPill";
import { ScrollArea } from "../ui/ScrollArea";
import { EmptyState } from "../ui/EmptyState";
import type { Anomaly } from "../../schema";

interface AnomalyQueueProps {
  anomalies: Anomaly[];
  selectedId: string;
  onSelect: (id: string) => void;
}

type Tone = "neutral" | "success" | "warning" | "critical" | "info" | "ai";

function severityTone(severity?: string): Tone {
  const s = String(severity || "").toLowerCase();
  if (s.includes("critical")) return "critical";
  if (s.includes("warn"))     return "warning";
  if (s.includes("low"))      return "ai";
  return "neutral";
}

function borderClass(severity?: string): string {
  const s = String(severity || "").toLowerCase();
  if (s.includes("critical")) return "border-l-accent-red";
  if (s.includes("warn"))     return "border-l-accent-amber";
  return "border-l-accent-teal";
}

const moneyFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const currency = (v: number) => moneyFmt.format(Number(v || 0));

export function AnomalyQueue({ anomalies, selectedId, onSelect }: AnomalyQueueProps) {
  if (anomalies.length === 0) {
    return <EmptyState title="No anomalies match" detail="Change filters or wait for a new dashboard summary." />;
  }

  return (
    <ScrollArea maxHeight="calc(100vh - 280px)" className="space-y-1.5">
      {anomalies.map((item) => {
        const isSelected = item.anomaly_id === selectedId;
        const tone = severityTone(item.severity);
        return (
          <button
            key={item.anomaly_id}
            onClick={() => onSelect(item.anomaly_id)}
            className={cn(
              "w-full text-left rounded-r-lg px-4 py-3 border-l-2 transition-all duration-150",
              borderClass(item.severity),
              isSelected
                ? "bg-accent-blue/8 border-l-accent-blue [box-shadow:var(--shadow-glow-blue)]"
                : "bg-surface-elevated/60 hover:bg-surface-elevated"
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-[10px] text-text-muted">{item.anomaly_id}</span>
                  <span className="text-sm font-semibold text-text-primary truncate">{item.service}</span>
                </div>
                <p className="text-xs text-text-secondary truncate">
                  {item.account_name} / {item.squad} / {currency(item.cost_delta_usd_per_day)}/day
                </p>
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <StatusPill tone={tone} label={item.severity} size="sm" />
                <span className="text-[10px] text-text-muted font-medium">
                  {Math.round(item.confidence_score * 100)}% conf
                </span>
              </div>
            </div>
          </button>
        );
      })}
    </ScrollArea>
  );
}
