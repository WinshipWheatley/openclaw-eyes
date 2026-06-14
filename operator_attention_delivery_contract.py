"""Operator attention and delivery contract v0.

This module records when OpenClaw may surface operator attention items and how
those items bind to local surface requests. It does not send Telegram, push,
email, launch apps, read files, call models/agents, or execute workflows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_surface_request_contract as local_surface


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "operator_attention_delivery_contract_v0"
READ_MODEL_ID = "operator_attention_delivery_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_OPERATOR_ATTENTION_DELIVERY_CONTRACT_NO_EXTERNAL_DELIVERY"

ACTOR_LABELS = ("Cassandra", "Chief", "Guardian", "Niles", "Hermes", "OpenClaw System")
URGENCY_LEVELS = ("high", "medium", "low")
DELIVERY_TARGETS = (
    "mac_helm",
    "active_chat",
    "telegram_candidate",
    "mobile_notification_candidate",
    "email_candidate",
)
OPERATOR_PRESENCE_CONTEXTS = ("active_in_chat", "active_in_world", "away", "unknown")
DISPLAY_POLICIES = (
    "auto_open_surface_when_active",
    "show_single_action_when_away",
    "quiet_below_deck",
    "proof_only",
)
ATTENTION_REASONS = (
    "missing_fact",
    "approval_needed",
    "ambiguous_classification",
    "protected_boundary_decision",
    "manual_confirmation",
    "stale_failure_state",
    "local_device_action_required",
    "quiet_backend_handled",
)

AUTHORITY_BOUNDARY = {
    "telegram_send_allowed": False,
    "push_notification_allowed": False,
    "email_send_allowed": False,
    "external_delivery_allowed": False,
    "app_launch_allowed": False,
    "browser_allowed": False,
    "network_allowed": False,
    "file_body_read_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "coupa_access_allowed": False,
    "coupa_submit_allowed": False,
    "credential_handling_allowed": False,
    "model_call_allowed": False,
    "agent_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "raw_body_ingestion_allowed": False,
    "path_translation_guess_allowed": False,
    "send_submit_allowed": False,
}


@dataclass(frozen=True)
class OperatorPresenceContext:
    context_id: str
    presence_context: str
    preferred_display_policy: str
    auto_open_surface_when_active_preferred: bool
    show_single_action_when_away: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorAttentionReason:
    reason_id: str
    reason_type: str
    needs_operator_attention: bool
    default_urgency_level: str
    description: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorAttentionSurface:
    surface_id: str
    delivery_target: str
    presentation_only: bool
    candidate_only: bool
    external_delivery_allowed: bool
    send_or_push_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorAttentionAction:
    action_id: str
    primary_human_action_label: str
    action_kind: str
    maps_to_local_surface_type: str
    direct_execution_allowed: bool
    external_action_allowed: bool
    receipt_required_after_operator_action: bool
    next_safe_move: str


@dataclass(frozen=True)
class AttentionToLocalSurfaceBinding:
    binding_id: str
    attention_id: str
    primary_human_action_label: str
    local_surface_request_id: str
    local_surface_type: str
    binding_status: str
    direct_execution_allowed: bool
    validation_required_after_result: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorAttentionItem:
    attention_id: str
    world_ref: str
    client_ref: str
    workflow_ref: str
    actor_label: str
    human_message: str
    concise_spoken_guidance: str
    reason_for_attention: str
    operator_only_reason: str
    urgency_level: str
    delivery_targets_allowed: tuple[str, ...]
    operator_presence_context: str
    display_policy: str
    primary_human_action_label: str
    linked_local_surface_request: dict[str, Any]
    required_confirmation: bool
    authority_boundary: dict[str, bool]
    external_delivery_allowed: bool
    telegram_send_allowed: bool
    push_allowed: bool
    email_send_allowed: bool
    external_action_allowed: bool
    expires_or_stale_after: str
    receipt_required_after_operator_action: bool
    fixture_ref: str
    attention_to_local_surface_binding: dict[str, Any]


@dataclass(frozen=True)
class OperatorAttentionDeliveryPolicy:
    policy_id: str
    supported_actor_labels: tuple[str, ...]
    supported_attention_reasons: tuple[str, ...]
    supported_delivery_targets: tuple[str, ...]
    supported_presence_contexts: tuple[str, ...]
    supported_display_policies: tuple[str, ...]
    active_in_chat_policy: str
    away_policy: str
    candidate_delivery_policy: str
    attention_actions_must_bind_to_local_surface_request: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorAttentionReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    surfaced_item_count: int
    quiet_item_count: int
    primary_next_action: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _safe_choice(value: str, allowed: tuple[str, ...], fallback: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else fallback


def _surface_dict(surface_request: local_surface.LocalSurfaceRequest | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(surface_request, Mapping):
        return dict(surface_request)
    return asdict(surface_request)


def _no_real_path(payload: Mapping[str, Any]) -> bool:
    rendered = stable_json(payload).lower()
    blocked_markers = ("/mnt/", "/volumes/", "/users/", "c:\\", "file://")
    return not any(marker in rendered for marker in blocked_markers)


def default_delivery_policy() -> OperatorAttentionDeliveryPolicy:
    return OperatorAttentionDeliveryPolicy(
        policy_id="operator_attention_delivery_policy:v0",
        supported_actor_labels=ACTOR_LABELS,
        supported_attention_reasons=ATTENTION_REASONS,
        supported_delivery_targets=DELIVERY_TARGETS,
        supported_presence_contexts=OPERATOR_PRESENCE_CONTEXTS,
        supported_display_policies=DISPLAY_POLICIES,
        active_in_chat_policy="Prefer auto_open_surface_when_active when the linked local surface is safe; keep confirmation cards confirmation-gated.",
        away_policy="Prepare one concise attention item with one human action; delivery targets remain candidate/future-gated.",
        candidate_delivery_policy="telegram_candidate, mobile_notification_candidate, and email_candidate are presentation candidates only, not sends.",
        attention_actions_must_bind_to_local_surface_request=True,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Surface only attention items that require an operator decision or local device result.",
    )


def presence_contexts() -> tuple[OperatorPresenceContext, ...]:
    return (
        OperatorPresenceContext(
            context_id="operator_presence:active_in_chat",
            presence_context="active_in_chat",
            preferred_display_policy="auto_open_surface_when_active",
            auto_open_surface_when_active_preferred=True,
            show_single_action_when_away=False,
            next_safe_move="Show the relevant local surface directly when safe; still require explicit confirmation for confirmation-gated surfaces.",
        ),
        OperatorPresenceContext(
            context_id="operator_presence:active_in_world",
            presence_context="active_in_world",
            preferred_display_policy="auto_open_surface_when_active",
            auto_open_surface_when_active_preferred=True,
            show_single_action_when_away=False,
            next_safe_move="Prefer one local surface in the current world without adding a start-button cluster.",
        ),
        OperatorPresenceContext(
            context_id="operator_presence:away",
            presence_context="away",
            preferred_display_policy="show_single_action_when_away",
            auto_open_surface_when_active_preferred=False,
            show_single_action_when_away=True,
            next_safe_move="Prepare one concise attention item with one human action; do not send it externally in this lane.",
        ),
        OperatorPresenceContext(
            context_id="operator_presence:unknown",
            presence_context="unknown",
            preferred_display_policy="proof_only",
            auto_open_surface_when_active_preferred=False,
            show_single_action_when_away=False,
            next_safe_move="Keep the readback below deck until presence is known or the operator asks.",
        ),
    )


def attention_reasons() -> tuple[OperatorAttentionReason, ...]:
    descriptions = {
        "missing_fact": "A required fact is missing before the next safe step.",
        "approval_needed": "The operator must approve a bounded plan or boundary.",
        "ambiguous_classification": "The backend cannot safely classify or route without clarification.",
        "protected_boundary_decision": "Protected/private handling requires a boundary decision.",
        "manual_confirmation": "The next step needs explicit human confirmation.",
        "stale_failure_state": "A stale or failed state needs local operator recovery.",
        "local_device_action_required": "The next safe step requires a device-local picker, panel, or receipt.",
        "quiet_backend_handled": "No operator action is needed; keep it below deck.",
    }
    urgencies = {
        "missing_fact": "medium",
        "approval_needed": "high",
        "ambiguous_classification": "medium",
        "protected_boundary_decision": "high",
        "manual_confirmation": "medium",
        "stale_failure_state": "medium",
        "local_device_action_required": "medium",
        "quiet_backend_handled": "low",
    }
    return tuple(
        OperatorAttentionReason(
            reason_id=f"operator_attention_reason:{reason}",
            reason_type=reason,
            needs_operator_attention=reason != "quiet_backend_handled",
            default_urgency_level=urgencies[reason],
            description=descriptions[reason],
            next_safe_move="Bind any human action to a local_surface_request, not direct execution.",
        )
        for reason in ATTENTION_REASONS
    )


def attention_surfaces() -> tuple[OperatorAttentionSurface, ...]:
    surfaces = []
    for target in DELIVERY_TARGETS:
        candidate = target.endswith("_candidate")
        surfaces.append(
            OperatorAttentionSurface(
                surface_id=f"operator_attention_surface:{target}",
                delivery_target=target,
                presentation_only=True,
                candidate_only=candidate,
                external_delivery_allowed=False,
                send_or_push_allowed=False,
                next_safe_move="Render or queue as candidate presentation only; do not send, push, email, launch, or execute.",
            )
        )
    return tuple(surfaces)


def make_binding(
    *,
    attention_id: str,
    primary_human_action_label: str,
    linked_local_surface_request: Mapping[str, Any],
    receipt_required_after_operator_action: bool,
) -> AttentionToLocalSurfaceBinding:
    return AttentionToLocalSurfaceBinding(
        binding_id=f"attention_to_local_surface:{_short_hash(attention_id, linked_local_surface_request.get('request_id'))}",
        attention_id=attention_id,
        primary_human_action_label=primary_human_action_label,
        local_surface_request_id=str(linked_local_surface_request.get("request_id") or ""),
        local_surface_type=str(linked_local_surface_request.get("surface_type") or "NO_SURFACE_REQUEST"),
        binding_status="BOUND_TO_LOCAL_SURFACE_REQUEST",
        direct_execution_allowed=False,
        validation_required_after_result=receipt_required_after_operator_action,
        next_safe_move="Device returns metadata/receipt; backend validates before any later action.",
    )


def make_attention_action(
    *,
    attention_id: str,
    label: str,
    linked_local_surface_request: Mapping[str, Any],
    receipt_required_after_operator_action: bool,
) -> OperatorAttentionAction:
    return OperatorAttentionAction(
        action_id=f"operator_attention_action:{_short_hash(attention_id, label)}",
        primary_human_action_label=label,
        action_kind="LOCAL_SURFACE_REQUEST",
        maps_to_local_surface_type=str(linked_local_surface_request.get("surface_type") or "NO_SURFACE_REQUEST"),
        direct_execution_allowed=False,
        external_action_allowed=False,
        receipt_required_after_operator_action=receipt_required_after_operator_action,
        next_safe_move="Present one human action that opens or shows the linked local surface only.",
    )


def make_attention_item(
    *,
    attention_key: str,
    world_ref: str,
    actor_label: str,
    human_message: str,
    concise_spoken_guidance: str,
    reason_for_attention: str,
    operator_only_reason: str,
    urgency_level: str,
    delivery_targets_allowed: tuple[str, ...],
    operator_presence_context: str,
    display_policy: str,
    primary_human_action_label: str,
    linked_local_surface_request: local_surface.LocalSurfaceRequest | Mapping[str, Any],
    fixture_ref: str,
    client_ref: str = "unknown",
    workflow_ref: str = "unknown",
    required_confirmation: bool = False,
    expires_or_stale_after: str = "operator_presence_or_source_state_changes",
    receipt_required_after_operator_action: bool = True,
) -> OperatorAttentionItem:
    surface_request = _surface_dict(linked_local_surface_request)
    attention_id = f"operator_attention:{attention_key}:{_short_hash(attention_key, fixture_ref)}"
    binding = make_binding(
        attention_id=attention_id,
        primary_human_action_label=primary_human_action_label,
        linked_local_surface_request=surface_request,
        receipt_required_after_operator_action=receipt_required_after_operator_action,
    )
    return OperatorAttentionItem(
        attention_id=attention_id,
        world_ref=world_ref,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        actor_label=_safe_choice(actor_label, ACTOR_LABELS, "OpenClaw System"),
        human_message=human_message,
        concise_spoken_guidance=concise_spoken_guidance,
        reason_for_attention=_safe_choice(reason_for_attention, ATTENTION_REASONS, "local_device_action_required"),
        operator_only_reason=operator_only_reason,
        urgency_level=_safe_choice(urgency_level, URGENCY_LEVELS, "low"),
        delivery_targets_allowed=tuple(
            target for target in delivery_targets_allowed if target in DELIVERY_TARGETS
        ),
        operator_presence_context=_safe_choice(operator_presence_context, OPERATOR_PRESENCE_CONTEXTS, "unknown"),
        display_policy=_safe_choice(display_policy, DISPLAY_POLICIES, "proof_only"),
        primary_human_action_label=primary_human_action_label,
        linked_local_surface_request=surface_request,
        required_confirmation=required_confirmation,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        external_delivery_allowed=False,
        telegram_send_allowed=False,
        push_allowed=False,
        email_send_allowed=False,
        external_action_allowed=False,
        expires_or_stale_after=expires_or_stale_after,
        receipt_required_after_operator_action=receipt_required_after_operator_action,
        fixture_ref=fixture_ref,
        attention_to_local_surface_binding=asdict(binding),
    )


def _statement_intake_surface() -> local_surface.LocalSurfaceRequest:
    return local_surface.make_surface_request(
        surface_type="OPEN_FILE_PICKER",
        human_label="Choose bank statement",
        human_reason="OpenClaw needs a local statement file reference or statement intake receipt; no bank access occurs.",
        concise_spoken_guidance="Choose the bank statement file when you have it.",
        input_requirements=(
            {"field": "statement_file_or_receipt", "required": True, "result": "metadata/manifest only"},
        ),
        allowed_file_types=("statement", "spreadsheet", "pdf"),
        allowed_file_extensions=(".pdf", ".csv", ".xlsx", ".xls"),
        accepted_result_type="file_metadata_manifest",
        world_ref="finance",
        workflow_ref="bank_ledger_update",
        related_contract_ref="operator_attention_delivery_contract",
    )


def _guardian_boundary_surface() -> local_surface.LocalSurfaceRequest:
    return local_surface.make_surface_request(
        surface_type="SHOW_CONFIRMATION_CARD",
        human_label="Review boundary",
        human_reason="Guardian needs a protected-file boundary decision before any private file handling.",
        concise_spoken_guidance="Review the protected-file boundary. No file body will be read.",
        input_requirements=(
            {"field": "protected_boundary_decision", "required": True},
            {"field": "operator_confirmation", "required": True},
        ),
        accepted_result_type="operator_confirmation_receipt",
        world_ref="security",
        workflow_ref="protected_file_boundary",
        related_contract_ref="operator_attention_delivery_contract",
        requires_operator_confirmation=True,
        safe_to_auto_open=False,
    )


def _niles_scene_surface() -> local_surface.LocalSurfaceRequest:
    return local_surface.make_surface_request(
        surface_type="OPEN_FILE_PICKER",
        human_label="Add scene file",
        human_reason="Niles needs a local music scene or project metadata reference; no hardware integration occurs.",
        concise_spoken_guidance="Add the local scene or project file.",
        input_requirements=(
            {"field": "music_scene_or_project_file", "required": True, "result": "metadata/manifest only"},
        ),
        allowed_file_types=("audio_project", "scene_file", "audio_file"),
        allowed_file_extensions=(".scn", ".x32", ".logicx", ".als", ".wav", ".aiff", ".mp3"),
        accepted_result_type="file_metadata_manifest",
        world_ref="music",
        workflow_ref="x32_scene_or_monitor_mix",
        related_contract_ref="operator_attention_delivery_contract",
    )


def _quiet_surface() -> local_surface.LocalSurfaceRequest:
    return local_surface.no_surface_request(
        next_action="No operator action required; keep this below deck.",
        device_type="unknown",
    )


def build_attention_items() -> dict[str, dict[str, Any]]:
    items = {
        "cassandra_capital_hilton_invoice_reminder": make_attention_item(
            attention_key="cassandra_capital_hilton_invoice_reminder",
            world_ref="finance",
            client_ref="capital_hilton",
            workflow_ref="capital_hilton_invoice_workflow",
            actor_label="Cassandra",
            human_message="Several Capital Hilton gigs appear ready for invoice review.",
            concise_spoken_guidance="Start the Capital Hilton invoice review when you are ready.",
            reason_for_attention="local_device_action_required",
            operator_only_reason="Fixture reminder: workbook intake or field mapping may be needed before invoice audit.",
            urgency_level="high",
            delivery_targets_allowed=("mac_helm", "active_chat"),
            operator_presence_context="active_in_chat",
            display_policy="auto_open_surface_when_active",
            primary_human_action_label="Start invoice",
            linked_local_surface_request=local_surface.capital_hilton_workbook_file_request(),
            fixture_ref="capital_hilton_invoice_workbook_candidate",
            required_confirmation=False,
        ),
        "chief_bank_ledger_stale": make_attention_item(
            attention_key="chief_bank_ledger_stale",
            world_ref="finance",
            workflow_ref="bank_ledger_update",
            actor_label="Chief",
            human_message="Your bank ledger appears stale. Download the statement from the last known update date to today.",
            concise_spoken_guidance="Update the ledger by adding the latest statement file.",
            reason_for_attention="stale_failure_state",
            operator_only_reason="Fixture stale-ledger reminder only; no live bank facts or bank access are claimed.",
            urgency_level="medium",
            delivery_targets_allowed=("mac_helm", "telegram_candidate", "mobile_notification_candidate"),
            operator_presence_context="away",
            display_policy="show_single_action_when_away",
            primary_human_action_label="Update ledger",
            linked_local_surface_request=_statement_intake_surface(),
            fixture_ref="bank_ledger_statement_intake_candidate",
        ),
        "guardian_protected_file_boundary": make_attention_item(
            attention_key="guardian_protected_file_boundary",
            world_ref="security",
            workflow_ref="protected_file_boundary",
            actor_label="Guardian",
            human_message="A protected-file boundary needs review before OpenClaw can proceed.",
            concise_spoken_guidance="Review the protected-file boundary.",
            reason_for_attention="protected_boundary_decision",
            operator_only_reason="Protected/private handling must be confirmed before any private file body access.",
            urgency_level="high",
            delivery_targets_allowed=("mac_helm", "active_chat"),
            operator_presence_context="active_in_chat",
            display_policy="auto_open_surface_when_active",
            primary_human_action_label="Review boundary",
            linked_local_surface_request=_guardian_boundary_surface(),
            fixture_ref="guardian_protected_file_boundary_fixture",
            required_confirmation=True,
        ),
        "niles_music_scene_file": make_attention_item(
            attention_key="niles_music_scene_file",
            world_ref="music",
            workflow_ref="x32_scene_or_monitor_mix",
            actor_label="Niles",
            human_message="Add the scene file when you want Niles to inspect the local music context.",
            concise_spoken_guidance="Add the scene file when you are ready.",
            reason_for_attention="local_device_action_required",
            operator_only_reason="Fixture music prompt only; no hardware control or file mutation is allowed.",
            urgency_level="low",
            delivery_targets_allowed=("mac_helm", "telegram_candidate"),
            operator_presence_context="away",
            display_policy="show_single_action_when_away",
            primary_human_action_label="Add scene file",
            linked_local_surface_request=_niles_scene_surface(),
            fixture_ref="niles_x32_scene_file_candidate",
        ),
        "quiet_below_deck_backend_handled": make_attention_item(
            attention_key="quiet_below_deck_backend_handled",
            world_ref="systems",
            actor_label="OpenClaw System",
            human_message="A backend read-model refreshed without needing operator action.",
            concise_spoken_guidance="No action needed.",
            reason_for_attention="quiet_backend_handled",
            operator_only_reason="The backend can handle this quietly; no local surface should appear.",
            urgency_level="low",
            delivery_targets_allowed=(),
            operator_presence_context="unknown",
            display_policy="quiet_below_deck",
            primary_human_action_label="No action",
            linked_local_surface_request=_quiet_surface(),
            fixture_ref="quiet_backend_readmodel_refresh_fixture",
            receipt_required_after_operator_action=False,
        ),
    }
    return {name: asdict(item) for name, item in items.items()}


def should_surface_item(item: Mapping[str, Any]) -> bool:
    return item.get("display_policy") not in {"quiet_below_deck", "proof_only"} and bool(
        item.get("primary_human_action_label")
    )


def validate_attention_item(item: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if item.get("actor_label") not in ACTOR_LABELS:
        errors.append("UNKNOWN_ACTOR_LABEL")
    if item.get("urgency_level") not in URGENCY_LEVELS:
        errors.append("UNKNOWN_URGENCY_LEVEL")
    if item.get("reason_for_attention") not in ATTENTION_REASONS:
        errors.append("UNKNOWN_ATTENTION_REASON")
    if item.get("operator_presence_context") not in OPERATOR_PRESENCE_CONTEXTS:
        errors.append("UNKNOWN_OPERATOR_PRESENCE_CONTEXT")
    if item.get("display_policy") not in DISPLAY_POLICIES:
        errors.append("UNKNOWN_DISPLAY_POLICY")
    if item.get("operator_presence_context") == "active_in_chat" and item.get("display_policy") != "auto_open_surface_when_active":
        errors.append("ACTIVE_IN_CHAT_SHOULD_AUTO_OPEN_SAFE_SURFACE")
    if item.get("operator_presence_context") == "away" and item.get("display_policy") != "show_single_action_when_away":
        errors.append("AWAY_SHOULD_SHOW_SINGLE_ACTION")
    if item.get("reason_for_attention") == "quiet_backend_handled" and item.get("display_policy") != "quiet_below_deck":
        errors.append("NO_ACTION_ITEM_SHOULD_BE_QUIET")
    targets = item.get("delivery_targets_allowed") if isinstance(item.get("delivery_targets_allowed"), (list, tuple)) else ()
    for target in targets:
        if target not in DELIVERY_TARGETS:
            errors.append("UNKNOWN_DELIVERY_TARGET")
    if item.get("external_delivery_allowed") is not False:
        errors.append("EXTERNAL_DELIVERY_NOT_ALLOWED")
    if item.get("telegram_send_allowed") is not False:
        errors.append("TELEGRAM_SEND_NOT_ALLOWED")
    if item.get("push_allowed") is not False:
        errors.append("PUSH_NOT_ALLOWED")
    if item.get("email_send_allowed") is not False:
        errors.append("EMAIL_SEND_NOT_ALLOWED")
    if item.get("external_action_allowed") is not False:
        errors.append("EXTERNAL_ACTION_NOT_ALLOWED")
    authority = item.get("authority_boundary") if isinstance(item.get("authority_boundary"), Mapping) else {}
    if any(value is True for value in authority.values()):
        errors.append("LIVE_AUTHORITY_NOT_ALLOWED")
    surface_request = (
        item.get("linked_local_surface_request")
        if isinstance(item.get("linked_local_surface_request"), Mapping)
        else {}
    )
    if not surface_request:
        errors.append("LOCAL_SURFACE_REQUEST_REQUIRED")
    else:
        errors.extend(local_surface.validate_surface_request(surface_request))
        if surface_request.get("raw_body_allowed") is not False:
            errors.append("LINKED_SURFACE_RAW_BODY_NOT_ALLOWED")
        if surface_request.get("external_model_share_allowed") is not False:
            errors.append("LINKED_SURFACE_EXTERNAL_MODEL_SHARE_NOT_ALLOWED")
        if surface_request.get("external_action_allowed") is not False:
            errors.append("LINKED_SURFACE_EXTERNAL_ACTION_NOT_ALLOWED")
    binding = (
        item.get("attention_to_local_surface_binding")
        if isinstance(item.get("attention_to_local_surface_binding"), Mapping)
        else {}
    )
    if not binding:
        errors.append("ATTENTION_TO_LOCAL_SURFACE_BINDING_REQUIRED")
    else:
        if binding.get("local_surface_type") != surface_request.get("surface_type"):
            errors.append("BINDING_SURFACE_TYPE_MISMATCH")
        if binding.get("direct_execution_allowed") is not False:
            errors.append("BINDING_DIRECT_EXECUTION_NOT_ALLOWED")
    if any(target.endswith("_candidate") for target in targets) and (
        item.get("telegram_send_allowed") is not False
        or item.get("push_allowed") is not False
        or item.get("email_send_allowed") is not False
    ):
        errors.append("CANDIDATE_DELIVERY_CANNOT_SEND")
    if item.get("display_policy") == "quiet_below_deck":
        if surface_request.get("surface_type") != "NO_SURFACE_REQUEST":
            errors.append("QUIET_ITEM_MUST_NOT_OPEN_SURFACE")
        if targets:
            errors.append("QUIET_ITEM_MUST_NOT_HAVE_DELIVERY_TARGETS")
    if not _no_real_path(item):
        errors.append("REAL_PATH_OR_GUESSED_PATH_MARKER_PRESENT")
    return tuple(dict.fromkeys(errors))


def validate_payload(payload: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    items = payload.get("attention_items") if isinstance(payload.get("attention_items"), Mapping) else {}
    return {name: validate_attention_item(item) for name, item in items.items()}


def build_readback(items: Mapping[str, Mapping[str, Any]], validation: Mapping[str, tuple[str, ...]]) -> OperatorAttentionReadback:
    surfaced = [item for item in items.values() if should_surface_item(item)]
    quiet = [item for item in items.values() if not should_surface_item(item)]
    return OperatorAttentionReadback(
        readback_id=f"operator_attention_readback:{_short_hash(SCHEMA_VERSION, len(items), len(surfaced))}",
        status="OPERATOR_ATTENTION_DELIVERY_CONTRACT_READY",
        operator_headline="Operator attention contract ready",
        operator_message=(
            "OpenClaw can describe why something needs Winship's attention and bind the one safe human action "
            "to a local surface request. External delivery remains candidate-only."
        ),
        surfaced_item_count=len(surfaced),
        quiet_item_count=len(quiet),
        primary_next_action="Next: use attention items as presentation contracts only; local surface results must return metadata or receipts.",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this read-model to choose one calm local action without sending, launching, dispatching, or executing workflows.",
    )


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    policy = default_delivery_policy()
    items = build_attention_items()
    validation = {name: validate_attention_item(item) for name, item in items.items()}
    surfaced_items = {name: item for name, item in items.items() if should_surface_item(item)}
    quiet_items = {name: item for name, item in items.items() if not should_surface_item(item)}
    readback = build_readback(items, validation)
    actions = {
        name: asdict(
            make_attention_action(
                attention_id=item["attention_id"],
                label=item["primary_human_action_label"],
                linked_local_surface_request=item["linked_local_surface_request"],
                receipt_required_after_operator_action=item["receipt_required_after_operator_action"],
            )
        )
        for name, item in items.items()
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "model_schemas": {
            "OperatorAttentionItem": tuple(field.name for field in fields(OperatorAttentionItem)),
            "OperatorAttentionReason": tuple(field.name for field in fields(OperatorAttentionReason)),
            "OperatorAttentionDeliveryPolicy": tuple(field.name for field in fields(OperatorAttentionDeliveryPolicy)),
            "OperatorAttentionSurface": tuple(field.name for field in fields(OperatorAttentionSurface)),
            "OperatorAttentionAction": tuple(field.name for field in fields(OperatorAttentionAction)),
            "OperatorAttentionReadback": tuple(field.name for field in fields(OperatorAttentionReadback)),
            "OperatorPresenceContext": tuple(field.name for field in fields(OperatorPresenceContext)),
            "AttentionToLocalSurfaceBinding": tuple(field.name for field in fields(AttentionToLocalSurfaceBinding)),
        },
        "operator_presence_contexts": tuple(asdict(context) for context in presence_contexts()),
        "attention_reasons": tuple(asdict(reason) for reason in attention_reasons()),
        "attention_surfaces": tuple(asdict(surface) for surface in attention_surfaces()),
        "delivery_policy": asdict(policy),
        "attention_items": items,
        "operator_attention_actions": actions,
        "surfaced_attention_items": surfaced_items,
        "quiet_attention_items": quiet_items,
        "attention_item_validation": validation,
        "readback": asdict(readback),
        "local_surface_contract_ref": local_surface.READ_MODEL_ID,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "operator_attention_contract_present": True,
            "local_surface_contract_bound": True,
            "all_items_validate": all(not errors for errors in validation.values()),
            "all_attention_actions_bind_to_local_surface_request": all(
                bool(item.get("attention_to_local_surface_binding")) for item in items.values()
            ),
            "all_linked_surface_requests_validate": all(
                not local_surface.validate_surface_request(item["linked_local_surface_request"])
                for item in items.values()
            ),
            "active_in_chat_prefers_auto_open_surface_when_active": all(
                item["display_policy"] == "auto_open_surface_when_active"
                for item in items.values()
                if item["operator_presence_context"] == "active_in_chat"
            ),
            "away_uses_single_action_when_away": all(
                item["display_policy"] == "show_single_action_when_away"
                for item in items.values()
                if item["operator_presence_context"] == "away"
            ),
            "no_action_items_are_quiet_below_deck": all(
                item["display_policy"] == "quiet_below_deck"
                for item in items.values()
                if item["reason_for_attention"] == "quiet_backend_handled"
            ),
            "candidate_delivery_only": all(
                item["external_delivery_allowed"] is False
                and item["telegram_send_allowed"] is False
                and item["push_allowed"] is False
                and item["email_send_allowed"] is False
                for item in items.values()
            ),
            "capital_hilton_fixture_uses_fixture_ref_only": _no_real_path(
                items["cassandra_capital_hilton_invoice_reminder"]
            )
            and items["cassandra_capital_hilton_invoice_reminder"]["fixture_ref"]
            == "capital_hilton_invoice_workbook_candidate",
            "device_ui_implemented": False,
            "telegram_send_performed": False,
            "push_notification_performed": False,
            "email_send_performed": False,
            "app_launch_performed": False,
            "browser_access_performed": False,
            "network_used": False,
            "file_body_read_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "ocr_performed": False,
            "coupa_access_or_submit_performed": False,
            "credential_handling_performed": False,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "workflow_execution_performed": False,
            "external_action_performed": False,
            "path_translation_guess_performed": False,
            "send_submit_performed": False,
            "fake_financial_fact_created": False,
            "fake_receipt_created": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload.get("readback") if isinstance(payload.get("readback"), Mapping) else {}
    items = payload.get("attention_items") if isinstance(payload.get("attention_items"), Mapping) else {}
    surfaced = payload.get("surfaced_attention_items") if isinstance(payload.get("surfaced_attention_items"), Mapping) else {}
    lines = [
        "# Operator Attention Delivery Contract",
        "",
        "ELIOPERATOR: Attention contract only. No Telegram, push, email, app launch, browser, Coupa, credential, model, agent, workflow, file-body, or workbook/cell action occurred.",
        "",
        f"- Status: `{readback.get('status', 'UNKNOWN')}`",
        f"- Attention items: `{len(items)}`",
        f"- Surfaced items: `{len(surfaced)}`",
        f"- Quiet items: `{readback.get('quiet_item_count', 0)}`",
        "",
        "## Example Attention Items",
        "",
        *[
            f"- {item.get('actor_label', 'OpenClaw System')}: {item.get('primary_human_action_label', 'No action')} -> `{item.get('linked_local_surface_request', {}).get('surface_type', 'NO_SURFACE_REQUEST')}`"
            for item in items.values()
        ],
        "",
        "## Next",
        "",
        str(readback.get("primary_next_action") or "Use local surface bindings for one safe human action."),
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
    readback = payload.get("readback") if isinstance(payload.get("readback"), Mapping) else {}
    return {
        "read_model_id": payload.get("read_model_id"),
        "contract_status": payload.get("contract_status"),
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "status": readback.get("status"),
        "attention_item_count": len(payload.get("attention_items") or {}),
        "surfaced_item_count": readback.get("surfaced_item_count"),
        "quiet_item_count": readback.get("quiet_item_count"),
        "local_surface_contract_bound": proof.get("local_surface_contract_bound"),
        "all_items_validate": proof.get("all_items_validate"),
        "candidate_delivery_only": proof.get("candidate_delivery_only"),
        "all_live_authority_false": proof.get("all_live_authority_false"),
        "content_hash": proof.get("content_hash"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export operator attention delivery contract.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    paths = write_exports(payload, Path(args.export_root))
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
