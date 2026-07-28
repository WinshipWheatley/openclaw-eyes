"""The bridge must send what the egress needs to judge an answer.

The listener could always surface a retrieval failure or a citation — it just never
received one. The response carried the ANSWER and dropped everything needed to weigh
it, so Maestro said UNKNOWN and the operator had no way to learn that
chief_status_rail.json had been selected and had failed to load.

These drive the real consumer function and the real egress, end to end.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import agent_reply_egress as egress
import workflow_package_request_consumer as consumer

QUESTION = "What is the current top blocker?"


def _result(packet=None, **kw):
    return SimpleNamespace(packet=packet, **kw)


# ─────────────────────────────────────────── extraction from the real result

def test_the_operator_question_is_carried() -> None:
    out = consumer._grounded_answer_provenance(_result(), source_text=QUESTION)
    assert out["source_text"] == QUESTION


def test_source_refs_are_lifted_from_the_packet() -> None:
    packet = {"source_refs": ["chief_status_rail.json"],
              "facts": [{"source_ref": "work_board.json", "value": "x"}]}
    out = consumer._grounded_answer_provenance(_result(packet), source_text=QUESTION)
    assert out["source_refs"] == ["chief_status_rail.json", "work_board.json"]


def test_source_refs_are_deduplicated() -> None:
    packet = {"source_refs": ["a.json", "a.json"],
              "facts": [{"source_ref": "a.json"}]}
    out = consumer._grounded_answer_provenance(_result(packet), source_text=QUESTION)
    assert out["source_refs"] == ["a.json"]


def test_a_retrieval_failure_survives_serialization() -> None:
    packet = {"source_refs": ["chief_status_rail.json"],
              "retrieval_status": {"status": "TABLES_MISSING",
                                   "detail": "canonical_facts absent",
                                   "source_path": "/x/ledger.sqlite"}}
    out = consumer._grounded_answer_provenance(_result(packet), source_text=QUESTION)
    assert out["retrieval_status"]["status"] == "TABLES_MISSING"
    assert out["retrieval_status"]["detail"] == "canonical_facts absent"


def test_a_mapping_payload_works_as_well_as_a_result_object() -> None:
    """The system-question path passes a plain dict; both are grounded answers."""

    payload = {"source_refs": ["b.json"],
               "retrieval_status": {"status": "LEDGER_MISSING", "detail": "gone"}}
    out = consumer._grounded_answer_provenance(payload, source_text=QUESTION)
    assert out["source_refs"] == ["b.json"]
    assert out["retrieval_status"]["status"] == "LEDGER_MISSING"


def test_extraction_is_total_and_never_breaks_a_good_response() -> None:
    """A response that fails to send is worse than one lacking a citation."""

    for bad in (None, object(), 42, "text", {"packet": "not-a-mapping"}):
        out = consumer._grounded_answer_provenance(bad, source_text=QUESTION)
        assert out["source_text"] == QUESTION


def test_no_status_key_is_emitted_when_there_is_no_status() -> None:
    """NON-VACUITY: absence must stay absent, or the egress sees noise every turn."""

    out = consumer._grounded_answer_provenance(_result({"facts": []}), source_text=QUESTION)
    assert "retrieval_status" not in out
    assert "source_refs" not in out


def test_a_malformed_status_is_dropped_not_forwarded() -> None:
    packet = {"retrieval_status": {"status": "", "detail": "junk"}}
    out = consumer._grounded_answer_provenance(_result(packet), source_text=QUESTION)
    assert "retrieval_status" not in out


# ───────────────────────────────────── the payload actually reaches the egress

def test_a_failure_status_becomes_an_actionable_operator_reply() -> None:
    """THE MAESTRO REGRESSION, bridge to reply."""

    packet = {"source_refs": ["chief_status_rail.json"],
              "retrieval_status": {"status": "TABLES_MISSING", "detail": "canonical_facts absent"}}
    payload = consumer._grounded_answer_provenance(_result(packet), source_text=QUESTION)

    reply = egress.finalize_agent_reply("maestro", "UNKNOWN.", payload=payload)
    assert "chief_status_rail.json" in reply
    assert "TABLES_MISSING" in reply
    assert reply.strip() != "UNKNOWN."


def test_an_honest_empty_reaches_the_operator_without_noise() -> None:
    packet = {"source_refs": ["cal.json"],
              "retrieval_status": {"status": "EMPTY_BY_QUERY", "detail": ""}}
    payload = consumer._grounded_answer_provenance(_result(packet), source_text=QUESTION)
    reply = egress.finalize_agent_reply("maestro", "Nothing scheduled.", payload=payload)
    assert "Retrieval failed" not in reply
    assert "Nothing scheduled." in reply


def test_the_carried_question_drives_dominance_without_being_passed_twice() -> None:
    """The egress reads source_text off the payload, so no caller has to remember."""

    niles_q = ("For the exact-send gate, what evidence proves a draft was approved "
               "before it was released, and which artifact records it?")
    payload = consumer._grounded_answer_provenance(_result(), source_text=niles_q)
    reply = egress.finalize_agent_reply(
        "niles", "What's the main goal: groove, melody, or arrangement?", payload=payload
    )
    assert "groove" not in reply
    assert "UNKNOWN" in reply


def test_a_real_answer_with_citations_survives_intact() -> None:
    """NON-VACUITY in the other direction."""

    packet = {"source_refs": ["work_board.json"],
              "facts": [{"source_ref": "work_board.json", "value": "x"}]}
    payload = consumer._grounded_answer_provenance(_result(packet), source_text=QUESTION)
    reply = egress.finalize_agent_reply("maestro", "The top blocker is identity.",
                                        payload=payload)
    assert "The top blocker is identity." in reply


# ─────────────────────────────────────────────── the wiring is really there

def test_both_grounded_response_paths_call_the_extractor() -> None:
    """Wiring only the path the battery caught is how the other keeps the bug."""

    import inspect

    source = inspect.getsource(consumer)
    assert source.count("_grounded_answer_provenance(") >= 3, (
        "expected the definition plus both grounded response sites"
    )
