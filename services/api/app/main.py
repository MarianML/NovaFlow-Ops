import json
import traceback
import asyncio
import re
import ipaddress
from urllib.parse import urlparse
from datetime import datetime
from typing import Optional, Set, Dict
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anyio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .db import init_db, get_session
from .models import BrandDoc, Run, RunLog
from .bedrock import nova_embed_text, nova_plan_with_lite
from .rag import top_k
from .planner import PLANNER_SYSTEM, build_planner_user_prompt
from .runner import run_one_step_stateful, close_session
from .config import settings
from .url_utils import sanitize_http_url

app = FastAPI(title="NovaFlow Ops API", version="0.2.0")

# --- Serve artifacts (screenshots, etc.) ---
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# One dedicated single-thread executor per run_id (keeps Playwright session thread-safe)
_UI_EXECUTORS: Dict[int, ThreadPoolExecutor] = {}


@app.on_event("startup")
async def on_startup():
    settings.validate()
    await init_db()


@app.on_event("shutdown")
async def on_shutdown():
    for run_id in list(_UI_EXECUTORS.keys()):
        try:
            close_session(run_id)
        except Exception:
            pass

    for ex in _UI_EXECUTORS.values():
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    _UI_EXECUTORS.clear()


def add_log(session: AsyncSession, run_id: int, level: str, message: str, data: dict | None = None):
    session.add(RunLog(run_id=run_id, level=level, message=message, data_json=json.dumps(data or {})))


def _get_executor(run_id: int) -> ThreadPoolExecutor:
    ex = _UI_EXECUTORS.get(run_id)
    if ex is None:
        ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"ui-run-{run_id}")
        _UI_EXECUTORS[run_id] = ex
    return ex


async def _run_ui_in_executor(run_id: int, fn, *args, timeout_seconds: int = 90):
    loop = asyncio.get_running_loop()
    ex = _get_executor(run_id)

    with anyio.fail_after(timeout_seconds):
        return await loop.run_in_executor(ex, partial(fn, *args))


def _strip_markdown_code_fences(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^\s*```(?:json|JSON)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _extract_json_object(text: str) -> str:
    s = (text or "").strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return s
    return s[start : end + 1]


def _parse_planner_json(plan_text: str) -> dict:
    raw = (plan_text or "").strip()

    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    cleaned = _strip_markdown_code_fences(raw)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    extracted = _extract_json_object(cleaned)
    try:
        obj = json.loads(extracted)
        if isinstance(obj, dict):
            return obj
    except Exception as e:
        preview = raw[:500].replace("\n", "\\n")
        raise HTTPException(500, f"Planner returned invalid JSON. Raw preview: {preview}") from e

    raise HTTPException(500, "Planner returned JSON but not an object/dict.")


# -----------------------------
# Starting URL selection (FIX + SSRF hygiene)
# -----------------------------
def _is_blocked_host(host: str) -> bool:
    """
    Block localhost + private/loopback IPs.
    NOTE: This does not DNS-resolve domains. It only blocks literal IP hosts + localhost.
    """
    h = (host or "").strip().lower()
    if not h:
        return True
    if h == "localhost":
        return True

    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def _choose_starting_url(plan_starting_url: str | None) -> str:
    """
    Decide starting URL based on STARTING_URL_MODE:

    - demo: always DEMO_STARTING_URL
    - plan: allow plan's starting_url only if hostname is in ALLOWED_STARTING_HOSTS
    - any_public: accept any http/https public host (still blocks localhost/private IPs)

    Always returns a safe http/https URL (fallbacks if invalid).
    """
    mode = (settings.STARTING_URL_MODE or "demo").strip().lower()

    demo_fallback = (
        sanitize_http_url(settings.DEMO_STARTING_URL)
        or "https://the-internet.herokuapp.com/"
    )

    if mode == "demo":
        return demo_fallback

    safe_plan_url = sanitize_http_url(plan_starting_url or "")
    if not safe_plan_url:
        return demo_fallback

    host = (urlparse(safe_plan_url).hostname or "").lower()
    if _is_blocked_host(host):
        return demo_fallback

    if mode == "any_public":
        return safe_plan_url

    if mode == "plan":
        allowed = set(settings.ALLOWED_STARTING_HOSTS_LIST)
        return safe_plan_url if host in allowed else demo_fallback

    return demo_fallback


# -----------------------------
# Plan validation (prevents model nonsense)
# -----------------------------
_ALLOWED_DSL_PREFIXES = (
    "CLICK_TEXT:",
    "CLICK_ID:",
    "CLICK_CSS:",
    "TYPE_ID:",
    "WAIT_TEXT:",
    "ASSERT_TEXT:",
    "WAIT_URL_CONTAINS:",
    "WAIT_MS:",
    "SCREENSHOT:",
)


def _validate_plan(plan: dict) -> None:
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise HTTPException(500, "Planner returned a plan without 'steps' list.")

    for i, s in enumerate(steps, start=1):
        if not isinstance(s, dict):
            raise HTTPException(500, f"Planner step #{i} is not an object.")

        stype = (s.get("type") or "").strip().lower()
        if stype == "ui":
            instr = (s.get("instruction") or "").strip()
            if not instr:
                raise HTTPException(500, f"Planner UI step #{i} has empty instruction.")
            if not any(instr.upper().startswith(p) for p in _ALLOWED_DSL_PREFIXES):
                raise HTTPException(
                    500,
                    f"Planner UI step #{i} instruction not in Runner DSL: '{instr}'"
                )

            if s.get("requires_approval") not in (False, None):
                raise HTTPException(500, f"Planner UI step #{i} requires_approval must be false.")

        elif stype in ("write", ""):
            # write steps are allowed in schema, but runner ignores them.
            # Keeping them won't break anything; they just won't be executed by /execute-next-ui-step.
            pass
        else:
            raise HTTPException(500, f"Planner step #{i} has invalid type='{s.get('type')}'.")


# ---------------------------
# Schemas
# ---------------------------
class BrandDocIn(BaseModel):
    title: str
    content: str
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)


class BrandKitIndexIn(BaseModel):
    docs: list[BrandDocIn]
    embedding_dimension: int = 1024


class TaskIn(BaseModel):
    task: str
    top_k: int = 4


# ---------------------------
# Routes
# ---------------------------
@app.get("/health")
async def health():
    effective_chat_model_id = (settings.NOVA_INFERENCE_PROFILE_ID or settings.NOVA_LITE_MODEL_ID)
    return {
        "ok": True,
        "provider": settings.NOVA_PROVIDER,
        "aws_region": settings.BEDROCK_REGION,
        "embed_model_id": settings.NOVA_EMBED_MODEL_ID,
        "lite_model_id": settings.NOVA_LITE_MODEL_ID,
        "inference_profile_id": settings.NOVA_INFERENCE_PROFILE_ID,
        "effective_chat_model_id": effective_chat_model_id,
        "db_configured": bool(settings.EFFECTIVE_DATABASE_URL),
        "artifacts_url": "/artifacts",
        "starting_url_mode": settings.STARTING_URL_MODE,
        "allowed_starting_hosts": settings.ALLOWED_STARTING_HOSTS_LIST,
        "demo_starting_url": settings.DEMO_STARTING_URL,
        "cors_origins": settings.CORS_ORIGINS_LIST,
    }


@app.post("/brandkit/index")
async def brandkit_index(payload: BrandKitIndexIn, session: AsyncSession = Depends(get_session)):
    count = 0
    for d in payload.docs:
        vec = await anyio.to_thread.run_sync(nova_embed_text, d.content, payload.embedding_dimension)
        session.add(
            BrandDoc(
                title=d.title,
                source=d.source,
                content=d.content,
                tags=",".join(d.tags),
                embedding_json=json.dumps(vec),
            )
        )
        count += 1

    await session.commit()
    return {"ok": True, "indexed": count}


@app.post("/task")
async def create_task(payload: TaskIn, session: AsyncSession = Depends(get_session)):
    qvec = await anyio.to_thread.run_sync(nova_embed_text, payload.task, 1024)

    rows = (await session.exec(select(BrandDoc))).all()
    docs = [(r.id, r.title, r.content, json.loads(r.embedding_json)) for r in rows]

    hits = top_k(qvec, docs, k=payload.top_k)
    ctx = [{"doc_id": h[1], "title": h[2], "content": h[3], "score": h[0]} for h in hits]

    user_prompt = build_planner_user_prompt(payload.task, ctx)
    plan_text = await anyio.to_thread.run_sync(nova_plan_with_lite, PLANNER_SYSTEM, user_prompt)
    plan = _parse_planner_json(plan_text)

    # Normalize/sanitize starting_url once, store it in the plan
    plan["starting_url"] = _choose_starting_url(plan.get("starting_url"))

    # Validate steps so the runner won't crash on weird outputs
    _validate_plan(plan)

    run = Run(
        task=payload.task,
        status="PLANNED",
        plan_json=json.dumps(plan),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    add_log(session, run.id, "INFO", "Run created", {"ctx": ctx, "plan": plan})
    await session.commit()

    return {"run_id": run.id, "plan": plan, "ctx": ctx}


@app.get("/runs/{run_id}")
async def get_run(run_id: int, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    logs = (
        await session.exec(
            select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.ts)
        )
    ).all()

    return {
        "run": {
            "id": run.id,
            "task": run.task,
            "status": run.status,
            "plan": json.loads(run.plan_json),
        },
        "logs": [
            {"ts": l.ts, "level": l.level, "message": l.message, "data": json.loads(l.data_json)}
            for l in logs
        ],
    }


def _executed_step_ids(logs: list[RunLog]) -> Set[str]:
    executed: Set[str] = set()
    for l in logs:
        if l.message == "UI step executed":
            try:
                data = json.loads(l.data_json)
                sid = data.get("step_id")
                if sid:
                    executed.add(sid)
            except Exception:
                pass
    return executed


def _pick_next_ui_step(plan: dict, executed_ids: Set[str]) -> Optional[dict]:
    steps = plan.get("steps", [])
    for s in steps:
        if (s.get("type") == "ui") and (s.get("id") not in executed_ids):
            return s
    return None


@app.post("/runs/{run_id}/execute-first-ui-step")
async def execute_first_ui_step(run_id: int, session: AsyncSession = Depends(get_session)):
    return await execute_next_ui_step(run_id, session)


@app.post("/runs/{run_id}/execute-next-ui-step")
async def execute_next_ui_step(run_id: int, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    plan = json.loads(run.plan_json)

    # Use plan.starting_url (already normalized), but re-apply safe fallback rules anyway
    starting_url = _choose_starting_url(plan.get("starting_url"))

    logs = (
        await session.exec(
            select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.ts)
        )
    ).all()

    executed_ids = _executed_step_ids(logs)
    ui_step = _pick_next_ui_step(plan, executed_ids)

    if not ui_step:
        run.status = "DONE"
        run.updated_at = datetime.utcnow()
        session.add(run)
        await session.commit()
        return {"run_id": run_id, "status": "DONE", "executed_step_id": None}

    instruction = (ui_step.get("instruction") or "").strip() or "CLICK_TEXT: Example"
    step_id = ui_step.get("id")

    # safer than list.index()
    step_index = -1
    for idx, s in enumerate(plan.get("steps", [])):
        if s.get("id") == step_id:
            step_index = idx
            break

    run.status = "RUNNING"
    run.updated_at = datetime.utcnow()
    session.add(run)

    add_log(
        session,
        run_id,
        "INFO",
        "Executing UI step",
        {"step_index": step_index, "step_id": step_id, "starting_url": starting_url, "instruction": instruction},
    )
    await session.commit()

    try:
        result = await _run_ui_in_executor(
            run_id,
            run_one_step_stateful,
            run_id,
            starting_url,
            instruction,
            timeout_seconds=90,
        )

        add_log(
            session,
            run_id,
            "INFO",
            "UI step executed",
            {"step_index": step_index, "step_id": step_id, "result": result},
        )

        remaining = _pick_next_ui_step(plan, executed_ids | {step_id})
        run.status = "DONE" if remaining is None else "PLANNED"

    except Exception as e:
        add_log(
            session,
            run_id,
            "ERROR",
            "UI step failed",
            {"step_index": step_index, "step_id": step_id, "error": str(e), "traceback": traceback.format_exc()},
        )
        run.status = "ERROR"

    run.updated_at = datetime.utcnow()
    session.add(run)
    await session.commit()

    return {"run_id": run_id, "status": run.status, "executed_step_id": step_id}


@app.post("/runs/{run_id}/close-ui-session")
async def close_ui_session(run_id: int, session: AsyncSession = Depends(get_session)):
    try:
        await _run_ui_in_executor(run_id, close_session, run_id, timeout_seconds=30)
    except Exception:
        close_session(run_id)

    ex = _UI_EXECUTORS.pop(run_id, None)
    if ex:
        ex.shutdown(wait=False, cancel_futures=True)

    return {"ok": True, "run_id": run_id}
