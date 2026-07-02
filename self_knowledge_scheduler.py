"""Arbiter-aware scheduling entry point for the perpetual self-knowledge engine.

`run_scheduled_crawl()` is the hook a cron/systemd timer calls. It never
starts a daemon and never fights the interactive session for the local GPU:
it only reads the current lease via `polish_loop.gpu_arbiter.GPUArbiter`
(imported, not modified — that primitive belongs to a different workstream)
and honestly defers when an interactive lease is active, otherwise it runs a
bounded incremental crawl via `self_knowledge_crawl_state`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polish_loop.gpu_arbiter import GPUArbiter
from self_knowledge_crawl_state import DEFAULT_STATE_DB, crawl_filesystem_incremental


def _parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _interactive_lease_active(lease_db_path: str | Path, now: datetime) -> bool:
    try:
        lease = GPUArbiter(lease_db_path).current()
    except Exception:
        # Fail open on arbiter read errors: an unreadable lease store must
        # not permanently block the self-knowledge crawl from ever running.
        return False
    if not lease:
        return False
    if str(lease.get("holder_type")) != "interactive":
        return False
    expires_at = _parse_iso(lease.get("expires_at"))
    if expires_at is not None and expires_at <= now:
        return False  # expired lease: no longer active
    return True


def run_scheduled_crawl(
    root: str | Path,
    *,
    lease_db_path: str | Path,
    state_db_path: str | Path = DEFAULT_STATE_DB,
    max_files: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Defer honestly while an interactive GPU lease is active; otherwise run
    a bounded incremental crawl and report how many files were (re)visited.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)

    if _interactive_lease_active(lease_db_path, now):
        return {"status": "deferred", "reason": "interactive_lease_active"}

    crumbs = crawl_filesystem_incremental(root, state_db_path, max_files=max_files)
    return {
        "status": "completed",
        "root": str(Path(root).resolve()),
        "files_visited": len(crumbs),
    }


__all__ = ["run_scheduled_crawl"]
