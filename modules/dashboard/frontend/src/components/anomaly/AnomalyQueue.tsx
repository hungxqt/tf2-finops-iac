import { cn } from "../../lib/utils";
import { StatusPill } from "../ui/StatusPill";
import { ScrollArea } from "../ui/ScrollArea";
import { EmptyState } from "../ui/EmptyState";
import { currency } from "../../lib/format";
import { severityTone, severityBorderClass } from "../../lib/anomaly";
import type { Anomaly } from "../../schema";

interface AnomalyQueueProps {
  anomalies: Anomaly[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function AnomalyQueue({ anomalies, selectedId, onSelect }: AnomalyQueueProps) {
  if (anomalies.length === 0) {
    return <EmptyState title="No anomalies match" detail="Change filters or wait for a new dashboard summary." />;
  }

  const selectedIndex = anomalies.findIndex((a) => a.anomaly_id === selectedId);

  function handleKeyDown(e: React.KeyboardEvent) {
    let nextIndex: number | null = null;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        nextIndex = Math.min(selectedIndex + 1, anomalies.length - 1);
        break;
      case "ArrowUp":
        e.preventDefault();
        nextIndex = Math.max(selectedIndex - 1, 0);
        break;
      case "Home":
        e.preventDefault();
        nextIndex = 0;
        break;
      case "End":
        e.preventDefault();
        nextIndex = anomalies.length - 1;
        break;
    }
    if (nextIndex !== null && nextIndex !== selectedIndex) {
      onSelect(anomalies[nextIndex].anomaly_id);
    }
  }

  return (
    <ScrollArea maxHeight="calc(100vh - 280px)">
      <div
        role="listbox"
        aria-label="Anomaly queue"
        aria-activedescendant={selectedId ? `anomaly-${selectedId}` : undefined}
        onKeyDown={handleKeyDown}
        className="space-y-1.5"
      >
        {anomalies.map((item, idx) => {
          const isSelected = item.anomaly_id === selectedId;
          const tone = severityTone(item.severity);
          return (
            <button
              key={item.anomaly_id}
              id={`anomaly-${item.anomaly_id}`}
              role="option"
              aria-selected={isSelected}
              aria-label={`${item.service} anomaly, severity ${item.severity}, ${Math.round(item.confidence_score * 100)}% confidence. Position ${idx + 1} of ${anomalies.length}`}
              onClick={() => onSelect(item.anomaly_id)}
              className={cn(
                "w-full text-left rounded-r-lg px-4 py-3 border-l-2 transition-all duration-150",
                severityBorderClass(item.severity),
                isSelected
                  ? "bg-accent-blue/8 border-l-accent-blue [box-shadow:var(--shadow-glow-blue)]"
                  : "bg-surface-elevated/60 hover:bg-surface-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/70"
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
      </div>
    </ScrollArea>
  );
}
