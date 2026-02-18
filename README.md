# NovaFlow Ops 🚦
**Turn natural-language ops requests into verified browser actions with approvals and audit trails.**  
Built for the **Amazon Nova AI Hackathon** on **Amazon Bedrock** using **Amazon Nova 2 Lite (planning)** + **Embeddings for BrandKit RAG** + **Nova Act-style deterministic UI actions** (with a reliable local Playwright executor for demo parity).

> A practical agent system: **Plan → Retrieve Brand Context → Execute UI Steps → Capture Evidence → Audit Everything**.

---

## 🏆 Hackathon Summary
Modern teams waste time doing repetitive “ops” work inside web dashboards: replying to reviews, updating listings, posting announcements, logging leads, and clicking through UI flows that often have limited or no APIs.

**NovaFlow Ops** takes a plain-English instruction and produces:
- a **structured, deterministic plan** (JSON steps)
- **brand-grounded output** (via BrandKit retrieval)
- **browser actions** executed step-by-step with safety boundaries
- a complete **audit trail** of what happened, when, and where

This is agentic automation designed to be **trustworthy, explainable, and demo-ready**.

---

## ✨ Core Capabilities
### 1) Natural-Language → Structured Plan (Nova 2 Lite)
- Converts a task into **strict JSON**:
  - `starting_url`
  - `steps[]` (UI and non-UI)
  - each step includes an `id`, `type`, `instruction`, and evidence intent

### 2) BrandKit RAG (Embeddings + Retrieval)
- Index internal docs (tone, policies, examples) into a searchable store
- Retrieve **top-k relevant snippets** per task
- Feed retrieved context into the planner to keep outputs **consistent and compliant**

### 3) Deterministic UI Execution (Nova Act-style actions)
Steps are intentionally narrow and inspectable:
- `CLICK_TEXT: ...`
- `CLICK_CSS: ...`
- `CLICK_ID: ...`
- `TYPE_ID: field=value`

This keeps automation safe and debuggable: the system never “freestyles” UI control outside the allowed instruction grammar.

### 4) Human-in-the-loop approvals (HITL)
- Steps can be flagged `requires_approval=true`
- Execution pauses until approval is granted (UI-ready + API-ready)

### 5) Audit Trail + Evidence
Every run produces logs with timestamps and step results:
- step executed / failed
- final URL, page title
- error tracebacks (on failures)
- (optional) artifacts such as screenshots per step

---

## 🧱 Architecture
**Monorepo**
novaflow-ops/
apps/
web/ # Next.js UI (task submission, run viewer, approvals)
services/
api/ # FastAPI orchestrator (planner, RAG, runner, audit)
brand-kit/ # Example BrandKit docs (tone/policy/examples)
docker-compose.yml # Postgres for runs/logs
scripts/ # Demo helpers (PowerShell)


**Runtime flow**
1. **Index BrandKit** (embeddings)
2. **Create task** → planner generates strict JSON plan
3. **Run execution** step-by-step (with approvals if needed)
4. **Persist logs + artifacts**
5. **Review run** in UI or via API

---

## 🧰 Tech Stack
**Frontend**
- Next.js (App Router)
- TypeScript
- Tailwind CSS

**Backend**
- Python 3.10+
- FastAPI + Uvicorn
- SQLModel + Postgres
- Playwright (stateful UI execution for deterministic demo)

**AWS / Nova (Bedrock)**
- Amazon Nova 2 Lite (planning)
- Embeddings (BrandKit indexing + retrieval)
- Nova Act integration pattern (bounded UI action grammar)

---

## ✅ Requirements
- Node.js 18+ (recommended 20)
- Python 3.10+ (recommended 3.11)
- Docker Desktop (Postgres)
- AWS credentials (Bedrock access)  
  If using AWS SSO: AWS CLI v2 configured with your profile

---

## 🚀 Quickstart (Local, End-to-End)
### 1) Clone

git clone <YOUR_REPO_URL>
cd novaflow-ops
2) Start Postgres
docker compose up -d
docker exec -it novaflow-postgres psql -U novaflow -d novaflow -c "select 1;"
3) Configure API env
Copy env example and fill in values:

# Windows PowerShell
Copy-Item services/api/.env.example services/api/.env
If using AWS SSO:

aws sso login --profile <YOUR_PROFILE>
4) Run the API
cd services/api
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

pip install -U pip
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
API docs:

Swagger: http://127.0.0.1:8000/docs

Health: http://127.0.0.1:8000/health

5) Run the Web UI (optional but recommended)
cd apps/web
npm install
npm run dev
Web UI:

http://localhost:3000

🎬 Demo Script (2–3 minutes, judge-friendly)
A) Index BrandKit
POST /brandkit/index
Example docs:

demo site description

credentials and expected success text

tone rules / do & don’t

B) Create a Run
POST /task
Use deterministic instructions to avoid UI flakiness:

prefer CLICK_CSS: button[type="submit"] over text-based submit

C) Execute Steps (automatic)
Run until DONE or ERROR:

POST /runs/{run_id}/execute-first-ui-step

then repeat: POST /runs/{run_id}/execute-next-ui-step

D) Verify Evidence / Logs
GET /runs/{run_id}
Show:

executed step IDs

final URLs (e.g. secure area)

timestamps and audit messages

🔌 API Overview
Base URL: http://127.0.0.1:8000

GET /health
Returns provider, region, configured model IDs, DB status

POST /brandkit/index
Index BrandKit docs into embedding store

POST /task
Create a run: retrieve context → plan JSON → persist run + logs

GET /runs/{run_id}
Fetch run details and full audit log

POST /runs/{run_id}/execute-first-ui-step
Execute first pending UI step

POST /runs/{run_id}/execute-next-ui-step
Execute next pending UI step (stateful Playwright session)

POST /runs/{run_id}/close-ui-session
Cleanup UI session resources

🔐 Safety, Security, and Reliability
No secrets committed (.env is ignored, .env.example included)

Bounded UI action grammar prevents “agent freestyle”

Stateful browser session per run (thread-safe executor)

Audit logs for every action

Strong defaults for stability:

use CSS selectors for submit buttons

timeouts + structured error reporting

🧩 What makes this “agentic” (and not a toy)
Planning is structured and validated (strict JSON)

Outputs are grounded via BrandKit retrieval

Actions are deterministic and inspectable

Execution is stepwise, approval-friendly, and fully logged

🏁 Submission Notes
Built for the Amazon Nova AI Hackathon

Demonstrates a complete loop: instruction → plan → execution → evidence → audit

Includes hashtag: #AmazonNova

📄 License
MIT (or replace with your preferred license)

🙌 Acknowledgements
Built for the Amazon Nova AI Hackathon using Amazon Bedrock + Nova models.
Thanks to the Nova ecosystem for enabling rapid agentic prototypes with governance-friendly patterns.
