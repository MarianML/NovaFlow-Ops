from __future__ import annotations
import subprocess
import sys


def install(*args, **kwargs) -> None:
    """
    Windows shim: Nova Act sometimes tries to import install_playwright.
    We keep this file to avoid import errors and to allow an idempotent install.
    """
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
