# NovaFlow Ops

NovaFlow Ops turns natural-language tasks into **verifiable browser actions**.

It generates a short, deterministic execution plan (RAG + planner), runs each UI step using Playwright, and stores **auditable logs + evidence screenshots** so results are inspectable, not “trust me bro”.

---

## What it does

Given a task like:

> Go to "Form Authentication", log in with username "tomsmith" and password "SuperSecretPassword!", then take a screenshot after login.

NovaFlow Ops will:

1. Retrieve relevant context (Brand Kit / RAG).
2. Produce a **bounded JSON plan** made of simple UI primitives.
3. Execute the plan step-by-step in a real browser session (Playwright).
4. Save **logs** + **screenshots** as evidence.
5. Expose evidence via API endpoints.

---

## Key features

- **Deterministic UI runner DSL** (one action per step)
- **Stateful Playwright sessions** (keeps browser state across steps per run)
- **Auditable execution logs** per run
- **Evidence artifacts** (screenshots) served via `/artifacts/...`
- **Provider switch**:
  - `NOVA_PROVIDER=mock` → no AWS needed (deterministic local embeddings + deterministic planner)
  - `NOVA_PROVIDER=bedrock` → real AWS Bedrock (**Titan embeddings** + **Nova 2 Lite planner**)

> Note: Embeddings are Titan by default. Planning is powered by Nova (Nova 2 Lite). This is intentional: Titan is used for RAG retrieval, while Nova is the reasoning/planning core.

---

## Architecture

- `apps/web` — Next.js UI
- `services/api` — FastAPI (planner + runner + DB + artifacts)
- Postgres — via Docker Compose

Flow:

1. Web UI sends task → `POST /task`
2. API embeds + retrieves top Brand Kit context (RAG)
3. Planner returns a JSON plan (steps)
4. Runner executes UI steps via Playwright
5. API stores logs + screenshots and serves them under `/artifacts`

---

## Runner DSL (supported UI instructions)

UI steps MUST use exactly one of these commands:

- `CLICK_TEXT: <text>`
- `CLICK_ID: <id>`
- `CLICK_CSS: <css>`
- `TYPE_ID: <fieldId>=<value>`
- `WAIT_TEXT: <text>`
- `ASSERT_TEXT: <text>`
- `WAIT_URL_CONTAINS: <fragment>`
- `WAIT_MS: <milliseconds>`
- `SCREENSHOT: <label>`

Anything outside this list is not guaranteed to run.

---

## Demo safety note (important)

For stability and safety in demos, the UI runner starts from `DEMO_STARTING_URL` (configured via env).
If your task contains a different URL, the planner may reference it, but the runner may still start from the demo URL depending on server configuration.

Recommended for reliable demos: use tasks that target the configured demo site (default: `https://the-internet.herokuapp.com/`).

---

## Quickstart

### Prerequisites

- Docker + Docker Compose
- Node.js 18+
- Python 3.11+

## One-command dev

Windows (PowerShell):
.\scripts\dev.ps1

### 1) Start Postgres

From repo root:

```bash
docker compose up -d
Default compose maps Postgres to port 5433 to avoid conflicts with local Postgres installs.

2) Backend (API)
Create and activate the venv from repo root:

Windows (PowerShell)

python -m venv .venv
.\.venv\Scripts\activate
pip install -r services/api/requirements.txt
python -m playwright install chromium
macOS/Linux

python -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
python -m playwright install chromium
Create services/api/.env (DO NOT commit):

# ----------------------------
# Database (Postgres)
# ----------------------------
DATABASE_URL=postgresql+asyncpg://novaflow:novaflowpass@localhost:5433/novaflow

# ----------------------------
# Provider selection
# ----------------------------
NOVA_PROVIDER=mock

# ----------------------------
# Demo site for UI automation
# ----------------------------
DEMO_STARTING_URL=https://the-internet.herokuapp.com/

# ----------------------------
# Playwright
# ----------------------------
PLAYWRIGHT_HEADLESS=true

# ----------------------------
# CORS
# ----------------------------
# Comma-separated list
CORS_ORIGINS=http://localhost:3000
Run the API:

uvicorn services.api.app.main:app --reload --port 8000
3) Frontend (Web UI)
cd apps/web
npm install
Create apps/web/.env.local:

NEXT_PUBLIC_API_URL=http://localhost:8000
Run:

npm run dev
Open:

Web UI: http://localhost:3000

API Docs: http://localhost:8000/docs

Health: http://localhost:8000/health

Provider Modes
NovaFlow Ops supports two providers controlled by NOVA_PROVIDER.

Option A: Mock provider (no AWS)
Set:

NOVA_PROVIDER=mock
Mock mode uses deterministic local embeddings and a deterministic planner.
Useful for local development and environments without AWS credentials.

Run:

uvicorn services.api.app.main:app --reload --port 8000
Option B: AWS Bedrock provider
Set:

NOVA_PROVIDER=bedrock
Create/update services/api/.env:

DATABASE_URL=postgresql+asyncpg://novaflow:novaflowpass@localhost:5433/novaflow

NOVA_PROVIDER=bedrock

AWS_PROFILE=novaflow
AWS_REGION=eu-north-1
AWS_DEFAULT_REGION=eu-north-1
BEDROCK_REGION=eu-north-1

# Embeddings: Titan (RAG)
NOVA_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0

# Planner: Nova 2 Lite
# Some accounts/regions require a region-prefixed model id like eu.amazon...
NOVA_LITE_MODEL_ID=amazon.nova-2-lite-v1:0
# NOVA_LITE_MODEL_ID=eu.amazon.nova-2-lite-v1:0

DEMO_STARTING_URL=https://the-internet.herokuapp.com/
PLAYWRIGHT_HEADLESS=true

# CORS
CORS_ORIGINS=http://localhost:3000
If using AWS SSO:

aws sso login --profile novaflow
aws sts get-caller-identity --profile novaflow
Then run:

uvicorn services.api.app.main:app --reload --port 8000
Index the Brand Kit (RAG)
If your repo contains Brand Kit markdown files, you can index them:

Example (PowerShell):

$docs = @(
  @{ title="tone"; content=(Get-Content .\brand-kit\tone.md -Raw); source="brand-kit"; tags=@("tone") },
  @{ title="policies"; content=(Get-Content .\brand-kit\policies.md -Raw); source="brand-kit"; tags=@("policies") },
  @{ title="examples"; content=(Get-Content .\brand-kit\examples.md -Raw); source="brand-kit"; tags=@("examples") }
)
$payload = @{ docs=$docs; embedding_dimension=1024 } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri http://localhost:8000/brandkit/index -ContentType "application/json" -Body $payload
Run a task
From the Web UI
Paste a task into the UI and click Create run, then Execute next UI step.

Recommended demo task:

Go to Form Authentication, login with tomsmith / SuperSecretPassword!, verify success text, then take a screenshot.

Execute steps via API (optional)
PowerShell example:

$runId = <RUN_ID>
1..6 | % { Invoke-RestMethod -Method Post "http://localhost:8000/runs/$runId/execute-next-ui-step" }
Invoke-RestMethod "http://localhost:8000/runs/$runId" | ConvertTo-Json -Depth 50
Evidence:

Inspect screenshot_url in the run logs.

Open:

http://localhost:8000<SCREENSHOT_URL>

API endpoints
GET /health — provider + model IDs + DB status

POST /brandkit/index — index Brand Kit docs

POST /task — create a run (plan + context)

GET /runs/{run_id} — run details + logs + evidence URLs

POST /runs/{run_id}/execute-next-ui-step — execute next UI step

POST /runs/{run_id}/close-ui-session — close Playwright session

GET /artifacts/... — screenshots & artifacts

Troubleshooting
AWS token / SSO errors
If you see errors like “SSO session expired”:

aws sso login --profile YOUR_PROFILE
aws sts get-caller-identity --profile YOUR_PROFILE
DB not ready / connection errors
docker compose ps
docker compose logs -f postgres
Playwright browser not installed
python -m playwright install chromium
Web UI stuck loading
Confirm API is running on http://localhost:8000

Confirm apps/web/.env.local contains:

NEXT_PUBLIC_API_URL=http://localhost:8000
Restart Next dev server after changing env vars.

CORS issues
Ensure backend CORS allows the frontend origin (configured via CORS_ORIGINS in services/api/.env).

Security notes
Never commit .env files containing secrets.

Screenshots/logs are stored locally under services/api/artifacts/... and exposed via /artifacts/....

Keep artifacts folders ignored in git.

License
MIT License. See LICENSE.
