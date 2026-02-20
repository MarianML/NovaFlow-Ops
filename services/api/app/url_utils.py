from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse


def sanitize_http_url(url: str | None) -> Optional[str]:
    """
    Accept only absolute http/https URLs with a hostname.
    Returns normalized string or None.
    """
    if not url:
        return None
    s = url.strip()
    if not s:
        return None

    try:
        p = urlparse(s)
    except Exception:
        return None

    if p.scheme not in ("http", "https"):
        return None
    if not p.netloc:
        return None

    return s
