# Emme

<p align="left">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/Postgres-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img alt="Gemini" src="https://img.shields.io/badge/Gemini_API-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white" />
  <img alt="Vercel" src="https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white" />
  <img alt="Render" src="https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" />
</p>

**Health insurance, finally in plain English**

Emme turns a health plan's fine print into a dashboard a member can actually read.
Upload a Summary of Benefits and Coverage or an Explanation of Benefits and Emme reads
it for you, or answer a few plain-language questions instead, both paths are always
available side by side. Uncertain extractions are confirmed one at a time before they
count; anything not found falls back to manual entry with a "where to find this"
explainer. A dashboard shows exactly where a member stands on their deductible and
out-of-pocket max, a compare view shows the plan against alternatives, and "Ask Emme"
answers questions using the member's own real numbers, never a recommendation on which
plan to buy.

**Live:** [frontend-lilac-one-63.vercel.app/compare.html](https://frontend-lilac-one-63.vercel.app/compare.html)
**Built for:** The Open Accelerator Healthcare Hackathon, 2026-07-25, Red Hat Fort Point, Boston (Track 2)

---

## Snapshot

- Real accounts (signup/login, hashed passwords), not a demo login
- Dual-path onboarding: document upload with AI extraction, or manual entry, always both
- Confidence-driven confirm flow: verified fields go straight to the dashboard, uncertain
  ones get a one-at-a-time "does this look right?" card with the source document cited
- Dashboard with live deductible/out-of-pocket meters and per-visit cost breakdown
- Plan-vs-alternatives compare view with a spend slider
- "Ask Emme" chat, aware of the member's actual extracted plan data
- Embedded "how it works" video walkthrough of the real live app, recorded end to end
- Full architecture writeup in [`ARCHITECTURE.md`](./ARCHITECTURE.md), written for
  presentation Q&A: why each tool was chosen, what was actually tested (not assumed),
  and the real bugs found and fixed during the build

---

## Built With

<p align="left">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white" />
  <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=python&logoColor=white" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/Postgres_(Neon)-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
  <img alt="Gemini" src="https://img.shields.io/badge/Gemini_API-8E75B2?style=flat-square&logo=googlegemini&logoColor=white" />
  <img alt="Vercel" src="https://img.shields.io/badge/Vercel-000000?style=flat-square&logo=vercel&logoColor=white" />
  <img alt="Render" src="https://img.shields.io/badge/Render-46E3B7?style=flat-square&logo=render&logoColor=white" />
</p>

---

## What It Does

### For members
- Sign up or sign in with a real account, plan data persists across sessions/devices
- Upload an SBC or EOB (PDF/image) and have Gemini read out deductible, copays, premium,
  HSA, and more, or skip straight to manual entry
- Confirm anything the AI wasn't fully sure about, one plain-language card at a time,
  with the source document cited
- See a live dashboard: deductible remaining, out-of-pocket progress, per-visit costs
- Compare the plan against alternatives with a spend slider showing where each plan
  actually wins or loses
- Ask "Ask Emme" anything about the plan in plain English, answered with real numbers

### Behind the scenes
- Every extracted field is tagged `verified`, `needs_confirmation`, or `missing` and
  routed accordingly, never silently trusted
- Identity fields (name, email, zip) are never sent to the AI, by construction, not by
  filtering after the fact, tested adversarially against a prompt-injection attempt
- Manual entry and confirm-card edits are type-checked (money rounds to 2dp, text stays
  text) on both the frontend and the backend, so a stray input can't corrupt stored data

---

## App Map

```text
emme-onboarding/
  server.py                Flask app: auth, session lifecycle, autosave, upload,
                            chat, and the frontend-contract routes
  app/
    schema.py               IntakeData Pydantic model (extraction's output shape)
    extraction.py            Gemini vision call + prompt (primary path)
    extraction_local_ollama.py  Local-only path tried and rejected, kept for reference
    chatbot.py               answer_question / answer_chat ("Ask Emme")
    adapter.py               IntakeData (snake_case) -> session storage (camelCase)
    plan_view.py             session storage <-> frontend's plan.json (flat, typed)
  frontend/
    compare.html             Primary deployed app: login/signup, onboarding,
                             dashboard, compare, chat, landing page, video
    index.html               Earlier onboarding-only prototype, kept for reference
    how-it-works.mp4          Recorded demo video, embedded in compare.html
    BACKEND_CONTRACT.md       The plan.json contract compare.html expects
  ARCHITECTURE.md            Full technical writeup + anticipated Q&A
  requirements.txt
```

---

## Project Details

- Backend: Flask + SQLAlchemy, deployed on Render (a real persistent process, not
  serverless — needed for Postgres session state to survive between requests)
- Database: Postgres on Neon
- AI: Google Gemini API for document extraction (vision) and the "Ask Emme" chat
- Frontend: a single dependency-free HTML file, no framework, no build step, deployed
  as a static site on Vercel
- Auth: real accounts, `werkzeug` password hashing, Flask session cookie

---

## Data Model

One `Session` row per member, holding the whole plan as a nested JSON blob (identity,
household, planDetails, costSharing, hsa, prescriptions, upcomingCare), autosaved via a
recursive merge on every field change rather than requiring the client to resend the
whole object. A `Session` can belong to a logged-in `User` (real accounts) or be tracked
anonymously by a signed cookie, both paths share the same session-resolution logic. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md#4-data-model--session-identity) for the full model
and why a JSON blob was chosen over per-field columns.

---

## Getting Started

### Prerequisites
- Python 3.10+
- A Gemini API key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey))
- A Postgres connection string (optional, defaults to local SQLite for dev)

### Install & Run

```bash
git clone https://github.com/FERBIN12/emme-onboarding
cd emme-onboarding
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export GEMINI_API_KEY=...          # required
export DATABASE_URL=...             # optional, defaults to sqlite:///intake.db

python server.py                    # -> http://localhost:3000
```

Open `frontend/compare.html` directly in a browser, or point its `API.base` constant at
your local server to run against it instead of the deployed backend.

---

## Roadmap

### Shipped for the hackathon
- [x] Dual-path onboarding (upload + manual), both always available
- [x] Real Gemini extraction, validated against real sample documents
- [x] Confidence-tagged confirm flow with source attribution
- [x] Real user accounts with persistent, per-user plan data
- [x] Dashboard, compare view, and plan-aware "Ask Emme" chat
- [x] Landing page + embedded how-it-works video

### Next
- [ ] Move off Gemini's free-tier quota (20 req/day/project) for real usage
- [ ] Unify the nested-storage / flat-`plan.json` dual representation (see
      `ARCHITECTURE.md` §4.3 and §8 for why this exists and the tradeoff)
- [ ] Route extraction through a BAA'd/HIPAA-compliant endpoint for real patient documents

---

## License

Built for The Open Accelerator Healthcare Hackathon, 2026. Not for production use as-is.
