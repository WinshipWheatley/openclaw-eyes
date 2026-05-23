"""Guided Capture / Protected Evidence Path Contract v0.

This read-model defines how OpenClaw can guide an operator to the easiest safe
evidence capture path when truth needs evidence. It models capture paths,
capture moments, protected artifact targets, outcomes, privacy guards, and
future receipt targets. It does not execute screenshot capture, write files,
write protected evidence, write receipts, persist operator answers, access
browsers/accounts/Coupa/Gmail/calendar/Telegram, handle credentials, refresh
the stable map, call models/tools/agents/runtimes, generate invoices, send
messages, submit approvals, write ledgers, or grant authority.
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

SCHEMA_VERSION = "guided_capture_protected_evidence_path_contract_v0"
READ_MODEL_ID = "guided_capture_protected_evidence_path_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_GUIDED_CAPTURE_CONTRACT"

PRIOR_LANE_REFS = {
    "operator_work_mode_schema_bandwidth_policy": (
        "generated/read_models/operator_work_mode_schema_bandwidth_policy.json"
    ),
    "operator_solve_path_decision_node_contract": (
        "generated/read_models/operator_solve_path_decision_node_contract.json"
    ),
    "capital_hilton_coupa_po_retrieval_automation_candidate": (
        "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json"
    ),
    "capital_hilton_protected_reference_placeholder": (
        "generated/read_models/capital_hilton_protected_reference_placeholder.json"
    ),
    "capital_hilton_guardian_review_packet": (
        "generated/read_models/capital_hilton_guardian_review_packet.json"
    ),
    "capital_hilton_proof_quieting_progress_state": (
        "generated/read_models/capital_hilton_proof_quieting_progress_state.json"
    ),
    "openclaw_work_terrain_gap_detector": "generated/read_models/openclaw_work_terrain_gap_detector.json",
}

RECOMMENDED_CAPTURE_METHODS = (
    "OPERATOR_TEXT_CONFIRMATION",
    "STRUCTURED_CHOICE",
    "MANUAL_REFERENCE_ENTRY",
    "GUIDED_SCREENSHOT_CAPTURE",
    "GUIDED_FILE_REFERENCE",
    "SOURCE_CARD_REFERENCE",
    "PROTECTED_EVIDENCE_REFERENCE",
    "RECEIPT_REFERENCE",
    "ASSISTED_BROWSER_CAPTURE",
    "SUPERVISED_AUTOMATION_CANDIDATE",
    "UNKNOWN_FAIL_CLOSED",
)

ARTIFACT_TYPES = (
    "SCREENSHOT_PROTECTED_REFERENCE",
    "PDF_PROTECTED_REFERENCE",
    "EXCEL_WORKBOOK_REFERENCE",
    "EMAIL_THREAD_REFERENCE",
    "WEB_PORTAL_REFERENCE",
    "SOURCE_CARD",
    "RECEIPT",
    "TEXT_CONFIRMATION",
    "UNKNOWN_FAIL_CLOSED",
)

OUTCOME_TYPES = (
    "CAPTURE_SUCCESS_RECEIPT_TARGET",
    "CAPTURE_CANCELLED",
    "NOT_THE_RIGHT_THING",
    "NEEDS_DISCOVERY",
    "PARKED",
    "PROTECTED_REVIEW_REQUIRED",
    "AUTOMATION_CANDIDATE_CREATED",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_CAPTURE_PATH_FIELDS = (
    "capture_path_id",
    "display_title",
    "world",
    "lane",
    "workflow_session_ref",
    "decision_node_ref",
    "capture_purpose",
    "truth_needed",
    "recommended_capture_method",
    "operator_goal",
    "system_can_do_now",
    "operator_must_do_now",
    "system_future_automation_candidate",
    "capture_moment_prompt",
    "allowed_capture_inputs",
    "blocked_capture_inputs",
    "target_artifact_type",
    "target_storage_policy",
    "protected_evidence_required",
    "guardian_review_required",
    "receipt_type",
    "receipt_target",
    "after_capture_state",
    "next_step_after_success",
    "fallback_if_not_available",
    "blocked_actions",
    "authority_granted",
    "next_safe_move",
)

REQUIRED_CAPTURE_MOMENT_FIELDS = (
    "capture_moment_id",
    "capture_path_ref",
    "display_prompt",
    "what_operator_should_verify",
    "ready_phrase",
    "confirm_button_label",
    "cancel_button_label",
    "not_the_right_thing_label",
    "system_pre_capture_checks",
    "system_capture_actions_if_authorized",
    "system_post_capture_actions_if_authorized",
    "capture_authority_currently_granted",
    "next_safe_move",
)

REQUIRED_ARTIFACT_TARGET_FIELDS = (
    "artifact_target_id",
    "artifact_type",
    "intended_storage_area",
    "path_policy",
    "naming_policy",
    "hash_required",
    "receipt_required",
    "redaction_required",
    "metadata_only_default",
    "raw_body_allowed",
    "protected_reference_required",
    "guardian_review_required",
    "operator_final_authority_required",
    "blocked_material",
    "next_safe_move",
)

REQUIRED_CAPTURE_OUTCOME_FIELDS = (
    "outcome_id",
    "capture_path_ref",
    "outcome_type",
    "would_create_artifact",
    "would_create_receipt",
    "would_link_to_workflow_step",
    "would_link_to_proof_item",
    "would_trigger_guardian_review",
    "would_advance_workflow",
    "would_quiet_step",
    "would_create_discovery_substep",
    "would_create_automation_candidate",
    "current_execution_authority",
    "next_safe_move",
)

REQUIRED_PRIVACY_GUARD_FIELDS = (
    "guard_id",
    "risk_surface",
    "risk_description",
    "required_guardrail",
    "blocked_capture_scope",
    "allowed_capture_scope",
    "redaction_required",
    "guardian_review_required",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "screenshot_capture_allowed": False,
    "file_write_allowed": False,
    "file_upload_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "credential_handling_allowed": False,
    "network_operation_allowed": False,
    "raw_body_ingestion_allowed": False,
    "protected_evidence_write_allowed": False,
    "receipt_write_allowed": False,
    "workflow_state_write_allowed": False,
    "invoice_generation_allowed": False,
    "email_send_allowed": False,
    "approval_submission_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "operator_input_persistence_allowed": False,
    "stable_map_refresh_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "file_move_delete_cleanup_allowed": False,
    "telegram_send_allowed": False,
    "direct_credential_store_reads_allowed": False,
}

FUTURE_NON_AUTHORITY_FLAGS = {
    "future_guided_capture_lane_candidate": True,
    "future_protected_storage_policy_candidate": True,
    "future_screenshot_capture_candidate": True,
    "future_assisted_browser_capture_candidate": True,
    "future_supervised_automation_candidate": True,
    "future_flags_grant_current_authority": False,
}

COMMON_BLOCKED_ACTIONS = (
    "screenshot capture execution",
    "file write or upload",
    "protected evidence write",
    "receipt write",
    "workflow state write",
    "browser/Coupa/account access",
    "credential handling",
    "network operation",
    "raw body ingestion",
    "invoice generation",
    "email send",
    "approval submission",
    "model/tool/agent/runtime/queue execution",
)


@dataclass(frozen=True)
class GuidedCapturePath:
    capture_path_id: str
    display_title: str
    world: str
    lane: str
    workflow_session_ref: str
    decision_node_ref: str
    capture_purpose: str
    truth_needed: str
    recommended_capture_method: str
    operator_goal: str
    system_can_do_now: tuple[str, ...]
    operator_must_do_now: tuple[str, ...]
    system_future_automation_candidate: bool
    capture_moment_prompt: str
    allowed_capture_inputs: tuple[str, ...]
    blocked_capture_inputs: tuple[str, ...]
    target_artifact_type: str
    target_storage_policy: str
    protected_evidence_required: bool
    guardian_review_required: bool
    receipt_type: str
    receipt_target: str
    after_capture_state: str
    next_step_after_success: str
    fallback_if_not_available: str
    blocked_actions: tuple[str, ...]
    authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class GuidedCaptureMoment:
    capture_moment_id: str
    capture_path_ref: str
    display_prompt: str
    what_operator_should_verify: tuple[str, ...]
    ready_phrase: str
    confirm_button_label: str
    cancel_button_label: str
    not_the_right_thing_label: str
    system_pre_capture_checks: tuple[str, ...]
    system_capture_actions_if_authorized: tuple[str, ...]
    system_post_capture_actions_if_authorized: tuple[str, ...]
    capture_authority_currently_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedEvidenceArtifactTarget:
    artifact_target_id: str
    artifact_type: str
    intended_storage_area: str
    path_policy: str
    naming_policy: str
    hash_required: bool
    receipt_required: bool
    redaction_required: bool
    metadata_only_default: bool
    raw_body_allowed: bool
    protected_reference_required: bool
    guardian_review_required: bool
    operator_final_authority_required: bool
    blocked_material: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class GuidedCaptureOutcome:
    outcome_id: str
    capture_path_ref: str
    outcome_type: str
    would_create_artifact: bool
    would_create_receipt: bool
    would_link_to_workflow_step: bool
    would_link_to_proof_item: bool
    would_trigger_guardian_review: bool
    would_advance_workflow: bool
    would_quiet_step: bool
    would_create_discovery_substep: bool
    would_create_automation_candidate: bool
    current_execution_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapturePrivacyGuard:
    guard_id: str
    risk_surface: str
    risk_description: str
    required_guardrail: str
    blocked_capture_scope: tuple[str, ...]
    allowed_capture_scope: tuple[str, ...]
    redaction_required: bool
    guardian_review_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class GuidedCaptureExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    capture_path_count: int
    capture_moment_count: int
    artifact_target_count: int
    outcome_count: int
    privacy_guard_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _all_authority_flags_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def _artifact_target(
    artifact_target_id: str,
    *,
    artifact_type: str,
    intended_storage_area: str,
    path_policy: str,
    naming_policy: str,
    redaction_required: bool,
    protected_reference_required: bool,
    guardian_review_required: bool,
    blocked_material: tuple[str, ...],
    next_safe_move: str,
    hash_required: bool = True,
    receipt_required: bool = True,
    metadata_only_default: bool = True,
    raw_body_allowed: bool = False,
    operator_final_authority_required: bool = True,
) -> ProtectedEvidenceArtifactTarget:
    return ProtectedEvidenceArtifactTarget(
        artifact_target_id=artifact_target_id,
        artifact_type=artifact_type,
        intended_storage_area=intended_storage_area,
        path_policy=path_policy,
        naming_policy=naming_policy,
        hash_required=hash_required,
        receipt_required=receipt_required,
        redaction_required=redaction_required,
        metadata_only_default=metadata_only_default,
        raw_body_allowed=raw_body_allowed,
        protected_reference_required=protected_reference_required,
        guardian_review_required=guardian_review_required,
        operator_final_authority_required=operator_final_authority_required,
        blocked_material=blocked_material,
        next_safe_move=next_safe_move,
    )


def default_artifact_targets() -> tuple[ProtectedEvidenceArtifactTarget, ...]:
    sensitive_blocked = (
        "credentials",
        "session cookies or tokens",
        "raw private body",
        "bank/check/remit details unless protected metadata only",
        "unrelated app/window content",
    )
    return (
        _artifact_target(
            "protected_screenshot_reference_target",
            artifact_type="SCREENSHOT_PROTECTED_REFERENCE",
            intended_storage_area="future_protected_evidence_store",
            path_policy="deterministic workflow/session/proof-item path chosen by future writer",
            naming_policy="workflow_session__proof_item__timestamp__hash_prefix",
            redaction_required=True,
            protected_reference_required=True,
            guardian_review_required=True,
            blocked_material=sensitive_blocked,
            next_safe_move="Model protected screenshot target only.",
        ),
        _artifact_target(
            "protected_pdf_reference_target",
            artifact_type="PDF_PROTECTED_REFERENCE",
            intended_storage_area="future_protected_evidence_store",
            path_policy="deterministic workflow/session/proof-item path chosen by future writer",
            naming_policy="workflow_session__pdf_reference__timestamp__hash_prefix",
            redaction_required=True,
            protected_reference_required=True,
            guardian_review_required=True,
            blocked_material=sensitive_blocked,
            next_safe_move="Model protected PDF target only.",
        ),
        _artifact_target(
            "excel_workbook_reference_target",
            artifact_type="EXCEL_WORKBOOK_REFERENCE",
            intended_storage_area="future_protected_evidence_store",
            path_policy="deterministic workflow/session/proof-item path chosen by future writer",
            naming_policy="workflow_session__excel_reference__timestamp__hash_prefix",
            redaction_required=True,
            protected_reference_required=True,
            guardian_review_required=True,
            blocked_material=sensitive_blocked,
            next_safe_move="Model workbook reference target only.",
        ),
        _artifact_target(
            "email_thread_reference_target",
            artifact_type="EMAIL_THREAD_REFERENCE",
            intended_storage_area="future_protected_evidence_store",
            path_policy="deterministic communication/session/proof-item path chosen by future writer",
            naming_policy="workflow_session__email_thread_reference__timestamp__hash_prefix",
            redaction_required=True,
            protected_reference_required=True,
            guardian_review_required=True,
            blocked_material=("raw email body", "recipient private data", "credentials", "unrelated thread content"),
            next_safe_move="Model email/thread reference target only.",
        ),
        _artifact_target(
            "web_portal_reference_target",
            artifact_type="WEB_PORTAL_REFERENCE",
            intended_storage_area="future_protected_evidence_store",
            path_policy="deterministic portal/workflow/proof-item path chosen by future writer",
            naming_policy="workflow_session__portal_reference__timestamp__hash_prefix",
            redaction_required=True,
            protected_reference_required=True,
            guardian_review_required=True,
            blocked_material=sensitive_blocked,
            next_safe_move="Model web portal reference target only.",
        ),
        _artifact_target(
            "source_card_reference_target",
            artifact_type="SOURCE_CARD",
            intended_storage_area="future_source_card_registry",
            path_policy="deterministic source-card id, no raw private body ingestion",
            naming_policy="source_card__workflow_or_lane__stable_id",
            redaction_required=False,
            protected_reference_required=False,
            guardian_review_required=False,
            blocked_material=("raw private body", "unbounded source excerpt", "file rewrite"),
            next_safe_move="Model source-card reference target only.",
        ),
        _artifact_target(
            "receipt_reference_target",
            artifact_type="RECEIPT",
            intended_storage_area="future_receipt_registry",
            path_policy="deterministic receipt target id; writer lane decides actual durable receipt path",
            naming_policy="receipt__workflow_session__step__timestamp",
            redaction_required=False,
            protected_reference_required=False,
            guardian_review_required=False,
            blocked_material=("credentials", "raw private body", "unrelated file paths"),
            next_safe_move="Model receipt reference target only.",
        ),
        _artifact_target(
            "text_confirmation_target",
            artifact_type="TEXT_CONFIRMATION",
            intended_storage_area="future_operator_confirmation_receipt",
            path_policy="deterministic workflow/session/step receipt target",
            naming_policy="operator_confirmation__workflow_session__step__timestamp",
            redaction_required=False,
            protected_reference_required=False,
            guardian_review_required=False,
            blocked_material=("raw protected body", "credentials", "unbounded private detail"),
            next_safe_move="Model text confirmation target only.",
        ),
        _artifact_target(
            "unknown_fail_closed_artifact_target",
            artifact_type="UNKNOWN_FAIL_CLOSED",
            intended_storage_area="none_currently",
            path_policy="fail closed until capture type is classified",
            naming_policy="none",
            redaction_required=True,
            protected_reference_required=True,
            guardian_review_required=True,
            blocked_material=("all unclassified material",),
            next_safe_move="Fail closed.",
        ),
    )


def _path(
    capture_path_id: str,
    *,
    display_title: str,
    world: str,
    lane: str,
    workflow_session_ref: str,
    decision_node_ref: str,
    capture_purpose: str,
    truth_needed: str,
    recommended_capture_method: str,
    operator_goal: str,
    system_can_do_now: tuple[str, ...],
    operator_must_do_now: tuple[str, ...],
    system_future_automation_candidate: bool,
    capture_moment_prompt: str,
    allowed_capture_inputs: tuple[str, ...],
    blocked_capture_inputs: tuple[str, ...],
    target_artifact_type: str,
    target_storage_policy: str,
    protected_evidence_required: bool,
    guardian_review_required: bool,
    receipt_type: str,
    receipt_target: str,
    after_capture_state: str,
    next_step_after_success: str,
    fallback_if_not_available: str,
    next_safe_move: str,
    authority_granted: bool = False,
    blocked_actions: tuple[str, ...] = COMMON_BLOCKED_ACTIONS,
) -> GuidedCapturePath:
    return GuidedCapturePath(
        capture_path_id=capture_path_id,
        display_title=display_title,
        world=world,
        lane=lane,
        workflow_session_ref=workflow_session_ref,
        decision_node_ref=decision_node_ref,
        capture_purpose=capture_purpose,
        truth_needed=truth_needed,
        recommended_capture_method=recommended_capture_method,
        operator_goal=operator_goal,
        system_can_do_now=system_can_do_now,
        operator_must_do_now=operator_must_do_now,
        system_future_automation_candidate=system_future_automation_candidate,
        capture_moment_prompt=capture_moment_prompt,
        allowed_capture_inputs=allowed_capture_inputs,
        blocked_capture_inputs=blocked_capture_inputs,
        target_artifact_type=target_artifact_type,
        target_storage_policy=target_storage_policy,
        protected_evidence_required=protected_evidence_required,
        guardian_review_required=guardian_review_required,
        receipt_type=receipt_type,
        receipt_target=receipt_target,
        after_capture_state=after_capture_state,
        next_step_after_success=next_step_after_success,
        fallback_if_not_available=fallback_if_not_available,
        blocked_actions=blocked_actions,
        authority_granted=authority_granted,
        next_safe_move=next_safe_move,
    )


def default_capture_paths() -> tuple[GuidedCapturePath, ...]:
    return (
        _path(
            "capital_hilton_coupa_po_screen_capture_path",
            display_title="Capital Hilton Coupa / PO Screen Capture Path",
            world="Finance",
            lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_solve_path",
            decision_node_ref="date_discovery_needed",
            capture_purpose="capture protected proof metadata for PO/reference evidence",
            truth_needed="PO/reference metadata or confirmation none exists.",
            recommended_capture_method="GUIDED_SCREENSHOT_CAPTURE",
            operator_goal="Get to the Coupa/PO/reference screen.",
            system_can_do_now=(
                "prepare deterministic destination policy",
                "describe what to capture",
                "model receipt target",
                "model later capture and protected storage when authorized",
            ),
            operator_must_do_now=("navigate manually later under proper authority", "confirm the capture moment"),
            system_future_automation_candidate=True,
            capture_moment_prompt="Is this the Capital Hilton PO/reference screen we should capture?",
            allowed_capture_inputs=("targeted window or region confirmation", "manual reference label"),
            blocked_capture_inputs=("credentials", "full desktop screenshot", "raw portal scrape", "session cookies"),
            target_artifact_type="SCREENSHOT_PROTECTED_REFERENCE",
            target_storage_policy="protected_screenshot_reference_target",
            protected_evidence_required=True,
            guardian_review_required=True,
            receipt_type="GUIDED_CAPTURE_PATH_RECEIPT",
            receipt_target="capital_hilton_coupa_po_capture_receipt_target",
            after_capture_state="protected_review_required_before_proof_completion",
            next_step_after_success="link protected reference to PO/reference proof item",
            fallback_if_not_available="create discovery substep or manual reference entry target",
            next_safe_move="Describe the capture target; do not access Coupa or capture a screenshot.",
        ),
        _path(
            "capital_hilton_rate_source_capture_path",
            display_title="Capital Hilton Rate Source Capture Path",
            world="Finance",
            lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_solve_path",
            decision_node_ref="confirm_rate",
            capture_purpose="capture source for the 400 dollar per gig rate",
            truth_needed="Proof or source for $400/gig rate.",
            recommended_capture_method="SOURCE_CARD_REFERENCE",
            operator_goal="Point to the safest rate source.",
            system_can_do_now=("model source-card target", "model protected evidence reference", "model text confirmation as memory candidate"),
            operator_must_do_now=("choose source type later", "avoid raw private body paste"),
            system_future_automation_candidate=False,
            capture_moment_prompt="Is this the source for the $400/gig rate?",
            allowed_capture_inputs=("source card reference", "protected evidence reference", "email/thread reference", "text confirmation"),
            blocked_capture_inputs=("raw email body", "raw contract body", "unbounded private excerpt"),
            target_artifact_type="SOURCE_CARD",
            target_storage_policy="source_card_reference_target",
            protected_evidence_required=False,
            guardian_review_required=False,
            receipt_type="PROOF_POINTER_RECEIPT",
            receipt_target="capital_hilton_rate_source_receipt_target",
            after_capture_state="rate_source_pointer_ready_for_review",
            next_step_after_success="link source pointer to rate proof item",
            fallback_if_not_available="operator text confirmation becomes memory candidate, not proof",
            next_safe_move="Model the rate source pointer only.",
        ),
        _path(
            "check_engine_diagnostic_screenshot_capture_path",
            display_title="Check Engine Diagnostic Screenshot Capture Path",
            world="Build",
            lane="system_diagnostic",
            workflow_session_ref="check_engine_diagnostic_solve_path",
            decision_node_ref="check_engine_actual_breakage",
            capture_purpose="capture visible diagnostic state",
            truth_needed="Visible error/status state.",
            recommended_capture_method="GUIDED_SCREENSHOT_CAPTURE",
            operator_goal="Show the visible status/error state.",
            system_can_do_now=("model diagnostic screenshot target", "model diagnostic receipt target"),
            operator_must_do_now=("verify this is the relevant diagnostic state later",),
            system_future_automation_candidate=False,
            capture_moment_prompt="Is this the diagnostic state we should capture?",
            allowed_capture_inputs=("targeted app/window region", "diagnostic receipt reference"),
            blocked_capture_inputs=("full desktop screenshot", "unrelated app/window content", "private directories"),
            target_artifact_type="SCREENSHOT_PROTECTED_REFERENCE",
            target_storage_policy="protected_screenshot_reference_target",
            protected_evidence_required=True,
            guardian_review_required=True,
            receipt_type="GUIDED_CAPTURE_PATH_RECEIPT",
            receipt_target="check_engine_diagnostic_screenshot_receipt_target",
            after_capture_state="diagnostic_evidence_ready_for_review",
            next_step_after_success="link diagnostic evidence to check engine step",
            fallback_if_not_available="create diagnostic discovery substep",
            next_safe_move="Model diagnostic capture target only.",
        ),
        _path(
            "chief_terrain_source_note_capture_path",
            display_title="Chief Terrain Source Note Capture Path",
            world="Operations",
            lane="Chief terrain reconciliation",
            workflow_session_ref="chief_terrain_reconciliation_solve_path",
            decision_node_ref="chief_terrain_currentness",
            capture_purpose="link terrain item to source note or generated read-model reference",
            truth_needed="Source note or terrain artifact reference.",
            recommended_capture_method="SOURCE_CARD_REFERENCE",
            operator_goal="Point to the source that explains the terrain item.",
            system_can_do_now=("model source-card reference", "model generated read-model reference"),
            operator_must_do_now=("choose the source label later",),
            system_future_automation_candidate=False,
            capture_moment_prompt="Is this the source that should anchor the terrain item?",
            allowed_capture_inputs=("source-card reference", "generated read-model ref", "receipt reference"),
            blocked_capture_inputs=("raw private note body", "file rewrite", "archive/delete action"),
            target_artifact_type="SOURCE_CARD",
            target_storage_policy="source_card_reference_target",
            protected_evidence_required=False,
            guardian_review_required=False,
            receipt_type="SOURCE_CARD_REFERENCE",
            receipt_target="chief_terrain_source_note_receipt_target",
            after_capture_state="terrain_source_ref_ready_for_reconciliation",
            next_step_after_success="link source ref to terrain reconciliation item",
            fallback_if_not_available="create source discovery substep",
            next_safe_move="Model source-card reference target only.",
        ),
        _path(
            "cassandra_draft_review_capture_path",
            display_title="Cassandra / Clara Draft Review Capture Path",
            world="Communications",
            lane="Cassandra / Clara drafts",
            workflow_session_ref="cassandra_clara_draft_work_mode",
            decision_node_ref="draft_review_state",
            capture_purpose="capture draft review state or operator correction",
            truth_needed="Draft review state or operator correction.",
            recommended_capture_method="OPERATOR_TEXT_CONFIRMATION",
            operator_goal="Confirm whether the draft is okay, needs changes, or should not send.",
            system_can_do_now=("model text confirmation target", "model draft receipt target", "model approval-later state"),
            operator_must_do_now=("review draft content later in an authorized surface",),
            system_future_automation_candidate=False,
            capture_moment_prompt="Is this the draft state we should capture?",
            allowed_capture_inputs=("text confirmation", "structured choice", "draft receipt reference"),
            blocked_capture_inputs=("raw email body", "email dispatch", "recipient payload mutation"),
            target_artifact_type="TEXT_CONFIRMATION",
            target_storage_policy="text_confirmation_target",
            protected_evidence_required=False,
            guardian_review_required=False,
            receipt_type="OPERATOR_CONFIRMATION_RECEIPT",
            receipt_target="cassandra_draft_review_capture_receipt_target",
            after_capture_state="draft_review_state_ready_for_approval_path_later",
            next_step_after_success="link review state to future approval bus",
            fallback_if_not_available="park draft review with reason",
            next_safe_move="Model draft review capture target only.",
        ),
        _path(
            "niles_struna_project_reference_capture_path",
            display_title="Niles / Struna Project Reference Capture Path",
            world="Creative",
            lane="Niles / Struna",
            workflow_session_ref="niles_struna_project_work_mode",
            decision_node_ref="creative_project_context",
            capture_purpose="capture project reference or context marker",
            truth_needed="Creative project reference or source marker.",
            recommended_capture_method="SOURCE_CARD_REFERENCE",
            operator_goal="Point to the project context without losing the creative thread.",
            system_can_do_now=("model source-card reference", "model receipt target"),
            operator_must_do_now=("choose the relevant project marker later",),
            system_future_automation_candidate=False,
            capture_moment_prompt="Is this the project reference we should attach?",
            allowed_capture_inputs=("source-card reference", "receipt reference", "text confirmation"),
            blocked_capture_inputs=("raw project file body", "publish action", "file rewrite"),
            target_artifact_type="SOURCE_CARD",
            target_storage_policy="source_card_reference_target",
            protected_evidence_required=False,
            guardian_review_required=False,
            receipt_type="SOURCE_CARD_REFERENCE",
            receipt_target="niles_struna_project_reference_receipt_target",
            after_capture_state="project_context_ref_ready",
            next_step_after_success="link reference to creative project work mode",
            fallback_if_not_available="park project context gap",
            next_safe_move="Model creative project reference target only.",
        ),
        _path(
            "client_project_delivery_reference_capture_path",
            display_title="Client Project Delivery Reference Capture Path",
            world="Delivery",
            lane="client project delivery",
            workflow_session_ref="client_project_delivery_issue",
            decision_node_ref="delivery_reference_needed",
            capture_purpose="capture delivery proof or project reference",
            truth_needed="Client/project delivery reference.",
            recommended_capture_method="RECEIPT_REFERENCE",
            operator_goal="Point to the delivery reference that supports the next project step.",
            system_can_do_now=("model receipt reference", "model source-card target"),
            operator_must_do_now=("select delivery reference later",),
            system_future_automation_candidate=False,
            capture_moment_prompt="Is this the delivery reference we should attach?",
            allowed_capture_inputs=("receipt reference", "source-card reference", "manual reference entry"),
            blocked_capture_inputs=("raw client private body", "send/submit action", "file upload"),
            target_artifact_type="RECEIPT",
            target_storage_policy="receipt_reference_target",
            protected_evidence_required=False,
            guardian_review_required=False,
            receipt_type="RECEIPT_REFERENCE",
            receipt_target="client_project_delivery_reference_receipt_target",
            after_capture_state="delivery_reference_ready_for_review",
            next_step_after_success="link delivery reference to project step",
            fallback_if_not_available="create delivery discovery substep",
            next_safe_move="Model delivery reference target only.",
        ),
    )


def default_capture_moments() -> tuple[GuidedCaptureMoment, ...]:
    return tuple(
        GuidedCaptureMoment(
            capture_moment_id=f"{path.capture_path_id}_moment",
            capture_path_ref=path.capture_path_id,
            display_prompt=path.capture_moment_prompt,
            what_operator_should_verify=(
                "this is the intended evidence or reference",
                "no credentials are visible",
                "no unrelated private content is visible",
                "targeted window or region is enough; full desktop is not needed",
            ),
            ready_phrase="Is this the thing we are supposed to capture?",
            confirm_button_label="Yes, this is it",
            cancel_button_label="Cancel",
            not_the_right_thing_label="Not the right thing",
            system_pre_capture_checks=(
                "verify capture path is classified",
                "verify target artifact policy exists",
                "verify blocked materials are not present",
                "verify Guardian review requirement is known",
            ),
            system_capture_actions_if_authorized=(
                "future lane captures targeted artifact",
                "future lane computes hash",
                "future lane stores protected reference if required",
            ),
            system_post_capture_actions_if_authorized=(
                "future lane writes receipt",
                "future lane links proof item and workflow step",
                "future lane advances or quiets step when policy allows",
            ),
            capture_authority_currently_granted=False,
            next_safe_move="Preview the capture moment only; do not capture.",
        )
        for path in default_capture_paths()
    )


def default_capture_outcomes() -> tuple[GuidedCaptureOutcome, ...]:
    return (
        GuidedCaptureOutcome(
            outcome_id="capital_hilton_coupa_po_capture_success_target",
            capture_path_ref="capital_hilton_coupa_po_screen_capture_path",
            outcome_type="CAPTURE_SUCCESS_RECEIPT_TARGET",
            would_create_artifact=True,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=True,
            would_trigger_guardian_review=True,
            would_advance_workflow=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model protected capture success target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="capital_hilton_coupa_po_not_available",
            capture_path_ref="capital_hilton_coupa_po_screen_capture_path",
            outcome_type="NEEDS_DISCOVERY",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=True,
            would_trigger_guardian_review=False,
            would_advance_workflow=False,
            would_quiet_step=False,
            would_create_discovery_substep=True,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model discovery substep target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="capital_hilton_rate_source_success_target",
            capture_path_ref="capital_hilton_rate_source_capture_path",
            outcome_type="CAPTURE_SUCCESS_RECEIPT_TARGET",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=True,
            would_trigger_guardian_review=False,
            would_advance_workflow=True,
            would_quiet_step=True,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model source pointer target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="check_engine_diagnostic_capture_success_target",
            capture_path_ref="check_engine_diagnostic_screenshot_capture_path",
            outcome_type="CAPTURE_SUCCESS_RECEIPT_TARGET",
            would_create_artifact=True,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=True,
            would_trigger_guardian_review=True,
            would_advance_workflow=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model diagnostic capture target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="chief_terrain_source_note_success_target",
            capture_path_ref="chief_terrain_source_note_capture_path",
            outcome_type="CAPTURE_SUCCESS_RECEIPT_TARGET",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=True,
            would_trigger_guardian_review=False,
            would_advance_workflow=True,
            would_quiet_step=True,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model terrain source reference target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="cassandra_draft_review_capture_success_target",
            capture_path_ref="cassandra_draft_review_capture_path",
            outcome_type="CAPTURE_SUCCESS_RECEIPT_TARGET",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=False,
            would_trigger_guardian_review=False,
            would_advance_workflow=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model draft review receipt target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="coupa_po_automation_candidate_created_target",
            capture_path_ref="capital_hilton_coupa_po_screen_capture_path",
            outcome_type="AUTOMATION_CANDIDATE_CREATED",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=False,
            would_trigger_guardian_review=True,
            would_advance_workflow=False,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_automation_candidate=True,
            current_execution_authority=False,
            next_safe_move="Model future automation candidate only; no authority.",
        ),
        GuidedCaptureOutcome(
            outcome_id="capture_cancelled_target",
            capture_path_ref="app_wide",
            outcome_type="CAPTURE_CANCELLED",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=False,
            would_trigger_guardian_review=False,
            would_advance_workflow=False,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model cancel receipt target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="not_the_right_thing_target",
            capture_path_ref="app_wide",
            outcome_type="NOT_THE_RIGHT_THING",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=False,
            would_trigger_guardian_review=False,
            would_advance_workflow=False,
            would_quiet_step=False,
            would_create_discovery_substep=True,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model correction/discovery target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="capture_parked_target",
            capture_path_ref="app_wide",
            outcome_type="PARKED",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=False,
            would_trigger_guardian_review=False,
            would_advance_workflow=False,
            would_quiet_step=True,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model parked capture target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="protected_review_required_target",
            capture_path_ref="app_wide",
            outcome_type="PROTECTED_REVIEW_REQUIRED",
            would_create_artifact=False,
            would_create_receipt=True,
            would_link_to_workflow_step=True,
            would_link_to_proof_item=True,
            would_trigger_guardian_review=True,
            would_advance_workflow=False,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Model Guardian review target only.",
        ),
        GuidedCaptureOutcome(
            outcome_id="unknown_fail_closed_outcome_target",
            capture_path_ref="unknown",
            outcome_type="UNKNOWN_FAIL_CLOSED",
            would_create_artifact=False,
            would_create_receipt=False,
            would_link_to_workflow_step=False,
            would_link_to_proof_item=False,
            would_trigger_guardian_review=True,
            would_advance_workflow=False,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_automation_candidate=False,
            current_execution_authority=False,
            next_safe_move="Fail closed.",
        ),
    )


def default_privacy_guards() -> tuple[CapturePrivacyGuard, ...]:
    return (
        CapturePrivacyGuard(
            guard_id="full_desktop_screenshot_leakage",
            risk_surface="full desktop screenshot leakage",
            risk_description="Full desktop capture may expose unrelated private apps, paths, or notifications.",
            required_guardrail="Prefer targeted window/region capture over full desktop.",
            blocked_capture_scope=("full desktop", "all monitors", "unrelated windows"),
            allowed_capture_scope=("targeted window or region", "cropped evidence area", "metadata-only reference"),
            redaction_required=True,
            guardian_review_required=True,
            next_safe_move="Stop or narrow capture if targeted scope is unavailable.",
        ),
        CapturePrivacyGuard(
            guard_id="browser_tab_leakage",
            risk_surface="browser tab leakage",
            risk_description="Tabs, URLs, bookmarks, and adjacent pages may reveal unrelated private context.",
            required_guardrail="Capture only the relevant portal area after unrelated tabs are out of scope.",
            blocked_capture_scope=("tab strip", "bookmark bar", "unrelated browser windows"),
            allowed_capture_scope=("targeted portal content region", "protected web portal reference"),
            redaction_required=True,
            guardian_review_required=True,
            next_safe_move="Do not capture if browser context cannot be bounded.",
        ),
        CapturePrivacyGuard(
            guard_id="credential_field_leakage",
            risk_surface="credential field leakage",
            risk_description="Login fields, password managers, keys, and account selectors must never be captured.",
            required_guardrail="Credentials must never be captured; stop if visible.",
            blocked_capture_scope=("password fields", "API keys", "credential manager", "account secrets"),
            allowed_capture_scope=("post-login noncredential evidence area if future authority exists",),
            redaction_required=True,
            guardian_review_required=True,
            next_safe_move="Stop capture and require operator/Guardian decision.",
        ),
        CapturePrivacyGuard(
            guard_id="session_cookie_token_leakage",
            risk_surface="session cookie/token leakage",
            risk_description="Developer tools, URLs, headers, and cookies can leak session authority.",
            required_guardrail="Never capture tokens, cookies, headers, or developer tools.",
            blocked_capture_scope=("session cookies", "tokens", "headers", "developer tools"),
            allowed_capture_scope=("ordinary page evidence region with no tokens visible",),
            redaction_required=True,
            guardian_review_required=True,
            next_safe_move="Stop capture if session material is visible.",
        ),
        CapturePrivacyGuard(
            guard_id="bank_check_remit_leakage",
            risk_surface="bank/check/remit leakage",
            risk_description="Payment routing, bank, check, and remit data require protected handling.",
            required_guardrail="Use metadata-only protected reference unless a future protected lane authorizes more.",
            blocked_capture_scope=("bank account numbers", "routing numbers", "check images", "remit full body"),
            allowed_capture_scope=("redacted protected reference metadata",),
            redaction_required=True,
            guardian_review_required=True,
            next_safe_move="Use protected reference or stop.",
        ),
        CapturePrivacyGuard(
            guard_id="raw_customer_private_data_leakage",
            risk_surface="raw customer/private data leakage",
            risk_description="Raw customer or private bodies must not be pulled into default read-models.",
            required_guardrail="Keep metadata-only by default and use protected reference policy.",
            blocked_capture_scope=("raw customer body", "raw private body", "unbounded excerpts"),
            allowed_capture_scope=("metadata-only reference", "redacted protected reference"),
            redaction_required=True,
            guardian_review_required=True,
            next_safe_move="Stop or route to protected evidence policy.",
        ),
        CapturePrivacyGuard(
            guard_id="unrelated_app_window_leakage",
            risk_surface="unrelated app/window leakage",
            risk_description="Other apps/windows may disclose unrelated work or private content.",
            required_guardrail="Only targeted window/region capture is acceptable.",
            blocked_capture_scope=("unrelated app windows", "notifications", "desktop background paths"),
            allowed_capture_scope=("single relevant app/window region",),
            redaction_required=True,
            guardian_review_required=True,
            next_safe_move="Narrow the capture or cancel.",
        ),
        CapturePrivacyGuard(
            guard_id="private_directory_path_exposure",
            risk_surface="accidental file path/private directory exposure",
            risk_description="Private directory paths can reveal sensitive client or personal context.",
            required_guardrail="Avoid path bars and use stable artifact refs instead of raw paths.",
            blocked_capture_scope=("private directory path", "full local path", "home directory listing"),
            allowed_capture_scope=("stable artifact reference", "redacted path label"),
            redaction_required=True,
            guardian_review_required=False,
            next_safe_move="Use reference label instead of raw path.",
        ),
    )


def relationship_to_prior_lanes(repo_root: str | Path = ROOT) -> list[dict[str, Any]]:
    root = Path(repo_root)
    relationships = []
    for lane_id, ref in PRIOR_LANE_REFS.items():
        relationships.append(
            {
                "lane_id": lane_id,
                "read_model_ref": ref,
                "observation_status": "OBSERVED" if (root / ref).exists() else "NOT_OBSERVED_OR_PENDING",
                "relationship": "guided capture extends prior deterministic work; it does not duplicate prior content",
            }
        )
    return relationships


def build_guided_capture_protected_evidence_path_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    capture_paths = [asdict(item) for item in default_capture_paths()]
    capture_moments = [asdict(item) for item in default_capture_moments()]
    artifact_targets = [asdict(item) for item in default_artifact_targets()]
    outcomes = [asdict(item) for item in default_capture_outcomes()]
    privacy_guards = [asdict(item) for item in default_privacy_guards()]
    prior_lanes = relationship_to_prior_lanes(repo_root)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": f"{READ_MODEL_ID}_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": CONTRACT_STATUS,
        "core_doctrine": {
            "pick_what_is_true": True,
            "if_truth_needs_evidence_guided_capture_path": True,
            "operator_confirms_capture_moments_not_folders": True,
            "system_manages_artifacts_receipts_links_and_workflow_advancement_later": True,
            "capture_paths_are_app_wide_not_finance_only": True,
            "capital_hilton_is_steel_thread_example_not_boundary": True,
            "no_capture_execution_in_this_lane": True,
        },
        "recommended_capture_methods": list(RECOMMENDED_CAPTURE_METHODS),
        "artifact_types": list(ARTIFACT_TYPES),
        "outcome_types": list(OUTCOME_TYPES),
        "guided_capture_path_schema": {
            "structure": "GuidedCapturePath",
            "required_fields": list(REQUIRED_CAPTURE_PATH_FIELDS),
            "unknown_or_missing_result": "UNKNOWN_FAIL_CLOSED",
        },
        "guided_capture_moment_schema": {
            "structure": "GuidedCaptureMoment",
            "required_fields": list(REQUIRED_CAPTURE_MOMENT_FIELDS),
            "capture_authority_default": False,
        },
        "protected_evidence_artifact_target_schema": {
            "structure": "ProtectedEvidenceArtifactTarget",
            "required_fields": list(REQUIRED_ARTIFACT_TARGET_FIELDS),
            "raw_body_allowed_default": False,
            "hash_required_for_captured_files_later": True,
            "receipt_required": True,
        },
        "guided_capture_outcome_schema": {
            "structure": "GuidedCaptureOutcome",
            "required_fields": list(REQUIRED_CAPTURE_OUTCOME_FIELDS),
            "models_outcome_targets_only": True,
            "executes_outcomes_now": False,
        },
        "capture_privacy_guard_schema": {
            "structure": "CapturePrivacyGuard",
            "required_fields": list(REQUIRED_PRIVACY_GUARD_FIELDS),
            "if_risk_cannot_be_bounded": "stop_or_require_operator_guardian_decision",
        },
        "capture_paths": capture_paths,
        "capture_paths_by_id": {item["capture_path_id"]: item for item in capture_paths},
        "capture_moments": capture_moments,
        "capture_moments_by_id": {item["capture_moment_id"]: item for item in capture_moments},
        "artifact_targets": artifact_targets,
        "artifact_targets_by_id": {item["artifact_target_id"]: item for item in artifact_targets},
        "capture_outcomes": outcomes,
        "capture_outcomes_by_id": {item["outcome_id"]: item for item in outcomes},
        "privacy_guards": privacy_guards,
        "privacy_guards_by_id": {item["guard_id"]: item for item in privacy_guards},
        "relationship_to_prior_lanes": prior_lanes,
        "future_non_authority_flags": dict(FUTURE_NON_AUTHORITY_FLAGS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_actual_capture": True,
            "does_not_implement_screenshot_buttons": True,
            "does_not_write_files": True,
            "does_not_create_file_pickers": True,
            "does_not_access_browser_coupa_email_accounts": True,
            "does_not_persist_operator_answers": True,
            "does_not_refresh_stable_map": True,
            "may_capture_screenshot_now": False,
            "may_write_protected_evidence_now": False,
            "may_write_receipt_now": False,
            "may_write_workflow_state_now": False,
        },
        "machine_proof": {
            "guided_capture_path_model_present": True,
            "capture_moment_model_present": True,
            "artifact_target_model_present": True,
            "capture_outcome_model_present": True,
            "privacy_guards_present": True,
            "capture_path_count": len(capture_paths),
            "capture_moment_count": len(capture_moments),
            "artifact_target_count": len(artifact_targets),
            "outcome_count": len(outcomes),
            "privacy_guard_count": len(privacy_guards),
            "capital_hilton_coupa_po_example_present": any(
                item["capture_path_id"] == "capital_hilton_coupa_po_screen_capture_path"
                for item in capture_paths
            ),
            "app_wide_examples_present": all(
                capture_path_id in {item["capture_path_id"] for item in capture_paths}
                for capture_path_id in {
                    "check_engine_diagnostic_screenshot_capture_path",
                    "chief_terrain_source_note_capture_path",
                    "cassandra_draft_review_capture_path",
                    "niles_struna_project_reference_capture_path",
                    "client_project_delivery_reference_capture_path",
                }
            ),
            "targeted_capture_preferred_over_full_desktop": any(
                "full desktop" in item["blocked_capture_scope"]
                and any("targeted window or region" in scope for scope in item["allowed_capture_scope"])
                for item in privacy_guards
            ),
            "credentials_capture_blocked": any(
                "credential" in " ".join(item["blocked_capture_scope"]).lower() for item in privacy_guards
            ),
            "raw_body_capture_blocked": all(item["raw_body_allowed"] is False for item in artifact_targets),
            "capture_authority_currently_false": all(
                item["capture_authority_currently_granted"] is False for item in capture_moments
            ),
            "outcome_execution_authority_false": all(
                item["current_execution_authority"] is False for item in outcomes
            ),
            "capture_path_authority_false": all(item["authority_granted"] is False for item in capture_paths),
            "future_automation_candidate_does_not_grant_authority": (
                FUTURE_NON_AUTHORITY_FLAGS["future_flags_grant_current_authority"] is False
                and all(item["authority_granted"] is False for item in capture_paths)
            ),
            "prior_lane_ref_count": len(prior_lanes),
            "all_authority_flags_false": _all_authority_flags_false(),
            "action_authority_granted": False,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_guided_capture_operator_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    coupa_path = payload["capture_paths_by_id"]["capital_hilton_coupa_po_screen_capture_path"]
    lines = [
        "# Guided Capture / Protected Evidence Path Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Guided capture means OpenClaw gets Winship as close as safely possible to the evidence moment, then asks a simple question: is this the thing we are supposed to capture?",
        "",
        "Winship should not manage folders, filenames, proof links, receipt paths, or downstream state. The operator confirms the capture moment. A later authorized lane would handle the artifact, hash, protected reference, receipt, proof link, and workflow advancement.",
        "",
        "This prompt does not capture screenshots, write files, create file pickers, access Coupa or a browser, persist answers, write protected evidence, write receipts, or refresh the stable map.",
        "",
        "## Capture Models",
        "",
        "- `GuidedCapturePath`: what truth is needed, what capture method is recommended, what the operator does, what the system would do later, and what remains blocked.",
        "- `GuidedCaptureMoment`: the safe confirmation moment: confirm, not yet, cancel, park, or request help later.",
        "- `ProtectedEvidenceArtifactTarget`: deterministic storage, naming, hash, receipt, redaction, raw-body, and Guardian-review policy.",
        "- `GuidedCaptureOutcome`: what would happen after success, cancel, not-right, discovery, protected review, park, or automation candidate.",
        "",
        "## Capital Hilton Coupa / PO",
        "",
        f"- Truth needed: {coupa_path['truth_needed']}",
        f"- Operator goal: {coupa_path['operator_goal']}",
        f"- Capture moment: {coupa_path['capture_moment_prompt']}",
        "- OpenClaw can currently prepare policy, describe the target, and model a receipt target.",
        "- OpenClaw cannot log in, store credentials, scrape the portal, submit, mutate anything, or capture now.",
        "",
        "## Privacy Guardrails",
        "",
        "- Prefer targeted window or region capture over full desktop.",
        "- Credentials, session cookies/tokens, bank/check/remit details, raw customer/private bodies, unrelated apps/windows, and private directory paths are blocked by default.",
        "- Sensitive portal captures require protected evidence policy and Guardian review.",
        "- If the risk cannot be bounded, capture stops or needs operator/Guardian decision.",
        "",
        "## App-Wide Use",
        "",
        "- Check Engine can later capture visible diagnostic state.",
        "- Chief terrain reconciliation can point to source-card or generated read-model refs.",
        "- Cassandra/Clara draft review can capture review state or correction without sending.",
        "- Niles/Struna and client delivery work can attach source-card or receipt references without publishing, sending, or rewriting files.",
        "",
        "## Prompt 4",
        "",
        "- Prompt 4 should add Workflow Session / Channel Projection / Approval Bus contracts so capture, decisions, drafts, channels, and approval refs can project into coherent app sessions later.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Capture paths: `{proof['capture_path_count']}`.",
        f"- Capture moments: `{proof['capture_moment_count']}`.",
        f"- Artifact targets: `{proof['artifact_target_count']}`.",
        f"- Outcomes: `{proof['outcome_count']}`.",
        f"- Privacy guards: `{proof['privacy_guard_count']}`.",
        f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_guided_capture_protected_evidence_path_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> GuidedCaptureExportResult:
    payload = build_guided_capture_protected_evidence_path_contract(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_guided_capture_operator_markdown(payload), encoding="utf-8")
    return GuidedCaptureExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        capture_path_count=len(payload["capture_paths"]),
        capture_moment_count=len(payload["capture_moments"]),
        artifact_target_count=len(payload["artifact_targets"]),
        outcome_count=len(payload["capture_outcomes"]),
        privacy_guard_count=len(payload["privacy_guards"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Guided Capture / Protected Evidence Path Contract.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_guided_capture_protected_evidence_path_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "capture_path_count": result.capture_path_count,
        "capture_moment_count": result.capture_moment_count,
        "artifact_target_count": result.artifact_target_count,
        "outcome_count": result.outcome_count,
        "privacy_guard_count": result.privacy_guard_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Guided Capture / Protected Evidence Path Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ARTIFACT_TYPES",
    "AUTHORITY_BOUNDARY",
    "FUTURE_NON_AUTHORITY_FLAGS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "OUTCOME_TYPES",
    "READ_MODEL_ID",
    "RECOMMENDED_CAPTURE_METHODS",
    "REQUIRED_ARTIFACT_TARGET_FIELDS",
    "REQUIRED_CAPTURE_MOMENT_FIELDS",
    "REQUIRED_CAPTURE_OUTCOME_FIELDS",
    "REQUIRED_CAPTURE_PATH_FIELDS",
    "REQUIRED_PRIVACY_GUARD_FIELDS",
    "SCHEMA_VERSION",
    "build_guided_capture_protected_evidence_path_contract",
    "default_artifact_targets",
    "default_capture_moments",
    "default_capture_outcomes",
    "default_capture_paths",
    "default_privacy_guards",
    "export_guided_capture_protected_evidence_path_contract",
    "format_guided_capture_operator_markdown",
    "relationship_to_prior_lanes",
    "stable_json",
]
