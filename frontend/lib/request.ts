/**
 * Turn the homeowner's answers (all in the query string) into the API v2 assess request.
 * Used by the "check your details" step to say what's missing, and by the results page.
 */
import type { AssessRequest } from "./api-v2-types";
import { parseEstimate } from "./estimate.ts";
import { parseJourney } from "./journey.ts";
import { isTimeOfUse, parseTariff } from "./tariff.ts";

export type Missing = "route" | "usage_kwh" | "property_type" | "files" | "tariff";

export interface BuiltRequest {
  request: AssessRequest | null;   // null until nothing is missing
  missing: Missing[];
}

type QueryLike = URLSearchParams | string | { toString(): string };

/**
 * @param hasFiles  whether usage files are loaded for the upload route (they live in memory, not the URL)
 */
export function buildAssessRequest(query: QueryLike, hasFiles = false): BuiltRequest {
  const j = parseJourney(query);
  const e = parseEstimate(query);
  const t = parseTariff(query);
  const missing: Missing[] = [];

  if (!j.route) missing.push("route");
  if (j.route === "estimate") {
    if (e.propertyType === null) missing.push("property_type");
    if (e.annualKwh === null) missing.push("usage_kwh");
  }
  if (j.route === "upload" && !hasFiles) missing.push("files");
  if (t.choice === "tou") missing.push("tariff");
  if (missing.length) return { request: null, missing };

  const request: AssessRequest = {
    usage: j.route === "estimate"
      ? { route: "estimate", annual_kwh: e.annualKwh!, property_type: e.propertyType!, heating_type: e.heating }
      : { route: "upload", property_type: e.propertyType ?? "semi", heating_type: e.heating },
    ev: j.home.ev === "none"
      ? { status: "none" }
      : { status: j.home.ev, ...(e.evMiles !== null ? { annual_miles: e.evMiles } : {}) },
    heat_pump: j.home.heat_pump === "none"
      ? { status: "none" }
      : {
          status: j.home.heat_pump,
          ...(e.floorArea !== null ? { floor_area_m2: e.floorArea } : {}),
          ...(e.epcRating !== null ? { epc_rating: e.epcRating } : {}),
        },
    // The journey asks only whether they have solar; the API assumes a typical 4 kWp south-facing roof.
    solar: { status: j.home.solar },
    tariff: {
      ...(isTimeOfUse(t.choice) ? { current_tariff_key: t.choice } : {}),
      ...(t.choice === "flat" && t.unitRateP !== null ? { unit_rate_p: t.unitRateP } : {}),
      ...(t.choice === "flat" && t.standingP !== null ? { standing_charge_p: t.standingP } : {}),
      ...(t.exportP !== null ? { export_rate_p: t.exportP } : {}),
    },
    battery: {},
  };
  return { request, missing: [] };
}
