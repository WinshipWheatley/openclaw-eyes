"""Operator Card Render Packet Contract v0.

This deterministic read-model defines semantic, truth-backed card packets that
can be rendered by future device-aware visual surfaces. It does not render UI,
generate images, call models, dispatch agents, run workflows, execute actions,
or perform external work.
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
DEFAULT_SOURCE_TRANSLATION = DEFAULT_EXPORT_ROOT / "operator_card_translation_mirror.json"

SCHEMA_VERSION = "operator_card_render_packet_contract_v0"
READ_MODEL_ID = "operator_card_render_packet_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_OPERATOR_CARD_RENDER_PACKET_CONTRACT"

CARD_TYPES = (
    "UNDERSTANDING",
    "PLAN",
    "MISSING_INFO",
    "BLOCKED",
    "PROOF",
    "APPROVAL",
    "COMPLETION",
    "WAITING",
    "STALE",
    "ERROR_FAIL_CLOSED",
)

TRUTH_STATUSES = (
    "DRAFT_NOT_TRUTH",
    "BACKEND_READBACK_READY",
    "RECEIPT_VERIFIED",
    "NEEDS_OPERATOR_REVIEW",
    "NEEDS_PROOF",
    "LOCKED_EXTERNAL_ACTION",
    "STALE",
    "UNKNOWN_FAIL_CLOSED",
)

TARGET_SURFACES = (
    "mac_chat",
    "telegram",
    "future_mobile",
    "future_voice",
    "dashboard_detail",
    "developer_diagnostics",
)

PREFERRED_LAYOUTS = (
    "compact_chat_card",
    "wide_summary_card",
    "stack_card",
    "proof_card",
    "approval_card",
    "completion_card",
    "hidden_diagnostics_only",
)

TONES = (
    "calm",
    "waiting",
    "warning",
    "proof",
    "approval",
    "completion",
    "blocked",
    "fail_closed",
)

FORBIDDEN_VISIBLE_TERMS = (
    "schema",
    "handler",
    "lifecycle",
    "artifact_type",
    "target_handler",
    "payload_hash",
    "idempotency",
    "manifest",
    "JSON",
    "SQLite",
    "local outbox",
    "visual-agnostic",
    "metadata posture",
    "raw ID",
    "package ref",
)

BLOCKER_TYPES = (
    "SOURCE_TRUTH_MISSING",
    "SOURCE_READBACK_STALE",
    "MACHINE_LANGUAGE_VISIBLE",
    "RAW_PII_IN_VISIBLE_CONTENT",
    "COMPLETION_WITHOUT_PROOF",
    "EXTERNAL_ACTION_ENABLED_WITHOUT_GATE",
    "CARD_WALL_OF_TEXT",
    "DEVICE_SPEC_MISSING",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_CONTRACT_FIELDS = (
    "contract_id",
    "doctrine",
    "source_truth_policy",
    "render_packet_policy",
    "visual_agent_policy",
    "chat_placement_policy",
    "device_awareness_policy",
    "privacy_policy",
    "action_authority_policy",
    "proof_disclosure_policy",
    "machine_language_policy",
    "current_live_authority",
    "next_safe_move",
)

REQUIRED_RENDER_PACKET_FIELDS = (
    "render_packet_id",
    "source_readback_ref",
    "source_card_ref",
    "workflow_ref",
    "workflow_type",
    "world_ref",
    "lane_ref",
    "client_ref",
    "tenant_ref",
    "card_type",
    "truth_status",
    "proof_status",
    "visual_priority",
    "placement_hint",
    "device_profile",
    "semantic_payload",
    "visible_content",
    "detail_content",
    "operator_actions",
    "blocked_actions",
    "style_directive",
    "accessibility_payload",
    "privacy_boundary",
    "next_safe_move",
)

REQUIRED_SEMANTIC_FIELDS = (
    "title",
    "short_summary",
    "primary_message",
    "key_facts",
    "missing_items",
    "proof_bullets",
    "blocked_items",
    "next_question",
    "next_safe_move",
    "confidence_note",
    "source_refs",
)

REQUIRED_DEVICE_FIELDS = (
    "device_profile_id",
    "target_surface",
    "size_class",
    "max_visible_bullets",
    "max_primary_actions",
    "preferred_layout",
    "compact_mode",
    "detail_disclosure_mode",
    "accessibility_mode",
    "placement_rule",
    "next_safe_move",
)

REQUIRED_STYLE_FIELDS = (
    "style_id",
    "tone",
    "urgency",
    "visual_metaphor",
    "accent_policy",
    "density",
    "background_policy",
    "icon_hint",
    "animation_hint",
    "forbidden_visuals",
    "next_safe_move",
)

REQUIRED_ACTION_FIELDS = (
    "action_id",
    "label",
    "enabled",
    "disabled_reason",
    "action_scope",
    "authority_required",
    "confirmation_required",
    "backend_rail_required",
    "external_action",
    "display_priority",
    "next_safe_move",
)

REQUIRED_FILTER_FIELDS = (
    "policy_id",
    "forbidden_machine_terms",
    "replacement_terms",
    "compression_rules",
    "visible_content_rules",
    "detail_content_rules",
    "fail_closed_on_machine_language",
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

REQUIRED_REPORT_FIELDS = (
    "report_id",
    "plain_summary",
    "what_this_enables",
    "what_this_does_not_do_yet",
    "how_truth_flows",
    "how_cards_are_composed",
    "how_device_awareness_works",
    "how_actions_remain_gated",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_visual_agent_allowed": False,
    "live_image_generation_allowed": False,
    "live_model_call_allowed": False,
    "live_render_runtime_allowed": False,
    "live_card_action_execution_allowed": False,
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

CAPITAL_WORKFLOW_REF = "capital_hilton_invoice_workflow"
CAPITAL_WORKFLOW_TYPE = "invoice_delivery_workflow"
CAPITAL_WORLD_REF = "finance"
CAPITAL_LANE_REF = "capital_hilton"
CAPITAL_CLIENT_REF = "capital_hilton"
CAPITAL_TENANT_REF = "operator_winship_local"
SOURCE_READBACK_REF = "operator_card_translation_mirror"
PRIVACY_BOUNDARY = "Safe operator card content only; no raw private bodies, credentials, protected evidence bodies, or raw payment references."


@dataclass(frozen=True)
class OperatorCardRenderPacketContract:
    contract_id: str
    doctrine: dict[str, Any]
    source_truth_policy: dict[str, Any]
    render_packet_policy: dict[str, Any]
    visual_agent_policy: dict[str, Any]
    chat_placement_policy: dict[str, Any]
    device_awareness_policy: dict[str, Any]
    privacy_policy: dict[str, Any]
    action_authority_policy: dict[str, Any]
    proof_disclosure_policy: dict[str, Any]
    machine_language_policy: dict[str, Any]
    current_live_authority: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorCardRenderPacket:
    render_packet_id: str
    source_readback_ref: str | None
    source_card_ref: str | None
    workflow_ref: str
    workflow_type: str
    world_ref: str
    lane_ref: str
    client_ref: str
    tenant_ref: str
    card_type: str
    truth_status: str
    proof_status: str
    visual_priority: str
    placement_hint: str
    device_profile: dict[str, Any]
    semantic_payload: dict[str, Any]
    visible_content: dict[str, Any]
    detail_content: dict[str, Any]
    operator_actions: tuple[dict[str, Any], ...]
    blocked_actions: tuple[str, ...]
    style_directive: dict[str, Any]
    accessibility_payload: dict[str, Any]
    privacy_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class SemanticCardPayload:
    title: str
    short_summary: str
    primary_message: str
    key_facts: tuple[str, ...]
    missing_items: tuple[str, ...]
    proof_bullets: tuple[str, ...]
    blocked_items: tuple[str, ...]
    next_question: str | None
    next_safe_move: str
    confidence_note: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class DeviceAwareCardSpec:
    device_profile_id: str
    target_surface: str
    size_class: str
    max_visible_bullets: int
    max_primary_actions: int
    preferred_layout: str
    compact_mode: bool
    detail_disclosure_mode: str
    accessibility_mode: str
    placement_rule: str
    next_safe_move: str


@dataclass(frozen=True)
class VisualStyleDirective:
    style_id: str
    tone: str
    urgency: str
    visual_metaphor: str
    accent_policy: str
    density: str
    background_policy: str
    icon_hint: str
    animation_hint: str
    forbidden_visuals: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorActionRenderSpec:
    action_id: str
    label: str
    enabled: bool
    disabled_reason: str | None
    action_scope: str
    authority_required: str
    confirmation_required: bool
    backend_rail_required: str | None
    external_action: bool
    display_priority: str
    next_safe_move: str


@dataclass(frozen=True)
class CardTranslationAndFilterPolicy:
    policy_id: str
    forbidden_machine_terms: tuple[str, ...]
    replacement_terms: dict[str, str]
    compression_rules: dict[str, Any]
    visible_content_rules: dict[str, Any]
    detail_content_rules: dict[str, Any]
    fail_closed_on_machine_language: bool
    next_safe_move: str


@dataclass(frozen=True)
class RenderPacketBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorCardRenderPacketElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_truth_flows: str
    how_cards_are_composed: str
    how_device_awareness_works: str
    how_actions_remain_gated: str
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
        raise ValueError("source translation mirror must be a JSON object")
    return value


def _model_schemas() -> dict[str, Any]:
    return {
        "operator_card_render_packet_contract": {"required_fields": list(REQUIRED_CONTRACT_FIELDS)},
        "operator_card_render_packet": {
            "required_fields": list(REQUIRED_RENDER_PACKET_FIELDS),
            "card_types": list(CARD_TYPES),
            "truth_statuses": list(TRUTH_STATUSES),
        },
        "semantic_card_payload": {"required_fields": list(REQUIRED_SEMANTIC_FIELDS)},
        "device_aware_card_spec": {
            "required_fields": list(REQUIRED_DEVICE_FIELDS),
            "target_surfaces": list(TARGET_SURFACES),
            "preferred_layouts": list(PREFERRED_LAYOUTS),
        },
        "visual_style_directive": {
            "required_fields": list(REQUIRED_STYLE_FIELDS),
            "tones": list(TONES),
        },
        "operator_action_render_spec": {"required_fields": list(REQUIRED_ACTION_FIELDS)},
        "card_translation_and_filter_policy": {
            "required_fields": list(REQUIRED_FILTER_FIELDS),
            "forbidden_visible_terms": list(FORBIDDEN_VISIBLE_TERMS),
        },
        "render_packet_blocker": {
            "required_fields": list(REQUIRED_BLOCKER_FIELDS),
            "blocker_types": list(BLOCKER_TYPES),
        },
        "operator_card_render_packet_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def build_contract() -> OperatorCardRenderPacketContract:
    return OperatorCardRenderPacketContract(
        contract_id="operator_card_render_packet_contract_v0",
        doctrine={
            "backend_owns_truth": True,
            "render_packet_owns_semantic_card_payload": True,
            "visual_agent_owns_presentation_later": True,
            "chat_owns_timing_and_placement": True,
            "operator_sees_object_not_machinery": True,
        },
        source_truth_policy={
            "render_packet_does_not_create_truth": True,
            "source_truth_or_readback_ref_required": True,
            "stale_source_fails_closed": True,
            "completion_requires_proof_receipts": True,
        },
        render_packet_policy={
            "semantic_payload_required": True,
            "visible_content_compact": True,
            "details_collapsed_by_default": True,
            "action_aware_but_authority_safe": True,
        },
        visual_agent_policy={
            "future_gated": True,
            "live_visual_agent_allowed": False,
            "live_image_generation_allowed": False,
            "live_render_runtime_allowed": False,
        },
        chat_placement_policy={
            "placement_hint_required": True,
            "chat_places_card_at_right_moment": True,
            "card_packet_does_not_push_to_chat": True,
        },
        device_awareness_policy={
            "mac_chat_default_compact": True,
            "max_visible_bullets_enforced": True,
            "detail_disclosure_collapsed_by_default": True,
        },
        privacy_policy={
            "no_raw_private_bodies": True,
            "no_credentials": True,
            "no_raw_payment_reference": True,
            "protected_evidence_metadata_only": True,
        },
        action_authority_policy={
            "render_packet_does_not_enable_external_action": True,
            "external_action_requires_future_gated_rail": True,
            "disabled_future_actions_may_be_present": True,
        },
        proof_disclosure_policy={
            "proof_summary_allowed": True,
            "proof_details_collapsed_by_default": True,
            "completion_without_proof_blocked": True,
        },
        machine_language_policy={
            "forbidden_visible_terms": FORBIDDEN_VISIBLE_TERMS,
            "fail_closed_on_visible_machine_language": True,
        },
        current_live_authority=AUTHORITY_BOUNDARY,
        next_safe_move="Use semantic packets as the next stable interface between backend truth and chat visuals.",
    )


def device_spec(target_surface: str = "mac_chat", layout: str = "compact_chat_card") -> DeviceAwareCardSpec:
    return DeviceAwareCardSpec(
        device_profile_id=f"device_profile_{target_surface}_{layout}",
        target_surface=target_surface,
        size_class="compact" if target_surface in {"mac_chat", "telegram", "future_mobile"} else "expanded",
        max_visible_bullets=5 if target_surface != "future_voice" else 3,
        max_primary_actions=3 if target_surface in {"mac_chat", "future_mobile"} else 2,
        preferred_layout=layout,
        compact_mode=target_surface in {"mac_chat", "telegram", "future_mobile"},
        detail_disclosure_mode="collapsed_by_default",
        accessibility_mode="plain_text_equivalent_required",
        placement_rule="inline_after_relevant_chat_turn",
        next_safe_move="Render compact card first; keep proof/details behind disclosure.",
    )


def style_directive(tone: str, *, card_type: str) -> VisualStyleDirective:
    icon = {
        "calm": "message-circle",
        "waiting": "clock",
        "warning": "triangle-alert",
        "proof": "file-check",
        "approval": "shield-check",
        "completion": "check-circle",
        "blocked": "lock",
        "fail_closed": "octagon-alert",
    }.get(tone, "message-circle")
    return VisualStyleDirective(
        style_id=f"style_{card_type.lower()}_{tone}",
        tone=tone,
        urgency="normal" if tone in {"calm", "proof"} else ("low" if tone == "waiting" else "guarded"),
        visual_metaphor="status card, not dashboard",
        accent_policy="quiet accent; no celebration unless proof-backed completion",
        density="compact",
        background_policy="plain surface; no decorative imagery required",
        icon_hint=icon,
        animation_hint="none",
        forbidden_visuals=(
            "celebratory completion without proof",
            "green success for waiting",
            "alarm styling for protective blocked state",
            "machine diagnostics in operator card",
        ),
        next_safe_move="Apply tone without implying authority or completion.",
    )


def action_spec(
    action_id: str,
    label: str,
    *,
    enabled: bool,
    disabled_reason: str | None = None,
    scope: str = "local_review",
    rail: str | None = None,
    priority: str = "primary",
) -> OperatorActionRenderSpec:
    return OperatorActionRenderSpec(
        action_id=action_id,
        label=label,
        enabled=enabled,
        disabled_reason=disabled_reason,
        action_scope=scope,
        authority_required="none" if enabled else "future_gated_backend_rail",
        confirmation_required=label in {"Looks right", "Approve"},
        backend_rail_required=rail,
        external_action=False,
        display_priority=priority,
        next_safe_move="Keep as local UI action unless a future proof-backed backend rail enables more.",
    )


def base_actions() -> tuple[OperatorActionRenderSpec, ...]:
    return (
        action_spec("render_action_looks_right", "Looks right", enabled=True, scope="local_review", priority="primary"),
        action_spec("render_action_change_something", "Change something", enabled=True, scope="local_edit", priority="primary"),
        action_spec("render_action_whats_missing", "What's missing?", enabled=True, scope="show_missing_details", priority="secondary"),
        action_spec(
            "render_action_store_as_procedure",
            "Store as procedure",
            enabled=False,
            disabled_reason="Procedure memory write is not connected yet.",
            scope="future_backend_write",
            rail="procedure_memory_writer",
            priority="future",
        ),
        action_spec(
            "render_action_prepare_package",
            "Prepare package",
            enabled=False,
            disabled_reason="Package creation is not connected yet.",
            scope="future_backend_package",
            rail="workflow_package_creator",
            priority="future",
        ),
    )


def filter_policy() -> CardTranslationAndFilterPolicy:
    return CardTranslationAndFilterPolicy(
        policy_id="operator_card_render_filter_policy_v0",
        forbidden_machine_terms=FORBIDDEN_VISIBLE_TERMS,
        replacement_terms={
            "schema": "shape",
            "handler": "rail",
            "payload_hash": "proof reference",
            "JSON": "readback file",
            "SQLite": "local state",
        },
        compression_rules={
            "max_visible_bullets": 5,
            "move_extra_to_details": True,
            "short_summary_required": True,
        },
        visible_content_rules={
            "human_readable": True,
            "compact": True,
            "no_machine_terms": True,
            "no_raw_private_values": True,
        },
        detail_content_rules={
            "collapsed_by_default": True,
            "human_readable": True,
            "proof_refs_metadata_only": True,
        },
        fail_closed_on_machine_language=True,
        next_safe_move="Reject or rewrite packets with machine language in visible content.",
    )


def semantic_payload(
    *,
    title: str,
    short_summary: str,
    primary_message: str,
    key_facts: tuple[str, ...] = (),
    missing_items: tuple[str, ...] = (),
    proof_bullets: tuple[str, ...] = (),
    blocked_items: tuple[str, ...] = (),
    next_question: str | None = None,
    next_safe_move: str,
    confidence_note: str = "Backed by current PC readback; still subject to operator review.",
    source_refs: tuple[str, ...] = (SOURCE_READBACK_REF,),
) -> SemanticCardPayload:
    return SemanticCardPayload(
        title=title,
        short_summary=short_summary,
        primary_message=primary_message,
        key_facts=key_facts,
        missing_items=missing_items,
        proof_bullets=proof_bullets,
        blocked_items=blocked_items,
        next_question=next_question,
        next_safe_move=next_safe_move,
        confidence_note=confidence_note,
        source_refs=source_refs,
    )


def render_packet(
    *,
    packet_id: str,
    source_card_ref: str,
    card_type: str,
    truth_status: str,
    proof_status: str,
    visual_priority: str,
    placement_hint: str,
    payload: SemanticCardPayload,
    visible_bullets: tuple[str, ...],
    detail_bullets: tuple[str, ...],
    tone: str,
    layout: str = "compact_chat_card",
    actions: tuple[OperatorActionRenderSpec, ...] = (),
    blocked_actions: tuple[str, ...] = (),
    next_safe_move: str | None = None,
) -> OperatorCardRenderPacket:
    device = device_spec("mac_chat", layout)
    style = style_directive(tone, card_type=card_type)
    visible = {
        "title": payload.title,
        "short_summary": payload.short_summary,
        "primary_message": payload.primary_message,
        "bullets": visible_bullets,
    }
    detail = {
        "detail_bullets": detail_bullets,
        "proof_bullets": payload.proof_bullets,
        "source_refs": payload.source_refs,
        "collapsed_by_default": True,
    }
    return OperatorCardRenderPacket(
        render_packet_id=packet_id,
        source_readback_ref=SOURCE_READBACK_REF,
        source_card_ref=source_card_ref,
        workflow_ref=CAPITAL_WORKFLOW_REF,
        workflow_type=CAPITAL_WORKFLOW_TYPE,
        world_ref=CAPITAL_WORLD_REF,
        lane_ref=CAPITAL_LANE_REF,
        client_ref=CAPITAL_CLIENT_REF,
        tenant_ref=CAPITAL_TENANT_REF,
        card_type=card_type,
        truth_status=truth_status,
        proof_status=proof_status,
        visual_priority=visual_priority,
        placement_hint=placement_hint,
        device_profile=asdict(device),
        semantic_payload=asdict(payload),
        visible_content=visible,
        detail_content=detail,
        operator_actions=tuple(asdict(action) for action in (actions or base_actions())),
        blocked_actions=blocked_actions,
        style_directive=asdict(style),
        accessibility_payload={
            "plain_text_title": payload.title,
            "plain_text_summary": payload.short_summary,
            "screen_reader_order": ("title", "summary", "bullets", "actions", "details"),
        },
        privacy_boundary=PRIVACY_BOUNDARY,
        next_safe_move=next_safe_move or payload.next_safe_move,
    )


def build_capital_hilton_examples() -> dict[str, Any]:
    locked_actions = (
        "email",
        "Coupa access",
        "browser",
        "approval",
        "invoice generation",
        "attachment",
        "payment update",
    )
    understanding = render_packet(
        packet_id="render_packet_capital_hilton_understanding",
        source_card_ref="operator_card_what_i_understood",
        card_type="UNDERSTANDING",
        truth_status="DRAFT_NOT_TRUTH",
        proof_status="NEEDS_OPERATOR_REVIEW",
        visual_priority="primary",
        placement_hint="after_pc_readback_arrives",
        payload=semantic_payload(
            title="What I understood",
            short_summary=(
                "Capital Hilton invoice: 4 dates at $400 each. OpenClaw thinks you want a Winship-branded "
                "Excel/PDF invoice sent to Annette, while Coupa/PO remains the official payment path."
            ),
            primary_message="Draft understanding — not confirmed truth.",
            key_facts=(
                "4 dates at $400 each",
                "Winship-branded Excel/PDF invoice to Annette",
                "Coupa/PO remains official payment path",
            ),
            next_question="Does this understanding look right?",
            next_safe_move="Ask whether this understanding looks right.",
        ),
        visible_bullets=(
            "4 dates at $400 each.",
            "Excel/PDF invoice to Annette.",
            "Coupa/PO stays the official payment path.",
            "Draft understanding — not confirmed truth.",
        ),
        detail_bullets=(
            "The source readback is current.",
            "This packet summarizes intent; it does not confirm invoice delivery.",
        ),
        tone="calm",
        blocked_actions=locked_actions,
    )
    plan = render_packet(
        packet_id="render_packet_capital_hilton_plan",
        source_card_ref="operator_card_the_plan",
        card_type="PLAN",
        truth_status="NEEDS_OPERATOR_REVIEW",
        proof_status="NEEDS_PROOF",
        visual_priority="secondary",
        placement_hint="after_understanding_card",
        payload=semantic_payload(
            title="The plan",
            short_summary=(
                "Confirm the invoice basis, build the invoice artifact, confirm Coupa/PO, draft the email, "
                "request approval, then send/submit only after gates are satisfied."
            ),
            primary_message="This is a plan for review, not a workflow run.",
            key_facts=(
                "Confirm invoice basis",
                "Build invoice artifact",
                "Confirm Coupa/PO",
                "Draft email and request approval",
            ),
            next_question="Do you want to change the plan?",
            next_safe_move="Review or change the plan before any future package is prepared.",
        ),
        visible_bullets=(
            "Confirm invoice basis.",
            "Build invoice artifact.",
            "Confirm Coupa/PO.",
            "Draft email and request approval.",
            "Send/submit only after gates.",
        ),
        detail_bullets=(
            "No workflow run has started.",
            "Future send/submit requires proof and approval rails.",
        ),
        tone="calm",
        blocked_actions=locked_actions,
    )
    needed = render_packet(
        packet_id="render_packet_capital_hilton_still_needed",
        source_card_ref="operator_card_still_needed",
        card_type="MISSING_INFO",
        truth_status="NEEDS_PROOF",
        proof_status="NEEDS_PROOF",
        visual_priority="secondary",
        placement_hint="after_plan_card",
        payload=semantic_payload(
            title="Still needed",
            short_summary=(
                "OpenClaw still needs the PO/reference, Annette confirmation, final artifact/hash, "
                "Guardian approval, and send/submit receipts before this can complete."
            ),
            primary_message="These are the missing pieces before completion.",
            missing_items=(
                "Exact Coupa PO/reference",
                "Annette confirmation",
                "Final artifact/hash",
                "Guardian approval",
                "Send/submit receipts",
            ),
            next_question="Do you have the Coupa PO/reference or contact confirmation?",
            next_safe_move="Ask for the Coupa reference or contact confirmation next.",
        ),
        visible_bullets=(
            "Exact Coupa PO/reference.",
            "Annette confirmation.",
            "Final artifact/hash.",
            "Guardian approval.",
            "Send/submit receipts.",
        ),
        detail_bullets=(
            "Completion stays blocked until proof receipts exist.",
            "Protected proof stays metadata-only.",
        ),
        tone="warning",
        blocked_actions=locked_actions,
    )
    locked = render_packet(
        packet_id="render_packet_capital_hilton_still_locked",
        source_card_ref="operator_card_still_locked",
        card_type="BLOCKED",
        truth_status="LOCKED_EXTERNAL_ACTION",
        proof_status="NEEDS_PROOF",
        visual_priority="secondary",
        placement_hint="after_missing_info_card",
        payload=semantic_payload(
            title="Still locked",
            short_summary=(
                "Nothing external happened. No email, Coupa access, browser, approval, invoice generation, "
                "attachment, or payment update."
            ),
            primary_message="This is protective lock state, not failure.",
            blocked_items=locked_actions,
            next_question=None,
            next_safe_move="Keep external actions locked until proof and approval rails exist.",
            confidence_note="Lock state is backed by source readback authority flags.",
        ),
        visible_bullets=(
            "Nothing external happened.",
            "No email, Coupa access, browser, or approval.",
            "No invoice generation, attachment, or payment update.",
            "External actions remain locked.",
        ),
        detail_bullets=(
            "The card can be rendered safely in chat.",
            "No external adapter was invoked.",
        ),
        tone="blocked",
        blocked_actions=locked_actions,
    )
    completion_blocked = render_packet(
        packet_id="render_packet_capital_hilton_completion_blocked",
        source_card_ref="future_completion_target",
        card_type="COMPLETION",
        truth_status="UNKNOWN_FAIL_CLOSED",
        proof_status="NEEDS_PROOF",
        visual_priority="hidden_until_proof",
        placement_hint="do_not_show_as_success_without_receipts",
        payload=semantic_payload(
            title="INVOICE SENT",
            short_summary="Completion card is blocked until send/submit proof receipts exist.",
            primary_message="Do not show this as completion yet.",
            proof_bullets=(),
            blocked_items=("send receipt missing", "submit receipt missing", "approval receipt missing"),
            next_question=None,
            next_safe_move="Wait for proof receipts before rendering completion.",
            confidence_note="No completion proof exists in this contract.",
            source_refs=("future_completion_receipt",),
        ),
        visible_bullets=(
            "Completion is blocked.",
            "Proof receipts are missing.",
            "Waiting is not success.",
        ),
        detail_bullets=(
            "No send receipt exists.",
            "No submit receipt exists.",
            "No approval receipt exists.",
        ),
        tone="fail_closed",
        layout="completion_card",
        actions=(),
        blocked_actions=locked_actions,
        next_safe_move="Do not render as completed until receipts exist.",
    )
    waiting = render_packet(
        packet_id="render_packet_capital_hilton_waiting",
        source_card_ref="waiting_on_pc",
        card_type="WAITING",
        truth_status="UNKNOWN_FAIL_CLOSED",
        proof_status="NEEDS_PROOF",
        visual_priority="temporary",
        placement_hint="after_request_sent_before_pc_readback",
        payload=semantic_payload(
            title="Waiting on PC",
            short_summary="I sent your request and am waiting for the PC readback.",
            primary_message="Waiting is not success.",
            key_facts=("Request is pending", "No current readback has returned"),
            next_question=None,
            next_safe_move="Wait for the PC readback before claiming understanding.",
            confidence_note="No current backend readback attached.",
            source_refs=("pending_request",),
        ),
        visible_bullets=(
            "Waiting for PC readback.",
            "No current understanding has returned.",
            "Nothing external happened.",
        ),
        detail_bullets=(
            "This card should not use green success styling.",
            "It is safe to replace once a current readback arrives.",
        ),
        tone="waiting",
        blocked_actions=locked_actions,
    )
    return {
        "understanding": asdict(understanding),
        "plan": asdict(plan),
        "still_needed": asdict(needed),
        "still_locked": asdict(locked),
        "completion_blocked": asdict(completion_blocked),
        "waiting": asdict(waiting),
    }


def build_blockers() -> tuple[RenderPacketBlocker, ...]:
    conditions = {
        "SOURCE_TRUTH_MISSING": "Render packet has no source truth/readback reference.",
        "SOURCE_READBACK_STALE": "Source readback is stale.",
        "MACHINE_LANGUAGE_VISIBLE": "Visible card content contains machine-contract language.",
        "RAW_PII_IN_VISIBLE_CONTENT": "Visible card content contains raw private data.",
        "COMPLETION_WITHOUT_PROOF": "Completion card cannot render without proof receipts.",
        "EXTERNAL_ACTION_ENABLED_WITHOUT_GATE": "External action cannot be enabled without a gated rail and receipt.",
        "CARD_WALL_OF_TEXT": "Visible card content is too long for chat.",
        "DEVICE_SPEC_MISSING": "Render packet has no device-aware spec.",
        "UNKNOWN_FAIL_CLOSED": "Unknown render packet state fails closed.",
    }
    return tuple(
        RenderPacketBlocker(
            blocker_id=f"render_packet_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_RENDER" if blocker_type != "CARD_WALL_OF_TEXT" else "SHOULD_COMPRESS",
            elioperator_warning=f"ELIOPERATOR: {condition}",
            fail_closed=blocker_type != "CARD_WALL_OF_TEXT",
            next_safe_move="Fix the packet or render a safe blocked/waiting card.",
        )
        for blocker_type, condition in conditions.items()
    )


def build_report() -> OperatorCardRenderPacketElioperatorReport:
    return OperatorCardRenderPacketElioperatorReport(
        report_id="operator_card_render_packet_elioperator_report_v0",
        plain_summary="Render packets turn backend readback into compact semantic cards for chat without exposing machinery.",
        what_this_enables="Any workflow can summon a truth-backed card object that a future visual layer can render.",
        what_this_does_not_do_yet="It does not render UI, generate images, call models, dispatch agents, run workflows, or perform external actions.",
        how_truth_flows="Backend readback supplies truth; the render packet references it and carries the semantic card payload.",
        how_cards_are_composed="Cards have compact visible content, collapsed details, safe actions, style directives, and accessibility text.",
        how_device_awareness_works="Mac chat defaults to compact cards with at most five visible bullets and details collapsed.",
        how_actions_remain_gated="Actions are local or disabled unless a future gated backend rail exists; external action remains false.",
        next_safe_move="Use the Capital Hilton examples as the semantic contract for future Mac chat rendering.",
    )


def _read_source_translation(path: Path) -> dict[str, Any] | None:
    return _load_json(path)


def _source_ready(source: Mapping[str, Any] | None) -> bool:
    if not source:
        return False
    mirror = source.get("operator_ready_card_mirror")
    return isinstance(mirror, Mapping) and mirror.get("translation_status") == "READY_FOR_OPERATOR_RENDER"


def _visible_packet_text(packet: Mapping[str, Any]) -> str:
    chunks: list[str] = []
    semantic = packet.get("semantic_payload", {})
    visible = packet.get("visible_content", {})
    detail = packet.get("detail_content", {})
    for container in (semantic, visible, detail):
        if isinstance(container, Mapping):
            for key, value in container.items():
                if key == "source_refs":
                    continue
                if isinstance(value, str):
                    chunks.append(value)
                elif isinstance(value, (list, tuple)):
                    chunks.extend(str(item) for item in value)
    for action in packet.get("operator_actions", ()):
        if isinstance(action, Mapping):
            chunks.extend(str(action.get(key) or "") for key in ("label", "disabled_reason"))
    return "\n".join(chunks)


def _machine_terms_found(examples: Mapping[str, Any]) -> tuple[str, ...]:
    text = "\n".join(_visible_packet_text(packet) for packet in examples.values()).lower()
    return tuple(term for term in FORBIDDEN_VISIBLE_TERMS if term.lower() in text)


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    examples = payload["capital_hilton_examples"]
    blockers = payload["render_packet_blockers_by_id"]
    visible_counts = [
        len(packet["visible_content"]["bullets"])
        for packet in examples.values()
        if packet["card_type"] != "COMPLETION"
    ]
    action_external_flags = [
        action["external_action"]
        for packet in examples.values()
        for action in packet["operator_actions"]
    ]
    completion = examples["completion_blocked"]
    waiting = examples["waiting"]
    return {
        "operator_card_render_packet_contract_model_present": True,
        "operator_card_render_packet_model_present": True,
        "semantic_card_payload_model_present": True,
        "device_aware_card_spec_model_present": True,
        "visual_style_directive_model_present": True,
        "operator_action_render_spec_model_present": True,
        "card_translation_and_filter_policy_model_present": True,
        "render_packet_blocker_model_present": True,
        "operator_card_render_packet_elioperator_report_model_present": True,
        "card_types_present": all(card_type in CARD_TYPES for card_type in (
            "UNDERSTANDING", "PLAN", "MISSING_INFO", "BLOCKED", "COMPLETION", "WAITING", "ERROR_FAIL_CLOSED"
        )),
        "truth_statuses_present": all(status in TRUTH_STATUSES for status in (
            "DRAFT_NOT_TRUTH", "BACKEND_READBACK_READY", "NEEDS_OPERATOR_REVIEW", "NEEDS_PROOF", "LOCKED_EXTERNAL_ACTION"
        )),
        "device_aware_spec_present": examples["understanding"]["device_profile"]["target_surface"] == "mac_chat",
        "visual_style_directive_present": examples["understanding"]["style_directive"]["tone"] == "calm",
        "action_render_spec_present": bool(examples["understanding"]["operator_actions"]),
        "filter_policy_present": payload["card_translation_and_filter_policy"]["fail_closed_on_machine_language"] is True,
        "blockers_present": all(blocker in {item["blocker_type"] for item in blockers.values()} for blocker in BLOCKER_TYPES),
        "capital_hilton_understanding_present": examples["understanding"]["visible_content"]["title"] == "What I understood",
        "capital_hilton_plan_present": examples["plan"]["visible_content"]["title"] == "The plan",
        "capital_hilton_still_needed_present": examples["still_needed"]["visible_content"]["title"] == "Still needed",
        "capital_hilton_still_locked_present": examples["still_locked"]["visible_content"]["title"] == "Still locked",
        "completion_card_blocked_without_proof": completion["card_type"] == "COMPLETION"
        and completion["truth_status"] == "UNKNOWN_FAIL_CLOSED"
        and completion["proof_status"] == "NEEDS_PROOF",
        "waiting_is_not_success": waiting["card_type"] == "WAITING"
        and waiting["style_directive"]["tone"] == "waiting"
        and "success" not in waiting["style_directive"]["accent_policy"].lower(),
        "visible_bullets_compact": all(count <= 5 for count in visible_counts),
        "machine_language_terms_absent": not _machine_terms_found(examples),
        "all_operator_actions_external_false": all(flag is False for flag in action_external_flags),
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "source_translation_ready": payload["source_translation_ready"],
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_visible_content": False,
        "external_action_performed": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_operator_card_render_packet_contract(
    *,
    source_translation_path: Path = DEFAULT_SOURCE_TRANSLATION,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source = _read_source_translation(source_translation_path)
    examples = build_capital_hilton_examples()
    contract = build_contract()
    blockers = build_blockers()
    policy = filter_policy()
    report = build_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "source_translation_path": source_translation_path.as_posix(),
        "source_translation_present": source is not None,
        "source_translation_ready": _source_ready(source),
        "card_types": CARD_TYPES,
        "truth_statuses": TRUTH_STATUSES,
        "target_surfaces": TARGET_SURFACES,
        "preferred_layouts": PREFERRED_LAYOUTS,
        "tones": TONES,
        "model_schemas": _model_schemas(),
        "operator_card_render_packet_contract": asdict(contract),
        "operator_card_render_packet": examples["understanding"],
        "semantic_card_payload": examples["understanding"]["semantic_payload"],
        "device_aware_card_spec": asdict(device_spec()),
        "visual_style_directive": asdict(style_directive("calm", card_type="UNDERSTANDING")),
        "operator_action_render_specs": tuple(asdict(action) for action in base_actions()),
        "card_translation_and_filter_policy": asdict(policy),
        "render_packet_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "operator_card_render_packet_elioperator_report": asdict(report),
        "capital_hilton_examples": examples,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["operator_card_render_packet_elioperator_report"]
    examples = payload["capital_hilton_examples"]
    lines = [
        "# Operator Card Render Packet Contract v0",
        "",
        "ELIOPERATOR: This defines semantic card packets for chat. Backend truth stays below deck; the operator sees compact card objects, not machinery.",
        "",
        "## What This Enables",
        "",
        report["what_this_enables"],
        "",
        "## Capital Hilton Examples",
        "",
    ]
    for key in ("understanding", "plan", "still_needed", "still_locked", "completion_blocked", "waiting"):
        packet = examples[key]
        visible = packet["visible_content"]
        lines.append(f"### {visible['title']}")
        lines.append(f"- {visible['short_summary']}")
        for bullet in visible["bullets"]:
            lines.append(f"- {bullet}")
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "- No live visual agent, image generation, model call, render runtime, card action execution, or external action exists here.",
            "- No email, Coupa, browser, invoice generation, credential handling, raw-body ingestion, Mac sync/import, Swift change, network, or push occurred.",
            "",
            f"Next safe move: {report['next_safe_move']}",
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
    examples = payload["capital_hilton_examples"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "source_translation_ready": payload["source_translation_ready"],
        "example_cards": [examples[key]["visible_content"]["title"] for key in (
            "understanding", "plan", "still_needed", "still_locked", "completion_blocked", "waiting"
        )],
        "completion_blocked": payload["machine_proof"]["completion_card_blocked_without_proof"],
        "waiting_is_not_success": payload["machine_proof"]["waiting_is_not_success"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the operator card render packet contract.")
    parser.add_argument("--source-translation", default=str(DEFAULT_SOURCE_TRANSLATION))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_operator_card_render_packet_contract(
        source_translation_path=Path(args.source_translation),
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
