"""Deterministic adversarial claim audit for temporal price-truth answers."""

from __future__ import annotations

from typing import Any, Mapping


def audit_temporal_truth_answer(answer: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    direct = answer.get("direct_answer") if isinstance(answer.get("direct_answer"), Mapping) else {}
    trace = answer.get("trace") if isinstance(answer.get("trace"), Mapping) else {}
    comparison = answer.get("comparison") if isinstance(answer.get("comparison"), Mapping) else {}
    transition = answer.get("transition") if isinstance(answer.get("transition"), Mapping) else {}
    authority = answer.get("authority_boundary") if isinstance(answer.get("authority_boundary"), Mapping) else {}
    axes = answer.get("axis_report") if isinstance(answer.get("axis_report"), list) else []

    if str(direct.get("posture") or "") == "HISTORICAL_OBSERVED":
        violations.append("PAST_AS_CURRENT")
    if direct.get("value_known") is True and direct.get("typed_value") is None:
        violations.append("UNKNOWN_AS_KNOWN")
    if "selected_fact_refs" not in trace or "rejected_facts" not in trace:
        violations.append("TRACE_INCOMPLETE")
    if any(
        not isinstance(row, Mapping)
        or not all(key in row for key in ("semantic_time", "evidence_freshness", "authority_state"))
        for row in axes
    ):
        violations.append("THREE_AXIS_TRACE_INCOMPLETE")
    if comparison.get("growth_claim_allowed") is True and comparison.get("comparable") is not True:
        violations.append("FALSE_COMPARABILITY")
    if transition.get("activated") is True and transition.get("requires_operator") is True:
        if not str(transition.get("operator_authority_ref") or ""):
            violations.append("UNAUTHORIZED_REGIME_ACTIVATION")
    if any(value is True for value in authority.values()):
        violations.append("ACTION_AUTHORITY_LEAK")
    machine = answer.get("machine_proof") if isinstance(answer.get("machine_proof"), Mapping) else {}
    if machine.get("historical_promoted_to_current") is True or machine.get("time_domains_blended") is True:
        violations.append("MACHINE_PROOF_TEMPORAL_VIOLATION")
    codes = sorted(set(violations))
    return {
        "schema_version": "price_truth_claim_audit_v1",
        "status": "BLOCK" if codes else "PASS",
        "violation_codes": codes,
        "selected_fact_refs": list(trace.get("selected_fact_refs") or []),
        "rejected_fact_count": len(trace.get("rejected_facts") or []),
        "action_authority_granted": False,
    }


__all__ = ["audit_temporal_truth_answer"]
