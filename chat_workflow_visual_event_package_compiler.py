"""Chat Workflow Visual Event Package Compiler v0.

This deterministic read-model defines safe, truth-backed visual prompt/package
metadata for Mac chat status moments. It does not render, generate images or
video, call cloud/local models, play media, run workflows, dispatch agents,
handle credentials, ingest raw bodies, or perform external actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "chat_workflow_visual_event_package_compiler_v0"
READ_MODEL_ID = "chat_workflow_visual_event_package_compiler"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CHAT_WORKFLOW_VISUAL_EVENT_PACKAGE_COMPILER_NO_RENDER"

EVENT_TYPES = (
    "SUCCESS_CONFIRMED",
    "PARTIAL_READY",
    "BLOCKED_MISSING_INPUT",
    "BLOCKED_APPROVAL_REQUIRED",
    "BLOCKED_SECRET_REQUIRED",
    "BLOCKED_PROOF_MISSING",
    "FAILED_WITH_REASON",
    "FILE_REFERENCE_CAPTURED",
    "DRY_RUN_COMPLETE",
    "COMPLETION_CONFIRMED",
    "UNKNOWN_FAIL_CLOSED",
)

PROVIDER_FAMILIES = (
    "MAC_ANIMATION_NATIVE",
    "STATIC_VISUAL_CARD",
    "VIDEO_MODEL_CLOUD_GATED",
    "IMAGE_MODEL_CLOUD_GATED",
    "LOCAL_VIDEO_MODEL_FUTURE",
    "LOCAL_IMAGE_MODEL_FUTURE",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "VISUAL_PACKAGE_READY",
    "VISUAL_PACKAGE_STATIC_ONLY",
    "VISUAL_PACKAGE_LOCAL_ANIMATION_READY",
    "BLOCKED_PRIVACY_BOUNDARY",
    "BLOCKED_FALSE_VISUAL_CLAIM",
    "BLOCKED_PROVIDER_UNAVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "FALSE_SUCCESS_VISUAL_CLAIM",
    "CLOUD_PROVIDER_BLOCKED_SENSITIVE_CONTEXT",
    "RAW_CLIENT_DATA_IN_PROMPT",
    "RAW_PO_IN_PROMPT",
    "RAW_EMAIL_IN_PROMPT",
    "RAW_FILE_PATH_IN_PROMPT",
    "RAW_HASH_IN_PROMPT",
    "SECRET_OR_CREDENTIAL_IN_PROMPT",
    "VISUAL_IMPLIES_SENT_WITHOUT_RECEIPT",
    "VISUAL_IMPLIES_SUBMITTED_WITHOUT_RECEIPT",
    "PROVIDER_CALL_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

PRIVACY_CLASSES = (
    "PUBLIC_ABSTRACT",
    "OPERATOR_LOCAL",
    "CLIENT_PRIVATE",
    "PROTECTED_SECRET",
    "PROTECTED_EVIDENCE",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_video_generation_allowed": False,
    "live_image_generation_allowed": False,
    "live_cloud_model_call_allowed": False,
    "live_local_model_call_allowed": False,
    "live_visual_asset_generation_allowed": False,
    "live_visual_playback_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_provider_call_allowed": False,
    "live_browser_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_submit_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

SOURCE_REFS = {
    "capital_hilton_status": "generated/read_models/capital_hilton_invoice_operator_readback.json",
    "completion_proof": "generated/read_models/invoice_delivery_completion_proof_aggregator.json",
    "file_metadata": "generated/read_models/operator_file_metadata_readback.json",
    "agent_voice": "generated/read_models/agent_voice_response_layer.json",
}


@dataclass(frozen=True)
class ChatWorkflowVisualEventPackageCompiler:
    compiler_id: str
    doctrine: tuple[str, ...]
    source_truth_policy: tuple[str, ...]
    event_taxonomy_policy: tuple[str, ...]
    visual_metaphor_policy: tuple[str, ...]
    provider_policy: tuple[str, ...]
    privacy_policy: tuple[str, ...]
    forbidden_claim_policy: tuple[str, ...]
    mac_render_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class VisualEventType:
    event_type: str
    description: str
    allowed_truth_states: tuple[str, ...]
    default_metaphor: str
    default_tone: str
    provider_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class VisualPromptPackage:
    visual_package_id: str
    source_event_ref: str
    source_response_ref: str
    workflow_ref: str
    client_ref: str
    tenant_ref: str
    response_author: str
    agent_vibe: str
    truth_state: str
    visual_event_type: str
    allowed_visual_facts: tuple[str, ...]
    forbidden_visual_claims: tuple[str, ...]
    metaphor_style: str
    style_direction: str
    duration_seconds: int
    aspect_ratio: str
    target_surface: str
    privacy_class: str
    provider_policy: dict[str, Any]
    proof_refs: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class VisualProviderPolicy:
    provider_policy_id: str
    visual_package_ref: str
    allowed_provider_families: tuple[str, ...]
    blocked_provider_families: tuple[str, ...]
    preferred_provider_family: str
    cloud_generation_allowed: bool
    local_asset_preferred: bool
    async_generation_only: bool
    blocked_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class VisualMetaphorMapping:
    mapping_id: str
    event_type: str
    metaphor_style: str
    description: str
    agent_role: str
    tone: str
    allowed_contexts: tuple[str, ...]
    blocked_contexts: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class VisualPrivacyPolicy:
    policy_id: str
    privacy_class: str
    safe_to_send_to_cloud: bool
    safe_to_render_locally: bool
    blocked_from_prompt: tuple[str, ...]
    allowed_abstractions: tuple[str, ...]
    required_sanitization: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class VisualEventReadback:
    readback_id: str
    visual_package_ref: str
    status: str
    operator_headline: str
    operator_message: str
    package_summary: str
    provider_summary: str
    blocked_items: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class VisualEventBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _model_schemas() -> dict[str, tuple[str, ...]]:
    classes = (
        ChatWorkflowVisualEventPackageCompiler,
        VisualEventType,
        VisualPromptPackage,
        VisualProviderPolicy,
        VisualMetaphorMapping,
        VisualPrivacyPolicy,
        VisualEventReadback,
        VisualEventBlocker,
    )
    return {cls.__name__: tuple(field.name for field in fields(cls)) for cls in classes}


def build_compiler() -> ChatWorkflowVisualEventPackageCompiler:
    return ChatWorkflowVisualEventPackageCompiler(
        compiler_id="chat_workflow_visual_event_package_compiler_v0",
        doctrine=(
            "Truth first.",
            "Video second.",
            "Fun third.",
            "The visual artifact represents proof-backed state; it is not proof itself.",
        ),
        source_truth_policy=(
            "Visual event packages derive from response/readback/proof refs.",
            "Package readiness, dry-run status, and completion status remain separate truth states.",
            "No package may claim success without receipt-backed completion.",
        ),
        event_taxonomy_policy=(
            "Each visual event type maps to allowed truth states.",
            "Unknown or contradictory states fail closed.",
            "Blocked states keep blockers visible.",
        ),
        visual_metaphor_policy=(
            "Metaphors must not contradict the source truth state.",
            "Bowling-style feedback is allowed only as a status metaphor.",
            "A strike or perfect sweep requires completion receipts.",
        ),
        provider_policy=(
            "Interactive chat status defaults to native Mac animation or static visual cards.",
            "Cloud generation is blocked for client-private and protected contexts.",
            "Provider candidates are future gated capabilities, not execution authority.",
        ),
        privacy_policy=(
            "Raw client data, PO numbers, emails, file paths, hashes, credentials, legal/tax data, and database schemas are blocked.",
            "Sanitized abstract descriptors are allowed.",
            "Proof refs remain refs only.",
        ),
        forbidden_claim_policy=(
            "Never show sent, submitted, paid, complete, or approved unless proof allows it.",
            "Visual prompts must explicitly block false success claims.",
            "Video or animation output is never proof.",
        ),
        mac_render_policy=(
            "Mac may render the package later using local UI assets.",
            "This compiler does not play media or write Swift.",
            "Target surface is compact Mac chat by default.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use these packages as local visual render inputs only after Mac chooses a safe renderer.",
    )


def build_event_taxonomy() -> tuple[VisualEventType, ...]:
    rows = {
        "SUCCESS_CONFIRMED": ("A non-final success state backed by receipts or deterministic proof.", ("SUCCESS_CONFIRMED",), "bowling_strike_clean_sweep", "celebratory_safe"),
        "PARTIAL_READY": ("Most inputs are ready, but completion is not proven.", ("PARTIAL_READY", "READY_FOR_REVIEW"), "bowling_spare_target", "encouraging"),
        "BLOCKED_MISSING_INPUT": ("A specific required input is missing.", ("BLOCKED_MISSING_INPUT",), "bowling_single_pin_left", "clear_blocked"),
        "BLOCKED_APPROVAL_REQUIRED": ("Guardian or exact operator approval is missing.", ("BLOCKED_APPROVAL_REQUIRED",), "guardian_checkpoint_lock", "strict"),
        "BLOCKED_SECRET_REQUIRED": ("A protected secret ref is missing.", ("BLOCKED_SECRET_REQUIRED",), "protected_safe_box", "protective"),
        "BLOCKED_PROOF_MISSING": ("Receipts or proof refs are missing.", ("BLOCKED_PROOF_MISSING",), "bowling_single_pin_left", "proof_first"),
        "FAILED_WITH_REASON": ("A request failed with an explainable reason.", ("FAILED_WITH_REASON",), "gutter_ball_reset", "constructive"),
        "FILE_REFERENCE_CAPTURED": ("A source reference was captured without reading the body.", ("FILE_REFERENCE_CAPTURED",), "source_object_into_folder", "calm_ready"),
        "DRY_RUN_COMPLETE": ("A dry run completed without external action.", ("DRY_RUN_COMPLETE",), "holographic_practice_lane", "informative"),
        "COMPLETION_CONFIRMED": ("Final completion receipts exist.", ("COMPLETION_CONFIRMED",), "perfect_game_sweep", "celebratory_proof_backed"),
        "UNKNOWN_FAIL_CLOSED": ("Unknown or contradictory truth state.", ("UNKNOWN_FAIL_CLOSED",), "lane_under_maintenance", "neutral_blocked"),
    }
    return tuple(
        VisualEventType(
            event_type=event_type,
            description=description,
            allowed_truth_states=truth_states,
            default_metaphor=metaphor,
            default_tone=tone,
            provider_policy="Use MAC_ANIMATION_NATIVE or STATIC_VISUAL_CARD unless privacy and future gates permit otherwise.",
            next_safe_move="Build a visual prompt package from sanitized truth refs only.",
        )
        for event_type, (description, truth_states, metaphor, tone) in rows.items()
    )


def _metaphor(
    event_type: str,
    metaphor_style: str,
    description: str,
    *,
    agent_role: str = "OPENCLAW_SYSTEM",
    tone: str = "truthful_status",
    allowed_contexts: tuple[str, ...] = ("Mac chat status", "local visual feedback"),
    blocked_contexts: tuple[str, ...] = ("raw private data", "unproven completion", "external action claim"),
) -> VisualMetaphorMapping:
    return VisualMetaphorMapping(
        mapping_id=_stable_id("visual_metaphor_mapping", event_type, metaphor_style),
        event_type=event_type,
        metaphor_style=metaphor_style,
        description=description,
        agent_role=agent_role,
        tone=tone,
        allowed_contexts=allowed_contexts,
        blocked_contexts=blocked_contexts,
        next_safe_move="Use the metaphor only when the source truth state allows this event type.",
    )


def build_metaphor_mappings() -> tuple[VisualMetaphorMapping, ...]:
    return (
        _metaphor("SUCCESS_CONFIRMED", "bowling_strike_clean_sweep", "A clean sweep animation for proof-backed success."),
        _metaphor("PARTIAL_READY", "bowling_spare_target", "A spare setup showing the workflow is close but not complete."),
        _metaphor("BLOCKED_MISSING_INPUT", "bowling_single_pin_left", "One pin remains to represent one missing input.", agent_role="CHIEF", tone="clear_blocked"),
        _metaphor("BLOCKED_APPROVAL_REQUIRED", "guardian_checkpoint_lock", "A Guardian checkpoint or locked gate represents approval still required.", agent_role="GUARDIAN", tone="strict"),
        _metaphor("BLOCKED_SECRET_REQUIRED", "protected_safe_box", "A safe box represents missing protected secret refs.", agent_role="GUARDIAN", tone="protective"),
        _metaphor("BLOCKED_PROOF_MISSING", "bowling_single_pin_left", "One pin remains to represent missing proof or receipt refs.", agent_role="GUARDIAN", tone="proof_first"),
        _metaphor("FAILED_WITH_REASON", "gutter_ball_reset", "A constructive reset animation for a failed request with a reason."),
        _metaphor("FILE_REFERENCE_CAPTURED", "source_object_into_folder", "A source object slides into a folder without implying analysis.", tone="calm_ready"),
        _metaphor("DRY_RUN_COMPLETE", "holographic_practice_lane", "A practice lane animation for dry-run results."),
        _metaphor("COMPLETION_CONFIRMED", "perfect_game_sweep", "A perfect-game sweep only when completion receipts exist.", tone="celebratory_proof_backed"),
        _metaphor("UNKNOWN_FAIL_CLOSED", "lane_under_maintenance", "A maintenance state for unknown or contradictory truth."),
    )


def build_privacy_policies() -> tuple[VisualPrivacyPolicy, ...]:
    blocked = (
        "raw invoice values",
        "raw PO numbers",
        "raw email addresses",
        "file paths",
        "hashes",
        "credentials or secrets",
        "legal or tax ledger details",
        "database schemas",
        "raw private bodies",
    )
    return (
        VisualPrivacyPolicy(
            policy_id="visual_privacy_public_abstract",
            privacy_class="PUBLIC_ABSTRACT",
            safe_to_send_to_cloud=True,
            safe_to_render_locally=True,
            blocked_from_prompt=blocked,
            allowed_abstractions=("generic workflow status", "generic celebration", "non-client metaphor"),
            required_sanitization=("remove refs and paths", "remove raw values", "avoid completion claims without receipts"),
            next_safe_move="Cloud generation may be modeled only as future gated async generation.",
        ),
        VisualPrivacyPolicy(
            policy_id="visual_privacy_operator_local",
            privacy_class="OPERATOR_LOCAL",
            safe_to_send_to_cloud=False,
            safe_to_render_locally=True,
            blocked_from_prompt=blocked,
            allowed_abstractions=("local source captured", "blocked input", "approval needed", "dry-run complete"),
            required_sanitization=("remove local paths", "remove hashes", "use abstract source labels"),
            next_safe_move="Prefer native Mac animation or static visual card.",
        ),
        VisualPrivacyPolicy(
            policy_id="visual_privacy_client_private",
            privacy_class="CLIENT_PRIVATE",
            safe_to_send_to_cloud=False,
            safe_to_render_locally=True,
            blocked_from_prompt=blocked,
            allowed_abstractions=("client workflow blocked", "missing source reference", "approval gate", "proof missing"),
            required_sanitization=("remove client private values", "remove PO values", "remove contact data", "keep proof refs as refs only"),
            next_safe_move="Block cloud providers and render locally from sanitized event type.",
        ),
        VisualPrivacyPolicy(
            policy_id="visual_privacy_protected_secret",
            privacy_class="PROTECTED_SECRET",
            safe_to_send_to_cloud=False,
            safe_to_render_locally=True,
            blocked_from_prompt=blocked,
            allowed_abstractions=("protected safe box", "secret ref required", "credential gate locked"),
            required_sanitization=("never include secret material", "use protected ref status only"),
            next_safe_move="Render only a protected-boundary metaphor locally.",
        ),
        VisualPrivacyPolicy(
            policy_id="visual_privacy_protected_evidence",
            privacy_class="PROTECTED_EVIDENCE",
            safe_to_send_to_cloud=False,
            safe_to_render_locally=True,
            blocked_from_prompt=blocked,
            allowed_abstractions=("proof required", "receipt missing", "evidence locked"),
            required_sanitization=("show proof status only", "never include evidence body"),
            next_safe_move="Render proof status locally and keep evidence body out of prompts.",
        ),
    )


def _provider_policy_for(
    visual_package_ref: str,
    *,
    privacy_class: str,
    preferred: str = "MAC_ANIMATION_NATIVE",
    async_generation_only: bool = False,
) -> VisualProviderPolicy:
    sensitive = privacy_class in {"CLIENT_PRIVATE", "PROTECTED_SECRET", "PROTECTED_EVIDENCE", "OPERATOR_LOCAL"}
    allowed = ("MAC_ANIMATION_NATIVE", "STATIC_VISUAL_CARD")
    blocked = ("VIDEO_MODEL_CLOUD_GATED", "IMAGE_MODEL_CLOUD_GATED", "UNKNOWN_FAIL_CLOSED")
    if privacy_class == "PUBLIC_ABSTRACT":
        allowed = ("MAC_ANIMATION_NATIVE", "STATIC_VISUAL_CARD", "VIDEO_MODEL_CLOUD_GATED", "IMAGE_MODEL_CLOUD_GATED")
        blocked = ("UNKNOWN_FAIL_CLOSED",)
    return VisualProviderPolicy(
        provider_policy_id=_stable_id("visual_provider_policy", visual_package_ref),
        visual_package_ref=visual_package_ref,
        allowed_provider_families=allowed,
        blocked_provider_families=blocked,
        preferred_provider_family=preferred,
        cloud_generation_allowed=not sensitive and privacy_class == "PUBLIC_ABSTRACT",
        local_asset_preferred=True,
        async_generation_only=async_generation_only,
        blocked_reason=(
            "Sensitive context blocks cloud visual generation."
            if sensitive
            else "Cloud generation is future gated and async only; no provider call occurs here."
        ),
        next_safe_move="Render locally now or hand off to a future gated visual provider only when privacy allows.",
    )


def _package(
    *,
    visual_package_id: str,
    source_event_ref: str,
    source_response_ref: str,
    workflow_ref: str,
    client_ref: str,
    tenant_ref: str,
    response_author: str,
    agent_vibe: str,
    truth_state: str,
    visual_event_type: str,
    allowed_visual_facts: tuple[str, ...],
    forbidden_visual_claims: tuple[str, ...],
    metaphor_style: str,
    style_direction: str,
    privacy_class: str,
    proof_refs: tuple[str, ...],
    duration_seconds: int = 3,
    aspect_ratio: str = "16:9",
    target_surface: str = "MAC_CHAT_COMPACT",
    preferred_provider: str = "MAC_ANIMATION_NATIVE",
    async_generation_only: bool = False,
) -> VisualPromptPackage:
    policy = _provider_policy_for(
        visual_package_id,
        privacy_class=privacy_class,
        preferred=preferred_provider,
        async_generation_only=async_generation_only,
    )
    return VisualPromptPackage(
        visual_package_id=visual_package_id,
        source_event_ref=source_event_ref,
        source_response_ref=source_response_ref,
        workflow_ref=workflow_ref,
        client_ref=client_ref,
        tenant_ref=tenant_ref,
        response_author=response_author,
        agent_vibe=agent_vibe,
        truth_state=truth_state,
        visual_event_type=visual_event_type,
        allowed_visual_facts=allowed_visual_facts,
        forbidden_visual_claims=forbidden_visual_claims,
        metaphor_style=metaphor_style,
        style_direction=style_direction,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        target_surface=target_surface,
        privacy_class=privacy_class,
        provider_policy=asdict(policy),
        proof_refs=proof_refs,
        next_safe_move="Render a local truth-backed visual status only; do not call providers from this compiler.",
    )


def _readback_for(package: VisualPromptPackage, status: str, *, blocked_items: tuple[str, ...] = ()) -> VisualEventReadback:
    provider = package.provider_policy
    provider_summary = (
        f"Preferred provider family is {provider['preferred_provider_family']}; "
        f"cloud generation allowed: {provider['cloud_generation_allowed']}."
    )
    return VisualEventReadback(
        readback_id=_stable_id("visual_event_readback", package.visual_package_id, status),
        visual_package_ref=package.visual_package_id,
        status=status,
        operator_headline=(
            "Visual package ready"
            if status in {"VISUAL_PACKAGE_READY", "VISUAL_PACKAGE_LOCAL_ANIMATION_READY", "VISUAL_PACKAGE_STATIC_ONLY"}
            else "Visual package blocked"
        ),
        operator_message=(
            f"OpenClaw compiled a truth-backed visual package for {package.visual_event_type}. "
            "No image, video, model call, playback, workflow, or external action occurred."
        ),
        package_summary=f"{package.metaphor_style} represents {package.truth_state}.",
        provider_summary=provider_summary,
        blocked_items=blocked_items,
        next_safe_move=package.next_safe_move if not blocked_items else "Fix the blocked visual claim or privacy issue before rendering.",
    )


def build_examples() -> dict[str, Any]:
    forbidden_delivery_claims = (
        "invoice sent",
        "Coupa invoice submitted",
        "payment updated",
        "approval complete",
        "workflow complete",
    )
    missing_po = _package(
        visual_package_id="visual_package_capital_hilton_missing_po_v0",
        source_event_ref="capital_hilton_invoice_status_missing_po",
        source_response_ref=SOURCE_REFS["capital_hilton_status"],
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        response_author="CHIEF",
        agent_vibe="vibe:chief:command_center",
        truth_state="BLOCKED_MISSING_INPUT",
        visual_event_type="BLOCKED_MISSING_INPUT",
        allowed_visual_facts=("invoice basis exists", "missing Coupa PO/reference"),
        forbidden_visual_claims=forbidden_delivery_claims,
        metaphor_style="bowling_single_pin_left",
        style_direction="one bright pin remains standing; keep it operational, not celebratory",
        privacy_class="CLIENT_PRIVATE",
        proof_refs=(SOURCE_REFS["capital_hilton_status"],),
    )
    file_captured = _package(
        visual_package_id="visual_package_file_reference_captured_v0",
        source_event_ref="file_reference_captured_metadata_only",
        source_response_ref=SOURCE_REFS["file_metadata"],
        workflow_ref="source_reference_capture",
        client_ref="client_ref:unknown_or_local",
        tenant_ref="tenant_ref:winship",
        response_author="OPENCLAW_SYSTEM",
        agent_vibe="vibe:system:neutral",
        truth_state="FILE_REFERENCE_CAPTURED",
        visual_event_type="FILE_REFERENCE_CAPTURED",
        allowed_visual_facts=("file reference captured", "file body not read"),
        forbidden_visual_claims=("file analyzed", "file parsed", "OCR complete", "contents extracted"),
        metaphor_style="source_object_into_folder",
        style_direction="a generic source tile slides into a local folder; no document contents visible",
        privacy_class="OPERATOR_LOCAL",
        proof_refs=(SOURCE_REFS["file_metadata"],),
        preferred_provider="STATIC_VISUAL_CARD",
    )
    complete = _package(
        visual_package_id="visual_package_completion_confirmed_fixture_v0",
        source_event_ref="completion_confirmed_fixture_all_receipts_present",
        source_response_ref=SOURCE_REFS["completion_proof"],
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        response_author="CHIEF",
        agent_vibe="vibe:chief:command_center",
        truth_state="COMPLETION_CONFIRMED",
        visual_event_type="COMPLETION_CONFIRMED",
        allowed_visual_facts=("completion receipts present", "email and Coupa proof refs present", "local record proof present"),
        forbidden_visual_claims=("show raw receipt body", "show provider ids", "show raw client values"),
        metaphor_style="perfect_game_sweep",
        style_direction="proof-backed perfect sweep; celebratory but still receipt-bound",
        privacy_class="CLIENT_PRIVATE",
        proof_refs=(SOURCE_REFS["completion_proof"],),
        duration_seconds=4,
        async_generation_only=True,
    )
    false_strike_attempt = _package(
        visual_package_id="visual_package_false_strike_attempt_blocked_v0",
        source_event_ref="blocked_workflow_attempted_success_visual",
        source_response_ref=SOURCE_REFS["capital_hilton_status"],
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        response_author="CHIEF",
        agent_vibe="vibe:chief:command_center",
        truth_state="BLOCKED_MISSING_INPUT",
        visual_event_type="SUCCESS_CONFIRMED",
        allowed_visual_facts=("workflow remains blocked",),
        forbidden_visual_claims=forbidden_delivery_claims,
        metaphor_style="bowling_strike_clean_sweep",
        style_direction="blocked attempt; do not render this success metaphor",
        privacy_class="CLIENT_PRIVATE",
        proof_refs=(SOURCE_REFS["capital_hilton_status"],),
    )
    guardian_approval = _package(
        visual_package_id="visual_package_guardian_approval_required_v0",
        source_event_ref="guardian_approval_required_missing_receipt",
        source_response_ref=SOURCE_REFS["capital_hilton_status"],
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        response_author="GUARDIAN",
        agent_vibe="vibe:guardian:strict_proof",
        truth_state="BLOCKED_APPROVAL_REQUIRED",
        visual_event_type="BLOCKED_APPROVAL_REQUIRED",
        allowed_visual_facts=("approval/proof gate missing", "external action locked"),
        forbidden_visual_claims=("approval complete", "send allowed", "submit allowed"),
        metaphor_style="guardian_checkpoint_lock",
        style_direction="strict locked checkpoint; no playful celebration",
        privacy_class="PROTECTED_EVIDENCE",
        proof_refs=(SOURCE_REFS["capital_hilton_status"], SOURCE_REFS["agent_voice"]),
    )

    return {
        "capital_hilton_missing_po": {
            "visual_package": asdict(missing_po),
            "provider_policy": missing_po.provider_policy,
            "readback": asdict(_readback_for(missing_po, "VISUAL_PACKAGE_LOCAL_ANIMATION_READY")),
        },
        "file_reference_captured": {
            "visual_package": asdict(file_captured),
            "provider_policy": file_captured.provider_policy,
            "readback": asdict(_readback_for(file_captured, "VISUAL_PACKAGE_STATIC_ONLY")),
        },
        "completion_confirmed_fixture": {
            "visual_package": asdict(complete),
            "provider_policy": complete.provider_policy,
            "readback": asdict(_readback_for(complete, "VISUAL_PACKAGE_LOCAL_ANIMATION_READY")),
            "completion_receipts_modeled_present": True,
        },
        "false_strike_blocked": {
            "attempted_visual_package": asdict(false_strike_attempt),
            "provider_policy": false_strike_attempt.provider_policy,
            "readback": asdict(_readback_for(false_strike_attempt, "BLOCKED_FALSE_VISUAL_CLAIM", blocked_items=("FALSE_SUCCESS_VISUAL_CLAIM",))),
            "blocker_type": "FALSE_SUCCESS_VISUAL_CLAIM",
            "fail_closed": True,
        },
        "guardian_approval_required": {
            "visual_package": asdict(guardian_approval),
            "provider_policy": guardian_approval.provider_policy,
            "readback": asdict(_readback_for(guardian_approval, "VISUAL_PACKAGE_LOCAL_ANIMATION_READY")),
        },
    }


def build_blockers() -> tuple[VisualEventBlocker, ...]:
    conditions = {
        "FALSE_SUCCESS_VISUAL_CLAIM": ("critical", "Visual package requests success metaphor while source truth is blocked or missing proof.", "Use a blocked or partial-ready metaphor."),
        "CLOUD_PROVIDER_BLOCKED_SENSITIVE_CONTEXT": ("critical", "Cloud visual generation is requested for client-private or protected context.", "Use native Mac animation or static card."),
        "RAW_CLIENT_DATA_IN_PROMPT": ("critical", "Prompt contains raw client/private data.", "Replace with sanitized abstract descriptors."),
        "RAW_PO_IN_PROMPT": ("critical", "Prompt contains raw PO/reference values.", "Use missing/confirmed PO status only."),
        "RAW_EMAIL_IN_PROMPT": ("critical", "Prompt contains raw email address or contact private data.", "Use safe contact labels only."),
        "RAW_FILE_PATH_IN_PROMPT": ("high", "Prompt contains raw local file path.", "Use source object abstraction only."),
        "RAW_HASH_IN_PROMPT": ("medium", "Prompt contains raw hash/fingerprint.", "Use proof ref status only."),
        "SECRET_OR_CREDENTIAL_IN_PROMPT": ("critical", "Prompt contains secret or credential material.", "Use protected safe-box metaphor only."),
        "VISUAL_IMPLIES_SENT_WITHOUT_RECEIPT": ("critical", "Visual implies email sent without send receipt.", "Use blocked proof-missing visual."),
        "VISUAL_IMPLIES_SUBMITTED_WITHOUT_RECEIPT": ("critical", "Visual implies Coupa submitted without submit receipt.", "Use blocked proof-missing visual."),
        "PROVIDER_CALL_ATTEMPTED": ("critical", "Compiler attempts provider/model/render call.", "Return package metadata only."),
        "UNKNOWN_FAIL_CLOSED": ("high", "Unknown visual truth state.", "Use lane-under-maintenance fail-closed visual."),
    }
    return tuple(
        VisualEventBlocker(
            blocker_id=_stable_id("visual_event_blocker", blocker_type),
            blocker_type=blocker_type,
            condition=condition,
            severity=severity,
            elioperator_warning=f"ELIOPERATOR: {condition}",
            fail_closed=True,
            next_safe_move=next_move,
        )
        for blocker_type, (severity, condition, next_move) in conditions.items()
    )


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    examples = payload["examples"]
    missing_po = examples["capital_hilton_missing_po"]["visual_package"]
    file_capture = examples["file_reference_captured"]["visual_package"]
    complete = examples["completion_confirmed_fixture"]["visual_package"]
    false_strike = examples["false_strike_blocked"]
    guardian = examples["guardian_approval_required"]["visual_package"]
    provider_policies = [example.get("provider_policy") for example in examples.values() if isinstance(example, dict)]
    visible_text = stable_json(
        {
            "examples": examples,
            "metaphor_mappings": payload["visual_metaphor_mappings"],
            "privacy_policies": payload["visual_privacy_policies"],
        }
    ).lower()
    blocked_terms = (
        "actual secret",
        "raw private body",
        "raw email address value",
        "database schema value",
        "file body content",
    )
    return {
        "compiler_model_present": True,
        "visual_event_type_model_present": True,
        "visual_prompt_package_model_present": True,
        "visual_provider_policy_model_present": True,
        "visual_metaphor_mapping_model_present": True,
        "visual_privacy_policy_model_present": True,
        "visual_event_readback_model_present": True,
        "visual_event_blocker_model_present": True,
        "event_taxonomy_complete": all(event_type in {row["event_type"] for row in payload["visual_event_types"]} for event_type in EVENT_TYPES),
        "provider_policy_present": all(policy for policy in provider_policies),
        "metaphor_mappings_present": all(event_type in {row["event_type"] for row in payload["visual_metaphor_mappings"]} for event_type in EVENT_TYPES),
        "privacy_policy_present": {row["privacy_class"] for row in payload["visual_privacy_policies"]}.issuperset({"CLIENT_PRIVATE", "PROTECTED_SECRET", "PROTECTED_EVIDENCE"}),
        "capital_hilton_missing_po_example_present": missing_po["visual_event_type"] == "BLOCKED_MISSING_INPUT",
        "file_reference_captured_example_present": file_capture["visual_event_type"] == "FILE_REFERENCE_CAPTURED",
        "completion_confirmed_fixture_present": complete["visual_event_type"] == "COMPLETION_CONFIRMED",
        "false_strike_blocked": false_strike["blocker_type"] == "FALSE_SUCCESS_VISUAL_CLAIM" and false_strike["fail_closed"] is True,
        "guardian_approval_example_present": guardian["visual_event_type"] == "BLOCKED_APPROVAL_REQUIRED",
        "cloud_blocked_for_sensitive_contexts": all(
            policy["cloud_generation_allowed"] is False
            for policy in provider_policies
            if policy and policy["visual_package_ref"] != "visual_package_public_abstract_fixture"
        ),
        "provider_calls_made": False,
        "video_generation_performed": False,
        "image_generation_performed": False,
        "cloud_model_call_performed": False,
        "local_model_call_performed": False,
        "visual_asset_generation_performed": False,
        "visual_playback_performed": False,
        "external_action_performed": False,
        "workflow_run_performed": False,
        "agent_dispatch_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "mac_sync_import_performed": False,
        "swift_change_performed": False,
        "git_push_performed": False,
        "network_used": False,
        "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "no_credentials_secrets_private_bodies": not any(term in visible_text for term in blocked_terms),
        "content_hash": None,
    }


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def build_payload(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    compiler = build_compiler()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "event_types": EVENT_TYPES,
        "provider_families": PROVIDER_FAMILIES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "privacy_classes": PRIVACY_CLASSES,
        "model_schemas": _model_schemas(),
        "compiler": asdict(compiler),
        "visual_event_types": tuple(asdict(row) for row in build_event_taxonomy()),
        "visual_metaphor_mappings": tuple(asdict(row) for row in build_metaphor_mappings()),
        "visual_privacy_policies": tuple(asdict(row) for row in build_privacy_policies()),
        "visual_event_blockers": tuple(asdict(row) for row in build_blockers()),
        "examples": build_examples(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    examples = payload["examples"]
    capital = examples["capital_hilton_missing_po"]["visual_package"]
    file_capture = examples["file_reference_captured"]["visual_package"]
    false_strike = examples["false_strike_blocked"]
    return "\n".join(
        [
            "# Chat Workflow Visual Event Package Compiler",
            "",
            "Deterministic visual prompt/package metadata only. No video generation, image generation, model call, provider call, playback, workflow run, or external action occurs.",
            "",
            "## Doctrine",
            "- Truth first.",
            "- Video second.",
            "- Fun third.",
            "- A visual artifact is not proof.",
            "",
            "## Capital Hilton Missing PO",
            f"- Event: {capital['visual_event_type']}",
            f"- Metaphor: {capital['metaphor_style']}",
            f"- Provider: {capital['provider_policy']['preferred_provider_family']}",
            f"- Cloud generation allowed: {capital['provider_policy']['cloud_generation_allowed']}",
            "",
            "## File Captured",
            f"- Event: {file_capture['visual_event_type']}",
            f"- Metaphor: {file_capture['metaphor_style']}",
            "- Claim blocked: file analyzed.",
            "",
            "## False Strike",
            f"- Blocker: {false_strike['blocker_type']}",
            f"- Fail closed: {false_strike['fail_closed']}",
            "",
            "## Authority",
            "- No video generation.",
            "- No image generation.",
            "- No cloud model call.",
            "- No local model call.",
            "- No visual playback.",
            "- No external action.",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path, operator_path: Path) -> dict[str, Any]:
    examples = payload["examples"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "capital_hilton_event": examples["capital_hilton_missing_po"]["visual_package"]["visual_event_type"],
        "file_capture_event": examples["file_reference_captured"]["visual_package"]["visual_event_type"],
        "completion_fixture_event": examples["completion_confirmed_fixture"]["visual_package"]["visual_event_type"],
        "false_strike_blocker": examples["false_strike_blocked"]["blocker_type"],
        "guardian_event": examples["guardian_approval_required"]["visual_package"]["visual_event_type"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "provider_calls_made": payload["machine_proof"]["provider_calls_made"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the Chat Workflow Visual Event Package Compiler read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(stable_json(build_summary(payload, json_path, operator_path)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
