import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# ------------------------------------------------------------
# Load .env reliably (works no matter where you run uvicorn from)
# services/api/app/config.py -> parents[1] == services/api
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # -> .../services/api
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


def _env(key: str, default: str | None = None) -> str | None:
    """
    Read an environment variable and treat empty strings as missing.
    """
    v = os.getenv(key)
    return v if v not in (None, "") else default


def _env_bool(key: str, default: bool = False) -> bool:
    """
    Parse a boolean env var (1/true/yes/on).
    """
    v = (_env(key) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # ---- Provider selection ----
    # bedrock: real AWS Bedrock (Titan embeddings + Nova planner)
    # mock: no AWS required, deterministic behavior for demos/judges
    NOVA_PROVIDER: str = (_env("NOVA_PROVIDER", "bedrock") or "bedrock").strip().lower()

    # ---- AWS / Bedrock ----
    AWS_REGION: str = _env("AWS_REGION", _env("AWS_DEFAULT_REGION", "eu-north-1")) or "eu-north-1"
    AWS_DEFAULT_REGION: str = _env("AWS_DEFAULT_REGION", "eu-north-1") or "eu-north-1"

    # If set, prefer it for the Bedrock runtime client region.
    BEDROCK_REGION: str = _env("BEDROCK_REGION") or (
        _env("AWS_REGION") or _env("AWS_DEFAULT_REGION") or "eu-north-1"
    )

    AWS_PROFILE: str | None = _env("AWS_PROFILE")
    AWS_SDK_LOAD_CONFIG: str = _env("AWS_SDK_LOAD_CONFIG", "1") or "1"

    # ---- Bedrock model IDs ----
    # Embeddings: Titan Text Embeddings v2 is widely available and supports 1024/512/256 dims.
    NOVA_EMBED_MODEL_ID: str = _env(
        "NOVA_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"
    ) or "amazon.titan-embed-text-v2:0"

    # Planner/chat: Nova 2 Lite (region-agnostic model id).
    # NOTE: sometimes accounts use region-prefixed ids like eu.amazon...
    NOVA_LITE_MODEL_ID: str = _env(
        "NOVA_LITE_MODEL_ID", "amazon.nova-2-lite-v1:0"
    ) or "amazon.nova-2-lite-v1:0"

    # ---- Database URLs (common aliases) ----
    DATABASE_URL: str | None = _env("DATABASE_URL")
    DB_URL: str | None = _env("DB_URL")
    SQLALCHEMY_DATABASE_URI: str | None = _env("SQLALCHEMY_DATABASE_URI")

    # ---- Demo / misc ----
    DEMO_STARTING_URL: str = _env(
        "DEMO_STARTING_URL", "https://the-internet.herokuapp.com/"
    ) or "https://the-internet.herokuapp.com/"
    PLAYWRIGHT_HEADLESS: bool = _env_bool("PLAYWRIGHT_HEADLESS", default=True)

    @property
    def EFFECTIVE_DATABASE_URL(self) -> str | None:
        """
        Choose the first available DB URL among common environment variable names.
        """
        return self.DATABASE_URL or self.DB_URL or self.SQLALCHEMY_DATABASE_URI

    def validate(self) -> None:
        """
        Validate critical configuration.

        - Always requires DATABASE_URL (we store runs/logs/docs).
        - Only requires AWS profile/model config sanity when provider=bedrock.
        """
        if self.NOVA_PROVIDER not in ("bedrock", "mock"):
            raise RuntimeError("NOVA_PROVIDER must be 'bedrock' or 'mock'.")

        if not self.EFFECTIVE_DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not configured. Set DATABASE_URL to a PostgreSQL asyncpg URL."
            )

        # Bedrock-specific checks
        if self.NOVA_PROVIDER == "bedrock":
            # Not strictly required (could use env creds), but helpful for SSO setups.
            # If you want to allow non-profile usage, you can remove this check.
            if not self.BEDROCK_REGION:
                raise RuntimeError("BEDROCK_REGION is not configured.")

            if not self.NOVA_EMBED_MODEL_ID:
                raise RuntimeError("NOVA_EMBED_MODEL_ID is not configured.")

            if not self.NOVA_LITE_MODEL_ID:
                raise RuntimeError("NOVA_LITE_MODEL_ID is not configured.")


# Single settings instance (import this everywhere)
settings = Settings()

# Ensure boto3 loads AWS config/credentials from shared config files (required for many SSO setups).
# Setting these in mock mode doesn't hurt, but you can conditionally set them if you want.
os.environ.setdefault("AWS_SDK_LOAD_CONFIG", settings.AWS_SDK_LOAD_CONFIG)
os.environ.setdefault("AWS_REGION", settings.AWS_REGION)
os.environ.setdefault("AWS_DEFAULT_REGION", settings.AWS_DEFAULT_REGION)
os.environ.setdefault("BEDROCK_REGION", settings.BEDROCK_REGION)
