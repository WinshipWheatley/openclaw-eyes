"""Shared reply pipeline — the one helper that gives EVERY agent the live reply engines.

Covers the contract that matters for cross-agent wiring: never raises, returns a string, comedy is
hard-locked on high-risk surfaces, jargon teaches verified terms inline, and the front-door central
enrichment returns a well-formed response for any agent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reply_pipeline import apply_reply_pipeline


def test_never_raises_on_junk(tmp_path):
    for bad in ["", "   ", None, 123]:  # type: ignore[list-item]
        out = apply_reply_pipeline(bad, "q", "maestro", read_model_root=str(tmp_path))  # type: ignore[arg-type]
        assert isinstance(out, str)


def test_plain_answer_with_no_term_or_signal_is_unchanged(tmp_path):
    ans = "Everything looks nominal here."
    out = apply_reply_pipeline(ans, "general progress update", "chief", read_model_root=str(tmp_path))
    assert out.startswith(ans)


def test_high_risk_hard_locks_comedy(tmp_path):
    # approval/blocked phrasing would normally let comedy-as-diagnostic fire; high_risk suppresses it
    ans = "The release is blocked by a circular approval dependency."
    out = apply_reply_pipeline(ans, "why is it blocked?", "guardian", high_risk=True, read_model_root=str(tmp_path))
    assert out == ans  # no joke appended, no verified term present -> identical


def test_jargon_teaches_verified_term_inline_for_fresh_operator():
    # realize_term_teaching is the jargon glue the pipeline uses; a fresh operator gets the FULL,
    # EXACT verified ELI5 inserted adjacent to the term — never an invented definition.
    from jargon_realize import realize_term_teaching

    ans = "This instruction is staged under SEND_HOLD until you approve it."
    out, hints = realize_term_teaching(ans, operator_id="pytest_fresh_operator_reply_pipeline")
    assert "SEND_HOLD" in out
    assert "no agent can ever actually send" in out  # the EXACT verified eli5_full fragment
    assert hints  # a teaching hint was applied


def test_over_generic_grounded_adjective_is_not_taught(tmp_path):
    # regression guard: the bare adjective "grounded" must NOT trigger the grounded_fact term and
    # split the noun phrase (the alias was tightened to "grounded facts"/"grounded-fact").
    from jargon_realize import realize_term_teaching

    ans = "I don't have a grounded Maestro packet for that yet."
    out, _ = realize_term_teaching(ans, operator_id="pytest_fresh_operator_reply_pipeline_2")
    assert out == ans  # untouched — no mid-phrase definition insertion


def test_central_enrichment_returns_wellformed_response_for_any_agent():
    # The front-door chokepoint: every agent's reply funnels through process() -> _enrich_operator_surface.
    import os

    os.environ["OPENCLAW_TEST_MODE"] = "1"
    os.environ["SEND_HOLD"] = "1"
    import openclaw_request_processor as proc

    for prompt in ("what is pending my approval and why is it blocked?", "what is the system status right now?"):
        r = proc.process(prompt, read_model_root="generated/read_models")
        assert hasattr(r, "operator_message")
        assert isinstance(r.operator_message, str) and r.operator_message.strip()
