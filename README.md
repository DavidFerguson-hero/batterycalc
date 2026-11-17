# BatterySizer

**[batterysizer.co.uk](https://www.batterysizer.co.uk)** helps UK homeowners decide whether a home battery makes financial sense, and when it would pay for itself. It answers in plain English, in £ and years:

- **a verdict:** worth it, borderline, or not yet
- **the best-value battery size and tariff**, with a payback range rather than a single figure
- **where the saving comes from**, and whether switching tariff alone gets you most of it
- **what would make it pay back**, such as a lower fitted price

It works from a quick estimate, or from the homeowner's own half-hourly smart meter data, which is used in memory and never stored. Solar panels, heat pumps and electric cars are included where they change the battery case.

The method is explained for homeowners at [/how-we-calculate](https://www.batterysizer.co.uk/how-we-calculate).

## How it fits together

```
frontend/  Next.js 16 + React 19 + Tailwind 4, hosted on Vercel
  app/check/…            the homeowner journey: home → usage → confirm → results
  app/how-we-calculate, privacy, legal, contact, tariff-updates
  app/calculator-classic the old calculator (public/calculator.html), until 16 Dec 2026
        │  JSON over HTTPS (NEXT_PUBLIC_API_URL)
        ▼
api/       FastAPI on Python 3.12, hosted on Render (Docker)
  routers/assess.py      POST /api/v2/assess: the whole answer in one call
  routers/summary.py     POST /api/v2/summary: the AI-written "In a nutshell" (Claude Haiku)
  routers/epc.py         GET /api/epc/lookup: home details by postcode (EPC register)
  engine/                simulation and finance: usage profiles, half-hourly battery
                         simulation, tariffs, sizes, lifetime money, verdict
  data/costs.json        installed prices (the only place to change them)

scripts/check_tariffs.py  nightly check of tariff rates against live sources
```

More detail:
- **API reference:** [docs/api-v2.md](docs/api-v2.md), with the schema in [docs/api-v2.schema.json](docs/api-v2.schema.json)
- **Development plan:** [docs/dev-plan-homeowner-v2.md](docs/dev-plan-homeowner-v2.md)
- **Accuracy check:** [docs/accuracy-check.md](docs/accuracy-check.md)

## Run it locally

You need **Python 3.12** and **Node 22**.

**API** (http://localhost:8000, interactive docs at `/docs`):

```bash
cd api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend** (http://localhost:3000), in a second terminal:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Or run both with Docker: `docker compose up`.

**Optional settings** for the API, from your shell or Render:

| Variable | What it switches on |
|---|---|
| `ANTHROPIC_API_KEY` | The AI summary on the results page. Without it, the summary is simply hidden. |
| `EPC_API_TOKEN` | Postcode lookup on the EPC (Energy Performance Certificate) register. A bearer token from [get-energy-performance-data.communities.gov.uk](https://get-energy-performance-data.communities.gov.uk). Without it, people type their home's details instead. |
| `CORS_EXTRA_ORIGINS` | Extra website addresses allowed to call the API, comma-separated (for example a Vercel preview). |

## Tests

```bash
cd api && pip install -r requirements-dev.txt && pytest               # API and engine
cd scripts && pip install -r requirements-dev.txt && pytest           # tariff checker
cd frontend && npm test                                               # unit tests
cd frontend && npx tsc --noEmit && npm run lint                       # types and lint
cd frontend && npx playwright install chromium && npm run test:a11y   # accessibility, phone and desktop
```

`test:a11y` starts its own server on port 3100 and stubs the API, so it doesn't need the API running. It checks every page for WCAG 2.1 AA problems (Web Content Accessibility Guidelines), sideways scrolling and visible keyboard focus.

If you change the API's models, regenerate the types the frontend uses (CI checks they match):

```bash
cd api && python scripts/export_v2_schema.py
cd frontend && npm run gen:api-types
```

## Deploy

Both sides deploy themselves from **`main`**. Work happens on a branch and reaches `main` only through a reviewed pull request.

- **API → Render.** [`render.yaml`](render.yaml) is a Render Blueprint: a Docker web service on the free plan in Frankfurt, with health check `/health`. It deploys about a minute after a merge to `main`. Set `ANTHROPIC_API_KEY` and `EPC_API_TOKEN` in the Render dashboard.
- **Frontend → Vercel.** The Vercel project's root directory is `frontend/`, and `NEXT_PUBLIC_API_URL` is set to the Render API address. Every pull request gets a preview deployment, and `main` goes to batterysizer.co.uk. Web Analytics is switched on in the Vercel project settings.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the API tests, the tariff checker tests, and the frontend checks (API types, unit tests, lint, build, accessibility) on every pull request.
- **Uptime** ([`.github/workflows/uptime.yml`](.github/workflows/uptime.yml)):
  - Every 10 minutes it checks the API's `/health`, a real estimate, and the website.
  - If something fails, it opens one GitHub issue labelled `uptime`, which GitHub emails to the repo's watchers. It closes the issue when everything works again.
  - It also keeps the free Render service from going to sleep.

## How the tariff check works

The rates the calculator uses live in [`api/engine/tariffs.py`](api/engine/tariffs.py). Nothing changes them automatically.

1. **Every night at 02:00 UTC,** [`.github/workflows/update-tariffs.yml`](.github/workflows/update-tariffs.yml) runs [`scripts/check_tariffs.py`](scripts/check_tariffs.py).
2. **The script compares** the rates we use (the `CURRENT` table at the top of the script, kept in step with `tariffs.py`) with live sources:
   - **Octopus Go, Intelligent Octopus Go and Cosy:** Octopus's public API
   - **Standard variable rates:** the Ofgem price cap page
   - **Other suppliers** (Economy 7, E.ON Next Drive, EDF and Scottish Power): no reliable public feed, so they're flagged for a person to check
3. **Each tariff gets a status:** `ok`, `changed` (with the old and new rates), `manual` or `error`. The run is added to [`frontend/public/tariff-logs.json`](frontend/public/tariff-logs.json), which keeps the last 90 runs. The bot commits that file to `main`, with `[skip ci]`.
4. **[/tariff-updates](https://www.batterysizer.co.uk/tariff-updates)** shows the latest runs.

**When a rate has changed,** update it by hand in a pull request:
- change `api/engine/tariffs.py` and the `CURRENT` table in `scripts/check_tariffs.py` together
- show the before and after rates in the pull request description
- run the API tests

Installed battery prices are handled the same way, in [`api/data/costs.json`](api/data/costs.json), which has a source listed for each figure.

## Privacy

- Uploaded smart meter data is read in memory to work out the answer, then discarded. It's never saved or logged.
- The homeowner's answers live in the page address, so share links work. Analytics strips them out before anything is sent.
- The AI summary sees only the headline figures, never meter data or postcodes.
- Full details: [/privacy](https://www.batterysizer.co.uk/privacy).

## Data and credits

- **Typical household use:** the Low Carbon London smart meter trial (UK Power Networks), via [4TU.ResearchData](https://data.4tu.nl/datasets/fbbe775b-48d8-469f-a39b-b64488bfd6fd), CC BY 4.0.
- **Home details:** the EPC register (Ministry of Housing, Communities and Local Government).
- **Battery prices:** the sources listed in `api/data/costs.json`.
