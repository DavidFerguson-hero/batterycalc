/**
 * "What if…?" changes on the results page (story H14). Each is applied on top of the
 * homeowner's own request and re-run through the API; nothing here changes their answers.
 */
import type { AssessRequest } from "./api-v2-types";

export interface WhatIf {
  sizeKwh: number;          // battery size to try
  priceGbp: number;         // fitted price to try
  ev: boolean;              // include an electric car
  heatPump: boolean;        // include a heat pump
}

export type LoadStatus = "none" | "have" | "planning";

/** Starting point: the answer they already have. */
export function initialWhatIf(
  rec: { battery_kwh: number; installed_price: number },
  ev: LoadStatus,
  hp: LoadStatus,
): WhatIf {
  return { sizeKwh: rec.battery_kwh, priceGbp: rec.installed_price, ev: ev !== "none", heatPump: hp !== "none" };
}

export function sameWhatIf(a: WhatIf, b: WhatIf): boolean {
  return a.sizeKwh === b.sizeKwh && a.priceGbp === b.priceGbp && a.ev === b.ev && a.heatPump === b.heatPump;
}

export const PRICE_MIN = 500;
export const PRICE_MAX = 50000;

/**
 * The request for a what-if. A car or heat pump they already have stays as it is
 * (it's in their usage); one they only plan, or don't have, is switched by the toggle.
 */
export function applyWhatIf(base: AssessRequest, w: WhatIf): AssessRequest {
  const ev = base.ev ?? { status: "none" as const };
  const hp = base.heat_pump ?? { status: "none" as const };
  const price = Math.min(PRICE_MAX, Math.max(PRICE_MIN, Math.round(w.priceGbp)));
  return {
    ...base,
    ev: ev.status === "have" ? ev : w.ev ? { ...ev, status: "planning" } : { status: "none" },
    heat_pump: hp.status === "have" ? hp : w.heatPump ? { ...hp, status: "planning" } : { status: "none" },
    battery: { ...base.battery, size_kwh: w.sizeKwh, price_gbp: price },
  };
}
