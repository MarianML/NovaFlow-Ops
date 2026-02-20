# NovaFlow Ops

NovaFlow Ops turns natural-language tasks into **verifiable browser actions**.

It generates a short, deterministic execution plan (RAG + planner), executes each UI step using Playwright, and stores **auditable logs + evidence screenshots** so results are inspectable — not “trust me bro”.

---

## What it does

Given a task like:

> Go to "Form Authentication", log in with username "tomsmith" and password "SuperSecretPassword!", then take a screenshot after login.

NovaFlow Ops will:

1. Retrieve relevant context (Brand Kit / RAG).
2. Produce a **bounded JSON plan** made of simple UI primitives.
3. Execute the plan step-by-step in a real browser session (Playwright).
4. Save **structured logs** + **screenshots** as evidence.
5. Expose evidence via API endpoints.

---

## Core components (what powers what)

- **Amazon Nova 2 Lite (Bedrock Converse)** — Agent planning and reasoning (produces the bounded JSON execution plan).
- **Amazon Titan Text Embeddings v2** — Retrieval for RAG (selects the most relevant Brand Kit context chunks).
- **Playwright (Chromium)** — Verifiable UI execution (runs each UI step in a real browser session).
- **Auditable output** — Every run produces structured logs and evidence screenshots served under `/artifacts/...`.

> Titan is used for retrieval (RAG). Nova is the reasoning/planning core.

---

## Architecture

- `apps/web` — Next.js 16 frontend
- `services/api` — FastAPI backend (planner + runner + DB + artifacts)
- Postgres — via Docker Compose

Flow:

1. Web UI sends task → `POST /task`
2. API embeds + retrieves top Brand Kit context (RAG)
3. Planner (Nova 2 Lite) returns a bounded JSON plan
4. Runner executes UI steps via Playwright
5. API stores logs + screenshots and serves them under `/artifacts`

---

## Runner DSL (supported UI instructions)

Each step must use exactly one of these commands:

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

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node **18.18+ or 20+ recommended**
- AWS CLI (only for Bedrock mode)

> The frontend uses **Next.js 16**.

---

## Quickstart (Mock Mode) — 5 Steps

No AWS required. Fully deterministic local mode.

### 1) Start Postgres

```bash
docker compose up -d
```

(Postgres runs on port `5433` by default.)

---

### 2) Setup backend

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r services/api/requirements.txt
python -m playwright install chromium
```

---

### 3) Create `services/api/.env`

```env
DATABASE_URL=postgresql+asyncpg://novaflow:novaflowpass@localhost:5433/novaflow
NOVA_PROVIDER=mock
DEMO_STARTING_URL=https://the-internet.herokuapp.com/
PLAYWRIGHT_HEADLESS=true
CORS_ORIGINS=http://localhost:3000
```

---

### 4) Run API

```bash
uvicorn services.api.app.main:app --reload --port 8000
```

---

### 5) Run frontend

```bash
cd apps/web
npm install
```

Create `apps/web/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start:

```bash
npm run dev
```

Open:

- Web UI → <http://localhost:3000>
- API Docs → <http://localhost:8000/docs>
- Health → <http://localhost:8000/health>

---

## Quickstart (Bedrock Mode) — 5 Steps

Uses real Amazon Nova + Titan via AWS Bedrock.

---

### 1) Configure AWS

```bash
aws sso login --profile YOUR_PROFILE
aws sts get-caller-identity --profile YOUR_PROFILE
```

---

### 2) Update `services/api/.env`

```env
DATABASE_URL=postgresql+asyncpg://novaflow:novaflowpass@localhost:5433/novaflow

NOVA_PROVIDER=bedrock

AWS_PROFILE=YOUR_PROFILE
AWS_REGION=eu-north-1
AWS_DEFAULT_REGION=eu-north-1
BEDROCK_REGION=eu-north-1

# Embeddings (RAG)
NOVA_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0

# Planner (Nova 2 Lite)
NOVA_LITE_MODEL_ID=amazon.nova-2-lite-v1:0
# Some regions may require:
# NOVA_LITE_MODEL_ID=eu.amazon.nova-2-lite-v1:0

DEMO_STARTING_URL=https://the-internet.herokuapp.com/
PLAYWRIGHT_HEADLESS=true
CORS_ORIGINS=http://localhost:3000
```

---

### 3) Start Postgres

```bash
docker compose up -d
```

---

### 4) Start backend

```bash
uvicorn services.api.app.main:app --reload --port 8000
```

---

### 5) Start frontend

```bash
cd apps/web
npm run dev
```

---

## Demo Script (3 Minutes)

Run full demo end-to-end:

```powershell
.\scripts\demo.ps1
```

This will:

- Start Postgres
- Launch API
- Index Brand Kit
- Create demo run
- Execute UI steps
- Generate screenshot artifacts

Then open:

- API Docs → <http://localhost:8000/docs>
- Artifacts → <http://localhost:8000/artifacts>
- Health → <http://localhost:8000/health>

---

## Running a Task

Recommended demo task:

```text
Go to Form Authentication, login with tomsmith / SuperSecretPassword!, verify success text, then take a screenshot.
```

From Web UI:

- Click **Create Run**
- Execute steps one by one

Or via API:

```powershell
$runId = "<RUN_ID>"
1..6 | % { Invoke-RestMethod -Method Post "http://localhost:8000/runs/$runId/execute-next-ui-step" }
Invoke-RestMethod "http://localhost:8000/runs/$runId" | ConvertTo-Json -Depth 50
```

---

## API Endpoints

- `GET /health` — provider + model IDs + DB status
- `POST /brandkit/index` — index Brand Kit documents
- `POST /task` — create a run (plan + context)
- `GET /runs/{run_id}` — run details + logs + evidence URLs  
  - Evidence screenshots: check `result.screenshot_url` in logs, or browse `/artifacts/`
- `POST /runs/{run_id}/execute-next-ui-step` — execute next UI step
- `POST /runs/{run_id}/close-ui-session` — close Playwright session
- `GET /artifacts/...` — screenshots & artifacts

---

## Troubleshooting

## AWS SSO / Token errors

If you see expired session errors:

```bash
aws sso login --profile YOUR_PROFILE
aws sts get-caller-identity --profile YOUR_PROFILE
```

---

## Bedrock inference profile issues

If Nova 2 Lite fails:

- Ensure model access is enabled in your AWS region
- Try region-prefixed model ID:
  
```text
eu.amazon.nova-2-lite-v1:0
```

- Verify `BEDROCK_REGION` matches your enabled region

---

## Database connection errors

```bash
docker compose ps
docker compose logs -f postgres
```

Ensure port `5433` is available.

---

## Playwright browser missing

```bash
python -m playwright install chromium
```

---

## Web UI stuck loading

- Confirm API is running at `http://localhost:8000`
- Confirm `apps/web/.env.local` contains:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Restart Next.js after changing env vars.

---

## CORS issues

Ensure backend `.env` contains:

```env
CORS_ORIGINS=http://localhost:3000
```

Restart API after changes.

---

## Security Notes

- Never commit `.env` files containing secrets.
- Artifacts are stored under `services/api/artifacts/...`
- Keep artifacts ignored in Git.

---

## SSRF Protection

The UI runner validates all starting URLs:

- Only http/https allowed
- Blocks localhost and private IP ranges
- Resolves DNS and blocks hostnames resolving to private or loopback addresses
- DNS resolution uses a timeout to prevent hanging

This reduces SSRF risk during UI automation.

---

## License

MIT License. See `LICENSE`.
