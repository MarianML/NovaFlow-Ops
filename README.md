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
  - `NOVA_PROVIDER=bedrock` → real AWS Bedrock (Titan embeddings + Nova planner)

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
- `SCREENSHOT: <label>`

Anything outside this list is not guaranteed to run.

---

## Quickstart

### Prerequisites

- Docker + Docker Compose
- Node.js 18+
- Python 3.11+

### 1) Start Postgres

From repo root:

docker compose up -d
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
Run the API:

uvicorn services.api.app.main:app --reload --port 8000
3) Frontend (Web UI)
cd apps/web
npm install
npm run dev
Open:

Web UI: <http://localhost:3000>

API Docs: <http://localhost:8000/docs>

Health: <http://localhost:8000/health>

Configuration
Frontend API base URL
Create apps/web/.env.local:

NEXT_PUBLIC_API_URL=http://localhost:8000
Restart the Next dev server after changing env vars.

Provider Modes
NovaFlow Ops supports two providers controlled by NOVA_PROVIDER.

Option A: Mock provider (no AWS)
Set:

NOVA_PROVIDER=mock

Mock mode uses deterministic local embeddings and a deterministic planner. It is useful for local development and environments without AWS credentials.

Windows (PowerShell)
$env:NOVA_PROVIDER="mock"
uvicorn services.api.app.main:app --reload --port 8000
macOS/Linux
export NOVA_PROVIDER=mock
uvicorn services.api.app.main:app --reload --port 8000
Option B: AWS Bedrock provider
Set:

NOVA_PROVIDER=bedrock

AWS region/profile variables

Bedrock model IDs

Create services/api/.env (DO NOT commit):

DATABASE_URL=postgresql+asyncpg://novaflow:novaflowpass@localhost:5432/novaflow

NOVA_PROVIDER=bedrock

AWS_PROFILE=novaflow
AWS_REGION=eu-north-1
AWS_DEFAULT_REGION=eu-north-1
BEDROCK_REGION=eu-north-1

NOVA_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0
NOVA_LITE_MODEL_ID=amazon.nova-2-lite-v1:0

DEMO_STARTING_URL=https://the-internet.herokuapp.com/
PLAYWRIGHT_HEADLESS=true
If using AWS SSO:

aws sso login --profile novaflow
aws sts get-caller-identity --profile novaflow
Then run API:

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
Paste a task into the UI and click Run.

Execute steps via API (optional)
PowerShell example:

$runId = <RUN_ID>
1..6 | % { Invoke-RestMethod -Method Post "http://localhost:8000/runs/$runId/execute-next-ui-step" }
Invoke-RestMethod "http://localhost:8000/runs/$runId" | ConvertTo-Json -Depth 50
Evidence:

Inspect screenshot_url in the run logs.

Open: http://localhost:8000<SCREENSHOT_URL>

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

aws sso login --profile <profile>
aws sts get-caller-identity --profile <profile>
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
Backend must allow http://localhost:3000 (configure CORS in the API).

Security notes
Never commit .env files containing secrets.

Screenshots/logs are stored locally under services/api/artifacts/... and exposed via /artifacts/....

Keep artifact folders ignored in git.

License
MIT License. See LICENSE.
