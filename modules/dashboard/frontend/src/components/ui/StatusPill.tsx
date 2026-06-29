import { cn } from "../../lib/utils";

type Tone = "neutral" | "success" | "warning" | "critical" | "info" | "ai";
type Size = "sm" | "md";

interface StatusPillProps {
  tone?: Tone;
  label: string;
  dot?: boolean;
  size?: Size;
  className?: string;
}

const toneClasses: Record<Tone, string> = {
  neutral:  "bg-surface-elevated text-text-secondary border-border-subtle",
  success:  "bg-accent-green/10 text-accent-green border-accent-green/30",
  warning:  "bg-accent-amber/10 text-accent-amber border-accent-amber/30",
  critical: "bg-accent-red/10 text-accent-red border-accent-red/30",
  info:     "bg-accent-blue/10 text-accent-blue border-accent-blue/30",
  ai:       "bg-accent-violet/10 text-accent-violet border-accent-violet/30",
};

const dotClasses: Record<Tone, string> = {
  neutral:  "bg-text-muted",
  success:  "bg-accent-green",
  warning:  "bg-accent-amber animate-pulse-dot",
  critical: "bg-accent-red animate-pulse-dot",
  info:     "bg-accent-blue",
  ai:       "bg-accent-violet",
};

const sizeClasses: Record<Size, string> = {
  sm: "text-[10px] px-2 py-0.5 rounded-full",
  md: "text-[10px] px-2.5 py-1 rounded-md",
};

export function StatusPill({ tone = "neutral", label, dot, size = "md", className }: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-bold uppercase tracking-wider border whitespace-nowrap",
        toneClasses[tone],
        sizeClasses[size],
        className
      )}
    >
      {dot && <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", dotClasses[tone])} />}
      {label}
    </span>
  );
}
