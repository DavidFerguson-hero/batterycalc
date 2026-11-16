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
  solar: boolean;           // include solar panels
}

export type LoadStatus = "none" | "have" | "planning";

/** Starting point: the answer they already have. */
export function initialWhatIf(
  rec: { battery_kwh: number; installed_price: number },
  ev: LoadStatus,
  hp: LoadStatus,
  solar: LoadStatus = "none",
): WhatIf {
  return {
    sizeKwh: rec.battery_kwh, priceGbp: rec.installed_price,
    ev: ev !== "none", heatPump: hp !== "none", solar: solar !== "none",
  };
}

export function sameWhatIf(a: WhatIf, b: WhatIf): boolean {
  return a.sizeKwh === b.sizeKwh && a.priceGbp === b.priceGbp && a.ev === b.ev && a.heatPump === b.heatPump
    && a.solar === b.solar;
}

export const PRICE_MIN = 500;
export const PRICE_MAX = 50000;

/**
 * The request for a what-if. A car, heat pump or solar panels they already have stay as they
 * are (they're in their usage); ones they only plan, or don't have, are switched by the toggle.
 */
export function applyWhatIf(base: AssessRequest, w: WhatIf): AssessRequest {
  const ev = base.ev ?? { status: "none" as const };
  const hp = base.heat_pump ?? { status: "none" as const };
  const solar = base.solar ?? { status: "none" as const };
  const price = Math.min(PRICE_MAX, Math.max(PRICE_MIN, Math.round(w.priceGbp)));
  return {
    ...base,
    ev: ev.status === "have" ? ev : w.ev ? { ...ev, status: "planning" } : { status: "none" },
    heat_pump: hp.status === "have" ? hp : w.heatPump ? { ...hp, status: "planning" } : { status: "none" },
    solar: solar.status === "have" ? solar : w.solar ? { ...solar, status: "planning" } : { status: "none" },
    battery: { ...base.battery, size_kwh: w.sizeKwh, price_gbp: price },
  };
}

/** "Your electric car and solar panels are already included." Null when they have none of them. */
export function alreadyIncludedNote(ev: LoadStatus, hp: LoadStatus, solar: LoadStatus): string | null {
  const items = [
    ...(ev === "have" ? ["electric car"] : []),
    ...(hp === "have" ? ["heat pump"] : []),
    ...(solar === "have" ? ["solar panels"] : []),
  ];
  if (!items.length) return null;
  const list = items.length === 1 ? items[0] : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
  const plural = items.length > 1 || items[0] === "solar panels";
  return `Your ${list} ${plural ? "are" : "is"} already included.`;
}
