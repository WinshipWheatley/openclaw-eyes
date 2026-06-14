"""Conversational Action Covenant Interrupter v0.

This deterministic read-model interrupts natural chat approvals before they can
be mistaken for authority. Casual phrases such as "go ahead", "send it", or
"looks right" are classified against context, risk, and pending covenant state.
High-consequence actions require a concrete Action Covenant and exact approval
phrase before any future execution lane could proceed.

This module does not authorize actions, execute actions, send email, submit to
Coupa, open browsers, mutate files, reveal secrets, run workflows, dispatch
agents, access credentials, ingest raw bodies, mutate Mission Control Swift, run
Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "conversational_action_covenant_interrupter_v0"
READ_MODEL_ID = "conversational_action_covenant_interrupter"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_ACTION_COVENANT_INTERRUPTER"

NORMALIZED_INTENTS = (
    "CONTINUE_CONVERSATION",
    "CONFIRM_DRAFT_UNDERSTANDING",
    "PREPARE_PACKAGE",
    "TEST_PACKAGE",
    "APPROVE_GATED_ACTION",
    "SEND_OR_SUBMIT_REQUEST",
    "MUTATE_FILE_REQUEST",
    "REVEAL_SECRET_REQUEST",
    "UNKNOWN_NEEDS_FRAMING",
)

RISK_LEVELS = (
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    "UNKNOWN_FAIL_CLOSED",
)

REQUESTED_ACTIONS = (
    "SEND_EMAIL",
    "SUBMIT_COUPA",
    "CREATE_GMAIL_DRAFT",
    "GENERATE_INVOICE_ARTIFACT",
    "ATTACH_FILE",
    "MUTATE_FILE",
    "OPEN_APP_AUTOMATION",
    "REVEAL_SECRET",
    "RUN_WORKFLOW_PACKAGE",
    "TEST_WORKFLOW_PACKAGE",
    "UNKNOWN_FAIL_CLOSED",
)

DECISION_STATUSES = (
    "ALLOWED_LOW_RISK_CONTINUE",
    "NEEDS_COVENANT",
    "NEEDS_EXACT_APPROVAL",
    "NEEDS_GUARDIAN_REVIEW",
    "BLOCKED_MISSING_PROOF",
    "BLOCKED_AMBIGUOUS_INTENT",
    "BLOCKED_EXPIRED_COVENANT",
    "BLOCKED_UNSUPPORTED_ACTION",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "CASUAL_PHRASE_USED_FOR_EXTERNAL_ACTION",
    "NO_PENDING_COVENANT",
    "AMBIGUOUS_APPROVAL",
    "EXACT_SIGNATURE_MISSING",
    "COVENANT_EXPIRED",
    "PROOF_MISSING",
    "GUARDIAN_REQUIRED",
    "UNSUPPORTED_ACTION",
    "EXTERNAL_ACTION_ATTEMPTED",
    "SECRET_REVEAL_ATTEMPTED_WITHOUT_GATE",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_action_authorization_allowed": False,
    "live_action_execution_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_file_mutation_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_approval_submission_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

CASUAL_APPROVAL_PHRASES = (
    "go ahead",
    "do it",
    "send it",
    "looks good",
    "looks right",
    "make it happen",
    "approve",
    "approved",
    "ship it",
    "yes",
)

EXTERNAL_ACTIONS = (
    "SEND_EMAIL",
    "SUBMIT_COUPA",
    "CREATE_GMAIL_DRAFT",
    "ATTACH_FILE",
    "OPEN_APP_AUTOMATION",
    "REVEAL_SECRET",
    "RUN_WORKFLOW_PACKAGE",
)

COMMON_FORBIDDEN_EXECUTION = (
    "email send",
    "Coupa submit",
    "browser automation",
    "file mutation",
    "secret reveal",
    "workflow run",
    "agent dispatch",
    "external action",
)


@dataclass(frozen=True)
class ConversationalActionCovenantInterrupter:
    interrupter_id: str
    doctrine: tuple[str, ...]
    trigger_phrase_policy: tuple[str, ...]
    action_risk_policy: tuple[str, ...]
    covenant_matching_policy: tuple[str, ...]
    approval_phrase_policy: tuple[str, ...]
    exact_signature_policy: tuple[str, ...]
    guardian_policy: tuple[str, ...]
    receipt_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ChatActionIntent:
    intent_id: str
    source_chat_request_ref: str
    operator_phrase: str
    normalized_intent: str
    candidate_action_type: str
    risk_level: str
    matched_pending_covenant_ref: str
    ambiguity_status: str
    approval_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class ActionCovenantRequest:
    covenant_id: str
    source_workflow_ref: str
    source_package_ref: str
    requested_action: str
    action_summary: str
    risk_level: str
    required_inputs: tuple[str, ...]
    required_proofs: tuple[str, ...]
    required_approvals: tuple[str, ...]
    blocked_until: tuple[str, ...]
    exact_approval_phrase: str
    expires_at_policy: str
    operator_visible_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class ActionCovenantDecision:
    decision_id: str
    source_intent_ref: str
    covenant_ref: str
    decision_status: str
    operator_message: str
    why_blocked: str
    how_to_fix: str
    receipt_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class ActionCovenantReceipt:
    receipt_id: str
    covenant_ref: str
    source_intent_ref: str
    decision_ref: str
    operator_phrase: str
    exact_phrase_matched: bool
    approved: bool
    action_authorized: bool
    action_executed: bool
    external_authority: bool
    created_at_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class ActionCovenantBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ConversationalActionCovenantElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: tuple[str, ...]
    what_this_does_not_do_yet: tuple[str, ...]
    how_chat_confirmations_are_interrupted: tuple[str, ...]
    how_covenants_are_created: tuple[str, ...]
    how_exact_approval_works: tuple[str, ...]
    how_external_actions_remain_gated: tuple[str, ...]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _normalize_phrase(phrase: str) -> str:
    return " ".join(str(phrase).strip().split())


def _lower_phrase(phrase: str) -> str:
    return _normalize_phrase(phrase).lower()


def build_interrupter() -> ConversationalActionCovenantInterrupter:
    return ConversationalActionCovenantInterrupter(
        interrupter_id="conversational_action_covenant_interrupter_v0",
        doctrine=(
            "Natural chat approval is not enough for high-consequence actions.",
            "Casual affirmations can continue low-risk conversation but cannot send, submit, mutate, reveal, dispatch, or run workflows.",
            "High-consequence actions require a concrete covenant with action, package, proofs, approvals, expiry, and exact phrase.",
            "Approval text must bind to a specific covenant, not a vague prior conversation.",
            "This lane models gates and receipts only; it grants no live authority.",
        ),
        trigger_phrase_policy=(
            "Treat phrases like go ahead, do it, send it, looks good, make it happen, approve, ship it, and yes as ambiguous until context is known.",
            "If no pending covenant matches, ask what the operator means instead of acting.",
            "If the phrase implies send, submit, mutation, workflow run, or secret reveal, fail closed into covenant creation.",
        ),
        action_risk_policy=(
            "LOW: conversational continuation and draft-understanding confirmation.",
            "MEDIUM: package preparation and local test package requests with existing rails.",
            "HIGH: send, submit, attach, app automation, generated artifacts, and workflow-package runs.",
            "CRITICAL: secret reveal, destructive file mutation, unsupported deletion, external authority, and ambiguous high-impact requests.",
        ),
        covenant_matching_policy=(
            "Match only by explicit pending covenant ref or exact approval phrase.",
            "A prior chat summary is not a covenant.",
            "An expired covenant cannot be matched.",
            "If multiple scopes could match, mark ambiguity and ask the operator to pick.",
        ),
        approval_phrase_policy=(
            "Low-risk continuation may proceed without covenant when no external action is implied.",
            "High-risk phrases require exact approval against a covenant.",
            "Model/worker/advisory text cannot approve for the operator.",
        ),
        exact_signature_policy=(
            "Exact phrase shape: APPROVE <REQUESTED_ACTION> <covenant_id>.",
            "Whitespace-normalized exact match is required for gated actions.",
            "The phrase must include the requested action and covenant id.",
        ),
        guardian_policy=(
            "Guardian review may be required for protected evidence, external sends/submits, secret use, and sensitive boundaries.",
            "Guardian requirement is modeled here but not requested or executed.",
            "Guardian approval is not a substitute for proof receipts.",
        ),
        receipt_policy=(
            "Every approval attempt produces a receipt model.",
            "Receipts record whether exact phrase matched, whether v0 allowed approval, and whether any action executed.",
            "In this lane action_authorized, action_executed, and external_authority remain false.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Wire request processor phrases through this interrupter before any future action-capable lane.",
    )


def classify_chat_action_intent(
    operator_phrase: str,
    *,
    source_chat_request_ref: str = "chat_request_fixture",
    context_hint: str = "",
    pending_covenant_ref: str = "",
) -> ChatActionIntent:
    phrase = _normalize_phrase(operator_phrase)
    lowered = _lower_phrase(phrase)
    context = context_hint.lower()

    normalized_intent = "UNKNOWN_NEEDS_FRAMING"
    candidate_action_type = "UNKNOWN_FAIL_CLOSED"
    risk_level = "UNKNOWN_FAIL_CLOSED"
    ambiguity_status = "UNKNOWN"
    approval_required = True
    next_safe_move = "Ask what specific action the operator means."

    if lowered in ("looks right", "looks good") and "draft" in context:
        normalized_intent = "CONFIRM_DRAFT_UNDERSTANDING"
        candidate_action_type = "UNKNOWN_FAIL_CLOSED"
        risk_level = "LOW"
        ambiguity_status = "CLEAR_LOW_RISK"
        approval_required = False
        next_safe_move = "Continue draft-understanding review; do not perform external action."
    elif lowered in ("go ahead", "do it", "yes", "approve", "approved", "ship it"):
        normalized_intent = "APPROVE_GATED_ACTION"
        risk_level = "UNKNOWN_FAIL_CLOSED"
        ambiguity_status = "AMBIGUOUS_NO_PENDING_COVENANT" if not pending_covenant_ref else "PENDING_COVENANT_MAY_MATCH"
        approval_required = True
        next_safe_move = "Ask the operator to name the specific covenant/action or use the exact approval phrase."
    elif lowered in ("send it", "send"):
        normalized_intent = "SEND_OR_SUBMIT_REQUEST"
        candidate_action_type = "SEND_EMAIL"
        risk_level = "HIGH"
        ambiguity_status = "CLEAR_HIGH_RISK_NO_COVENANT" if not pending_covenant_ref else "PENDING_COVENANT_MAY_MATCH"
        approval_required = True
        next_safe_move = "Create or match a SEND_EMAIL covenant; do not send."
    elif "coupa" in lowered and ("submit" in lowered or "send" in lowered):
        normalized_intent = "SEND_OR_SUBMIT_REQUEST"
        candidate_action_type = "SUBMIT_COUPA"
        risk_level = "HIGH"
        ambiguity_status = "CLEAR_HIGH_RISK_NO_COVENANT" if not pending_covenant_ref else "PENDING_COVENANT_MAY_MATCH"
        approval_required = True
        next_safe_move = "Create or match a SUBMIT_COUPA covenant; do not submit."
    elif "password" in lowered or "secret" in lowered or "token" in lowered or "credential" in lowered:
        normalized_intent = "REVEAL_SECRET_REQUEST"
        candidate_action_type = "REVEAL_SECRET"
        risk_level = "CRITICAL"
        ambiguity_status = "CLEAR_CRITICAL_NO_COVENANT"
        approval_required = True
        next_safe_move = "Require protected secret covenant and adapter gate; do not reveal raw secret."
    elif lowered in ("test it", "test package", "run tests") or ("test" in lowered and "package" in context):
        normalized_intent = "TEST_PACKAGE"
        candidate_action_type = "TEST_WORKFLOW_PACKAGE"
        risk_level = "MEDIUM"
        ambiguity_status = "NEEDS_PACKAGE_REF"
        approval_required = False
        next_safe_move = "Run only bounded validation if a package and test rail exist; no external action."
    elif "delete" in lowered or "remove whole" in lowered or "wipe" in lowered:
        normalized_intent = "MUTATE_FILE_REQUEST"
        candidate_action_type = "MUTATE_FILE"
        risk_level = "CRITICAL"
        ambiguity_status = "DESTRUCTIVE_UNSUPPORTED"
        approval_required = True
        next_safe_move = "Block destructive action and ask for scoped non-destructive alternative."
    elif lowered == "make it happen":
        normalized_intent = "PREPARE_PACKAGE"
        candidate_action_type = "RUN_WORKFLOW_PACKAGE"
        risk_level = "MEDIUM"
        ambiguity_status = "NEEDS_PACKAGE_COMPILATION"
        approval_required = True
        next_safe_move = "Compile package/readiness plan; do not execute workflow."

    matched = pending_covenant_ref if pending_covenant_ref else ""
    return ChatActionIntent(
        intent_id=_stable_id("chat_action_intent", source_chat_request_ref, phrase, context_hint, matched),
        source_chat_request_ref=source_chat_request_ref,
        operator_phrase=phrase,
        normalized_intent=normalized_intent,
        candidate_action_type=candidate_action_type,
        risk_level=risk_level,
        matched_pending_covenant_ref=matched,
        ambiguity_status=ambiguity_status,
        approval_required=approval_required,
        next_safe_move=next_safe_move,
    )


def build_covenant_request(
    *,
    covenant_id: str,
    source_workflow_ref: str,
    source_package_ref: str,
    requested_action: str,
    action_summary: str,
    risk_level: str,
    required_inputs: tuple[str, ...],
    required_proofs: tuple[str, ...],
    required_approvals: tuple[str, ...],
    blocked_until: tuple[str, ...],
    expires_at_policy: str = "expires when package/proof context changes or after bounded operator review window",
) -> ActionCovenantRequest:
    exact = f"APPROVE {requested_action} {covenant_id}"
    return ActionCovenantRequest(
        covenant_id=covenant_id,
        source_workflow_ref=source_workflow_ref,
        source_package_ref=source_package_ref,
        requested_action=requested_action,
        action_summary=action_summary,
        risk_level=risk_level,
        required_inputs=required_inputs,
        required_proofs=required_proofs,
        required_approvals=required_approvals,
        blocked_until=blocked_until,
        exact_approval_phrase=exact,
        expires_at_policy=expires_at_policy,
        operator_visible_summary=(
            f"Covenant required for {requested_action}: {action_summary}. "
            f"Exact approval phrase would be `{exact}`."
        ),
        next_safe_move="Show covenant summary to operator and wait for exact phrase; do not execute.",
    )


def decide_action_intent(
    intent: ChatActionIntent,
    *,
    covenant: ActionCovenantRequest | None = None,
    covenant_expired: bool = False,
    proof_missing: bool = False,
    guardian_required: bool = False,
) -> ActionCovenantDecision:
    if intent.risk_level == "LOW" and intent.approval_required is False:
        status = "ALLOWED_LOW_RISK_CONTINUE"
        operator_message = "I can continue with the draft understanding. Nothing external will happen."
        why_blocked = ""
        how_to_fix = "No fix needed for low-risk continuation."
    elif intent.ambiguity_status.startswith("AMBIGUOUS"):
        status = "BLOCKED_AMBIGUOUS_INTENT"
        operator_message = "What should I go ahead with?"
        why_blocked = "The phrase is a casual approval, but no specific covenant/action is bound to it."
        how_to_fix = "Name the specific action or select an existing covenant."
    elif intent.candidate_action_type == "MUTATE_FILE" and intent.risk_level == "CRITICAL":
        status = "BLOCKED_UNSUPPORTED_ACTION"
        operator_message = "I cannot delete or mutate a broad client folder from a casual chat phrase."
        why_blocked = "The requested action is destructive and unsupported by this lane."
        how_to_fix = "Ask for a scoped non-destructive review, backup plan, or metadata-only inventory first."
    elif covenant is None:
        status = "NEEDS_COVENANT"
        operator_message = "I need a concrete Action Covenant before that action can be approved."
        why_blocked = "No pending covenant is bound to this phrase."
        how_to_fix = "Create or choose a covenant that lists the action, package, required proofs, approvals, and exact phrase."
    elif covenant_expired:
        status = "BLOCKED_EXPIRED_COVENANT"
        operator_message = "That covenant is expired."
        why_blocked = "The bounded approval window or source context is stale."
        how_to_fix = "Regenerate the covenant from current package/proof context."
    elif proof_missing:
        status = "BLOCKED_MISSING_PROOF"
        operator_message = "The covenant is missing required proof."
        why_blocked = "Required receipts or artifact references are not present."
        how_to_fix = "Attach or generate the missing proof/readback first."
    elif guardian_required:
        status = "NEEDS_GUARDIAN_REVIEW"
        operator_message = "Guardian review is required before this covenant could proceed."
        why_blocked = "The action touches protected, external, or sensitive authority."
        how_to_fix = "Route the covenant to Guardian review in a future approved lane."
    elif intent.operator_phrase != covenant.exact_approval_phrase:
        status = "NEEDS_EXACT_APPROVAL"
        operator_message = "That phrase is not enough to approve the covenant."
        why_blocked = "The exact covenant approval phrase was not provided."
        how_to_fix = f"Use the exact phrase `{covenant.exact_approval_phrase}` if you mean this covenant."
    else:
        status = "NEEDS_GUARDIAN_REVIEW" if covenant.requested_action in EXTERNAL_ACTIONS else "NEEDS_EXACT_APPROVAL"
        operator_message = "The exact phrase matches, but v0 still does not authorize or execute the action."
        why_blocked = "This lane models approval only; live action authorization is disabled."
        how_to_fix = "Use a future governed execution adapter after Guardian/proof gates exist."

    return ActionCovenantDecision(
        decision_id=_stable_id(
            "action_covenant_decision",
            intent.intent_id,
            covenant.covenant_id if covenant else "",
            status,
        ),
        source_intent_ref=intent.intent_id,
        covenant_ref=covenant.covenant_id if covenant else "",
        decision_status=status,
        operator_message=operator_message,
        why_blocked=why_blocked,
        how_to_fix=how_to_fix,
        receipt_required=True,
        next_safe_move=how_to_fix,
    )


def build_receipt(
    *,
    intent: ChatActionIntent,
    decision: ActionCovenantDecision,
    covenant: ActionCovenantRequest | None = None,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> ActionCovenantReceipt:
    exact_phrase = covenant.exact_approval_phrase if covenant else ""
    exact_matched = bool(exact_phrase and intent.operator_phrase == exact_phrase)
    approved = decision.decision_status == "ALLOWED_LOW_RISK_CONTINUE"
    return ActionCovenantReceipt(
        receipt_id=_stable_id("action_covenant_receipt", intent.intent_id, decision.decision_id, generated_at),
        covenant_ref=covenant.covenant_id if covenant else "",
        source_intent_ref=intent.intent_id,
        decision_ref=decision.decision_id,
        operator_phrase=intent.operator_phrase,
        exact_phrase_matched=exact_matched,
        approved=approved,
        action_authorized=False,
        action_executed=False,
        external_authority=False,
        created_at_policy=generated_at,
        next_safe_move="Keep any future execution blocked until a governed adapter separately authorizes and receipts it.",
    )


def build_blockers() -> tuple[ActionCovenantBlocker, ...]:
    return (
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_casual_external",
            blocker_type="CASUAL_PHRASE_USED_FOR_EXTERNAL_ACTION",
            condition="A phrase like send it, do it, approve, or go ahead is used for external send/submit/mutation.",
            severity="critical",
            elioperator_warning="Casual chat approval cannot authorize external action.",
            fail_closed=True,
            next_safe_move="Create or match an Action Covenant and require exact approval.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_no_pending",
            blocker_type="NO_PENDING_COVENANT",
            condition="Operator approval phrase appears but no pending covenant is bound.",
            severity="high",
            elioperator_warning="There is no pending covenant to approve.",
            fail_closed=True,
            next_safe_move="Ask what action the operator means or create a covenant.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_ambiguous",
            blocker_type="AMBIGUOUS_APPROVAL",
            condition="Operator phrase could refer to multiple packages/actions or no action at all.",
            severity="high",
            elioperator_warning="Ambiguous approval must be clarified.",
            fail_closed=True,
            next_safe_move="Ask the operator to pick the covenant/action.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_exact_signature",
            blocker_type="EXACT_SIGNATURE_MISSING",
            condition="A gated action is requested without the exact covenant approval phrase.",
            severity="critical",
            elioperator_warning="Exact covenant signature is missing.",
            fail_closed=True,
            next_safe_move="Show the exact phrase and wait.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_expired",
            blocker_type="COVENANT_EXPIRED",
            condition="Covenant approval arrives after expiry or after source context changed.",
            severity="high",
            elioperator_warning="Expired covenants cannot be approved.",
            fail_closed=True,
            next_safe_move="Regenerate the covenant from current context.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_proof",
            blocker_type="PROOF_MISSING",
            condition="Required receipt, artifact hash, approval, or protected evidence ref is missing.",
            severity="critical",
            elioperator_warning="Proof is missing.",
            fail_closed=True,
            next_safe_move="Collect the required proof/readback before approval.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_guardian",
            blocker_type="GUARDIAN_REQUIRED",
            condition="Action touches protected evidence, external send/submit, secret use, or sensitive boundary.",
            severity="critical",
            elioperator_warning="Guardian review is required.",
            fail_closed=True,
            next_safe_move="Route to Guardian in a future approved lane.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_unsupported",
            blocker_type="UNSUPPORTED_ACTION",
            condition="Requested action is unsupported, destructive, or not mapped to a safe adapter.",
            severity="critical",
            elioperator_warning="Unsupported high-consequence action is blocked.",
            fail_closed=True,
            next_safe_move="Ask for a scoped, non-destructive alternative.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_external_attempt",
            blocker_type="EXTERNAL_ACTION_ATTEMPTED",
            condition="Any live send, submit, browser, workflow, or external action is attempted in this lane.",
            severity="critical",
            elioperator_warning="External action is blocked.",
            fail_closed=True,
            next_safe_move="Return a blocked decision/readback only.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_secret_reveal",
            blocker_type="SECRET_REVEAL_ATTEMPTED_WITHOUT_GATE",
            condition="Secret reveal or adapter use is requested without protected secret covenant.",
            severity="critical",
            elioperator_warning="Secret reveal requires a protected covenant and adapter gate.",
            fail_closed=True,
            next_safe_move="Use protected secret refs only.",
        ),
        ActionCovenantBlocker(
            blocker_id="action_covenant_blocker_unknown",
            blocker_type="UNKNOWN_FAIL_CLOSED",
            condition="Unknown action phrase, risk, or context.",
            severity="high",
            elioperator_warning="Unknown action approval fails closed.",
            fail_closed=True,
            next_safe_move="Ask for framing.",
        ),
    )


def build_report() -> ConversationalActionCovenantElioperatorReport:
    return ConversationalActionCovenantElioperatorReport(
        report_id="conversational_action_covenant_elioperator_report_v0",
        plain_summary="OpenClaw now has a deterministic interrupter for chat phrases that sound like approval.",
        what_this_enables=(
            "Classify casual confirmation versus gated action intent.",
            "Create covenant requests for high-consequence actions.",
            "Require exact approval phrases bound to specific covenant ids.",
            "Return useful blocked messages with how-to-fix guidance.",
        ),
        what_this_does_not_do_yet=(
            "It does not authorize or execute actions.",
            "It does not send email, submit Coupa, open browsers, mutate files, reveal secrets, run workflows, or dispatch agents.",
            "It does not request live Guardian approval.",
        ),
        how_chat_confirmations_are_interrupted=(
            "Phrases are interpreted against context and risk.",
            "Low-risk draft confirmation can continue.",
            "Ambiguous or high-risk phrases become blocked decisions or covenant requests.",
        ),
        how_covenants_are_created=(
            "A covenant names the workflow/package/action, required inputs, required proofs, required approvals, blocked-until conditions, expiry policy, and exact phrase.",
            "The operator-visible summary explains the action before any approval phrase can matter.",
        ),
        how_exact_approval_works=(
            "The phrase must exactly match APPROVE <REQUESTED_ACTION> <covenant_id>.",
            "A phrase like go ahead, yes, approve, or send it is not accepted for high-consequence action.",
        ),
        how_external_actions_remain_gated=(
            "All live authority flags are false.",
            "Receipts record action_authorized false, action_executed false, and external_authority false.",
            "Future execution adapters must require their own proof/Guardian gates.",
        ),
        next_safe_move="Add this interrupter to request processing before any future action-capable adapter.",
    )


def _example_low_risk(generated_at: str) -> dict[str, Any]:
    intent = classify_chat_action_intent(
        "looks right",
        source_chat_request_ref="chat_request_looks_right_fixture",
        context_hint="Draft understanding review only",
    )
    decision = decide_action_intent(intent)
    receipt = build_receipt(intent=intent, decision=decision, generated_at=generated_at)
    return {"intent": asdict(intent), "decision": asdict(decision), "receipt": asdict(receipt)}


def _example_go_ahead(generated_at: str) -> dict[str, Any]:
    intent = classify_chat_action_intent("go ahead", source_chat_request_ref="chat_request_go_ahead_fixture")
    decision = decide_action_intent(intent)
    receipt = build_receipt(intent=intent, decision=decision, generated_at=generated_at)
    return {"intent": asdict(intent), "decision": asdict(decision), "receipt": asdict(receipt)}


def _example_send_it(generated_at: str) -> dict[str, Any]:
    intent = classify_chat_action_intent("send it", source_chat_request_ref="chat_request_send_it_fixture")
    decision = decide_action_intent(intent)
    receipt = build_receipt(intent=intent, decision=decision, generated_at=generated_at)
    return {"intent": asdict(intent), "decision": asdict(decision), "receipt": asdict(receipt)}


def _capital_hilton_covenant() -> ActionCovenantRequest:
    return build_covenant_request(
        covenant_id="capital_hilton_invoice_covenant_v0",
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_package_ref="workflow_execution_package_compiler:capital_hilton_package_chain",
        requested_action="SEND_EMAIL",
        action_summary="Email recipient contact candidate with Winship-branded invoice artifact reference and preserve Coupa/PO as official rail.",
        risk_level="HIGH",
        required_inputs=(
            "confirmed recipient contact route",
            "exact Coupa PO/reference if payment rail requires it",
            "final invoice artifact refs",
        ),
        required_proofs=(
            "invoice artifact hash/readback",
            "recipient/contact confirmation receipt",
            "send/submit receipts before completion can be claimed",
        ),
        required_approvals=(
            "operator exact approval phrase",
            "Guardian review if configured for external send",
        ),
        blocked_until=(
            "missing proofs are present",
            "Guardian/external-send gate exists",
            "future send adapter is approved",
        ),
    )


def _example_capital_hilton(generated_at: str) -> dict[str, Any]:
    covenant = _capital_hilton_covenant()
    intent = classify_chat_action_intent(
        "send it",
        source_chat_request_ref="chat_request_capital_hilton_send_fixture",
        context_hint="Capital Hilton invoice send covenant available",
        pending_covenant_ref=covenant.covenant_id,
    )
    decision = decide_action_intent(intent, covenant=covenant, guardian_required=True)
    receipt = build_receipt(intent=intent, decision=decision, covenant=covenant, generated_at=generated_at)
    return {
        "intent": asdict(intent),
        "covenant_request": asdict(covenant),
        "decision": asdict(decision),
        "receipt": asdict(receipt),
    }


def _example_reveal_secret(generated_at: str) -> dict[str, Any]:
    covenant = build_covenant_request(
        covenant_id="protected_secret_use_coupa_credential_covenant_v0",
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_package_ref="protected_secret_intake_contract:task_scoped_secret_ref",
        requested_action="REVEAL_SECRET",
        action_summary="Use a protected Coupa credential ref through a future approved adapter without exposing the raw value.",
        risk_level="CRITICAL",
        required_inputs=("protected secret token ref", "task scope", "TTL policy"),
        required_proofs=("protected secret intake receipt", "adapter-use receipt"),
        required_approvals=("operator exact approval phrase", "Guardian secret-use review"),
        blocked_until=("protected secret ref exists", "approved adapter exists", "Guardian review exists"),
    )
    intent = classify_chat_action_intent(
        "use my Coupa password",
        source_chat_request_ref="chat_request_secret_fixture",
    )
    decision = decide_action_intent(intent, covenant=covenant, guardian_required=True)
    receipt = build_receipt(intent=intent, decision=decision, covenant=covenant, generated_at=generated_at)
    return {
        "intent": asdict(intent),
        "covenant_request": asdict(covenant),
        "decision": asdict(decision),
        "receipt": asdict(receipt),
    }


def _example_test_package(generated_at: str) -> dict[str, Any]:
    covenant = build_covenant_request(
        covenant_id="test_workflow_package_covenant_v0",
        source_workflow_ref="openclaw_backend_validation",
        source_package_ref="package_ref:bounded_test_fixture",
        requested_action="TEST_WORKFLOW_PACKAGE",
        action_summary="Run focused deterministic validation for a compiled package without external action.",
        risk_level="MEDIUM",
        required_inputs=("package ref", "test rail ref"),
        required_proofs=("test output readback",),
        required_approvals=("operator scoped test request when package exists",),
        blocked_until=("package ref exists", "test rail exists"),
    )
    intent = classify_chat_action_intent(
        "test it",
        source_chat_request_ref="chat_request_test_package_fixture",
        context_hint="package test request",
        pending_covenant_ref=covenant.covenant_id,
    )
    decision = decide_action_intent(intent, covenant=covenant, proof_missing=True)
    receipt = build_receipt(intent=intent, decision=decision, covenant=covenant, generated_at=generated_at)
    return {
        "intent": asdict(intent),
        "covenant_request": asdict(covenant),
        "decision": asdict(decision),
        "receipt": asdict(receipt),
    }


def _example_destructive(generated_at: str) -> dict[str, Any]:
    intent = classify_chat_action_intent(
        "delete that whole client folder",
        source_chat_request_ref="chat_request_delete_folder_fixture",
    )
    decision = decide_action_intent(intent)
    receipt = build_receipt(intent=intent, decision=decision, generated_at=generated_at)
    return {"intent": asdict(intent), "decision": asdict(decision), "receipt": asdict(receipt)}


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    return {
        "looks_right": _example_low_risk(generated_at),
        "go_ahead": _example_go_ahead(generated_at),
        "send_it": _example_send_it(generated_at),
        "capital_hilton_send": _example_capital_hilton(generated_at),
        "reveal_secret": _example_reveal_secret(generated_at),
        "test_package": _example_test_package(generated_at),
        "destructive_action": _example_destructive(generated_at),
    }


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    interrupter = build_interrupter()
    blockers = build_blockers()
    examples = build_examples(generated_at)
    report = build_report()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "normalized_intents": NORMALIZED_INTENTS,
        "risk_levels": RISK_LEVELS,
        "requested_actions": REQUESTED_ACTIONS,
        "decision_statuses": DECISION_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "casual_approval_phrases": CASUAL_APPROVAL_PHRASES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "interrupter": asdict(interrupter),
        "action_covenant_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "elioperator_report": asdict(report),
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "live_action_authorization_performed": False,
            "action_execution_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "browser_access_performed": False,
            "file_mutation_performed": False,
            "secret_reveal_performed": False,
            "workflow_run_performed": False,
            "agent_dispatch_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "OpenClaw can now interrupt casual chat approvals before high-consequence actions. "
            "Low-risk confirmations can continue, but send/submit/mutate/reveal/run requests require "
            "a concrete Action Covenant and exact phrase, with no live authorization or execution in v0."
        ),
        "next_safe_move": "Call this interrupter from the request processor before future action-capable adapters.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    examples = payload["examples"]
    lines = [
        "# Conversational Action Covenant Interrupter",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## How It Works",
        "- Casual phrases are classified before action.",
        "- High-consequence actions require a concrete covenant.",
        "- Gated actions require an exact phrase bound to the covenant id.",
        "- Receipts record that nothing executed in this lane.",
        "",
        "## Examples",
        f"- looks right: {examples['looks_right']['decision']['decision_status']}",
        f"- go ahead: {examples['go_ahead']['decision']['operator_message']}",
        f"- send it: {examples['send_it']['decision']['decision_status']}",
        f"- Capital Hilton send covenant: {examples['capital_hilton_send']['covenant_request']['exact_approval_phrase']}",
        f"- reveal-secret request: {examples['reveal_secret']['decision']['decision_status']}",
        f"- test package: {examples['test_package']['decision']['decision_status']}",
        f"- destructive action: {examples['destructive_action']['decision']['decision_status']}",
        "",
        "## Blocked",
    ]
    for blocker in payload["action_covenant_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No live action authorization, no action execution, no email send, no Coupa submit, no browser, no file mutation, no secret reveal, no workflow run, no agent dispatch, no external action, no credential handling, no raw-body ingestion.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "examples": tuple(payload["examples"].keys()),
        "blocker_count": len(payload["action_covenant_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Conversational Action Covenant Interrupter read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(generated_at=args.generated_at)
    write_exports(payload, export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(stable_json(_summary(payload, export_root)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
