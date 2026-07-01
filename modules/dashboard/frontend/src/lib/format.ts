const moneyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 6,
});

export function currency(v: number, suffix = ""): string {
  const num = Number(v || 0);
  if (num === 0) return `$0${suffix}`;
  if (Math.abs(num) < 0.01) {
    return `$${num.toFixed(6)}${suffix}`;
  }
  return `${moneyFmt.format(num)}${suffix}`;
}

export function pct(v: number): string {
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(Number(v || 0))}%`;
}

export function formatDateTime(ts?: string): string {
  if (!ts) return "not published";
  return new Date(ts).toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(ts?: string, now = Date.now()): string {
  if (!ts) return "";
  const diff = now - new Date(ts).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "< 1h ago";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function formatDateLabel(value?: string): string {
  return formatDateTime(value);
}
