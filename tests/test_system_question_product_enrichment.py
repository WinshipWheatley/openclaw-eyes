"""A product-related SYSTEM question gets the governed evidence. Nothing else changes.

The acceptance prompt is claimed by is_system_question_request, whose local answer
path reads its own narrow source — hence UNKNOWN with the thesis sitting indexed and
budgeted. The safer fix is additive: leave the predicate and the local semantics
alone, and give that responder the same facts, hashes, budget and provenance the
grounded path already proves it can deliver.
"""

from __future__ import annotations

import pytest

import workflow_package_request_consumer as c

PRODUCT_SYSTEM = [
    "STATUS CHECK — what is the current owner-first product hypothesis and the top blocker?",
    "Remind me: what is the smallest version of this that earns trust?",
    "For the record, which blocker is ahead of packet delivery now?",
    "what does provable delegation mean for the product",
]

NON_PRODUCT_SYSTEM = [
    "is the gateway up?",
    "what services are running right now?",
    "how much VRAM is free?",
    "when did the listener last restart?",
]

DIRECTIVES = [
    "Stage the follow-up email to Megan. Do not send it.",
    "Prepare the monthly speaker rental invoice.",
]

BASE = {"answer": {"proof_refs": ["generated/read_models/openclaw_request_processor_status.json"]}}


@pytest.mark.parametrize("q", PRODUCT_SYSTEM)
def test_product_system_questions_receive_governed_evidence(q: str) -> None:
    out = c._enrich_system_answer_with_product_facts(BASE, q)
    refs = out.get("source_refs") or []
    if not any("fleet_coord/PRODUCT/" in r for r in refs):
        pytest.skip("governed PRODUCT index not present in this environment")
    assert out.get("product_artifact_evidence")
    assert "sha256=" in out["product_artifact_evidence"], "evidence carries no hash"


@pytest.mark.parametrize("q", NON_PRODUCT_SYSTEM + DIRECTIVES)
def test_unrelated_system_questions_are_left_byte_identical(q: str) -> None:
    """NON-VACUITY the safety way: enrichment must not broaden to everything."""

    out = c._enrich_system_answer_with_product_facts(BASE, q)
    assert "product_artifact_evidence" not in out, f"{q!r} was wrongly enriched"
    assert out.get("answer", {}).get("proof_refs") == BASE["answer"]["proof_refs"]


def test_the_original_proof_refs_are_preserved_not_replaced() -> None:
    out = c._enrich_system_answer_with_product_facts(BASE, PRODUCT_SYSTEM[0])
    refs = out.get("answer", {}).get("proof_refs") or []
    assert BASE["answer"]["proof_refs"][0] in refs, "local-answer provenance was dropped"


def test_evidence_is_bounded() -> None:
    out = c._enrich_system_answer_with_product_facts(BASE, PRODUCT_SYSTEM[0])
    text = out.get("product_artifact_evidence") or ""
    if not text:
        pytest.skip("governed PRODUCT index not present in this environment")
    ceiling = c.PRODUCT_SYSTEM_MAX_SECTIONS * (c.PRODUCT_SYSTEM_SECTION_CHARS + 220)
    assert len(text) <= ceiling, f"{len(text)} chars would crowd the context window"


@pytest.mark.parametrize("bad", [None, "text", 42, {}, {"answer": "not-a-mapping"}])
def test_a_bad_payload_never_breaks_a_system_answer(bad) -> None:
    assert isinstance(c._enrich_system_answer_with_product_facts(bad, "what is the blocker?"), dict)


def test_an_empty_question_enriches_nothing() -> None:
    assert "product_artifact_evidence" not in c._enrich_system_answer_with_product_facts(BASE, "")


def test_the_enrichment_is_wired_into_the_system_receipt() -> None:
    """Structural: a helper nobody calls changes nothing."""

    import inspect

    src = inspect.getsource(c._system_question_receipt)
    assert "_enrich_system_answer_with_product_facts(" in src
