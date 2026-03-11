/**
 * Typed API client — all communication with the FastAPI backend.
 * No calculation logic lives here; this is purely request/response.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface AnalyseParams {
  files: File[];
  tariffKey?: string;
  batteryCapKwh?: number;
  batteryCostGbp?: number;
  maxChargeRateKw?: number;
  efficiencyPct?: number;
  inflationPct?: number;
}

export interface RecalcParams {
  sessionId: string;
  tariffKey: string;
  batteryCapKwh: number;
  batteryCostGbp: number;
  maxChargeRateKw: number;
  efficiencyPct: number;
  inflationPct: number;
}

export interface Summary {
  days_analysed: number;
  total_kwh: number;
  daily_avg_kwh: number;
  annual_kwh_estimate: number;
  inferred_rate_pence: number | null;
}

export interface Financials {
  ann_cost_current: number;
  ann_cost_no_battery: number;
  ann_cost_with_battery: number;
  saving_battery_only: number;
  saving_tariff_switch: number;
  total_saving: number;
  payback_years: number | null;
  roi_10yr: number;
}

export interface HeatmapCell {
  battery_kwh: number;
  payback_years: number | null;
  total_saving: number;
  roi_10yr: number;
}

export interface HeatmapRow {
  tariff_key: string;
  tariff_name: string;
  cells: HeatmapCell[];
}

export interface TariffRankRow {
  tariff_key: string;
  tariff_name: string;
  tariff_color: string;
  battery_kwh: number;
  total_saving: number;
  payback_years: number | null;
  roi_10yr: number;
}

export interface BatteryRankRow {
  battery_kwh: number;
  battery_label: string;
  battery_cost: number;
  total_saving: number;
  payback_years: number | null;
  roi_10yr: number;
}

export interface AnalyseResult {
  session_id: string;
  summary: Summary;
  selected: {
    tariff_key: string;
    tariff_name: string;
    battery_cap_kwh: number;
    battery_cost_gbp: number;
    max_charge_rate_kw: number;
    efficiency_pct: number;
    inflation_pct: number;
  };
  financials: Financials;
  charts: {
    soc_profile: number[];
    cumulative_savings: number[];
    heatmap: HeatmapRow[];
  };
  recommendations: {
    best_tariff_key: string | null;
    best_battery_kwh: number | null;
    tariff_ranking: TariffRankRow[];
    battery_ranking: BatteryRankRow[];
  };
  all_combinations: TariffRankRow[];
}

export interface Tariff {
  key: string;
  name: string;
  supplier: string;
  description: string;
  color: string;
  standing_charge_pence: number;
  is_flat_rate: boolean;
  is_dynamic: boolean;
  slot_rates_pence: number[];
}

// ── Helpers ────────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ── Public API ─────────────────────────────────────────────────────────────────

export async function analyse(params: AnalyseParams): Promise<AnalyseResult> {
  const form = new FormData();
  for (const file of params.files) form.append("files", file);
  if (params.tariffKey)       form.append("tariff_key",          params.tariffKey);
  if (params.batteryCapKwh)   form.append("battery_cap_kwh",     String(params.batteryCapKwh));
  if (params.batteryCostGbp)  form.append("battery_cost_gbp",    String(params.batteryCostGbp));
  if (params.maxChargeRateKw) form.append("max_charge_rate_kw",  String(params.maxChargeRateKw));
  if (params.efficiencyPct)   form.append("efficiency_pct",      String(params.efficiencyPct));
  if (params.inflationPct !== undefined) form.append("inflation_pct", String(params.inflationPct));

  return apiFetch<AnalyseResult>("/api/analyse", { method: "POST", body: form });
}

export async function recalculate(params: RecalcParams): Promise<AnalyseResult> {
  return apiFetch<AnalyseResult>("/api/recalculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id:          params.sessionId,
      tariff_key:          params.tariffKey,
      battery_cap_kwh:     params.batteryCapKwh,
      battery_cost_gbp:    params.batteryCostGbp,
      max_charge_rate_kw:  params.maxChargeRateKw,
      efficiency_pct:      params.efficiencyPct,
      inflation_pct:       params.inflationPct,
    }),
  });
}

export async function fetchTariffs(): Promise<Tariff[]> {
  return apiFetch<Tariff[]>("/api/tariffs");
}
