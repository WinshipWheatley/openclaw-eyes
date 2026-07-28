"""Did the pre-model append actually fire?

The evidence visible in the response comes from the POST-answer wire and proves
nothing about the append. That ambiguity is the only thing separating "the brain
ignored the evidence" from "the brain never received it", and it has cost several
turns. This marker sits at the append site itself.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import openclaw_request_processor as orp


def test_it_records_a_fired_append(tmp_path: Path) -> None:
    log = tmp_path / "m.jsonl"
    row = orp._mark_pre_model_append(
        {"request_id": "req-1"}, "E" * 2442, "Q" * 3000, path=log
    )
    assert row["evidence_present"] is True
    assert row["evidence_len"] == 2442
    assert row["final_operator_text_len"] == 3000
    assert row["correlation"] == "req-1"
    assert len(row["operator_text_sha256"]) == 24
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["evidence_present"] is True


def test_it_records_a_skipped_append(tmp_path: Path) -> None:
    """NON-VACUITY: absence must be recorded, not inferred from a missing row."""

    row = orp._mark_pre_model_append({"request_id": "r"}, "", "Q" * 400, path=tmp_path / "m.jsonl")
    assert row["evidence_present"] is False and row["evidence_len"] == 0


def test_no_content_is_recorded(tmp_path: Path) -> None:
    row = orp._mark_pre_model_append(
        {"request_id": "r"}, "SECRET-EVIDENCE-TEXT", "SENSITIVE-OPERATOR-QUESTION",
        path=tmp_path / "m.jsonl",
    )
    blob = json.dumps(row)
    for forbidden in ("SECRET-EVIDENCE-TEXT", "SENSITIVE-OPERATOR-QUESTION"):
        assert forbidden not in blob
    assert set(row) == {
        "at", "correlation", "evidence_present", "evidence_len",
        "final_operator_text_len", "operator_text_sha256",
    }


def test_it_is_append_only(tmp_path: Path) -> None:
    log = tmp_path / "m.jsonl"
    orp._mark_pre_model_append({"request_id": "a"}, "x", "y", path=log)
    orp._mark_pre_model_append({"request_id": "b"}, "", "y", path=log)
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert [r["correlation"] for r in rows] == ["a", "b"]


def test_tests_never_write_production_state(monkeypatch) -> None:
    """Fourth time closing this hole; this time by construction, not per-file."""

    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    before = (orp.PRE_MODEL_APPEND_MARKERS.read_text(encoding="utf-8")
              if orp.PRE_MODEL_APPEND_MARKERS.exists() else "")
    row = orp._mark_pre_model_append({"request_id": "no"}, "x", "y")
    after = (orp.PRE_MODEL_APPEND_MARKERS.read_text(encoding="utf-8")
             if orp.PRE_MODEL_APPEND_MARKERS.exists() else "")
    assert after == before
    assert row["evidence_present"] is True, "the row must still be returned"


def test_a_bad_request_shape_never_breaks_the_answer(tmp_path: Path) -> None:
    for bad in (None, "text", 42, []):
        row = orp._mark_pre_model_append(bad, "x", "y", path=tmp_path / "m.jsonl")
        assert row["correlation"] == ""


def test_the_marker_sits_at_the_append_site() -> None:
    src = inspect.getsource(orp)
    marker = src.index("_mark_pre_model_append(raw_request, _evidence, operator_text)")
    append = src.index("GROUNDED EVIDENCE")
    call = src.index("answer_frontdoor_chat(", append)
    assert append < marker < call, "the marker is not between the append and the model call"
