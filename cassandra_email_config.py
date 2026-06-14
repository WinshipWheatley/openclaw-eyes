"""Safe Cassandra email configuration.

This module stores no secrets. It reads non-secret routing values from the
process environment first, then from a local `.chief.env` style file if present,
and finally falls back to a safe operator review inbox.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


DEFAULT_REVIEW_INBOX = "winshiplive@gmail.com"
ENV_KEYS = (
    "CASSANDRA_EMAIL_REVIEW_INBOX",
    "OPENCLAW_REVIEW_INBOX",
    "OPENCLAW_OPERATOR_EMAIL",
)
DEFAULT_ENV_PATH = Path(".chief.env")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_value(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    if not _EMAIL_RE.match(text):
        return None
    return text


def _read_env_file_value(path: str | Path, keys: tuple[str, ...] = ENV_KEYS) -> str | None:
    env_path = Path(path)
    if not env_path.exists() or not env_path.is_file():
        return None
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    wanted = set(keys)
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        key, value = stripped.split("=", 1)
        if key.strip() in wanted:
            cleaned = _clean_value(value)
            if cleaned:
                return cleaned
    return None


def get_review_inbox(env_path: str | Path = DEFAULT_ENV_PATH) -> str:
    """Return Cassandra's review inbox without exposing credential values."""

    for key in ENV_KEYS:
        cleaned = _clean_value(os.environ.get(key))
        if cleaned:
            return cleaned
    return _read_env_file_value(env_path) or DEFAULT_REVIEW_INBOX


__all__ = [
    "DEFAULT_REVIEW_INBOX",
    "ENV_KEYS",
    "get_review_inbox",
]
