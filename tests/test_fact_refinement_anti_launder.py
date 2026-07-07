from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

import canonical_doctrine_facts as cdf
import model_selection_doctrine_facts as ms
import niles_lane_doctrine_facts as nl
from business_ops_ledger import init_business_ops_ledger
from canonical_fact_ingest import ingest_graded_fact
from maestro_context_packet import build_maestro_context_packet
from scripts import ingest_canonical_docs as icd
from scripts import populate_real_ledger as prl


RAW_DICTATION = "papa rapper says Live Arts is all caught up for June, I think"


def _raw_dictation_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "fact_id": "DICT-RAW-1",
        "source_file": "OPENCLAW_RUNTIME.md",
        "section_heading": "Operator dictation",
        "source_commit": "HEAD",
        "fact_text": RAW_DICTATION,
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["maestro", "chief"],
        "doc_category": "operator_dictation",
        "temporal_or_doctrine": "temporal_checkpoint",
        "source_description": "dictation fixture",
        "truth_status": "declared",
        "verification_required": 1,
    }
    record.update(overrides)
    return record


def _fetch_fact(db_path: Path, fact_id: str = "DICT-RAW-1") -> sqlite3.Row:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM canonical_facts WHERE fact_id = ?", (fact_id,)).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


def test_populate_real_ledger_path_refines_dictation_without_laundering_raw_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "ledger.sqlite"
    review_path = tmp_path / "fact_refinement_review.json"
    init_business_ops_ledger(str(db_path))
    monkeypatch.setenv("OPENCLAW_FACT_REFINEMENT_REVIEW_PATH", str(review_path))
    monkeypatch.setattr(cdf, "SHARED_DOCTRINE_FACTS", [
        {
            **_raw_dictation_record(),
            "provenance": {"grounding_status": "GROUNDED"},
        }
    ])
    monkeypatch.setattr(ms, "MODEL_SELECTION_DOCTRINE_FACTS", [])
    monkeypatch.setattr(nl, "NILES_LANE_DOCTRINE_FACTS", [])

    result = prl._populate(str(db_path), allow_production=False)

    assert result["inserted"] == 1
    row = _fetch_fact(db_path)
    assert "papa rapper" not in row["fact_text"].lower()
    assert row["provenance_raw"] == RAW_DICTATION
    assert row["needs_operator_review"] == 1
    review = json.loads(review_path.read_text())
    assert review["facts_needing_operator_review"][0]["fact_id"] == "DICT-RAW-1"
    assert RAW_DICTATION not in json.dumps(review)


def test_ingest_canonical_docs_path_refines_dictation_without_laundering_raw_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "ledger.sqlite"
    review_path = tmp_path / "fact_refinement_review.json"
    source = tmp_path / "dictation.md"
    source.write_text(f"# Intake\n\n## Operator dictation\n{RAW_DICTATION}\n")
    monkeypatch.setenv("OPENCLAW_FACT_REFINEMENT_REVIEW_PATH", str(review_path))
    monkeypatch.setattr(icd, "SOURCE_REGISTRY", {
        str(source): {
            "doc_category": "operator_dictation",
            "sensitivity_class": "public_canonical",
            "allowed_actors": ["maestro", "chief"],
            "temporal_or_doctrine": "temporal_checkpoint",
            "description": "dictation fixture",
        }
    })
    monkeypatch.setattr(icd.subprocess, "check_output", lambda *_args, **_kwargs: "HEAD\n")
    monkeypatch.setattr(sys, "argv", [
        "ingest_canonical_docs.py",
        "--db",
        str(db_path),
        "--source",
        str(source),
    ])

    icd.main()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM canonical_facts LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row is not None
    assert "papa rapper" not in row["fact_text"].lower()
    assert RAW_DICTATION in row["provenance_raw"]
    assert row["needs_operator_review"] == 1
    assert RAW_DICTATION not in review_path.read_text()


def test_packet_never_prints_raw_dictation_from_canonical_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "ledger.sqlite"
    monkeypatch.setenv("OPENCLAW_LEDGER_PATH", str(db_path))
    monkeypatch.setenv("OPENCLAW_FACT_REFINEMENT_REVIEW_PATH", str(tmp_path / "review.json"))
    ingest_graded_fact(_raw_dictation_record(), db_path=str(db_path))

    packet = build_maestro_context_packet(
        question="what is the papa rapper Live Arts status?",
        session={},
        require_real_truth=False,
        packet_source="sqlite",
    )

    assert "papa rapper" not in packet["packet_text"].lower()
    assert RAW_DICTATION in _fetch_fact(db_path)["provenance_raw"]


def test_month_bounded_receivables_question_without_structured_fact_gets_not_tracked_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "ledger.sqlite"
    init_business_ops_ledger(str(db_path))
    monkeypatch.setenv("OPENCLAW_LEDGER_PATH", str(db_path))

    packet = build_maestro_context_packet(
        question="what did Live Arts owe me in June 2026?",
        session={"as_of_date": "2026-07-07"},
        require_real_truth=False,
        packet_source="sqlite",
    )

    assert "not tracked: month-bounded receivables" in packet["packet_text"].lower()
    marker = [fact for fact in packet["facts"] if fact.get("topic") == "money_not_tracked"][0]
    assert marker["as_of"] == "2026-07-07"
