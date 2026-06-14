"""Repository-level pytest collection and isolation rules."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import unquote

# Archived planning docs contain copied historical test files with names that
# collide with canonical tests under ./tests. Keep full-suite collection on live
# tests and ignore docs as artifacts.
collect_ignore = ["test_effect_adapters.py"]
collect_ignore_glob = ["docs/**"]


_REPO_ROOT = Path(__file__).resolve().parent
_ISOLATED_ROOT = _REPO_ROOT / ".pytest_openclaw"
_ISOLATED_LEDGER = _REPO_ROOT / ".pytest_openclaw" / "business_ops" / "ledger.sqlite"
_ISOLATED_EXPENSE_LOG = _ISOLATED_ROOT / "logs" / "expense_log.json"
_ISOLATED_GOOGLE_TOKEN = _ISOLATED_ROOT / "secrets" / "token.json"
_LIVE_BUSINESS_LEDGER = Path("/home/openclaw/.openclaw/business_ops/ledger.sqlite").resolve(strict=False)

os.environ.setdefault("OPENCLAW_LEDGER_PATH", str(_ISOLATED_LEDGER))
os.environ.setdefault("OPENCLAW_EXPENSE_LOG_PATH", str(_ISOLATED_EXPENSE_LOG))
os.environ.setdefault("OPENCLAW_GOOGLE_TOKEN_FILE", str(_ISOLATED_GOOGLE_TOKEN))
os.environ.setdefault("OPENCLAW_TEST_MODE", "1")
os.environ.setdefault("OPENCLAW_SEND_HOLD", "1")
os.environ.setdefault("PII_VAULT_KEY", "pytest-local-placeholder")

_ISOLATED_EXPENSE_LOG.parent.mkdir(parents=True, exist_ok=True)
_ISOLATED_GOOGLE_TOKEN.parent.mkdir(parents=True, exist_ok=True)
if not _ISOLATED_EXPENSE_LOG.exists():
    _ISOLATED_EXPENSE_LOG.write_text("[]\n", encoding="utf-8")
if not _ISOLATED_GOOGLE_TOKEN.exists():
    _ISOLATED_GOOGLE_TOKEN.write_text("{}\n", encoding="utf-8")

_ORIGINAL_SQLITE_CONNECT = sqlite3.connect


def _path_from_sqlite_database_arg(database: object) -> Path | None:
    if database in (":memory:", b":memory:"):
        return None
    try:
        raw = os.fspath(database)  # type: ignore[arg-type]
    except TypeError:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    value = str(raw)
    if not value or value == ":memory:":
        return None
    if value.startswith("file:"):
        value = value[5:].split("?", 1)[0]
        value = unquote(value)
    try:
        return Path(value).expanduser().resolve(strict=False)
    except OSError:
        return None


def _guarded_sqlite_connect(database: object, *args: object, **kwargs: object):
    target = _path_from_sqlite_database_arg(database)
    if target == _LIVE_BUSINESS_LEDGER:
        raise RuntimeError(
            "pytest attempted to open the live business-ops ledger; "
            f"use OPENCLAW_LEDGER_PATH instead: {_LIVE_BUSINESS_LEDGER}"
        )
    return _ORIGINAL_SQLITE_CONNECT(database, *args, **kwargs)


sqlite3.connect = _guarded_sqlite_connect
