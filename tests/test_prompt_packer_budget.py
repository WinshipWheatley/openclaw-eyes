"""What the model is HANDED, not what the packet holds.

Every claim tonight that a fix worked was made about something upstream of the final
prompt string. The packet held 3 thesis facts, 911 characters, status OK — and then
rendered 16,792 characters into a ~4,000-character front-door window, so roughly three
quarters was amputated by the runtime and the model answered "UNKNOWN — required
packet not retrieved". It was telling the truth about what reached it.

A fact-count cap of 30 bounds no characters at all, and the Boundaries block was
emitted LAST, which made the safety text the first thing to be cut.

These tests assert on the final string.
"""

from __future__ import annotations

import pytest

import maestro_context_packet as mcp

BUDGET = mcp.PROMPT_CHAR_BUDGET

OPERATOR_PROMPT = (
    "MAESTRO ACCEPTANCE TEST — Use only grounded packets you can actually retrieve. "
    "What is OpenClaw's current owner-first product hypothesis, what is the smallest "
    "v1, and what is the top blocker before it is useful?"
)


def _fact(topic: str, label: str, value: str, ref: str, sha: str = "") -> dict:
    return {
        "topic": topic, "label": label, "value": value, "source_ref": ref,
        "provenance": "test", "pii_tier": "PUBLIC",
        "freshness": {"sha256": sha} if sha else {},
    }


def _packet(*, facts, question=OPERATOR_PROMPT, skills=(), actionable=None) -> dict:
    return {
        "packet_id": "test", "generated_at": "2026-07-28T05:00:00Z",
        "question": question, "facts": list(facts), "skills": list(skills),
        "actionable": actionable or {}, "bounds": {"send_hold_absolute": True},
    }


def _bulk(n: int, size: int = 400) -> list[dict]:
    return [
        _fact("read_model", f"Filler {i}", "x" * size, f"generated/read_models/f{i}.json")
        for i in range(n)
    ]


THESIS_FACT = _fact(
    "product_artifact",
    "Product thesis — provable delegation — 5. Gaps",
    "Blocking v1, reordered on evidence: agent identity first, packet delivery second.",
    "fleet_coord/PRODUCT/PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md",
    sha="sha256:4270f9b4db346afaaed6a7beb4b862febece12698880c7cedeec36b67420e64e",
)


# ─────────────────────────────────────────────── the budget is a contract

def test_a_huge_packet_still_fits_the_window() -> None:
    """41 facts at 400 chars is ~16,000 — the live shape that got amputated."""

    text = mcp.format_maestro_context_packet(_packet(facts=[THESIS_FACT, *_bulk(40)]))
    assert len(text) <= BUDGET, f"{len(text)} chars would be truncated by the runtime"


def test_a_small_packet_is_not_padded() -> None:
    """NON-VACUITY: the packer must bound, not rewrite."""

    text = mcp.format_maestro_context_packet(_packet(facts=[THESIS_FACT]))
    assert len(text) < BUDGET
    assert "Product thesis" in text


# ────────────────────────────────── priority order, under pressure

def test_the_operator_question_survives_a_huge_packet() -> None:
    text = mcp.format_maestro_context_packet(_packet(facts=_bulk(60)))
    assert "OPERATOR QUESTION" in text
    assert "owner-first product hypothesis" in text


def test_the_safety_boundaries_survive_a_huge_packet() -> None:
    """They used to be emitted last, so they were first to be cut."""

    text = mcp.format_maestro_context_packet(_packet(facts=_bulk(60)))
    assert "SEND_HOLD absolute" in text
    assert "Money movement allowed" in text


def test_the_evidence_survives_a_huge_packet_with_its_citation() -> None:
    """THE LIVE FAILURE: 3 thesis facts present in the packet, absent from the prompt."""

    text = mcp.format_maestro_context_packet(_packet(facts=[*_bulk(40), THESIS_FACT]))
    assert "PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md" in text
    assert "sha256=sha256:4270f9b4" in text
    assert len(text) <= BUDGET


def test_priority_order_is_question_then_boundaries_then_evidence() -> None:
    text = mcp.format_maestro_context_packet(_packet(facts=[*_bulk(40), THESIS_FACT]))
    q, b, e = (text.find("OPERATOR QUESTION"), text.find("Boundaries:"),
               text.find("PRODUCT-THESIS"))
    assert -1 < q < b < e


def test_a_persona_can_never_crowd_out_the_evidence() -> None:
    """Personas come last by construction."""

    fat_skill = {"skill_id": "persona", "display_name": "P", "owner_agent": "maestro",
                 "selected_tier": "full", "authority": "read", "tools": [],
                 "tier_body": "y" * 9000}
    text = mcp.format_maestro_context_packet(
        _packet(facts=[*_bulk(20), THESIS_FACT], skills=[fat_skill])
    )
    assert "PRODUCT-THESIS" in text
    assert len(text) <= BUDGET
    assert "y" * 9000 not in text


def test_lower_relevance_facts_are_dropped_and_the_drop_is_declared() -> None:
    """Silent truncation is what caused this. Say what was left out."""

    text = mcp.format_maestro_context_packet(_packet(facts=[*_bulk(60), THESIS_FACT]))
    assert "lower-relevance facts omitted" in text


def test_remaining_facts_are_ranked_by_the_question() -> None:
    relevant = _fact("read_model", "Blocker status",
                     "the top blocker before it is useful is identity",
                     "generated/read_models/blockers.json")
    text = mcp.format_maestro_context_packet(_packet(facts=[*_bulk(40), relevant]))
    assert "Blocker status" in text, "a question-relevant fact lost to arrival order"


# ──────────────────────────────────── mutation at the truncation seam

def test_the_old_count_only_cap_would_have_failed_this() -> None:
    """MUTATION: facts[:30] with no character budget is the defect, reproduced."""

    facts = [*_bulk(40), THESIS_FACT]
    naive = "\n".join(f"- {f['label']}: {f['value']}" for f in facts[:30])
    assert len(naive) > BUDGET, "the fixture is too small to reproduce the bug"
    assert "PRODUCT-THESIS" not in naive, "the thesis was at position 41, beyond the cap"

    packed = mcp.format_maestro_context_packet(_packet(facts=facts))
    assert len(packed) <= BUDGET
    assert "PRODUCT-THESIS" in packed


def test_evidence_is_never_dropped_even_when_it_alone_exceeds_nothing() -> None:
    many_evidence = [
        _fact("product_artifact", f"Thesis section {i}", "z" * 300,
              "fleet_coord/PRODUCT/PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md")
        for i in range(3)
    ]
    text = mcp.format_maestro_context_packet(_packet(facts=[*many_evidence, *_bulk(40)]))
    assert text.count("Thesis section") == 3
    assert len(text) <= BUDGET


def test_an_empty_packet_still_carries_question_and_boundaries() -> None:
    text = mcp.format_maestro_context_packet(_packet(facts=[]))
    assert "OPERATOR QUESTION" in text and "SEND_HOLD absolute" in text


# ─────────────────────────────────────────────────────── the receipt

def test_the_receipt_records_the_final_prompt_not_the_packet(tmp_path, monkeypatch) -> None:
    import json
    from pathlib import Path

    receipt = tmp_path / "r.json"
    real_path = Path

    class _P(type(Path())):
        pass

    monkeypatch.setattr(mcp, "Path", real_path)
    text = mcp.format_maestro_context_packet(_packet(facts=[*_bulk(40), THESIS_FACT]))
    written = real_path("/home/openclaw/state/prompt_packer_receipt.json")
    if not written.exists():
        pytest.skip("receipt path not writable in this sandbox")
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["final_prompt_chars"] == len(text)
    assert payload["within_budget"] is True
    assert any("PRODUCT-THESIS" in r for r in payload["included_source_refs"])
