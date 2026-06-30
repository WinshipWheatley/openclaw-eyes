from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fold_satellite_to_ledger as fold  # noqa: E402


def _satellite(tmp: Path) -> Path:
    p = tmp / "demo_satellite.sqlite"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE system_component (id TEXT, name TEXT)")
    c.executemany("INSERT INTO system_component VALUES (?,?)", [("a", "Alpha"), ("b", "Beta")])
    c.execute("CREATE TABLE build_task (id TEXT)")
    c.execute("INSERT INTO build_task VALUES ('t1')")
    c.commit(); c.close()
    return p


def _ledger(tmp: Path) -> Path:
    p = tmp / "ledger.sqlite"
    sqlite3.connect(p).close()
    return p


def test_fold_writes_prefixed_tables_with_provenance(tmp_path: Path) -> None:
    sat, led = _satellite(tmp_path), _ledger(tmp_path)
    res = fold.fold(sat, led, "demo", skip={"build_task"})
    assert res["written"] == {"knowledge_demo_system_component": 2}
    c = sqlite3.connect(led)
    rows = c.execute('SELECT id, name, "_fold_source" FROM knowledge_demo_system_component ORDER BY id').fetchall()
    assert rows == [("a", "Alpha", str(sat)), ("b", "Beta", str(sat))]
    # skipped table is NOT folded
    assert c.execute("SELECT count(*) FROM sqlite_master WHERE name='knowledge_demo_build_task'").fetchone()[0] == 0
    c.close()


def test_fold_is_idempotent(tmp_path: Path) -> None:
    sat, led = _satellite(tmp_path), _ledger(tmp_path)
    fold.fold(sat, led, "demo", skip=set())
    fold.fold(sat, led, "demo", skip=set())  # second fold must not double rows
    c = sqlite3.connect(led)
    assert c.execute("SELECT count(*) FROM knowledge_demo_system_component").fetchone()[0] == 2
    c.close()


def test_verify_fails_when_unfolded(tmp_path: Path) -> None:
    sat, led = _satellite(tmp_path), _ledger(tmp_path)
    # not folded yet -> must NOT be ok to archive
    v = fold.verify(sat, led, "demo", skip=set(), repo_root=tmp_path)
    assert v["ok_to_archive"] is False
    assert "system_component" in v["unfolded_tables"]


def test_verify_passes_after_complete_fold_and_no_consumers(tmp_path: Path) -> None:
    sat, led = _satellite(tmp_path), _ledger(tmp_path)
    fold.fold(sat, led, "demo", skip={"build_task"})
    v = fold.verify(sat, led, "demo", skip={"build_task"}, repo_root=tmp_path)
    assert v["ok_to_archive"] is True
    assert v["unfolded_tables"] == [] and v["row_count_mismatches"] == []


def test_verify_fails_when_a_live_consumer_still_references_the_path(tmp_path: Path) -> None:
    sat, led = _satellite(tmp_path), _ledger(tmp_path)
    fold.fold(sat, led, "demo", skip={"build_task"})
    # a live .py that still references the satellite by name
    (tmp_path / "live_reader.py").write_text(f"PATH = '{sat.name}'\n", encoding="utf-8")
    v = fold.verify(sat, led, "demo", skip={"build_task"}, repo_root=tmp_path)
    assert v["ok_to_archive"] is False
    assert any("live_reader.py" in c for c in v["live_consumers_still_referencing_path"])
