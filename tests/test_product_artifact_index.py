"""Governed product artifacts must be selectable, rankable, and fail closed.

The operator's product question could not select the product thesis — not because
ranking scored it poorly, but because `interpreter_lm._KNOWN_READ_MODELS` was a
literal list of ten filenames and the thesis was not one of them. A selection failure
wearing a retrieval failure's clothes.

Nothing here special-cases a question or asserts an answer string. The six intents
are ranking inputs; what is asserted is which document is *reachable*, never what it
says.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import product_artifact_index as pai

THESIS = "PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md"
ACCEPTANCE = "TELEGRAM-PACKET-ACCEPTANCE-20260728.md"

#: The six acceptance intents, phrased as an operator would.
INTENTS = {
    "product_thesis": (
        "What is OpenClaw's current owner-first product hypothesis, what is the "
        "smallest v1, and what is the top blocker before it is useful?"
    ),
    "exact_send_rules": (
        "What evidence proves a draft was approved before the exact-send gate released it?"
    ),
    "exact_send_failures": (
        "Why did the exact-send tests fail and what does the Gmail draft commit change?"
    ),
    "readiness_evidence": "What evidence already works and what is still a gap?",
    "approval_refusal": "Why would an approval be refused and what does the refusal say?",
    "transport_delivery": "Is fleet message delivery actually proven or just assumed?",
}


def _write(dirpath: Path, name: str, body: str) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / name
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    d = tmp_path / "PRODUCT"
    # Shaped like the real documents: the thesis carries "hypothesis" in a heading,
    # the acceptance report carries "delivery"/"transport". A fixture that omits the
    # words the real file has proves nothing about the real ranking.
    _write(d, THESIS, "# Product thesis — provable delegation\n\n"
                      "## The owner-first product hypothesis\n"
                      "Provable delegation binds authority to exact bytes.\n\n"
                      "## The painful job and the exact-send gate\n"
                      "An approval proves a draft was approved before release.\n\n"
                      "## Smallest v1\nOne recurring invoice, one channel.\n\n"
                      "## Gaps and blockers\nEvidence that works, and what is still a gap.\n\n"
                      "## Approval refusal\nA refusal names its reason.\n")
    _write(d, ACCEPTANCE, "# Telegram transport delivery acceptance test\n\n"
                          "## Verdict\nFAIL. Message delivery was not proven.\n\n"
                          "## Transport delivery truth\n"
                          "Six agents were tested; delivery is assumed, not proven.\n")
    _write(d, "REPAIR-PLAN.md", "# Repair plan — packet delivery and agent identity\n\n"
                                "## Seam one\nRetrieval status must be named.\n\n"
                                "## Approval refusal\nA refusal names its reason.\n")
    return d


# ────────────────────────────────────────────────────── indexing

def test_every_governed_artifact_is_indexed_with_hash_and_metadata(corpus: Path) -> None:
    rows = pai.build_index([corpus])
    assert len(rows) == 3
    for row in rows:
        assert row.sha256.startswith("sha256:")
        assert row.title.strip()
        assert row.source_ref.startswith("fleet_coord/PRODUCT/")
        assert row.size_bytes > 0
        assert row.modified_at.endswith("Z")
        assert row.sections, f"{row.source_ref} produced no sections"


def test_bounded_text_is_actually_bounded(corpus: Path) -> None:
    _write(corpus, "HUGE.md", "# Huge\n\n" + ("word " * 20000))
    rows = {r.source_ref.split("/")[-1]: r for r in pai.build_index([corpus])}
    huge = rows["HUGE.md"]
    assert len(huge.bounded_text) <= pai.ARTIFACT_TEXT_BUDGET + 4
    for section in huge.sections:
        assert len(section.text) <= pai.SECTION_TEXT_BUDGET + 4


def test_a_missing_source_directory_yields_an_empty_index_not_a_crash(tmp_path: Path) -> None:
    assert pai.build_index([tmp_path / "nope"]) == ()


# ────────────────────────────────────────────────────── ranking

def test_the_exact_operator_product_question_selects_the_thesis_first(corpus: Path) -> None:
    """The live failure, repaired: this query could not reach this document."""

    hits = pai.rank_artifacts(pai.build_index([corpus]), INTENTS["product_thesis"])
    assert hits, "the product question selected nothing"
    assert hits[0].source_ref.endswith(THESIS)


REAL_DIR = Path("/mnt/e/openclaw/fleet_coord/PRODUCT")


def _real_index():
    if not REAL_DIR.is_dir():
        pytest.skip("governed PRODUCT board not mounted")
    index = pai.build_index([REAL_DIR])
    if not index:
        pytest.skip("governed PRODUCT board is empty")
    return index


@pytest.mark.parametrize("intent", sorted(INTENTS))
def test_every_acceptance_intent_reaches_a_real_governed_artifact(intent: str) -> None:
    """The claim is about the REAL corpus, so it is tested against the real corpus."""

    assert pai.rank_artifacts(_real_index(), INTENTS[intent]), f"{intent} selected nothing"


def test_the_real_product_question_selects_the_real_thesis_first() -> None:
    hits = pai.rank_artifacts(_real_index(), INTENTS["product_thesis"])
    assert hits and hits[0].source_ref.endswith(THESIS)


def test_the_real_transport_question_prefers_the_real_acceptance_report() -> None:
    """NON-VACUITY on the real corpus: ranking must discriminate, not constant-answer."""

    hits = pai.rank_artifacts(_real_index(), INTENTS["transport_delivery"])
    assert hits and hits[0].source_ref.endswith(ACCEPTANCE)


def test_a_transport_question_prefers_the_transport_evidence(corpus: Path) -> None:
    """NON-VACUITY: if the thesis won every intent, ranking would be a constant."""

    hits = pai.rank_artifacts(pai.build_index([corpus]), INTENTS["transport_delivery"])
    assert hits and hits[0].source_ref.endswith(ACCEPTANCE)


@pytest.mark.parametrize("intent", ["product_thesis", "readiness_evidence",
                                    "approval_refusal", "transport_delivery"])
def test_synthetic_corpus_intents_reach_an_artifact(intent: str, corpus: Path) -> None:
    hits = pai.rank_artifacts(pai.build_index([corpus]), INTENTS[intent])
    assert hits, f"{intent} selected nothing"


def test_an_unrelated_question_selects_nothing(corpus: Path) -> None:
    """An honest empty beats dragging a document in because it shares the word 'the'."""

    assert pai.rank_artifacts(pai.build_index([corpus]), "what is the weather in Reykjavik") == ()


def test_an_empty_query_selects_nothing(corpus: Path) -> None:
    assert pai.rank_artifacts(pai.build_index([corpus]), "") == ()


def test_ranking_is_deterministic(corpus: Path) -> None:
    index = pai.build_index([corpus])
    a = [r.source_ref for r in pai.rank_artifacts(index, INTENTS["product_thesis"])]
    b = [r.source_ref for r in pai.rank_artifacts(index, INTENTS["product_thesis"])]
    assert a == b


def test_a_title_match_outranks_a_body_mention(corpus: Path) -> None:
    """The general rule that fixed the live ranking, stated as a rule."""

    _write(corpus, "MENTIONS.md", "# Weekly log\n\n## Notes\n"
                                  "We discussed the product hypothesis and the smallest v1 "
                                  "and the top blocker at length today.\n")
    hits = pai.rank_artifacts(pai.build_index([corpus]), INTENTS["product_thesis"])
    assert hits[0].source_ref.endswith(THESIS), (
        "a document merely mentioning the subject outranked the document about it"
    )


# ──────────────────────────────────────── load failure is NAMED

def test_loading_a_present_artifact_succeeds(corpus: Path) -> None:
    row = pai.build_index([corpus])[0].to_dict()
    status, text, _ = pai.load_artifact(row)
    assert status == pai.LOAD_OK and text.strip()


def test_a_deleted_selected_artifact_fails_closed_with_a_name(corpus: Path) -> None:
    rows = {r.source_ref.split("/")[-1]: r for r in pai.build_index([corpus])}
    row = rows[THESIS].to_dict()
    Path(row["path"]).unlink()
    status, text, detail = pai.load_artifact(row)
    assert status == pai.LOAD_MISSING
    assert text == "" and detail
    assert status in pai.LOAD_FAILURES


def test_an_edited_artifact_is_hash_drift_not_silent_substitution(corpus: Path) -> None:
    rows = {r.source_ref.split("/")[-1]: r for r in pai.build_index([corpus])}
    row = rows[THESIS].to_dict()
    Path(row["path"]).write_text("# Product thesis\n\nSomething else entirely.\n", encoding="utf-8")
    status, text, _ = pai.load_artifact(row)
    assert status == pai.LOAD_HASH_DRIFT
    assert text == "", "drifted content must not be served as if it were indexed"


def test_an_unreadable_artifact_fails_closed(corpus: Path) -> None:
    rows = {r.source_ref.split("/")[-1]: r for r in pai.build_index([corpus])}
    row = rows[THESIS].to_dict()
    Path(row["path"]).chmod(0o000)
    try:
        status, text, _ = pai.load_artifact(row)
    finally:
        Path(row["path"]).chmod(0o644)
    assert status in pai.LOAD_FAILURES
    assert text == ""


def test_no_failure_status_is_ever_confusable_with_success() -> None:
    assert pai.LOAD_OK not in pai.LOAD_FAILURES
    for bad in pai.LOAD_FAILURES:
        assert bad != pai.LOAD_OK


# ─────────────────────────────────── the interpreter can now select it

def test_the_interpreter_candidate_list_includes_indexed_artifacts(tmp_path, monkeypatch) -> None:
    """The actual defect: the thesis was not a candidate at all."""

    import interpreter_lm

    model = tmp_path / "index.json"
    model.write_text(json.dumps({
        "artifacts": [{"source_ref": f"fleet_coord/PRODUCT/{THESIS}", "path": "/x", "sha256": ""}]
    }), encoding="utf-8")
    monkeypatch.setattr(pai, "READ_MODEL_PATH", model)

    names = interpreter_lm._selectable_read_models()
    assert any(n.endswith(THESIS) for n in names), "the thesis is still unselectable"
    assert "chief_status_rail.json" in names, "the existing ten must not be dropped"


def test_an_unavailable_index_leaves_classification_working(monkeypatch) -> None:
    """NON-VACUITY: a broken index must degrade, never break the interpreter."""

    import interpreter_lm

    monkeypatch.setattr(pai, "READ_MODEL_PATH", Path("/nowhere/none.json"))
    names = interpreter_lm._selectable_read_models()
    assert "chief_status_rail.json" in names


def test_the_index_read_model_round_trips(corpus: Path, tmp_path: Path) -> None:
    out = pai.export_read_model(tmp_path / "rm.json", index=pai.build_index([corpus]))
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["read_model_id"] == pai.READ_MODEL_ID
    assert payload["artifact_count"] == 3
    assert len(pai.load_index_rows(out)) == 3
