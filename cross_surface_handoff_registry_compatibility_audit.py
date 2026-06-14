"""Cross-Surface Handoff Registry Compatibility Audit for Capital Hilton bridges.

This deterministic audit maps the existing Capital Hilton Mac/PC capture,
readback, artifact, and shuttle package rails against the Cross-Surface
Artifact Handoff Registry v0. It is read-model only: no live registry migration,
auto-patching, watcher, runtime queue, Mac import, external action, or backend
state mutation occurs here.
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
SHUTTLE_ROOT = Path("/mnt/e/openclaw/shuttle/to_mac")

SCHEMA_VERSION = "cross_surface_handoff_registry_compatibility_audit_v0"
READ_MODEL_ID = "cross_surface_handoff_registry_compatibility_audit"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_METADATA_ONLY_COMPATIBILITY_AUDIT"

COMPATIBILITY_STATUSES = (
    "REGISTRY_READY",
    "MOSTLY_COMPATIBLE",
    "NEEDS_METADATA_PATCH",
    "NEEDS_HANDLER_MAPPING",
    "NEEDS_PRIVACY_BOUNDARY",
    "BESPOKE_BUT_SAFE",
    "DO_NOT_MIGRATE_YET",
    "UNKNOWN_REVIEW_REQUIRED",
)

SOURCE_KINDS = (
    "CAPTURE_REQUEST_INTAKE",
    "DELIVERY_FACTS_INTAKE",
    "SHUTTLE_PACKAGE",
    "READBACK_PACKAGE",
    "OUTBOX_CONTRACT_MARKER",
    "ARTIFACT_GENERATOR",
    "OPERATOR_MARKDOWN",
    "UNKNOWN",
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

GAP_SEVERITIES = (
    "INFO",
    "SHOULD_PATCH",
    "MUST_PATCH_BEFORE_MIGRATION",
    "BLOCKS_SAFE_MIGRATION",
    "DO_NOT_PATCH_NOW",
)

MIGRATION_TYPES = (
    "ADD_METADATA_ONLY",
    "ADD_LIFECYCLE_STATUS",
    "ADD_SCHEMA_REF",
    "ADD_REPLY_ROUTE",
    "ADD_PRIVACY_BOUNDARY",
    "ADD_ELIOPERATOR_MESSAGE",
    "ADD_TARGET_HANDLER_MAPPING",
    "LEAVE_AS_BESPOKE_FOR_NOW",
    "DO_NOT_MIGRATE_YET",
)

REQUIRED_REGISTRY_FIELDS = (
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

REQUIRED_AUDIT_FIELDS = (
    "audit_id",
    "registry_contract_ref",
    "audited_at_policy",
    "audited_packages",
    "audited_intake_contracts",
    "audited_readbacks",
    "compatibility_results",
    "migration_candidates",
    "do_not_migrate_items",
    "missing_common_fields",
    "safety_findings",
    "next_safe_move",
)

REQUIRED_RECORD_FIELDS = (
    "record_id",
    "source_name",
    "source_kind",
    "source_path_or_ref",
    "current_role",
    "maps_to_artifact_type",
    "maps_to_schema_ref",
    "maps_to_workflow_session_ref",
    "maps_to_world_ref",
    "maps_to_lane_ref",
    "maps_to_block_id",
    "maps_to_operation",
    "maps_to_origin_surface",
    "maps_to_target_handler",
    "maps_to_reply_surface",
    "maps_to_lifecycle_state",
    "maps_to_authority_boundary",
    "maps_to_privacy_boundary",
    "idempotency_present",
    "payload_hash_present",
    "safe_display_summary_present",
    "elioperator_message_present",
    "compatibility_status",
    "missing_fields",
    "safe_to_patch_now",
    "migration_risk",
    "recommended_action",
    "next_safe_move",
)

REQUIRED_LIFECYCLE_MAPPING_FIELDS = (
    "mapping_id",
    "source_record_ref",
    "current_status_field",
    "current_status_value",
    "registry_lifecycle_state",
    "operator_visible_translation",
    "below_deck_translation",
    "confidence",
    "next_safe_move",
)

REQUIRED_GAP_FIELDS = (
    "gap_id",
    "source_record_ref",
    "missing_field",
    "severity",
    "why_it_matters",
    "safe_patch_strategy",
    "blocks_registry_migration",
    "elioperator_warning",
    "next_safe_move",
)

REQUIRED_MIGRATION_CANDIDATE_FIELDS = (
    "candidate_id",
    "source_record_ref",
    "migration_type",
    "migration_status",
    "proposed_patch",
    "expected_benefit",
    "risk_level",
    "safe_to_do_now",
    "requires_tests",
    "requires_mac_change",
    "requires_backend_handler_change",
    "next_safe_move",
)

REQUIRED_PLAN_FIELDS = (
    "plan_id",
    "phase_0_inventory",
    "phase_1_metadata_alignment",
    "phase_2_lifecycle_readbacks",
    "phase_3_handler_mapping",
    "phase_4_optional_runtime_later",
    "explicit_non_goals",
    "rollback_policy",
    "next_safe_move",
)

REQUIRED_ELIOPERATOR_FIELDS = (
    "report_id",
    "plain_summary",
    "what_already_works",
    "what_is_still_bespoke",
    "what_should_be_patched_later",
    "what_not_to_touch",
    "operator_impact",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_registry_migration_allowed": False,
    "live_auto_patch_allowed": False,
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
    "backend_state_mutation_allowed": False,
}

PACKAGE_NAMES = (
    "mission_control_capture_intake_20260524",
    "mission_control_capture_readback_593fdd2_20260524",
    "capital_hilton_delivery_facts_readback_a868125_20260524",
    "capital_hilton_delivery_facts_capture_intake_a868125_20260524",
    "capital_hilton_po_coupa_delivery_facts_readback_d247cd5_20260524",
)

RELATIONSHIP_REF_PATHS = {
    "cross_surface_artifact_handoff_registry_contract": (
        "generated/read_models/cross_surface_artifact_handoff_registry_contract.json"
    ),
    "mission_control_capture_request_intake": "generated/read_models/mission_control_capture_request_intake.json",
    "capital_hilton_delivery_facts_capture_writer": (
        "generated/read_models/capital_hilton_delivery_facts_capture_writer.json"
    ),
    "capital_hilton_delivery_facts_capture_bridge": (
        "generated/read_models/capital_hilton_delivery_facts_capture_bridge.json"
    ),
    "capital_hilton_invoice_artifact_generator": (
        "generated/read_models/capital_hilton_invoice_artifact_generator.json"
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
    "bridge_routing_operator_attention_contract": (
        "generated/read_models/bridge_routing_operator_attention_contract.json"
    ),
}


@dataclass(frozen=True)
class HandoffCompatibilityAudit:
    audit_id: str
    registry_contract_ref: str
    audited_at_policy: str
    audited_packages: tuple[str, ...]
    audited_intake_contracts: tuple[str, ...]
    audited_readbacks: tuple[str, ...]
    compatibility_results: tuple[str, ...]
    migration_candidates: tuple[str, ...]
    do_not_migrate_items: tuple[str, ...]
    missing_common_fields: tuple[str, ...]
    safety_findings: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class HandoffBridgeCompatibilityRecord:
    record_id: str
    source_name: str
    source_kind: str
    source_path_or_ref: str
    current_role: str
    maps_to_artifact_type: str
    maps_to_schema_ref: str
    maps_to_workflow_session_ref: str
    maps_to_world_ref: str
    maps_to_lane_ref: str
    maps_to_block_id: str
    maps_to_operation: str
    maps_to_origin_surface: str
    maps_to_target_handler: str
    maps_to_reply_surface: str
    maps_to_lifecycle_state: str
    maps_to_authority_boundary: str
    maps_to_privacy_boundary: str
    idempotency_present: bool
    payload_hash_present: bool
    safe_display_summary_present: bool
    elioperator_message_present: bool
    compatibility_status: str
    missing_fields: tuple[str, ...]
    safe_to_patch_now: bool
    migration_risk: str
    recommended_action: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffLifecycleMapping:
    mapping_id: str
    source_record_ref: str
    current_status_field: str
    current_status_value: str
    registry_lifecycle_state: str
    operator_visible_translation: str
    below_deck_translation: str
    confidence: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffMetadataGap:
    gap_id: str
    source_record_ref: str
    missing_field: str
    severity: str
    why_it_matters: str
    safe_patch_strategy: str
    blocks_registry_migration: bool
    elioperator_warning: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffMigrationCandidate:
    candidate_id: str
    source_record_ref: str
    migration_type: str
    migration_status: str
    proposed_patch: str
    expected_benefit: str
    risk_level: str
    safe_to_do_now: bool
    requires_tests: bool
    requires_mac_change: bool
    requires_backend_handler_change: bool
    next_safe_move: str


@dataclass(frozen=True)
class HandoffNoBigBangMigrationPlan:
    plan_id: str
    phase_0_inventory: str
    phase_1_metadata_alignment: str
    phase_2_lifecycle_readbacks: str
    phase_3_handler_mapping: str
    phase_4_optional_runtime_later: str
    explicit_non_goals: tuple[str, ...]
    rollback_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffCompatibilityElioperatorReport:
    report_id: str
    plain_summary: str
    what_already_works: tuple[str, ...]
    what_is_still_bespoke: tuple[str, ...]
    what_should_be_patched_later: tuple[str, ...]
    what_not_to_touch: tuple[str, ...]
    operator_impact: str
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


def _read_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _package_manifest_summary(package_name: str) -> dict[str, Any]:
    package_root = SHUTTLE_ROOT / package_name
    manifest = _read_json_if_present(package_root / "shuttle_manifest.json")
    if manifest is None:
        return {
            "package_name": package_name,
            "present": False,
            "manifest_present": False,
            "raw_private_bodies_included": False,
            "network_authority": False,
            "runtime_authority": False,
            "model_execution_allowed": False,
            "agent_activation_allowed": False,
            "tool_execution_allowed": False,
            "truth_promotion_allowed": False,
            "metadata_only_inspected": True,
        }
    return {
        "package_name": package_name,
        "present": True,
        "manifest_present": True,
        "package_id": manifest.get("package_id"),
        "package_purpose": manifest.get("package_purpose"),
        "file_count": manifest.get("file_count"),
        "has_approved_outbox_contracts": bool(manifest.get("approved_outbox_contracts")),
        "has_delivery_facts_capture_outbox_contract": bool(manifest.get("delivery_facts_capture_outbox_contract")),
        "has_future_post_office_metadata": "future_post_office_metadata" in manifest,
        "future_post_office_metadata_present_fields": (
            manifest.get("future_post_office_metadata", {}).get("present", [])
        ),
        "future_post_office_metadata_missing_fields": (
            manifest.get("future_post_office_metadata", {}).get("missing", [])
        ),
        "has_readback_values": "readback_values" in manifest,
        "raw_private_bodies_included": manifest.get("raw_private_bodies_included", False),
        "network_authority": manifest.get("network_authority", False),
        "runtime_authority": manifest.get("runtime_authority", False),
        "model_execution_allowed": manifest.get("model_execution_allowed", False),
        "agent_activation_allowed": manifest.get("agent_activation_allowed", False),
        "tool_execution_allowed": manifest.get("tool_execution_allowed", False),
        "truth_promotion_allowed": manifest.get("truth_promotion_allowed", False),
        "metadata_only_inspected": True,
    }


def _package_summaries() -> dict[str, dict[str, Any]]:
    return {name: _package_manifest_summary(name) for name in PACKAGE_NAMES}


def _records() -> tuple[HandoffBridgeCompatibilityRecord, ...]:
    return (
        HandoffBridgeCompatibilityRecord(
            record_id="record_performance_dates_capture_intake",
            source_name="Mission Control capture request intake",
            source_kind="CAPTURE_REQUEST_INTAKE",
            source_path_or_ref="mission_control_capture_request_intake.py",
            current_role="Consumes visual-agnostic Performance Dates and Rate capture requests into local SQLite.",
            maps_to_artifact_type="CAPTURE_REQUEST",
            maps_to_schema_ref="mission_control_capture_request_intake.MissionControlBlockCaptureRequest",
            maps_to_workflow_session_ref="capital_hilton_invoice_workflow_session",
            maps_to_world_ref="finance",
            maps_to_lane_ref="capital_hilton_invoice",
            maps_to_block_id="performance_dates",
            maps_to_operation="add_dates",
            maps_to_origin_surface="Mission Control Mac",
            maps_to_target_handler="mission_control_capture_request_intake",
            maps_to_reply_surface="Mission Control Mac",
            maps_to_lifecycle_state="WRITTEN",
            maps_to_authority_boundary="local_sqlite_capture_write_allowed_for_enabled_adapters",
            maps_to_privacy_boundary="non_sensitive_operational",
            idempotency_present=True,
            payload_hash_present=True,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="MOSTLY_COMPATIBLE",
            missing_fields=("artifact_id", "artifact_type", "schema_version", "assigned_role"),
            safe_to_patch_now=True,
            migration_risk="low",
            recommended_action="Add post-office envelope metadata while leaving the existing intake path unchanged.",
            next_safe_move="Metadata-only alignment patch after audit review.",
        ),
        HandoffBridgeCompatibilityRecord(
            record_id="record_performance_dates_readback_package",
            source_name="Mission Control capture readback package 593fdd2",
            source_kind="READBACK_PACKAGE",
            source_path_or_ref="shuttle/to_mac/mission_control_capture_readback_593fdd2_20260524",
            current_role="Mac-bound package for Mission Control to render captured Performance Dates closeout.",
            maps_to_artifact_type="CAPTURE_READBACK",
            maps_to_schema_ref="mission_control_capture_request_intake.MissionControlCaptureIntakeReadback",
            maps_to_workflow_session_ref="capital_hilton_invoice_workflow_session",
            maps_to_world_ref="finance",
            maps_to_lane_ref="capital_hilton_invoice",
            maps_to_block_id="performance_dates",
            maps_to_operation="add_dates",
            maps_to_origin_surface="Repo A backend",
            maps_to_target_handler="mission_control_capture_readback_renderer",
            maps_to_reply_surface="Mission Control Mac",
            maps_to_lifecycle_state="READBACK_READY",
            maps_to_authority_boundary="read_model_shuttle_no_runtime_authority",
            maps_to_privacy_boundary="non_sensitive_operational",
            idempotency_present=True,
            payload_hash_present=True,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="NEEDS_METADATA_PATCH",
            missing_fields=("artifact_type", "schema_ref", "lifecycle_state", "target_handler", "reply_to_channel"),
            safe_to_patch_now=True,
            migration_risk="low",
            recommended_action="Add future_post_office_metadata to manifest; do not change package copy/import behavior.",
            next_safe_move="Patch only manifests/read-model metadata in a later lane.",
        ),
        HandoffBridgeCompatibilityRecord(
            record_id="record_delivery_facts_capture_writer",
            source_name="Capital Hilton delivery facts capture writer",
            source_kind="DELIVERY_FACTS_INTAKE",
            source_path_or_ref="capital_hilton_delivery_facts_capture_writer.py",
            current_role="Consumes PO/Coupa, AP route, and protected-evidence posture capture requests into local SQLite.",
            maps_to_artifact_type="CAPTURE_REQUEST",
            maps_to_schema_ref="capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureRequest",
            maps_to_workflow_session_ref="capital_hilton_invoice_workflow_session",
            maps_to_world_ref="finance",
            maps_to_lane_ref="capital_hilton_invoice",
            maps_to_block_id="proof_po_reference",
            maps_to_operation="set_needs_discovery",
            maps_to_origin_surface="Mission Control Mac",
            maps_to_target_handler="capital_hilton_delivery_facts_capture_writer",
            maps_to_reply_surface="Mission Control Mac",
            maps_to_lifecycle_state="WRITTEN",
            maps_to_authority_boundary="local_delivery_fact_write_allowed_for_enabled_adapters",
            maps_to_privacy_boundary="protected_payment_reference_posture_metadata_only",
            idempotency_present=True,
            payload_hash_present=True,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="MOSTLY_COMPATIBLE",
            missing_fields=("artifact_id", "artifact_type", "schema_version", "reply_to_channel"),
            safe_to_patch_now=True,
            migration_risk="low",
            recommended_action="Wrap request/readback with registry envelope fields; keep writer adapters lane-specific.",
            next_safe_move="Metadata-only envelope patch when Mac contract is ready to render it.",
        ),
        HandoffBridgeCompatibilityRecord(
            record_id="record_delivery_facts_capture_intake_package",
            source_name="Delivery facts capture intake/outbox package a868125",
            source_kind="OUTBOX_CONTRACT_MARKER",
            source_path_or_ref="shuttle/to_mac/capital_hilton_delivery_facts_capture_intake_a868125_20260524",
            current_role="Tells Mission Control which delivery-fact capture requests may be emitted and where.",
            maps_to_artifact_type="CAPTURE_REQUEST",
            maps_to_schema_ref="capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureRequest",
            maps_to_workflow_session_ref="capital_hilton_invoice_workflow_session",
            maps_to_world_ref="finance",
            maps_to_lane_ref="capital_hilton_invoice",
            maps_to_block_id="proof_po_reference",
            maps_to_operation="set_needs_discovery",
            maps_to_origin_surface="Mission Control Mac",
            maps_to_target_handler="capital_hilton_delivery_facts_capture_writer",
            maps_to_reply_surface="Mission Control Mac",
            maps_to_lifecycle_state="CREATED",
            maps_to_authority_boundary="bounded_outbox_no_backend_execution",
            maps_to_privacy_boundary="protected_metadata_only_no_raw_body",
            idempotency_present=False,
            payload_hash_present=False,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="NEEDS_METADATA_PATCH",
            missing_fields=("artifact_id", "artifact_type", "payload_hash", "idempotency_key", "lifecycle_state"),
            safe_to_patch_now=True,
            migration_risk="low",
            recommended_action="Add registry field checklist to outbox marker; do not broaden allowed blocks.",
            next_safe_move="Patch marker metadata only; Mac still writes bounded JSON to the same outbox.",
        ),
        HandoffBridgeCompatibilityRecord(
            record_id="record_po_coupa_readback_package",
            source_name="PO/Coupa delivery facts readback package d247cd5",
            source_kind="READBACK_PACKAGE",
            source_path_or_ref="shuttle/to_mac/capital_hilton_po_coupa_delivery_facts_readback_d247cd5_20260524",
            current_role="Mac-bound package showing PO/Coupa posture locally captured as NEEDS_DISCOVERY.",
            maps_to_artifact_type="CAPTURE_READBACK",
            maps_to_schema_ref="capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureReadback",
            maps_to_workflow_session_ref="capital_hilton_invoice_workflow_session",
            maps_to_world_ref="finance",
            maps_to_lane_ref="capital_hilton_invoice",
            maps_to_block_id="proof_po_reference",
            maps_to_operation="set_needs_discovery",
            maps_to_origin_surface="Repo A backend",
            maps_to_target_handler="capital_hilton_delivery_facts_readback_renderer",
            maps_to_reply_surface="Mission Control Mac",
            maps_to_lifecycle_state="READBACK_READY",
            maps_to_authority_boundary="read_model_shuttle_external_authority_false",
            maps_to_privacy_boundary="protected_payment_reference_posture_metadata_only",
            idempotency_present=True,
            payload_hash_present=True,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="REGISTRY_READY",
            missing_fields=("registry_contract_ref",),
            safe_to_patch_now=True,
            migration_risk="very_low",
            recommended_action="Replace old missing registry placeholder with cross_surface_artifact_handoff_registry_contract ref.",
            next_safe_move="Use this as the template for future readback manifests.",
        ),
        HandoffBridgeCompatibilityRecord(
            record_id="record_invoice_artifact_preview",
            source_name="Capital Hilton invoice artifact generator",
            source_kind="ARTIFACT_GENERATOR",
            source_path_or_ref="capital_hilton_invoice_artifact_generator.py",
            current_role="Produces deterministic local invoice preview with real path and hash.",
            maps_to_artifact_type="INVOICE_ARTIFACT_PREVIEW",
            maps_to_schema_ref="capital_hilton_invoice_artifact_generator.CapitalHiltonInvoiceArtifactReadback",
            maps_to_workflow_session_ref="capital_hilton_invoice_workflow_session",
            maps_to_world_ref="finance",
            maps_to_lane_ref="capital_hilton_invoice",
            maps_to_block_id="invoice_packet",
            maps_to_operation="generate_local_preview",
            maps_to_origin_surface="Repo A backend",
            maps_to_target_handler="future_invoice_artifact_preview_renderer",
            maps_to_reply_surface="Mission Control Mac",
            maps_to_lifecycle_state="READBACK_READY",
            maps_to_authority_boundary="local_deterministic_artifact_preview_allowed_external_false",
            maps_to_privacy_boundary="operational_invoice_preview_no_private_remit_data",
            idempotency_present=False,
            payload_hash_present=True,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="MOSTLY_COMPATIBLE",
            missing_fields=("artifact_id", "idempotency_key", "target_handler", "reply_to_channel"),
            safe_to_patch_now=True,
            migration_risk="low",
            recommended_action="Add post-office artifact envelope and stable idempotency key for preview readback.",
            next_safe_move="Patch generated read-model metadata only; do not regenerate/send invoice.",
        ),
        HandoffBridgeCompatibilityRecord(
            record_id="record_reusable_fact_registry",
            source_name="Cross-lane reusable block registry contract",
            source_kind="UNKNOWN",
            source_path_or_ref="cross_lane_reusable_block_registry_contract.py",
            current_role="Defines future tokenized reusable facts and protected value rules.",
            maps_to_artifact_type="REUSABLE_FACT",
            maps_to_schema_ref="cross_lane_reusable_block_registry_contract.CrossLaneReusableFactBlock",
            maps_to_workflow_session_ref="requires_target_workflow_session_ref",
            maps_to_world_ref="any",
            maps_to_lane_ref="any",
            maps_to_block_id="compatible_reusable_fact_block",
            maps_to_operation="suggest_reuse_or_inform_only",
            maps_to_origin_surface="Repo A backend",
            maps_to_target_handler="future_reusable_block_intake_handler",
            maps_to_reply_surface="origin_surface",
            maps_to_lifecycle_state="CREATED",
            maps_to_authority_boundary="no_live_auto_apply_no_de_tokenization",
            maps_to_privacy_boundary="tokenized_refs_only_raw_values_forbidden",
            idempotency_present=True,
            payload_hash_present=True,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="DO_NOT_MIGRATE_YET",
            missing_fields=("live_handler",),
            safe_to_patch_now=False,
            migration_risk="medium",
            recommended_action="Keep as compatibility contract until a protected reusable-fact handler exists.",
            next_safe_move="Do not implement live auto-apply or de-tokenization.",
        ),
        HandoffBridgeCompatibilityRecord(
            record_id="record_telegram_cassandra_future_entry",
            source_name="Telegram/Cassandra future entry",
            source_kind="UNKNOWN",
            source_path_or_ref="future_entry_surface_only",
            current_role="Future fronting surface that should normalize into the same workflow/session/block grammar.",
            maps_to_artifact_type="CAPTURE_REQUEST",
            maps_to_schema_ref="target_block_specific_capture_request_schema",
            maps_to_workflow_session_ref="required_before_capture",
            maps_to_world_ref="target_world_required",
            maps_to_lane_ref="target_lane_required",
            maps_to_block_id="target_block_required",
            maps_to_operation="target_operation_required",
            maps_to_origin_surface="Telegram",
            maps_to_target_handler="same_backend_handler_as_Mission_Control_for_same_block",
            maps_to_reply_surface="Telegram",
            maps_to_lifecycle_state="CREATED",
            maps_to_authority_boundary="no_live_telegram_integration",
            maps_to_privacy_boundary="tokenized_or_safe_summary_only",
            idempotency_present=False,
            payload_hash_present=False,
            safe_display_summary_present=True,
            elioperator_message_present=True,
            compatibility_status="DO_NOT_MIGRATE_YET",
            missing_fields=("workflow_session_ref", "idempotency_key", "payload_hash", "approved_surface_handler"),
            safe_to_patch_now=False,
            migration_risk="medium",
            recommended_action="Do not build live Telegram; preserve required addressed_actor/fronting_agent/assigned_role fields.",
            next_safe_move="Use only as compatibility requirement for future packet compiler/handoff rails.",
        ),
    )


def _lifecycle_mappings() -> tuple[HandoffLifecycleMapping, ...]:
    return (
        HandoffLifecycleMapping(
            mapping_id="lifecycle_performance_dates_sqlite_written",
            source_record_ref="record_performance_dates_capture_intake",
            current_status_field="write_status",
            current_status_value="WRITTEN_TO_LOCAL_SQLITE or DUPLICATE_NOOP",
            registry_lifecycle_state="WRITTEN",
            operator_visible_translation="OpenClaw saved the local state or already had the exact capture.",
            below_deck_translation="SQLite receipt/state writer idempotency path.",
            confidence="high",
            next_safe_move="Represent duplicate replay as DUPLICATE_NOOP in post-office lifecycle.",
        ),
        HandoffLifecycleMapping(
            mapping_id="lifecycle_capture_readback_package_ready",
            source_record_ref="record_performance_dates_readback_package",
            current_status_field="package purpose",
            current_status_value="Mac-bound capture readback package staged",
            registry_lifecycle_state="READBACK_READY",
            operator_visible_translation="Backend readback is ready for Mission Control to render.",
            below_deck_translation="Package manifest/file hash verification remains a shuttle detail.",
            confidence="medium",
            next_safe_move="Add explicit lifecycle_state to manifest later.",
        ),
        HandoffLifecycleMapping(
            mapping_id="lifecycle_delivery_facts_duplicate_noop",
            source_record_ref="record_po_coupa_readback_package",
            current_status_field="duplicate_retry",
            current_status_value="DUPLICATE_NOOP",
            registry_lifecycle_state="DUPLICATE_NOOP",
            operator_visible_translation="OpenClaw already had this exact PO/Coupa posture.",
            below_deck_translation="Idempotency key matched existing local state.",
            confidence="high",
            next_safe_move="Keep duplicate readback explicit; do not write a second receipt.",
        ),
        HandoffLifecycleMapping(
            mapping_id="lifecycle_invoice_artifact_preview_ready",
            source_record_ref="record_invoice_artifact_preview",
            current_status_field="artifact_status",
            current_status_value="GENERATED_LOCAL_PREVIEW",
            registry_lifecycle_state="READBACK_READY",
            operator_visible_translation="A local preview artifact exists with a real hash.",
            below_deck_translation="Artifact exists locally; delivery gates remain separate.",
            confidence="high",
            next_safe_move="Add post-office artifact envelope without changing artifact generation.",
        ),
    )


def _gaps() -> tuple[HandoffMetadataGap, ...]:
    return (
        HandoffMetadataGap(
            gap_id="gap_capture_intake_artifact_envelope",
            source_record_ref="record_performance_dates_capture_intake",
            missing_field="artifact_id/artifact_type/schema_version",
            severity="SHOULD_PATCH",
            why_it_matters="The handler works, but the generic post office cannot classify it without envelope fields.",
            safe_patch_strategy="Add metadata fields to request/readback fixtures while preserving existing accepted keys.",
            blocks_registry_migration=False,
            elioperator_warning="ELIOPERATOR: The bridge works; this is a label/metadata gap, not a broken capture path.",
            next_safe_move="Patch metadata only after audit.",
        ),
        HandoffMetadataGap(
            gap_id="gap_early_readback_package_lifecycle",
            source_record_ref="record_performance_dates_readback_package",
            missing_field="lifecycle_state",
            severity="SHOULD_PATCH",
            why_it_matters="Mission Control readback packages are safe, but lifecycle is inferred from package purpose.",
            safe_patch_strategy="Add lifecycle_state=READBACK_READY and target_handler metadata to package manifests.",
            blocks_registry_migration=False,
            elioperator_warning="ELIOPERATOR: Add a clear status label; do not change the shuttle behavior.",
            next_safe_move="Use PO/Coupa readback package as template.",
        ),
        HandoffMetadataGap(
            gap_id="gap_outbox_contract_payload_hash_idempotency",
            source_record_ref="record_delivery_facts_capture_intake_package",
            missing_field="payload_hash/idempotency_key",
            severity="MUST_PATCH_BEFORE_MIGRATION",
            why_it_matters="A post-office-created capture request needs deterministic duplicate protection.",
            safe_patch_strategy="Specify idempotency/hash basis in marker without changing Mac write path.",
            blocks_registry_migration=True,
            elioperator_warning="ELIOPERATOR: Future generic handoffs need duplicate protection before any write.",
            next_safe_move="Patch marker contract only; do not auto-consume.",
        ),
        HandoffMetadataGap(
            gap_id="gap_invoice_artifact_idempotency_key",
            source_record_ref="record_invoice_artifact_preview",
            missing_field="idempotency_key",
            severity="SHOULD_PATCH",
            why_it_matters="The preview has a real hash, but the registry should also know the stable handoff identity.",
            safe_patch_strategy="Add artifact handoff idempotency key derived from session/artifact type/path/hash.",
            blocks_registry_migration=False,
            elioperator_warning="ELIOPERATOR: Hash proves the file; idempotency labels the handoff.",
            next_safe_move="Patch read-model metadata only.",
        ),
        HandoffMetadataGap(
            gap_id="gap_reusable_fact_live_handler_absent",
            source_record_ref="record_reusable_fact_registry",
            missing_field="live_handler",
            severity="DO_NOT_PATCH_NOW",
            why_it_matters="Reusable facts need privacy-protected handler work before live routing.",
            safe_patch_strategy="Leave as contract/read-model until protected handler exists.",
            blocks_registry_migration=True,
            elioperator_warning="ELIOPERATOR: Tokenized facts are not permission to auto-apply or reveal values.",
            next_safe_move="Do not migrate yet.",
        ),
        HandoffMetadataGap(
            gap_id="gap_telegram_live_surface_absent",
            source_record_ref="record_telegram_cassandra_future_entry",
            missing_field="approved_surface_handler",
            severity="DO_NOT_PATCH_NOW",
            why_it_matters="Telegram/Cassandra is a future entry surface, not a live integration.",
            safe_patch_strategy="Preserve addressed_actor/fronting_agent/assigned_role fields for future use.",
            blocks_registry_migration=True,
            elioperator_warning="ELIOPERATOR: Future Telegram compatibility is metadata, not a live channel.",
            next_safe_move="Do not build Telegram in this lane.",
        ),
    )


def _migration_candidates() -> tuple[HandoffMigrationCandidate, ...]:
    return (
        HandoffMigrationCandidate(
            candidate_id="candidate_add_post_office_metadata_to_performance_dates_intake",
            source_record_ref="record_performance_dates_capture_intake",
            migration_type="ADD_METADATA_ONLY",
            migration_status="candidate_not_applied",
            proposed_patch="Add artifact_type/schema_ref/schema_version/origin/target/reply metadata to fixtures and read-model.",
            expected_benefit="Performance Dates capture can be shown as a post-office handoff without changing the writer.",
            risk_level="low",
            safe_to_do_now=True,
            requires_tests=True,
            requires_mac_change=False,
            requires_backend_handler_change=False,
            next_safe_move="Apply in a metadata-only alignment lane.",
        ),
        HandoffMigrationCandidate(
            candidate_id="candidate_add_lifecycle_to_readback_manifests",
            source_record_ref="record_performance_dates_readback_package",
            migration_type="ADD_LIFECYCLE_STATUS",
            migration_status="candidate_not_applied",
            proposed_patch="Add lifecycle_state=READBACK_READY plus target_handler/reply_to_channel to package manifests.",
            expected_benefit="Mac/PC packages can be compared using generic lifecycle terms.",
            risk_level="low",
            safe_to_do_now=True,
            requires_tests=True,
            requires_mac_change=False,
            requires_backend_handler_change=False,
            next_safe_move="Patch future packages first; do not rewrite old packages.",
        ),
        HandoffMigrationCandidate(
            candidate_id="candidate_patch_po_coupa_readback_registry_ref",
            source_record_ref="record_po_coupa_readback_package",
            migration_type="ADD_SCHEMA_REF",
            migration_status="candidate_not_applied",
            proposed_patch="Replace missing registry placeholder with cross_surface_artifact_handoff_registry_contract_v0 ref.",
            expected_benefit="Newest readback package becomes fully registry-ready.",
            risk_level="very_low",
            safe_to_do_now=True,
            requires_tests=True,
            requires_mac_change=False,
            requires_backend_handler_change=False,
            next_safe_move="Use as first alignment patch if desired.",
        ),
        HandoffMigrationCandidate(
            candidate_id="candidate_add_invoice_artifact_envelope",
            source_record_ref="record_invoice_artifact_preview",
            migration_type="ADD_METADATA_ONLY",
            migration_status="candidate_not_applied",
            proposed_patch="Add INVOICE_ARTIFACT_PREVIEW handoff envelope, target renderer, reply route, and idempotency key.",
            expected_benefit="Artifact previews can travel through the same post-office vocabulary as captures/readbacks.",
            risk_level="low",
            safe_to_do_now=True,
            requires_tests=True,
            requires_mac_change=False,
            requires_backend_handler_change=False,
            next_safe_move="Patch metadata only; do not regenerate or send artifact.",
        ),
        HandoffMigrationCandidate(
            candidate_id="candidate_leave_reusable_fact_bespoke_for_now",
            source_record_ref="record_reusable_fact_registry",
            migration_type="DO_NOT_MIGRATE_YET",
            migration_status="blocked_until_protected_handler_exists",
            proposed_patch="None in this lane.",
            expected_benefit="Avoids accidental live reusable-fact auto-apply or protected value reveal.",
            risk_level="medium",
            safe_to_do_now=False,
            requires_tests=True,
            requires_mac_change=False,
            requires_backend_handler_change=True,
            next_safe_move="Review after protected local handler design.",
        ),
    )


def _plan() -> HandoffNoBigBangMigrationPlan:
    return HandoffNoBigBangMigrationPlan(
        plan_id="capital_hilton_post_office_no_big_bang_plan_v0",
        phase_0_inventory="Keep current rails intact; inventory intakes, readbacks, package manifests, and artifact previews.",
        phase_1_metadata_alignment=(
            "Add artifact_type/schema_ref/lifecycle/target_handler/reply route metadata to future read-models and manifests."
        ),
        phase_2_lifecycle_readbacks=(
            "Normalize WRITTEN, DUPLICATE_NOOP, READBACK_READY, RENDERED, BLOCKED, and REJECTED labels in readback outputs."
        ),
        phase_3_handler_mapping=(
            "Map existing handlers into the registry one by one, starting with Performance Dates and PO/Coupa posture."
        ),
        phase_4_optional_runtime_later=(
            "Only after audits and tests, consider a gated runtime; this audit does not create one."
        ),
        explicit_non_goals=(
            "no file watcher",
            "no daemon",
            "no auto-import",
            "no live runtime queue",
            "no Telegram live integration",
            "no automatic agent dispatch",
            "no external actions",
            "no big-bang replacement",
        ),
        rollback_policy="Metadata-only changes can be ignored by existing rails; old bespoke packages remain valid fallback.",
        next_safe_move="Patch future manifests/read-models first; never replace the working capture/readback path in one step.",
    )


def _elioperator_report() -> HandoffCompatibilityElioperatorReport:
    return HandoffCompatibilityElioperatorReport(
        report_id="capital_hilton_handoff_compatibility_elioperator_report_v0",
        plain_summary=(
            "The current Mac/PC handoff works, but each package still has custom instructions. "
            "The new post office contract can standardize labels and lifecycle without changing live behavior yet."
        ),
        what_already_works=(
            "Mission Control can emit bounded capture request JSON.",
            "Repo A can validate, write local SQLite receipt/state, and read back captured values.",
            "Mac-bound packages can render closeouts/readbacks without external authority.",
            "The PO/Coupa readback package already carries many future post-office metadata fields.",
        ),
        what_is_still_bespoke=(
            "Earlier packages infer lifecycle from package purpose instead of explicit lifecycle_state.",
            "Package manifests use custom outbox/readback vocabulary instead of a shared artifact envelope.",
            "Artifact preview readback has a real file hash but no generic handoff idempotency key.",
        ),
        what_should_be_patched_later=(
            "Add artifact_type, schema_ref, lifecycle_state, target_handler, reply route, privacy class, and role fields.",
            "Add idempotency/hash basis to outbox markers where the future generic handoff will create requests.",
            "Use the PO/Coupa readback manifest as the first template for registry-ready package metadata.",
        ),
        what_not_to_touch=(
            "Do not replace the working Mission Control capture intake.",
            "Do not rewrite shuttle copy/import behavior.",
            "Do not add a watcher, daemon, runtime queue, or auto-consume path.",
            "Do not build live Telegram/Cassandra integration in this migration.",
            "Do not route raw protected values through normal handoffs.",
        ),
        operator_impact=(
            "Winship keeps the working Capital Hilton steel thread while future packages become easier to reason about."
        ),
        next_safe_move="Run a small metadata-only alignment patch after review.",
    )


def _audit(records: tuple[HandoffBridgeCompatibilityRecord, ...]) -> HandoffCompatibilityAudit:
    status_counts = sorted({record.compatibility_status for record in records})
    return HandoffCompatibilityAudit(
        audit_id="capital_hilton_cross_surface_handoff_compatibility_audit_v0",
        registry_contract_ref="cross_surface_artifact_handoff_registry_contract_v0",
        audited_at_policy="deterministic export timestamp only; no live package mutation",
        audited_packages=PACKAGE_NAMES,
        audited_intake_contracts=(
            "mission_control_capture_request_intake",
            "capital_hilton_delivery_facts_capture_writer",
            "capital_hilton_delivery_facts_capture_bridge",
            "capital_hilton_invoice_artifact_generator",
            "cross_lane_reusable_block_registry_contract",
        ),
        audited_readbacks=(
            "mission_control_capture_request_intake closeout/readback",
            "capital_hilton_delivery_facts_capture_writer readbacks",
            "capital_hilton_invoice_artifact_generator artifact_readback",
            "Mac-bound shuttle package manifests",
        ),
        compatibility_results=tuple(status_counts),
        migration_candidates=tuple(candidate.candidate_id for candidate in _migration_candidates()),
        do_not_migrate_items=(
            "reusable fact live handler",
            "Telegram/Cassandra live integration",
            "runtime bus or watcher",
            "existing working capture/readback rails",
        ),
        missing_common_fields=(
            "artifact_id",
            "artifact_type",
            "schema_ref",
            "schema_version",
            "lifecycle_state",
            "target_handler",
            "reply_to_channel",
            "assigned_role",
            "privacy_class",
            "sensitivity_class",
        ),
        safety_findings=(
            "Existing packages keep external authority false.",
            "Existing capture rails are visual-agnostic enough to map.",
            "No raw protected bodies are needed for this audit.",
            "Do not migrate live reusable facts or Telegram yet.",
        ),
        next_safe_move="Perform metadata-only alignment; do not replace working rails.",
    )


def _model_schemas() -> dict[str, dict[str, Any]]:
    return {
        "handoff_compatibility_audit": {
            "model_name": "HandoffCompatibilityAudit",
            "required_fields": list(REQUIRED_AUDIT_FIELDS),
        },
        "handoff_bridge_compatibility_record": {
            "model_name": "HandoffBridgeCompatibilityRecord",
            "required_fields": list(REQUIRED_RECORD_FIELDS),
            "source_kinds": list(SOURCE_KINDS),
            "compatibility_statuses": list(COMPATIBILITY_STATUSES),
        },
        "handoff_lifecycle_mapping": {
            "model_name": "HandoffLifecycleMapping",
            "required_fields": list(REQUIRED_LIFECYCLE_MAPPING_FIELDS),
            "registry_lifecycle_states": list(LIFECYCLE_STATES),
        },
        "handoff_metadata_gap": {
            "model_name": "HandoffMetadataGap",
            "required_fields": list(REQUIRED_GAP_FIELDS),
            "severity_values": list(GAP_SEVERITIES),
        },
        "handoff_migration_candidate": {
            "model_name": "HandoffMigrationCandidate",
            "required_fields": list(REQUIRED_MIGRATION_CANDIDATE_FIELDS),
            "migration_types": list(MIGRATION_TYPES),
        },
        "handoff_no_big_bang_migration_plan": {
            "model_name": "HandoffNoBigBangMigrationPlan",
            "required_fields": list(REQUIRED_PLAN_FIELDS),
        },
        "handoff_compatibility_elioperator_report": {
            "model_name": "HandoffCompatibilityElioperatorReport",
            "required_fields": list(REQUIRED_ELIOPERATOR_FIELDS),
        },
    }


def build_cross_surface_handoff_registry_compatibility_audit(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    records = _records()
    lifecycle_mappings = _lifecycle_mappings()
    gaps = _gaps()
    candidates = _migration_candidates()
    plan = _plan()
    report = _elioperator_report()
    audit = _audit(records)
    package_summaries = _package_summaries()

    records_by_id = {record.record_id: asdict(record) for record in records}
    gaps_by_id = {gap.gap_id: asdict(gap) for gap in gaps}
    candidates_by_id = {candidate.candidate_id: asdict(candidate) for candidate in candidates}

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "purpose": (
            "Audit existing Capital Hilton Mac/PC bridge packages and capture/readback rails against "
            "the Cross-Surface Artifact Handoff Registry without migrating or rewriting them."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "required_registry_fields_checked": list(REQUIRED_REGISTRY_FIELDS),
        "model_schemas": _model_schemas(),
        "audit": asdict(audit),
        "compatibility_records_by_id": records_by_id,
        "lifecycle_mappings_by_id": {
            mapping.mapping_id: asdict(mapping) for mapping in lifecycle_mappings
        },
        "metadata_gaps_by_id": gaps_by_id,
        "migration_candidates_by_id": candidates_by_id,
        "no_big_bang_migration_plan": asdict(plan),
        "elioperator_report": asdict(report),
        "package_manifest_summaries": package_summaries,
        "relationship_inventory": _relationship_inventory(),
        "examples": {
            "performance_dates_capture_readback": "record_performance_dates_capture_intake",
            "po_coupa_delivery_facts_capture_readback": "record_po_coupa_readback_package",
            "delivery_facts_capture_intake_package": "record_delivery_facts_capture_intake_package",
            "invoice_artifact_preview": "record_invoice_artifact_preview",
            "reusable_fact_registry_compatibility": "record_reusable_fact_registry",
            "telegram_cassandra_future_entry": "record_telegram_cassandra_future_entry",
        },
        "security_privacy_rules": {
            "no_raw_pii_in_generated_read_models": True,
            "no_raw_protected_values_in_operator_markdown": True,
            "no_raw_package_payloads_with_private_bodies": True,
            "no_public_raw_hash_of_sensitive_values": True,
            "no_credential_token_cookie_private_key_material": True,
            "no_path_crawling_beyond_relevant_package_metadata": True,
            "no_mac_sync_import": True,
            "no_external_systems": True,
        },
    }

    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record.compatibility_status] = status_counts.get(record.compatibility_status, 0) + 1

    payload["machine_proof"] = {
        "handoff_compatibility_audit_model_present": True,
        "handoff_bridge_compatibility_record_model_present": True,
        "handoff_lifecycle_mapping_model_present": True,
        "handoff_metadata_gap_model_present": True,
        "handoff_migration_candidate_model_present": True,
        "handoff_no_big_bang_migration_plan_model_present": True,
        "handoff_compatibility_elioperator_report_model_present": True,
        "performance_dates_record_present": "record_performance_dates_capture_intake" in records_by_id,
        "po_coupa_record_present": "record_po_coupa_readback_package" in records_by_id,
        "invoice_artifact_preview_record_present": "record_invoice_artifact_preview" in records_by_id,
        "reusable_fact_record_present": "record_reusable_fact_registry" in records_by_id,
        "metadata_gap_records_present": bool(gaps_by_id),
        "migration_candidates_present": bool(candidates_by_id),
        "no_big_bang_plan_present": True,
        "elioperator_report_present": True,
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "no_migration_or_replacement_performed": True,
        "metadata_only_package_inspection": all(
            summary.get("metadata_only_inspected") is True for summary in package_summaries.values()
        ),
        "package_manifest_raw_private_bodies_false": all(
            summary.get("raw_private_bodies_included") is False for summary in package_summaries.values()
        ),
        "compatibility_status_counts": status_counts,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_sensitive_fixture_values_included": False,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["elioperator_report"]
    plan = payload["no_big_bang_migration_plan"]
    proof = payload["machine_proof"]
    return "\n".join(
        [
            "# Cross-Surface Handoff Registry Compatibility Audit",
            "",
            "## ELIOPERATOR",
            "",
            report["plain_summary"],
            "",
            "The audit says the Capital Hilton bridge is real and should not be ripped out. The practical move is "
            "metadata alignment: add post-office labels, lifecycle states, schema refs, reply routes, privacy classes, "
            "and idempotency/hash basis where missing.",
            "",
            "## What Already Works",
            "",
            "\n".join(f"- {item}" for item in report["what_already_works"]),
            "",
            "## Still Bespoke",
            "",
            "\n".join(f"- {item}" for item in report["what_is_still_bespoke"]),
            "",
            "## Patch Later",
            "",
            "\n".join(f"- {item}" for item in report["what_should_be_patched_later"]),
            "",
            "## Do Not Touch Yet",
            "",
            "\n".join(f"- {item}" for item in report["what_not_to_touch"]),
            "",
            "## No Big-Bang Plan",
            "",
            f"- Phase 0: {plan['phase_0_inventory']}",
            f"- Phase 1: {plan['phase_1_metadata_alignment']}",
            f"- Phase 2: {plan['phase_2_lifecycle_readbacks']}",
            f"- Phase 3: {plan['phase_3_handler_mapping']}",
            f"- Phase 4: {plan['phase_4_optional_runtime_later']}",
            "",
            "Explicit non-goals:",
            "\n".join(f"- {item}" for item in plan["explicit_non_goals"]),
            "",
            "## Machine Proof",
            "",
            f"- All live authority flags false: {proof['all_live_authority_flags_false']}",
            f"- No migration or replacement performed: {proof['no_migration_or_replacement_performed']}",
            f"- Metadata-only package inspection: {proof['metadata_only_package_inspection']}",
            f"- Raw private bodies included: {proof['raw_private_bodies_included']}",
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
        "audited_record_count": len(payload["compatibility_records_by_id"]),
        "metadata_gap_count": len(payload["metadata_gaps_by_id"]),
        "migration_candidate_count": len(payload["migration_candidates_by_id"]),
        "compatibility_status_counts": payload["machine_proof"]["compatibility_status_counts"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Directory for generated read-models.")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--no-write", action="store_true", help="Build output without writing generated files.")
    args = parser.parse_args(argv)

    payload = build_cross_surface_handoff_registry_compatibility_audit()
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
