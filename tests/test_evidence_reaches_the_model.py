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


def test_the_evidence_is_appended_before_the_brain_call() -> None:
    """Structural, because the sandbox cannot run the brain: position is the contract."""

    src = inspect.getsource(orp)
    marker = src.index(MARKER)
    call = src.index("answer_frontdoor_chat(", marker)
    assert marker < call, "evidence is appended after the model call"


def test_it_reads_the_key_the_upstream_step_writes() -> None:
    """The gap that made two commits inert: written but never read."""

    src = inspect.getsource(orp)
    assert 'get("product_artifact_evidence")' in src
    assert 'raw_request = {**raw_request, "product_artifact_evidence": product_evidence}' in src


def test_absent_evidence_leaves_the_text_untouched() -> None:
    """Byte-identity: the append is guarded by a truthiness check on the key."""

    src = inspect.getsource(orp)
    i = src.index(MARKER)
    window = src[max(0, i - 400): i]
    assert "if _evidence:" in window, "the append is unconditional"


def test_the_evidence_is_budget_clipped() -> None:
    src = inspect.getsource(orp)
    i = src.index(MARKER)
    assert "[:2600]" in src[max(0, i - 400): i], "unbounded evidence would blow the window"


def test_the_label_tells_the_model_to_use_it() -> None:
    src = inspect.getsource(orp)
    i = src.index(MARKER)
    label = src[i: i + 160]
    assert "cited" in label and "answer from this" in label


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
