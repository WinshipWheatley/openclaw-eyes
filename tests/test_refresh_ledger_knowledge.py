from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_ledger_knowledge as refresh  # noqa: E402


def _satellite(tmp: Path, name: str, rows: int) -> Path:
    p = tmp / f"{name}.sqlite"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE component (id TEXT)")
    c.executemany("INSERT INTO component VALUES (?)", [(f"r{i}",) for i in range(rows)])
    c.commit(); c.close()
    return p


def test_refresh_folds_all_sources_and_stamps_freshness(tmp_path: Path, monkeypatch) -> None:
    sat_a = _satellite(tmp_path, "alpha", 3)
    sat_b = _satellite(tmp_path, "beta", 5)
    ledger = tmp_path / "ledger.sqlite"; sqlite3.connect(ledger).close()
    monkeypatch.setattr(refresh, "KNOWLEDGE_SOURCES", (
        {"prefix": "alpha", "path": str(sat_a), "skip": set()},
        {"prefix": "beta", "path": str(sat_b), "skip": set()},
        {"prefix": "ghost", "path": str(tmp_path / "missing.sqlite"), "skip": set()},
    ))
    out = refresh.refresh(ledger)
    status = {s["prefix"]: s["status"] for s in out["sources"]}
    assert status == {"alpha": "refreshed", "beta": "refreshed", "ghost": "MISSING_SOURCE"}

    c = sqlite3.connect(ledger)
    assert c.execute("SELECT count(*) FROM knowledge_alpha_component").fetchone()[0] == 3
    assert c.execute("SELECT count(*) FROM knowledge_beta_component").fetchone()[0] == 5
    # every source (incl. the missing one) is stamped, so staleness/coverage is queryable
    stamped = {r[0] for r in c.execute("SELECT DISTINCT prefix FROM knowledge_fold_runs")}
    assert stamped == {"alpha", "beta", "ghost"}
    c.close()

    # idempotent: a second refresh does not double rows
    refresh.refresh(ledger)
    c = sqlite3.connect(ledger)
    assert c.execute("SELECT count(*) FROM knowledge_alpha_component").fetchone()[0] == 3
    c.close()


def test_staleness_reports_never_before_first_fold(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "ledger.sqlite"; sqlite3.connect(ledger).close()
    monkeypatch.setattr(refresh, "KNOWLEDGE_SOURCES", (
        {"prefix": "alpha", "path": str(tmp_path / "x.sqlite"), "skip": set()},
    ))
    rows = refresh.staleness(ledger)
    assert rows[0]["prefix"] == "alpha" and rows[0]["last_fold"] is None
