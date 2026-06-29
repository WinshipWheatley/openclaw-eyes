"""Tests for the curated shared-doctrine facts (SD-1..SD-13) + their loader.

These confirm the doctrine set is grounded in real tracked sources, that the
loader is idempotent and refuses ungrounded facts, and that loaded facts are
FTS-searchable. All ingestion runs against a TEMP db — never the real ledger.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import canonical_doctrine_facts as cdf

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_thirteen_doctrine_facts_with_required_fields_and_real_provenance() -> None:
    facts = cdf.SHARED_DOCTRINE_FACTS
    assert len(facts) == 13
    seen_ids = set()
    for rec in facts:
        for field in ("fact_id", "fact_text", "sensitivity_class", "allowed_actors", "doc_category", "temporal_or_doctrine"):
            assert rec.get(field), f"{rec.get('fact_id')} missing {field}"
        assert rec["fact_id"] not in seen_ids, f"duplicate fact_id {rec['fact_id']}"
        seen_ids.add(rec["fact_id"])
        prov = rec.get("provenance") or {}
        source_file = prov.get("source_file") or rec.get("source_file")
        assert source_file, f"{rec['fact_id']} has no provenance source_file"
        assert (REPO_ROOT / source_file).is_file(), f"{rec['fact_id']} source_file is not a real tracked file: {source_file}"
        assert prov.get("grounding_status") in {"GROUNDED", "PARTIALLY_GROUNDED", "UNGROUNDED"}


def test_no_fact_is_ungrounded() -> None:
    # Current curation must be fully grounded (or partially, against code). If an
    # UNGROUNDED fact ever appears, the loader is required to skip it (next test).
    ungrounded = [r["fact_id"] for r in cdf.SHARED_DOCTRINE_FACTS
                  if (r.get("provenance") or {}).get("grounding_status") == "UNGROUNDED"]
    assert ungrounded == [], f"ungrounded facts must be grounded or removed: {ungrounded}"


def test_every_basis_quote_is_grounded_in_its_cited_source() -> None:
    for rec in cdf.SHARED_DOCTRINE_FACTS:
        prov = rec.get("provenance") or {}
        if prov.get("grounding_status") == "UNGROUNDED":
            continue
        source_file = prov.get("source_file") or rec.get("source_file")
        basis = (prov.get("basis_quote") or "").strip().strip('"').strip("'")
        if not basis:
            continue
        text = (REPO_ROOT / source_file).read_text(errors="ignore")
        if basis[:50] in text:
            continue
        words = re.findall(r"[A-Za-z_]{5,}", basis)[:4]
        assert words and any(w in text for w in words), \
            f"{rec['fact_id']} basis_quote not found in cited source {source_file}"


def test_loader_ingests_then_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "doctrine.sqlite")
    first = cdf.load_doctrine_facts(db)
    ingestable = first["total"] - first["ungrounded_skipped"]
    assert first["inserted"] == ingestable
    assert first["ungrounded_skipped"] == 0  # current curation
    second = cdf.load_doctrine_facts(db)
    assert second["inserted"] == 0
    assert second["skipped"] == ingestable
    rows = sqlite3.connect(db).execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
    assert rows == ingestable


def test_loader_skips_ungrounded(tmp_path: Path, monkeypatch) -> None:
    # Inject a synthetic UNGROUNDED fact and confirm the loader holds it.
    bogus = {
        "fact_id": "SD-TEST-UNGROUNDED",
        "fact_text": "This claim has no real source.",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief"],
        "doc_category": "test",
        "temporal_or_doctrine": "doctrine",
        "source_file": "protected_generate.py",
        "section_heading": "test",
        "source_commit": "HEAD",
        "provenance": {"source_file": "protected_generate.py", "basis_quote": "", "grounding_status": "UNGROUNDED"},
    }
    monkeypatch.setattr(cdf, "SHARED_DOCTRINE_FACTS", list(cdf.SHARED_DOCTRINE_FACTS) + [bogus])
    db = str(tmp_path / "doctrine_skip.sqlite")
    result = cdf.load_doctrine_facts(db)
    assert result["ungrounded_skipped"] == 1
    ids = [r.get("fact_id") for r in result["results"] if r.get("status") == "ungrounded_skipped"]
    assert "SD-TEST-UNGROUNDED" in ids


def test_doctrine_actor_validator_rejects_phantom_roster_actor(tmp_path: Path) -> None:
    record = {
        "fact_id": "SD-TEST-PHANTOM-ACTOR",
        "fact_text": "OpenClaw agent roster: phantom (finance/invoicing).",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief"],
        "doc_category": "test",
        "temporal_or_doctrine": "doctrine",
        "source_file": "agent_lane_registry.py",
        "section_heading": "test",
        "source_commit": "HEAD",
        "provenance": {
            "source_file": "agent_lane_registry.py",
            "basis_quote": "AgentLaneSeed",
            "grounding_status": "GROUNDED",
        },
    }

    result = cdf.validate_doctrine_fact_actors(record, db_path=str(tmp_path / "ledger.sqlite"))

    assert result["ok"] is False
    assert result["unknown_actors"] == ["phantom"]


def test_loader_accepts_corrected_roster_without_fin_residue(tmp_path: Path) -> None:
    db = str(tmp_path / "doctrine_actor_guard.sqlite")
    result = cdf.load_doctrine_facts(db)

    held = [r for r in result["results"] if r.get("status") == "actor_validation_failed"]
    sd4 = next(record for record in cdf.SHARED_DOCTRINE_FACTS if record["fact_id"] == "SD-4")
    assert "fin (" not in sd4["fact_text"].lower()
    assert result["actor_validation_failed"] == 0
    assert held == []


def test_loaded_doctrine_is_fts_searchable(tmp_path: Path) -> None:
    db = str(tmp_path / "doctrine_fts.sqlite")
    cdf.load_doctrine_facts(db)
    con = sqlite3.connect(db)
    fts_rows = con.execute("SELECT COUNT(*) FROM fts_canonical_facts").fetchone()[0]
    cf_rows = con.execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
    assert fts_rows == cf_rows
    hits = con.execute("SELECT fact_id FROM fts_canonical_facts WHERE fts_canonical_facts MATCH ?", ("send",)).fetchall()
    assert hits, "expected the SEND_HOLD doctrine to be FTS-searchable for 'send'"
