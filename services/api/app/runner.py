from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Dict
import re
from pathlib import Path
from datetime import datetime

from .config import settings

# IMPORTANT: Playwright needs subprocess support on Windows.
# Selector event loop policy breaks asyncio subprocess -> NotImplementedError.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright


@dataclass
class UISession:
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page
    created_at: float
    last_used_at: float


# Keep UI sessions in-memory (per run_id). Good enough for demos/hackathons.
_SESSIONS: Dict[int, UISession] = {}


def _parse_instruction(instruction: str) -> dict:
    """
    Supported instructions (Runner DSL):

    Actions:
      - CLICK_TEXT: <text>
      - CLICK_ID: <id>
      - CLICK_CSS: <css>
      - TYPE_ID: <fieldId>=<value>

    Evidence / stability:
      - WAIT_TEXT: <text>
      - ASSERT_TEXT: <text>
      - WAIT_URL_CONTAINS: <fragment>
      - WAIT_MS: <milliseconds>
      - SCREENSHOT: <label>
    """
    instruction = (instruction or "").strip()

    m = re.match(r"^CLICK_TEXT:\s*(.+)$", instruction, flags=re.I)
    if m:
        return {"action": "click_text", "value": m.group(1).strip()}

    m = re.match(r"^CLICK_ID:\s*(.+)$", instruction, flags=re.I)
    if m:
        return {"action": "click_id", "value": m.group(1).strip()}

    m = re.match(r"^CLICK_CSS:\s*(.+)$", instruction, flags=re.I)
    if m:
        return {"action": "click_css", "value": m.group(1).strip()}

    m = re.match(r"^TYPE_ID:\s*([A-Za-z0-9_\-]+)\s*=\s*(.*)$", instruction, flags=re.I)
    if m:
        return {"action": "type_id", "field_id": m.group(1).strip(), "value": m.group(2)}

    m = re.match(r"^WAIT_TEXT:\s*(.+)$", instruction, flags=re.I)
    if m:
        return {"action": "wait_text", "value": m.group(1).strip()}

    m = re.match(r"^ASSERT_TEXT:\s*(.+)$", instruction, flags=re.I)
    if m:
        return {"action": "assert_text", "value": m.group(1).strip()}

    m = re.match(r"^WAIT_URL_CONTAINS:\s*(.+)$", instruction, flags=re.I)
    if m:
        return {"action": "wait_url_contains", "value": m.group(1).strip()}

    m = re.match(r"^WAIT_MS:\s*(\d+)\s*$", instruction, flags=re.I)
    if m:
        return {"action": "wait_ms", "value": int(m.group(1))}

    m = re.match(r"^SCREENSHOT:\s*(.*)$", instruction, flags=re.I)
    if m:
        label = (m.group(1) or "").strip() or "shot"
        return {"action": "screenshot", "value": label}

    # Fallback: treat as CLICK_TEXT for convenience
    return {"action": "click_text", "value": instruction}


def _artifact_paths(run_id: int, label: str) -> tuple[Path, str]:
    """
    Returns (absolute_path, public_url_path) for an artifact file.
    Public URL assumes FastAPI mounts /artifacts -> <services/api/artifacts>.
    """
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", label).strip("_") or "shot"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{ts}_{safe}.png"

    # runner.py is .../services/api/app/runner.py
    # parents[1] => .../services/api
    base_dir = Path(__file__).resolve().parents[1]
    out_dir = base_dir / "artifacts" / "screenshots" / f"run_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    abs_path = out_dir / filename
    public_url = f"/artifacts/screenshots/run_{run_id}/{filename}"
    return abs_path, public_url


def _get_or_create_session(run_id: int, starting_url: str) -> UISession:
    """
    Create a single persistent Playwright session per run_id.

    NOTE: Must be called from the SAME thread each time for a given run_id.
    FastAPI enforces this via a dedicated single-thread executor per run_id.
    """
    sess = _SESSIONS.get(run_id)
    if sess is not None:
        sess.last_used_at = time.time()
        return sess

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
    context = browser.new_context()
    page = context.new_page()
    page.goto(starting_url, wait_until="domcontentloaded", timeout=60000)

    sess = UISession(
        playwright=pw,
        browser=browser,
        context=context,
        page=page,
        created_at=time.time(),
        last_used_at=time.time(),
    )
    _SESSIONS[run_id] = sess
    return sess


def close_session(run_id: int) -> None:
    """
    Close and remove a UI session.
    """
    sess = _SESSIONS.pop(run_id, None)
    if not sess:
        return
    try:
        sess.context.close()
    except Exception:
        pass
    try:
        sess.browser.close()
    except Exception:
        pass
    try:
        sess.playwright.stop()
    except Exception:
        pass


def run_one_step_stateful(run_id: int, starting_url: str, instruction: str) -> dict:
    """
    Execute ONE UI step using a persistent session.
    Returns a small result payload for logging.
    """
    sess = _get_or_create_session(run_id, starting_url)
    page = sess.page

    spec = _parse_instruction(instruction)

    # Small delay for stability (demo sites load fast, but still)
    page.wait_for_timeout(250)

    timeout_click = 20000
    timeout_wait = 25000

    action = spec["action"]

    if action == "click_text":
        target = spec["value"]
        locator = page.get_by_text(target, exact=True)
        if locator.count() == 0:
            locator = page.get_by_text(target, exact=False)
        locator.first.click(timeout=timeout_click)

    elif action == "click_id":
        target = spec["value"]
        page.locator(f"#{target}").click(timeout=timeout_click)

    elif action == "click_css":
        css = spec["value"]
        page.locator(css).first.click(timeout=timeout_click)

    elif action == "type_id":
        field_id = spec["field_id"]
        value = spec["value"]
        locator = page.locator(f"#{field_id}")
        locator.wait_for(state="visible", timeout=timeout_wait)
        locator.fill(value, timeout=timeout_click)

    elif action == "wait_text":
        target = spec["value"]
        locator = page.get_by_text(target, exact=False)
        locator.first.wait_for(state="visible", timeout=timeout_wait)

    elif action == "assert_text":
        # ASSERT_TEXT should fail if not present. Give a short grace wait.
        target = spec["value"]
        locator = page.get_by_text(target, exact=False)
        try:
            locator.first.wait_for(state="visible", timeout=8000)
        except Exception as e:
            raise ValueError(f"ASSERT_TEXT failed: '{target}' not found/visible.") from e

    elif action == "wait_url_contains":
        frag = spec["value"]
        page.wait_for_url(f"**{frag}**", timeout=timeout_wait)

    elif action == "wait_ms":
        ms = int(spec["value"])
        page.wait_for_timeout(ms)

    elif action == "screenshot":
        label = spec["value"]
        abs_path, public_url = _artifact_paths(run_id, label)
        page.screenshot(path=str(abs_path), full_page=True)

        sess.last_used_at = time.time()
        return {
            "ok": True,
            "runner": "playwright-local-stateful",
            "run_id": run_id,
            "starting_url": starting_url,
            "instruction": instruction,
            "parsed": spec,
            "final_url": page.url,
            "title": page.title(),
            "screenshot_path": str(abs_path),
            "screenshot_url": public_url,
        }

    else:
        raise ValueError(f"Unsupported action: {spec}")

    # Let navigation finish if it happens
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass

    sess.last_used_at = time.time()

    return {
        "ok": True,
        "runner": "playwright-local-stateful",
        "run_id": run_id,
        "starting_url": starting_url,
        "instruction": instruction,
        "parsed": spec,
        "final_url": page.url,
        "title": page.title(),
    }
