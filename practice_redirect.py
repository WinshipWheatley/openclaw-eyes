"""Practice-mode side-effect redirects for OpenClaw broker benches.

This module is intentionally tiny and fail-closed. It does not perform any
network action; it only rewrites broker params after approval gates have passed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


PRACTICE_SINK_EMAIL = "winshiplive+practice@gmail.com"
EXACT_SEND_PRACTICE_REDIRECTED = "EXACT_SEND_PRACTICE_REDIRECTED"
_EMAIL_CAPABILITIES = {"google.gmail.send", "google.gmail.draft.create"}
_DEFAULT_PROD_TOKEN_PATH = Path("/home/openclaw/.google-secrets/token.json").resolve(strict=False)
_THREADING_KEYS = {
    "thread_id",
    "in_reply_to",
    "references",
    "reply_to",
    "message_id",
    "gmail_message_id",
}


def _env_flag(name: str) -> bool:
    return os.environ.get(name) == "1"


def _active_token_is_not_prod(active_token_path: str | Path | None) -> bool:
    if active_token_path is None:
        return False
    token_path = Path(active_token_path).expanduser()
    try:
        resolved = token_path.resolve(strict=False)
    except OSError:
        resolved = token_path
    if resolved == _DEFAULT_PROD_TOKEN_PATH:
        return False
    return token_path.exists()


def practice_mode_armed(*, active_token_path: str | Path | None = None) -> bool:
    """Return True only for an explicit human bench, never pytest/prod defaults."""
    if not _env_flag("OPENCLAW_PRACTICE_MODE"):
        return False
    if not _env_flag("OPENCLAW_PRACTICE_BENCH"):
        return False
    if os.environ.get("OPENCLAW_TEST_MODE") == "1":
        return False
    if "OPENCLAW_NETWORK_DISABLED" in os.environ:
        return False
    if "OPENCLAW_LIVE_RUNTIME_DISABLED" in os.environ:
        return False
    return _active_token_is_not_prod(active_token_path)


def apply(capability: str, params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return broker params rewritten to the safe sink for supported email caps."""
    original = dict(params or {})
    if capability not in _EMAIL_CAPABILITIES:
        return original

    redirected = dict(original)
    original_to = str(original.get("to", "")).strip()
    original_cc = str(original.get("cc", "")).strip()
    original_bcc = str(original.get("bcc", "")).strip()
    subject = str(original.get("subject", "")).strip()
    if not subject.startswith("[PRACTICE] "):
        subject = f"[PRACTICE] {subject}".strip()

    redirected["to"] = PRACTICE_SINK_EMAIL
    redirected["cc"] = ""
    redirected["bcc"] = ""
    redirected["subject"] = subject
    for key in _THREADING_KEYS:
        redirected.pop(key, None)

    redirected["_practice_redirect"] = {
        "practice_redirect_applied": True,
        "terminal_status": EXACT_SEND_PRACTICE_REDIRECTED,
        "target_redirected_to": PRACTICE_SINK_EMAIL,
        "original_recipient": original_to,
        "original_cc": original_cc,
        "original_bcc": original_bcc,
    }
    return redirected
