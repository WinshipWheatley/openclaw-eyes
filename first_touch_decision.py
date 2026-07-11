"""One reusable pre-dispatch decision seam for operator turns.

Task 162 establishes the seam with the deterministic refusal family only.
Later contract work extends this module; it must not install a competing tap.
The seam is transport-neutral, calls no model, grants no authority, and writes
only the existing append-only refusal audit receipt when a refusal is handled.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping

import operator_refusal_guard


SCHEMA_VERSION = "first_touch_decision_v1"
RECEIPT_TYPE = "first_touch_decision_receipt"


@dataclass(frozen=True)
class FirstTouchDecision:
    handled: bool
    label: str
    action: str
    reply: str
    agent: str
    surface: str
    receipt: Mapping[str, Any]


@dataclass(frozen=True)
class FirstTouchOutcome:
    attempted: bool
    handled: bool
    decision: FirstTouchDecision | None
    receipt: Mapping[str, Any]
    status: str


def _decision_id(guard_receipt: Mapping[str, Any]) -> str:
    material = "|".join(
        (
            str(guard_receipt.get("guard_version") or ""),
            str(guard_receipt.get("agent") or ""),
            str(guard_receipt.get("surface") or ""),
            str(guard_receipt.get("reason_class") or ""),
            str(guard_receipt.get("text_sha256") or ""),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return "first_touch:" + "-".join(
        digest[index : index + 4] for index in range(0, 20, 4)
    )


def _pass_through_receipt(
    text: str,
    *,
    agent: str,
    surface: str,
    attempted: bool,
    status: str,
) -> dict[str, Any]:
    text_sha256 = hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()
    agent_key = str(agent or "maestro").strip().lower() or "maestro"
    surface_key = str(surface or "")
    identity = {
        "guard_version": operator_refusal_guard.GUARD_VERSION,
        "agent": agent_key,
        "surface": surface_key,
        "reason_class": "pass_through",
        "text_sha256": text_sha256,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": RECEIPT_TYPE,
        "decision_id": _decision_id(identity),
        "attempted": attempted,
        "handled": False,
        "label": "pass_through",
        "action": "continue",
        "agent": agent_key,
        "surface": surface_key,
        "guard_evaluation_status": status,
        "text_sha256": text_sha256,
        "refusal_receipt_append_performed": False,
        "refusal_receipt_persistence_status": "not_applicable",
        "file_mutation_performed": False,
        "model_called": False,
        "model_call_performed": False,
        "workflow_package_staged": False,
        "queue_sqlite_mutated": False,
        "business_or_domain_store_write_performed": False,
        "session_state_mutated": False,
        "worker_dispatch_performed": False,
        "external_action_performed": False,
    }


def _evaluate_guard(
    text: str,
    *,
    agent: str,
    surface: str,
    allow_informational_money: bool,
) -> tuple[Any | None, str]:
    original = str(text or "")
    candidate = original
    original_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
    for _attempt in range(32):
        decision = operator_refusal_guard.evaluate_operator_refusal(
            candidate,
            agent=agent,
            surface=surface,
        )
        if decision is None:
            status = (
                "evaluated_informational_money_exemption"
                if candidate != original
                else "evaluated"
            )
            return None, status
        if (
            decision.reason_class != operator_refusal_guard.REASON_MONEY
            or not allow_informational_money
        ):
            if candidate != original:
                decision.receipt["text_sha256"] = original_hash
            return decision, "evaluated"
        previous = candidate
        for matched in decision.matched:
            candidate = re.sub(
                re.escape(str(matched)),
                " ",
                candidate,
                count=1,
                flags=re.IGNORECASE,
            )
        if candidate == previous:
            return None, "evaluated_informational_money_exemption"
    # Exhaustion can never mint a pass marker.  A long adversarial compound
    # may put another informational-money hit ahead of a destructive clause;
    # fail closed on whatever guard class remains after the bounded masks.
    remaining = operator_refusal_guard.evaluate_operator_refusal(
        candidate,
        agent=agent,
        surface=surface,
    )
    if remaining is not None:
        remaining.receipt["text_sha256"] = original_hash
        return remaining, "evaluated"
    return None, "evaluated_informational_money_exemption"


def attempt_first_touch(
    text: str,
    *,
    agent: str,
    surface: str = "",
    allow_informational_money: bool = False,
) -> FirstTouchOutcome:
    """Attempt the shared first tap and return a cacheable, hash-bound outcome."""

    try:
        guard_decision, evaluation_status = _evaluate_guard(
            text,
            agent=agent,
            surface=surface,
            allow_informational_money=allow_informational_money,
        )
    except Exception:
        receipt = _pass_through_receipt(
            text,
            agent=agent,
            surface=surface,
            attempted=False,
            status="classification_error_fail_open",
        )
        return FirstTouchOutcome(
            attempted=False,
            handled=False,
            decision=None,
            receipt=receipt,
            status="classification_error_fail_open",
        )

    if guard_decision is None:
        receipt = _pass_through_receipt(
            text,
            agent=agent,
            surface=surface,
            attempted=True,
            status=evaluation_status,
        )
        return FirstTouchOutcome(
            attempted=True,
            handled=False,
            decision=None,
            receipt=receipt,
            status="pass_through",
        )

    try:
        receipt_path = operator_refusal_guard.log_refusal_receipt(guard_decision)
    except Exception:
        receipt_path = None
    guard_receipt = dict(guard_decision.receipt)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": RECEIPT_TYPE,
        "decision_id": _decision_id(guard_receipt),
        "attempted": True,
        "handled": True,
        "label": "refusal",
        "action": "refuse",
        "agent": guard_decision.agent,
        "surface": guard_decision.surface,
        "reason_class": guard_decision.reason_class,
        "gate": guard_decision.gate,
        "guard_receipt": guard_receipt,
        "refusal_receipt_append_performed": receipt_path is not None,
        "refusal_receipt_persistence_status": (
            "appended" if receipt_path is not None else "append_failed"
        ),
        "file_mutation_performed": receipt_path is not None,
        "model_called": False,
        "model_call_performed": False,
        "workflow_package_staged": False,
        "queue_sqlite_mutated": False,
        "business_or_domain_store_write_performed": False,
        "session_state_mutated": False,
        "worker_dispatch_performed": False,
        "external_action_performed": False,
    }
    decision = FirstTouchDecision(
        handled=True,
        label="refusal",
        action="refuse",
        reply=guard_decision.refusal_text,
        agent=guard_decision.agent,
        surface=guard_decision.surface,
        receipt=receipt,
    )
    return FirstTouchOutcome(
        attempted=True,
        handled=True,
        decision=decision,
        receipt=receipt,
        status="handled",
    )


def valid_pass_through_marker(
    marker: Mapping[str, Any] | None,
    *,
    text: str,
    agent: str,
) -> bool:
    if not isinstance(marker, Mapping):
        return False
    if marker.get("receipt_type") != RECEIPT_TYPE:
        return False
    if marker.get("attempted") is not True or marker.get("handled") is not False:
        return False
    if str(marker.get("guard_evaluation_status") or "") not in {
        "evaluated",
        "evaluated_informational_money_exemption",
    }:
        return False
    if str(marker.get("agent") or "").strip().lower() != str(agent or "").strip().lower():
        return False
    expected_hash = hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()
    return str(marker.get("text_sha256") or "") == expected_hash


def rebind_pass_through_marker(
    marker: Mapping[str, Any] | None,
    *,
    source_text: str,
    target_text: str,
    agent: str,
    surface: str,
) -> dict[str, Any] | None:
    """Derive a marker for a deterministic adapter normalization.

    Rebinding is allowed only from an already valid source marker.  This lets
    an adapter strip its own address prefix without either trusting an
    arbitrary boolean or rerunning the refusal classifier.
    """

    if not valid_pass_through_marker(marker, text=source_text, agent=agent):
        return None
    rebound = dict(marker or {})
    rebound["surface"] = str(surface or "")
    rebound["text_sha256"] = hashlib.sha256(
        str(target_text or "").encode("utf-8")
    ).hexdigest()
    rebound["derived_from_decision_id"] = str(rebound.get("decision_id") or "")
    rebound["decision_id"] = _decision_id(
        {
            "guard_version": operator_refusal_guard.GUARD_VERSION,
            "agent": str(agent or "").strip().lower(),
            "surface": rebound["surface"],
            "reason_class": "pass_through_rebound",
            "text_sha256": rebound["text_sha256"],
        }
    )
    return rebound


def decide_first_touch(
    text: str,
    *,
    agent: str,
    surface: str = "",
    allow_informational_money: bool = False,
) -> FirstTouchDecision | None:
    """Compatibility wrapper returning only a handled refusal decision."""

    outcome = attempt_first_touch(
        text,
        agent=agent,
        surface=surface,
        allow_informational_money=allow_informational_money,
    )
    return outcome.decision


__all__ = [
    "FirstTouchDecision",
    "FirstTouchOutcome",
    "attempt_first_touch",
    "decide_first_touch",
    "rebind_pass_through_marker",
    "valid_pass_through_marker",
]
