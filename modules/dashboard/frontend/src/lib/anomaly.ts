export type Tone = "neutral" | "success" | "warning" | "critical" | "info" | "ai";

export function severityTone(severity?: string): Tone {
  const s = String(severity || "").toLowerCase();
  if (s.includes("critical")) return "critical";
  if (s.includes("warn")) return "warning";
  if (s.includes("low")) return "ai";
  return "neutral";
}

export function severityBorderClass(severity?: string): string {
  const s = String(severity || "").toLowerCase();
  if (s.includes("critical")) return "border-l-accent-red";
  if (s.includes("warn")) return "border-l-accent-amber";
  return "border-l-accent-teal";
}
