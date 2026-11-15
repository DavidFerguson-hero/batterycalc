# BatterySizer (batterysizer.co.uk)

Helps UK homeowners decide whether a home battery makes financial sense, and when it pays back. Batteries are the focus; solar, heat pumps and EVs appear only as context that changes the battery case.

## Current plan
Follow `docs/dev-plan-homeowner-v2.md`. Work through the tasks in order and tick checkboxes as you finish them. Stop and ask David at anything marked [DECISION].

## Layout
- `api/` — FastAPI (Python 3.12, same as `api/Dockerfile` and CI). Simulation and finance engine in `api/engine/`, HTTP endpoints in `api/routers/`.
- `frontend/` — Next.js 16 + Tailwind. Landing page in `app/page.tsx`. The current calculator is the plain HTML/JS file `public/calculator.html`, loaded in an iframe by `app/calculator/page.tsx`.
- `scripts/check_tariffs.py` — nightly GitHub Action that compares live tariff rates with `api/engine/tariffs.py` and logs to `frontend/public/tariff-logs.json`. It never edits tariffs itself.

## Run locally
- API: `cd api && pip install -r requirements.txt && uvicorn main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`
- Tests: `cd api && pip install -r requirements-dev.txt && pytest` and `cd scripts && pip install -r requirements-dev.txt && pytest`

## Rules
- Branch `feature/homeowner-v2`, one small pull request per task, never push to `main`.
- Never store or log uploaded usage data.
- Never change tariff rates without showing the before/after diff.
- UI copy: plain English, explain acronyms on first use, £ and years.
