import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Adaptive USD money formatter.
 *
 * Picks the minimum number of decimal places needed to display at least one
 * significant digit, so tiny sandbox values (e.g. 0.000831) show up as
 * "$0.000831" rather than "$0".
 *
 * Scale tiers:
 *   >= 1 000 000  → "$1.23M"
 *   >= 1 000      → "$1.23k"
 *   >= 1          → "$1.23"   (2 dp)
 *   >= 0.01       → "$0.0123" (4 dp)
 *   >= 0.0001     → "$0.000831" (6 dp)
 *   < 0.0001      → "$0.0000083" (7 dp) or "< $0.00001" when negligible
 */
export function formatMoney(raw: number, suffix = ""): string {
  const v = Number(raw) || 0;
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";

  let formatted: string;

  if (abs === 0) {
    formatted = "$0.00";
  } else if (abs >= 1_000_000) {
    formatted = `$${(abs / 1_000_000).toFixed(2)}M`;
  } else if (abs >= 1_000) {
    formatted = `$${(abs / 1_000).toFixed(2)}k`;
  } else if (abs >= 1) {
    formatted = new Intl.NumberFormat("en-US", {
      style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2
    }).format(abs);
  } else if (abs >= 0.01) {
    formatted = new Intl.NumberFormat("en-US", {
      style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4
    }).format(abs);
  } else if (abs >= 0.0001) {
    // Show 6 significant digits for micro-dollar values
    const dp = Math.max(2, Math.ceil(-Math.log10(abs)) + 2);
    formatted = new Intl.NumberFormat("en-US", {
      style: "currency", currency: "USD", minimumFractionDigits: dp, maximumFractionDigits: dp
    }).format(abs);
  } else {
    // Sub-micro: show up to 7 dp or flag as "< $0.00001"
    if (abs < 0.000001) {
      return `${sign}< $0.000001${suffix}`;
    }
    formatted = new Intl.NumberFormat("en-US", {
      style: "currency", currency: "USD", minimumFractionDigits: 7, maximumFractionDigits: 7
    }).format(abs);
  }

  return `${sign}${formatted}${suffix}`;
}

/**
 * Returns a Y-axis tick formatter suitable for a Recharts chart whose data
 * values are in `dataValues`. Picks a readable unit automatically.
 *
 * @param dataValues - All Y values in the chart dataset (actual + baseline).
 */
export function yAxisMoneyFormatter(dataValues: number[]): (v: number) => string {
  const maxAbs = Math.max(...dataValues.map(Math.abs), 0);

  if (maxAbs >= 1_000_000) return (v: number) => `$${(v / 1_000_000).toFixed(1)}M`;
  if (maxAbs >= 1_000)     return (v: number) => `$${(v / 1_000).toFixed(1)}k`;
  if (maxAbs >= 1)         return (v: number) => `$${v.toFixed(2)}`;
  if (maxAbs >= 0.01)      return (v: number) => v === 0 ? "$0" : `$${v.toFixed(4)}`;
  if (maxAbs >= 0.0001)    return (v: number) => v === 0 ? "$0" : `$${v.toFixed(6)}`;
  // Sub-micro values
  return (v: number) => v === 0 ? "$0" : `$${v.toFixed(7)}`;
}

