"""Evidence must precede reasoning, and only for genuine questions.

The first attempt attached evidence to the finished payload: it reached the response
file while the model had already written "packet content unavailable". Context has to
precede reasoning.

The second attempt gated only on index match, and "Prepare the monthly speaker rental
invoice" — an imperative — drew 1,966 characters because it shares tokens with the
thesis's recurring-invoice section. The byte-identity tests passed vacuously, because
the pytest sandbox cannot reach the governed index and every question produced nothing.

So these tests refuse to pass vacuously: the product case SKIPS if the index is
unreachable rather than silently agreeing.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import openclaw_request_processor as orp

PRODUCT_QUESTIONS = [
    "STATUS CHECK — what is the current owner-first product hypothesis and the top blocker?",
    "Remind me, what is the smallest version that earns trust?",
    "which blocker sits ahead of packet delivery now?",
]
UNRELATED_SYSTEM = ["is the gateway up?", "what services are running right now?"]
IMPERATIVES = [
    "Prepare the monthly speaker rental invoice.",
    "Stage the follow-up email to Megan. Do not send it.",
    "Draft the invoice for St Annes and hold it for review.",
]


def _req(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"source_text": text}), encoding="utf-8")
    return p


@pytest.mark.parametrize("q", PRODUCT_QUESTIONS)
def test_product_questions_get_evidence_before_the_model(tmp_path: Path, q: str) -> None:
    ev = orp._product_evidence_for_request(_req(tmp_path, q))
    if ev is None:
        pytest.skip("governed PRODUCT index unreachable here — NOT a pass")
    assert "sha256=" in ev and "PRODUCT-THESIS" in ev


@pytest.mark.parametrize("q", UNRELATED_SYSTEM)
def test_unrelated_system_questions_get_nothing(tmp_path: Path, q: str) -> None:
    assert orp._product_evidence_for_request(_req(tmp_path, q)) is None


@pytest.mark.parametrize("q", IMPERATIVES)
def test_imperatives_get_nothing_even_when_tokens_overlap(tmp_path: Path, q: str) -> None:
    """THE REGRESSION: index match alone wrongly armed an invoice imperative."""

    assert orp._product_evidence_for_request(_req(tmp_path, q)) is None


def test_form_is_checked_before_index_match() -> None:
    """Structural, because the sandbox cannot exercise it: the interrogative gate
    must run before the enrichment call, or an imperative can be armed again."""

    src = inspect.getsource(orp._product_evidence_for_request)
    assert "_is_general_question_text" in src
    assert src.index("_is_general_question_text(question)") < src.index(
        "_enrich_system_answer_with_product_facts({}"
    ), "index match runs before the form check"


def test_a_missing_or_unreadable_request_yields_none(tmp_path: Path) -> None:
    assert orp._product_evidence_for_request(tmp_path / "absent.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert orp._product_evidence_for_request(bad) is None


def test_core_defaults_to_identity() -> None:
    """The keyword-only parameter defaults to None, so every existing caller is
    byte-identical by construction."""

    sig = inspect.signature(orp._process_request_path_core)
    param = sig.parameters["product_evidence"]
    assert param.default is None
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_core_attaches_evidence_after_normalisation_and_before_preflight() -> None:
    src = inspect.getsource(orp._process_request_path_core)
    assert 'raw_request = {**raw_request, "product_artifact_evidence": product_evidence}' in src
    assert src.index("product_artifact_evidence") < src.index("preflight_request("), (
        "evidence is attached after preflight, so the model would not see it"
    )


def test_the_live_branch_passes_evidence_to_core() -> None:
    """process_once -> process_request_path -> core, the branch the stack named."""

    src = inspect.getsource(orp.process_request_path)
    assert "_product_evidence_for_request(request_path)" in src
    assert "product_evidence=_product_evidence" in src
    assert src.index("_product_evidence_for_request") < src.index(
        "_process_request_path_core("
    ), "evidence is derived after the model call"


def test_process_once_reaches_that_branch() -> None:
    src = inspect.getsource(orp.process_once)
    assert "process_request_path(" in src


def test_the_post_answer_wire_is_still_present() -> None:
    """Kept for independent provenance verification."""

    assert "_maybe_enrich_with_product_evidence(response_payload)" in inspect.getsource(
        orp.run_and_write
    )
