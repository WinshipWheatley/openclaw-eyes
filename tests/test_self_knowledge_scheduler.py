from __future__ import annotations

import sys
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polish_loop.gpu_arbiter import GPUArbiter  # noqa: E402
from self_knowledge_scheduler import run_scheduled_crawl  # noqa: E402
from self_knowledge_ledger_gap_writer import ACTIVATION_TABLE, GRAPH_NODE_TABLE  # noqa: E402


def _t(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _make_tree(root: Path) -> None:
    root.mkdir()
    (root / "a.py").write_text("# a\n")
    (root / "b.py").write_text("# b\n")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_git_tree(root: Path) -> None:
    _make_tree(root)
    _git(root, "init")
    _git(root, "config", "user.email", "codex@example.test")
    _git(root, "config", "user.name", "Codex Test")
    _git(root, "checkout", "-b", "main")
    _git(root, "add", "a.py", "b.py")
    _git(root, "commit", "-m", "init")


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


def test_scheduled_crawl_can_confirm_write_gap_rows_to_injected_ledger(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    lease_db = tmp_path / "leases.sqlite"
    state_db = tmp_path / "state.sqlite"
    ledger = tmp_path / "ledger.sqlite"
    with sqlite3.connect(ledger) as conn:
        conn.execute("CREATE TABLE file_inventory (path TEXT)")

    result = run_scheduled_crawl(
        root,
        lease_db_path=lease_db,
        state_db_path=state_db,
        ledger_path=ledger,
        confirm_ledger_write=True,
        now=_t("2026-07-01T12:00:00"),
    )

    assert result["status"] == "completed"
    assert result["ledger_gap_write"]["status"] == "written"
    assert result["activation_record"]["ledger_write_confirmed"] is True
    with sqlite3.connect(ledger) as conn:
        rows = conn.execute(
            "SELECT subject FROM knowledge_sysknow_known_unknown ORDER BY subject"
        ).fetchall()
    assert [row[0] for row in rows] == ["a.py", "b.py"]


def test_scheduled_crawl_can_confirm_write_graph_and_activation_rows_to_injected_ledger(tmp_path):
    root = tmp_path / "repo"
    _make_git_tree(root)
    lease_db = tmp_path / "leases.sqlite"
    state_db = tmp_path / "state.sqlite"
    ledger = tmp_path / "ledger.sqlite"
    with sqlite3.connect(ledger) as conn:
        conn.execute("CREATE TABLE file_inventory (path TEXT)")

    result = run_scheduled_crawl(
        root,
        lease_db_path=lease_db,
        state_db_path=state_db,
        ledger_path=ledger,
        confirm_ledger_write=True,
        write_inventory_graph=True,
        write_activation_record=True,
        owner_scope="pc",
        now=_t("2026-07-01T12:00:00"),
    )

    assert result["status"] == "completed"
    assert result["ledger_gap_write"]["status"] == "written"
    assert result["inventory_graph_write"]["status"] == "written"
    assert result["activation_record_write"]["status"] == "written"
    assert result["activation_record"]["ledger_write_confirmed"] is True
    assert result["activation_record"]["inventory_graph_write_confirmed"] is True

    with sqlite3.connect(ledger) as conn:
        node_kinds = {
            row[0]
            for row in conn.execute(f'SELECT kind FROM "{GRAPH_NODE_TABLE}"')
        }
        activation_rows = conn.execute(
            f'SELECT activation_state, ledger_write_confirmed, inventory_graph_write_confirmed '
            f'FROM "{ACTIVATION_TABLE}"'
        ).fetchall()

    assert {"machine", "repo", "worktree", "openclaw_instance"} <= node_kinds
    assert activation_rows == [("invoked", 1, 1)]


def _state_row_count(state_db: Path) -> int:
    import sqlite3

    with sqlite3.connect(state_db) as conn:
        try:
            return conn.execute("SELECT COUNT(*) FROM crawl_directory_state").fetchone()[0]
        except sqlite3.OperationalError:
            return 0
