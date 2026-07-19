from __future__ import annotations

from copy import deepcopy

from price_truth_claim_audit import audit_temporal_truth_answer
from price_truth_packet_adapter import build_price_truth_packet


def _answer() -> dict:
    return build_price_truth_packet(
        "What do I charge for a solo acoustic gig now?",
        as_of="2026-07-19",
    )["temporal_truth_answer"]


def test_real_resolver_answer_passes_claim_audit() -> None:
    audit = audit_temporal_truth_answer(_answer())
    assert audit["status"] == "PASS"
    assert audit["violation_codes"] == []
    assert audit["action_authority_granted"] is False


def test_past_as_current_is_blocked() -> None:
    answer = _answer()
    answer["direct_answer"] = deepcopy(answer["historical_context"][0])
    answer["direct_answer"]["posture"] = "HISTORICAL_OBSERVED"

    audit = audit_temporal_truth_answer(answer)
    assert audit["status"] == "BLOCK"
    assert "PAST_AS_CURRENT" in audit["violation_codes"]


def test_unknown_as_known_is_blocked() -> None:
    answer = _answer()
    answer["direct_answer"]["value_known"] = True
    answer["direct_answer"]["typed_value"] = None

    audit = audit_temporal_truth_answer(answer)
    assert "UNKNOWN_AS_KNOWN" in audit["violation_codes"]


def test_missing_selected_or_rejected_trace_is_blocked() -> None:
    answer = _answer()
    answer["trace"].pop("selected_fact_refs")
    answer["trace"].pop("rejected_facts")

    audit = audit_temporal_truth_answer(answer)
    assert "TRACE_INCOMPLETE" in audit["violation_codes"]


def test_false_comparability_and_unauthorized_activation_are_blocked() -> None:
    answer = _answer()
    answer["comparison"].update(
        {"comparable": False, "growth_claim_allowed": True, "direction": "higher"}
    )
    answer["transition"].update(
        {"activated": True, "requires_operator": True, "operator_authority_ref": ""}
    )

    audit = audit_temporal_truth_answer(answer)
    assert "FALSE_COMPARABILITY" in audit["violation_codes"]
    assert "UNAUTHORIZED_REGIME_ACTIVATION" in audit["violation_codes"]
