"""Instrument the ANSWER call, not the interpreter's.

Three diagnoses in a row measured protected_generate's seam and described the
interpreter's classification packet — 124 characters, no facts — because only the
interpreter reaches that seam. This receipt sits at the call site in
_answer_status_capability_with_brain that hands the packet to the model, so its
call_type is structural rather than inferred from prompt text.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import maestro_cassandra_responder as mcr

PACKET = {
    "packet_id": "maestro_context_packet:abc123",
    "packet_text": "x" * 3703,
    "facts": [
        {"topic": "product_artifact", "source_ref": "fleet_coord/PRODUCT/PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md"},
        {"source_ref": "generated/read_models/work_board.json"},
    ],
}


def test_the_receipt_records_the_answer_packet(tmp_path: Path) -> None:
    log = tmp_path / "a.jsonl"
    row = mcr._answer_generate_receipt(
        packet=PACKET, question="owner-first product hypothesis", agent="maestro",
        injected=False, path=log,
    )
    assert row["call_type"] == "answer_brain"
    assert row["packet_id"] == "maestro_context_packet:abc123"
    assert row["packet_text_chars"] == 3703
    assert row["fact_count"] == 2
    assert row["product_artifact_present"] is True
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["fact_count"] == 2


def test_the_receipt_is_append_only(tmp_path: Path) -> None:
    """Two calls, both visible — the defect that hid the answer call."""

    log = tmp_path / "a.jsonl"
    mcr._answer_generate_receipt(packet=PACKET, question="q1", agent="maestro",
                                 injected=False, path=log)
    mcr._answer_generate_receipt(packet={"packet_id": "stub", "packet_text": "y" * 124,
                                         "facts": []},
                                 question="q2", agent="maestro", injected=False, path=log)
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2, "one call overwrote the other"
    assert rows[0]["packet_id"] != rows[1]["packet_id"]
    assert rows[0]["fact_count"] == 2 and rows[1]["fact_count"] == 0


def test_the_receipt_never_carries_prompt_text(tmp_path: Path) -> None:
    """Lengths, a hash and refs only."""

    log = tmp_path / "a.jsonl"
    secret_packet = dict(PACKET, packet_text="SENSITIVE-OPERATOR-CONTENT" * 40)
    row = mcr._answer_generate_receipt(packet=secret_packet, question="q", agent="maestro",
                                       injected=False, path=log)
    assert "SENSITIVE-OPERATOR-CONTENT" not in json.dumps(row)
    assert len(row["packet_text_sha256"]) == 24


def test_a_stub_packet_is_visibly_a_stub(tmp_path: Path) -> None:
    """NON-VACUITY: the receipt must distinguish the real packet from the stub."""

    log = tmp_path / "a.jsonl"
    row = mcr._answer_generate_receipt(
        packet={"packet_id": "status_capability_x", "packet_text": "z" * 124, "facts": []},
        question="q", agent="maestro", injected=False, path=log,
    )
    assert row["fact_count"] == 0
    assert row["product_artifact_present"] is False
    assert row["packet_text_chars"] == 124


def test_the_real_answer_path_calls_the_receipt() -> None:
    """Structural: the instrumentation is on the answer call site itself."""

    src = inspect.getsource(mcr._answer_status_capability_with_brain)
    assert "_answer_generate_receipt(" in src
    i = src.index("_answer_generate_receipt(")
    assert "protected_generate" in src[i: i + 600], "receipt is not at the model boundary"


def test_a_bad_packet_shape_never_breaks_the_answer(tmp_path: Path) -> None:
    for bad in (None, "text", 42, []):
        row = mcr._answer_generate_receipt(packet=bad, question="q", agent="maestro",
                                           injected=False, path=tmp_path / "a.jsonl")
        assert row["call_type"] == "answer_brain"


def test_tests_can_never_write_the_production_receipt(monkeypatch) -> None:
    """The defect this closes: existing suites drive the real answer function, so the
    default path collected pytest fixture rows and I read them as live traffic.

    Third time tonight a receipt of mine was polluted by tests. The sandbox guard
    built this morning covers generated/read_models and not state/."""

    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    before = (mcr.ANSWER_GENERATE_RECEIPTS.read_text(encoding="utf-8")
              if mcr.ANSWER_GENERATE_RECEIPTS.exists() else "")
    row = mcr._answer_generate_receipt(packet=PACKET, question="q", agent="maestro",
                                       injected=False)
    after = (mcr.ANSWER_GENERATE_RECEIPTS.read_text(encoding="utf-8")
             if mcr.ANSWER_GENERATE_RECEIPTS.exists() else "")
    assert after == before, "a test wrote the production receipt"
    assert row["call_type"] == "answer_brain", "the row must still be returned"


def test_an_explicit_path_still_writes_under_test_mode(tmp_path, monkeypatch) -> None:
    """NON-VACUITY: the guard must block the DEFAULT path, not all writing."""

    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    log = tmp_path / "a.jsonl"
    mcr._answer_generate_receipt(packet=PACKET, question="q", agent="maestro",
                                 injected=False, path=log)
    assert log.exists() and log.read_text(encoding="utf-8").strip()


# ─────────────────────── every reachable model site, distinctly labelled

BRANCHES = ("status_capability_with_brain", "maestro_brain")


def test_every_model_site_carries_a_distinct_branch_id() -> None:
    """_answer_status_capability_with_brain was assumed live for hours on no
    evidence. There are two brain functions and four invocation sites; only a live
    turn can say which runs, and it can only say so if each is labelled."""

    import inspect

    src = inspect.getsource(mcr)
    for branch in BRANCHES:
        assert f'branch_id="{branch}"' in src, f"{branch} call site is unlabelled"
    assert src.count("_answer_generate_receipt(") >= 3, "a model site lost its marker"


def test_each_branch_id_is_recorded_verbatim(tmp_path) -> None:
    log = tmp_path / "b.jsonl"
    for branch in BRANCHES:
        row = mcr._answer_generate_receipt(
            packet=PACKET, question="q", agent="maestro", injected=False,
            branch_id=branch, path=log,
        )
        assert row["branch_id"] == branch
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert {r["branch_id"] for r in rows} == set(BRANCHES), "branches collapsed together"


def test_product_facts_are_counted_separately(tmp_path) -> None:
    row = mcr._answer_generate_receipt(
        packet=PACKET, question="q", agent="maestro", injected=False,
        branch_id="maestro_brain", path=tmp_path / "b.jsonl",
    )
    assert row["fact_count"] == 2
    assert row["product_artifact_facts"] == 1
    assert row["packet_text_chars"] == 3703


def test_a_stub_packet_shows_zero_product_facts(tmp_path) -> None:
    """NON-VACUITY: the count must distinguish a real packet from a stub."""

    row = mcr._answer_generate_receipt(
        packet={"packet_id": "stub", "packet_text": "z" * 124, "facts": []},
        question="q", agent="maestro", injected=False,
        branch_id="maestro_brain", path=tmp_path / "b.jsonl",
    )
    assert row["product_artifact_facts"] == 0 and row["packet_text_chars"] == 124


def test_the_question_hash_correlates_without_content(tmp_path) -> None:
    row = mcr._answer_generate_receipt(
        packet=PACKET, question="SENSITIVE-QUESTION", agent="maestro", injected=False,
        branch_id="maestro_brain", path=tmp_path / "b.jsonl",
    )
    assert len(row["question_sha256"]) == 24
    assert "SENSITIVE-QUESTION" not in json.dumps(row)
