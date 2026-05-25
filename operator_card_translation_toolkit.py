"""Operator Card Translation Toolkit v0.

This deterministic toolkit turns machine-shaped readback cards into
operator-ready chat cards. It does not call a model, dispatch agents, run
workflows, write procedure memory, create packages, access external systems,
handle credentials, ingest raw bodies, send, submit, or mutate backend state
beyond deterministic generated read-model output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_SOURCE_MIRROR = DEFAULT_EXPORT_ROOT / "chat_readback_card_mirror.json"

SCHEMA_VERSION = "operator_card_translation_toolkit_v0"
READ_MODEL_ID = "operator_card_translation_mirror"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_OPERATOR_CARD_TRANSLATION_TOOLKIT"

TRANSLATION_STATUSES = (
    "READY_FOR_OPERATOR_RENDER",
    "SOURCE_MISSING",
    "SOURCE_STALE",
    "BLOCKED_MACHINE_LANGUAGE",
    "BLOCKED_PRIVACY_RISK",
    "UNKNOWN_FAIL_CLOSED",
)

FORBIDDEN_NORMAL_UI_TERMS = (
    "Readback:",
    "schema",
    "handler",
    "lifecycle",
    "artifact_type",
    "target_handler",
    "payload_hash",
    "idempotency",
    "raw ID",
    "manifest",
    "JSON",
    "SQLite",
    "package ref",
    "local outbox",
    "visual-agnostic",
    "metadata posture",
)

ALLOWED_REPLACEMENTS = (
    "OpenClaw understood",
    "PC readback",
    "local request",
    "waiting on PC",
    "still locked",
    "proof needed",
    "approval needed",
    "nothing external happened",
)

REQUIRED_TOOLKIT_FIELDS = (
    "toolkit_id",
    "source_readback_ref",
    "target_operator_profile",
    "translation_policy",
    "machine_language_filter",
    "card_selection_policy",
    "card_compression_policy",
    "operator_choice_policy",
    "truth_boundary_policy",
    "privacy_boundary_policy",
    "next_safe_move",
)

REQUIRED_MIRROR_FIELDS = (
    "mirror_id",
    "source_mirror_ref",
    "translation_status",
    "assistant_lead_in",
    "cards",
    "operator_choices",
    "future_actions",
    "truth_boundary",
    "privacy_boundary",
    "locked_actions",
    "next_safe_move",
)

REQUIRED_CARD_FIELDS = (
    "card_id",
    "source_card_type",
    "human_title",
    "human_summary",
    "visible_bullets",
    "detail_bullets",
    "status_tone",
    "truth_status",
    "proof_status",
    "detail_available",
    "next_safe_move",
)

REQUIRED_FILTER_FIELDS = (
    "filter_id",
    "forbidden_terms",
    "replacement_policy",
    "blocked_terms_found",
    "cleaned_output",
    "fail_closed",
    "next_safe_move",
)

REQUIRED_CHOICE_FIELDS = (
    "choice_id",
    "source_choice",
    "human_label",
    "enabled",
    "disabled_reason",
    "action_scope",
    "truth_effect",
    "external_authority",
    "next_safe_move",
)

REQUIRED_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "fail_closed",
    "next_safe_move",
)

BLOCKER_TYPES = (
    "MACHINE_LANGUAGE_VISIBLE",
    "SOURCE_MIRROR_MISSING",
    "SOURCE_MIRROR_STALE",
    "RAW_PII_IN_CARD",
    "FAKE_TRUTH_CLAIM",
    "EXTERNAL_ACTION_ENABLED",
    "UNSUPPORTED_ACTION_ENABLED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_translation_runtime_allowed": False,
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_workflow_run_allowed": False,
    "live_procedure_memory_write_allowed": False,
    "live_package_creation_allowed": False,
    "live_external_action_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_browser_access_allowed": False,
    "live_invoice_generation_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

TITLE_MAP = {
    "OpenClaw understood": "What I understood",
    "Proposed workflow": "The plan",
    "What still needs to be confirmed": "Still needed",
    "What is not happening yet": "Still locked",
}

ASSISTANT_LEAD_IN = "I got the PC readback. Here's what OpenClaw thinks you mean."
TRUTH_BOUNDARY = "Draft understanding — not confirmed truth."
PRIVACY_BOUNDARY = "Operator-ready cards only; no raw private bodies, credentials, protected evidence bodies, or raw payment references."


@dataclass(frozen=True)
class OperatorCardTranslationToolkit:
    toolkit_id: str
    source_readback_ref: str | None
    target_operator_profile: str
    translation_policy: dict[str, Any]
    machine_language_filter: dict[str, Any]
    card_selection_policy: dict[str, Any]
    card_compression_policy: dict[str, Any]
    operator_choice_policy: dict[str, Any]
    truth_boundary_policy: dict[str, Any]
    privacy_boundary_policy: dict[str, Any]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorReadyCardMirror:
    mirror_id: str
    source_mirror_ref: str | None
    translation_status: str
    assistant_lead_in: str
    cards: tuple[dict[str, Any], ...]
    operator_choices: tuple[dict[str, Any], ...]
    future_actions: tuple[dict[str, Any], ...]
    truth_boundary: str
    privacy_boundary: str
    locked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorReadyCard:
    card_id: str
    source_card_type: str
    human_title: str
    human_summary: str
    visible_bullets: tuple[str, ...]
    detail_bullets: tuple[str, ...]
    status_tone: str
    truth_status: str
    proof_status: str
    detail_available: bool
    next_safe_move: str


@dataclass(frozen=True)
class MachineLanguageFilter:
    filter_id: str
    forbidden_terms: tuple[str, ...]
    replacement_policy: dict[str, str]
    blocked_terms_found: tuple[str, ...]
    cleaned_output: bool
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorChoiceTranslation:
    choice_id: str
    source_choice: str
    human_label: str
    enabled: bool
    disabled_reason: str | None
    action_scope: str
    truth_effect: str
    external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorCardTranslationBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source mirror JSON must be an object")
    return value


def _model_schemas() -> dict[str, Any]:
    return {
        "operator_card_translation_toolkit": {
            "required_fields": list(REQUIRED_TOOLKIT_FIELDS),
        },
        "operator_ready_card_mirror": {
            "required_fields": list(REQUIRED_MIRROR_FIELDS),
            "translation_statuses": list(TRANSLATION_STATUSES),
        },
        "operator_ready_card": {
            "required_fields": list(REQUIRED_CARD_FIELDS),
        },
        "machine_language_filter": {
            "required_fields": list(REQUIRED_FILTER_FIELDS),
            "forbidden_terms": list(FORBIDDEN_NORMAL_UI_TERMS),
            "allowed_replacements": list(ALLOWED_REPLACEMENTS),
        },
        "operator_choice_translation": {
            "required_fields": list(REQUIRED_CHOICE_FIELDS),
        },
        "operator_card_translation_blocker": {
            "required_fields": list(REQUIRED_BLOCKER_FIELDS),
            "blocker_types": list(BLOCKER_TYPES),
        },
    }


def _source_mirror(source: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not source:
        return {}
    mirror = source.get("chat_readback_card_mirror")
    return mirror if isinstance(mirror, Mapping) else {}


def _source_cards(source: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    mirror = _source_mirror(source)
    cards = mirror.get("cards")
    if isinstance(cards, list):
        return tuple(card for card in cards if isinstance(card, Mapping))
    return ()


def _source_choices(source: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    mirror = _source_mirror(source)
    choices = mirror.get("operator_choices")
    if isinstance(choices, list):
        return tuple(choice for choice in choices if isinstance(choice, Mapping))
    return ()


def _strip_machine_prefix(text: str) -> str:
    cleaned = text.strip()
    while cleaned.lower().startswith("readback:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned


def _clean_text(text: str) -> str:
    replacements = {
        "Readback:": "",
        "Mac-renderable": "chat-ready",
        "backend package": "next package",
        "backend readback": "PC readback",
        "backend procedure memory write": "procedure memory",
        "backend package creation": "package creation",
    }
    cleaned = _strip_machine_prefix(text)
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return " ".join(cleaned.split())


def _visible_text(cards: tuple[OperatorReadyCard, ...], choices: tuple[OperatorChoiceTranslation, ...]) -> str:
    chunks: list[str] = []
    for card in cards:
        chunks.extend([card.human_title, card.human_summary])
        chunks.extend(card.visible_bullets)
        chunks.extend(card.detail_bullets)
    for choice in choices:
        chunks.extend([choice.human_label, choice.disabled_reason or ""])
    return "\n".join(chunks)


def _machine_terms_found(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    found = []
    for term in FORBIDDEN_NORMAL_UI_TERMS:
        if term.lower() in lowered:
            found.append(term)
    return tuple(found)


def build_toolkit(source: Mapping[str, Any] | None) -> OperatorCardTranslationToolkit:
    mirror = _source_mirror(source)
    return OperatorCardTranslationToolkit(
        toolkit_id="operator_card_translation_toolkit_v0",
        source_readback_ref=str(mirror.get("source_readback_ref") or "") or None,
        target_operator_profile="Winship operator/captain",
        translation_policy={
            "translate_for_human_operator": True,
            "mac_should_not_humanize_machine_language": True,
            "deterministic_templates_only": True,
            "no_live_llm": True,
        },
        machine_language_filter={
            "forbidden_terms": FORBIDDEN_NORMAL_UI_TERMS,
            "allowed_replacements": ALLOWED_REPLACEMENTS,
            "normal_card_content_must_pass_filter": True,
        },
        card_selection_policy={
            "capital_hilton_titles": tuple(TITLE_MAP.values()),
            "prefer_four_card_summary": True,
            "details_available": True,
        },
        card_compression_policy={
            "visible_bullets_max": 5,
            "move_extra_to_detail_bullets": True,
            "preserve_truth_and_lock_boundaries": True,
        },
        operator_choice_policy={
            "primary_choices": ("Looks right", "Change something", "What's missing?"),
            "future_choices_disabled": ("Store as procedure", "Prepare package"),
            "external_authority": False,
        },
        truth_boundary_policy={
            "truth_boundary": TRUTH_BOUNDARY,
            "no_fake_truth": True,
            "readback_is_draft_until_operator_confirms": True,
        },
        privacy_boundary_policy={
            "no_raw_private_bodies": True,
            "no_raw_po_or_payment_reference": True,
            "no_credentials": True,
            "no_protected_evidence_bodies": True,
        },
        next_safe_move="Render operator-ready cards and ask whether the understanding looks right.",
    )


def _card_by_title(source: Mapping[str, Any] | None, title: str) -> Mapping[str, Any]:
    for card in _source_cards(source):
        if card.get("title") == title:
            return card
    return {}


def _capital_hilton_cards(source: Mapping[str, Any] | None) -> tuple[OperatorReadyCard, ...]:
    understood_source = _card_by_title(source, "OpenClaw understood")
    plan_source = _card_by_title(source, "Proposed workflow")
    needed_source = _card_by_title(source, "What still needs to be confirmed")
    locked_source = _card_by_title(source, "What is not happening yet")
    default_truth = "DRAFT_UNDERSTANDING_NOT_TRUTH"
    return (
        OperatorReadyCard(
            card_id="operator_card_what_i_understood",
            source_card_type=str(understood_source.get("card_type") or "OPENCLAW_UNDERSTOOD"),
            human_title="What I understood",
            human_summary=(
                "Capital Hilton invoice: 4 dates at $400 each. OpenClaw thinks you want a Winship-branded "
                "Excel/PDF invoice sent to Annette, while Coupa/PO remains the official payment path."
            ),
            visible_bullets=(
                "Capital Hilton invoice: 4 dates at $400 each.",
                "Winship-branded Excel/PDF invoice goes to Annette as the follow-up packet.",
                "Coupa/PO remains the official payment path.",
                TRUTH_BOUNDARY,
            ),
            detail_bullets=tuple(
                _clean_text(bullet)
                for bullet in understood_source.get("bullets", ())
                if isinstance(bullet, str) and "External actions" not in bullet
            ),
            status_tone="ready",
            truth_status=str(understood_source.get("truth_status") or default_truth),
            proof_status=str(understood_source.get("proof_status") or "PROOF_REQUIRED"),
            detail_available=True,
            next_safe_move="Ask Winship whether this is what he means.",
        ),
        OperatorReadyCard(
            card_id="operator_card_the_plan",
            source_card_type=str(plan_source.get("card_type") or "PROPOSED_WORKFLOW"),
            human_title="The plan",
            human_summary=(
                "Confirm the dates/rate, build the invoice artifact, confirm Coupa/PO, draft the email to "
                "Annette, get Guardian approval, then send/submit only after gates are satisfied."
            ),
            visible_bullets=(
                "Confirm dates/rate and build the invoice artifact.",
                "Confirm Coupa/PO and draft the email to Annette.",
                "Get Guardian approval before anything sends.",
                "Send/submit only after gates are satisfied.",
            ),
            detail_bullets=tuple(
                _clean_text(bullet)
                for bullet in plan_source.get("bullets", ())
                if isinstance(bullet, str)
            ),
            status_tone="review",
            truth_status=str(plan_source.get("truth_status") or "NEEDS_OPERATOR_REVIEW"),
            proof_status=str(plan_source.get("proof_status") or "BACKEND_READBACK_REQUIRED"),
            detail_available=True,
            next_safe_move="Review or change the plan before any future package is prepared.",
        ),
        OperatorReadyCard(
            card_id="operator_card_still_needed",
            source_card_type=str(needed_source.get("card_type") or "MISSING_INFO"),
            human_title="Still needed",
            human_summary=(
                "Exact Coupa PO/reference, confirmation that Annette is the right contact, final invoice "
                "artifact/hash, Guardian approval, and send/submit receipts."
            ),
            visible_bullets=(
                "Exact Coupa PO/reference.",
                "Confirmation that Annette is the right contact.",
                "Final invoice artifact/hash.",
                "Guardian approval and send/submit receipts.",
            ),
            detail_bullets=tuple(
                _clean_text(bullet)
                for bullet in needed_source.get("bullets", ())
                if isinstance(bullet, str)
            ),
            status_tone="needs_confirmation",
            truth_status=str(needed_source.get("truth_status") or "NEEDS_OPERATOR_REVIEW"),
            proof_status=str(needed_source.get("proof_status") or "PROOF_REQUIRED"),
            detail_available=True,
            next_safe_move="Ask for the Coupa reference or contact confirmation next.",
        ),
        OperatorReadyCard(
            card_id="operator_card_still_locked",
            source_card_type=str(locked_source.get("card_type") or "BLOCKED"),
            human_title="Still locked",
            human_summary=(
                "Nothing external happened. No email, Coupa access, browser, approval, invoice generation, "
                "attachment, or payment update."
            ),
            visible_bullets=(
                "Nothing external happened.",
                "No email, Coupa access, browser, or approval.",
                "No invoice generation, attachment, or payment update.",
                "External actions remain locked.",
            ),
            detail_bullets=tuple(
                _clean_text(bullet)
                for bullet in locked_source.get("bullets", ())
                if isinstance(bullet, str)
            ),
            status_tone="locked",
            truth_status=str(locked_source.get("truth_status") or "LOCKED_EXTERNAL_ACTION"),
            proof_status=str(locked_source.get("proof_status") or "PROOF_REQUIRED"),
            detail_available=True,
            next_safe_move="Keep external actions locked until proof and approval rails exist.",
        ),
    )


def _choice(
    *,
    choice_id: str,
    source_choice: str,
    human_label: str,
    enabled: bool,
    disabled_reason: str | None,
    action_scope: str,
    truth_effect: str,
    next_safe_move: str,
) -> OperatorChoiceTranslation:
    return OperatorChoiceTranslation(
        choice_id=choice_id,
        source_choice=source_choice,
        human_label=human_label,
        enabled=enabled,
        disabled_reason=disabled_reason,
        action_scope=action_scope,
        truth_effect=truth_effect,
        external_authority=False,
        next_safe_move=next_safe_move,
    )


def build_operator_choices(source: Mapping[str, Any] | None) -> tuple[OperatorChoiceTranslation, ...]:
    source_labels = {
        str(choice.get("operator_action") or choice.get("human_label") or "")
        for choice in _source_choices(source)
    }
    return (
        _choice(
            choice_id="operator_choice_looks_right",
            source_choice="Looks right" if "Looks right" in source_labels else "local_review_confirm",
            human_label="Looks right",
            enabled=True,
            disabled_reason=None,
            action_scope="local UI review only",
            truth_effect="does not write backend truth by itself",
            next_safe_move="Keep this as local confirmation until a backend capture rail exists.",
        ),
        _choice(
            choice_id="operator_choice_change_something",
            source_choice="Edit understanding" if "Edit understanding" in source_labels else "edit_understanding",
            human_label="Change something",
            enabled=True,
            disabled_reason=None,
            action_scope="return to chat input/edit",
            truth_effect="does not change backend truth until a new request/readback exists",
            next_safe_move="Let the operator revise the instruction.",
        ),
        _choice(
            choice_id="operator_choice_whats_missing",
            source_choice="missing_info_explanation",
            human_label="What's missing?",
            enabled=True,
            disabled_reason=None,
            action_scope="explain missing info",
            truth_effect="read-only explanation",
            next_safe_move="Show the Still needed card.",
        ),
    )


def build_future_actions(source: Mapping[str, Any] | None) -> tuple[OperatorChoiceTranslation, ...]:
    source_labels = {
        str(choice.get("operator_action") or choice.get("human_label") or "")
        for choice in _source_choices(source)
    }
    return (
        _choice(
            choice_id="operator_future_store_as_procedure",
            source_choice="Store as procedure" if "Store as procedure" in source_labels else "store_as_procedure",
            human_label="Store as procedure",
            enabled=False,
            disabled_reason="Backend procedure memory write is not connected yet.",
            action_scope="future backend procedure memory write",
            truth_effect="would require an operator-reviewed procedure receipt",
            next_safe_move="Keep disabled until the governed procedure write rail exists.",
        ),
        _choice(
            choice_id="operator_future_prepare_package",
            source_choice="Prepare package" if "Prepare package" in source_labels else "prepare_package",
            human_label="Prepare package",
            enabled=False,
            disabled_reason="Backend package creation is not connected yet.",
            action_scope="future backend package creation",
            truth_effect="would require a package creation receipt",
            next_safe_move="Keep disabled until the deterministic package creation rail exists.",
        ),
    )


def _blocker(blocker_type: str, condition: str, *, severity: str = "BLOCKS_OPERATOR_RENDER") -> OperatorCardTranslationBlocker:
    return OperatorCardTranslationBlocker(
        blocker_id=f"operator_card_translation_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=f"ELIOPERATOR: {condition}",
        fail_closed=True,
        next_safe_move="Do not render operator-ready cards until the source is safe.",
    )


def build_standard_blockers() -> tuple[OperatorCardTranslationBlocker, ...]:
    conditions = {
        "MACHINE_LANGUAGE_VISIBLE": "Machine readback language is visible in normal card content.",
        "SOURCE_MIRROR_MISSING": "The chat readback card mirror is missing.",
        "SOURCE_MIRROR_STALE": "The source mirror is stale or not ready.",
        "RAW_PII_IN_CARD": "Raw private values must not appear in operator cards.",
        "FAKE_TRUTH_CLAIM": "Cards must not claim confirmed truth without proof.",
        "EXTERNAL_ACTION_ENABLED": "Operator card choices cannot enable external action.",
        "UNSUPPORTED_ACTION_ENABLED": "Unsupported actions must remain disabled.",
        "UNKNOWN_FAIL_CLOSED": "Unknown translation state fails closed.",
    }
    return tuple(_blocker(blocker_type, condition) for blocker_type, condition in conditions.items())


def _filter(cards: tuple[OperatorReadyCard, ...], choices: tuple[OperatorChoiceTranslation, ...], future: tuple[OperatorChoiceTranslation, ...]) -> MachineLanguageFilter:
    visible = _visible_text(cards, choices + future)
    found = _machine_terms_found(visible)
    return MachineLanguageFilter(
        filter_id="machine_language_filter_operator_cards",
        forbidden_terms=FORBIDDEN_NORMAL_UI_TERMS,
        replacement_policy={
            "Readback:": "",
            "schema": "card type",
            "handler": "rail",
            "payload_hash": "proof reference",
            "JSON": "readback file",
            "SQLite": "local state",
        },
        blocked_terms_found=found,
        cleaned_output=not found,
        fail_closed=bool(found),
        next_safe_move="Render only if normal card content is free of machine-contract language.",
    )


def _translation_status(source: Mapping[str, Any] | None, filter_result: MachineLanguageFilter) -> str:
    if source is None:
        return "SOURCE_MISSING"
    mirror = _source_mirror(source)
    mirror_status = str(mirror.get("mirror_status") or "")
    if mirror_status != "READY_FOR_MAC_RENDER":
        if "STALE" in mirror_status:
            return "SOURCE_STALE"
        return "UNKNOWN_FAIL_CLOSED"
    if filter_result.fail_closed:
        return "BLOCKED_MACHINE_LANGUAGE"
    return "READY_FOR_OPERATOR_RENDER"


def build_ready_mirror(source: Mapping[str, Any] | None) -> tuple[OperatorReadyCardMirror, MachineLanguageFilter, tuple[OperatorCardTranslationBlocker, ...]]:
    cards = _capital_hilton_cards(source) if source else ()
    choices = build_operator_choices(source)
    future_actions = build_future_actions(source)
    filter_result = _filter(cards, choices, future_actions)
    translation_status = _translation_status(source, filter_result)
    blockers: list[OperatorCardTranslationBlocker] = []
    source_mirror = _source_mirror(source)

    if source is None:
        blockers.append(_blocker("SOURCE_MIRROR_MISSING", "The chat readback card mirror is missing."))
    if source is not None and str(source_mirror.get("mirror_status") or "") != "READY_FOR_MAC_RENDER":
        blockers.append(_blocker("SOURCE_MIRROR_STALE", "The source mirror is not ready for operator rendering."))
    if filter_result.fail_closed:
        blockers.append(_blocker("MACHINE_LANGUAGE_VISIBLE", "Machine readback language is visible in normal card content."))
    if any(choice.enabled and choice.external_authority for choice in choices + future_actions):
        blockers.append(_blocker("EXTERNAL_ACTION_ENABLED", "An operator choice attempted to enable external authority."))
    if any(action.human_label in {"Store as procedure", "Prepare package"} and action.enabled for action in future_actions):
        blockers.append(_blocker("UNSUPPORTED_ACTION_ENABLED", "Unsupported future actions were enabled."))

    return (
        OperatorReadyCardMirror(
            mirror_id="operator_card_translation_mirror_current",
            source_mirror_ref=str(source.get("read_model_id") or "") if source else None,
            translation_status=translation_status,
            assistant_lead_in=ASSISTANT_LEAD_IN if translation_status == "READY_FOR_OPERATOR_RENDER" else "I do not have a safe translated readback yet.",
            cards=tuple(asdict(card) for card in cards),
            operator_choices=tuple(asdict(choice) for choice in choices),
            future_actions=tuple(asdict(choice) for choice in future_actions),
            truth_boundary=TRUTH_BOUNDARY,
            privacy_boundary=PRIVACY_BOUNDARY,
            locked_actions=tuple(str(action) for action in source_mirror.get("locked_actions", ())) if source_mirror else (),
            next_safe_move=(
                "Show these translated cards in chat and ask whether they look right."
                if translation_status == "READY_FOR_OPERATOR_RENDER"
                else "Wait for a safe source mirror before rendering translated cards."
            ),
        ),
        filter_result,
        tuple(blockers),
    )


def build_operator_card_translation_mirror(
    *,
    source_mirror_path: Path = DEFAULT_SOURCE_MIRROR,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source = _load_json(source_mirror_path)
    toolkit = build_toolkit(source)
    mirror, filter_result, active_blockers = build_ready_mirror(source)
    standard_blockers = build_standard_blockers()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "source_mirror_path": source_mirror_path.as_posix(),
        "source_mirror_present": source is not None,
        "translation_statuses": TRANSLATION_STATUSES,
        "model_schemas": _model_schemas(),
        "operator_card_translation_toolkit": asdict(toolkit),
        "operator_ready_card_mirror": asdict(mirror),
        "operator_ready_cards": mirror.cards,
        "machine_language_filter": asdict(filter_result),
        "operator_choice_translations": mirror.operator_choices,
        "future_action_translations": mirror.future_actions,
        "active_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in active_blockers},
        "standard_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in standard_blockers},
        "relationship_refs": {
            "chat_readback_card_mirror": "source mirror read-model",
            "conversational_workflow_router_intake": "source machine readback",
            "workflow_readback_concierge_contract": "request/readback responsibility",
            "operator_question_assist_scope_expansion_contract": "future operator question compatibility",
            "cross_surface_artifact_handoff_registry_contract": "post-office compatibility",
            "openclaw_sensitive_policy": "privacy boundary dependency",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    cards = tuple(OperatorReadyCard(**card) for card in payload["operator_ready_card_mirror"]["cards"])
    choices = tuple(OperatorChoiceTranslation(**choice) for choice in payload["operator_ready_card_mirror"]["operator_choices"])
    future = tuple(OperatorChoiceTranslation(**choice) for choice in payload["operator_ready_card_mirror"]["future_actions"])
    visible = _visible_text(cards, choices + future)
    future_by_label = {choice.human_label: choice for choice in future}
    return {
        "operator_card_translation_toolkit_model_present": True,
        "operator_ready_card_mirror_model_present": True,
        "operator_ready_card_model_present": True,
        "machine_language_filter_model_present": True,
        "operator_choice_translation_model_present": True,
        "operator_card_translation_blocker_model_present": True,
        "source_mirror_loads": payload["source_mirror_present"],
        "capital_hilton_cards_translate": {card.human_title for card in cards} == {
            "What I understood",
            "The plan",
            "Still needed",
            "Still locked",
        },
        "readback_prefix_removed": "Readback:" not in visible,
        "human_titles_used": all(title in {card.human_title for card in cards} for title in TITLE_MAP.values()),
        "visible_bullets_compressed": all(len(card.visible_bullets) <= 5 for card in cards),
        "detail_bullets_available": all(card.detail_available and card.detail_bullets for card in cards),
        "operator_choices_translated": {choice.human_label for choice in choices} == {
            "Looks right",
            "Change something",
            "What's missing?",
        },
        "future_actions_disabled": all(
            label in future_by_label and future_by_label[label].enabled is False
            for label in ("Store as procedure", "Prepare package")
        ),
        "truth_boundary_preserved": payload["operator_ready_card_mirror"]["truth_boundary"] == TRUTH_BOUNDARY
        and TRUTH_BOUNDARY in visible,
        "external_actions_locked": "Nothing external happened." in visible and all(
            action in payload["operator_ready_card_mirror"]["locked_actions"]
            for action in (
                "email send",
                "Coupa access",
                "browser automation",
                "invoice submission",
                "approval request",
                "invoice generation",
                "attachment",
                "payment state change",
            )
        ),
        "machine_language_absent_from_normal_cards": not _machine_terms_found(visible),
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_cards": False,
        "external_action_performed": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    mirror = payload["operator_ready_card_mirror"]
    lines = [
        "# Operator Card Translation Mirror v0",
        "",
        "ELIOPERATOR: This translates PC readback cards into operator-ready chat cards. It does not run the workflow or grant authority.",
        "",
        f"- Translation status: `{mirror['translation_status']}`.",
        f"- Lead-in: {mirror['assistant_lead_in']}",
        f"- Truth boundary: {mirror['truth_boundary']}",
        "",
        "## Cards",
        "",
    ]
    for card in mirror["cards"]:
        lines.append(f"### {card['human_title']}")
        lines.append(f"- {card['human_summary']}")
        for bullet in card["visible_bullets"]:
            lines.append(f"- {bullet}")
        lines.append("")
    lines.extend(["## Operator Choices", ""])
    for choice in mirror["operator_choices"]:
        status = "available" if choice["enabled"] else f"disabled: {choice['disabled_reason'].rstrip('.')}"
        lines.append(f"- {choice['human_label']}: {status}.")
    lines.extend(["", "## Future Actions", ""])
    for choice in mirror["future_actions"]:
        status = "available" if choice["enabled"] else f"disabled: {choice['disabled_reason'].rstrip('.')}"
        lines.append(f"- {choice['human_label']}: {status}.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No live translation runtime, model call, agent dispatch, workflow run, procedure write, package creation, send, submit, Coupa/browser access, credential handling, or raw-body ingestion occurred.",
            "",
            f"Next safe move: {mirror['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    mirror = payload["operator_ready_card_mirror"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "translation_status": mirror["translation_status"],
        "assistant_lead_in": mirror["assistant_lead_in"],
        "cards": [card["human_title"] for card in mirror["cards"]],
        "operator_choices": [choice["human_label"] for choice in mirror["operator_choices"]],
        "future_actions": [choice["human_label"] for choice in mirror["future_actions"]],
        "machine_terms_found": list(payload["machine_language_filter"]["blocked_terms_found"]),
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export operator-ready translated readback cards.")
    parser.add_argument("--source-mirror", default=str(DEFAULT_SOURCE_MIRROR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_operator_card_translation_mirror(
        source_mirror_path=Path(args.source_mirror),
        generated_at=args.generated_at,
    )
    json_path, operator_path = write_exports(payload, Path(args.export_root))
    summary = build_summary(payload, json_path, operator_path)
    if args.format == "summary":
        print(stable_json(summary), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
