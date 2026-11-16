/** Plain-English formatting for the results page: £, years and the verdict wording. */

export type Verdict = "worth_it" | "borderline" | "not_yet";

/** £1,234 (rounded to the pound). Negative numbers get a proper minus sign. */
export function gbp(n: number): string {
  const s = `£${Math.round(Math.abs(n)).toLocaleString("en-GB")}`;
  return n < 0 ? `−${s}` : s;
}

/** £4,500 to £8,900 (or a single figure when both ends round to the same pound). */
export function gbpRange(low: number, high: number): string {
  const [a, b] = low <= high ? [low, high] : [high, low];
  return Math.round(a) === Math.round(b) ? gbp(a) : `${gbp(a)} to ${gbp(b)}`;
}

/** "8.2 years", "1 year", or a plain phrase when it doesn't pay back within the battery's life. */
export function years(y: number | null | undefined, life = 15): string {
  if (y === null || y === undefined) return `not within ${life} years`;
  const r = Math.round(y * 10) / 10;
  return `${r.toLocaleString("en-GB")} year${r === 1 ? "" : "s"}`;
}

/** "6 to 10 years", "6 years to never", etc., for a low/likely/high payback range. */
export function yearsRange(low: number | null, high: number | null, life = 15): string {
  if (low === null && high === null) return `not within ${life} years`;
  if (low === null) return years(high, life);
  if (high === null) return `${Math.round(low * 10) / 10} years, or not within ${life} years`;
  const a = Math.round(low * 10) / 10, b = Math.round(high * 10) / 10;
  return a === b ? years(a) : `${a.toLocaleString("en-GB")} to ${b.toLocaleString("en-GB")} years`;
}

export const kwh = (n: number) => `${Math.round(n).toLocaleString("en-GB")} kWh`;

export const VERDICT: Record<Verdict, { title: string; icon: string; summary: (warranty: number) => string; tone: string }> = {
  worth_it: {
    title: "Worth it",
    icon: "✓",
    summary: (w) => `A battery is likely to pay for itself well within its ${w}-year warranty.`,
    tone: "border-[#4ade80] bg-[#4ade80]/10",
  },
  borderline: {
    title: "Borderline",
    icon: "≈",
    summary: (w) => `A battery is likely to pay for itself, but only towards the end of its ${w}-year warranty.`,
    tone: "border-[#fbbf24] bg-[#fbbf24]/10",
  },
  not_yet: {
    title: "Not yet",
    icon: "✕",
    summary: (w) => `A battery isn't likely to pay for itself within its ${w}-year warranty at today's prices.`,
    tone: "border-slate-400 bg-slate-400/10",
  },
};

export const CONFIDENCE: Record<string, { label: string; text: string }> = {
  high: { label: "Based on a year of your data", text: "We used about a year of your real smart meter readings." },
  medium: { label: "Based on some of your data", text: "We used a few months of your real readings and filled in the rest of the year from typical seasonal patterns." },
  low: { label: "Based on a little of your data", text: "We had only a short stretch of your readings, so most of the year comes from typical patterns. Treat this as a rough guide." },
  estimate: { label: "Estimate", text: "We estimated your use from your home's details and typical patterns for homes like yours." },
};

export const BREAKDOWN_LABELS = {
  time_shifting: "Charging when electricity is cheap and using it when it's dearer",
  solar_storage: "Storing your solar instead of selling it for less",
  other: "Selling stored energy back to the grid",
} as const;

/** "15 November 2026" from an ISO date ("2026-11-15"); anything else is returned as it is. */
export function ukDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

/** Spell out the acronyms in the API's upgrade labels (e.g. "Solar panels (4 kWp)", "Home EV charger"). */
export function plainUpgradeLabel(label: string): string {
  return label
    .replace(/\((\d+(?:\.\d+)?) kWp\)/, (_, n) => `(${n} kWp, about ${Math.round(Number(n) / 0.4)} panels)`)
    .replace(/\bEV charger\b/, "electric car charger");
}

/** The "could be…" line under a payback figure; plain words when no case pays back. */
export function paybackNote(low: number | null, high: number | null, life = 15): string {
  if (low === null && high === null) return `Not in any of our cases, even the optimistic one`;
  return `Could be ${yearsRange(low, high, life)}`;
}
