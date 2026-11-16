/** Plain-English summary of a modelled day (half-hourly kWh, 48 slots from midnight). */

export interface Day {
  load: number[];
  grid_to_battery: number[];
  from_battery: number[];
  grid_to_home: number[];
  battery_level: number[];
}

/** "00:00" … "23:30" for slot 0 … 47. */
export function slotTime(i: number): string {
  const m = (((i % 48) + 48) % 48) * 30;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

const sum = (a: number[]) => a.reduce((s, v) => s + v, 0);
const THRESHOLD = 0.01;   // kWh in a half hour; below this counts as "not charging"

/**
 * The longest run of half hours spent charging, as "00:30 to 04:30" (wrapping past
 * midnight). null when the battery doesn't charge from the grid that day.
 */
export function chargeWindow(gridToBattery: number[]): string | null {
  const n = gridToBattery.length;
  const on = gridToBattery.map((v) => v > THRESHOLD);
  if (!on.some(Boolean)) return null;
  if (on.every(Boolean)) return "all day";
  let best = { start: 0, len: 0 };
  // Start from a slot that isn't charging so a run that wraps midnight is counted once.
  const origin = on.indexOf(false);
  let start = -1, len = 0;
  for (let k = 1; k <= n; k++) {
    const i = (origin + k) % n;
    if (on[i]) {
      if (start < 0) { start = i; len = 0; }
      len++;
      if (len > best.len) best = { start, len };
    } else {
      start = -1;
    }
  }
  return `${slotTime(best.start)} to ${slotTime(best.start + best.len)}`;
}

export interface DaySummary {
  use: number;            // kWh the home uses
  fromBattery: number;    // kWh of that the battery covers
  share: number;          // 0–1
  charged: number;        // kWh drawn from the grid into the battery
  window: string | null;  // main charging time
}

export function summariseDay(d: Day): DaySummary {
  const use = sum(d.load);
  const fromBattery = sum(d.from_battery);
  return {
    use,
    fromBattery,
    share: use > 0 ? Math.min(1, fromBattery / use) : 0,
    charged: sum(d.grid_to_battery),
    window: chargeWindow(d.grid_to_battery),
  };
}
