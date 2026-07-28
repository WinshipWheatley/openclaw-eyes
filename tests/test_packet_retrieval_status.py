"""An empty packet must say which kind of empty it is.

Maestro named chief_status_rail.json and answered a bare UNKNOWN while that file
sat on disk at 30KB, because every failure in the canonical-facts loader collapsed
to []. These tests keep the four kinds of empty distinguishable.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import maestro_context_packet as mcp
import packet_retrieval_status as prs


def _ledger_with(tmp_path: Path, *, tables: bool = True) -> Path:
    db = tmp_path / "ledger.sqlite"
    conn = sqlite3.connect(db)
    if tables:
        conn.execute(
            "CREATE TABLE canonical_facts (fact_id TEXT PRIMARY KEY, "
            "temporal_or_doctrine TEXT, doc_category TEXT)"
        )
    else:
        conn.execute("CREATE TABLE unrelated (x TEXT)")
    conn.commit()
    conn.close()
    return db


def _load(ledger: Path | str, question: str = "product hypothesis") -> tuple[list, dict]:
    status: dict = {}
    facts = mcp._sqlite_canonical_facts(question, ledger_path=str(ledger), status_out=status)
    return facts, status


# ------------------------------------------------------- the four kinds of empty

def test_missing_ledger_reports_LEDGER_MISSING_not_empty(tmp_path: Path) -> None:
    facts, status = _load(tmp_path / "nope.sqlite")
    assert facts == []
    assert status["status"] == prs.LEDGER_MISSING
    assert status["failed"] is True
    assert "nope.sqlite" in status["detail"]


def test_missing_tables_reports_TABLES_MISSING(tmp_path: Path) -> None:
    facts, status = _load(_ledger_with(tmp_path, tables=False))
    assert facts == []
    assert status["status"] == prs.TABLES_MISSING
    assert status["failed"] is True


def test_a_genuinely_empty_query_reports_EMPTY_BY_QUERY(tmp_path: Path) -> None:
    """NON-VACUITY. Without this, every test above passes for the wrong reason:
    a loader that reported failure unconditionally would satisfy them all."""

    facts, status = _load(_ledger_with(tmp_path, tables=True))
    assert facts == []
    assert status["status"] == prs.EMPTY_BY_QUERY
    assert status["failed"] is False, "an honest empty must not be reported as a failure"


def test_query_failure_is_distinguishable_from_an_honest_empty(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"this is not a database" * 40)
    facts, status = _load(corrupt)
    assert facts == []
    assert status["status"] in {prs.QUERY_FAILED, prs.TABLES_MISSING}
    assert status["failed"] is True
    assert status["status"] != prs.EMPTY_BY_QUERY


def test_the_four_empties_are_all_different(tmp_path: Path) -> None:
    """The whole point: four situations that used to be one value."""

    seen = {
        _load(tmp_path / "gone.sqlite")[1]["status"],
        _load(_ledger_with(tmp_path / "a", tables=False) if (tmp_path / "a").mkdir() is None else None)[1]["status"],
        _load(_ledger_with(tmp_path / "b", tables=True) if (tmp_path / "b").mkdir() is None else None)[1]["status"],
    }
    assert len(seen) == 3, f"statuses collapsed together: {seen}"


def test_status_out_is_optional_and_callers_do_not_break(tmp_path: Path) -> None:
    assert mcp._sqlite_canonical_facts("x", ledger_path=str(tmp_path / "none.sqlite")) == []


# ------------------------------------------------------------ result semantics

def test_ok_with_no_facts_degrades_to_empty_by_query() -> None:
    """OK + [] must not become the new ambiguous value."""

    assert prs.ok([]).status == prs.EMPTY_BY_QUERY


def test_only_ok_and_empty_by_query_are_trustworthy_empties() -> None:
    assert prs.RetrievalResult(status=prs.EMPTY_BY_QUERY).trustworthy_empty is True
    for bad in (prs.LEDGER_MISSING, prs.TABLES_MISSING, prs.QUERY_FAILED, prs.DECODE_FAILED):
        assert prs.RetrievalResult(status=bad).trustworthy_empty is False


def test_failure_refuses_to_dress_up_a_success() -> None:
    with pytest.raises(ValueError):
        prs.failure(prs.OK)


def test_every_failure_status_has_a_human_reason() -> None:
    for bad in prs.FAILURE_STATUSES:
        reason = prs.RetrievalResult(status=bad).human_reason()
        assert reason and "unrecognised" not in reason


# --------------------------------------------------------- provenance contract

def _packet(refs, facts) -> dict:
    return {"source_refs": list(refs), "facts": list(facts)}


def test_a_declared_source_ref_carries_facts_or_a_reason() -> None:
    good = _packet(["chief_status_rail.json"],
                   [{"source_ref": "chief_status_rail.json", "value": "x"}])
    ok, violations = prs.verify_source_refs(good)
    assert ok is True and violations == ()


def test_citing_a_source_you_did_not_read_is_a_violation() -> None:
    """THE MAESTRO REGRESSION: named chief_status_rail.json, carried nothing."""

    bad = _packet(["chief_status_rail.json"], [])
    ok, violations = prs.verify_source_refs(bad)
    assert ok is False
    assert violations[0]["source_ref"] == "chief_status_rail.json"
    assert violations[0]["reason"] == prs.MISSING_SOURCE_FACTS


def test_a_named_retrieval_failure_excuses_the_empty_source() -> None:
    bad = _packet(["chief_status_rail.json"], [])
    ok, violations = prs.verify_source_refs(
        bad, retrieval=prs.failure(prs.TABLES_MISSING, "canonical_facts absent")
    )
    assert ok is True, "a named reason is exactly what the contract asks for"


def test_an_honest_empty_does_not_excuse_citing_a_source() -> None:
    """EMPTY_BY_QUERY means the ledger was fine — so a cited source with no facts
    is still a citation of something unread."""

    bad = _packet(["chief_status_rail.json"], [])
    ok, _ = prs.verify_source_refs(bad, retrieval=prs.empty_by_query())
    assert ok is False


# ------------------------------------------------ the answer must surface it

def test_retrieval_failure_reaches_the_rendered_answer() -> None:
    suffix = prs.answer_suffix(
        _packet(["chief_status_rail.json"], []),
        retrieval=prs.failure(prs.TABLES_MISSING, "canonical_facts absent"),
    )
    assert "chief_status_rail.json" in suffix
    assert prs.TABLES_MISSING in suffix
    assert "No answer is possible" in suffix


def test_a_bare_unknown_is_no_longer_the_best_available_answer() -> None:
    """The defect in one assertion: the operator must learn which lever to pull."""

    suffix = prs.answer_suffix(_packet(["chief_status_rail.json"], []),
                               retrieval=prs.failure(prs.LEDGER_MISSING, "no file"))
    assert suffix.strip() != ""
    assert "ledger" in suffix.lower()


def test_grounded_answers_carry_provenance() -> None:
    packet = _packet(["chief_status_rail.json"],
                     [{"source_ref": "chief_status_rail.json", "value": "x"}])
    assert prs.provenance_line(packet).startswith("Evidence: ")
    assert "chief_status_rail.json" in prs.answer_suffix(packet)


def test_provenance_is_empty_when_there_is_nothing_true_to_cite() -> None:
    """No fabricated citations: an empty packet cites nothing."""

    assert prs.provenance_line(_packet(["a.json"], [])) == ""
