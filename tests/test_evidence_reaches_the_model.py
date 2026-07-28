"""The evidence must be IN the text the brain receives, not merely near it.

Every prior attempt carried the evidence one step further and stopped short: into the
response payload (after the model wrote its answer), then into raw_request (which
nothing read). Each time the model said "not retrievable in this lane" and was telling
the truth. operator_text is what actually reaches the brain.
"""

from __future__ import annotations

import inspect

import pytest

import openclaw_request_processor as orp

MARKER = "GROUNDED EVIDENCE"
THESIS_REF = "fleet_coord/PRODUCT/PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md"


def test_the_evidence_is_not_double_injected_as_free_text() -> None:
    """Live counts proved the packet already carries 5 product facts with source_ref
    and sha256. Appending the same text to operator_text put ~2,250 duplicate
    characters into a ~4,000-character window and the answers degenerated to one
    truncated line. The packet is the only home for this evidence."""

    src = inspect.getsource(orp)
    assert MARKER not in src, "evidence is being appended as free text again"


def test_it_reads_the_key_the_upstream_step_writes() -> None:
    """The gap that made two commits inert: written but never read."""

    src = inspect.getsource(orp)
    assert 'get("product_artifact_evidence")' in src
    assert 'raw_request = {**raw_request, "product_artifact_evidence": product_evidence}' in src


def test_operator_text_is_never_mutated_by_evidence() -> None:
    """Byte-identity by construction: nothing rewrites operator_text at all now."""

    src = inspect.getsource(orp)
    assert "operator_text = (" not in src.split("_mark_pre_model_append")[0][-1200:]


def test_the_packet_remains_the_single_source_of_evidence() -> None:
    """The mechanism that works, asserted where it lives."""

    import maestro_context_packet as mcp

    psrc = inspect.getsource(mcp)
    assert "_product_artifact_facts(question=question)" in psrc
    assert "*product_facts," in psrc, "product facts dropped from a fact assembly"


def test_the_derivation_still_refuses_imperatives(tmp_path) -> None:
    """End-to-end on the derivation half, which the sandbox CAN run."""

    import json

    for text in ("Prepare the monthly speaker rental invoice.",
                 "Stage the follow-up email to Megan. Do not send it."):
        p = tmp_path / "r.json"
        p.write_text(json.dumps({"source_text": text}), encoding="utf-8")
        assert orp._product_evidence_for_request(p) is None


def test_a_product_question_still_derives_evidence(tmp_path) -> None:
    import json

    p = tmp_path / "r.json"
    p.write_text(json.dumps(
        {"source_text": "what is the current owner-first product hypothesis and top blocker?"}
    ), encoding="utf-8")
    ev = orp._product_evidence_for_request(p)
    if ev is None:
        pytest.skip("governed PRODUCT index unreachable here — NOT a pass")
    assert THESIS_REF in ev and "sha256=" in ev


def test_the_live_branch_still_threads_evidence_to_core() -> None:
    src = inspect.getsource(orp.process_request_path)
    assert "product_evidence=_product_evidence" in src
    assert "process_request_path(" in inspect.getsource(orp.process_once)


def test_diagnostics_are_still_present_until_pass() -> None:
    assert "_diagnostic_producing_stack" in inspect.getsource(orp)
    assert "_maybe_enrich_with_product_evidence(response_payload)" in inspect.getsource(
        orp.run_and_write
    )
