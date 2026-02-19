# NovaFlow Ops

NovaFlow Ops turns natural-language tasks into **verifiable browser actions**.  
It plans a short sequence of steps (RAG + planner), executes UI steps with Playwright, and stores **auditable logs + evidence screenshots**.

## Why this exists

Hackathon demos die for two reasons:

1) “It worked on my machine.”
2) “Trust me, it clicked the thing.”

NovaFlow Ops fixes #2 by producing **evidence** (screenshots + logs), and fixes #1 by supporting a **No-AWS Mock Mode** that runs without credentials.

---

## ✅ 1-Minute Demo (Jury Friendly)

### 0) Prerequisites

- Docker + Docker Compose
- Node.js (recommended: 18+)
- Python (recommended: 3.11+)

---

## 🚀 Option A: No AWS Needed (Mock Mode) [Recommended for Judges]

This mode runs fully offline from AWS: deterministic planner + local embeddings.

### 1) Start Postgres

```bash
docker compose up -d
2) Backend (API)
From repo root:

Windows (PowerShell)

python -m venv .venv
.\.venv\Scripts\activate
pip install -r services/api/requirements.txt
$env:NOVA_PROVIDER="mock"
python -m uvicorn services.api.app.main:app --reload --port 8000
macOS/Linux

python -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
export NOVA_PROVIDER=mock
uvicorn services.api.app.main:app --reload --port 8000
3) Frontend (Web UI)
cd apps/web
npm install
npm run dev
Open:

Web UI: http://localhost:3000

API Docs: http://localhost:8000/docs

Health: http://localhost:8000/health

4) Run a demo task
In the Web UI, paste:

Go to "Form Authentication", log in with username "tomsmith" and password "SuperSecretPassword!", then take a screenshot after login.

Click Run.

Then execute steps (optional via API):

PowerShell

$runId = <RUN_ID>
1..6 | % { Invoke-RestMethod -Method Post "http://localhost:8000/runs/$runId/execute-next-ui-step" }
Invoke-RestMethod "http://localhost:8000/runs/$runId" | ConvertTo-Json -Depth 50
Evidence:

Find screenshot_url in logs (run details endpoint)

Open: http://localhost:8000<SCREENSHOT_URL>

☁️ Option B: Real AWS Bedrock Mode (Nova + Titan)
This mode uses:

Titan Text Embeddings v2 for embeddings

Nova 2 Lite for planning/chat via Bedrock

1) Start Postgres
docker compose up -d
2) Configure environment
Create services/api/.env (DO NOT commit it). Example:

DATABASE_URL=postgresql+asyncpg://novaflow:novaflowpass@localhost:5432/novaflow

NOVA_PROVIDER=bedrock

AWS_PROFILE=novaflow
AWS_REGION=eu-north-1
AWS_DEFAULT_REGION=eu-north-1
BEDROCK_REGION=eu-north-1

NOVA_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0
NOVA_LITE_MODEL_ID=eu.amazon.nova-2-lite-v1:0

DEMO_STARTING_URL=https://the-internet.herokuapp.com/
PLAYWRIGHT_HEADLESS=true
3) AWS login (SSO)
aws sso login --profile novaflow
aws sts get-caller-identity --profile novaflow
4) Run API + Web
Backend:

pip install -r services/api/requirements.txt
uvicorn services.api.app.main:app --reload --port 8000
Frontend:

cd apps/web
npm install
npm run dev
🎯 What to show judges (quick narrative)
Planner output: API returns a JSON plan with step instructions

Execution logs: each step is logged as "Executing UI step" + "UI step executed"

Evidence: screenshots stored under /artifacts/...

Offline demo: Mock Mode runs without AWS credentials

Architecture (simple)
apps/web (Next.js UI)

services/api (FastAPI + DB + planner + runner)

Postgres (Docker)

Flow:

UI sends task → API /task

API embeds + retrieves top brand docs → plans steps

API executes steps with Playwright (stateful session)

API stores logs + screenshots → served via /artifacts

Configuration
Frontend API base URL
Set in apps/web/.env.local (recommended):

NEXT_PUBLIC_API_URL=http://localhost:8000
The UI uses NEXT_PUBLIC_API_URL so it’s not hardcoded to localhost in code.

Database
docker-compose.yml starts Postgres with:

user: novaflow

password: novaflowpass

db: novaflow

port: 5432

API endpoints (useful)
GET /health — env + provider + model IDs + DB status

POST /brandkit/index — index brand docs

POST /task — create run with plan + context

GET /runs/{run_id} — run + logs + evidence URLs

POST /runs/{run_id}/execute-next-ui-step — execute next UI step

POST /runs/{run_id}/close-ui-session — cleanup session

GET /artifacts/... — screenshots & artifacts

Troubleshooting (common)
“AWS SSO expired / Session token not found”
aws sso login --profile <profile>
aws sts get-caller-identity --profile <profile>
DB not ready / connection errors
docker compose ps
docker compose logs -f postgres
Playwright missing browser
python -m playwright install chromium
Web UI stuck loading
Confirm API is running on port 8000

Confirm apps/web/.env.local has:
NEXT_PUBLIC_API_URL=http://localhost:8000

Restart Next dev server after changing env vars.

CORS errors
Backend must allow http://localhost:3000 (already configured in API).

Notes on evidence and safety
The planner generates a bounded set of steps.

The runner executes deterministic step primitives:

CLICK_TEXT, CLICK_ID, CLICK_CSS, TYPE_ID, WAIT_TEXT, WAIT_URL_CONTAINS, SCREENSHOT

The system never claims actions were performed unless confirmed by logs/evidence.

License
Hackathon project. Licensed under the MIT License. See `LICENSE`.
