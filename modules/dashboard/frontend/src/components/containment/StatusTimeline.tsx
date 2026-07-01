import { useEffect, useState } from "react";
import { cn } from "../../lib/utils";
import { relativeTime, formatDateTime } from "../../lib/format";
import type { Containment } from "../../schema";

type ActionLog = NonNullable<Containment["actions_log"]>[number];

interface StatusTimelineProps {
  log: ActionLog[];
}

function dotColor(status?: string): string {
  const s = String(status || "").toLowerCase();
  if (s.includes("complet") || s.includes("success")) return "bg-accent-green";
  if (s.includes("pending") || s.includes("dry_run")) return "bg-accent-amber";
  if (s.includes("fail") || s.includes("error"))      return "bg-accent-red";
  return "bg-text-muted";
}

export function StatusTimeline({ log }: StatusTimelineProps) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(id);
  }, []);

  if (!log || log.length === 0) return null;

  return (
    <div className="pl-4 border-l-2 border-border-subtle ml-3 space-y-3 py-3">
      {log.map((entry, i) => (
        <div key={i} className="relative flex items-start gap-3">
          {/* Dot on the timeline line */}
          <div className={cn("absolute -left-[21px] top-1 w-3 h-3 rounded-full border-2 border-surface-panel shrink-0", dotColor(entry.status))} />

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className="text-[10px] text-text-muted"
                title={formatDateTime(entry.timestamp)}
              >
                {relativeTime(entry.timestamp, now)}
              </span>
              {entry.actor && (
                <span className="text-[10px] text-accent-cyan font-mono">{entry.actor}</span>
              )}
            </div>
            <p className="text-xs font-semibold text-text-primary mt-0.5">{entry.action}</p>
            {entry.status && (
              <p className="text-[10px] text-text-secondary">{entry.status}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
