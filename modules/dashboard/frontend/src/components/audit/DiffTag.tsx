import { memo } from "react";
import { cn } from "../../lib/utils";

interface DiffTagProps {
  value: string;
  tone: "added" | "removed";
}

export const DiffTag = memo(function DiffTag({ value, tone }: DiffTagProps) {
  return (
    <span
      className={cn(
        "inline-flex font-mono text-[11px] px-2 py-0.5 rounded border",
        tone === "added"
          ? "bg-accent-green/10 text-accent-green border-accent-green/25"
          : "bg-accent-red/10 text-accent-red border-accent-red/25"
      )}
    >
      {tone === "added" ? "+" : "-"} {value}
    </span>
  );
});
