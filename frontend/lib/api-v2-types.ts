/* Generated from docs/api-v2.schema.json by scripts/gen-api-types.mjs. Do not edit by hand. */

/* eslint-disable */

export interface AssessRequest {
  battery?: BatteryInput;
  ev?: EVInput;
  heat_pump?: HeatPumpInput;
  tariff?: TariffInput;
  usage: UsageInput;
}
export interface BatteryInput {
  efficiency_pct?: number;
  max_charge_rate_kw?: number;
  /**
   * Empty: typical installed price for the size.
   */
  price_gbp?: number | null;
  /**
   * Empty: recommend the best-value size.
   */
  size_kwh?: number | null;
  /**
   * Empty: the best tariff for this battery.
   */
  tariff_key?: string | null;
}
export interface EVInput {
  annual_miles?: number;
  charge_end?: string;
  charge_start?: string;
  kwh_per_mile?: number;
  status?: "none" | "have" | "planning";
}
export interface HeatPumpInput {
  efficiency?: number;
  epc_rating?: string | null;
  floor_area_m2?: number | null;
  heat_demand_kwh?: number | null;
  status?: "none" | "have" | "planning";
}
export interface TariffInput {
  /**
   * Leave empty for a flat rate at unit_rate_p and standing_charge_p.
   */
  current_tariff_key?: string | null;
  /**
   * Pence per kWh for stored energy sold back.
   */
  export_rate_p?: number;
  /**
   * Pence per day.
   */
  standing_charge_p?: number;
  /**
   * Pence per kWh. Empty: inferred from the CSV cost column, else the price cap rate.
   */
  unit_rate_p?: number | null;
}
export interface UsageInput {
  /**
   * Required for the estimate route.
   */
  annual_kwh?: number | null;
  /**
   * From the EPC: "electric" when there is no mains gas.
   */
  heating_type?: "gas" | "electric";
  property_type?: "flat" | "terraced" | "semi" | "detached";
  /**
   * "estimate": from annual_kwh. "upload": from half-hourly CSV files sent as multipart "files".
   */
  route: "estimate" | "upload";
}


export interface AssessResponse {
  assumptions: Assumptions;
  break_even: BreakEven;
  context_costs: {
    [k: string]: ContextCost | undefined;
  };
  day_in_life: DayInLife;
  fair_price: FairPrice;
  headline: Headline;
  recommendation: Recommendation;
  saving_breakdown: SavingBreakdown;
  schema_version?: "2.0";
  size_comparison: SizeComparison;
  tariff_check: TariffCheck;
  usage: UsageSummary;
  verdict: "worth_it" | "borderline" | "not_yet";
  what_would_make_it_pay_back: Levers | null;
}
export interface Assumptions {
  battery_life_years: number;
  capacity_loss_pct_per_year: number;
  costs_as_of: string;
  inverter_replacement_cost: number;
  inverter_replacement_year: number | null;
  price_growth_pct: {
    [k: string]: number | undefined;
  };
  tariffs_checked: string;
  verdict_thresholds: {
    [k: string]: number | undefined;
  };
  warranty_years: number;
}
export interface BreakEven {
  likely: number[];
  optimistic: number[];
  pessimistic: number[];
  years: number[];
}
export interface ContextCost {
  after_grant?: {
    [k: string]: number | undefined;
  } | null;
  grant?: number | null;
  grant_name?: string | null;
  high: number;
  label: string;
  low: number;
  typical: number;
}
export interface DayInLife {
  average: DayFlows;
  summer: DayFlows | null;
  winter: DayFlows | null;
}
export interface DayFlows {
  battery_level: number[];
  from_battery: number[];
  grid_to_battery: number[];
  grid_to_home: number[];
  label: string;
  load: number[];
}
export interface FairPrice {
  as_of: string;
  high: number;
  kwh: number;
  low: number;
  typical: number;
  your_price?: number | null;
  your_price_is?: ("below_range" | "within_range" | "above_range") | null;
}
export interface Headline {
  average_yearly_saving: Range;
  installed_cost: Range1;
  lifetime_net_gain: Range1;
  payback_years: OptionalRange;
  /**
   * £ in year 1, beyond the best tariff without a battery.
   */
  year1_battery_saving: number;
}
/**
 * £ a year averaged over the battery's life, per case.
 */
export interface Range {
  high: number;
  likely: number;
  low: number;
}
export interface Range1 {
  high: number;
  likely: number;
  low: number;
}
/**
 * None means 'not within the battery's life'.
 */
export interface OptionalRange {
  high: number | null;
  likely: number | null;
  low: number | null;
}
export interface Recommendation {
  battery_kwh: number;
  battery_label: string;
  chosen_by: "best_value" | "you";
  installed_price: number;
  tariff_key: string;
  tariff_name: string;
}
export interface SavingBreakdown {
  other: number;
  solar_storage: number;
  time_shifting: number;
  total: number;
}
export interface SizeComparison {
  all_sizes: SizeRow[];
  best_value: BestSize;
  biggest_saving_kwh: number;
  larger: SizeRow | null;
  smaller: SizeRow | null;
}
export interface SizeRow {
  installed_cost: number;
  kwh: number;
  label: string;
  lifetime_net_gain: number;
  payback_years: number | null;
  tariff_key: string;
  tariff_name: string;
  verdict: "worth_it" | "borderline" | "not_yet";
  year1_battery_saving: number;
}
export interface BestSize {
  fair_price: FairPrice;
  installed_cost: number;
  kwh: number;
  label: string;
  lifetime_net_gain: number;
  payback_years: number | null;
  tariff_key: string;
  tariff_name: string;
  verdict: "worth_it" | "borderline" | "not_yet";
  year1_battery_saving: number;
}
export interface TariffCheck {
  battery_adds: number;
  best_no_battery: TariffOption;
  best_with_battery: TariffOption;
  by_tariff: TariffRow[];
  current: {};
  savings: {
    [k: string]: number | undefined;
  };
  switch_first: boolean;
  switch_share_of_best: number | null;
}
export interface TariffOption {
  annual_cost: number;
  key: string;
  name: string;
}
export interface TariffRow {
  annual_cost_no_battery: number;
  annual_cost_with_battery: number;
  key: string;
  name: string;
}
export interface UsageSummary {
  /**
   * Modelled year, including any planned EV or heat pump.
   */
  annual_kwh: number;
  confidence: "high" | "medium" | "low" | "estimate";
  /**
   * Upload route: dates found, gaps filled, days scaled.
   */
  coverage: {} | null;
  /**
   * Days with real readings (upload route).
   */
  days_found: number | null;
  days_modelled: number;
  extra_loads: {} | null;
  route: "estimate" | "upload";
  /**
   * Current unit rate used, pence per kWh.
   */
  unit_rate_p: number;
}
export interface Levers {
  add_ev: VerdictChange | null;
  price: PriceLever;
  switch_tariff: VerdictChange | null;
}
export interface VerdictChange {
  annual_miles?: number | null;
  changes_verdict: boolean;
  payback_years: number | null;
  tariff_key: string;
  tariff_name: string;
  verdict: "worth_it" | "borderline" | "not_yet";
  year1_battery_saving: number;
}
export interface PriceLever {
  current_price: number;
  price_for_payback_within_warranty: number | null;
  price_for_worth_it: number | null;
}
