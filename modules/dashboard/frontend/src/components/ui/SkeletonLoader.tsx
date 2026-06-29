import { cn } from "../../lib/utils";

type SkeletonVariant = "line" | "card" | "kpi" | "table";

interface SkeletonLoaderProps {
  variant?: SkeletonVariant;
  height?: string;
  rows?: number;
  className?: string;
}

function SkeletonBase({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={cn("animate-shimmer rounded", className)} style={style} />;
}

export function SkeletonLoader({ variant = "line", height, rows = 5, className }: SkeletonLoaderProps) {
  if (variant === "line") {
    return <SkeletonBase className={cn("h-4 w-full", className)} />;
  }

  if (variant === "card") {
    return (
      <SkeletonBase
        className={cn("w-full rounded-lg border border-border-subtle", className)}
        style={{ height: height ?? "200px" } as React.CSSProperties}
      />
    );
  }

  if (variant === "kpi") {
    return (
      <div className={cn("bg-surface-panel border border-border-subtle rounded-lg overflow-hidden min-h-[140px] p-5 relative", className)}>
        <div className="absolute top-0 left-0 right-0 h-[3px] animate-shimmer" />
        <SkeletonBase className="h-3 w-24 mb-5" />
        <SkeletonBase className="h-8 w-32 mb-2" />
        <SkeletonBase className="h-3 w-20" />
      </div>
    );
  }

  if (variant === "table") {
    return (
      <div className={cn("space-y-2", className)}>
        {/* header */}
        <div className="flex gap-4 px-4 py-3 border-b border-border-subtle">
          {[35, 20, 15, 15, 15].map((w, i) => (
            <SkeletonBase key={i} className={`h-3`} style={{ width: `${w}%` } as React.CSSProperties} />
          ))}
        </div>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-4 px-4 py-3 border-b border-border-subtle/50">
            {[35, 20, 15, 15, 15].map((w, j) => (
              <SkeletonBase key={j} className="h-3" style={{ width: `${w}%` } as React.CSSProperties} />
            ))}
          </div>
        ))}
      </div>
    );
  }

  return null;
}
