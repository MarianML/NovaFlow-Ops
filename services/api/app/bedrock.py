from __future__ import annotations

import hashlib
import json
import math
import random
import re
from typing import Any, Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
    UnauthorizedSSOTokenError,
)

from .config import settings

# Cache the Bedrock Runtime client. Recreate it if an SSO token expires.
_bedrock_client = None


# -----------------------------
# Helpers
# -----------------------------
def _provider() -> str:
    return (settings.NOVA_PROVIDER or "bedrock").strip().lower()


def _aws_login_hint() -> str:
    prof = settings.AWS_PROFILE
    if prof:
        return (
            f"Run:\n"
            f"  aws sso login --profile {prof}\n"
            f"Then verify:\n"
            f"  aws sts get-caller-identity --profile {prof}\n"
        )
    return (
        "Run:\n"
        "  aws sso login\n"
        "Then verify:\n"
        "  aws sts get-caller-identity\n"
    )


def _looks_like_token_problem(err: ClientError) -> bool:
    """
    Detect token/SSO expiration issues that are worth retrying once.
    """
    code = (err.response.get("Error", {}) or {}).get("Code", "") or ""
    msg = (err.response.get("Error", {}) or {}).get("Message", "") or ""
    msg_l = msg.lower()
    return (
        code in ("UnauthorizedException", "UnrecognizedClientException", "ExpiredTokenException")
        or "token" in msg_l
        or "expired" in msg_l
        or "sso" in msg_l
    )


def _safe_json_dumps(obj: Any) -> str:
    # Compact + stable output for planner JSON
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _sanitize_http_url(url: str) -> Optional[str]:
    """
    Accept only http/https absolute URLs. Otherwise return None.
    """
    try:
        p = urlparse(url.strip())
        if p.scheme not in ("http", "https"):
            return None
        if not p.netloc:
            return None
        return url.strip()
    except Exception:
        return None


# -----------------------------
# Bedrock client (real AWS)
# -----------------------------
def get_bedrock_client():
    """
    Create a bedrock-runtime client.

    - Uses boto3.Session(profile_name=...) to support AWS SSO profiles.
    - Uses BEDROCK_REGION to avoid region mismatches.
    """
    global _bedrock_client
    if _bedrock_client is not None:
        return _bedrock_client

    region = settings.BEDROCK_REGION

    try:
        if settings.AWS_PROFILE:
            sess = boto3.Session(profile_name=settings.AWS_PROFILE, region_name=region)
        else:
            sess = boto3.Session(region_name=region)
    except ProfileNotFound as e:
        raise RuntimeError(
            f"AWS profile '{settings.AWS_PROFILE}' was not found. "
            "Run: aws configure list-profiles"
        ) from e

    _bedrock_client = sess.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            read_timeout=3600,
            retries={"max_attempts": 8, "mode": "standard"},
        ),
    )
    return _bedrock_client


def _recreate_client():
    """
    Drop cached client and create a fresh one (useful after SSO refresh).
    """
    global _bedrock_client
    _bedrock_client = None
    return get_bedrock_client()


# -----------------------------
# Mock Mode (no AWS)
# -----------------------------
def _mock_embed_text(text: str, dimension: int = 1024) -> list[float]:
    """
    Deterministic local embedding (no ML, no downloads, no AWS).
    Produces a stable, normalized vector for the same text.

    Perfect for hackathon demos / judges without credentials.
    """
    dim = int(dimension) if dimension is not None else 1024
    if dim <= 0:
        raise ValueError("dimension must be > 0")

    # Stable seed from hash(text + dim)
    h = hashlib.sha256((f"{dim}::" + (text or "")).encode("utf-8")).digest()
    seed = int.from_bytes(h[:8], "big", signed=False)
    rng = random.Random(seed)

    vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _extract_task_from_prompt(user: str) -> str:
    """
    Your planner user prompt typically looks like:

    TASK:
    <task>

    BRAND KIT CONTEXT:
    <ctx>
    """
    if not user:
        return ""
    m = re.search(
        r"TASK:\s*(.*?)\s*\n\s*\nBRAND KIT CONTEXT:",
        user,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if m:
        return (m.group(1) or "").strip()
    return user.strip()


def _find_first_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(https?://[^\s\"\'\)\]]+)", text)
    if not m:
        return None
    return _sanitize_http_url(m.group(1))


def _mock_plan(system: str, user: str) -> str:
    """
    Deterministic planner that returns ONLY JSON (string),
    following schema:
      { starting_url, steps: [ {id,type,instruction,requires_approval,evidence}, ... ] }

    Supported Runner DSL actions:
      CLICK_TEXT, CLICK_ID, CLICK_CSS, TYPE_ID,
      WAIT_TEXT, ASSERT_TEXT, WAIT_URL_CONTAINS, WAIT_MS, SCREENSHOT
    """
    task = _extract_task_from_prompt(user)
    task_l = task.lower()

    # Default starting URL for demos
    starting_url = settings.DEMO_STARTING_URL or "https://the-internet.herokuapp.com/"
    starting_url = _sanitize_http_url(starting_url) or "https://the-internet.herokuapp.com/"

    # If task contains a URL, use it (but only if it's valid http/https)
    url_in_task = _find_first_url(task)
    if url_in_task:
        starting_url = url_in_task

    # Special-case: "Form Authentication" demo
    if ("form authentication" in task_l) or ("tomsmith" in task_l) or ("supersecretpassword" in task_l):
        plan = {
            "starting_url": "https://the-internet.herokuapp.com/",
            "steps": [
                {
                    "id": "S1",
                    "type": "ui",
                    "instruction": "CLICK_TEXT: Form Authentication",
                    "requires_approval": False,
                    "evidence": "Navigated to Form Authentication page",
                },
                {
                    "id": "S2",
                    "type": "ui",
                    "instruction": "TYPE_ID: username=tomsmith",
                    "requires_approval": False,
                    "evidence": "Entered username",
                },
                {
                    "id": "S3",
                    "type": "ui",
                    "instruction": "TYPE_ID: password=SuperSecretPassword!",
                    "requires_approval": False,
                    "evidence": "Entered password",
                },
                {
                    "id": "S4",
                    "type": "ui",
                    "instruction": "CLICK_CSS: button[type=\"submit\"]",
                    "requires_approval": False,
                    "evidence": "Submitted login form",
                },
                {
                    "id": "S5",
                    "type": "ui",
                    "instruction": "WAIT_TEXT: You logged into a secure area!",
                    "requires_approval": False,
                    "evidence": "Verified successful login",
                },
                {
                    "id": "S6",
                    "type": "ui",
                    "instruction": "SCREENSHOT: after_login",
                    "requires_approval": False,
                    "evidence": "Captured post-login screen",
                },
            ],
        }
        return _safe_json_dumps(plan)

    # Generic fallback: prove page loaded + evidence screenshots
    host = urlparse(starting_url).netloc or "the-internet.herokuapp.com"

    plan = {
        "starting_url": starting_url,
        "steps": [
            {
                "id": "S1",
                "type": "ui",
                "instruction": f"WAIT_URL_CONTAINS: {host}",
                "requires_approval": False,
                "evidence": "Page loaded (URL contains expected host)",
            },
            {
                "id": "S2",
                "type": "ui",
                "instruction": "SCREENSHOT: landing",
                "requires_approval": False,
                "evidence": "Captured landing page screenshot",
            },
            {
                "id": "S3",
                "type": "ui",
                "instruction": "WAIT_MS: 500",
                "requires_approval": False,
                "evidence": "Brief wait for stability",
            },
            {
                "id": "S4",
                "type": "ui",
                "instruction": "SCREENSHOT: landing_2",
                "requires_approval": False,
                "evidence": "Captured a second screenshot for evidence",
            },
        ],
    }
    return _safe_json_dumps(plan)


# -----------------------------
# Public API used by the rest of the app
# -----------------------------
def nova_embed_text(text: str, dimension: int = 1024) -> list[float]:
    """
    Generate embeddings.

    - bedrock: uses Titan Text Embeddings v2 (by default)
    - mock: deterministic local embedding, no AWS
    """
    prov = _provider()
    if prov == "mock":
        return _mock_embed_text(text, dimension)
    if prov != "bedrock":
        raise RuntimeError(f"Unknown NOVA_PROVIDER='{settings.NOVA_PROVIDER}'. Use 'bedrock' or 'mock'.")

    # --- Bedrock mode ---
    model_id = settings.NOVA_EMBED_MODEL_ID
    dim = int(dimension) if dimension is not None else 1024

    # Only enforce Titan v2 dimension rules if it looks like Titan v2
    if "titan-embed-text-v2" in (model_id or "").lower():
        if dim not in (1024, 512, 256):
            raise ValueError("For amazon.titan-embed-text-v2:0, dimensions must be 1024, 512, or 256.")

    body = {"inputText": text, "dimensions": dim, "normalize": True}
    bedrock = get_bedrock_client()

    try:
        resp = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
    except (UnauthorizedSSOTokenError, NoCredentialsError) as e:
        raise RuntimeError(
            "AWS credentials/SSO token not found or expired.\n" + _aws_login_hint()
        ) from e
    except ClientError as e:
        if _looks_like_token_problem(e):
            # Retry once with fresh client (useful after quick re-auth)
            bedrock = _recreate_client()
            resp = bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                accept="application/json",
                contentType="application/json",
            )
        else:
            code = (e.response.get("Error", {}) or {}).get("Code", "")
            msg = (e.response.get("Error", {}) or {}).get("Message", "")
            raise RuntimeError(f"Bedrock invoke_model failed for {model_id}: {code} - {msg}") from e

    raw = resp["body"].read()
    payload = json.loads(raw)

    if "embedding" in payload:
        return payload["embedding"]

    if "embeddingsByType" in payload and "float" in payload["embeddingsByType"]:
        return payload["embeddingsByType"]["float"]

    raise RuntimeError(f"Unexpected embedding response from model ({model_id}): {payload}")


def nova_plan_with_lite(system: str, user: str) -> str:
    """
    Planning/chat.

    - bedrock: Nova 2 Lite via Bedrock Converse API
    - mock: deterministic planner that returns ONLY JSON
    """
    prov = _provider()
    if prov == "mock":
        return _mock_plan(system, user)
    if prov != "bedrock":
        raise RuntimeError(f"Unknown NOVA_PROVIDER='{settings.NOVA_PROVIDER}'. Use 'bedrock' or 'mock'.")

    bedrock = get_bedrock_client()

    try:
        resp = bedrock.converse(
            modelId=settings.NOVA_LITE_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": user}]}],
            system=[{"text": system}],
            inferenceConfig={"maxTokens": 1500, "temperature": 0.2, "topP": 0.9},
        )
    except (UnauthorizedSSOTokenError, NoCredentialsError) as e:
        raise RuntimeError(
            "AWS credentials/SSO token not found or expired.\n" + _aws_login_hint()
        ) from e
    except ClientError as e:
        if _looks_like_token_problem(e):
            bedrock = _recreate_client()
            resp = bedrock.converse(
                modelId=settings.NOVA_LITE_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": user}]}],
                system=[{"text": system}],
                inferenceConfig={"maxTokens": 1500, "temperature": 0.2, "topP": 0.9},
            )
        else:
            code = (e.response.get("Error", {}) or {}).get("Code", "")
            msg = (e.response.get("Error", {}) or {}).get("Message", "")
            raise RuntimeError(f"Bedrock converse failed: {code} - {msg}") from e

    try:
        return resp["output"]["message"]["content"][0]["text"]
    except Exception as e:
        raise RuntimeError(f"Unexpected Converse response shape: {resp}") from e
