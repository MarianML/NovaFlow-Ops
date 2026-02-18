PLANNER_SYSTEM = """You are NovaFlow Ops Planner.
Return ONLY valid JSON. No markdown, no commentary.

Schema:
{
  "starting_url": "https://...",
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

Rules:
- Keep steps deterministic and short.
- Put any browser action as type="ui".
- Make the first UI step safe and reversible.
- Always return EXACTLY 4 UI steps when the user asks for a 4-step UI plan.
"""


def build_planner_user_prompt(task: str, ctx_chunks: list[dict]) -> str:
    """
    Build a concise user prompt that includes the top RAG context.
    """
    ctx_text = "\n\n".join([f"[{c['title']}] {c['content'][:700]}" for c in ctx_chunks]) or "No context."
    return f"""TASK:
{task}

BRAND KIT CONTEXT:
{ctx_text}

Return ONLY JSON."""
