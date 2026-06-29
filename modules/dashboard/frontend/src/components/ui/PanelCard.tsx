import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface PanelCardProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  aside?: ReactNode;
  noPadding?: boolean;
  children: ReactNode;
  className?: string;
}

export function PanelCard({ icon, title, description, aside, noPadding, children, className }: PanelCardProps) {
  return (
    <section className={cn("bg-surface-panel border border-border-subtle rounded-lg overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-border-subtle">
        <div className="flex items-start gap-3 min-w-0">
          {icon && (
            <div className="shrink-0 p-1.5 rounded bg-accent-blue/10 text-accent-blue mt-0.5">
              <div className="w-4 h-4 [&>svg]:w-full [&>svg]:h-full">{icon}</div>
            </div>
          )}
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-text-primary leading-snug">{title}</h2>
            {description && (
              <p className="text-xs text-text-secondary mt-0.5 leading-relaxed">{description}</p>
            )}
          </div>
        </div>
        {aside && <div className="shrink-0">{aside}</div>}
      </div>

      {/* Body */}
      <div className={cn(noPadding ? "" : "p-5")}>
        {children}
      </div>
    </section>
  );
}
