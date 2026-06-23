#!/usr/bin/env python3
"""Shared operator-reply pipeline — apply the 3 live engines to ANY agent's answer.

One call wires jargon teaching + scoped comedy-as-diagnostic + claim detection into any agent's
operator-facing reply. Agent-aware via ``agent_id`` (drives the comedy funniness rank). Every stage
is non-blocking and TRUTH-FIRST: jargon teaches only VERIFIED terms (exact wording), comedy uses
grounded slots + is scoped to the answer's situation + gate-governed, the detector audits the exact
text and queues only SUPERVISED heals (shadow-default, never deploys). NEVER raises.

Usage in any agent's reply path:
    from reply_pipeline import apply_reply_pipeline
    answer_text = apply_reply_pipeline(answer_text, question, agent_id="cassandra", packet_id=pid)
"""
from __future__ import annotations

from typing import Optional


def apply_reply_pipeline(
    answer_text: str,
    question: str,
    agent_id: str,
    *,
    packet_id: str = "",
    operator_id: str = "winship",
    read_model_root: Optional[str] = None,
    high_risk: bool = False,
) -> str:
    """Run jargon -> scoped comedy -> surface-guard -> claim detection on one agent's answer.
    Returns the (possibly enriched) answer. ``high_risk=True`` hard-locks comedy (blocked/deny/
    money/legal surfaces stay joke-free) while jargon + detection still run. Never raises — a
    pipeline failure must never affect or delay the answer."""
    if not isinstance(answer_text, str) or not answer_text.strip():
        return answer_text if isinstance(answer_text, str) else ""
    rid = (str(packet_id) or f"{agent_id}-reply")[:64] or f"{agent_id}-reply"

    # 1) Jargon teaching — verified terms only, exact ELI5, records learning progress.
    #    SKIPPED on high_risk surfaces (deny/safety/blocked): never mutate a crisp safety denial —
    #    an inline insert would split a verbatim phrase like "SEND_HOLD remains in force". Only the
    #    read-only guard + detector run on those surfaces (below).
    if not high_risk:
        try:
            from jargon_realize import realize_term_teaching
            from jargon_teaching_store import record_teaching_events_after_delivery

            answer_text, _hints = realize_term_teaching(answer_text, operator_id=operator_id)
            if _hints:
                record_teaching_events_after_delivery(operator_id, rid, _hints)
        except Exception:
            pass

    # 2) Comedy-as-diagnostic — grounded, scoped to the answer's situation, gate + rank governed.
    try:
        from comedy_signal_facts import produce_signal_facts, default_state
        from comedy_archetype_seeder import seed_comedy_archetype, realize_comedy_line
        from operator_surface_guard import check_comedy_gate
        from comedy_scope import is_comedy_relevant

        _sig = produce_signal_facts(default_state())
        if _sig:
            _gr = check_comedy_gate(agent_role=agent_id, error_flags=0, process_hung=False, high_risk_context=high_risk, payload_hash=str(packet_id))
            _gd = {
                "admitted": _gr.comedy_eligible, "zero_error_pass": not _gr.comedy_hard_locked,
                "agent_rank": _gr.agent_humor_rank, "intensity_cap": _gr.agent_humor_rank,
                "golden_ratio_roll_passed": _gr.golden_ratio_passed, "gate_decision_ref": str(packet_id),
            }
            _ch = seed_comedy_archetype(context_packet_facts=_sig, gate_decision=_gd, reply_id=rid, agent_id=agent_id)
            if getattr(_ch, "enabled", False) and is_comedy_relevant(getattr(_ch, "diagnostic_signal", None), question, answer_text):
                _cl = realize_comedy_line(_ch, _sig, literal_explanation=answer_text)
                if _cl:
                    answer_text = f"{answer_text}\n\n{_cl}"
    except Exception:
        pass

    # 2b) Surface guard (defense-in-depth, all agents) — flag any machine-contract leak that
    #     survived to the operator surface. Observability only; never alters or blocks the reply.
    try:
        from operator_surface_guard import check_machine_contract_leak

        _leak = check_machine_contract_leak(answer_text, audience="ELIWINSHIP")
        if getattr(_leak, "is_leak", False):
            print(f"[{agent_id}] operator-surface leak survived to surface: {_leak.reasons}", flush=True)
    except Exception:
        pass

    # 3) Claim detector — audit the EXACT final text; supervised heals only, never deploys.
    try:
        from pathlib import Path as _Path
        from claim_detector import detect_claims

        detect_claims(rid, agent_id, question, answer_text, read_model_root=_Path(read_model_root or "generated/read_models"))
    except Exception:
        pass

    return answer_text
