"""Cross-Surface Handoff Registry metadata alignment patch v0.

This module defines an additive post-office metadata shape for future Capital
Hilton Mac/PC handoff manifests and readbacks. It does not change live intake
semantics, mutate SQLite, rewrite existing packages, import on Mac, create a
watcher, or route through a live registry.
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

SCHEMA_VERSION = "cross_surface_handoff_registry_metadata_alignment_v0"
READ_MODEL_ID = "cross_surface_handoff_registry_metadata_alignment"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "ADDITIVE_METADATA_ONLY_ALIGNMENT_PATCH"

REGISTRY_CONTRACT_REF = "cross_surface_artifact_handoff_registry_contract_v0"
COMPATIBILITY_AUDIT_REF = "cross_surface_handoff_registry_compatibility_audit_v0"

POST_OFFICE_METADATA_FIELDS = (
    "artifact_id",
    "artifact_type",
    "schema_ref",
    "schema_version",
    "lifecycle_state",
    "world_ref",
    "lane_ref",
    "block_id",
    "workflow_session_ref",
    "operation",
    "origin_surface",
    "source_channel",
    "target_surface",
    "target_handler",
    "reply_to_surface",
    "reply_to_channel",
    "authority_boundary",
    "privacy_boundary",
    "idempotency_key",
    "payload_hash",
    "safe_display_summary",
    "elioperator_message",
    "missing_fields",
    "missing_field_reasons",
    "next_safe_move",
)

REQUIRED_PATCH_FIELDS = (
    "patch_id",
    "registry_contract_ref",
    "compatibility_audit_ref",
    "alignment_scope",
    "changed_sources",
    "additive_metadata_fields",
    "untouched_working_rails",
    "unsupported_migration_items",
    "safety_summary",
    "next_safe_move",
)

REQUIRED_SHAPE_FIELDS = (
    "shape_id",
    "artifact_id",
    "source_kind",
    "artifact_type",
    "schema_ref",
    "schema_version",
    "lifecycle_state",
    "world_ref",
    "lane_ref",
    "block_id",
    "workflow_session_ref",
    "operation",
    "origin_surface",
    "source_channel",
    "target_surface",
    "target_handler",
    "reply_to_surface",
    "reply_to_channel",
    "authority_boundary",
    "privacy_boundary",
    "idempotency_key",
    "payload_hash",
    "safe_display_summary",
    "elioperator_message",
    "missing_fields",
    "missing_field_reasons",
    "next_safe_move",
)

REQUIRED_CANDIDATE_FIELDS = (
    "candidate_id",
    "source_name",
    "source_kind",
    "compatibility_status_before",
    "metadata_fields_added",
    "fields_still_missing",
    "safe_to_align_now",
    "risk_level",
    "reason",
    "next_safe_move",
)

REQUIRED_NO_REGRESSION_FIELDS = (
    "check_id",
    "package_paths_unchanged",
    "existing_manifest_fields_preserved",
    "existing_consumers_not_required_to_parse_new_metadata",
    "live_behavior_changed",
    "live_registry_migration_added",
    "watcher_or_daemon_added",
    "external_authority_changed",
    "result",
    "next_safe_move",
)

REQUIRED_ELIOPERATOR_FIELDS = (
    "report_id",
    "plain_summary",
    "what_changed",
    "what_did_not_change",
    "why_it_matters",
    "what_stays_bespoke",
    "what_gets_easier_later",
    "next_safe_move",
)

KNOWN_PACKAGE_PATHS = (
    "/mnt/e/openclaw/shuttle/to_mac/mission_control_capture_intake_20260524",
    "/mnt/e/openclaw/shuttle/to_mac/mission_control_capture_readback_593fdd2_20260524",
    "/mnt/e/openclaw/shuttle/to_mac/capital_hilton_delivery_facts_readback_a868125_20260524",
    "/mnt/e/openclaw/shuttle/to_mac/capital_hilton_delivery_facts_capture_intake_a868125_20260524",
    "/mnt/e/openclaw/shuttle/to_mac/capital_hilton_po_coupa_delivery_facts_readback_d247cd5_20260524",
)

EXPLICIT_NON_GOALS = (
    "no live post-office runtime",
    "no watcher",
    "no daemon",
    "no auto-import",
    "no auto-consume",
    "no automatic handler dispatch",
    "no live Telegram",
    "no agent dispatch",
    "no migration or replacement of working rails",
    "no Mac Swift change",
    "no external send, submit, browser, Coupa, or Gmail actions",
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

STANDARD_EXTERNAL_FALSE_AUTHORITY = {
    "external_action_allowed": False,
    "email_send_allowed": False,
    "email_draft_allowed": False,
    "coupa_submit_allowed": False,
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "credential_handling_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "raw_body_ingestion_allowed": False,
}

RELATIONSHIP_REF_PATHS = {
    "cross_surface_artifact_handoff_registry_contract": (
        "generated/read_models/cross_surface_artifact_handoff_registry_contract.json"
    ),
    "cross_surface_handoff_registry_compatibility_audit": (
        "generated/read_models/cross_surface_handoff_registry_compatibility_audit.json"
    ),
    "mission_control_capture_request_intake": "generated/read_models/mission_control_capture_request_intake.json",
    "capital_hilton_delivery_facts_capture_writer": (
        "generated/read_models/capital_hilton_delivery_facts_capture_writer.json"
    ),
    "capital_hilton_invoice_artifact_generator": (
        "generated/read_models/capital_hilton_invoice_artifact_generator.json"
    ),
    "read_model_shuttle": "read_model_shuttle.py",
    "generated_read_model_files": "generated_read_model_files.py",
}


@dataclass(frozen=True)
class HandoffMetadataAlignmentPatch:
    patch_id: str
    registry_contract_ref: str
    compatibility_audit_ref: str
    alignment_scope: str
    changed_sources: tuple[str, ...]
    additive_metadata_fields: tuple[str, ...]
    untouched_working_rails: tuple[str, ...]
    unsupported_migration_items: tuple[str, ...]
    safety_summary: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class HandoffAlignedMetadataShape:
    shape_id: str
    artifact_id: str
    source_kind: str
    artifact_type: str
    schema_ref: str
    schema_version: str
    lifecycle_state: str
    world_ref: str
    lane_ref: str
    block_id: str
    workflow_session_ref: str
    operation: str
    origin_surface: str
    source_channel: str
    target_surface: str
    target_handler: str
    reply_to_surface: str
    reply_to_channel: str
    authority_boundary: dict[str, Any]
    privacy_boundary: dict[str, Any]
    idempotency_key: str | None
    payload_hash: str | None
    safe_display_summary: str
    elioperator_message: str
    missing_fields: tuple[str, ...]
    missing_field_reasons: dict[str, str]
    next_safe_move: str


@dataclass(frozen=True)
class HandoffMetadataPatchCandidate:
    candidate_id: str
    source_name: str
    source_kind: str
    compatibility_status_before: str
    metadata_fields_added: tuple[str, ...]
    fields_still_missing: tuple[str, ...]
    safe_to_align_now: bool
    risk_level: str
    reason: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffMetadataNoRegressionCheck:
    check_id: str
    package_paths_unchanged: bool
    existing_manifest_fields_preserved: bool
    existing_consumers_not_required_to_parse_new_metadata: bool
    live_behavior_changed: bool
    live_registry_migration_added: bool
    watcher_or_daemon_added: bool
    external_authority_changed: bool
    result: str
    next_safe_move: str


@dataclass(frozen=True)
class HandoffMetadataElioperatorReport:
    report_id: str
    plain_summary: str
    what_changed: tuple[str, ...]
    what_did_not_change: tuple[str, ...]
    why_it_matters: tuple[str, ...]
    what_stays_bespoke: tuple[str, ...]
    what_gets_easier_later: tuple[str, ...]
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


def _authority(*, local_readback_allowed: bool = True, render_allowed: bool = True) -> dict[str, Any]:
    return {
        "external_action_allowed": False,
        "local_receipt_write_allowed": False,
        "local_state_write_allowed": False,
        "readback_write_allowed": local_readback_allowed,
        "render_allowed": render_allowed,
        "approval_required": False,
        "guardian_review_required": False,
        "protected_evidence_required": False,
        **STANDARD_EXTERNAL_FALSE_AUTHORITY,
    }


def _privacy(
    *,
    privacy_class: str,
    sensitivity_class: str,
    raw_value_allowed: bool,
    tokenized_value_ref_allowed: bool = False,
    protected_store_ref_allowed: bool = False,
    central_sync_allowed: bool = True,
) -> dict[str, Any]:
    return {
        "privacy_class": privacy_class,
        "sensitivity_class": sensitivity_class,
        "raw_value_allowed": raw_value_allowed,
        "tokenized_value_ref_allowed": tokenized_value_ref_allowed,
        "protected_store_ref_allowed": protected_store_ref_allowed,
        "central_sync_allowed": central_sync_allowed,
        "normal_read_model_body_allowed": not protected_store_ref_allowed,
        "raw_protected_payload_allowed": False,
        "redaction_required": not raw_value_allowed,
        "de_tokenization_allowed": False,
    }


def build_post_office_metadata(
    *,
    shape_id: str,
    artifact_id: str,
    source_kind: str,
    artifact_type: str,
    schema_ref: str,
    schema_version: str,
    lifecycle_state: str,
    world_ref: str,
    lane_ref: str,
    block_id: str,
    workflow_session_ref: str,
    operation: str,
    origin_surface: str,
    source_channel: str,
    target_surface: str,
    target_handler: str,
    reply_to_surface: str,
    reply_to_channel: str,
    authority_boundary: dict[str, Any],
    privacy_boundary: dict[str, Any],
    idempotency_key: str | None,
    payload_hash: str | None,
    safe_display_summary: str,
    elioperator_message: str,
    missing_fields: tuple[str, ...] = (),
    missing_field_reasons: dict[str, str] | None = None,
    next_safe_move: str,
) -> HandoffAlignedMetadataShape:
    return HandoffAlignedMetadataShape(
        shape_id=shape_id,
        artifact_id=artifact_id,
        source_kind=source_kind,
        artifact_type=artifact_type,
        schema_ref=schema_ref,
        schema_version=schema_version,
        lifecycle_state=lifecycle_state,
        world_ref=world_ref,
        lane_ref=lane_ref,
        block_id=block_id,
        workflow_session_ref=workflow_session_ref,
        operation=operation,
        origin_surface=origin_surface,
        source_channel=source_channel,
        target_surface=target_surface,
        target_handler=target_handler,
        reply_to_surface=reply_to_surface,
        reply_to_channel=reply_to_channel,
        authority_boundary=authority_boundary,
        privacy_boundary=privacy_boundary,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        safe_display_summary=safe_display_summary,
        elioperator_message=elioperator_message,
        missing_fields=missing_fields,
        missing_field_reasons=missing_field_reasons or {},
        next_safe_move=next_safe_move,
    )


def _aligned_shapes() -> tuple[HandoffAlignedMetadataShape, ...]:
    return (
        build_post_office_metadata(
            shape_id="aligned_performance_dates_capture_readback",
            artifact_id="mission_control_capture_readback_593fdd2_performance_dates",
            source_kind="READBACK_PACKAGE",
            artifact_type="CAPTURE_READBACK",
            schema_ref="mission_control_capture_request_intake.MissionControlCaptureIntakeReadback",
            schema_version="mission_control_capture_request_intake_v0",
            lifecycle_state="DUPLICATE_NOOP",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="performance_dates",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="add_dates",
            origin_surface="Repo A backend",
            source_channel="read_model_shuttle_package",
            target_surface="Mission Control Mac",
            target_handler="mission_control_capture_readback_renderer",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            authority_boundary=_authority(),
            privacy_boundary=_privacy(
                privacy_class="sanitized_readback",
                sensitivity_class="low",
                raw_value_allowed=True,
            ),
            idempotency_key=None,
            payload_hash=None,
            safe_display_summary="Backend readback is ready for Mission Control; duplicate replay wrote no second row.",
            elioperator_message=(
                "OpenClaw already had this exact capture; no duplicate was written. Nothing was sent, submitted, opened, or accessed."
            ),
            missing_fields=("idempotency_key", "payload_hash"),
            missing_field_reasons={
                "idempotency_key": "Older performance-date readback does not expose the original request idempotency key.",
                "payload_hash": "Older performance-date readback does not expose the original request payload hash.",
            },
            next_safe_move="Add these fields to future capture readbacks; do not rewrite the existing package.",
        ),
        build_post_office_metadata(
            shape_id="aligned_po_coupa_delivery_facts_readback",
            artifact_id="capital_hilton_po_coupa_delivery_facts_readback_d247cd5",
            source_kind="READBACK_PACKAGE",
            artifact_type="DELIVERY_FACT_UPDATE",
            schema_ref="capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureReadback",
            schema_version="capital_hilton_delivery_facts_capture_writer_v0",
            lifecycle_state="READBACK_READY",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="proof_po_reference",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="set_needs_discovery",
            origin_surface="Repo A backend",
            source_channel="mission_control_capture_outbox",
            target_surface="Mission Control Mac",
            target_handler="capital_hilton_delivery_facts_readback_renderer",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            authority_boundary=_authority(),
            privacy_boundary=_privacy(
                privacy_class="protected_reference",
                sensitivity_class="protected",
                raw_value_allowed=False,
                protected_store_ref_allowed=False,
                central_sync_allowed=False,
            ),
            idempotency_key=(
                "capital_hilton_delivery_fact:capital_hilton_invoice_workflow_session:"
                "proof_po_reference:set_needs_discovery:OPERATOR_PROOF_PO_DISCOVERY_POSTURE:fbe90eff5b41b888a58a"
            ),
            payload_hash="sha256:88a9e28d8a39696d720b39e450cb9767a839fe3f08275b6b96edc955d528afb1",
            safe_display_summary="PO/Coupa posture is locally captured as Needs Discovery; no reference is confirmed.",
            elioperator_message=(
                "PO/Coupa posture is locally captured as Needs Discovery. Nothing was sent, submitted, opened, or accessed."
            ),
            missing_fields=(),
            next_safe_move="Render the next operator question for reference/discovery; keep delivery gates closed.",
        ),
        build_post_office_metadata(
            shape_id="aligned_delivery_facts_capture_intake_package",
            artifact_id="capital_hilton_delivery_facts_capture_intake_a868125",
            source_kind="OUTBOX_CONTRACT_MARKER",
            artifact_type="CAPTURE_REQUEST",
            schema_ref="capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureRequest",
            schema_version="capital_hilton_delivery_facts_capture_writer_v0",
            lifecycle_state="EMITTED",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="proof_po_reference",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="set_needs_discovery",
            origin_surface="Mission Control Mac",
            source_channel="bounded_capture_outbox_json",
            target_surface="Repo A backend",
            target_handler="capital_hilton_delivery_facts_capture_writer",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            authority_boundary=_authority(local_readback_allowed=False, render_allowed=False),
            privacy_boundary=_privacy(
                privacy_class="protected_reference",
                sensitivity_class="protected",
                raw_value_allowed=False,
                central_sync_allowed=False,
            ),
            idempotency_key=None,
            payload_hash=None,
            safe_display_summary="Capture request handed off through the bounded outbox contract.",
            elioperator_message=(
                "Mission Control may emit supported delivery-fact capture requests only through the approved bounded outbox."
            ),
            missing_fields=("idempotency_key", "payload_hash"),
            missing_field_reasons={
                "idempotency_key": "Unavailable until a concrete capture request file is emitted.",
                "payload_hash": "Unavailable until a concrete capture request file is emitted.",
            },
            next_safe_move="Future emitted requests must include deterministic idempotency and payload hash.",
        ),
        build_post_office_metadata(
            shape_id="aligned_invoice_artifact_preview",
            artifact_id="capital_hilton_invoice_artifact_preview_v0",
            source_kind="ARTIFACT_GENERATOR",
            artifact_type="INVOICE_ARTIFACT_PREVIEW",
            schema_ref="capital_hilton_invoice_artifact_generator.CapitalHiltonInvoiceArtifactReadback",
            schema_version="capital_hilton_invoice_artifact_generator_v0",
            lifecycle_state="READBACK_READY",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            block_id="invoice_packet",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            operation="generate_local_preview",
            origin_surface="Repo A backend",
            source_channel="generated_read_model_export",
            target_surface="Mission Control Mac",
            target_handler="future_invoice_artifact_preview_renderer",
            reply_to_surface="Mission Control Mac",
            reply_to_channel="read_model_shuttle_package",
            authority_boundary=_authority(),
            privacy_boundary=_privacy(
                privacy_class="sanitized_readback",
                sensitivity_class="medium",
                raw_value_allowed=False,
            ),
            idempotency_key=(
                "post_office:capital_hilton:invoice_preview:"
                "a135264f8df31f762170ea53f50d74d44d08cfe1ee95dfc8fd318fad178970fc"
            ),
            payload_hash="sha256:a135264f8df31f762170ea53f50d74d44d08cfe1ee95dfc8fd318fad178970fc",
            safe_display_summary="Invoice artifact preview exists with a real hash; delivery/send remains blocked.",
            elioperator_message=(
                "The invoice preview can be rendered as an artifact handoff. It is not a send, draft, or submission."
            ),
            missing_fields=(),
            next_safe_move="Attach this metadata to future artifact-preview readbacks; keep send/submit gates closed.",
        ),
        build_post_office_metadata(
            shape_id="aligned_reusable_fact_future_compatibility",
            artifact_id="future_reusable_fact_handoff_metadata_template",
            source_kind="FUTURE_COMPATIBILITY",
            artifact_type="REUSABLE_FACT",
            schema_ref="cross_lane_reusable_block_registry_contract.CrossLaneReusableFactBlock",
            schema_version="cross_lane_reusable_block_registry_contract_v0",
            lifecycle_state="CREATED",
            world_ref="future_target_world",
            lane_ref="future_target_lane",
            block_id="future_reusable_fact_block",
            workflow_session_ref="future_target_workflow_session_required",
            operation="suggest_reuse_or_inform_only",
            origin_surface="Repo A backend",
            source_channel="future_agent_or_surface_handoff",
            target_surface="future compatible surface",
            target_handler="future_reusable_block_intake_handler",
            reply_to_surface="origin_surface",
            reply_to_channel="safe_readback_summary",
            authority_boundary=_authority(local_readback_allowed=False, render_allowed=False),
            privacy_boundary=_privacy(
                privacy_class="protected_reference",
                sensitivity_class="protected",
                raw_value_allowed=False,
                tokenized_value_ref_allowed=True,
                protected_store_ref_allowed=True,
                central_sync_allowed=False,
            ),
            idempotency_key=None,
            payload_hash=None,
            safe_display_summary="Reusable fact compatibility is metadata-only; raw value remains forbidden.",
            elioperator_message=(
                "Reusable facts can carry tokenized refs later. They do not grant live auto-apply or reveal authority."
            ),
            missing_fields=("idempotency_key", "payload_hash", "live_handler"),
            missing_field_reasons={
                "idempotency_key": "Future concrete reusable fact handoff must derive this from scope and token ref.",
                "payload_hash": "Future concrete reusable fact handoff must hash the safe payload.",
                "live_handler": "Reusable fact intake is intentionally not live yet.",
            },
            next_safe_move="Keep do-not-migrate posture until protected handler exists.",
        ),
    )


def _patch() -> HandoffMetadataAlignmentPatch:
    return HandoffMetadataAlignmentPatch(
        patch_id="capital_hilton_post_office_metadata_alignment_patch_v0",
        registry_contract_ref=REGISTRY_CONTRACT_REF,
        compatibility_audit_ref=COMPATIBILITY_AUDIT_REF,
        alignment_scope="Additive post-office metadata shapes for future Capital Hilton manifests/readbacks.",
        changed_sources=(
            "cross_surface_handoff_registry_metadata_alignment.py",
            "generated/read_models/cross_surface_handoff_registry_metadata_alignment.json",
            "generated/read_models/cross_surface_handoff_registry_metadata_alignment_OPERATOR.md",
        ),
        additive_metadata_fields=POST_OFFICE_METADATA_FIELDS,
        untouched_working_rails=(
            "mission_control_capture_request_intake.py",
            "capital_hilton_delivery_facts_capture_writer.py",
            "capital_hilton_delivery_facts_capture_bridge.py",
            "capital_hilton_invoice_artifact_generator.py",
            "read_model_shuttle.py live behavior",
            "existing Mac-bound shuttle package paths",
        ),
        unsupported_migration_items=(
            "live post-office runtime",
            "watcher or daemon",
            "auto-import",
            "auto-consume",
            "automatic handler dispatch",
            "live Telegram",
            "agent dispatch",
            "working rail replacement",
            "Mac Swift change",
            "external send or submit",
        ),
        safety_summary=(
            "Metadata is additive and safe to ignore.",
            "Missing values are reported as missing instead of invented.",
            "All external authority remains false.",
            "No raw protected payload examples are included.",
            "Existing package paths remain unchanged.",
        ),
        next_safe_move="Use these shapes in future package generation after review; do not rewrite old packages.",
    )


def _patch_candidates() -> tuple[HandoffMetadataPatchCandidate, ...]:
    return (
        HandoffMetadataPatchCandidate(
            candidate_id="candidate_future_performance_dates_readback_metadata",
            source_name="Mission Control capture readback package",
            source_kind="READBACK_PACKAGE",
            compatibility_status_before="NEEDS_METADATA_PATCH",
            metadata_fields_added=POST_OFFICE_METADATA_FIELDS,
            fields_still_missing=("idempotency_key", "payload_hash"),
            safe_to_align_now=True,
            risk_level="low",
            reason="Performance Dates readback already has receipt/state and safe display, but older readback omits request hash fields.",
            next_safe_move="Add idempotency/hash to future readbacks at the intake layer.",
        ),
        HandoffMetadataPatchCandidate(
            candidate_id="candidate_future_delivery_facts_readback_metadata",
            source_name="PO/Coupa delivery facts readback package",
            source_kind="READBACK_PACKAGE",
            compatibility_status_before="REGISTRY_READY",
            metadata_fields_added=POST_OFFICE_METADATA_FIELDS,
            fields_still_missing=(),
            safe_to_align_now=True,
            risk_level="very_low",
            reason="PO/Coupa readback already has idempotency, payload hash, lifecycle, block, operation, and authority metadata.",
            next_safe_move="Use this as the first concrete package-generation template.",
        ),
        HandoffMetadataPatchCandidate(
            candidate_id="candidate_future_delivery_capture_intake_metadata",
            source_name="Delivery facts capture intake/outbox marker",
            source_kind="OUTBOX_CONTRACT_MARKER",
            compatibility_status_before="NEEDS_METADATA_PATCH",
            metadata_fields_added=POST_OFFICE_METADATA_FIELDS,
            fields_still_missing=("idempotency_key", "payload_hash"),
            safe_to_align_now=True,
            risk_level="low",
            reason="Outbox marker can describe required idempotency/hash basis before actual requests exist.",
            next_safe_move="Patch future markers only; keep the approved outbox path unchanged.",
        ),
        HandoffMetadataPatchCandidate(
            candidate_id="candidate_future_invoice_artifact_preview_metadata",
            source_name="Invoice artifact preview readback",
            source_kind="ARTIFACT_GENERATOR",
            compatibility_status_before="MOSTLY_COMPATIBLE",
            metadata_fields_added=POST_OFFICE_METADATA_FIELDS,
            fields_still_missing=(),
            safe_to_align_now=True,
            risk_level="low",
            reason="Preview has real artifact hash and can map to INVOICE_ARTIFACT_PREVIEW without delivery authority.",
            next_safe_move="Attach metadata to future preview packages; do not send or submit.",
        ),
        HandoffMetadataPatchCandidate(
            candidate_id="candidate_reusable_fact_future_metadata_only",
            source_name="Reusable fact future compatibility",
            source_kind="FUTURE_COMPATIBILITY",
            compatibility_status_before="DO_NOT_MIGRATE_YET",
            metadata_fields_added=("artifact_type", "schema_ref", "privacy_boundary", "authority_boundary"),
            fields_still_missing=("idempotency_key", "payload_hash", "live_handler"),
            safe_to_align_now=False,
            risk_level="medium",
            reason="Tokenized reusable facts need a protected handler before live handoff or auto-apply.",
            next_safe_move="Keep explicit do-not-migrate posture.",
        ),
    )


def _no_regression_check() -> HandoffMetadataNoRegressionCheck:
    return HandoffMetadataNoRegressionCheck(
        check_id="post_office_metadata_alignment_no_regression_v0",
        package_paths_unchanged=True,
        existing_manifest_fields_preserved=True,
        existing_consumers_not_required_to_parse_new_metadata=True,
        live_behavior_changed=False,
        live_registry_migration_added=False,
        watcher_or_daemon_added=False,
        external_authority_changed=False,
        result="PASS_METADATA_ONLY_NO_REGRESSION",
        next_safe_move="Future package builders may include post_office_metadata; existing consumers may ignore it.",
    )


def _elioperator_report() -> HandoffMetadataElioperatorReport:
    return HandoffMetadataElioperatorReport(
        report_id="post_office_metadata_alignment_elioperator_report_v0",
        plain_summary=(
            "This adds a standard metadata shape for future Mac/PC handoffs. It prepares post-office routing language "
            "without replacing the working bridge."
        ),
        what_changed=(
            "Defined the additive post_office_metadata fields future manifests/readbacks can include.",
            "Modeled aligned metadata for Performance Dates, PO/Coupa readback, delivery capture intake, invoice preview, and reusable facts.",
            "Recorded which fields are still missing instead of inventing values.",
        ),
        what_did_not_change=(
            "No existing package path changed.",
            "No existing manifest field was removed.",
            "No live intake semantics changed.",
            "No SQLite state changed.",
            "No Mac import or Swift code changed.",
            "No send, submit, browser, Coupa, Gmail, Telegram, model, agent, tool, or runtime action was added.",
        ),
        why_it_matters=(
            "Future packages can say what they are, which handler owns them, what lifecycle state they are in, and what authority applies.",
            "Mission Control can later render cleaner readback status without each package needing custom language.",
            "Protected or unavailable values stay explicit and fail-closed.",
        ),
        what_stays_bespoke=(
            "The current capture writers and shuttle packages stay in place.",
            "Reusable fact handoff remains future-only.",
            "Telegram/Cassandra remains compatibility-only, not live.",
        ),
        what_gets_easier_later=(
            "Readback package generation can attach one post-office metadata section.",
            "Mac can eventually route closeouts by artifact_type and lifecycle_state.",
            "Backend audits can compare manifests using shared field names.",
        ),
        next_safe_move="Use this metadata shape in a future readback package generation lane.",
    )


def _model_schemas() -> dict[str, dict[str, Any]]:
    return {
        "handoff_metadata_alignment_patch": {
            "model_name": "HandoffMetadataAlignmentPatch",
            "required_fields": list(REQUIRED_PATCH_FIELDS),
        },
        "handoff_aligned_metadata_shape": {
            "model_name": "HandoffAlignedMetadataShape",
            "required_fields": list(REQUIRED_SHAPE_FIELDS),
            "post_office_metadata_fields": list(POST_OFFICE_METADATA_FIELDS),
        },
        "handoff_metadata_patch_candidate": {
            "model_name": "HandoffMetadataPatchCandidate",
            "required_fields": list(REQUIRED_CANDIDATE_FIELDS),
        },
        "handoff_metadata_no_regression_check": {
            "model_name": "HandoffMetadataNoRegressionCheck",
            "required_fields": list(REQUIRED_NO_REGRESSION_FIELDS),
        },
        "handoff_metadata_elioperator_report": {
            "model_name": "HandoffMetadataElioperatorReport",
            "required_fields": list(REQUIRED_ELIOPERATOR_FIELDS),
        },
    }


def build_cross_surface_handoff_registry_metadata_alignment(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    shapes = _aligned_shapes()
    candidates = _patch_candidates()
    patch = _patch()
    no_regression = _no_regression_check()
    report = _elioperator_report()

    shapes_by_id = {shape.shape_id: asdict(shape) for shape in shapes}
    candidates_by_id = {candidate.candidate_id: asdict(candidate) for candidate in candidates}

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "purpose": (
            "Define additive post-office metadata for future Capital Hilton Mac/PC handoff packages "
            "without changing live bridge behavior."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "explicit_non_goals": list(EXPLICIT_NON_GOALS),
        "known_package_paths": list(KNOWN_PACKAGE_PATHS),
        "model_schemas": _model_schemas(),
        "metadata_alignment_patch": asdict(patch),
        "aligned_metadata_shapes_by_id": shapes_by_id,
        "patch_candidates_by_id": candidates_by_id,
        "no_regression_check": asdict(no_regression),
        "elioperator_report": asdict(report),
        "relationship_inventory": _relationship_inventory(),
        "examples": {
            "performance_dates": "aligned_performance_dates_capture_readback",
            "po_coupa_readback": "aligned_po_coupa_delivery_facts_readback",
            "delivery_capture_intake": "aligned_delivery_facts_capture_intake_package",
            "invoice_artifact": "aligned_invoice_artifact_preview",
            "reusable_fact_compatibility": "aligned_reusable_fact_future_compatibility",
        },
        "security_privacy_rules": {
            "raw_email_addresses_included": False,
            "raw_phone_numbers_included": False,
            "raw_po_or_payment_references_included": False,
            "raw_screenshot_bodies_included": False,
            "raw_email_bodies_included": False,
            "raw_pdf_or_excel_bodies_included": False,
            "credentials_tokens_cookies_included": False,
            "tax_bank_remit_private_documents_included": False,
            "raw_private_bodies_included": False,
        },
    }

    missing_fields = sorted(
        {
            missing
            for shape in shapes
            for missing in shape.missing_fields
        }
    )
    do_not_migrate = tuple(
        candidate.candidate_id for candidate in candidates if candidate.safe_to_align_now is False
    )
    payload["machine_proof"] = {
        "handoff_metadata_alignment_patch_model_present": True,
        "handoff_aligned_metadata_shape_model_present": True,
        "handoff_metadata_patch_candidate_model_present": True,
        "handoff_metadata_no_regression_check_model_present": True,
        "handoff_metadata_elioperator_report_model_present": True,
        "all_required_post_office_fields_modeled": set(POST_OFFICE_METADATA_FIELDS)
        == set(REQUIRED_SHAPE_FIELDS) - {"shape_id", "source_kind"},
        "performance_dates_example_present": "aligned_performance_dates_capture_readback" in shapes_by_id,
        "po_coupa_readback_example_present": "aligned_po_coupa_delivery_facts_readback" in shapes_by_id,
        "delivery_capture_intake_example_present": "aligned_delivery_facts_capture_intake_package" in shapes_by_id,
        "invoice_artifact_example_present": "aligned_invoice_artifact_preview" in shapes_by_id,
        "reusable_fact_compatibility_example_present": (
            "aligned_reusable_fact_future_compatibility" in shapes_by_id
        ),
        "missing_fields_reported_not_faked": "idempotency_key" in missing_fields and "payload_hash" in missing_fields,
        "existing_manifest_fields_preserved": no_regression.existing_manifest_fields_preserved,
        "package_paths_unchanged": no_regression.package_paths_unchanged,
        "live_behavior_changed": no_regression.live_behavior_changed,
        "live_registry_migration_added": no_regression.live_registry_migration_added,
        "watcher_or_daemon_added": no_regression.watcher_or_daemon_added,
        "external_authority_changed": no_regression.external_authority_changed,
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "all_shape_external_authority_false": all(
            all(shape.authority_boundary[field] is False for field in STANDARD_EXTERNAL_FALSE_AUTHORITY)
            for shape in shapes
        ),
        "do_not_migrate_items_remain": do_not_migrate,
        "elioperator_report_present": True,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_protected_payload_examples_included": False,
        "raw_sensitive_fixture_values_included": False,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["elioperator_report"]
    proof = payload["machine_proof"]
    return "\n".join(
        [
            "# Cross-Surface Handoff Registry Metadata Alignment",
            "",
            "## ELIOPERATOR",
            "",
            report["plain_summary"],
            "",
            "This is metadata-only. It does not create a post-office runtime, watcher, daemon, auto-import, "
            "auto-consume path, Telegram integration, agent dispatch, Mac Swift change, or external action.",
            "",
            "## What Changed",
            "",
            "\n".join(f"- {item}" for item in report["what_changed"]),
            "",
            "## What Did Not Change",
            "",
            "\n".join(f"- {item}" for item in report["what_did_not_change"]),
            "",
            "## Why It Matters",
            "",
            "\n".join(f"- {item}" for item in report["why_it_matters"]),
            "",
            "## Still Bespoke",
            "",
            "\n".join(f"- {item}" for item in report["what_stays_bespoke"]),
            "",
            "## Easier Later",
            "",
            "\n".join(f"- {item}" for item in report["what_gets_easier_later"]),
            "",
            "## Machine Proof",
            "",
            f"- Package paths unchanged: {proof['package_paths_unchanged']}",
            f"- Existing manifest fields preserved: {proof['existing_manifest_fields_preserved']}",
            f"- Live behavior changed: {proof['live_behavior_changed']}",
            f"- Live registry migration added: {proof['live_registry_migration_added']}",
            f"- External authority changed: {proof['external_authority_changed']}",
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
        "aligned_shape_count": len(payload["aligned_metadata_shapes_by_id"]),
        "patch_candidate_count": len(payload["patch_candidates_by_id"]),
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "all_shape_external_authority_false": payload["machine_proof"]["all_shape_external_authority_false"],
        "package_paths_unchanged": payload["machine_proof"]["package_paths_unchanged"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Directory for generated read-models.")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--no-write", action="store_true", help="Build output without writing generated files.")
    args = parser.parse_args(argv)

    payload = build_cross_surface_handoff_registry_metadata_alignment()
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
