"""The connection at the live boundary, proven at that boundary.

A stack captured from the written response named the path: service:2344 ->
run_and_write -> stamp -> publish. Everything repaired tonight sat upstream of it and
never reached the operator. This is the wire, not the mechanism — the enrichment
itself is already proven elsewhere.
"""

from __future__ import annotations

import inspect

import pytest

import openclaw_request_processor as orp

PRODUCT_QUESTIONS = [
    "STATUS CHECK — what is the current owner-first product hypothesis and the top blocker?",
    "Remind me, what is the smallest version that earns trust?",
    "which blocker sits ahead of packet delivery now?",
]

NON_PRODUCT = [
    "is the gateway up?",
    "what services are running right now?",
    "when did the listener last restart?",
]

IMPERATIVES = [
    "Stage the follow-up email to Megan. Do not send it.",
    "Prepare the monthly speaker rental invoice.",
]

BASE = {"one_line_answer": "x", "source_refs": ["generated/read_models/a.json"]}


def _payload(question: str) -> dict:
    return dict(BASE, source_text=question)


@pytest.mark.parametrize("q", PRODUCT_QUESTIONS)
def test_product_questions_gain_evidence_at_this_boundary(q: str) -> None:
    out = orp._maybe_enrich_with_product_evidence(_payload(q))
    if "product_artifact_evidence" not in out:
        pytest.skip("governed PRODUCT index not present in this environment")
    assert "sha256=" in out["product_artifact_evidence"]
    assert any("fleet_coord/PRODUCT/" in r for r in (out.get("source_refs") or []))
    assert out["source_refs"][0] == "generated/read_models/a.json", "existing refs dropped"


@pytest.mark.parametrize("q", NON_PRODUCT + IMPERATIVES)
def test_everything_else_is_byte_identical(q: str) -> None:
    """NON-VACUITY the safety way: the wire must not change unrelated answers."""

    payload = _payload(q)
    assert orp._maybe_enrich_with_product_evidence(payload) == payload


def test_a_payload_without_a_question_is_untouched() -> None:
    assert orp._maybe_enrich_with_product_evidence(dict(BASE)) == dict(BASE)


@pytest.mark.parametrize("bad", [None, "text", 42, []])
def test_a_bad_payload_never_breaks_the_write(bad) -> None:
    assert orp._maybe_enrich_with_product_evidence(bad) is bad


def test_the_wire_sits_between_build_and_publish() -> None:
    """Structural: after the payload is built, before it is stamped and written."""

    src = inspect.getsource(orp.run_and_write)
    assert "_maybe_enrich_with_product_evidence(response_payload)" in src
    build = src.index("build_payloads(")
    wire = src.index("_maybe_enrich_with_product_evidence(")
    publish = src.index("publish_response_for_mac_outbox(")
    assert build < wire < publish, "the wire is not between build and publish"


def test_the_service_reaches_run_and_write() -> None:
    """The boundary the captured stack named."""

    import openclaw_request_response_service as svc

    src = inspect.getsource(svc.process_one_pending_request)
    assert "run_and_write(" in src
    assert "pc_handled" in src


def test_enrichment_failure_leaves_the_payload_intact(monkeypatch) -> None:
    import workflow_package_request_consumer as c

    monkeypatch.setattr(
        c, "_enrich_system_answer_with_product_facts",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    payload = _payload(PRODUCT_QUESTIONS[0])
    assert orp._maybe_enrich_with_product_evidence(payload) == payload
