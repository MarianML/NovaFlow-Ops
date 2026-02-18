from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Literal, Optional
from uuid import uuid4
from datetime import datetime

app = FastAPI(title="NovaFlow Ops API", version="0.1.0")

# --- CORS para que Next.js (3000) pueda llamar al API (8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelos
class TaskRequest(BaseModel):
    task: str

StepStatus = Literal["pending", "done"]

class Step(BaseModel):
    id: str
    title: str
    status: StepStatus = "pending"
    requires_approval: bool = False
    approved_at: Optional[str] = None

RunStatus = Literal["queued", "awaiting_approval", "running", "done"]

class Run(BaseModel):
    runId: str
    task: str
    status: RunStatus
    created_at: str
    steps: List[Step]
    audit: List[str]

# --- “DB” en memoria (para demo)
RUNS: Dict[str, Run] = {}

@app.get("/")
def root():
    return {"name": "NovaFlow Ops API", "docs": "/docs"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/task")
def create_task(payload: TaskRequest):
    run_id = f"demo-run-{uuid4().hex[:6]}"
    now = datetime.utcnow().isoformat() + "Z"

    # Plan mock (después lo reemplazas por Nova 2 Lite)
    steps = [
        Step(id="step-1", title="Generate action plan + draft copy", status="done"),
        Step(id="step-2", title="Prepare UI automation (navigate/click/fill)", status="done"),
        Step(id="step-3", title="Request human approval before publishing", requires_approval=True),
        Step(id="step-4", title="Execute publish + save proof (screenshot/logs)"),
    ]

    run = Run(
        runId=run_id,
        task=payload.task,
        status="awaiting_approval",
        created_at=now,
        steps=steps,
        audit=[
            f"{now} - run created",
            f"{now} - plan generated",
            f"{now} - ready for approval",
        ],
    )
    RUNS[run_id] = run
    return {"runId": run_id, "task": payload.task}

@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@app.post("/runs/{run_id}/approve")
def approve(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    now = datetime.utcnow().isoformat() + "Z"

    # Marca el step de approval como done
    approved_any = False
    for s in run.steps:
        if s.requires_approval and s.status != "done":
            s.status = "done"
            s.approved_at = now
            approved_any = True

    if not approved_any:
        return {"ok": True, "message": "Nothing to approve"}

    run.status = "running"
    run.audit.append(f"{now} - human approval granted")

    # Ejecuta el último step (mock)
    for s in run.steps:
        if s.id == "step-4":
            s.status = "done"
    run.status = "done"
    run.audit.append(f"{now} - execution completed (mock)")

    RUNS[run_id] = run
    return {"ok": True, "runId": run_id, "status": run.status}
