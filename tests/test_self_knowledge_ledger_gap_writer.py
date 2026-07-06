from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from self_knowledge_ledger_gap_writer import (  # noqa: E402
    GAP_TABLE,
    backup_ledger,
    query_inventory_graph_from_ledger,
    write_inventory_graph_to_ledger,
    write_gaps_to_ledger,
)


def _make_ledger(path: Path, known_paths: list[str]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE file_inventory (path TEXT)")
        for p in known_paths:
            conn.execute("INSERT INTO file_inventory(path) VALUES (?)", (p,))


def test_dry_run_does_not_touch_ledger_or_write_backup(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    known = root / "known.py"
    unknown = root / "unknown.py"
    known.write_text("# known\n")
    unknown.write_text("# unknown\n")

    ledger = tmp_path / "ledger.sqlite"
    _make_ledger(ledger, [str(known)])
    before_mtime = ledger.stat().st_mtime

    result = write_gaps_to_ledger(root, ledger, confirm=False)

    assert result["status"] == "dry_run"
    assert result["plan"]["table"] == GAP_TABLE
    assert len(result["plan"]["rows"]) == 1
    assert result["plan"]["rows"][0]["subject"] == "unknown.py"
    # No backup files created, ledger untouched.
    assert ledger.stat().st_mtime == before_mtime
    siblings = list(tmp_path.glob("ledger.sqlite.bak-*"))
    assert siblings == []
    with sqlite3.connect(ledger) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert GAP_TABLE not in tables


def test_confirm_backs_up_then_writes_gap_rows(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    known = root / "known.py"
    unknown = root / "unknown.py"
    known.write_text("# known\n")
    unknown.write_text("# unknown\n")

    ledger = tmp_path / "ledger.sqlite"
    _make_ledger(ledger, [str(known)])

    result = write_gaps_to_ledger(root, ledger, confirm=True)

    assert result["status"] == "written"
    assert result["written_count"] == 1

    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert backup_path.stat().st_size > 0
    assert backup_path.parent == ledger.parent

    with sqlite3.connect(ledger) as conn:
        rows = conn.execute(
            f"SELECT subject, unknown_status, reason, _fold_source FROM {GAP_TABLE}"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "unknown.py"
    assert rows[0][1]
    assert rows[0][2]
    assert rows[0][3] == f"self_knowledge_crawler:{root.resolve()}"


def test_confirm_is_idempotent_replacing_only_its_own_fold_source(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "known.py").write_text("# known\n")
    (root / "unknown.py").write_text("# unknown\n")

    ledger = tmp_path / "ledger.sqlite"
    _make_ledger(ledger, [str(root / "known.py")])

    # Pre-seed a gap row from a different source that must be left alone.
    with sqlite3.connect(ledger) as conn:
        conn.execute(
            f"CREATE TABLE {GAP_TABLE} (unknown_id TEXT, subject TEXT, unknown_status TEXT, "
            "reason TEXT, next_safe_check TEXT, _fold_source TEXT, _fold_at TEXT)"
        )
        conn.execute(
            f"INSERT INTO {GAP_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("other::x", "other/x.py", "unconfirmed_gap", "manual", "n/a", "other_source", "2020-01-01"),
        )
        conn.commit()

    first = write_gaps_to_ledger(root, ledger, confirm=True)
    assert first["status"] == "written"
    second = write_gaps_to_ledger(root, ledger, confirm=True)
    assert second["status"] == "written"

    with sqlite3.connect(ledger) as conn:
        rows = conn.execute(f"SELECT subject, _fold_source FROM {GAP_TABLE}").fetchall()
    subjects = {(r[0], r[1]) for r in rows}
    assert ("other/x.py", "other_source") in subjects
    assert len([s for s in subjects if s[1] != "other_source"]) == 1


def test_confirm_fails_closed_if_backup_would_be_empty(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "unknown.py").write_text("# unknown\n")
    ledger = tmp_path / "ledger.sqlite"
    _make_ledger(ledger, [])

    def fake_copy2(src, dst):
        Path(dst).write_bytes(b"")  # simulate a bad/empty backup

    monkeypatch.setattr("self_knowledge_ledger_gap_writer.shutil.copy2", fake_copy2)

    result = write_gaps_to_ledger(root, ledger, confirm=True)

    assert result["status"] == "backup_verification_failed"
    with sqlite3.connect(ledger) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert GAP_TABLE not in tables


def test_backup_ledger_creates_timestamped_nonempty_copy(tmp_path):
    ledger = tmp_path / "ledger.sqlite"
    _make_ledger(ledger, ["x"])

    backup_path = backup_ledger(ledger)

    assert backup_path.exists()
    assert backup_path.stat().st_size > 0
    assert backup_path.name.startswith("ledger.sqlite.bak-")


def test_inventory_graph_writes_and_answers_high_medium_deep_queries(tmp_path):
    ledger = tmp_path / "ledger.sqlite"
    _make_ledger(ledger, [])
    graph = {
        "schema_version": "self_knowledge_inventory_graph_v1",
        "owner_scope": "pc",
        "nodes": {
            "machine:pc": {"id": "machine:pc", "kind": "machine", "owner_scope": "pc"},
            "repo:/repo": {"id": "repo:/repo", "kind": "repo", "owner_scope": "pc", "path": "/repo"},
            "worktree:/repo-wt": {
                "id": "worktree:/repo-wt",
                "kind": "worktree",
                "owner_scope": "pc",
                "worktree_path": "/repo-wt",
                "repo_path": "/repo",
                "health_status": "dirty",
                "last_seen_at": "2026-07-05T12:00:00+00:00",
            },
            "openclaw_instance:/repo-wt": {
                "id": "openclaw_instance:/repo-wt",
                "kind": "openclaw_instance",
                "owner_scope": "pc",
                "root_path": "/repo-wt",
                "activity_status": "idle",
            },
            "service:pc:kokoro-voice.service": {
                "id": "service:pc:kokoro-voice.service",
                "kind": "service",
                "owner_scope": "pc",
                "unit": "kokoro-voice.service",
                "activation_state": "active",
            },
        },
        "edges": [
            {"source": "machine:pc", "target": "repo:/repo", "relation": "contains"},
            {"source": "machine:pc", "target": "worktree:/repo-wt", "relation": "contains"},
            {"source": "worktree:/repo-wt", "target": "repo:/repo", "relation": "branch-of"},
            {"source": "worktree:/repo-wt", "target": "openclaw_instance:/repo-wt", "relation": "has-state"},
            {"source": "machine:pc", "target": "service:pc:kokoro-voice.service", "relation": "runs"},
        ],
    }

    dry_run = write_inventory_graph_to_ledger(graph, ledger, confirm=False)

    assert dry_run["status"] == "dry_run"
    with sqlite3.connect(ledger) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "knowledge_system_nodes" not in tables

    written = write_inventory_graph_to_ledger(graph, ledger, confirm=True)
    assert written["status"] == "written"
    assert written["node_count"] == 5
    assert written["edge_count"] == 5
    assert Path(written["backup_path"]).exists()

    high = query_inventory_graph_from_ledger(ledger, resolution="high")
    medium = query_inventory_graph_from_ledger(ledger, resolution="medium", owner_scope="pc")
    deep = query_inventory_graph_from_ledger(ledger, resolution="deep", node_id="worktree:/repo-wt")

    assert high["machine_count"] == 1
    assert high["repo_count"] == 1
    assert high["worktree_count"] == 1
    assert high["openclaw_instance_count"] == 1
    assert medium["machines"]["pc"]["worktrees"] == ["/repo-wt"]
    assert deep["node"]["health_status"] == "dirty"
    assert {node["kind"] for node in deep["neighbors"]} == {"machine", "openclaw_instance", "repo"}
