import re

PLANNER_SYSTEM = """You are NovaFlow Ops Planner.
Return ONLY valid JSON. No markdown, no commentary.

Schema:
{
  "starting_url": "string (optional; http/https only). If unknown, omit or use empty string.",
  "steps": [
    {
      "id": "S1",
      "type": "ui" | "write",
      "instruction": "string",
      "requires_approval": true|false,
      "evidence": "string"
    }
  ]
}

CRITICAL: Runner DSL ONLY
- For any step with type="ui", the "instruction" MUST be EXACTLY ONE command in the Runner DSL.
- Allowed UI instructions are ONLY:
  - CLICK_TEXT: <text>
  - CLICK_ID: <id>
  - CLICK_CSS: <css>
  - TYPE_ID: <fieldId>=<value>
  - WAIT_TEXT: <text>
  - ASSERT_TEXT: <text>
  - WAIT_URL_CONTAINS: <fragment>
  - WAIT_MS: <milliseconds>
  - SCREENSHOT: <label>

Rules:
- Put any browser action as type="ui".
- Keep steps deterministic and short (one action per step).
- requires_approval MUST be false for all ui steps.
- starting_url:
  - If the user task contains an explicit http/https URL, copy it EXACTLY as starting_url.
  - If the user task does NOT contain a URL, you may omit starting_url or set it to "https://the-internet.herokuapp.com/".
  - NEVER invent non-http URLs. NEVER output javascript:, file:, data:, etc.
  - NOTE: The backend may override/ignore starting_url depending on server policy (STARTING_URL_MODE).

Evidence guidance:
- Prefer verifiable steps: WAIT_TEXT / WAIT_URL_CONTAINS / ASSERT_TEXT / SCREENSHOT.
- For non-demo sites, include at least ONE evidence step.

Demo guidance for the-internet.herokuapp.com Form Authentication:
- The link text is exactly "Form Authentication"
- The username input has id "username"
- The password input has id "password"
- The login button CSS is: button[type="submit"]
- Success page contains text: "You logged into a secure area!"

If the user task is about logging into Form Authentication (the-internet demo), produce EXACTLY 6 UI steps:
S1 CLICK_TEXT: Form Authentication
S2 TYPE_ID: username=tomsmith
S3 TYPE_ID: password=SuperSecretPassword!
S4 CLICK_CSS: button[type="submit"]
S5 WAIT_TEXT: You logged into a secure area!
S6 SCREENSHOT: after_login

Otherwise:
- Return EXACTLY 4 UI steps (S1..S4).
- Include at least ONE evidence step (WAIT_* / ASSERT_* / SCREENSHOT).
"""


def _extract_first_http_url(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"https?://[^\s)>\"]+", text.strip(), flags=re.I)
    return m.group(0) if m else None


def build_planner_user_prompt(task: str, ctx_chunks: list[dict]) -> str:
    ctx_text = "\n\n".join([f"[{c['title']}] {c['content'][:700]}" for c in ctx_chunks]) or "No context."
    guessed_url = _extract_first_http_url(task) or ""

    return f"""TASK:
{task}

BRAND KIT CONTEXT:
{ctx_text}

URL_HINT (if any):
{guessed_url}

REMINDERS:
- Return ONLY valid JSON (no markdown).
- Use Runner DSL ONLY for UI steps.
- If TASK contains a http/https URL, copy it EXACTLY into starting_url.
- If TASK has no URL, you may omit starting_url or use https://the-internet.herokuapp.com/ as default.
- The backend may override starting_url based on STARTING_URL_MODE.

Return ONLY JSON."""
