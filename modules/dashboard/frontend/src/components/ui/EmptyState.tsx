import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cn } from "../../lib/utils";

interface EmptyStateProps {
  title: string;
  detail?: string;
  icon?: ReactNode;
  className?: string;
}

export function EmptyState({ title, detail, icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 min-h-[160px] p-6 text-center",
        "border border-dashed border-border-strong rounded-lg bg-surface-base/50",
        className
      )}
    >
      <div className="text-text-muted opacity-50 animate-icon-float">
        {icon ?? <Inbox className="w-8 h-8" />}
      </div>
      <p className="text-sm font-semibold text-text-secondary">{title}</p>
      {detail && <p className="text-xs text-text-muted max-w-xs">{detail}</p>}
    </div>
  );
}
