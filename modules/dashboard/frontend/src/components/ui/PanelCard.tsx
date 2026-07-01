import { type ReactNode, useRef } from "react";
import { Download } from "lucide-react";
import { cn } from "../../lib/utils";
import { exportToCsv, exportChartToPng } from "../../lib/export";

interface PanelCardProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  aside?: ReactNode;
  noPadding?: boolean;
  children: ReactNode;
  className?: string;
  csvData?: string[][];
  csvFilename?: string;
  chartExportRef?: React.RefObject<HTMLDivElement | null>;
  chartFilename?: string;
}

export function PanelCard({ icon, title, description, aside, noPadding, children, className, csvData, csvFilename, chartExportRef, chartFilename }: PanelCardProps) {
  const chartRefInternal = useRef<HTMLDivElement>(null);
  const exportRef = chartExportRef ?? chartRefInternal;

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
        <div className="flex items-center gap-2 shrink-0">
          {csvData && csvFilename && (
            <button
              onClick={() => exportToCsv(csvData, csvFilename)}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-text-muted hover:text-text-primary hover:bg-surface-elevated border border-border-subtle hover:border-border-strong transition-colors"
              aria-label={`Export ${csvFilename} as CSV`}
              title="Export as CSV"
            >
              <Download className="w-3 h-3" />
              CSV
            </button>
          )}
          {chartExportRef && chartFilename && (
            <button
              onClick={() => exportChartToPng(exportRef.current, chartFilename)}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-text-muted hover:text-text-primary hover:bg-surface-elevated border border-border-subtle hover:border-border-strong transition-colors"
              aria-label={`Export ${chartFilename} as PNG`}
              title="Export as PNG"
            >
              <Download className="w-3 h-3" />
              PNG
            </button>
          )}
          {aside}
        </div>
      </div>

      {/* Body */}
      <div ref={exportRef} className={cn(noPadding ? "" : "p-5")}>
        {children}
      </div>
    </section>
  );
}
