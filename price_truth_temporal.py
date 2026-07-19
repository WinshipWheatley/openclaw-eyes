"""Pure three-axis temporal truth resolver for the pricing vertical slice.

This module is read-only. It cannot quote, send, schedule, activate a regime,
or grant action authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


TIME_DOMAINS = frozenset(
    {"HISTORICAL_OBSERVED", "CURRENT_DECLARED", "CURRENT_PROVISIONAL", "FUTURE_TRIGGER"}
)
COMPARISON_DIMENSIONS = (
    "job_type",
    "duration_minutes",
    "personnel",
    "scope",
    "location",
    "production",
    "client_event_class",
)
ROOT = Path(__file__).resolve().parent
DEFAULT_FACTS_PATH = ROOT / "config/price_truth_facts.v1.json"


@dataclass(frozen=True)
class TemporalTruthFact:
    fact_ref: str
    subject_ref: str
    metric_ref: str
    value_known: bool
    typed_value: Any
    time_domain: str
    valid_from: str
    valid_until: str | None
    observed_at: str
    evidence_as_of: str
    freshness_policy: str
    freshness_status: str
    authority_status: str
    operator_authority_ref: str
    regime_ref: str
    transition_event_ref: str
    transition_status: str
    transition_requires_operator: bool
    comparison_signature: Mapping[str, Any]
    source_refs: tuple[str, ...]
    source_hashes: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TemporalTruthFact":
        fact = cls(
            fact_ref=str(value.get("fact_ref") or ""),
            subject_ref=str(value.get("subject_ref") or ""),
            metric_ref=str(value.get("metric_ref") or ""),
            value_known=value.get("value_known") is True,
            typed_value=value.get("typed_value"),
            time_domain=str(value.get("time_domain") or ""),
            valid_from=str(value.get("valid_from") or ""),
            valid_until=str(value.get("valid_until")) if value.get("valid_until") else None,
            observed_at=str(value.get("observed_at") or ""),
            evidence_as_of=str(value.get("evidence_as_of") or ""),
            freshness_policy=str(value.get("freshness_policy") or ""),
            freshness_status=str(value.get("freshness_status") or ""),
            authority_status=str(value.get("authority_status") or ""),
            operator_authority_ref=str(value.get("operator_authority_ref") or ""),
            regime_ref=str(value.get("regime_ref") or ""),
            transition_event_ref=str(value.get("transition_event_ref") or ""),
            transition_status=str(value.get("transition_status") or ""),
            transition_requires_operator=value.get("transition_requires_operator") is True,
            comparison_signature=dict(value.get("comparison_signature") or {}),
            source_refs=tuple(str(item) for item in value.get("source_refs") or ()),
            source_hashes=tuple(str(item) for item in value.get("source_hashes") or ()),
        )
        fact.validate()
        return fact

    def validate(self) -> None:
        if not self.fact_ref or not self.subject_ref or not self.metric_ref:
            raise ValueError("fact_ref, subject_ref, and metric_ref are required")
        if self.time_domain not in TIME_DOMAINS:
            raise ValueError(f"unsupported time_domain: {self.time_domain}")
        _date(self.valid_from)
        if self.valid_until:
            _date(self.valid_until)
        if self.value_known and self.typed_value is None:
            raise ValueError("known values require typed_value")
        if not self.source_refs:
            raise ValueError("source_refs are required")

    def as_trace_row(self) -> dict[str, Any]:
        return {
            "fact_ref": self.fact_ref,
            "time_domain": self.time_domain,
            "freshness_status": self.freshness_status,
            "authority_status": self.authority_status,
            "source_refs": list(self.source_refs),
        }

    def as_answer_row(self) -> dict[str, Any]:
        return {
            "fact_ref": self.fact_ref,
            "value_known": self.value_known,
            "typed_value": self.typed_value,
            "posture": self.time_domain,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "evidence_as_of": self.evidence_as_of,
            "freshness_status": self.freshness_status,
            "authority_status": self.authority_status,
            "source_refs": list(self.source_refs),
        }


def _date(value: str) -> date:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _valid_on(fact: TemporalTruthFact, as_of: date) -> bool:
    return _date(fact.valid_from) <= as_of and (
        fact.valid_until is None or as_of <= _date(fact.valid_until)
    )


def _future_activated(fact: TemporalTruthFact, as_of: date) -> bool:
    if fact.time_domain != "FUTURE_TRIGGER" or not _valid_on(fact, as_of):
        return False
    if not fact.transition_requires_operator:
        return fact.transition_status == "OPERATOR_ACTIVATED"
    return bool(
        fact.transition_status == "OPERATOR_ACTIVATED"
        and fact.authority_status == "OPERATOR_ACTIVATED"
        and fact.operator_authority_ref
    )


def _unknown_direct(reason: str) -> dict[str, Any]:
    return {
        "value_known": False,
        "typed_value": None,
        "posture": "CURRENT_VALUE_UNKNOWN",
        "reason": reason,
    }


def _select_current(
    facts: Sequence[TemporalTruthFact], as_of: date
) -> tuple[TemporalTruthFact | None, list[dict[str, str]]]:
    rejected: list[dict[str, str]] = []
    candidates: list[TemporalTruthFact] = []
    for fact in facts:
        if fact.time_domain in {"CURRENT_DECLARED", "CURRENT_PROVISIONAL"}:
            if _valid_on(fact, as_of):
                candidates.append(fact)
            else:
                rejected.append({"fact_ref": fact.fact_ref, "reason": "not_valid_as_of"})
        elif fact.time_domain == "FUTURE_TRIGGER":
            if _future_activated(fact, as_of):
                candidates.append(fact)
            else:
                rejected.append({"fact_ref": fact.fact_ref, "reason": "future_transition_not_operator_activated"})
    if not candidates:
        return None, rejected
    order = {"CURRENT_DECLARED": 0, "CURRENT_PROVISIONAL": 1, "FUTURE_TRIGGER": 2}
    candidates.sort(key=lambda item: (order[item.time_domain], item.valid_from, item.fact_ref))
    chosen = candidates[0]
    for extra in candidates[1:]:
        reason = "lower_authority_current_candidate"
        if order[extra.time_domain] == order[chosen.time_domain] and extra.typed_value != chosen.typed_value:
            reason = "conflicting_current_value"
        rejected.append({"fact_ref": extra.fact_ref, "reason": reason})
    return chosen, rejected


def _signature_comparison(
    current: TemporalTruthFact | None, historical: TemporalTruthFact | None
) -> dict[str, Any]:
    if current is None or historical is None:
        return {
            "comparable": False,
            "growth_claim_allowed": False,
            "missing_dimensions": list(COMPARISON_DIMENSIONS),
            "mismatched_dimensions": [],
            "direction": "unknown",
        }
    missing = [
        key
        for key in COMPARISON_DIMENSIONS
        if key not in current.comparison_signature
        or key not in historical.comparison_signature
        or current.comparison_signature.get(key) in (None, "", [], {})
        or historical.comparison_signature.get(key) in (None, "", [], {})
    ]
    mismatched = [
        key
        for key in COMPARISON_DIMENSIONS
        if key not in missing
        and current.comparison_signature.get(key) != historical.comparison_signature.get(key)
    ]
    comparable = not missing and not mismatched
    direction = "unknown"
    if comparable and current.value_known and historical.value_known:
        current_minor = (current.typed_value or {}).get("minor_units")
        history_minor = (historical.typed_value or {}).get("minor_units")
        current_currency = (current.typed_value or {}).get("currency")
        history_currency = (historical.typed_value or {}).get("currency")
        if type(current_minor) is int and type(history_minor) is int and current_currency == history_currency:
            direction = "higher" if current_minor > history_minor else "lower" if current_minor < history_minor else "unchanged"
        else:
            comparable = False
    return {
        "comparable": comparable,
        "growth_claim_allowed": comparable and direction != "unknown",
        "missing_dimensions": missing,
        "mismatched_dimensions": mismatched,
        "direction": direction,
    }


def resolve_temporal_truth(
    question_class: str,
    rows: Sequence[Mapping[str, Any] | TemporalTruthFact],
    *,
    subject_ref: str,
    as_of: str,
) -> dict[str, Any]:
    question = str(question_class or "").upper()
    if question not in {"C1", "C2", "C3", "C4"}:
        raise ValueError("question_class must be C1, C2, C3, or C4")
    as_of_date = _date(as_of)
    facts = [row if isinstance(row, TemporalTruthFact) else TemporalTruthFact.from_mapping(row) for row in rows]
    relevant = [fact for fact in facts if fact.subject_ref == subject_ref]
    rejected = [
        {"fact_ref": fact.fact_ref, "reason": "subject_mismatch"}
        for fact in facts
        if fact.subject_ref != subject_ref
    ]
    current, current_rejected = _select_current(relevant, as_of_date)
    rejected.extend(current_rejected)
    historical = sorted(
        [fact for fact in relevant if fact.time_domain == "HISTORICAL_OBSERVED"],
        key=lambda item: (item.valid_from, item.fact_ref),
        reverse=True,
    )
    direct = current.as_answer_row() if current is not None else _unknown_direct("no current declared or provisional value")
    if current is not None and current.time_domain == "FUTURE_TRIGGER":
        direct["posture"] = "CURRENT_OPERATOR_ACTIVATED_REGIME"
    comparison = _signature_comparison(current, historical[0] if historical else None)
    if question == "C2" and historical and not comparison["comparable"]:
        rejected.append({"fact_ref": historical[0].fact_ref, "reason": "comparison_signature_mismatch"})
    selected_refs = ([current.fact_ref] if current is not None else []) + [fact.fact_ref for fact in historical]
    axis_report = [
        {
            "fact_ref": fact.fact_ref,
            "semantic_time": fact.time_domain,
            "evidence_freshness": fact.freshness_status,
            "authority_state": fact.authority_status,
            "current_rate_claim_allowed": fact is current and fact.time_domain != "HISTORICAL_OBSERVED",
        }
        for fact in relevant
    ]
    future = next((fact for fact in relevant if fact.time_domain == "FUTURE_TRIGGER"), None)
    transition = {
        "event_ref": future.transition_event_ref if future else "",
        "status": future.transition_status if future else "",
        "requires_operator": future.transition_requires_operator if future else False,
        "activated": bool(future and _future_activated(future, as_of_date)),
        "operator_authority_ref": future.operator_authority_ref if future else "",
    }
    return {
        "schema_version": "price_truth_temporal_answer_v1",
        "question_class": question,
        "subject_ref": subject_ref,
        "as_of": as_of_date.isoformat(),
        "direct_answer": direct,
        "historical_context": [fact.as_answer_row() for fact in historical],
        "axis_report": axis_report,
        "comparison": comparison,
        "transition": transition,
        "trace": {
            "selected_fact_refs": selected_refs,
            "rejected_facts": rejected,
            "selected_fact_traces": [fact.as_trace_row() for fact in relevant if fact.fact_ref in selected_refs],
        },
        "authority_boundary": {
            "quote_staged": False,
            "email_sent": False,
            "calendar_written": False,
            "regime_activated": False,
            "doctrine_edited": False,
        },
        "machine_proof": {
            "semantic_time_axis_present": True,
            "evidence_freshness_axis_present": True,
            "authority_state_axis_present": True,
            "historical_promoted_to_current": False,
            "time_domains_blended": False,
            "selected_and_rejected_trace_present": True,
        },
    }


def load_price_truth_facts(path: str | Path = DEFAULT_FACTS_PATH) -> dict[str, Any]:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "price_truth_fact_set_v1":
        raise ValueError("unexpected price truth fact-set schema")
    if payload.get("doctrine_ref") != "gig_business_doctrine:v1.2":
        raise ValueError("price facts are not bound to doctrine v1.2")
    rows = payload.get("facts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("price truth fact set is empty")
    facts = [TemporalTruthFact.from_mapping(row) for row in rows]
    refs = [fact.fact_ref for fact in facts]
    if len(refs) != len(set(refs)):
        raise ValueError("duplicate price truth fact_ref")
    return {
        **payload,
        "facts": facts,
        "source_sha256": "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest(),
    }


__all__ = [
    "COMPARISON_DIMENSIONS",
    "TemporalTruthFact",
    "load_price_truth_facts",
    "resolve_temporal_truth",
]
