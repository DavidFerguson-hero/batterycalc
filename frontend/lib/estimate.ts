/**
 * The quick-estimate answers (route B), kept in the query string next to lib/journey.ts.
 *
 * Only facts about the home go in the URL. The postcode and address never do, so a
 * shared link doesn't say where someone lives.
 */

export type PropertyType = "flat" | "terraced" | "semi" | "detached";
export const PROPERTY_TYPES: readonly PropertyType[] = ["flat", "terraced", "semi", "detached"];
export const PROPERTY_LABELS: Record<PropertyType, string> = {
  flat: "Flat or maisonette", terraced: "Terraced house", semi: "Semi-detached house", detached: "Detached house",
};

export type Heating = "gas" | "electric";

export interface EstimateAnswers {
  annualKwh: number | null;
  propertyType: PropertyType | null;
  bedrooms: number | null;      // 1–5 (5 means 5 or more)
  heating: Heating;             // "electric" when the home is heated by electricity
  people: number | null;        // 1–6 (6 means 6 or more)
  evMiles: number | null;       // only asked when an EV is in the picture
  floorArea: number | null;     // m², from the EPC
  epcRating: string | null;     // A–G, from the EPC
}

export const DEFAULT_ESTIMATE: EstimateAnswers = {
  annualKwh: null, propertyType: null, bedrooms: null, heating: "gas",
  people: null, evMiles: null, floorArea: null, epcRating: null,
};

const KEYS = {
  annualKwh: "kwh", propertyType: "prop", bedrooms: "beds", heating: "heat",
  people: "people", evMiles: "miles", floorArea: "area", epcRating: "epc",
} as const;

type QueryLike = URLSearchParams | string | { toString(): string };
const asParams = (q: QueryLike) => (q instanceof URLSearchParams ? q : new URLSearchParams(q.toString()));

function intIn(v: string | null, lo: number, hi: number): number | null {
  if (v === null || !/^\d+$/.test(v)) return null;
  const n = Number(v);
  return n >= lo && n <= hi ? n : null;
}

/** Read the estimate answers. Anything missing or out of range comes back as null. */
export function parseEstimate(q: QueryLike): EstimateAnswers {
  const p = asParams(q);
  const prop = p.get(KEYS.propertyType);
  const epc = (p.get(KEYS.epcRating) ?? "").toUpperCase();
  return {
    annualKwh: intIn(p.get(KEYS.annualKwh), 500, 20000),
    propertyType: PROPERTY_TYPES.includes(prop as PropertyType) ? (prop as PropertyType) : null,
    bedrooms: intIn(p.get(KEYS.bedrooms), 1, 5),
    heating: p.get(KEYS.heating) === "electric" ? "electric" : "gas",
    people: intIn(p.get(KEYS.people), 1, 6),
    evMiles: intIn(p.get(KEYS.evMiles), 0, 60000),
    floorArea: intIn(p.get(KEYS.floorArea), 15, 1000),
    epcRating: /^[A-G]$/.test(epc) ? epc : null,
  };
}

/** Write the estimate answers into a query string, keeping everything else in it. */
export function writeEstimate(e: EstimateAnswers, existing: QueryLike = ""): string {
  const out = new URLSearchParams(asParams(existing));
  const set = (key: string, v: string | number | null) => (v === null ? out.delete(key) : out.set(key, String(v)));
  set(KEYS.annualKwh, e.annualKwh);
  set(KEYS.propertyType, e.propertyType);
  set(KEYS.bedrooms, e.bedrooms);
  set(KEYS.heating, e.heating === "electric" ? "electric" : null);   // gas is the default
  set(KEYS.people, e.people);
  set(KEYS.evMiles, e.evMiles);
  set(KEYS.floorArea, e.floorArea === null ? null : Math.round(e.floorArea));
  set(KEYS.epcRating, e.epcRating);
  out.sort();
  return out.toString();
}

/** Enough to run the estimate route. */
export function isComplete(e: EstimateAnswers): boolean {
  return e.annualKwh !== null && e.propertyType !== null;
}

// ── Suggested annual use ──────────────────────────────────────────────────────

/**
 * Typical metered electricity use (kWh a year) by property type and bedrooms, for homes
 * heated by other fuels. Same table as the API's SUGGESTED_KWH (BEIS domestic statistics,
 * api/engine/profile_estimator.py); keep the two in step.
 */
export const SUGGESTED_KWH: Record<PropertyType, Record<number, number>> = {
  flat: { 1: 1800, 2: 2400, 3: 2900 },
  terraced: { 2: 2800, 3: 3200, 4: 3800 },
  semi: { 2: 3000, 3: 3500, 4: 4200 },
  detached: { 3: 4200, 4: 5100, 5: 6500 },
};

export function typicalKwh(prop: PropertyType, beds: number): number {
  const table = SUGGESTED_KWH[prop];
  if (table[beds]) return table[beds];
  const sizes = Object.keys(table).map(Number);
  const nearest = sizes.reduce((a, b) => (Math.abs(b - beds) < Math.abs(a - beds) ? b : a));
  return table[nearest];
}

/**
 * How many people typically live in a home with this many bedrooms (England average,
 * approximate). More or fewer people than that moves everyday electricity use up or down.
 */
const TYPICAL_PEOPLE: Record<number, number> = { 1: 1.5, 2: 2, 3: 2.6, 4: 3, 5: 3.3 };
const PER_PERSON = 0.12;   // APPROXIMATE: each person above or below typical changes everyday use by ~12%

export function peopleFactor(people: number | null, beds: number): number {
  if (people === null) return 1;
  const typical = TYPICAL_PEOPLE[Math.min(Math.max(beds, 1), 5)];
  return Math.min(1.4, Math.max(0.7, 1 + PER_PERSON * (people - typical)));
}

const round100 = (n: number) => Math.round(n / 100) * 100;

/**
 * Suggested annual use for the answers so far. If the EPC lookup gave an estimate that
 * includes electric heating, only the everyday part (not the heating) is adjusted for
 * the number of people.
 */
export function suggestKwh(prop: PropertyType, beds: number, people: number | null, epcAnnualKwh?: number | null): number {
  const everyday = typicalKwh(prop, beds);
  const heating = epcAnnualKwh ? Math.max(0, epcAnnualKwh - everyday) : 0;
  return Math.min(20000, Math.max(500, round100(everyday * peopleFactor(people, beds) + heating)));
}
