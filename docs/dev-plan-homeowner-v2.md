# BatterySizer: Homeowner Journey v2, Development Plan

Owner: David Ferguson · Drafted: 15 Nov 2026 · Status: ready to start Phase 0

**Goal:** a homeowner gets an honest answer to "does a battery make sense for my home, and when does it pay back?" They can use either a year of half-hourly data or a quick EPC-based estimate. The answer is a verdict, a payback range and a clear break-even chart.

**Source of truth for requirements:** "BatterySizer: User Journeys & Experience Design" (https://claude.ai/artifact/E8j4WYhuhajNfsPN3jYzHs). Story IDs (H1–H24) below refer to that doc.

**In scope:** homeowner journey only.
**Out of scope:**
- the installer and supplier journey
- user accounts
- consented smart meter data access
- a quotes marketplace (H23)
- save-and-return (H24)
- flexibility income

---

## How Claude Code should work on this

- Work on branch `feature/homeowner-v2`. Open one small pull request per task (IDs below). Never push straight to `main`.
- Run the API tests (`cd api && pytest`) and the frontend build (`cd frontend && npm run build`) before every commit.
- Tick the task's checkbox in this file in the same pull request that completes it.
- Never change rates in `api/engine/tariffs.py` without showing the before/after in the pull request description.
- Never store uploaded usage files on disk or in logs. Process them in memory only.
- UI copy rules:
  - plain English
  - explain every acronym the first time it appears (EPC = Energy Performance Certificate)
  - money in £ and time in years; no IRR or NPV on homeowner screens
- If a task needs a decision marked **[DECISION]**, stop and ask David rather than guessing.

---

## Decisions needed from David before or during the work

| # | Decision | Recommendation | Needed by |
| --- | --- | --- | --- |
| D1 | Where to host the API (Railway reports "Application not found") | **Decided 15 Nov 2026: Render free tier** (Railway free plan no longer available). Blueprint in `render.yaml`. URL comes from `NEXT_PUBLIC_API_URL` | Task 0.1 |
| D2 | Rebuild the homeowner journey as Next.js pages, or keep extending `public/calculator.html` (3,000 lines, loaded in an iframe) | **Decided 16 Nov 2026: rebuild in Next.js under `/check`.** Keep the old calculator live until the new one matches it, then redirect | Phase 2 |
| D3 | Verdict thresholds | **Decided 15 Nov 2026: as recommended.** Green "Worth it" if likely payback ≤ 70% of warranty years. Amber "Borderline" if ≤ 100%. Grey "Not yet" otherwise | Task 1.3 |
| D4 | Cost figures (battery, inverter, install, VAT; solar, heat pump, EV charger for context) and their sources | **Decided 16 Nov 2026: researched figures approved.** Held in `api/data/costs.json` with a source and date for each | Task 1.8 |
| D5 | Default assumptions | **Decided 15 Nov 2026: as recommended.** Energy price growth 3% a year (central; 1% low, 5% high). Battery capacity loss 2% a year. Battery life 15 years. Warranty 10 years. Inverter replacement at year 10 | Task 1.3 |

---

## Phase 0: Stabilise (about 1–2 days)

- [x] **0.1 Restore the API.** **[DECISION D1]** Re-deploy `api/` and confirm `GET /health` returns `{"status":"ok"}`. Replace the hard-coded `API_BASE` in `frontend/public/calculator.html` (line ~1193) with a value injected at build time, or with `NEXT_PUBLIC_API_URL`. Add the new host to the CORS (cross-origin) list in `api/main.py`.
  - *Done when:* the live site at /calculator produces results end to end.
- [x] **0.2 Real test runner.** `api/tests/test_simulator.py` is a script, so pytest collects 0 tests. Convert its 60 checks into pytest test functions, keeping the same cases. Add `pytest` to `api/requirements-dev.txt`.
  - *Done when:* `pytest` reports 60 passed.
- [x] **0.3 Continuous integration (CI).** Add `.github/workflows/ci.yml` to run the API tests and the frontend lint and build on every pull request.
- [x] **0.4 Update tariff rates.** Apply the changes flagged in the latest run in `frontend/public/tariff-logs.json` to `api/engine/tariffs.py` and to the `CURRENT` copy in `scripts/check_tariffs.py`. Show the diff for David to approve.
- [x] **0.5 Fix the tariff checker.** It reports Intelligent Octopus Go day and night both as 24.27p, which is almost certainly a parsing error. Fix it and add a test using a saved sample response.
- [x] **0.6 Dependency check.** Pin compatible versions (pip reports a starlette/sse-starlette conflict). Remove the unused Postgres/Redis services from `docker-compose.yml`, or comment them as future use.

---

## Phase 1: Engine upgrades for an honest business case

All new engine code lives in `api/engine/` with pytest tests. Existing endpoints keep working until Phase 2 switches over.

- [x] **1.1 Full-year modelling.** (H2, H3, H4, H19)
  - CSV route: accept up to 12 months of half-hourly data and simulate every day.
    - Report coverage (days found, gaps filled) back to the user.
    - If less than a year is uploaded, scale by month using the estimate shapes and lower the confidence label.
  - Estimate route: replace the "35 identical days" in `profile_estimator.generate_days` with 365 days. Use monthly seasonal scaling (more in winter) and adjust for heating type from the EPC.
  - *Done when:* the sum of 365 estimated days equals the annual kWh within 1%, and December use is greater than June use for a typical house.
- [x] **1.2 Extra loads: EV and heat pump.** (H1, H6, H18, H19)
  - EV: annual miles → kWh (default 0.3 kWh per mile), charged in a chosen window (overnight cheap slot by default).
  - Heat pump: annual heat demand from the EPC (or floor area) ÷ efficiency (default 3.0), spread with a winter-heavy monthly shape and a morning/evening daily shape.
  - Both can be "already have" (already in the CSV data, so don't add again) or "planning" (add to the data).
- [x] **1.3 Lifetime finance with ranges.** (H7, H9, H13) **[DECISIONS D3, D5]**
  - Replace `engine/payback.py` with a lifetime model covering:
    - battery capacity loss each year
    - inverter replacement cost in its replacement year
    - energy price growth with low/central/high cases
    - cost low/typical/high
  - Output:
    - a 15-year cumulative cash series for each case
    - payback years (low, likely, high)
    - lifetime net gain
    - verdict (`worth_it` | `borderline` | `not_yet`)
  - *Done when:* tests cover the never-pays-back case, the mid-life inverter dip and the verdict boundaries.
- [x] **1.4 Where the saving comes from.** (H10) Split the annual saving into:
  - (a) cheap-rate charging used at peak (time-shifting)
  - (b) solar stored instead of exported, net of lost export income
  - (c) other peak avoidance
  - *Done when:* the parts sum to the total saving within £1.
- [x] **1.5 Tariff check.** (H11, H18, H20) Always compute four cases:
  - current tariff without a battery (baseline)
  - best-fit tariff without a battery ("switch tariff only")
  - current tariff with a battery
  - best-fit tariff with a battery

  Flag when switching tariff alone captures 70% or more of the best saving.
- [x] **1.6 Size comparison.** (H8, H12) Sweep standard sizes and return the best-value size (highest lifetime net gain, not largest saving) plus its neighbours either side.
- [x] **1.7 "What would make it pay back".** (H14) When the verdict is `not_yet`, calculate:
  - the battery price at which payback equals the warranty period
  - whether a tariff switch or adding a planned EV changes the verdict
- [x] **1.8 Cost data file.** (H9, H21) **[DECISION D4]**
  - Move `OPT_BATTERIES` and `DEFAULT_COSTS` out of `tariffs.py` into `api/data/costs.json`, with low/typical/high, components (unit, inverter, install, VAT), source and as-of date.
  - Add context costs for solar, heat pump and EV charger.
  - The API returns a "fair price range" for the recommended size.
- [x] **1.9 One assessment endpoint.** `POST /api/v2/assess`: one request with all inputs, one response holding everything the results page needs (sections below).
  - Document the request/response schema in `docs/api-v2.md`.
  - Add a contract test that validates a sample response against the schema.
  - Keep `/api/epc/lookup` and `/api/solar` as they are.

---

## Phase 2: Homeowner front end (Next.js) [DECISION D2]

Build in `frontend/app/check/` with React components in `frontend/components/`. Inputs live in the URL query string, so any result can be shared or bookmarked without a database (H22). Add a charting library (Recharts suggested) and keep styling consistent with the current landing page.

- [x] **2.1 Foundations.** Shared layout, progress indicator, typed API client for `/api/v2/assess` in `frontend/lib/api.ts`, and a `Term` tooltip component for plain-English definitions (kWh, EPC, tariff, payback).
- [x] **2.2 Step: your home setup** `/check` (H1, H6). Pick what you have now and what you're planning: solar, heat pump, EV, existing battery, none.
- [x] **2.3 Step: choose a route** (H2). Two cards: "I have my usage data" and "Quick estimate (2 minutes)".
- [x] **2.4 Route A: upload** (H4).
  - Supplier-specific how-to panels (Octopus, British Gas, EDF, E.ON, OVO, other suppliers).
  - Drag-and-drop upload.
  - Validation showing date range, days found and gaps.
- [x] **2.5 Route B: estimate** (H3).
  - Postcode → list of EPC addresses → select, which pre-fills property type, floor area, heating and annual use.
  - Ask only for what the EPC can't give (people at home, EV miles).
- [x] **2.6 Step: confirm** (H5). Tariff picker (searchable list plus "enter my rates"), with an editable summary of everything the model will use.
- [x] **2.7 Results page** (H7–H22), in this order:
  1. VerdictCard
  2. HeadlineNumbers (cost range, yearly saving range, payback, lifetime gain)
  3. ConfidenceBadge with an "add real data" upgrade link
  4. BreakEvenChart (15-year cumulative cash, payback year marked, range shaded)
  5. SavingBreakdown
  6. SizeComparison
  7. TariffCheck
  8. WhatIfs (battery price, price growth, add EV, heat pump or solar; debounced live recalculation)
  9. DayInLife (summer and winter day)
  10. ContextPanel (solar, heat pump, EV charger costs, shown below and smaller)
  11. NextSteps (fair price range, installer question checklist, share)
  12. Assumptions (collapsed, with the tariff-checked date)
- [ ] **2.8 Share and download** (H22). "Copy link" button, plus a print stylesheet that produces a tidy one-page summary when saved as PDF.
- [ ] **2.9 Plain-English summary.** Optionally reuse `/api/explain` (Claude-written summary) beneath the verdict, clearly labelled as AI-generated.
- [ ] **2.10 Mobile and accessibility.**
  - Works at 375px wide.
  - Keyboard navigable.
  - Colour is never the only signal (the verdict has words too).
  - Meets WCAG (Web Content Accessibility Guidelines) 2.1 AA contrast.
- [ ] **2.11 Switch over.**
  - Landing page call-to-action → `/check`.
  - Once 2.1–2.8 are done and checked against the old calculator on 3 sample inputs, redirect `/calculator` → `/check`.
  - Keep the old page at `/calculator-classic` for one month.

---

## Phase 3: Quality and launch

- [ ] **3.1 Accuracy check.** Run 10 or more real households (David to source data) through both routes and compare estimated against actual payback. Use the result to set the confidence wording.
- [ ] **3.2 Missing pages.** "How we calculate", "Legal disclaimer", "Privacy" (uploaded data is not stored) and a contact route. The footer links currently all point to the calculator.
- [ ] **3.3 Monitoring.** Uptime check on `/health` with an email alert, plus privacy-friendly analytics on the funnel (landing → route chosen → result → share).
- [ ] **3.4 README.** Replace the default Next.js README with: what the project is, how to run the API and frontend locally, how to deploy, and how the tariff check works.

---

## Story coverage

| Story | Priority | Tasks |
| --- | --- | --- |
| H1 Setup | Must | 1.2, 2.2 |
| H2 Choose route | Must | 1.1, 2.3 |
| H3 EPC by postcode | Must | 1.1, 2.5 |
| H4 Data download help | Must | 1.1, 2.4 |
| H5 Current tariff | Must | 2.6 |
| H6 Planned tech | Should | 1.2, 2.2, 2.7 (what-ifs) |
| H7 Verdict + payback | Must | 1.3, 2.7 |
| H8 Best-value size | Must | 1.6, 2.7 |
| H9 Ranges | Must | 1.3, 1.8, 2.7 |
| H10 Where saving comes from | Must | 1.4, 2.7 |
| H11 Current vs best tariff | Must | 1.5, 2.7 |
| H12 Size comparison | Should | 1.6, 2.7 |
| H13 Wear and replacement | Should | 1.3 |
| H14 What would make it pay back | Should | 1.7, 2.7 |
| H15 Day in the life | Could | 2.7 (existing data) |
| H16 Carbon | Could | 2.7 (existing carbon engine) |
| H17 Existing solar | Must | 1.4, 2.7 |
| H18 EV tariff first | Must | 1.2, 1.5 |
| H19 Heat pump winter | Must | 1.1, 1.2 |
| H20 Standalone battery | Must | 1.5 |
| H21 Fair price + checklist | Must | 1.8, 2.7 |
| H22 Share summary | Must | 2.8 |
| H23 Get quotes | Could | Not in this plan |
| H24 Save and return | Could | Not in this plan (share link covers part of it) |
