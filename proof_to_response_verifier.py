"""Deterministic verifier for proof-to-response LM shadow drafts.

The verifier is the publish gate. An LM draft is treated as phrasing only; it
does not become truth, does not grant authority, and cannot promise protected
actions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import proof_bundle_builder as bundles
import proof_to_response_tdd_spec as proof_spec


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

READY_STATUS = "VERIFIED_FOR_SHADOW_PUBLISH"
BLOCKED_STATUS = "BLOCKED_BY_DETERMINISTIC_VERIFIER"

REQUIRED_SHADOW_RESPONSE_FIELDS = (
    "response_id",
    "proof_bundle_id",
    "speaker_ref",
    "draft_headline",
    "draft_body",
    "draft_next_step",
    "claimed_facts",
    "implied_actions",
    "requested_controls",
    "uncertainty_notes",
)

MACHINE_CONTRACT_JARGON = proof_spec.MACHINE_CONTRACT_JARGON

PROTECTED_ACTIONS = {
    "email_send",
    "send_email",
    "coupa_submit",
    "submit_coupa",
    "portal_submit",
    "ledger_mutation",
    "mutate_ledger",
    "ledger_post",
    "mark_paid",
    "paid_marking",
    "workbook_mutation",
    "pdf_export",
    "merge",
    "push",
    "spawn_worker",
    "worker_spawn",
}

SAFE_NEGATIVE_CONTEXTS = (
    "does not mark paid",
    "not paid",
    "no paid",
    "cannot mark paid",
    "cannot send",
    "will not mark this paid",
    "not mark this paid",
    "not touch the ledger",
    "will not touch the ledger",
    "no send",
    "not send",
    "nothing gets sent",
    "will not send",
    "cannot submit",
    "no submit",
    "blocked until",
    "ledger stays untouched",
    "ledger remains untouched",
    "ledger untouched",
    "ledger was not changed",
    "no ledger",
    "no merge",
    "no push",
)

NEGATIVE_CONTEXTS_BY_COMPLETION = {
    "paid": (
        "does not mark paid",
        "not paid",
        "no paid",
        "cannot mark paid",
        "cannot mark this paid",
        "cannot mark it paid",
        "not mark paid",
        "not mark this paid",
        "will not mark this paid",
    ),
    "sent": (
        "cannot send",
        "no send",
        "not send",
        "nothing gets sent",
        "will not send",
    ),
    "submitted": (
        "cannot submit",
        "no submit",
        "not submit",
    ),
    "executed": (
        "blocked until",
        "no execution",
        "not executed",
    ),
    "ledger": (
        "ledger stays untouched",
        "ledger remains untouched",
        "ledger untouched",
        "ledger was not changed",
        "no ledger",
    ),
}

UNSAFE_COMPLETION_PHRASES = (
    "has been paid",
    "is paid",
    "marked paid",
    "i sent",
    "sent the",
    "was sent",
    "has been sent",
    "submitted",
    "has been submitted",
    "approved and executed",
    "executed",
    "ledger updated",
    "ledger changed",
)

COMPLETION_PHRASE_CATEGORIES = {
    "has been paid": "paid",
    "is paid": "paid",
    "marked paid": "paid",
    "i sent": "sent",
    "sent the": "sent",
    "was sent": "sent",
    "has been sent": "sent",
    "submitted": "submitted",
    "has been submitted": "submitted",
    "approved and executed": "executed",
    "executed": "executed",
    "ledger updated": "ledger",
    "ledger changed": "ledger",
}

PROMISE_PHRASES_BY_ACTION = {
    "email_send": ("i will send", "will send", "i can send", "send it now"),
    "coupa_submit": ("i will submit", "will submit", "i can submit", "submit in coupa", "submit this in coupa"),
    "ledger_mutation": ("i will update the ledger", "will update the ledger", "touch the ledger", "change the ledger"),
    "mark_paid": ("i will mark paid", "will mark paid", "mark it paid", "mark paid now"),
    "merge": ("i will merge", "will merge"),
    "push": ("i will push", "will push"),
    "spawn_worker": ("spawn a worker", "will spawn"),
}

UNSAFE_TRUE_KEYS = {
    "protected_actions_allowed",
    "authority_granted",
    "authority_grant_allowed",
    "business_action_allowed",
    "business_action_performed",
    "paid",
    "paid_marking_allowed",
    "paid_marking_performed",
    "ledger_mutation_allowed",
    "ledger_mutation_performed",
    "ledger_posting_allowed",
    "email_send_allowed",
    "email_send_performed",
    "coupa_allowed",
    "coupa_submit_performed",
    "portal_submit_allowed",
    "workbook_mutation_allowed",
    "workbook_mutation_performed",
    "pdf_export_allowed",
    "pdf_export_performed",
    "git_push_allowed",
    "git_push_performed",
    "merge_allowed",
    "merge_performed",
    "worker_spawn_allowed",
    "worker_spawn_performed",
    "external_llm_invoked",
    "local_model_runtime_connected",
    "external_action_allowed",
    "incoming_authority_granted_accepted",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _primary_text(response: Mapping[str, Any]) -> str:
    return " ".join(
        [
            str(response.get("draft_headline") or ""),
            str(response.get("draft_body") or ""),
            str(response.get("draft_next_step") or ""),
        ]
    ).lower()


def _contains_negative_context(text: str) -> bool:
    return any(negative in text for negative in SAFE_NEGATIVE_CONTEXTS)


def _known_fact_ids(bundle: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for fact in bundle.get("known_facts") or []:
        if isinstance(fact, Mapping) and fact.get("fact_id"):
            ids.add(str(fact["fact_id"]))
    return ids


def _allowed_controls(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    controls: dict[str, Mapping[str, Any]] = {}
    for control in bundle.get("allowed_response_controls") or []:
        if isinstance(control, Mapping) and control.get("label"):
            controls[str(control["label"])] = control
    return controls


def _next_step_allowed(next_step: str, allowed_labels: set[str], scenario_id: str) -> bool:
    if next_step in allowed_labels:
        return True
    lowered = next_step.lower()
    if any(label.lower() in lowered for label in allowed_labels):
        return True
    if scenario_id == "unknown_context" and "world" in lowered and ("thread" in lowered or "lane" in lowered):
        return True
    return False


def response_is_concise(response: Mapping[str, Any]) -> bool:
    headline = str(response.get("draft_headline") or "")
    body = str(response.get("draft_body") or "")
    next_step = str(response.get("draft_next_step") or "")
    paragraphs = [part for part in body.split("\n\n") if part.strip()]
    sentence_count = sum(body.count(mark) for mark in ".!?")
    return (
        bool(headline)
        and "\n" not in headline
        and len(headline) <= 90
        and len(paragraphs) <= 2
        and len(body) <= 280
        and sentence_count <= 4
        and bool(next_step)
        and len(next_step) <= 120
    )


def _required_phrase_errors(response: Mapping[str, Any], bundle: Mapping[str, Any]) -> list[str]:
    scenario_id = str(bundle.get("scenario_id") or "")
    text = _primary_text(response)
    errors: list[str] = []
    required_by_scenario = {
        "finance_capital_hilton_payment_watch": ("payment evidence", "ledger"),
        "finance_capital_hilton_attach_proof_explanation": ("candidate", "paid", "ledger"),
        "finance_live_arts_payment_evidence": ("evidence", "paid"),
        "business_development_capital_hilton_followup": ("stage", "send"),
        "build_review_packet": ("merge", "push"),
        "unknown_context": ("world", "thread"),
        "protected_coupa_ledger_email_request": ("blocked", "proof", "approval"),
    }
    for phrase in required_by_scenario.get(scenario_id, ()):
        if phrase not in text:
            errors.append(f"required_phrase_missing:{phrase}")
    return errors


def unsupported_completion_claims(response: Mapping[str, Any]) -> list[str]:
    text = _primary_text(response)
    failures: list[str] = []
    for phrase in UNSAFE_COMPLETION_PHRASES:
        category = COMPLETION_PHRASE_CATEGORIES.get(phrase, "executed")
        negatives = NEGATIVE_CONTEXTS_BY_COMPLETION.get(category, ())
        if phrase in text and not any(negative in text for negative in negatives):
            failures.append(phrase)
    return failures


def protected_action_promises(response: Mapping[str, Any]) -> list[str]:
    text = _primary_text(response)
    actions = {str(action) for action in response.get("implied_actions") or [] if str(action)}
    failures = sorted(action for action in actions if action in PROTECTED_ACTIONS)
    for action, phrases in PROMISE_PHRASES_BY_ACTION.items():
        if any(phrase in text for phrase in phrases) and not _contains_negative_context(text):
            failures.append(action)
    return sorted(set(failures))


def machine_jargon_terms(response: Mapping[str, Any]) -> list[str]:
    text = _primary_text(response)
    return sorted(term for term in MACHINE_CONTRACT_JARGON if term in text)


def _validate_requested_controls(response: Mapping[str, Any], bundle: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = _allowed_controls(bundle)
    for label in response.get("requested_controls") or []:
        control = allowed.get(str(label))
        if control is None:
            errors.append(f"requested_control_not_allowed:{label}")
            continue
        event_type = str(control.get("controller_event_type") or "")
        if event_type not in bundles.SAFE_CONTROLLER_EVENTS:
            errors.append(f"requested_control_unsafe_event:{label}:{event_type}")
        boundary = control.get("authority_boundary")
        if not isinstance(boundary, Mapping) or boundary.get("protected_actions_allowed") is not False:
            errors.append(f"requested_control_boundary_not_false:{label}")
    next_step = str(response.get("draft_next_step") or "")
    if not _next_step_allowed(next_step, set(allowed), str(bundle.get("scenario_id") or "")):
        errors.append(f"next_step_not_allowed:{next_step}")
    return errors


def verify_lm_shadow_response(
    lm_response: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    errors: list[str] = []
    for field in REQUIRED_SHADOW_RESPONSE_FIELDS:
        if field not in lm_response:
            errors.append(f"missing_field:{field}")
    if lm_response.get("proof_bundle_id") != proof_bundle.get("proof_bundle_id"):
        errors.append("proof_bundle_id_mismatch")
    if lm_response.get("speaker_ref") != proof_bundle.get("response_speaker_ref"):
        errors.append(f"speaker_ref_mismatch:{lm_response.get('speaker_ref')}")
    if lm_response.get("details_collapsed") is False:
        errors.append("details_not_collapsed")
    if not response_is_concise(lm_response):
        errors.append("response_not_concise")
    errors.extend(f"machine_contract_jargon:{term}" for term in machine_jargon_terms(lm_response))
    errors.extend(f"unsupported_completion_claim:{claim}" for claim in unsupported_completion_claims(lm_response))
    errors.extend(f"protected_action_promise:{action}" for action in protected_action_promises(lm_response))
    known_fact_ids = _known_fact_ids(proof_bundle)
    for fact_id in lm_response.get("claimed_facts") or []:
        if str(fact_id) not in known_fact_ids:
            errors.append(f"claimed_fact_not_in_bundle:{fact_id}")
    errors.extend(_required_phrase_errors(lm_response, proof_bundle))
    errors.extend(_validate_requested_controls(lm_response, proof_bundle))
    errors.extend(f"proof_bundle:{error}" for error in bundles.validate_proof_bundle(proof_bundle, read_model_root=read_model_root))
    publishable = not errors
    result = {
        "verifier_id": "proof_to_response_verifier_v0",
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "response_id": str(lm_response.get("response_id") or ""),
        "status": READY_STATUS if publishable else BLOCKED_STATUS,
        "publishable": publishable,
        "verification_errors": errors,
        "rewrite_request": "" if publishable else _rewrite_request(errors),
        "safe_fallback_response": None if publishable else safe_fallback_response(proof_bundle, reason="; ".join(errors[:3])),
        "details_collapsed": True,
        "authority_boundary": {"protected_actions_allowed": False},
        "business_action_performed": False,
        "paid_marking_performed": False,
        "ledger_mutation_performed": False,
        "email_send_performed": False,
        "coupa_submit_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "worker_spawn_performed": False,
        "external_llm_invoked": False,
        "local_model_runtime_connected": False,
    }
    unsafe = unsafe_true_grants(result)
    result["unsafe_true_grants"] = unsafe
    if unsafe:
        result["status"] = BLOCKED_STATUS
        result["publishable"] = False
    return result


def _rewrite_request(errors: list[str]) -> str:
    return "Rewrite using only bundle facts, no execution claims, concise body, and allowed next step. Errors: " + ", ".join(errors)


def safe_fallback_response(proof_bundle: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    scenario_id = str(proof_bundle.get("scenario_id") or "")
    if scenario_id == "unknown_context":
        headline = "Needs lane context"
        body = "Which world and thread should I use for this?"
        next_step = "Pick the world and thread"
        claimed = ["lane_context_missing"]
        controls = ["Choose lane"] if "Choose lane" in _allowed_controls(proof_bundle) else []
    elif "protected" in scenario_id:
        headline = "Blocked until proof and approval"
        body = "This protected action stays blocked until the required proof and approval are present."
        next_step = "Prepare approval"
        claimed = ["protected_action_blocked", "proof_and_approval_required"]
        controls = ["Prepare approval"] if "Prepare approval" in _allowed_controls(proof_bundle) else []
    else:
        headline = "Needs verification"
        body = "I need stronger proof before I can publish a response."
        next_step = "Show details"
        claimed = []
        controls = ["Show details"] if "Show details" in _allowed_controls(proof_bundle) else []
    return {
        "response_id": f"lm_shadow_response:fallback:{scenario_id or 'unknown'}",
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "openclaw"),
        "draft_headline": headline,
        "draft_body": body,
        "draft_next_step": next_step,
        "claimed_facts": claimed,
        "implied_actions": [],
        "requested_controls": controls,
        "uncertainty_notes": [reason],
    }
