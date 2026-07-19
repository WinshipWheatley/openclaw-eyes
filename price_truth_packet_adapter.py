"""Natural-question adapter for the pure price-truth temporal resolver."""

from __future__ import annotations

from datetime import date
from typing import Any

from price_truth_claim_audit import audit_temporal_truth_answer
from price_truth_temporal import load_price_truth_facts, resolve_temporal_truth


def classify_price_truth_question(question: str) -> tuple[str, str]:
    text = " ".join(str(question or "").casefold().split())
    if not any(term in text for term in ("price", "pricing", "charge", "rate", "cost", "paid", "quote")):
        return "", ""
    if any(term in text for term in ("organization", "comes online", "goes online", "new regime")):
        question_class = "C4"
    elif any(term in text for term in ("fresh", "evidence", "up to date", "source current")):
        question_class = "C3"
    elif any(term in text for term in ("past", "used to", "before", "versus", "compare", "then")):
        question_class = "C2"
    else:
        question_class = "C1"
    if any(term in text for term in ("solo", "acoustic", "reynolds")):
        subject_ref = "solo_acoustic"
    elif "capital hilton" in text:
        subject_ref = "capital_hilton_per_gig"
    else:
        subject_ref = "band_event"
    return question_class, subject_ref


def build_price_truth_packet(question: str, *, as_of: str | None = None) -> dict[str, Any]:
    question_class, subject_ref = classify_price_truth_question(question)
    if not question_class:
        return {"status": "NOT_RELEVANT", "question": question}
    facts_payload = load_price_truth_facts()
    answer = resolve_temporal_truth(
        question_class,
        facts_payload["facts"],
        subject_ref=subject_ref,
        as_of=as_of or date.today().isoformat(),
    )
    claim_audit = audit_temporal_truth_answer(answer)
    direct = answer["direct_answer"]
    if direct.get("value_known") is True:
        typed = direct.get("typed_value") or {}
        minor = typed.get("minor_units")
        currency = typed.get("currency")
        direct_text = (
            f"Current recorded {typed.get('kind') or 'value'}: {currency} {minor / 100:,.2f}."
            if type(minor) is int and currency
            else "A current typed value is recorded; see trace."
        )
    else:
        direct_text = "Current exact pricing is not declared; the present posture is custom and provisional."
    if answer["historical_context"]:
        direct_text += " Historical observations are shown separately and are not current rates."
    return {
        "schema_version": "price_truth_temporal_packet_v1",
        "status": (
            "TRACE_READY_NOT_SHIPPED"
            if claim_audit["status"] == "PASS"
            else "TRACE_BLOCKED_CLAIM_AUDIT"
        ),
        "intent_class": "price_truth_temporal",
        "question": question,
        "question_class": question_class,
        "subject_ref": subject_ref,
        "answer_text": direct_text,
        "temporal_truth_answer": answer,
        "claim_audit": claim_audit,
        "source_refs": [
            str(facts_payload["source_sha256"]),
            "gig_business_doctrine:v1.2",
        ],
        "ship_gate": "MAC_COMPUTER_USE_STRESS_TEST_REQUIRED",
        "action_surfaces_opened": False,
    }


__all__ = ["build_price_truth_packet", "classify_price_truth_question"]
