# BatterySizer API v2: `POST /api/v2/assess`

One request with everything about the home, one response with everything the results page needs.

- **Machine-readable contract:** [`api-v2.schema.json`](api-v2.schema.json) (JSON Schema for the request and response). It is generated from [`api/models/assess.py`](../api/models/assess.py) by `python api/scripts/export_v2_schema.py`; a test fails if the two drift apart.
- **Interactive docs:** `/docs` on the API (FastAPI's OpenAPI page).
- **Stateless:** nothing is stored between requests. Uploaded files are processed in memory and never written to disk or logs.
- **Unchanged:** `/api/epc/lookup` and `/api/solar` work as before. The classic calculator keeps using the v1 endpoints until Phase 2 switches over.

All money is **£** (pounds, not pence, unless a field name ends in `_p`). Energy is **kWh**. Time is **years** unless stated.

---

## Request

### Estimate route (JSON)

```http
POST /api/v2/assess
Content-Type: application/json
```

```json
{
  "usage":     { "route": "estimate", "annual_kwh": 3500, "property_type": "semi", "heating_type": "gas" },
  "ev":        { "status": "planning", "annual_miles": 10000 },
  "heat_pump": { "status": "none" },
  "solar":     { "status": "have", "kwp": 4 },
  "tariff":    { "unit_rate_p": 28.16, "standing_charge_p": 53.0, "export_rate_p": 15 },
  "battery":   {}
}
```

### Upload route (multipart)

```http
POST /api/v2/assess
Content-Type: multipart/form-data
```

| Part | Content |
|---|---|
| `inputs` | The same JSON as above, with `"usage": { "route": "upload" }` |
| `files` | One or more half-hourly CSV exports (repeat the part for several files) |

### Fields

Only `usage.route` is required (plus `usage.annual_kwh` on the estimate route). Unknown fields are rejected.

| Field | Default | Meaning |
|---|---|---|
| `usage.route` | — | `"estimate"` or `"upload"` |
| `usage.annual_kwh` | — | Annual electricity use, 500–20,000 kWh (estimate route) |
| `usage.property_type` | `"semi"` | `flat`, `terraced`, `semi`, `detached` |
| `usage.heating_type` | `"gas"` | `"electric"` when the EPC (Energy Performance Certificate) shows no mains gas; makes winter use higher |
| `ev.status` | `"none"` | `none`, `have` (already in the figures), `planning` (add it) |
| `ev.annual_miles` / `kwh_per_mile` | 7,000 / 0.3 | Electric car use |
| `ev.charge_start` / `charge_end` | `"00:30"` / `"04:30"` | Charging window, on the hour or half hour |
| `heat_pump.status` | `"none"` | As for `ev.status` |
| `heat_pump.heat_demand_kwh` | — | Annual heat demand; else `floor_area_m2` × the rate for `epc_rating` |
| `heat_pump.efficiency` | 3.0 | kWh of heat per kWh of electricity |
| `solar.status` | `"none"` | `none`, `have` (panels fitted), `planning` (panels to add). See [Solar](#solar) |
| `solar.kwp` | 4 | Panel size in kWp (kilowatts peak), 0.5–20 |
| `solar.orientation` | `"south"` | `south`, `south_east`, `south_west`, `east`, `west` |
| `tariff.current_tariff_key` | — | If already on a time-of-use tariff (a key from `GET /api/tariffs`); else a flat rate |
| `tariff.unit_rate_p` | from CSV, else 28.16 | Current unit rate, pence per kWh |
| `tariff.standing_charge_p` | 53.0 | Pence per day |
| `tariff.export_rate_p` | 0 | Pence per kWh for electricity sold back: spare solar and stored energy |
| `battery.size_kwh` | — | Leave empty to get the **best-value** size |
| `battery.price_gbp` | typical for the size | Installed price |
| `battery.tariff_key` | best for the battery | Tariff to pair it with |
| `battery.max_charge_rate_kw` / `efficiency_pct` | 3.6 / 90 | Battery performance |

### Errors

| Status | When |
|---|---|
| 422 | A field is missing, out of range, unknown, or a CSV can't be read. `detail` says which. |
| 400 | An unknown tariff key |

---

## Response

The sections appear in the order the results page shows them.

| Field | What it holds | Results page |
|---|---|---|
| `schema_version` | `"2.0"` | — |
| `usage` | Modelled annual kWh, days modelled, days found, `confidence` (`high`/`medium`/`low`/`estimate`), CSV `coverage`, EV/heat pump `extra_loads`, unit rate used, `solar` (size, typical generation, whether it was modelled, kWh used at home and spare with no battery; `null` without panels). `annual_kwh` is the home's use before solar | ConfidenceBadge |
| `recommendation` | Battery size, tariff, installed price; `chosen_by` is `best_value` or `you` | — |
| `verdict` | `worth_it` (likely payback ≤ 70% of the warranty), `borderline` (≤ 100%), `not_yet` | VerdictCard |
| `headline` | Installed cost range, year-1 battery saving, average yearly saving range, payback range, lifetime net gain range | HeadlineNumbers |
| `break_even` | `years` 0–15 and the cumulative £ for `optimistic`, `likely`, `pessimistic` | BreakEvenChart |
| `saving_breakdown` | `time_shifting`, `solar_storage` (spare solar stored and used at home, less the export income given up), `other` (stored energy sold back), `total` | SavingBreakdown |
| `size_comparison` | `best_value` (with its `fair_price`), `smaller`, `larger`, `biggest_saving_kwh`, `all_sizes` | SizeComparison |
| `tariff_check` | Current and best tariffs with and without a battery, `savings`, `battery_adds`, `switch_first`, `by_tariff` | TariffCheck |
| `what_would_make_it_pay_back` | Only when `not_yet`: `price`, `switch_tariff`, `add_ev` levers | WhatIfs |
| `day_in_life` | Half-hourly `load`, `grid_to_battery`, `from_battery`, `grid_to_home`, `battery_level` for an `average` day, plus `summer` and `winter` when dates are known. With solar modelled, also `solar_generation`, `solar_to_battery` and `exported` (otherwise `null`) | DayInLife |
| `context_costs` | Solar, heat pump (with grant) and EV charger price ranges | ContextPanel |
| `fair_price` | Low/typical/high for the size, and where the given price sits | NextSteps |
| `assumptions` | Battery life, warranty, wear, price growth, inverter replacement, verdict thresholds, `costs_as_of`, `tariffs_checked` | Assumptions |

### How the key numbers are worked out

- **Battery saving** is what the battery saves **beyond the best tariff the home could switch to without one** (tariff check case B minus the chosen tariff with the battery). Money from switching tariff alone is not credited to the battery.
- **Ranges** come from three cases: optimistic (low price, 5% a year energy price growth), likely (typical price, 3%), pessimistic (high price, 1%). Each year's saving allows for 2% a year capacity loss, and the inverter is replaced in year 10.
- **Payback** is when the cumulative cash stays above zero for good; `null` means not within the battery's 15-year life.
- **Solar** (see below) is taken off the usage before any of this, so every tariff, size and lever is worked out with the panels in place.
- **Best value** is the size with the highest likely lifetime net gain, which is often not the size with the biggest saving.

### Solar

- **Generation** is about 850 kWh per kWp a year, split by a typical UK monthly yield (December ≈ 20, June ≈ 115 kWh per kWp) and spread over each day between sunrise and sunset for the month. East or west roofs make 82% of a south roof and peak 1½ hours earlier or later; south-east and south-west make 95%. There's no network call and no postcode: the v1 PVGIS fetcher (`engine/solar_fetcher.py`) is not used.
- **Which usage is changed:** the generation is subtracted half-hour by half-hour on the estimate route (`have` or `planning`) and for `planning` on the upload route. For `have` on the upload route the meter readings already have the solar taken off, so they are used as they are and `usage.solar.modelled` is `false`. (Import readings don't show the spare solar that went to the grid, so the battery's solar saving isn't counted there.)
- **Spare solar** first charges the battery; what doesn't fit is exported at `tariff.export_rate_p`. On days with spare solar, cheap-rate grid charging stops short of full to leave room. Stored solar can be used in any half-hour that isn't a cheap charging slot, including on a flat rate.
- **Limits:** every day in a month is that month's average day, so bright and dull days aren't told apart. The model knows the day's generation in advance, as a forecast-driven battery would.

### Example (abridged)

Estimate route, 3,500 kWh a year, semi-detached, no battery specified:

```json
{
  "schema_version": "2.0",
  "recommendation": { "battery_kwh": 10.0, "tariff_key": "edfFreePhaseDynamic",
                      "installed_price": 6500.0, "chosen_by": "best_value" },
  "verdict": "not_yet",
  "headline": {
    "installed_cost": { "low": 4500.0, "likely": 6500.0, "high": 8900.0 },
    "year1_battery_saving": 706.7,
    "payback_years": { "low": 5.9, "likely": 10.4, "high": null },
    "lifetime_net_gain": { "low": -224.0, "likely": 3627.0, "high": 7348.0 }
  },
  "what_would_make_it_pay_back": {
    "price": { "current_price": 6500.0, "price_for_payback_within_warranty": 6173.0, "price_for_worth_it": 5088.0 }
  }
}
```

---

## `POST /api/v2/usage/check`

Reads uploaded usage files and says what was found, **without** running the assessment, so the upload step can show "We found 342 days from …" in a second or two. In memory only; nothing is stored.

```http
POST /api/v2/usage/check
Content-Type: multipart/form-data
```

Send one or more CSV files as `files` parts (up to 20 files, 10 MB each).

**Response** (`usage_check_response` in [`api-v2.schema.json`](api-v2.schema.json)):

| Field | What it holds |
|---|---|
| `files[]` | Per file: `name`, `ok`, and either `days_found`, `first_date`, `last_date`, or a plain-English `error` |
| `combined` | All good files together: `first_date`, `last_date`, `days_found`, days and half-hours filled, days scaled from the seasonal shape, days dropped (older than a year), `confidence`, `annual_kwh_estimate`, and `inferred_unit_rate_p` if a file had a cost column. `null` when no file could be used. |

One unreadable file doesn't stop the others: it gets `ok: false` with a reason.

### Which CSV layouts are understood

Column names are matched by what they contain, so exports from Octopus, OVO, the Bright app (Glowmarkt), n3rgy and most others work:

- **Usage:** a column whose name contains `kWh`, `consumption`, `usage` or `import`, but not `export`, `generation`, `cost`, `price`, `rate`, `cumulative` or `register`.
- **Time:** a start/timestamp column, an end column (read as the end of the half-hour), or separate date and time columns. Times with an offset or `Z` are honoured; a column whose name says `UTC` is read as UTC; otherwise times are UK clock time.
- **Interval:** half-hourly readings are used as they are; **hourly readings are split evenly into two half-hours**; daily (or coarser) readings are rejected with a message asking for half-hourly data.
