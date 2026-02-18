import json
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
from .config import settings

# Cache the Bedrock Runtime client. Recreate it if an SSO token expires.
_bedrock_client = None


def get_bedrock_client():
    """
    Create a bedrock-runtime client.

    - Uses boto3.Session(profile_name=...) to support AWS SSO profiles.
    - Uses BEDROCK_REGION (or AWS_REGION fallback) to avoid region mismatches.
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


def _looks_like_token_problem(err: ClientError) -> bool:
    """
    Detect token/SSO expiration issues that are worth retrying once.
    """
    code = err.response.get("Error", {}).get("Code", "") or ""
    msg = err.response.get("Error", {}).get("Message", "") or ""
    msg_l = msg.lower()
    return (
        code in ("UnauthorizedException", "UnrecognizedClientException", "ExpiredTokenException")
        or "token" in msg_l
        or "expired" in msg_l
        or "sso" in msg_l
    )


def nova_embed_text(text: str, dimension: int = 1024) -> list[float]:
    """
    Generate embeddings via Bedrock.

    Default model: amazon.titan-embed-text-v2:0
    Schema:
      { "inputText": "...", "dimensions": 1024|512|256, "normalize": true|false }
    """
    model_id = settings.NOVA_EMBED_MODEL_ID

    dim = int(dimension) if dimension is not None else 1024
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
    except NoCredentialsError as e:
        raise RuntimeError(
            "AWS credentials were not found. If you use SSO, run:\n"
            f"  aws sso login --profile {settings.AWS_PROFILE}\n"
            "Then retry. Also verify:\n"
            f"  aws sts get-caller-identity --profile {settings.AWS_PROFILE}\n"
        ) from e
    except ClientError as e:
        if _looks_like_token_problem(e):
            bedrock = _recreate_client()
            resp = bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                accept="application/json",
                contentType="application/json",
            )
        else:
            code = e.response.get("Error", {}).get("Code", "")
            msg = e.response.get("Error", {}).get("Message", "")
            raise RuntimeError(f"Bedrock invoke_model failed for {model_id}: {code} - {msg}") from e

    payload = json.loads(resp["body"].read())

    # Titan v2 returns {"embedding":[...], ...}
    if "embedding" in payload:
        return payload["embedding"]

    # Fallback shapes (rare)
    if "embeddingsByType" in payload and "float" in payload["embeddingsByType"]:
        return payload["embeddingsByType"]["float"]

    raise RuntimeError(f"Unexpected embedding response from model ({model_id}): {payload}")


def nova_plan_with_lite(system: str, user: str) -> str:
    """
    Planning/chat via Nova 2 Lite using the Bedrock Converse API.
    """
    bedrock = get_bedrock_client()

    try:
        resp = bedrock.converse(
            modelId=settings.NOVA_LITE_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": user}]}],
            system=[{"text": system}],
            inferenceConfig={"maxTokens": 1500, "temperature": 0.2, "topP": 0.9},
        )
    except NoCredentialsError as e:
        raise RuntimeError(
            "AWS credentials were not found. If you use SSO, run:\n"
            f"  aws sso login --profile {settings.AWS_PROFILE}\n"
            "Then retry."
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
            code = e.response.get("Error", {}).get("Code", "")
            msg = e.response.get("Error", {}).get("Message", "")
            raise RuntimeError(f"Bedrock converse failed: {code} - {msg}") from e

    # Typical shape: resp["output"]["message"]["content"][0]["text"]
    try:
        return resp["output"]["message"]["content"][0]["text"]
    except Exception:
        raise RuntimeError(f"Unexpected Converse response shape: {resp}")
