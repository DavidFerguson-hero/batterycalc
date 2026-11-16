/**
 * The homeowner's current tariff, kept in the query string.
 *
 *   tariff=flat               a standard single-rate tariff, at rate= and sc= if given
 *   tariff=<key>              one of the time-of-use tariffs we model (GET /api/tariffs)
 *   (absent)                  not sure: use typical price-cap figures
 *   tariff=tou                on a time-of-use tariff but hasn't picked which one yet
 *   rate=  unit rate, pence per kWh (flat only)
 *   sc=    standing charge, pence per day (flat only)
 *   exp=   export rate, pence per kWh, for stored energy sold back
 */

export type TariffChoice = "flat" | "unsure" | string;

export interface TariffAnswers {
  choice: TariffChoice;
  unitRateP: number | null;
  standingP: number | null;
  exportP: number | null;
}

/** Typical figures used when the homeowner isn't sure (the API's defaults: price-cap level, early 2026). */
export const TYPICAL_RATE_P = 28.16;
export const TYPICAL_STANDING_P = 53;

export const DEFAULT_TARIFF: TariffAnswers = { choice: "unsure", unitRateP: null, standingP: null, exportP: null };

type QueryLike = URLSearchParams | string | { toString(): string };
const asParams = (q: QueryLike) => (q instanceof URLSearchParams ? q : new URLSearchParams(q.toString()));

function num(v: string | null, lo: number, hi: number): number | null {
  if (v === null || !/^\d+(\.\d{1,2})?$/.test(v)) return null;
  const n = Number(v);
  return n >= lo && n <= hi ? n : null;
}

export function parseTariff(q: QueryLike): TariffAnswers {
  const p = asParams(q);
  const t = p.get("tariff");
  const choice: TariffChoice = !t ? "unsure" : /^[A-Za-z][A-Za-z0-9]{0,40}$/.test(t) ? t : "unsure";
  return {
    choice,
    unitRateP: choice === "flat" ? num(p.get("rate"), 5, 100) : null,
    standingP: choice === "flat" ? num(p.get("sc"), 0, 200) : null,
    exportP: num(p.get("exp"), 0, 100),
  };
}

export function writeTariff(t: TariffAnswers, existing: QueryLike = ""): string {
  const out = new URLSearchParams(asParams(existing));
  const set = (k: string, v: string | number | null) => (v === null ? out.delete(k) : out.set(k, String(v)));
  set("tariff", t.choice === "unsure" ? null : t.choice);
  set("rate", t.choice === "flat" ? t.unitRateP : null);
  set("sc", t.choice === "flat" ? t.standingP : null);
  set("exp", t.exportP);
  out.sort();
  return out.toString();
}

/** A specific time-of-use tariff key ("flat", "unsure" and "tou" aren't tariff keys). */
export function isTimeOfUse(choice: TariffChoice): boolean {
  return choice !== "flat" && choice !== "unsure" && choice !== "tou";
}
