# Emme

TOA Healthcare Hackathon 2026-07-25 — Track 2 (Emme).

Member-facing insurance onboarding: upload an SBC/EOB to auto-fill plan details, or
answer plain-language questions instead. Uncertain extractions are confirmed one at a
time; anything not found falls back to manual entry. A dashboard shows where you stand
on your deductible and out-of-pocket max, a compare view shows your plan against
alternatives, and "Ask Emme" answers questions using your own real plan numbers.

Live: https://frontend-lilac-one-63.vercel.app/compare.html

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full technical writeup (data model,
AI extraction pipeline, why each tool was chosen, bugs found and fixed, anticipated Q&A).

## Structure

- `server.py` — Flask backend: auth, session storage, autosave, document upload,
  chat, and the routes `compare.html` expects
- `app/` — extraction (Gemini vision), chatbot, schema, and the translation layer
  between internal session storage and the frontend's `plan.json` contract
- `frontend/compare.html` — the deployed app (login/signup, onboarding, dashboard,
  compare, chat, landing page, embedded how-it-works video)
- `frontend/index.html` — an earlier onboarding-only prototype, kept for reference
- `frontend/how-it-works.mp4` — recorded walkthrough of the real live app

## Stack

Flask + SQLAlchemy (Render) · Postgres (Neon) · Gemini API (extraction + chat) ·
static frontend, no framework (Vercel)

## Running locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=...          # aistudio.google.com/apikey
export DATABASE_URL=...             # optional, defaults to local sqlite:///intake.db
python server.py                    # -> http://localhost:3000
```

Open `frontend/compare.html` directly, or set `API.base` in it to your local server.

## Team

4-person team, Red Hat Fort Point, Boston.
