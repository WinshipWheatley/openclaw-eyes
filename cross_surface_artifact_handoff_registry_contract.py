"""Cross-Surface Artifact Handoff Registry / OpenClaw Post Office Contract v0.

This deterministic read-model defines how typed artifacts can move between
Mission Control, Repo A, Telegram/fronting agents, and future surfaces without
creating a live bus, watcher, queue, auto-import path, or external authority.
It is metadata and contract only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "cross_surface_artifact_handoff_registry_contract_v0"
READ_MODEL_ID = "cross_surface_artifact_handoff_registry_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_HANDOFF_REGISTRY_CONTRACT"

ARTIFACT_TYPES = (
    "CAPTURE_REQUEST",
    "CAPTURE_READBACK",
    "DELIVERY_FACT_UPDATE",
    "INVOICE_ARTIFACT_PREVIEW",
    "APPROVAL_PACKET",
    "AGENT_HANDOFF",
    "OPERATOR_CLOSEOUT",
    "REUSABLE_FACT",
    "PROTECTED_EVIDENCE_REFERENCE",
    "UNKNOWN_FAIL_CLOSED",
)

LIFECYCLE_STATES = (
    "CREATED",
    "EMITTED",
    "RECEIVED",
    "VALIDATED",
    "CONSUMED",
    "WRITTEN",
    "READBACK_READY",
    "RENDERED",
    "BLOCKED",
    "REJECTED",
    "DUPLICATE_NOOP",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_TYPES = (
    "CAPTURE_VALIDATED",
    "LOCAL_STATE_WRITTEN",
    "DUPLICATE_NOOP",
    "READBACK_READY_FOR_SURFACE",
    "RENDERED_BY_SURFACE",
    "BLOCKED_FAIL_CLOSED",
    "REJECTED_UNSUPPORTED_SHAPE",
)

BUILDER_BLOCKER_TYPES = (
    "MISSING_WORKFLOW_SESSION_REF",
    "MISSING_ARTIFACT_TYPE",
    "MISSING_SCHEMA_REF",
    "MISSING_IDEMPOTENCY_KEY",
    "MISSING_AUTHORITY_BOUNDARY",
    "UI_COUPLED_PAYLOAD",
    "RAW_PROTECTED_VALUE_IN_PAYLOAD",
    "UNSUPPORTED_TARGET_HANDLER",
    "GENERATED_ARTIFACT_WITHOUT_FILE_HASH",
    "SEND_READY_WITHOUT_APPROVAL_GATE",
    "CALCULATED_STATE_COPIED_AS_TRUTH",
    "CROSS_TENANT_PAYLOAD_LEAK",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_HANDOFF_FIELDS = (
    "handoff_id",
    "artifact_id",
    "artifact_type",
    "schema_ref",
    "schema_version",
    "world_ref",
    "lane_ref",
    "block_id",
    "workflow_session_ref",
    "operation",
    "origin_surface",
    "origin_actor",
    "source_channel",
    "addressed_actor",
    "fronting_agent",
    "assigned_role",
    "target_surface",
    "target_handler",
    "reply_to_surface",
    "reply_to_channel",
    "lifecycle_state",
    "authority_boundary",
    "privacy_class",
    "sensitivity_class",
    "tokenized_value_refs",
    "protected_store_refs",
    "payload_hash",
    "idempotency_key",
    "created_at",
    "safe_display_summary",
    "elioperator_message",
    "next_safe_move",
)

REQUIRED_LIFECYCLE_POLICY_FIELDS = (
    "policy_id",
    "allowed_lifecycle_states",
    "operator_visible_states",
    "below_deck_states",
    "terminal_states",
    "duplicate_policy",
    "blocked_policy",
    "rejection_policy",
    "retry_policy",
    "stale_policy",
    "next_safe_move",
)

REQUIRED_SCHEMA_RULE_FIELDS = (
    "rule_id",
    "artifact_type",
    "required_fields",
    "forbidden_fields",
    "required_namespace_fields",
    "required_authority_fields",
    "required_privacy_fields",
    "required_idempotency_fields",
    "visual_agnostic_requirements",
    "raw_value_forbidden",
    "validation_failure_state",
    "elioperator_failure_message",
    "next_safe_move",
)

REQUIRED_ROUTING_RULE_FIELDS = (
    "routing_rule_id",
    "artifact_type",
    "world_ref",
    "lane_ref",
    "block_id",
    "target_surface",
    "target_handler",
    "reply_to_surface",
    "reply_to_channel",
    "handler_authority_scope",
    "supported_operations",
    "unsupported_operations",
    "routing_status",
    "fallback_behavior",
    "next_safe_move",
)

REQUIRED_AUTHORITY_BOUNDARY_FIELDS = (
    "boundary_id",
    "handoff_ref",
    "external_action_allowed",
    "local_receipt_write_allowed",
    "local_state_write_allowed",
    "readback_write_allowed",
    "render_allowed",
    "approval_required",
    "guardian_review_required",
    "protected_evidence_required",
    "email_send_allowed",
    "email_draft_allowed",
    "coupa_submit_allowed",
    "coupa_access_allowed",
    "browser_automation_allowed",
    "gmail_access_allowed",
    "telegram_send_allowed",
    "credential_handling_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "queue_execution_allowed",
    "runtime_dispatch_allowed",
    "raw_body_ingestion_allowed",
    "next_safe_move",
)

REQUIRED_PRIVACY_BOUNDARY_FIELDS = (
    "privacy_boundary_id",
    "handoff_ref",
    "privacy_class",
    "sensitivity_class",
    "raw_value_allowed",
    "tokenized_value_ref_allowed",
    "protected_store_ref_allowed",
    "central_sync_allowed",
    "allowed_surfaces",
    "forbidden_surfaces",
    "redaction_required",
    "de_tokenization_allowed",
    "de_tokenization_authority",
    "safe_display_label",
    "elioperator_privacy_summary",
    "next_safe_move",
)

REQUIRED_READBACK_FIELDS = (
    "readback_id",
    "source_handoff_ref",
    "readback_type",
    "readback_status",
    "written_receipt_refs",
    "written_state_refs",
    "duplicate_retry_result",
    "rendered_surface_refs",
    "safe_display_summary",
    "blockers",
    "next_operator_question",
    "elioperator_message",
    "proof_refs",
    "protected_refs",
    "lifecycle_transition",
    "next_safe_move",
)

REQUIRED_COMPATIBILITY_FIELDS = (
    "compatibility_id",
    "surfaces",
    "artifact_types",
    "compatible_origins",
    "compatible_targets",
    "compatible_agents",
    "role_based_actor_refs",
    "channel_neutrality",
    "workflow_owner",
    "state_owner",
    "blocked_split_brain_patterns",
    "next_safe_move",
)

REQUIRED_BUILDER_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "builder_action_required",
    "fail_closed",
    "next_safe_move",
)

REQUIRED_POST_OFFICE_FIELDS = (
    "concept_id",
    "description",
    "what_it_solves",
    "what_it_does_not_do_yet",
    "future_runtime_path",
    "migration_strategy",
    "no_big_bang_rewrite_policy",
    "capital_hilton_adapter_path",
    "next_safe_move",
)

FORBIDDEN_PAYLOAD_FIELDS = (
    "screen_x",
    "screen_y",
    "button_frame",
    "font_size",
    "view_id",
    "swift_view_path",
    "raw_email",
    "raw_phone",
    "raw_po_reference",
    "raw_credentials",
    "raw_cookie",
    "raw_token",
    "raw_email_body",
    "raw_screenshot_body",
    "raw_pdf_body",
    "raw_private_document_body",
)

VISUAL_AGNOSTIC_REQUIREMENTS = (
    "No UI coordinates",
    "No button layout",
    "No font or screen geometry",
    "No Mac-only rendering paths",
    "Workflow/session/block/value metadata only",
)

AUTHORITY_BOUNDARY = {
    "live_handoff_bus_allowed": False,
    "live_file_watcher_allowed": False,
    "live_runtime_queue_allowed": False,
    "live_auto_consume_allowed": False,
    "live_auto_import_allowed": False,
    "live_telegram_integration_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_external_action_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "email_send_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "file_cleanup_archive_promotion_allowed": False,
}

EXTERNAL_AUTHORITY_FIELDS = (
    "external_action_allowed",
    "email_send_allowed",
    "email_draft_allowed",
    "coupa_submit_allowed",
    "coupa_access_allowed",
    "browser_automation_allowed",
    "gmail_access_allowed",
    "telegram_send_allowed",
    "credential_handling_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "queue_execution_allowed",
    "runtime_dispatch_allowed",
    "raw_body_ingestion_allowed",
)

RELATIONSHIP_REF_PATHS = {
    "mission_control_capture_request_intake": "generated/read_models/mission_control_capture_request_intake.json",
    "capital_hilton_delivery_facts_capture_writer": (
        "generated/read_models/capital_hilton_delivery_facts_capture_writer.json"
    ),
    "cross_lane_reusable_block_registry_contract": (
        "generated/read_models/cross_lane_reusable_block_registry_contract.json"
    ),
    "workflow_block_intent_live_draft_contract": (
        "generated/read_models/workflow_block_intent_live_draft_contract.json"
    ),
    "entry_agnostic_workflow_block_chain_routing_contract": (
        "generated/read_models/entry_agnostic_workflow_block_chain_routing_contract.json"
    ),
    "agent_conversation_handoff_step_packet_contract": (
        "generated/read_models/agent_conversation_handoff_step_packet_contract.json"
    ),
    "agent_execution_packet_compiler_contract": "generated/read_models/agent_execution_packet_compiler_contract.json",
    "bridge_routing_operator_attention_contract": (
        "generated/read_models/bridge_routing_operator_attention_contract.json"
    ),
    "openclaw_sensitive_policy": "openclaw_sensitive_policy.py",
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "guardian_protected_access_gate_spec": "generated/read_models/guardian_protected_access_gate_spec.json",
    "read_model_shuttle": "read_model_shuttle.py",
    "generated_read_model_files": "generated_read_model_files.py",
    "operator_map_bundle_contract": "generated/read_models/operator_map_bundle_contract.json",
}


@dataclass(frozen=True)
class CrossSurfaceArtifactHandoff:
    handoff_id: str
    artifact_id: str
    artifact_type: str
    schema_ref: str
    schema_version: str
    world_ref: str
    lane_ref: str
    block_id: str
    workflow_session_ref: str
    operation: str
    origin_surface: str
    origin_actor: str
    source_channel: str
    addressed_actor: str | None
    fronting_agent: str | None
    assigned_role: str
    target_surface: str
    target_handler: str
    reply_to_surface: str
    reply_to_channel: str
    lifecycle_state: str
    authority_boundary: str
    privacy_class: str
    sensitivity_class: str
    tokenized_value_refs: tuple[str, ...]
    protected_store_refs: tuple[str, ...]
    payload_hash: str
    idempotency_key: str
    created_at: str
    safe_display_summary: str
    elioperator_message: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffLifecyclePolicy:
    policy_id: str
    allowed_lifecycle_states: tuple[str, ...]
    operator_visible_states: tuple[str, ...]
    below_deck_states: tuple[str, ...]
    terminal_states: tuple[str, ...]
    duplicate_policy: str
    blocked_policy: str
    rejection_policy: str
    retry_policy: str
    stale_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffSchemaValidationRule:
    rule_id: str
    artifact_type: str
    required_fields: tuple[str, ...]
    forbidden_fields: tuple[str, ...]
    required_namespace_fields: tuple[str, ...]
    required_authority_fields: tuple[str, ...]
    required_privacy_fields: tuple[str, ...]
    required_idempotency_fields: tuple[str, ...]
    visual_agnostic_requirements: tuple[str, ...]
    raw_value_forbidden: bool
    validation_failure_state: str
    elioperator_failure_message: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffRoutingRule:
    routing_rule_id: str
    artifact_type: str
    world_ref: str
    lane_ref: str
    block_id: str
    target_surface: str
    target_handler: str
    reply_to_surface: str
    reply_to_channel: str
    handler_authority_scope: str
    supported_operations: tuple[str, ...]
    unsupported_operations: tuple[str, ...]
    routing_status: str
    fallback_behavior: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffAuthorityBoundary:
    boundary_id: str
    handoff_ref: str
    external_action_allowed: bool
    local_receipt_write_allowed: bool
    local_state_write_allowed: bool
    readback_write_allowed: bool
    render_allowed: bool
    approval_required: bool
    guardian_review_required: bool
    protected_evidence_required: bool
    email_send_allowed: bool
    email_draft_allowed: bool
    coupa_submit_allowed: bool
    coupa_access_allowed: bool
    browser_automation_allowed: bool
    gmail_access_allowed: bool
    telegram_send_allowed: bool
    credential_handling_allowed: bool
    model_call_allowed: bool
    agent_activation_allowed: bool
    tool_execution_allowed: bool
    queue_execution_allowed: bool
    runtime_dispatch_allowed: bool
    raw_body_ingestion_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class HandoffPrivacyBoundary:
    privacy_boundary_id: str
    handoff_ref: str
    privacy_class: str
    sensitivity_class: str
    raw_value_allowed: bool
    tokenized_value_ref_allowed: bool
    protected_store_ref_allowed: bool
    central_sync_allowed: bool
    allowed_surfaces: tuple[str, ...]
    forbidden_surfaces: tuple[str, ...]
    redaction_required: bool
    de_tokenization_allowed: bool
    de_tokenization_authority: str
    safe_display_label: str
    elioperator_privacy_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffReadbackContract:
    readback_id: str
    source_handoff_ref: str
    readback_type: str
    readback_status: str
    written_receipt_refs: tuple[str, ...]
    written_state_refs: tuple[str, ...]
    duplicate_retry_result: str
    rendered_surface_refs: tuple[str, ...]
    safe_display_summary: str
    blockers: tuple[str, ...]
    next_operator_question: str
    elioperator_message: str
    proof_refs: tuple[str, ...]
    protected_refs: tuple[str, ...]
    lifecycle_transition: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class HandoffCompatibilityMatrix:
    compatibility_id: str
    surfaces: tuple[str, ...]
    artifact_types: tuple[str, ...]
    compatible_origins: tuple[str, ...]
    compatible_targets: tuple[str, ...]
    compatible_agents: tuple[str, ...]
    role_based_actor_refs: dict[str, tuple[str, ...]]
    channel_neutrality: str
    workflow_owner: str
    state_owner: str
    blocked_split_brain_patterns: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class HandoffBuilderBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    builder_action_required: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class HandoffPostOfficeConcept:
    concept_id: str
    description: str
    what_it_solves: tuple[str, ...]
    what_it_does_not_do_yet: tuple[str, ...]
    future_runtime_path: str
    migration_strategy: str
    no_big_bang_rewrite_policy: str
    capital_hilton_adapter_path: str
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256(clone)


def _relationship_inventory() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "ref": name,
            "path": path,
            "present": (ROOT / path).exists(),
            "used_as": "relationship_reference_only_no_content_duplication",
        }
        for name, path in RELATIONSHIP_REF_PATHS.items()
    }


def _boundary(
    *,
    boundary_id: str,
    handoff_ref: str,
    local_write: bool = False,
    readback: bool = True,
    render: bool = True,
    approval_required: bool = False,
    guardian_review_required: bool = False,
    protected_evidence_required: bool = False,
    next_safe_move: str,
) -> HandoffAuthorityBoundary:
    return HandoffAuthorityBoundary(
        boundary_id=boundary_id,
        handoff_ref=handoff_ref,
        external_action_allowed=False,
        local_receipt_write_allowed=local_write,
        local_state_write_allowed=local_write,
        readback_write_allowed=readback,
        render_allowed=render,
        approval_required=approval_required,
        guardian_review_required=guardian_review_required,
        protected_evidence_required=protected_evidence_required,
        email_send_allowed=False,
        email_draft_allowed=False,
        coupa_submit_allowed=False,
        coupa_access_allowed=False,
        browser_automation_allowed=False,
        gmail_access_allowed=False,
        telegram_send_allowed=False,
        credential_handling_allowed=False,
        model_call_allowed=False,
        agent_activation_allowed=False,
        tool_execution_allowed=False,
        queue_execution_allowed=False,
        runtime_dispatch_allowed=False,
        raw_body_ingestion_allowed=False,
        next_safe_move=next_safe_move,
    )


def _handoff_payload_hash(seed: dict[str, Any]) -> str:
    return _sha256({"handoff_payload_seed": seed})


def _handoffs(created_at: str) -> tuple[CrossSurfaceArtifactHandoff, ...]:
    perf_seed = {
        "workflow_session_ref": "capital_hilton_invoice_workflow_session",
        "block_id": "performance_dates",
        "operation": "add_dates",
        "schema_ref": "mission_control_capture_request_intake.MissionControlBlockCaptureRequest",
    }
    po_seed = {
        "workflow_session_ref": "capital_hilton_invoice_workflow_session",
        "block_id": "proof_po_reference",
        "operation": "set_needs_discovery",
        "schema_ref": "capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureRequest",
    }
    reusable_seed = {
        "workflow_session_ref": "capital_hilton_invoice_workflow_session",
        "block_id": "ap_email_route",
        "operation": "reuse_fact_candidate",
        "schema_ref": "cross_lane_reusable_block_registry_contract.CrossLaneReusableFactBlock",
    }
    telegram_seed = {
        "workflow_session_ref": "capital_hilton_invoice_workflow_session",
        "block_id": "proof_po_reference",
        "operation": "set_needs_discovery",
        "origin_surface": "Telegram",
        "fronting_agent": "Cassandra",
    }
    return (
        CrossSurfaceArtifactHandoff(
            handoff_id="handoff_capital_hilton_performance_dates_capture",
            artifact_id="artifact_mission_control_perf_dates_add_may_22_29",
            artifact_type="CAPTURE_REQUEST",
            schema_ref="mission_control_capture_request_intake.MissionControlBlockCaptureRequest",
            schema_version="mission_control_capture_request_intake_v0",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="performance_dates",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="add_dates",
            origin_surface="Mission Control Mac",
            origin_actor="operator",
            source_channel="bounded_capture_outbox_json",
            addressed_actor=None,
            fronting_agent=None,
            assigned_role="validation_role",
            target_surface="Repo A backend",
            target_handler="mission_control_capture_request_intake",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            lifecycle_state="READBACK_READY",
            authority_boundary="authority_boundary_performance_dates_capture",
            privacy_class="non_sensitive_operational",
            sensitivity_class="low",
            tokenized_value_refs=(),
            protected_store_refs=(),
            payload_hash=_handoff_payload_hash(perf_seed),
            idempotency_key="handoff:v0:capital_hilton:performance_dates:add_dates",
            created_at=created_at,
            safe_display_summary="Capital Hilton performance dates capture handed to backend and readback is ready.",
            elioperator_message=(
                "OpenClaw can track this as a typed handoff: Mission Control emits, backend writes local state, "
                "Mission Control renders the readback later."
            ),
            next_safe_move="Check schema, consume through the existing backend intake, then publish readback.",
        ),
        CrossSurfaceArtifactHandoff(
            handoff_id="handoff_capital_hilton_po_coupa_delivery_facts_capture",
            artifact_id="artifact_capital_hilton_po_coupa_needs_discovery_capture",
            artifact_type="CAPTURE_REQUEST",
            schema_ref="capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureRequest",
            schema_version="capital_hilton_delivery_facts_capture_writer_v0",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="proof_po_reference",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="set_needs_discovery",
            origin_surface="Mission Control Mac",
            origin_actor="operator",
            source_channel="bounded_capture_outbox_json",
            addressed_actor=None,
            fronting_agent=None,
            assigned_role="delivery_readiness_role",
            target_surface="Repo A backend",
            target_handler="capital_hilton_delivery_facts_capture_writer",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            lifecycle_state="DUPLICATE_NOOP",
            authority_boundary="authority_boundary_po_coupa_capture",
            privacy_class="protected_payment_reference_posture",
            sensitivity_class="protected_metadata",
            tokenized_value_refs=(),
            protected_store_refs=(),
            payload_hash=_handoff_payload_hash(po_seed),
            idempotency_key="handoff:v0:capital_hilton:proof_po_reference:set_needs_discovery",
            created_at=created_at,
            safe_display_summary="PO/Coupa posture is NEEDS_DISCOVERY; no reference is confirmed.",
            elioperator_message=(
                "OpenClaw can show the real state without pretending it has a PO or Coupa route."
            ),
            next_safe_move="Ask for PO/reference, no-PO posture, Coupa requirement posture, or guided discovery.",
        ),
        CrossSurfaceArtifactHandoff(
            handoff_id="handoff_reusable_fact_tokenized_ap_route",
            artifact_id="artifact_reusable_fact_ap_route_tokenized",
            artifact_type="REUSABLE_FACT",
            schema_ref="cross_lane_reusable_block_registry_contract.CrossLaneReusableFactBlock",
            schema_version="cross_lane_reusable_block_registry_contract_v0",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="ap_email_route",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="suggest_tokenized_reuse",
            origin_surface="Repo A backend",
            origin_actor="local_read_model_export",
            source_channel="post_office_contract_preview",
            addressed_actor=None,
            fronting_agent=None,
            assigned_role="delivery_readiness_role",
            target_surface="future compatible surface",
            target_handler="future_reusable_block_intake_handler",
            reply_to_surface="Repo A backend",
            reply_to_channel="readback_contract",
            lifecycle_state="CREATED",
            authority_boundary="authority_boundary_reusable_fact_preview",
            privacy_class="protected_contact_route",
            sensitivity_class="protected",
            tokenized_value_refs=("tokref:local-only:capital_hilton:ap_route:v1",),
            protected_store_refs=("pii_vault_ref:local-only:ap_route:capital_hilton:v1",),
            payload_hash=_handoff_payload_hash(reusable_seed),
            idempotency_key="handoff:v0:capital_hilton:reusable_fact:ap_route_token",
            created_at=created_at,
            safe_display_summary="Reusable fact handoff carries token refs and safe labels only.",
            elioperator_message="Useful facts can travel between surfaces without printing protected values everywhere.",
            next_safe_move="Keep raw value out of normal payloads; require protected local authority for reveal.",
        ),
        CrossSurfaceArtifactHandoff(
            handoff_id="handoff_telegram_cassandra_delivery_facts_entry",
            artifact_id="artifact_telegram_cassandra_po_posture_capture_preview",
            artifact_type="CAPTURE_REQUEST",
            schema_ref="capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureRequest",
            schema_version="capital_hilton_delivery_facts_capture_writer_v0",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="proof_po_reference",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="set_needs_discovery",
            origin_surface="Telegram",
            origin_actor="operator",
            source_channel="future_telegram_entry_surface",
            addressed_actor="Cassandra",
            fronting_agent="Cassandra",
            assigned_role="delivery_readiness_role",
            target_surface="Repo A backend",
            target_handler="capital_hilton_delivery_facts_capture_writer",
            reply_to_surface="Telegram",
            reply_to_channel="future_safe_readback_summary",
            lifecycle_state="CREATED",
            authority_boundary="authority_boundary_telegram_entry_no_send",
            privacy_class="protected_payment_reference_posture",
            sensitivity_class="protected_metadata",
            tokenized_value_refs=(),
            protected_store_refs=(),
            payload_hash=_handoff_payload_hash(telegram_seed),
            idempotency_key="handoff:v0:telegram:capital_hilton:proof_po_reference:set_needs_discovery",
            created_at=created_at,
            safe_display_summary="Telegram/Cassandra can front the same backend handler; Telegram does not own truth.",
            elioperator_message=(
                "The entry surface changes, but the workflow/session/block grammar stays the same."
            ),
            next_safe_move="Normalize into the same backend capture shape before any local write.",
        ),
    )


def _lifecycle_policy() -> HandoffLifecyclePolicy:
    return HandoffLifecyclePolicy(
        policy_id="handoff_lifecycle_policy_v0",
        allowed_lifecycle_states=LIFECYCLE_STATES,
        operator_visible_states=(
            "EMITTED",
            "RECEIVED",
            "WRITTEN",
            "READBACK_READY",
            "RENDERED",
            "BLOCKED",
            "REJECTED",
            "DUPLICATE_NOOP",
        ),
        below_deck_states=(
            "VALIDATED",
            "CONSUMED",
            "technical handler details",
            "payload hash checks",
            "schema validation details",
        ),
        terminal_states=("RENDERED", "BLOCKED", "REJECTED", "DUPLICATE_NOOP", "UNKNOWN_FAIL_CLOSED"),
        duplicate_policy="Same idempotency key and payload hash returns DUPLICATE_NOOP; no second write implied.",
        blocked_policy="Blocked means fail closed and show a safe operator message.",
        rejection_policy="Unsupported schema, target handler, or UI-coupled payload becomes REJECTED.",
        retry_policy="Retries must preserve idempotency key and payload hash or become a new reviewed handoff.",
        stale_policy="Readback packages can be stale; target surface must compare lifecycle and payload hash.",
        next_safe_move="Use lifecycle as status only, never as external execution authority.",
    )


def _schema_rule() -> HandoffSchemaValidationRule:
    return HandoffSchemaValidationRule(
        rule_id="handoff_schema_validation_rule_v0",
        artifact_type="ALL_TYPED_HANDOFF_ARTIFACTS",
        required_fields=REQUIRED_HANDOFF_FIELDS,
        forbidden_fields=FORBIDDEN_PAYLOAD_FIELDS,
        required_namespace_fields=(
            "world_ref",
            "lane_ref",
            "block_id",
            "workflow_session_ref",
            "operation",
        ),
        required_authority_fields=("authority_boundary",),
        required_privacy_fields=("privacy_class", "sensitivity_class"),
        required_idempotency_fields=("payload_hash", "idempotency_key"),
        visual_agnostic_requirements=VISUAL_AGNOSTIC_REQUIREMENTS,
        raw_value_forbidden=True,
        validation_failure_state="REJECTED",
        elioperator_failure_message=(
            "ELIOPERATOR: This handoff shape is not safe enough to route; fix the packet instead of guessing."
        ),
        next_safe_move="Reject UI-coupled or raw protected payloads before handler routing.",
    )


def _routing_rules() -> tuple[HandoffRoutingRule, ...]:
    return (
        HandoffRoutingRule(
            routing_rule_id="route_capital_hilton_performance_dates_capture",
            artifact_type="CAPTURE_REQUEST",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="performance_dates",
            target_surface="Repo A backend",
            target_handler="mission_control_capture_request_intake",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            handler_authority_scope="local guarded capture intake only",
            supported_operations=("add_dates", "confirm_dates", "correct_dates"),
            unsupported_operations=("invoice_generation", "email_send", "coupa_submit"),
            routing_status="SUPPORTED_EXISTING_HANDLER",
            fallback_behavior="Fail closed as UNSUPPORTED_OPERATION or UNSUPPORTED_TARGET_HANDLER.",
            next_safe_move="Validate schema and use existing performance dates intake path.",
        ),
        HandoffRoutingRule(
            routing_rule_id="route_capital_hilton_po_coupa_delivery_facts_capture",
            artifact_type="CAPTURE_REQUEST",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="proof_po_reference",
            target_surface="Repo A backend",
            target_handler="capital_hilton_delivery_facts_capture_writer",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            handler_authority_scope="local delivery facts receipt/state intake only",
            supported_operations=(
                "set_needs_discovery",
                "set_no_po_known_pending_proof",
                "set_coupa_required_unknown",
                "set_po_reference_candidate",
                "set_coupa_reference_candidate",
            ),
            unsupported_operations=("coupa_login", "browser_automation", "credential_capture", "submit_invoice"),
            routing_status="SUPPORTED_EXISTING_HANDLER",
            fallback_behavior="Fail closed and ask for a supported delivery facts posture.",
            next_safe_move="Validate and capture posture without confirming hidden references.",
        ),
        HandoffRoutingRule(
            routing_rule_id="route_reusable_fact_future_handler",
            artifact_type="REUSABLE_FACT",
            world_ref="any",
            lane_ref="any",
            block_id="compatible_reusable_fact_block",
            target_surface="Repo A backend",
            target_handler="future_reusable_block_intake_handler",
            reply_to_surface="origin_surface",
            reply_to_channel="safe_readback_summary",
            handler_authority_scope="future suggestion/readback only; no live auto-apply",
            supported_operations=("suggest_reuse", "inform_only", "tokenized_match_pending"),
            unsupported_operations=("raw_value_reveal", "cross_tenant_apply", "live_auto_apply"),
            routing_status="FUTURE_HANDLER_NOT_LIVE",
            fallback_behavior="Keep as read-model compatibility only.",
            next_safe_move="Build handler later only with tokenization and scope checks.",
        ),
        HandoffRoutingRule(
            routing_rule_id="route_protected_evidence_reference_future_handler",
            artifact_type="PROTECTED_EVIDENCE_REFERENCE",
            world_ref="any",
            lane_ref="any",
            block_id="protected_evidence_reference",
            target_surface="Repo A backend",
            target_handler="future_protected_evidence_reference_handler",
            reply_to_surface="origin_surface",
            reply_to_channel="protected_metadata_readback",
            handler_authority_scope="metadata-only protected reference validation",
            supported_operations=("register_metadata_reference", "require_guardian_review"),
            unsupported_operations=("raw_body_ingestion", "credential_capture", "session_cookie_capture"),
            routing_status="FUTURE_HANDLER_NOT_LIVE",
            fallback_behavior="Redirect to protected-evidence contract; normal read-models stay metadata-only.",
            next_safe_move="Do not ingest raw proof bodies.",
        ),
    )


def _authority_boundaries() -> tuple[HandoffAuthorityBoundary, ...]:
    return (
        _boundary(
            boundary_id="authority_boundary_performance_dates_capture",
            handoff_ref="handoff_capital_hilton_performance_dates_capture",
            local_write=True,
            next_safe_move="Local guarded receipt/state/readback only; no invoice/send/submit.",
        ),
        _boundary(
            boundary_id="authority_boundary_po_coupa_capture",
            handoff_ref="handoff_capital_hilton_po_coupa_delivery_facts_capture",
            local_write=True,
            protected_evidence_required=False,
            next_safe_move="Capture posture only; no Coupa access or reference reveal.",
        ),
        _boundary(
            boundary_id="authority_boundary_reusable_fact_preview",
            handoff_ref="handoff_reusable_fact_tokenized_ap_route",
            local_write=False,
            guardian_review_required=True,
            protected_evidence_required=True,
            next_safe_move="Tokenized suggestion only; no live reuse or de-tokenization.",
        ),
        _boundary(
            boundary_id="authority_boundary_telegram_entry_no_send",
            handoff_ref="handoff_telegram_cassandra_delivery_facts_entry",
            local_write=False,
            render=False,
            next_safe_move="Normalize future Telegram entry; no Telegram send or backend mutation from this contract.",
        ),
        _boundary(
            boundary_id="authority_boundary_send_gate_blocked",
            handoff_ref="approval_send_gate_example",
            local_write=False,
            readback=True,
            render=True,
            approval_required=True,
            next_safe_move="Block send-ready claims until approval receipt and gated adapter exist.",
        ),
    )


def _privacy_boundaries() -> tuple[HandoffPrivacyBoundary, ...]:
    return (
        HandoffPrivacyBoundary(
            privacy_boundary_id="privacy_boundary_non_sensitive_operational",
            handoff_ref="handoff_capital_hilton_performance_dates_capture",
            privacy_class="non_sensitive_operational",
            sensitivity_class="low",
            raw_value_allowed=True,
            tokenized_value_ref_allowed=False,
            protected_store_ref_allowed=False,
            central_sync_allowed=True,
            allowed_surfaces=("Mission Control Mac", "Repo A backend", "future Telegram safe summary"),
            forbidden_surfaces=(),
            redaction_required=False,
            de_tokenization_allowed=False,
            de_tokenization_authority="not_applicable",
            safe_display_label="Performance dates captured",
            elioperator_privacy_summary="ELIOPERATOR: Dates are normal workflow facts, but the packet still uses typed metadata.",
            next_safe_move="Allow safe readback; keep execution authority separate.",
        ),
        HandoffPrivacyBoundary(
            privacy_boundary_id="privacy_boundary_protected_reference_posture",
            handoff_ref="handoff_capital_hilton_po_coupa_delivery_facts_capture",
            privacy_class="protected_payment_reference_posture",
            sensitivity_class="protected_metadata",
            raw_value_allowed=False,
            tokenized_value_ref_allowed=True,
            protected_store_ref_allowed=True,
            central_sync_allowed=False,
            allowed_surfaces=("Mission Control Mac", "Repo A backend", "Guardian review surface"),
            forbidden_surfaces=("public_channel", "unscoped_client_surface"),
            redaction_required=True,
            de_tokenization_allowed=False,
            de_tokenization_authority="none_in_this_contract",
            safe_display_label="PO/Coupa posture needs discovery",
            elioperator_privacy_summary=(
                "ELIOPERATOR: The normal handoff can say a reference is needed; it cannot print a protected reference."
            ),
            next_safe_move="Capture protected references only through a guarded metadata/token path later.",
        ),
        HandoffPrivacyBoundary(
            privacy_boundary_id="privacy_boundary_reusable_fact_tokenized",
            handoff_ref="handoff_reusable_fact_tokenized_ap_route",
            privacy_class="protected_contact_route",
            sensitivity_class="protected",
            raw_value_allowed=False,
            tokenized_value_ref_allowed=True,
            protected_store_ref_allowed=True,
            central_sync_allowed=False,
            allowed_surfaces=("Mission Control Mac", "Repo A backend", "agent handoff packet"),
            forbidden_surfaces=("public_channel", "cross_tenant_surface"),
            redaction_required=True,
            de_tokenization_allowed=False,
            de_tokenization_authority="explicit_protected_local_authority_required_future",
            safe_display_label="AP route token available",
            elioperator_privacy_summary="ELIOPERATOR: A token can prove OpenClaw has a route without exposing the route.",
            next_safe_move="Use safe label and token ref only.",
        ),
    )


def _readbacks() -> tuple[HandoffReadbackContract, ...]:
    return (
        HandoffReadbackContract(
            readback_id="readback_capital_hilton_performance_dates_capture",
            source_handoff_ref="handoff_capital_hilton_performance_dates_capture",
            readback_type="READBACK_READY_FOR_SURFACE",
            readback_status="READBACK_READY",
            written_receipt_refs=("mc_receipt_45620b4bce5c87a6b208",),
            written_state_refs=("mc_state_f63e73dee78916436061",),
            duplicate_retry_result="DUPLICATE_NOOP",
            rendered_surface_refs=("Mission Control closeout rendered by later Mac import",),
            safe_display_summary="OpenClaw has four Capital Hilton performance dates locally.",
            blockers=(
                "rate_confirmation_if_not_already_confirmed",
                "po_coupa_reference_unresolved",
                "delivery_approval_send_gates",
            ),
            next_operator_question="Confirm remaining delivery facts before final send or submit.",
            elioperator_message="ELIOPERATOR: Backend readback is ready; rendered does not mean sent.",
            proof_refs=(),
            protected_refs=(),
            lifecycle_transition=("EMITTED", "RECEIVED", "WRITTEN", "READBACK_READY", "RENDERED"),
            next_safe_move="Use readback to update visible state; keep delivery gates closed.",
        ),
        HandoffReadbackContract(
            readback_id="readback_capital_hilton_po_coupa_delivery_facts",
            source_handoff_ref="handoff_capital_hilton_po_coupa_delivery_facts_capture",
            readback_type="DUPLICATE_NOOP",
            readback_status="DUPLICATE_NOOP",
            written_receipt_refs=("ch_delivery_receipt_dedaea68629bdc8d003a",),
            written_state_refs=("ch_delivery_state_8a4fb289efc696c438b2",),
            duplicate_retry_result="DUPLICATE_NOOP",
            rendered_surface_refs=("Mission Control PO/Coupa readback package",),
            safe_display_summary="PO/Coupa posture is NEEDS_DISCOVERY; no reference is confirmed.",
            blockers=(
                "po_or_payment_reference_unknown",
                "coupa_requirement_unresolved",
                "ap_email_route_needs_confirmation",
                "email_coupa_approval_send_blocked",
            ),
            next_operator_question=(
                "Provide a reference, mark no known reference pending proof, mark Coupa unknown, or continue discovery."
            ),
            elioperator_message="ELIOPERATOR: Duplicate means OpenClaw already had this exact posture; no duplicate was written.",
            proof_refs=("protected_evidence_metadata_only_future",),
            protected_refs=("guardian_posture_required_for_raw_proof_future",),
            lifecycle_transition=("EMITTED", "RECEIVED", "DUPLICATE_NOOP", "READBACK_READY"),
            next_safe_move="Ask only the next delivery-facts question; no external action.",
        ),
        HandoffReadbackContract(
            readback_id="readback_send_gate_blocked_without_approval",
            source_handoff_ref="approval_send_gate_example",
            readback_type="BLOCKED_FAIL_CLOSED",
            readback_status="BLOCKED",
            written_receipt_refs=(),
            written_state_refs=(),
            duplicate_retry_result="not_applicable",
            rendered_surface_refs=(),
            safe_display_summary="Send-ready claim is blocked because approval and gated adapter are absent.",
            blockers=("missing_approval_receipt", "missing_gated_send_or_submit_adapter"),
            next_operator_question="Approve only after artifact, route, proof, and delivery adapter are coherent.",
            elioperator_message="ELIOPERATOR: OpenClaw will not call something send-ready just because a draft exists.",
            proof_refs=(),
            protected_refs=(),
            lifecycle_transition=("CREATED", "BLOCKED"),
            next_safe_move="Build approval packet/readback first; no send.",
        ),
    )


def _compatibility_matrix() -> HandoffCompatibilityMatrix:
    return HandoffCompatibilityMatrix(
        compatibility_id="handoff_compatibility_matrix_v0",
        surfaces=(
            "Mission Control Mac",
            "Repo A backend",
            "Telegram",
            "Cassandra",
            "Chief",
            "Guardian",
            "Hermes",
            "Niles",
            "future agent",
            "future client app",
            "future mobile",
            "future voice",
        ),
        artifact_types=ARTIFACT_TYPES,
        compatible_origins=("Mission Control Mac", "Telegram", "Repo A backend", "future client app"),
        compatible_targets=("Repo A backend", "Mission Control Mac", "Guardian", "future safe renderer"),
        compatible_agents=("Cassandra", "Chief", "Guardian", "Hermes", "Niles", "Clara", "future agent"),
        role_based_actor_refs={
            "validation_role": ("Cassandra", "Guardian", "future validation agent"),
            "approval_role": ("Guardian", "operator"),
            "drafting_role": ("Clara", "future drafting agent"),
            "delivery_readiness_role": ("Cassandra", "Guardian", "future delivery readiness agent"),
            "security_gate_role": ("Guardian",),
        },
        channel_neutrality="Same workflow/session/block/capture grammar regardless of surface.",
        workflow_owner="backend receipt/state/readback substrate",
        state_owner="backend receipt/state/readback substrate",
        blocked_split_brain_patterns=(
            "Mac-only canonical workflow state",
            "Telegram-owned workflow truth",
            "agent-owned durable state",
            "surface-local send readiness without receipt/readback",
        ),
        next_safe_move="Keep surfaces as render/origin points and keep truth in receipt-backed readback.",
    )


def _builder_blockers() -> tuple[HandoffBuilderBlocker, ...]:
    return (
        HandoffBuilderBlocker(
            blocker_id="blocker_missing_workflow_session_ref",
            blocker_type="MISSING_WORKFLOW_SESSION_REF",
            condition="Packet lacks workflow_session_ref.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: OpenClaw cannot route work without knowing which workflow session it belongs to.",
            builder_action_required="Add workflow_session_ref before routing.",
            fail_closed=True,
            next_safe_move="Reject and request a corrected packet.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_missing_artifact_type",
            blocker_type="MISSING_ARTIFACT_TYPE",
            condition="Packet lacks artifact_type.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: The post office needs to know what kind of artifact this is.",
            builder_action_required="Set one of the supported artifact types.",
            fail_closed=True,
            next_safe_move="Reject unsupported shape.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_missing_schema_ref",
            blocker_type="MISSING_SCHEMA_REF",
            condition="Packet lacks schema_ref.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: No schema means no safe handler.",
            builder_action_required="Attach schema_ref and schema_version.",
            fail_closed=True,
            next_safe_move="Reject until schema is explicit.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_missing_idempotency_key",
            blocker_type="MISSING_IDEMPOTENCY_KEY",
            condition="Packet lacks idempotency key or payload hash.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: OpenClaw needs duplicate protection before it writes state.",
            builder_action_required="Provide deterministic idempotency_key and payload_hash.",
            fail_closed=True,
            next_safe_move="Reject until duplicate behavior is defined.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_missing_authority_boundary",
            blocker_type="MISSING_AUTHORITY_BOUNDARY",
            condition="Packet does not state what authority is requested or forbidden.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: A handoff without authority boundaries is not safe to process.",
            builder_action_required="Attach explicit authority_boundary.",
            fail_closed=True,
            next_safe_move="Reject and require authority metadata.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_ui_coupled_payload",
            blocker_type="UI_COUPLED_PAYLOAD",
            condition="Packet contains screen coordinates, view identifiers, button frames, or rendering geometry.",
            severity="reject",
            elioperator_warning="ELIOPERATOR: This packet is tied to a screen layout, not workflow state.",
            builder_action_required="Replace UI fields with workflow/session/block/value fields.",
            fail_closed=True,
            next_safe_move="Reject as REJECTED and ask sender to emit visual-agnostic payload.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_raw_protected_value_in_payload",
            blocker_type="RAW_PROTECTED_VALUE_IN_PAYLOAD",
            condition="Packet carries raw contact, phone, payment reference, credential, token, body, or private document material.",
            severity="reject_or_redirect_to_protected_path",
            elioperator_warning="ELIOPERATOR: Protected values must be tokenized or referenced, not copied into normal handoffs.",
            builder_action_required="Use tokenized_value_ref, protected_store_ref, or protected evidence reference path.",
            fail_closed=True,
            next_safe_move="Reject normal handoff or redirect to protected-evidence metadata contract.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_unsupported_target_handler",
            blocker_type="UNSUPPORTED_TARGET_HANDLER",
            condition="Packet names a handler that has no route in the registry.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: OpenClaw will not guess which backend path should handle this.",
            builder_action_required="Add a routing rule or use a supported handler.",
            fail_closed=True,
            next_safe_move="Reject until route is explicit.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_generated_artifact_without_file_hash",
            blocker_type="GENERATED_ARTIFACT_WITHOUT_FILE_HASH",
            condition="Artifact preview claims a generated file but provides no path/hash proof.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: No file hash means no artifact proof.",
            builder_action_required="Generate real artifact and hash, or mark preview/readiness only.",
            fail_closed=True,
            next_safe_move="Block fake artifact readiness.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_send_ready_without_approval_gate",
            blocker_type="SEND_READY_WITHOUT_APPROVAL_GATE",
            condition="Packet says send-ready without approval receipt and gated adapter.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: Drafts and readbacks do not authorize sending.",
            builder_action_required="Add approval packet, approval receipt, and gated send/submit adapter before readiness.",
            fail_closed=True,
            next_safe_move="Block send and produce approval/readiness blocker.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_calculated_state_copied_as_truth",
            blocker_type="CALCULATED_STATE_COPIED_AS_TRUTH",
            condition="Packet tries to reuse calculated subtotal or readiness as copied canonical truth.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: Calculated state must derive from source facts each time.",
            builder_action_required="Carry source receipt refs and recalculate below deck.",
            fail_closed=True,
            next_safe_move="Reject copied calculated state as truth.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_cross_tenant_payload_leak",
            blocker_type="CROSS_TENANT_PAYLOAD_LEAK",
            condition="Packet mixes tenant/client scope or tries to reuse protected values across tenant boundaries.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: One client's protected facts cannot bleed into another client's work.",
            builder_action_required="Correct tenant/client scope and use protected local comparison only.",
            fail_closed=True,
            next_safe_move="Reject cross-scope payload.",
        ),
        HandoffBuilderBlocker(
            blocker_id="blocker_unknown_fail_closed",
            blocker_type="UNKNOWN_FAIL_CLOSED",
            condition="Packet cannot be classified safely.",
            severity="fail_closed",
            elioperator_warning="ELIOPERATOR: Unknown handoff shape stays parked until it is made explicit.",
            builder_action_required="Add schema, route, authority, privacy, and readback metadata.",
            fail_closed=True,
            next_safe_move="Park and request a typed packet.",
        ),
    )


def _post_office_concept() -> HandoffPostOfficeConcept:
    return HandoffPostOfficeConcept(
        concept_id="openclaw_post_office_contract_v0",
        description=(
            "A typed artifact handoff registry for routing capture requests, readbacks, closeouts, "
            "agent handoffs, reusable facts, and protected references between surfaces."
        ),
        what_it_solves=(
            "Reduces one-off Mac/PC relay packages.",
            "Makes artifact type, schema, workflow/session/block, route, authority, privacy, and readback explicit.",
            "Lets Mission Control, Telegram, agents, and future apps remain surfaces instead of truth owners.",
            "Gives builder agents fail-closed warnings before they ship unsafe handoffs.",
        ),
        what_it_does_not_do_yet=(
            "No live bus.",
            "No file watcher.",
            "No automatic Mac import.",
            "No automatic PC consume.",
            "No live Telegram integration.",
            "No model, agent, or tool dispatch.",
            "No external email, Coupa, browser, or approval action.",
        ),
        future_runtime_path=(
            "A later gated runtime may consume this registry, but only after handlers, approvals, "
            "idempotency, privacy, and readback contracts are implemented."
        ),
        migration_strategy=(
            "Check existing custom bridge packages against this registry and migrate one adapter at a time."
        ),
        no_big_bang_rewrite_policy="Existing steel-thread adapters keep working; the registry becomes the common map.",
        capital_hilton_adapter_path=(
            "Start by mapping Mission Control capture request intake and Capital Hilton delivery facts writer."
        ),
        next_safe_move="Run compatibility/replacement audit before implementing any live post-office runtime.",
    )


def _examples() -> dict[str, dict[str, Any]]:
    return {
        "capital_hilton_performance_dates_capture": {
            "example_id": "capital_hilton_performance_dates_capture",
            "artifact_type": "CAPTURE_REQUEST",
            "origin_surface": "Mission Control Mac",
            "target_handler": "mission_control_capture_request_intake",
            "lifecycle": ("EMITTED", "RECEIVED", "WRITTEN", "READBACK_READY", "RENDERED"),
            "block_id": "performance_dates",
            "operation": "add_dates",
            "external_authority": False,
            "readback": "OpenClaw has four local performance dates after receipt/state readback.",
        },
        "capital_hilton_po_coupa_delivery_facts_capture": {
            "example_id": "capital_hilton_po_coupa_delivery_facts_capture",
            "artifact_type": "CAPTURE_REQUEST",
            "block_id": "proof_po_reference",
            "operation": "set_needs_discovery",
            "target_handler": "capital_hilton_delivery_facts_capture_writer",
            "readback": "PO/Coupa posture is NEEDS_DISCOVERY.",
            "false_claims_blocked": ("no PO/reference falsely confirmed", "no Coupa route falsely resolved"),
            "external_authority": False,
        },
        "reusable_fact_handoff": {
            "example_id": "reusable_fact_handoff",
            "artifact_type": "REUSABLE_FACT",
            "compatible_contract": "cross_lane_reusable_block_registry_contract",
            "tokenized_value_ref_allowed": True,
            "raw_value_forbidden": True,
            "live_auto_apply": False,
        },
        "telegram_cassandra_entry": {
            "example_id": "telegram_cassandra_entry",
            "origin_surface": "Telegram",
            "addressed_actor": "Cassandra",
            "fronting_agent": "Cassandra",
            "assigned_role": "delivery_readiness_role",
            "target_handler": "capital_hilton_delivery_facts_capture_writer",
            "workflow_owner": "backend receipt/state/readback substrate",
            "truth_owner": "backend receipt/state/readback substrate",
            "next_safe_move": "Normalize to the same handler as Mission Control for the same block and operation.",
        },
        "blocked_ui_coupled_payload": {
            "example_id": "blocked_ui_coupled_payload",
            "contains_forbidden_fields": ("screen_x", "button_frame"),
            "result": "REJECTED",
            "elioperator_warning": "ELIOPERATOR: Screen layout is not workflow state.",
        },
        "blocked_raw_protected_payload": {
            "example_id": "blocked_raw_protected_payload",
            "contains_forbidden_fields": ("raw_email", "raw_po_reference"),
            "result": "REJECTED_OR_REDIRECTED_TO_PROTECTED_PATH",
            "normal_read_model_must_not_contain_raw_value": True,
            "elioperator_warning": "ELIOPERATOR: Protected values need token refs or protected metadata paths.",
        },
        "approval_send_gate": {
            "example_id": "approval_send_gate",
            "send_ready_claim": "blocked_without_approval_receipt_and_gated_adapter",
            "result": "BLOCKED",
            "fake_readiness_allowed": False,
            "external_authority": False,
            "elioperator_warning": "ELIOPERATOR: Drafts are not permission to send.",
        },
    }


def _model_schemas() -> dict[str, dict[str, Any]]:
    return {
        "cross_surface_artifact_handoff": {
            "model_name": "CrossSurfaceArtifactHandoff",
            "required_fields": list(REQUIRED_HANDOFF_FIELDS),
            "artifact_types": list(ARTIFACT_TYPES),
            "lifecycle_states": list(LIFECYCLE_STATES),
        },
        "handoff_lifecycle_policy": {
            "model_name": "HandoffLifecyclePolicy",
            "required_fields": list(REQUIRED_LIFECYCLE_POLICY_FIELDS),
        },
        "handoff_schema_validation_rule": {
            "model_name": "HandoffSchemaValidationRule",
            "required_fields": list(REQUIRED_SCHEMA_RULE_FIELDS),
        },
        "handoff_routing_rule": {
            "model_name": "HandoffRoutingRule",
            "required_fields": list(REQUIRED_ROUTING_RULE_FIELDS),
        },
        "handoff_authority_boundary": {
            "model_name": "HandoffAuthorityBoundary",
            "required_fields": list(REQUIRED_AUTHORITY_BOUNDARY_FIELDS),
        },
        "handoff_privacy_boundary": {
            "model_name": "HandoffPrivacyBoundary",
            "required_fields": list(REQUIRED_PRIVACY_BOUNDARY_FIELDS),
        },
        "handoff_readback_contract": {
            "model_name": "HandoffReadbackContract",
            "required_fields": list(REQUIRED_READBACK_FIELDS),
            "readback_types": list(READBACK_TYPES),
        },
        "handoff_compatibility_matrix": {
            "model_name": "HandoffCompatibilityMatrix",
            "required_fields": list(REQUIRED_COMPATIBILITY_FIELDS),
        },
        "handoff_builder_blocker": {
            "model_name": "HandoffBuilderBlocker",
            "required_fields": list(REQUIRED_BUILDER_BLOCKER_FIELDS),
            "blocker_types": list(BUILDER_BLOCKER_TYPES),
        },
        "handoff_post_office_concept": {
            "model_name": "HandoffPostOfficeConcept",
            "required_fields": list(REQUIRED_POST_OFFICE_FIELDS),
        },
    }


def _all_external_authority_false(boundaries: tuple[HandoffAuthorityBoundary, ...]) -> bool:
    for boundary in boundaries:
        data = asdict(boundary)
        if any(data[field] is not False for field in EXTERNAL_AUTHORITY_FIELDS):
            return False
    return True


def build_cross_surface_artifact_handoff_registry_contract(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or utc_now()
    handoffs = _handoffs(timestamp)
    lifecycle = _lifecycle_policy()
    schema_rule = _schema_rule()
    routing_rules = _routing_rules()
    authority_boundaries = _authority_boundaries()
    privacy_boundaries = _privacy_boundaries()
    readbacks = _readbacks()
    compatibility = _compatibility_matrix()
    blockers = _builder_blockers()
    concept = _post_office_concept()
    examples = _examples()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": timestamp,
        "purpose": (
            "Define a cross-surface typed artifact handoff registry so surfaces can route capture requests, "
            "readbacks, closeouts, reusable facts, and protected references without owning workflow truth."
        ),
        "doctrine": {
            "post_office_contract_not_live_bus": True,
            "handoff_lifecycle_not_external_authority": True,
            "rendered_does_not_mean_sent_or_submitted": True,
            "written_does_not_mean_approved": True,
            "handoffs_are_visual_agnostic": True,
            "surfaces_are_not_state_owners": True,
            "raw_protected_values_forbidden_in_normal_handoffs": True,
            "tokenized_value_refs_are_not_proof": True,
            "calculated_state_must_derive_not_copy": True,
        },
        "model_schemas": _model_schemas(),
        "forbidden_payload_fields": list(FORBIDDEN_PAYLOAD_FIELDS),
        "visual_agnostic_requirements": list(VISUAL_AGNOSTIC_REQUIREMENTS),
        "lifecycle_policy": asdict(lifecycle),
        "schema_validation_rule": asdict(schema_rule),
        "handoffs_by_id": {handoff.handoff_id: asdict(handoff) for handoff in handoffs},
        "routing_rules_by_id": {rule.routing_rule_id: asdict(rule) for rule in routing_rules},
        "authority_boundaries_by_id": {
            boundary.boundary_id: asdict(boundary) for boundary in authority_boundaries
        },
        "privacy_boundaries_by_id": {
            boundary.privacy_boundary_id: asdict(boundary) for boundary in privacy_boundaries
        },
        "readbacks_by_id": {readback.readback_id: asdict(readback) for readback in readbacks},
        "compatibility_matrix": asdict(compatibility),
        "builder_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "post_office_concept": asdict(concept),
        "examples": examples,
        "relationship_inventory": _relationship_inventory(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "privacy_security_requirements": {
            "no_raw_pii_in_generated_read_models": True,
            "no_raw_protected_values_in_operator_markdown": True,
            "handoff_examples_avoid_real_contact_or_reference_values": True,
            "tokenized_protected_values_allowed_as_refs_only": True,
            "public_raw_hash_of_sensitive_values_allowed": False,
            "de_tokenization_allowed": False,
            "cross_tenant_leakage_blocked": True,
            "ui_specific_payload_fields_blocked": True,
        },
        "operator_markdown_mode": "ELIOPERATOR",
    }

    payload["machine_proof"] = {
        "cross_surface_artifact_handoff_model_present": True,
        "handoff_lifecycle_policy_model_present": True,
        "handoff_schema_validation_rule_model_present": True,
        "handoff_routing_rule_model_present": True,
        "handoff_authority_boundary_model_present": True,
        "handoff_privacy_boundary_model_present": True,
        "handoff_readback_contract_model_present": True,
        "handoff_compatibility_matrix_model_present": True,
        "handoff_builder_blocker_model_present": True,
        "handoff_post_office_concept_model_present": True,
        "all_required_lifecycle_states_present": set(LIFECYCLE_STATES) == set(lifecycle.allowed_lifecycle_states),
        "capital_hilton_performance_dates_example_present": (
            "capital_hilton_performance_dates_capture" in examples
        ),
        "capital_hilton_po_coupa_example_present": (
            "capital_hilton_po_coupa_delivery_facts_capture" in examples
        ),
        "reusable_fact_example_tokenization_compatible": examples["reusable_fact_handoff"][
            "tokenized_value_ref_allowed"
        ]
        is True
        and examples["reusable_fact_handoff"]["raw_value_forbidden"] is True,
        "telegram_cassandra_fronting_role_distinct": (
            examples["telegram_cassandra_entry"]["fronting_agent"] == "Cassandra"
            and examples["telegram_cassandra_entry"]["assigned_role"] == "delivery_readiness_role"
        ),
        "ui_coupled_payload_blocker_present": "blocker_ui_coupled_payload"
        in payload["builder_blockers_by_id"],
        "raw_protected_payload_blocker_present": "blocker_raw_protected_value_in_payload"
        in payload["builder_blockers_by_id"],
        "send_ready_without_approval_blocker_present": "blocker_send_ready_without_approval_gate"
        in payload["builder_blockers_by_id"],
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "all_external_authority_flags_false_in_boundaries": _all_external_authority_false(authority_boundaries),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_sensitive_fixture_values_included": False,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    concept = payload["post_office_concept"]
    proof = payload["machine_proof"]
    return "\n".join(
        [
            "# Cross-Surface Artifact Handoff Registry v0",
            "",
            "## ELIOPERATOR",
            "",
            "This is the OpenClaw post office contract. It does not move files by itself, watch folders, "
            "import Mac packages, run Telegram, launch agents, or send anything externally.",
            "",
            "The problem it solves: Mission Control can emit a capture request, Repo A can consume it, "
            "Repo A can publish readback, and Mission Control can render the result. That loop works, "
            "but each lane has been using one-off shuttle language. The post office gives those artifacts "
            "a common envelope.",
            "",
            "A handoff records what the artifact is, which schema validates it, which world/lane/block/session "
            "it belongs to, who originated it, which handler should process it, what authority boundary applies, "
            "what privacy boundary applies, and what readback the operator should see.",
            "",
            "Lifecycle is status, not permission. WRITTEN means OpenClaw saved local state. RENDERED means a "
            "surface showed the result. Neither means approved, sent, submitted, or externally executed.",
            "",
            "Mission Control, Telegram, Cassandra, Chief, Guardian, Hermes, Niles, and future client apps are "
            "surfaces or fronting actors. They do not own workflow truth. The backend receipt/state/readback "
            "substrate owns canonical local truth.",
            "",
            "Protected values stay protected. Normal handoffs can carry safe labels, tokenized_value_ref, "
            "protected_store_ref, privacy_class, and sensitivity_class. They cannot carry raw contact routes, "
            "raw payment references, raw proof bodies, credentials, cookies, tokens, or private documents.",
            "",
            "Builder warnings are fail-closed. UI-coupled packets, raw protected payloads, missing schema, "
            "missing idempotency, fake artifact hashes, send-ready claims without approval, copied calculated "
            "state, and cross-tenant leaks are blocked before routing.",
            "",
            "## What It Does Not Do Yet",
            "",
            "\n".join(f"- {item}" for item in concept["what_it_does_not_do_yet"]),
            "",
            "## Capital Hilton Examples",
            "",
            "- Performance dates capture maps to `mission_control_capture_request_intake`.",
            "- PO/Coupa delivery facts capture maps to `capital_hilton_delivery_facts_capture_writer`.",
            "- Reusable fact handoff references the tokenization contract and forbids raw values.",
            "- Telegram/Cassandra can front the same backend handler without owning truth.",
            "- Approval/send remains blocked unless an approval receipt and gated adapter exist.",
            "",
            "## Machine Proof",
            "",
            f"- All live authority flags false: {proof['all_live_authority_flags_false']}",
            f"- External authority false in modeled boundaries: {proof['all_external_authority_flags_false_in_boundaries']}",
            f"- Raw private bodies included: {proof['raw_private_bodies_included']}",
            f"- Raw sensitive fixture values included: {proof['raw_sensitive_fixture_values_included']}",
            f"- Content hash: `{proof['content_hash']}`",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "schema_version": payload["schema_version"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "handoff_count": len(payload["handoffs_by_id"]),
        "routing_rule_count": len(payload["routing_rules_by_id"]),
        "builder_blocker_count": len(payload["builder_blockers_by_id"]),
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "all_external_authority_flags_false_in_boundaries": payload["machine_proof"][
            "all_external_authority_flags_false_in_boundaries"
        ],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Directory for generated read-models.")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--no-write", action="store_true", help="Build output without writing generated files.")
    args = parser.parse_args(argv)

    payload = build_cross_surface_artifact_handoff_registry_contract()
    json_path: Path | None = None
    operator_path: Path | None = None
    if not args.no_write:
        json_path, operator_path = write_exports(payload, Path(args.export_root))

    if args.format == "json":
        sys.stdout.write(stable_json(payload))
    elif args.format == "operator":
        sys.stdout.write(format_operator_markdown(payload))
    else:
        sys.stdout.write(stable_json(build_summary(payload, json_path, operator_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
