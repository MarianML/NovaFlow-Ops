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
    # mock: no AWS required, deterministic behavior for demos
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
    # Embeddings: Titan (RAG retrieval)
    NOVA_EMBED_MODEL_ID: str = _env(
        "NOVA_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"
    ) or "amazon.titan-embed-text-v2:0"

    # Planner: Nova 2 Lite (reasoning + plan)
    NOVA_LITE_MODEL_ID: str = _env(
        "NOVA_LITE_MODEL_ID", "amazon.nova-2-lite-v1:0"
    ) or "amazon.nova-2-lite-v1:0"

    # Optional: inference profile ARN/ID for Nova if required by your account/region.
    NOVA_INFERENCE_PROFILE_ID: str | None = _env("NOVA_INFERENCE_PROFILE_ID")

    # ---- Database URLs (common aliases) ----
    DATABASE_URL: str | None = _env("DATABASE_URL")
    DB_URL: str | None = _env("DB_URL")
    SQLALCHEMY_DATABASE_URI: str | None = _env("SQLALCHEMY_DATABASE_URI")

    # ---- Demo / misc ----
    DEMO_STARTING_URL: str = _env(
        "DEMO_STARTING_URL", "https://the-internet.herokuapp.com/"
    ) or "https://the-internet.herokuapp.com/"

    PLAYWRIGHT_HEADLESS: bool = _env_bool("PLAYWRIGHT_HEADLESS", default=True)

    # ---- Starting URL policy ----
    # demo: always use DEMO_STARTING_URL
    # plan: use planner's starting_url only if host is in allowlist
    # any_public: accept any public http/https URL (blocks localhost/private IPs in server logic)
    STARTING_URL_MODE: str = (_env("STARTING_URL_MODE", "demo") or "demo").strip().lower()

    # Comma-separated allowlist of hostnames (used when STARTING_URL_MODE=plan)
    ALLOWED_STARTING_HOSTS: str = _env(
        "ALLOWED_STARTING_HOSTS",
        "the-internet.herokuapp.com",
    ) or "the-internet.herokuapp.com"

    # ---- Optional DNS SSRF protection ----
    # If enabled, hostnames will be DNS-resolved and blocked if they resolve to private/loopback/link-local IPs.
    ENABLE_DNS_SSRF_PROTECTION: bool = _env_bool("ENABLE_DNS_SSRF_PROTECTION", default=False)

    # DNS resolve timeout (seconds)
    DNS_RESOLVE_TIMEOUT_S: float = float(_env("DNS_RESOLVE_TIMEOUT_S", "1.5") or "1.5")

    @property
    def ALLOWED_STARTING_HOSTS_LIST(self) -> list[str]:
        return [h.strip().lower() for h in (self.ALLOWED_STARTING_HOSTS or "").split(",") if h.strip()]

    # ---- CORS ----
    CORS_ORIGINS: str = _env("CORS_ORIGINS", "http://localhost:3000") or "http://localhost:3000"

    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        return [o.strip() for o in (self.CORS_ORIGINS or "").split(",") if o.strip()]

    @property
    def EFFECTIVE_DATABASE_URL(self) -> str | None:
        return self.DATABASE_URL or self.DB_URL or self.SQLALCHEMY_DATABASE_URI

    def validate(self) -> None:
        if self.NOVA_PROVIDER not in ("bedrock", "mock"):
            raise RuntimeError("NOVA_PROVIDER must be 'bedrock' or 'mock'.")

        if not self.EFFECTIVE_DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured. Set DATABASE_URL to a PostgreSQL asyncpg URL.")

        if self.STARTING_URL_MODE not in ("demo", "plan", "any_public"):
            raise RuntimeError("STARTING_URL_MODE must be one of: demo, plan, any_public.")

        if self.STARTING_URL_MODE == "plan" and not self.ALLOWED_STARTING_HOSTS_LIST:
            raise RuntimeError("ALLOWED_STARTING_HOSTS must not be empty when STARTING_URL_MODE=plan.")

        if self.DNS_RESOLVE_TIMEOUT_S <= 0:
            raise RuntimeError("DNS_RESOLVE_TIMEOUT_S must be > 0.")

        if self.NOVA_PROVIDER == "bedrock":
            if not self.BEDROCK_REGION:
                raise RuntimeError("BEDROCK_REGION is not configured.")
            if not self.NOVA_EMBED_MODEL_ID:
                raise RuntimeError("NOVA_EMBED_MODEL_ID is not configured.")
            if not self.NOVA_LITE_MODEL_ID and not self.NOVA_INFERENCE_PROFILE_ID:
                raise RuntimeError("NOVA_LITE_MODEL_ID (or NOVA_INFERENCE_PROFILE_ID) is not configured.")


settings = Settings()

# Ensure boto3 loads AWS config/credentials from shared config files (required for many SSO setups).
os.environ.setdefault("AWS_SDK_LOAD_CONFIG", settings.AWS_SDK_LOAD_CONFIG)
os.environ.setdefault("AWS_REGION", settings.AWS_REGION)
os.environ.setdefault("AWS_DEFAULT_REGION", settings.AWS_DEFAULT_REGION)
os.environ.setdefault("BEDROCK_REGION", settings.BEDROCK_REGION)