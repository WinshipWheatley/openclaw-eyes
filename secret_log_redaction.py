"""Reusable token redaction helpers for logs and sender error paths."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable


_TELEGRAM_BOT_URL_RE = re.compile(
    r"\bbot(?P<digits>\d{8,10}):(?P<secret>AA[\w-]{30,}|[A-Za-z0-9_-]{20,})"
)
_TELEGRAM_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<digits>\d{8,10}):AA[\w-]{30,}"
)
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{7,}\b")
_GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{16,}\b")
_GITHUB_PAT_RE = re.compile(r"\bghp_[0-9A-Za-z_]{20,}\b")

_Replacement = str | Callable[[re.Match[str]], str]


def _telegram_url_replacement(match: re.Match[str]) -> str:
    return f"bot{match.group('digits')}:[REDACTED]"


def _telegram_token_replacement(match: re.Match[str]) -> str:
    return f"{match.group('digits')}:[REDACTED]"


_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], _Replacement], ...] = (
    (_TELEGRAM_BOT_URL_RE, _telegram_url_replacement),
    (_TELEGRAM_TOKEN_RE, _telegram_token_replacement),
    (_OPENAI_KEY_RE, "<REDACTED>"),
    (_GOOGLE_API_KEY_RE, "<REDACTED>"),
    (_GITHUB_PAT_RE, "<REDACTED>"),
)


def _redact_with_count(text: str) -> tuple[str, int]:
    redacted = str(text)
    count = 0
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted, replacements = pattern.subn(replacement, redacted)
        count += replacements
    return redacted, count


def redact_secrets(text: str) -> str:
    """Return ``text`` with token-shaped secrets replaced by redaction markers."""

    redacted, _count = _redact_with_count(text)
    return redacted


def scrub_log_file(path: str | os.PathLike[str]) -> int:
    """Rewrite ``path`` in place with token-shaped strings redacted.

    Returns the number of replacements made. This helper is intended for
    post-crash cleanup paths, so it never raises.
    """

    try:
        log_path = Path(path)
        original = log_path.read_text(encoding="utf-8", errors="replace")
        redacted, count = _redact_with_count(original)
        if count:
            log_path.write_text(redacted, encoding="utf-8")
        return count
    except Exception:
        return 0
