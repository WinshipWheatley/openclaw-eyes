"""Tests for the sanctioned real-ledger populator + the allow_production override.

Confirms: the production guard blocks by default and only opens with an explicit override;
the populator dry-run never writes its target; --confirm writes + emits a reversible receipt;
--rollback fully reverses. All against TEMP dbs (the real ledger path is monkeypatched/overridden).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import canonical_doctrine_facts as cdf
import canonical_fact_ingest as cfi
from canonical_fact_ingest import ingest_graded_fact, reconcile_fact_index
from scripts import populate_real_ledger as prl


def _count(db: str) -> int:
    return sqlite3.connect(db).execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]


def _rec(text: str = "Doctrine fact for guard test.") -> dict:
    return {
        "fact_id": "X-1", "source_file": "OPENCLAW_RUNTIME.md", "section_heading": "x",
        "source_commit": "HEAD", "fact_text": text, "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief"], "doc_category": "test", "temporal_or_doctrine": "doctrine",
    }


def _grounded_count() -> int:
    return len([f for f in cdf.SHARED_DOCTRINE_FACTS
                if (f.get("provenance") or {}).get("grounding_status") != "UNGROUNDED"])


def test_guard_blocks_production_by_default(tmp_path, monkeypatch):
    prod = str(tmp_path / "prod.sqlite")
    monkeypatch.setattr(cfi, "_PRODUCTION_DB_PATH", prod)
    with pytest.raises(ValueError):
        ingest_graded_fact(_rec(), db_path=prod)  # allow_production defaults to False


def test_guard_allows_with_explicit_override(tmp_path, monkeypatch):
    prod = str(tmp_path / "prod.sqlite")
    monkeypatch.setattr(cfi, "_PRODUCTION_DB_PATH", prod)
    out = ingest_graded_fact(_rec(), db_path=prod, allow_production=True)
    assert out["status"] == "inserted"
    assert _count(prod) == 1


def test_dry_run_does_not_write(tmp_path):
    db = str(tmp_path / "ledger.sqlite")
    reconcile_fact_index(db)  # init empty schema
    before = _count(db)
    rc = prl.main(["--db", db])  # no --confirm -> dry run on a temp copy
    assert rc == 0
    assert _count(db) == before  # real target untouched


def test_confirm_writes_then_rollback(tmp_path, monkeypatch):
    db = str(tmp_path / "ledger.sqlite")
    reconcile_fact_index(db)
    monkeypatch.setattr(prl, "RECEIPT_DIR", tmp_path / "receipts")
    assert _count(db) == 0

    rc = prl.main(["--db", db, "--confirm"])
    assert rc == 0
    assert _count(db) == _grounded_count()

    receipts = list((tmp_path / "receipts").glob("*.json"))
    assert receipts, "confirmed population must write an audit receipt"

    rc2 = prl.main(["--rollback", str(receipts[0])])
    assert rc2 == 0
    assert _count(db) == 0  # fully reversible
