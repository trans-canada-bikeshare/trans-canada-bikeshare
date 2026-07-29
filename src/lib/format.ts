/** Number and date formatting, in one place so every surface agrees. */

const CA = "en-CA";

export function compact(n: number): string {
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}k`;
  return n.toLocaleString(CA);
}

export function full(n: number): string {
  return Number.isFinite(n) ? n.toLocaleString(CA) : "—";
}

export function percent(n: number, digits = 1): string {
  return Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : "—";
}

/** Seconds to a compact human duration: 754 -> "12m 34s". */
export function duration(seconds: number): string {
  if (!Number.isFinite(seconds)) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`;
  return `${m}m ${s}s`;
}

/** "2025-06" -> "Jun 2025". Month keys are always YYYY-MM. */
export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  if (!y || !m) return key;
  return `${new Date(Date.UTC(y, m - 1, 1)).toLocaleString(CA, { month: "short", timeZone: "UTC" })} ${y}`;
}

export const MONTH_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** "2026-07-28" -> "28 July 2026", for stating a data window in prose. */
export function longDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(CA, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}
