"""
Request and response models for POST /api/v2/assess (task 1.9).

These models are the contract with the front end: every response is validated
against AssessResponse before it is sent, and its JSON Schema is published at
docs/api-v2.schema.json. See docs/api-v2.md for the field-by-field guide.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "2.0"

PropertyType = Literal["flat", "terraced", "semi", "detached"]
HeatingType = Literal["gas", "electric"]
LoadStatus = Literal["none", "have", "planning"]
Verdict = Literal["worth_it", "borderline", "not_yet"]
Confidence = Literal["high", "medium", "low", "estimate"]
Orientation = Literal["south", "south_east", "south_west", "east", "west"]
_HHMM = r"^([01]\d|2[0-3]):(00|30)$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Request ───────────────────────────────────────────────────────────────────

class UsageInput(_Strict):
    route: Literal["estimate", "upload"] = Field(
        description='"estimate": from annual_kwh. "upload": from half-hourly CSV files sent as multipart "files".')
    annual_kwh: Optional[float] = Field(None, ge=500, le=20000, description="Required for the estimate route.")
    property_type: PropertyType = "semi"
    heating_type: HeatingType = Field("gas", description='From the EPC: "electric" when there is no mains gas.')


class EVInput(_Strict):
    status: LoadStatus = "none"
    annual_miles: float = Field(7000, ge=0, le=60000)
    kwh_per_mile: float = Field(0.3, ge=0.1, le=1.0)
    charge_start: str = Field("00:30", pattern=_HHMM)
    charge_end: str = Field("04:30", pattern=_HHMM)


class HeatPumpInput(_Strict):
    status: LoadStatus = "none"
    heat_demand_kwh: Optional[float] = Field(None, ge=500, le=60000)
    floor_area_m2: Optional[float] = Field(None, ge=15, le=1000)
    epc_rating: Optional[str] = Field(None, pattern=r"^[A-Ga-g]$")
    efficiency: float = Field(3.0, ge=1.5, le=6.0)


class SolarInput(_Strict):
    status: LoadStatus = Field(
        "none", description='"have": panels already fitted. "planning": panels you plan to add.')
    kwp: float = Field(4.0, ge=0.5, le=20, description="Size of the panels in kWp (kilowatts peak).")
    orientation: Orientation = Field("south", description="Which way the panels face.")


class TariffInput(_Strict):
    current_tariff_key: Optional[str] = Field(
        None, description="Leave empty for a flat rate at unit_rate_p and standing_charge_p.")
    unit_rate_p: Optional[float] = Field(
        None, ge=5, le=100, description="Pence per kWh. Empty: inferred from the CSV cost column, else the price cap rate.")
    standing_charge_p: float = Field(53.0, ge=0, le=200, description="Pence per day.")
    export_rate_p: float = Field(
        0.0, ge=0, le=100, description="Pence per kWh for electricity sold back: spare solar and stored energy.")


class BatteryInput(_Strict):
    size_kwh: Optional[float] = Field(None, ge=1, le=50, description="Empty: recommend the best-value size.")
    price_gbp: Optional[float] = Field(None, ge=500, le=50000, description="Empty: typical installed price for the size.")
    tariff_key: Optional[str] = Field(None, description="Empty: the best tariff for this battery.")
    max_charge_rate_kw: float = Field(3.6, ge=0.5, le=15)
    efficiency_pct: float = Field(90.0, ge=50, le=100)


class AssessRequest(_Strict):
    usage: UsageInput
    ev: EVInput = EVInput()
    heat_pump: HeatPumpInput = HeatPumpInput()
    solar: SolarInput = SolarInput()
    tariff: TariffInput = TariffInput()
    battery: BatteryInput = BatteryInput()


# ── Response ──────────────────────────────────────────────────────────────────

class Range(BaseModel):
    low: float
    likely: float
    high: float


class OptionalRange(BaseModel):
    """None means 'not within the battery's life'."""
    low: Optional[float]
    likely: Optional[float]
    high: Optional[float]


class SolarSummary(BaseModel):
    status: LoadStatus
    kwp: float
    orientation: Orientation
    annual_generation_kwh: float = Field(description="Typical yearly generation for this size and direction.")
    modelled: bool = Field(
        description="True when generation was taken off the usage. False on the upload route with "
                    "panels already fitted: the meter readings already include them.")
    used_at_home_kwh: Optional[float] = Field(description="Solar used as it's made, no battery. None when not modelled.")
    spare_kwh: Optional[float] = Field(description="Solar left over with no battery, exported or stored. None when not modelled.")


class UsageSummary(BaseModel):
    route: Literal["estimate", "upload"]
    annual_kwh: float = Field(description="Modelled year, including any planned EV or heat pump.")
    days_modelled: int
    days_found: Optional[int] = Field(description="Days with real readings (upload route).")
    confidence: Confidence
    coverage: Optional[dict] = Field(description="Upload route: dates found, gaps filled, days scaled.")
    extra_loads: Optional[dict]
    unit_rate_p: float = Field(description="Current unit rate used, pence per kWh.")
    solar: Optional[SolarSummary] = Field(None, description="None when there are no solar panels.")


class Recommendation(BaseModel):
    battery_kwh: float
    battery_label: str
    tariff_key: str
    tariff_name: str
    installed_price: float
    chosen_by: Literal["best_value", "you"]


class Headline(BaseModel):
    installed_cost: Range
    year1_battery_saving: float = Field(description="£ in year 1, beyond the best tariff without a battery.")
    average_yearly_saving: Range = Field(description="£ a year averaged over the battery's life, per case.")
    payback_years: OptionalRange
    lifetime_net_gain: Range


class BreakEven(BaseModel):
    years: list[int]
    optimistic: list[float]
    likely: list[float]
    pessimistic: list[float]


class SavingBreakdown(BaseModel):
    time_shifting: float
    solar_storage: float
    other: float
    total: float


class TariffOption(BaseModel):
    key: str
    name: str
    annual_cost: float


class TariffRow(BaseModel):
    key: str
    name: str
    annual_cost_no_battery: float
    annual_cost_with_battery: float


class TariffCheck(BaseModel):
    current: dict
    best_no_battery: TariffOption
    best_with_battery: TariffOption
    savings: dict[str, float]
    battery_adds: float
    switch_share_of_best: Optional[float]
    switch_first: bool
    by_tariff: list[TariffRow]


class FairPrice(BaseModel):
    kwh: float
    low: float
    typical: float
    high: float
    as_of: str
    your_price: Optional[float] = None
    your_price_is: Optional[Literal["below_range", "within_range", "above_range"]] = None


class SizeRow(BaseModel):
    kwh: float
    label: str
    installed_cost: float
    tariff_key: str
    tariff_name: str
    year1_battery_saving: float
    payback_years: Optional[float]
    lifetime_net_gain: float
    verdict: Verdict


class BestSize(SizeRow):
    fair_price: FairPrice


class SizeComparison(BaseModel):
    best_value: BestSize
    smaller: Optional[SizeRow]
    larger: Optional[SizeRow]
    biggest_saving_kwh: float
    all_sizes: list[SizeRow]


class PriceLever(BaseModel):
    current_price: float
    price_for_payback_within_warranty: Optional[float]
    price_for_worth_it: Optional[float]


class VerdictChange(BaseModel):
    year1_battery_saving: float
    payback_years: Optional[float]
    verdict: Verdict
    changes_verdict: bool
    tariff_key: str
    tariff_name: str
    annual_miles: Optional[float] = None


class Levers(BaseModel):
    price: PriceLever
    switch_tariff: Optional[VerdictChange]
    add_ev: Optional[VerdictChange]


class DayFlows(BaseModel):
    label: str
    load: list[float]
    grid_to_battery: list[float]
    from_battery: list[float]
    grid_to_home: list[float]
    battery_level: list[float]
    solar_generation: Optional[list[float]] = Field(None, description="Only when solar is modelled.")
    solar_to_battery: Optional[list[float]] = None
    exported: Optional[list[float]] = Field(None, description="Spare solar sent to the grid.")


class DayInLife(BaseModel):
    summer: Optional[DayFlows]
    winter: Optional[DayFlows]
    average: DayFlows


class ContextCost(BaseModel):
    label: str
    low: float
    typical: float
    high: float
    grant: Optional[float] = None
    grant_name: Optional[str] = None
    after_grant: Optional[dict[str, float]] = None


class Assumptions(BaseModel):
    battery_life_years: int
    warranty_years: int
    capacity_loss_pct_per_year: float
    price_growth_pct: dict[str, float]
    inverter_replacement_year: Optional[int]
    inverter_replacement_cost: float
    verdict_thresholds: dict[str, float]
    costs_as_of: str
    tariffs_checked: str


class AssessResponse(BaseModel):
    schema_version: Literal["2.0"] = SCHEMA_VERSION
    usage: UsageSummary
    recommendation: Recommendation
    verdict: Verdict
    headline: Headline
    break_even: BreakEven
    saving_breakdown: SavingBreakdown
    tariff_check: TariffCheck
    size_comparison: SizeComparison
    what_would_make_it_pay_back: Optional[Levers]
    day_in_life: DayInLife
    fair_price: FairPrice
    context_costs: dict[str, ContextCost]
    assumptions: Assumptions


# ── Usage check (POST /api/v2/usage/check) ────────────────────────────────────

class FileCheck(BaseModel):
    name: str
    ok: bool
    error: Optional[str] = Field(None, description="Plain-English reason the file couldn't be used.")
    days_found: Optional[int] = None
    first_date: Optional[str] = None
    last_date: Optional[str] = None


class UsageCoverage(BaseModel):
    has_dates: bool
    first_date: Optional[str]
    last_date: Optional[str]
    days_found: int
    complete_days: Optional[int]
    partial_days_filled: Optional[int]
    missing_days_filled: Optional[int]
    half_hours_filled: Optional[int]
    days_scaled_from_estimate: Optional[int]
    days_dropped_older_than_a_year: Optional[int]
    confidence: Confidence
    annual_kwh_estimate: float
    inferred_unit_rate_p: Optional[float] = Field(description="From a cost column, if the file has one.")


class UsageCheckResponse(BaseModel):
    schema_version: Literal["2.0"] = SCHEMA_VERSION
    files: list[FileCheck]
    combined: Optional[UsageCoverage] = Field(description="None when no file could be used.")
