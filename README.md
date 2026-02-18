# NovaFlow Ops
**Turn natural-language tasks into verified browser actions with human approval + audit trails.**  
Built for the **Amazon Nova AI Hackathon** using **Amazon Nova 2 Lite + Nova Multimodal Embeddings + Nova Act** (planned integration), with a working demo stack: **Next.js (web) + FastAPI (api)**.

---

## 🚀 Elevator Pitch
Small teams waste hours on repetitive “ops” work across web dashboards that often have limited APIs (posting updates, replying to reviews, updating settings, logging leads). **NovaFlow Ops** is an agentic assistant that doesn’t just suggest what to do. It **plans the workflow, requests human approval for sensitive steps, and produces an audit trail** so every action is explainable and reviewable.

---

## ✨ What it does
NovaFlow Ops converts a plain-English request into a verified workflow:

1. **Plan & draft**  
   Creates a step-by-step action plan and the text to publish (posts, replies, messages).

2. **Grounded knowledge (RAG) – planned**  
   Uses **Nova Multimodal Embeddings** to index a **Brand Kit** (docs/policies/examples) so outputs stay consistent with internal tone and rules.

3. **UI automation – planned**  
   Uses **Nova Act** to execute browser actions (navigate, click, fill forms, submit) in a controlled way.

4. **Human-in-the-loop (HITL)**  
   Before sensitive actions (publishing, editing settings), the agent pauses and requests approval.

5. **Audit trail**  
   Every step is logged with timestamps and artifacts so actions are explainable and reviewable.

---

## 🧠 Why it matters (Impact)
- **Community / SMB benefit:** reduces repetitive admin work and helps small teams move faster without needing API integrations for every tool.
- **Safer automation:** approvals + audit trails make “agentic” workflows more trustworthy and enterprise-friendly.
- **Brand consistency:** grounded generation reduces hallucinations and tone drift.

---

## 🏗 Architecture
**Monorepo layout**
novaflow-ops/
apps/
web/ # Next.js dashboard (task submission, run view, approval)
services/
api/ # FastAPI orchestrator (runs, steps, approval, audit)
brand-kit/ # Example policies, tone, product facts (for RAG)


**Current demo flow (working locally)**
- `POST /task` creates a run (`runId`) with steps and audit entries.
- `GET /runs/{runId}` shows status, steps, logs.
- `POST /runs/{runId}/approve` simulates HITL approval and completes execution (mock).

**Planned Nova-backed flow**
- **Nova 2 Lite**: planning, reasoning, copy generation
- **Nova Multimodal Embeddings**: Brand Kit indexing + retrieval (RAG)
- **Nova Act**: browser UI execution with deterministic boundaries

---

## 🧰 Tech Stack (Built With)
**Frontend**
- Next.js (App Router)
- TypeScript
- Tailwind CSS

**Backend**
- Python 3
- FastAPI
- Uvicorn

**Planned AWS / Nova**
- Amazon Bedrock (Nova models)
- Amazon Nova 2 Lite
- Amazon Nova Multimodal Embeddings
- Amazon Nova Act
- (Optional) S3 for artifact storage, DynamoDB for run metadata, CloudWatch for logs

---

## ✅ Requirements
- Node.js 18+ (recommended 20)
- Python 3.10+ (recommended 3.11)
- npm (or pnpm/yarn if you adapt scripts)

---

## 🧪 Run Locally (Development)
### 1) Clone repo

git clone <YOUR_REPO_URL>
cd novaflow-ops
2) Start the API (FastAPI)
cd services/api
python -m venv .venv
# Windows Git Bash:
source .venv/Scripts/activate
# macOS/Linux:
# source .venv/bin/activate

pip install -U pip
pip install fastapi uvicorn

uvicorn main:app --reload --port 8000
API docs:

Swagger UI: http://127.0.0.1:8000/docs

Health: http://127.0.0.1:8000/health

3) Start the Web App (Next.js)
Open a new terminal:

cd apps/web
npm install
Create apps/web/.env.local:

NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
Run:

npm run dev
Web UI:

http://localhost:3000

🧭 Demo Walkthrough (2–3 minutes)
Open the web UI at http://localhost:3000

Enter a task like:

“Reply to 3 reviews using our brand tone”

“Post an update announcing our new feature”

Click Create run

Observe:

generated steps (plan → automation prep → approval → execution)

audit trail entries

Click Approve

The run completes and the audit trail updates

This demonstrates: instruction → plan → approve → audit.

🔌 API Reference
Base URL: http://127.0.0.1:8000

GET /health
Returns { "ok": true }

POST /task
Request:

{ "task": "Reply to 3 reviews using our brand tone" }
Response:

{ "runId": "demo-run-xxxxxx", "task": "..." }
GET /runs/{runId}
Returns run status, steps, and audit trail.

POST /runs/{runId}/approve
Approves sensitive step(s) and completes the run (demo/mock execution).

🧱 Brand Kit (RAG-ready)
Place internal tone guides, examples, and policies under:

brand-kit/
  tone.md
  do-and-dont.md
  product-faq.md
  examples/
Planned: index these docs with Nova Multimodal Embeddings for grounded generation.

🔐 Security & Safety Considerations
NovaFlow Ops is designed around trustworthy agentic automation:

Approval gates (HITL) for sensitive actions

Restricted domains (planned) to reduce prompt injection during navigation

Deterministic step boundaries + retries (planned) to improve UI automation reliability

Audit trail to make actions explainable and reviewable

🧩 Roadmap (Post-Hackathon)
Real Nova planning: replace mock plan with Nova 2 Lite via Bedrock

Brand Kit RAG: embeddings + retrieval for consistent “brand-safe” copy

Nova Act execution: real browser automation + screenshots as artifacts

Governance: roles, approvals, policy templates

Integrations: CRM/ticketing/e-commerce dashboards

Optional: voice commands with Nova Sonic for hands-free ops

🎥 Video Demo (Submission)
Target: ~3 minutes

Must show the project functioning (create run → approve → audit trail)

Include hashtag #AmazonNova

No copyrighted music/trademarks without permission

📄 License
MIT (or your preferred license).
If you plan to keep it private during judging, remember to share access with:

testing@devpost.com

Amazon-Nova-hackathon@amazon.com

🙌 Acknowledgements
Built for the Amazon Nova AI Hackathon.
Thanks to Amazon Nova and Bedrock tooling for enabling rapid agentic prototypes.
