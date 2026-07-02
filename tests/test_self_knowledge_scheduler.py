from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polish_loop.gpu_arbiter import GPUArbiter  # noqa: E402
from self_knowledge_scheduler import run_scheduled_crawl  # noqa: E402


def _t(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _make_tree(root: Path) -> None:
    root.mkdir()
    (root / "a.py").write_text("# a\n")
    (root / "b.py").write_text("# b\n")


def test_runs_crawl_when_no_lease_present(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    lease_db = tmp_path / "leases.sqlite"
    state_db = tmp_path / "state.sqlite"

    result = run_scheduled_crawl(
        root, lease_db_path=lease_db, state_db_path=state_db, now=_t("2026-07-01T12:00:00")
    )

    assert result["status"] == "completed"
    assert result["files_visited"] == 2


def test_defers_when_interactive_lease_is_active(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    lease_db = tmp_path / "leases.sqlite"
    state_db = tmp_path / "state.sqlite"

    arbiter = GPUArbiter(lease_db)
    arbiter.acquire("interactive", "maestro", now=_t("2026-07-01T12:00:00"), ttl_seconds=900)

    result = run_scheduled_crawl(
        root, lease_db_path=lease_db, state_db_path=state_db, now=_t("2026-07-01T12:05:00")
    )

    assert result == {
        "status": "deferred",
        "reason": "interactive_lease_active",
    }
    # The crawl must NOT have run: no state rows recorded.
    assert not state_db.exists() or _state_row_count(state_db) == 0


def test_runs_crawl_when_lease_is_expired(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    lease_db = tmp_path / "leases.sqlite"
    state_db = tmp_path / "state.sqlite"

    arbiter = GPUArbiter(lease_db)
    arbiter.acquire("interactive", "maestro", now=_t("2026-07-01T12:00:00"), ttl_seconds=60)

    # Well past expiry.
    result = run_scheduled_crawl(
        root, lease_db_path=lease_db, state_db_path=state_db, now=_t("2026-07-01T13:00:00")
    )

    assert result["status"] == "completed"
    assert result["files_visited"] == 2


def test_runs_crawl_when_lease_is_build_not_interactive(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    lease_db = tmp_path / "leases.sqlite"
    state_db = tmp_path / "state.sqlite"

    arbiter = GPUArbiter(lease_db)
    arbiter.acquire("build", "polish-loop-builder", now=_t("2026-07-01T12:00:00"), ttl_seconds=900)

    result = run_scheduled_crawl(
        root, lease_db_path=lease_db, state_db_path=state_db, now=_t("2026-07-01T12:05:00")
    )

    assert result["status"] == "completed"
    assert result["files_visited"] == 2


def test_second_run_is_incremental(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    lease_db = tmp_path / "leases.sqlite"
    state_db = tmp_path / "state.sqlite"

    first = run_scheduled_crawl(
        root, lease_db_path=lease_db, state_db_path=state_db, now=_t("2026-07-01T12:00:00")
    )
    assert first["files_visited"] == 2

    second = run_scheduled_crawl(
        root, lease_db_path=lease_db, state_db_path=state_db, now=_t("2026-07-01T12:05:00")
    )
    assert second["status"] == "completed"
    assert second["files_visited"] == 0


def _state_row_count(state_db: Path) -> int:
    import sqlite3

    with sqlite3.connect(state_db) as conn:
        try:
            return conn.execute("SELECT COUNT(*) FROM crawl_directory_state").fetchone()[0]
        except sqlite3.OperationalError:
            return 0
