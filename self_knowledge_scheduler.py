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
    ledger_path: str | Path | None = None,
    confirm_ledger_write: bool = False,
    write_inventory_graph: bool = False,
    write_activation_record: bool = False,
    owner_scope: str = "pc",
) -> dict[str, Any]:
    """Defer honestly while an interactive GPU lease is active; otherwise run
    a bounded incremental crawl and report how many files were (re)visited.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)

    if _interactive_lease_active(lease_db_path, now):
        return {"status": "deferred", "reason": "interactive_lease_active"}

    crumbs = crawl_filesystem_incremental(root, state_db_path, max_files=max_files)
    result: dict[str, Any] = {
        "status": "completed",
        "root": str(Path(root).resolve()),
        "files_visited": len(crumbs),
        "activation_record": {
            "activation_ref": f"self_knowledge_scheduled_crawl:{Path(root).resolve()}",
            "activation_state": "invoked",
            "root": str(Path(root).resolve()),
            "scheduled_runtime_installed_by_this_call": False,
            "ledger_path": str(Path(ledger_path).resolve()) if ledger_path is not None else None,
            "ledger_write_confirm_requested": bool(confirm_ledger_write),
            "ledger_write_confirmed": False,
            "inventory_graph_write_confirmed": False,
            "last_verified_at": now.isoformat(),
        },
    }
    if ledger_path is not None:
        from self_knowledge_ledger_gap_writer import (
            write_activation_record_to_ledger,
            write_gaps_to_ledger,
            write_inventory_graph_to_ledger,
        )

        ledger_result = write_gaps_to_ledger(
            root,
            ledger_path,
            confirm=confirm_ledger_write,
            max_files=max_files,
        )
        result["ledger_gap_write"] = ledger_result
        result["activation_record"]["ledger_write_confirmed"] = (
            confirm_ledger_write and ledger_result.get("status") == "written"
        )
        if write_inventory_graph:
            from self_knowledge_system_enumerators import enumerate_system_state

            system_state = enumerate_system_state(
                timeout=10,
                repo_root=root,
                roots=[root],
                owner_scope=owner_scope,
            )
            graph_result = write_inventory_graph_to_ledger(
                system_state["inventory_graph"],
                ledger_path,
                confirm=confirm_ledger_write,
            )
            result["inventory_graph_write"] = graph_result
            result["activation_record"]["inventory_graph_write_confirmed"] = (
                confirm_ledger_write and graph_result.get("status") == "written"
            )
        if write_activation_record:
            activation_result = write_activation_record_to_ledger(
                result["activation_record"],
                ledger_path,
                confirm=confirm_ledger_write,
            )
            result["activation_record_write"] = activation_result
    elif write_activation_record:
        result["activation_record_write"] = {
            "status": "ledger_path_required",
            "reason": "write_activation_record requires ledger_path",
        }
    return result


__all__ = ["run_scheduled_crawl"]
