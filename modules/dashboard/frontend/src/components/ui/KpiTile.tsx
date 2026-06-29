import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "../../lib/utils";

type Tone = "info" | "success" | "warning" | "critical";

interface KpiTileProps {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: Tone;
  className?: string;
}

const gradientClasses: Record<Tone, string> = {
  info:     "from-accent-blue to-accent-cyan",
  success:  "from-accent-teal to-accent-green",
  warning:  "from-accent-amber to-orange-400",
  critical: "from-accent-red to-rose-400",
};

const iconColorClasses: Record<Tone, string> = {
  info:     "text-accent-blue",
  success:  "text-accent-teal",
  warning:  "text-accent-amber",
  critical: "text-accent-red",
};

export function KpiTile({ icon, label, value, detail, tone = "info", className }: KpiTileProps) {
  const valueRef = useRef<HTMLSpanElement>(null);

  // Count-up animation for numeric values
  useEffect(() => {
    const el = valueRef.current;
    if (!el) return;

    // Extract numeric part for animation
    const numMatch = value.replace(/,/g, "").match(/[-+]?[\d.]+/);
    if (!numMatch) return;
    const target = parseFloat(numMatch[0]);
    if (isNaN(target) || target === 0) return;

    const prefix = value.slice(0, value.indexOf(numMatch[0]));
    const suffix = value.slice(value.indexOf(numMatch[0]) + numMatch[0].length);

    let start: number | null = null;
    const duration = 900;

    function step(timestamp: number) {
      if (!start) start = timestamp;
      const progress = Math.min((timestamp - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      const current = target * eased;

      const formatted =
        target >= 1000
          ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(current)
          : new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(current);

      if (el) el.textContent = `${prefix}${formatted}${suffix}`;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, [value]);

  return (
    <article
      className={cn(
        "relative bg-surface-panel border border-border-subtle rounded-lg overflow-hidden min-h-[140px] p-5",
        "hover:border-border-strong hover:[box-shadow:var(--shadow-card)] transition-all duration-200",
        className
      )}
    >
      {/* Gradient top accent bar */}
      <div className={cn("absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r", gradientClasses[tone])} />

      {/* Icon */}
      <div className={cn("absolute top-5 right-5 opacity-50", iconColorClasses[tone])}>
        <div className="w-5 h-5 [&>svg]:w-full [&>svg]:h-full">{icon}</div>
      </div>

      {/* Label */}
      <p className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">{label}</p>

      {/* Value */}
      <p className="text-3xl font-bold text-text-primary mt-4 mb-1 leading-none">
        <span ref={valueRef}>{value}</span>
      </p>

      {/* Detail */}
      <p className="text-xs text-text-secondary">{detail}</p>
    </article>
  );
}
