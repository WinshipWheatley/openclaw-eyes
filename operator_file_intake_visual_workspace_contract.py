"""Operator File Intake + Visual Workspace Contract v0.

This deterministic read-model defines how operator-provided or referenced
materials become governed source refs and visual workspace requests. It is a
contract/read-model only: it does not ingest file bodies, extract raw private
content, automate apps, mutate files, capture screens, call models, dispatch
agents, access external systems, modify Mission Control Swift, run Mac
sync/import, or push.
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

SCHEMA_VERSION = "operator_file_intake_visual_workspace_contract_v0"
READ_MODEL_ID = "operator_file_intake_visual_workspace_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_FILE_INTAKE_VISUAL_WORKSPACE_CONTRACT"

SUPPORTED_FILE_TYPES = (
    "spreadsheet",
    "pdf",
    "doc",
    "rich_text_doc",
    "image",
    "screenshot",
    "audio_session_or_project_metadata",
    "video_project_metadata",
    "invoice_artifact",
    "contract_or_legal_doc",
    "email_thread_reference",
    "calendar_or_event_reference",
    "database_or_export_file",
    "folder_or_project_capsule",
    "web_or_downloaded_source",
    "unknown_file_fail_closed",
)

INTAKE_MODES = (
    "REFERENCE_ONLY",
    "METADATA_ONLY",
    "SAFE_EXTRACT_REQUESTED",
    "PROTECTED_EVIDENCE_REFERENCE",
    "VISUAL_WORKSPACE_SOURCE",
    "TRANSIENT_SESSION_ONLY",
    "ENCRYPTED_OR_PROTECTED",
    "PUBLIC_OR_SHAREABLE",
    "FUTURE_FULL_INGEST_GATED",
)

VISUAL_MODES = (
    "SHOW_RELEVANT_FILES",
    "SHOW_SPREADSHEET_AND_DOC",
    "SHOW_WORKFLOW_STATE",
    "SHOW_SONG_SESSION_CONTEXT",
    "SHOW_INVOICE_PACKET",
    "SHOW_PROOF_PACKAGE",
    "SHOW_TIMELINE",
    "SHOW_AGENT_PROGRESS",
    "SHOW_SOURCE_COMPARISON",
    "SHOW_TASK_BOARD",
    "SHOW_ARTIFACT_PREVIEW",
    "SHOW_PROJECT_MAP",
    "SHOW_RELATIONSHIP_GRAPH",
    "SHOW_CHECKLIST_OR_WORKFLOW_CHAIN",
    "SHOW_MEDIA_SESSION_OVERVIEW",
    "SHOW_BEFORE_AFTER_REVIEW",
    "CHAT_ATTACHED_VISUAL_CARD",
    "EXTERNAL_APP_HANDOFF_PREVIEW",
    "UNKNOWN_NEEDS_FRAMING",
)

TARGET_SURFACES = (
    "mac_chat",
    "mac_visual_workspace",
    "future_split_view",
    "future_external_app_view",
    "developer_diagnostics",
    "future_mobile",
    "future_voice",
)

ARTIFACT_ROLES = (
    "PRIMARY_SPREADSHEET",
    "RELATED_RICH_TEXT_DOC",
    "SOURCE_PDF",
    "INVOICE_ARTIFACT",
    "SCREENSHOT_PROOF",
    "AUDIO_PROJECT_METADATA",
    "VIDEO_PROJECT_METADATA",
    "CONTRACT_SOURCE",
    "EMAIL_THREAD_REFERENCE",
    "CALENDAR_EVENT_REFERENCE",
    "DATABASE_EXPORT",
    "FOLDER_OR_PROJECT_CAPSULE",
    "TASK_STATE_CARD",
    "TIMELINE_OR_HISTORY",
    "AGENT_PROGRESS",
    "WARNING_OR_LOCK",
    "UNKNOWN",
)

OPEN_MODES = (
    "READ_ONLY_PREVIEW",
    "OPEN_IN_MAC_APP_GATED",
    "SHOW_METADATA_ONLY",
    "PROTECTED_REFERENCE_ONLY",
    "FUTURE_EDIT_GATED",
    "FUTURE_EXPORT_GATED",
    "FUTURE_PUBLISH_GATED",
)

TARGET_APPS = (
    "Mission Control",
    "Logic Pro",
    "Ableton",
    "Final Cut Pro",
    "DaVinci Resolve",
    "Mail",
    "Calendar",
    "Contacts",
    "Messages",
    "Telegram Desktop",
    "Finder",
    "Browser",
    "unknown_app_fail_closed",
)

AUTOMATION_MODES = (
    "SHOW_OR_PREVIEW",
    "INSPECT_OR_READ",
    "EXTRACT_METADATA",
    "DRAFT",
    "PREPARE_PACKAGE",
    "OPEN_APP",
    "MUTATE_FILE_GATED",
    "SEND_OR_SUBMIT_GATED",
    "APPROVE_GATED",
    "PUBLISH_OR_EXPORT_GATED",
)

VISUAL_TRANSITION_MODES = (
    "CHAT_ONLY",
    "BACKGROUND_WORKING",
    "VISUAL_WORKSPACE",
    "APP_CONTROL_PREVIEW",
    "PROOF_VIEW",
    "COMPLETION_VIEW",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "RAW_FILE_BODY_TO_LLM",
    "PRIVATE_FILE_PATH_VISIBLE",
    "UNSCOPED_FILE_INGESTION",
    "BROAD_FILESYSTEM_SCAN",
    "UNSAFE_APP_AUTOMATION",
    "MUTATION_WITHOUT_APPROVAL",
    "MISSING_BACKUP_OR_RECEIPT",
    "PROTECTED_FILE_WITHOUT_GUARDIAN",
    "STALE_SOURCE_REF",
    "WRONG_APP_OR_WORKER_TARGET",
    "UNKNOWN_FILE_TYPE",
    "UNBOUNDED_FOLDER_INGEST",
    "VISUAL_WORKSPACE_PRETENDS_TO_BE_PROOF",
    "SEND_EXPORT_PUBLISH_WITHOUT_APPROVAL",
    "HIDDEN_APP_AUTOMATION",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_file_ingestion_allowed": False,
    "live_raw_body_extraction_allowed": False,
    "live_app_automation_allowed": False,
    "live_file_mutation_allowed": False,
    "live_external_app_control_allowed": False,
    "live_email_send_allowed": False,
    "live_project_edit_allowed": False,
    "live_screenshot_capture_allowed": False,
    "live_screen_recording_allowed": False,
    "live_export_allowed": False,
    "live_publish_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

SOURCE_REF_PRIVACY_POLICY = (
    "Use safe display labels instead of full private paths.",
    "Store source refs and fingerprints, not raw file bodies, in normal generated read-models.",
    "Route protected or sensitive sources through protected evidence posture.",
    "Fail closed on broad folder ingestion or unknown file type.",
)

COMMON_PROHIBITED_USE = (
    "raw body to LLM",
    "hidden app automation",
    "external send or submit",
    "file mutation without approval",
    "broad filesystem scan",
)


@dataclass(frozen=True)
class OperatorFileIntakeContract:
    contract_id: str
    doctrine: tuple[str, ...]
    supported_file_types: tuple[str, ...]
    intake_modes: tuple[str, ...]
    source_reference_policy: tuple[str, ...]
    raw_body_policy: tuple[str, ...]
    extraction_policy: tuple[str, ...]
    pii_policy: tuple[str, ...]
    protected_evidence_policy: tuple[str, ...]
    visual_workspace_policy: tuple[str, ...]
    automation_boundary_policy: tuple[str, ...]
    worker_routing_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorFileSourceRef:
    source_ref_id: str
    original_filename: str
    file_type: str
    source_surface: str
    local_path_policy: str
    safe_display_label: str
    privacy_class: str
    sensitivity_class: str
    allowed_use: tuple[str, ...]
    prohibited_use: tuple[str, ...]
    extraction_status: str
    protected_ref_required: bool
    hash_or_fingerprint_policy: str
    source_card_ref: str
    stale_or_current_status: str
    next_safe_move: str


@dataclass(frozen=True)
class VisualWorkspaceRequest:
    workspace_request_id: str
    source_chat_ref: str
    operator_goal: str
    visual_mode: str
    requested_artifacts: tuple[str, ...]
    related_artifacts: tuple[str, ...]
    workspace_bundle_ref: str
    target_surface: str
    target_worker_type: str
    target_machine: str
    display_requirements: tuple[str, ...]
    interaction_requirements: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class VisualWorkspaceArtifactBinding:
    binding_id: str
    workspace_request_ref: str
    artifact_role: str
    source_ref: str
    display_label: str
    display_priority: int
    open_mode: str
    edit_allowed: bool
    mutation_allowed: bool
    proof_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class VisualWorkspaceBundle:
    bundle_id: str
    workspace_request_ref: str
    primary_artifact: str
    related_notes: tuple[str, ...]
    proof_or_source_docs: tuple[str, ...]
    timeline_or_history: tuple[str, ...]
    task_status: tuple[str, ...]
    next_actions: tuple[str, ...]
    agent_progress: tuple[str, ...]
    warnings_or_locks: tuple[str, ...]
    source_refs: tuple[str, ...]
    privacy_boundary: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class AppAutomationRequest:
    automation_request_id: str
    operator_goal: str
    target_app: str
    target_machine: str
    automation_mode: str
    command_sequence_summary: str
    allowed_commands: tuple[str, ...]
    forbidden_commands: tuple[str, ...]
    required_operator_confirmation: bool
    required_backup_or_receipt: bool
    dry_run_required: bool
    mutation_allowed: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class VisualModeTransition:
    transition_id: str
    from_mode: str
    to_mode: str
    trigger_phrase: str
    operator_intent: str
    required_context: tuple[str, ...]
    visual_output: str
    worker_route: str
    next_safe_move: str


@dataclass(frozen=True)
class FileVisualWorkspaceBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorFileIntakeVisualWorkspaceElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_file_intake_works: str
    how_visual_workspace_requests_work: str
    how_app_automation_is_gated: str
    how_agents_see_file_refs: str
    how_worker_routing_applies: str
    next_safe_move: str


REQUIRED_CONTRACT_FIELDS = tuple(OperatorFileIntakeContract.__dataclass_fields__.keys())
REQUIRED_SOURCE_REF_FIELDS = tuple(OperatorFileSourceRef.__dataclass_fields__.keys())
REQUIRED_WORKSPACE_REQUEST_FIELDS = tuple(VisualWorkspaceRequest.__dataclass_fields__.keys())
REQUIRED_ARTIFACT_BINDING_FIELDS = tuple(VisualWorkspaceArtifactBinding.__dataclass_fields__.keys())
REQUIRED_WORKSPACE_BUNDLE_FIELDS = tuple(VisualWorkspaceBundle.__dataclass_fields__.keys())
REQUIRED_AUTOMATION_REQUEST_FIELDS = tuple(AppAutomationRequest.__dataclass_fields__.keys())
REQUIRED_TRANSITION_FIELDS = tuple(VisualModeTransition.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(FileVisualWorkspaceBlocker.__dataclass_fields__.keys())
REQUIRED_REPORT_FIELDS = tuple(OperatorFileIntakeVisualWorkspaceElioperatorReport.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "operator_file_intake_contract": {"required_fields": list(REQUIRED_CONTRACT_FIELDS)},
        "operator_file_source_ref": {"required_fields": list(REQUIRED_SOURCE_REF_FIELDS)},
        "visual_workspace_request": {"required_fields": list(REQUIRED_WORKSPACE_REQUEST_FIELDS)},
        "visual_workspace_artifact_binding": {"required_fields": list(REQUIRED_ARTIFACT_BINDING_FIELDS)},
        "visual_workspace_bundle": {"required_fields": list(REQUIRED_WORKSPACE_BUNDLE_FIELDS)},
        "app_automation_request": {"required_fields": list(REQUIRED_AUTOMATION_REQUEST_FIELDS)},
        "visual_mode_transition": {"required_fields": list(REQUIRED_TRANSITION_FIELDS)},
        "file_visual_workspace_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "operator_file_intake_visual_workspace_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def _local_authority_boundary() -> dict[str, bool]:
    return dict(AUTHORITY_BOUNDARY)


def build_contract() -> OperatorFileIntakeContract:
    return OperatorFileIntakeContract(
        contract_id="operator_file_intake_visual_workspace_contract_v0",
        doctrine=(
            "Chat is the operator command surface.",
            "Files are source materials and become governed source refs.",
            "Raw private bodies do not go to LLMs by default.",
            "Agents see source refs, summaries, and allowed extracts.",
            "Visual workspace requests are explicit operator intent.",
            "Visual workspace is representation, not proof by itself.",
            "Mutation and automation require scoped packages, approval, backup or receipt posture, and readbacks.",
            "Truth remains receipts, source refs, hashes or fingerprints, approved extracts, and readbacks.",
        ),
        supported_file_types=SUPPORTED_FILE_TYPES,
        intake_modes=INTAKE_MODES,
        source_reference_policy=SOURCE_REF_PRIVACY_POLICY,
        raw_body_policy=(
            "Raw bodies are not ingested by default.",
            "Normal read-models contain metadata, source refs, safe labels, and hash/fingerprint policy only.",
            "Raw private body extraction requires a future governed extraction rail.",
            "Unknown or broad source material fails closed.",
        ),
        extraction_policy=(
            "Safe extracts must be separately requested and scoped.",
            "Protected or sensitive extracts require protected evidence and Guardian posture.",
            "Extraction output must be summarized or tokenized before model context unless explicitly approved.",
        ),
        pii_policy=(
            "Do not expose raw email bodies, private full paths, account identifiers, payment references, or protected bodies.",
            "Use tokenized refs and safe labels in operator cards.",
            "Run PII and private-body scans over generated outputs.",
        ),
        protected_evidence_policy=(
            "Sensitive screenshots, contracts, emails, and proof materials can become protected refs.",
            "Protected refs may be displayed as safe labels while raw bodies remain hidden.",
            "Guardian review may be required before protected source material is used for decisions.",
        ),
        visual_workspace_policy=(
            "A visual workspace is requested explicitly by the operator.",
            "A workspace can bundle multiple related source refs, notes, task state, proof refs, warnings, and next actions.",
            "Mac-side visual display routes to MAC_CODEX; backend proof/source packaging routes to PC_CODEX.",
            "Visual display does not prove completion or source truth by itself.",
        ),
        automation_boundary_policy=(
            "Live app automation is false in this contract.",
            "App open, inspect, mutate, export, publish, send, submit, and approve commands require future gated adapters.",
            "Mutation requires explicit operator approval plus backup or receipt posture.",
            "No arbitrary AppleScript or JXA automation is allowed by default.",
        ),
        worker_routing_policy=(
            "Mac visual workspace and Apple-app display work routes to MAC_CODEX / MAC.",
            "Backend source-ref, proof, package, and read-model work routes to PC_CODEX / PC_WSL.",
            "Design, scouting, and taste audit routes to GEMINI_AGY.",
            "Protected/sensitive proof posture routes to GUARDIAN.",
            "Communications drafting routes to CASSANDRA when gated.",
        ),
        authority_boundary=_local_authority_boundary(),
        next_safe_move="Create source refs and workspace request plans; do not ingest, automate, mutate, or dispatch.",
    )


def source_ref(
    *,
    source_ref_id: str,
    original_filename: str,
    file_type: str,
    safe_display_label: str,
    privacy_class: str = "PRIVATE_METADATA_ONLY",
    sensitivity_class: str = "BUSINESS_OR_CREATIVE_SOURCE",
    source_surface: str = "operator_chat_attachment_or_reference",
    allowed_use: tuple[str, ...] = ("show metadata", "bind into visual workspace", "reference in package plan"),
    extraction_status: str = "NOT_EXTRACTED",
    protected_ref_required: bool = False,
    stale_or_current_status: str = "UNKNOWN_UNTIL_FINGERPRINTED",
) -> OperatorFileSourceRef:
    return OperatorFileSourceRef(
        source_ref_id=source_ref_id,
        original_filename=original_filename,
        file_type=file_type,
        source_surface=source_surface,
        local_path_policy="hidden_in_normal_read_model",
        safe_display_label=safe_display_label,
        privacy_class=privacy_class,
        sensitivity_class=sensitivity_class,
        allowed_use=allowed_use,
        prohibited_use=COMMON_PROHIBITED_USE,
        extraction_status=extraction_status,
        protected_ref_required=protected_ref_required,
        hash_or_fingerprint_policy="fingerprint_required_before_truth_or_mutation_claim",
        source_card_ref=f"source_card:{source_ref_id}",
        stale_or_current_status=stale_or_current_status,
        next_safe_move="Keep this as a governed source ref; request safe extraction only if needed.",
    )


def workspace_request(
    *,
    workspace_request_id: str,
    source_chat_ref: str,
    operator_goal: str,
    visual_mode: str,
    requested_artifacts: tuple[str, ...],
    related_artifacts: tuple[str, ...],
    workspace_bundle_ref: str,
    target_surface: str,
    target_worker_type: str,
    target_machine: str,
    display_requirements: tuple[str, ...],
    interaction_requirements: tuple[str, ...] = ("read-only preview", "collapsed proof/details", "operator can ask follow-up in chat"),
    next_safe_move: str = "Route this visual workspace request as a non-executing package plan.",
) -> VisualWorkspaceRequest:
    return VisualWorkspaceRequest(
        workspace_request_id=workspace_request_id,
        source_chat_ref=source_chat_ref,
        operator_goal=operator_goal,
        visual_mode=visual_mode,
        requested_artifacts=requested_artifacts,
        related_artifacts=related_artifacts,
        workspace_bundle_ref=workspace_bundle_ref,
        target_surface=target_surface,
        target_worker_type=target_worker_type,
        target_machine=target_machine,
        display_requirements=display_requirements,
        interaction_requirements=interaction_requirements,
        authority_boundary=_local_authority_boundary(),
        next_safe_move=next_safe_move,
    )


def artifact_binding(
    *,
    binding_id: str,
    workspace_request_ref: str,
    artifact_role: str,
    source_ref_id: str,
    display_label: str,
    display_priority: int,
    open_mode: str = "READ_ONLY_PREVIEW",
    edit_allowed: bool = False,
    mutation_allowed: bool = False,
    proof_required: bool = False,
    next_safe_move: str = "Show as a safe workspace binding without mutation.",
) -> VisualWorkspaceArtifactBinding:
    return VisualWorkspaceArtifactBinding(
        binding_id=binding_id,
        workspace_request_ref=workspace_request_ref,
        artifact_role=artifact_role,
        source_ref=source_ref_id,
        display_label=display_label,
        display_priority=display_priority,
        open_mode=open_mode,
        edit_allowed=edit_allowed,
        mutation_allowed=mutation_allowed,
        proof_required=proof_required,
        next_safe_move=next_safe_move,
    )


def workspace_bundle(
    *,
    bundle_id: str,
    workspace_request_ref: str,
    primary_artifact: str,
    source_refs: tuple[str, ...],
    related_notes: tuple[str, ...] = (),
    proof_or_source_docs: tuple[str, ...] = (),
    timeline_or_history: tuple[str, ...] = (),
    task_status: tuple[str, ...] = (),
    next_actions: tuple[str, ...] = (),
    agent_progress: tuple[str, ...] = (),
    warnings_or_locks: tuple[str, ...] = (),
) -> VisualWorkspaceBundle:
    return VisualWorkspaceBundle(
        bundle_id=bundle_id,
        workspace_request_ref=workspace_request_ref,
        primary_artifact=primary_artifact,
        related_notes=related_notes,
        proof_or_source_docs=proof_or_source_docs,
        timeline_or_history=timeline_or_history,
        task_status=task_status,
        next_actions=next_actions,
        agent_progress=agent_progress,
        warnings_or_locks=warnings_or_locks,
        source_refs=source_refs,
        privacy_boundary=SOURCE_REF_PRIVACY_POLICY,
        next_safe_move="Render the workspace from source refs and readbacks; do not treat display as proof.",
    )


def app_automation_request(
    *,
    automation_request_id: str,
    operator_goal: str,
    target_app: str,
    target_machine: str,
    automation_mode: str,
    command_sequence_summary: str,
    allowed_commands: tuple[str, ...],
    forbidden_commands: tuple[str, ...],
    required_operator_confirmation: bool = True,
    required_backup_or_receipt: bool = True,
    dry_run_required: bool = True,
    mutation_allowed: bool = False,
    next_safe_move: str = "Create an app boundary package only; do not automate the app.",
) -> AppAutomationRequest:
    return AppAutomationRequest(
        automation_request_id=automation_request_id,
        operator_goal=operator_goal,
        target_app=target_app,
        target_machine=target_machine,
        automation_mode=automation_mode,
        command_sequence_summary=command_sequence_summary,
        allowed_commands=allowed_commands,
        forbidden_commands=forbidden_commands,
        required_operator_confirmation=required_operator_confirmation,
        required_backup_or_receipt=required_backup_or_receipt,
        dry_run_required=dry_run_required,
        mutation_allowed=mutation_allowed,
        authority_boundary=_local_authority_boundary(),
        next_safe_move=next_safe_move,
    )


def visual_transition(
    *,
    transition_id: str,
    from_mode: str,
    to_mode: str,
    trigger_phrase: str,
    operator_intent: str,
    required_context: tuple[str, ...],
    visual_output: str,
    worker_route: str,
    next_safe_move: str,
) -> VisualModeTransition:
    return VisualModeTransition(
        transition_id=transition_id,
        from_mode=from_mode,
        to_mode=to_mode,
        trigger_phrase=trigger_phrase,
        operator_intent=operator_intent,
        required_context=required_context,
        visual_output=visual_output,
        worker_route=worker_route,
        next_safe_move=next_safe_move,
    )


def build_examples() -> dict[str, Any]:
    album_sheet = source_ref(
        source_ref_id="source_ref_album_spreadsheet",
        original_filename="album_spreadsheet.example",
        file_type="spreadsheet",
        safe_display_label="Album spreadsheet",
        sensitivity_class="CREATIVE_SOURCE_METADATA",
    )
    song_doc = source_ref(
        source_ref_id="source_ref_song_rich_text_doc",
        original_filename="song_notes.example",
        file_type="rich_text_doc",
        safe_display_label="Related song notes",
        sensitivity_class="CREATIVE_SOURCE_METADATA",
    )
    album_request = workspace_request(
        workspace_request_id="workspace_request_album_spreadsheet_song_doc",
        source_chat_ref="chat_ref_album_visual_request",
        operator_goal="Show the album spreadsheet and the rich text document that goes with this song.",
        visual_mode="SHOW_SPREADSHEET_AND_DOC",
        requested_artifacts=(album_sheet.source_ref_id,),
        related_artifacts=(song_doc.source_ref_id,),
        workspace_bundle_ref="workspace_bundle_album_spreadsheet_song_doc",
        target_surface="mac_visual_workspace",
        target_worker_type="MAC_CODEX",
        target_machine="MAC",
        display_requirements=("side-by-side read-only preview", "source labels", "no raw body to LLM by default"),
    )
    album_bindings = (
        artifact_binding(
            binding_id="binding_album_primary_spreadsheet",
            workspace_request_ref=album_request.workspace_request_id,
            artifact_role="PRIMARY_SPREADSHEET",
            source_ref_id=album_sheet.source_ref_id,
            display_label="Album spreadsheet",
            display_priority=1,
        ),
        artifact_binding(
            binding_id="binding_album_related_song_doc",
            workspace_request_ref=album_request.workspace_request_id,
            artifact_role="RELATED_RICH_TEXT_DOC",
            source_ref_id=song_doc.source_ref_id,
            display_label="Related song notes",
            display_priority=2,
        ),
    )
    album_bundle = workspace_bundle(
        bundle_id="workspace_bundle_album_spreadsheet_song_doc",
        workspace_request_ref=album_request.workspace_request_id,
        primary_artifact=album_sheet.source_ref_id,
        related_notes=(song_doc.source_ref_id,),
        source_refs=(album_sheet.source_ref_id, song_doc.source_ref_id),
        task_status=("visual workspace requested", "read-only preview only"),
        warnings_or_locks=("No raw body is sent to an LLM by default.", "Edit requires a future gated package."),
    )

    invoice_preview = source_ref(
        source_ref_id="source_ref_capital_hilton_invoice_preview",
        original_filename="capital_hilton_invoice_preview.example",
        file_type="invoice_artifact",
        safe_display_label="Capital Hilton invoice packet preview",
        sensitivity_class="BUSINESS_SOURCE_METADATA",
    )
    invoice_readback = source_ref(
        source_ref_id="source_ref_capital_hilton_router_readback",
        original_filename="capital_hilton_router_readback.example",
        file_type="database_or_export_file",
        safe_display_label="Capital Hilton workflow readback",
        sensitivity_class="BUSINESS_READBACK_METADATA",
    )
    invoice_request = workspace_request(
        workspace_request_id="workspace_request_capital_hilton_invoice_packet",
        source_chat_ref="chat_ref_capital_hilton_invoice_workspace",
        operator_goal="Show what is going on with the Capital Hilton invoice packet.",
        visual_mode="SHOW_INVOICE_PACKET",
        requested_artifacts=(invoice_preview.source_ref_id,),
        related_artifacts=(invoice_readback.source_ref_id,),
        workspace_bundle_ref="workspace_bundle_capital_hilton_invoice_packet",
        target_surface="mac_visual_workspace",
        target_worker_type="MAC_CODEX",
        target_machine="MAC",
        display_requirements=("show invoice packet status", "show missing proof", "show locked send/submit actions"),
    )
    invoice_bundle = workspace_bundle(
        bundle_id="workspace_bundle_capital_hilton_invoice_packet",
        workspace_request_ref=invoice_request.workspace_request_id,
        primary_artifact=invoice_preview.source_ref_id,
        proof_or_source_docs=(invoice_readback.source_ref_id,),
        source_refs=(invoice_preview.source_ref_id, invoice_readback.source_ref_id),
        task_status=("invoice packet visible as metadata", "send and submit remain locked"),
        next_actions=("confirm source refs", "route display work to Mac", "route proof packaging to PC if needed"),
        warnings_or_locks=("No email send.", "No Coupa access.", "No invoice generation."),
    )

    contract_source = source_ref(
        source_ref_id="source_ref_contract_review_source",
        original_filename="contract_review_source.example",
        file_type="contract_or_legal_doc",
        safe_display_label="Contract source document",
        privacy_class="PROTECTED_METADATA_ONLY",
        sensitivity_class="LEGAL_OR_CONTRACT_SOURCE",
        protected_ref_required=True,
    )
    contract_request = workspace_request(
        workspace_request_id="workspace_request_contract_review",
        source_chat_ref="chat_ref_contract_review_workspace",
        operator_goal="Show the contract review workspace.",
        visual_mode="SHOW_SOURCE_COMPARISON",
        requested_artifacts=(contract_source.source_ref_id,),
        related_artifacts=(),
        workspace_bundle_ref="workspace_bundle_contract_review",
        target_surface="mac_visual_workspace",
        target_worker_type="GUARDIAN",
        target_machine="LOCAL_ONLY",
        display_requirements=("protected reference preview", "legal advice authority false", "extract only through governed future rail"),
    )

    video_project = source_ref(
        source_ref_id="source_ref_video_project_metadata",
        original_filename="video_project_metadata.example",
        file_type="video_project_metadata",
        safe_display_label="Video project metadata",
        sensitivity_class="CREATIVE_PROJECT_METADATA",
    )
    video_request = workspace_request(
        workspace_request_id="workspace_request_video_edit_review",
        source_chat_ref="chat_ref_video_review_workspace",
        operator_goal="Prepare a video edit/review workspace.",
        visual_mode="SHOW_TIMELINE",
        requested_artifacts=(video_project.source_ref_id,),
        related_artifacts=(),
        workspace_bundle_ref="workspace_bundle_video_edit_review",
        target_surface="mac_visual_workspace",
        target_worker_type="MAC_CODEX",
        target_machine="MAC",
        display_requirements=("timeline metadata view", "review notes", "no project mutation/export"),
    )

    live_show_event = source_ref(
        source_ref_id="source_ref_live_show_event_plan",
        original_filename="live_show_event_plan.example",
        file_type="calendar_or_event_reference",
        safe_display_label="Live show planning source",
        sensitivity_class="EVENT_PLANNING_METADATA",
    )
    live_show_request = workspace_request(
        workspace_request_id="workspace_request_live_show_planning",
        source_chat_ref="chat_ref_live_show_workspace",
        operator_goal="Show the live show planning checklist and timeline.",
        visual_mode="SHOW_TIMELINE",
        requested_artifacts=(live_show_event.source_ref_id,),
        related_artifacts=(),
        workspace_bundle_ref="workspace_bundle_live_show_planning",
        target_surface="mac_visual_workspace",
        target_worker_type="MAC_CODEX",
        target_machine="MAC",
        display_requirements=("timeline view", "checklist view", "no calendar mutation"),
    )

    client_folder = source_ref(
        source_ref_id="source_ref_client_delivery_capsule",
        original_filename="client_delivery_capsule.example",
        file_type="folder_or_project_capsule",
        safe_display_label="Client delivery capsule",
        sensitivity_class="CLIENT_DELIVERY_METADATA",
        allowed_use=("show capsule metadata", "bind selected source refs", "route proof package"),
    )
    client_delivery_request = workspace_request(
        workspace_request_id="workspace_request_client_delivery",
        source_chat_ref="chat_ref_client_delivery_workspace",
        operator_goal="Show the client delivery workspace.",
        visual_mode="SHOW_TASK_BOARD",
        requested_artifacts=(client_folder.source_ref_id,),
        related_artifacts=(),
        workspace_bundle_ref="workspace_bundle_client_delivery",
        target_surface="mac_visual_workspace",
        target_worker_type="MAC_CODEX",
        target_machine="MAC",
        display_requirements=("task board", "proof/source refs", "no broad folder ingest"),
    )

    debug_log_ref = source_ref(
        source_ref_id="source_ref_debug_log_metadata",
        original_filename="debug_log_excerpt_metadata.example",
        file_type="database_or_export_file",
        safe_display_label="Debug log metadata",
        sensitivity_class="SYSTEM_DEBUG_METADATA",
    )
    debug_request = workspace_request(
        workspace_request_id="workspace_request_bug_debug",
        source_chat_ref="chat_ref_bug_debug_workspace",
        operator_goal="Show the bug/debug workspace and source refs.",
        visual_mode="SHOW_WORKFLOW_STATE",
        requested_artifacts=(debug_log_ref.source_ref_id,),
        related_artifacts=(),
        workspace_bundle_ref="workspace_bundle_bug_debug",
        target_surface="developer_diagnostics",
        target_worker_type="PC_CODEX",
        target_machine="PC_WSL",
        display_requirements=("Work Terrain or Build Cue tie-in", "source refs", "no external action"),
    )

    screenshot_proof = source_ref(
        source_ref_id="source_ref_screenshot_proof",
        original_filename="screenshot_proof.example",
        file_type="screenshot",
        safe_display_label="Screenshot proof",
        privacy_class="PROTECTED_METADATA_ONLY",
        sensitivity_class="PROOF_SOURCE_METADATA",
        protected_ref_required=True,
    )
    protected_proof_request = workspace_request(
        workspace_request_id="workspace_request_protected_proof",
        source_chat_ref="chat_ref_protected_proof_workspace",
        operator_goal="Show the protected proof workspace.",
        visual_mode="SHOW_PROOF_PACKAGE",
        requested_artifacts=(screenshot_proof.source_ref_id,),
        related_artifacts=(),
        workspace_bundle_ref="workspace_bundle_protected_proof",
        target_surface="mac_visual_workspace",
        target_worker_type="GUARDIAN",
        target_machine="LOCAL_ONLY",
        display_requirements=("protected evidence refs", "raw bodies hidden", "Guardian may be required"),
    )

    invoice_artifact = source_ref(
        source_ref_id="source_ref_attached_invoice_artifact",
        original_filename="invoice_artifact.example",
        file_type="invoice_artifact",
        safe_display_label="Attached invoice artifact",
        sensitivity_class="BUSINESS_ARTIFACT_METADATA",
    )
    invoice_artifact_binding = artifact_binding(
        binding_id="binding_invoice_artifact_source",
        workspace_request_ref="workspace_request_invoice_artifact_source",
        artifact_role="INVOICE_ARTIFACT",
        source_ref_id=invoice_artifact.source_ref_id,
        display_label="Invoice artifact",
        display_priority=1,
        proof_required=True,
        next_safe_move="Fingerprint the artifact before any attachment or completion claim.",
    )

    logic_request = app_automation_request(
        automation_request_id="automation_request_logic_show_session_state",
        operator_goal="Open Logic and show me the session state.",
        target_app="Logic Pro",
        target_machine="MAC",
        automation_mode="SHOW_OR_PREVIEW",
        command_sequence_summary="Future Mac-side visual/app request only; no project mutation.",
        allowed_commands=("prepare visual app boundary package", "inspect metadata through future approved adapter"),
        forbidden_commands=("mutate project", "export audio", "record", "delete files", "run hidden automation"),
        required_operator_confirmation=True,
        required_backup_or_receipt=True,
        dry_run_required=True,
        mutation_allowed=False,
    )

    unsafe_mail_request = app_automation_request(
        automation_request_id="automation_request_mail_send_invoice_blocked",
        operator_goal="Open Mail and send this invoice automatically.",
        target_app="Mail",
        target_machine="MAC",
        automation_mode="SEND_OR_SUBMIT_GATED",
        command_sequence_summary="Send authority is requested but blocked until governed email/approval adapter exists.",
        allowed_commands=("show blocked send posture", "prepare future approval requirements"),
        forbidden_commands=("send email", "attach invoice", "open external account", "bypass Guardian approval"),
        required_operator_confirmation=True,
        required_backup_or_receipt=True,
        dry_run_required=True,
        mutation_allowed=False,
        next_safe_move="Block send/export/publish and require governed email plus approval adapter later.",
    )

    mode_transition = visual_transition(
        transition_id="visual_transition_show_me_whats_going_on",
        from_mode="CHAT_ONLY",
        to_mode="VISUAL_WORKSPACE",
        trigger_phrase="Show me what's going on.",
        operator_intent="Move from chat/background explanation into a visual workspace.",
        required_context=("source refs", "current readback", "worker route", "authority boundary"),
        visual_output="A compact workspace card or workspace bundle showing current state, sources, missing items, and locks.",
        worker_route="MAC_CODEX for display, PC_CODEX for source/proof package if needed.",
        next_safe_move="Ask what source or workflow should be shown if the target is ambiguous.",
    )

    return {
        "album_spreadsheet_song_doc": {
            "operator_says": "I'm working on my album spreadsheet. Show me the spreadsheet and the rich text doc that goes with this song.",
            "source_refs": {
                album_sheet.source_ref_id: asdict(album_sheet),
                song_doc.source_ref_id: asdict(song_doc),
            },
            "visual_workspace_request": asdict(album_request),
            "artifact_bindings": {binding.binding_id: asdict(binding) for binding in album_bindings},
            "visual_workspace_bundle": asdict(album_bundle),
            "expected_route": "MAC_CODEX / MAC for visual workspace UI",
            "raw_body_to_llm": False,
        },
        "capital_hilton_invoice_workspace": {
            "operator_says": "Show me what's going on with the Capital Hilton invoice packet.",
            "source_refs": {
                invoice_preview.source_ref_id: asdict(invoice_preview),
                invoice_readback.source_ref_id: asdict(invoice_readback),
            },
            "visual_workspace_request": asdict(invoice_request),
            "artifact_bindings": {
                "binding_capital_hilton_invoice_preview": asdict(
                    artifact_binding(
                        binding_id="binding_capital_hilton_invoice_preview",
                        workspace_request_ref=invoice_request.workspace_request_id,
                        artifact_role="INVOICE_ARTIFACT",
                        source_ref_id=invoice_preview.source_ref_id,
                        display_label="Invoice packet preview",
                        display_priority=1,
                        proof_required=True,
                    )
                ),
                "binding_capital_hilton_router_readback": asdict(
                    artifact_binding(
                        binding_id="binding_capital_hilton_router_readback",
                        workspace_request_ref=invoice_request.workspace_request_id,
                        artifact_role="TASK_STATE_CARD",
                        source_ref_id=invoice_readback.source_ref_id,
                        display_label="Workflow readback",
                        display_priority=2,
                    )
                ),
            },
            "visual_workspace_bundle": asdict(invoice_bundle),
            "pc_backend_role": "PC_CODEX can prepare source/proof package if needed.",
            "send_or_submit_performed": False,
        },
        "legal_contract_review_workspace": {
            "visual_workspace_request": asdict(contract_request),
            "source_ref": asdict(contract_source),
            "legal_advice_authority": False,
            "raw_contract_body_to_llm": False,
            "protected_posture": "Protected reference required before any extract.",
        },
        "video_edit_review_workspace": {
            "visual_workspace_request": asdict(video_request),
            "source_ref": asdict(video_project),
            "expected_route": "MAC_CODEX / MAC for Final Cut or DaVinci display concepts.",
            "project_mutation_or_export_allowed": False,
        },
        "live_show_planning_workspace": {
            "visual_workspace_request": asdict(live_show_request),
            "source_ref": asdict(live_show_event),
            "external_calendar_mutation_allowed": False,
        },
        "client_delivery_workspace": {
            "visual_workspace_request": asdict(client_delivery_request),
            "source_ref": asdict(client_folder),
            "broad_folder_ingest_allowed": False,
        },
        "bug_debug_workspace": {
            "visual_workspace_request": asdict(debug_request),
            "source_ref": asdict(debug_log_ref),
            "route_policy": "PC_CODEX for Repo A/backend source refs, MAC_CODEX for app-side UI or screenshot validation.",
            "external_action_allowed": False,
        },
        "protected_proof_workspace": {
            "visual_workspace_request": asdict(protected_proof_request),
            "source_ref": asdict(screenshot_proof),
            "guardian_may_be_required": True,
            "raw_body_hidden": True,
        },
        "invoice_artifact_source": {
            "source_ref": asdict(invoice_artifact),
            "artifact_binding": asdict(invoice_artifact_binding),
            "hash_or_fingerprint_required": True,
            "send_or_submit_performed": False,
        },
        "screenshot_proof": {
            "source_ref": asdict(screenshot_proof),
            "proof_role": "SCREENSHOT_PROOF",
            "protected_evidence_reference_if_sensitive": True,
            "raw_body_in_normal_read_model": False,
        },
        "app_automation_request": {
            "operator_says": "Open Logic and show me the session state.",
            "app_automation_request": asdict(logic_request),
            "expected_route": "MAC_CODEX / MAC",
            "mutation_allowed": False,
        },
        "unsafe_automation_blocker": {
            "operator_says": "Open Mail and send this invoice automatically.",
            "app_automation_request": asdict(unsafe_mail_request),
            "blocker_type": "SEND_EXPORT_PUBLISH_WITHOUT_APPROVAL",
            "email_send_blocked": True,
            "requires_governed_email_approval_adapter": True,
        },
        "visual_mode_transition": {
            "operator_says": "Show me what's going on.",
            "visual_mode_transition": asdict(mode_transition),
            "expected_transition": "CHAT_ONLY -> VISUAL_WORKSPACE",
        },
    }


def build_blockers() -> tuple[FileVisualWorkspaceBlocker, ...]:
    details = {
        "RAW_FILE_BODY_TO_LLM": (
            "A raw source body would be placed into model context.",
            "Use a source ref, safe summary, or future governed extract instead.",
        ),
        "PRIVATE_FILE_PATH_VISIBLE": (
            "A full private local path would be shown in normal cards or read-models.",
            "Hide the full path and show a safe display label.",
        ),
        "UNSCOPED_FILE_INGESTION": (
            "A file is ingested without declared scope.",
            "Ask what the file is for and create a scoped source ref first.",
        ),
        "BROAD_FILESYSTEM_SCAN": (
            "The request would scan broad folders or drives.",
            "Narrow the scope to named materials or a bounded project capsule.",
        ),
        "UNSAFE_APP_AUTOMATION": (
            "An app automation command lacks an approved adapter and authority boundary.",
            "Keep it as a preview or package plan until the adapter exists.",
        ),
        "MUTATION_WITHOUT_APPROVAL": (
            "A file or project mutation is requested without explicit approval.",
            "Require operator approval, backup or receipt posture, and a future gated adapter.",
        ),
        "MISSING_BACKUP_OR_RECEIPT": (
            "A mutating or app-control action lacks backup or receipt posture.",
            "Add backup/receipt requirements before any future mutation package.",
        ),
        "PROTECTED_FILE_WITHOUT_GUARDIAN": (
            "Protected material would be used without protected evidence posture.",
            "Route through protected refs and Guardian review when needed.",
        ),
        "STALE_SOURCE_REF": (
            "A source ref may not match current file state.",
            "Refresh or fingerprint the source ref before using it as truth.",
        ),
        "WRONG_APP_OR_WORKER_TARGET": (
            "A visual/app task is routed to the wrong worker or machine.",
            "Route Mac visual/app display to MAC_CODEX and backend source/proof work to PC_CODEX.",
        ),
        "UNKNOWN_FILE_TYPE": (
            "The file type cannot be classified safely.",
            "Fail closed and ask the operator to describe the file.",
        ),
        "UNBOUNDED_FOLDER_INGEST": (
            "A folder/project capsule is treated as permission to ingest everything.",
            "Bind only named source refs or metadata until a scoped ingest rail exists.",
        ),
        "VISUAL_WORKSPACE_PRETENDS_TO_BE_PROOF": (
            "A visual workspace is treated as proof by itself.",
            "Use receipts, source refs, fingerprints, and readbacks for truth.",
        ),
        "SEND_EXPORT_PUBLISH_WITHOUT_APPROVAL": (
            "Send, export, publish, or submit is requested without approval gates.",
            "Block the action and require a governed adapter plus approval receipt.",
        ),
        "HIDDEN_APP_AUTOMATION": (
            "An app would be controlled silently or through hidden automation.",
            "Make the app-control scope explicit and gated before any future adapter.",
        ),
        "UNKNOWN_FAIL_CLOSED": (
            "The intake/workspace request cannot be classified.",
            "Fail closed and ask a clarifying question.",
        ),
    }
    return tuple(
        FileVisualWorkspaceBlocker(
            blocker_id=f"file_visual_workspace_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="CRITICAL" if blocker_type == "UNKNOWN_FAIL_CLOSED" else "HIGH",
            elioperator_warning=warning,
            fail_closed=True,
            next_safe_move="Return a human-readable blocker and avoid ingestion, automation, mutation, or dispatch.",
        )
        for blocker_type, (condition, warning) in details.items()
    )


def build_elioperator_report() -> OperatorFileIntakeVisualWorkspaceElioperatorReport:
    return OperatorFileIntakeVisualWorkspaceElioperatorReport(
        report_id="operator_file_intake_visual_workspace_elioperator_report_v0",
        plain_summary="This lets OpenClaw turn operator materials into governed source refs and visual workspace requests.",
        what_this_enables=(
            "Operators can attach or reference source material, ask to see work visually, and let the router choose the "
            "right visual, backend, proof, or app-boundary worker package."
        ),
        what_this_does_not_do_yet=(
            "It does not ingest raw bodies, automate apps, mutate files, capture screens, send email, export, publish, "
            "call models, dispatch agents, or access external systems."
        ),
        how_file_intake_works=(
            "Files become source refs with safe labels, privacy class, sensitivity class, extraction status, and "
            "fingerprint policy. Normal read-models do not include full private paths or raw bodies."
        ),
        how_visual_workspace_requests_work=(
            "A chat request can ask for a workspace mode. The workspace binds source refs, related notes, proof refs, "
            "task status, warnings, and next actions into a compact visual plan."
        ),
        how_app_automation_is_gated=(
            "App targets and command summaries can be modeled, but live automation and mutation remain false until a future "
            "approved adapter has explicit scope, confirmation, backup or receipt posture, and readback."
        ),
        how_agents_see_file_refs=(
            "Agents see source refs, safe labels, summaries, allowed extracts, and proof posture. Raw private bodies stay out "
            "of LLM context by default."
        ),
        how_worker_routing_applies=(
            "Mac visual/app work routes to MAC_CODEX, backend source/proof packaging routes to PC_CODEX, protected proof "
            "routes to GUARDIAN, design audit routes to GEMINI_AGY, and communications drafting routes to CASSANDRA when gated."
        ),
        next_safe_move="Use this contract to build future intake packets and visual workspace mirrors without live ingestion or automation.",
    )


def _all_authority_flags_false(payload: dict[str, Any]) -> bool:
    if any(payload["authority_boundary"].values()):
        return False
    examples = payload["examples"].values()
    for example in examples:
        for item in example.values():
            if isinstance(item, dict) and "authority_boundary" in item:
                if any(item["authority_boundary"].values()):
                    return False
    return True


def _all_source_refs_hide_paths(payload: dict[str, Any]) -> bool:
    for example in payload["examples"].values():
        refs = []
        if "source_ref" in example:
            refs.append(example["source_ref"])
        if "source_refs" in example:
            refs.extend(example["source_refs"].values())
        for ref in refs:
            if ref["local_path_policy"] != "hidden_in_normal_read_model":
                return False
    return True


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    examples = payload["examples"]
    blocker_types = {blocker["blocker_type"] for blocker in payload["file_visual_workspace_blockers_by_id"].values()}
    return {
        "operator_file_intake_contract_model_present": True,
        "operator_file_source_ref_model_present": True,
        "visual_workspace_request_model_present": True,
        "visual_workspace_artifact_binding_model_present": True,
        "visual_workspace_bundle_model_present": True,
        "app_automation_request_model_present": True,
        "visual_mode_transition_model_present": True,
        "file_visual_workspace_blocker_model_present": True,
        "operator_file_intake_visual_workspace_elioperator_report_model_present": True,
        "file_types_exist": set(SUPPORTED_FILE_TYPES).issubset(payload["supported_file_types"]),
        "intake_modes_exist": set(INTAKE_MODES).issubset(payload["intake_modes"]),
        "visual_modes_exist": set(VISUAL_MODES).issubset(payload["visual_modes"]),
        "target_surfaces_exist": set(TARGET_SURFACES).issubset(payload["target_surfaces"]),
        "artifact_roles_exist": set(ARTIFACT_ROLES).issubset(payload["artifact_roles"]),
        "open_modes_exist": set(OPEN_MODES).issubset(payload["open_modes"]),
        "target_apps_exist": set(TARGET_APPS).issubset(payload["target_apps"]),
        "automation_modes_exist": set(AUTOMATION_MODES).issubset(payload["automation_modes"]),
        "visual_transition_modes_exist": set(VISUAL_TRANSITION_MODES).issubset(payload["visual_transition_modes"]),
        "source_ref_model_exists": bool(examples["album_spreadsheet_song_doc"]["source_refs"]),
        "visual_workspace_request_exists": "visual_workspace_request" in examples["album_spreadsheet_song_doc"],
        "workspace_bundle_exists": "visual_workspace_bundle" in examples["album_spreadsheet_song_doc"],
        "artifact_binding_exists": bool(examples["album_spreadsheet_song_doc"]["artifact_bindings"]),
        "app_automation_request_exists": "app_automation_request" in examples["app_automation_request"],
        "visual_mode_transition_exists": "visual_mode_transition" in examples["visual_mode_transition"],
        "blockers_exist": set(BLOCKER_TYPES).issubset(blocker_types),
        "album_spreadsheet_song_doc_example_exists": examples["album_spreadsheet_song_doc"]["visual_workspace_request"]["visual_mode"] == "SHOW_SPREADSHEET_AND_DOC",
        "invoice_workspace_example_exists": examples["capital_hilton_invoice_workspace"]["visual_workspace_request"]["visual_mode"] == "SHOW_INVOICE_PACKET",
        "legal_contract_example_exists": examples["legal_contract_review_workspace"]["source_ref"]["protected_ref_required"] is True,
        "video_edit_review_example_exists": examples["video_edit_review_workspace"]["visual_workspace_request"]["visual_mode"] == "SHOW_TIMELINE",
        "live_show_planning_example_exists": examples["live_show_planning_workspace"]["source_ref"]["file_type"] == "calendar_or_event_reference",
        "client_delivery_example_exists": examples["client_delivery_workspace"]["source_ref"]["file_type"] == "folder_or_project_capsule",
        "bug_debug_example_exists": examples["bug_debug_workspace"]["visual_workspace_request"]["target_worker_type"] == "PC_CODEX",
        "protected_proof_example_exists": examples["protected_proof_workspace"]["guardian_may_be_required"] is True,
        "invoice_artifact_example_exists": examples["invoice_artifact_source"]["artifact_binding"]["artifact_role"] == "INVOICE_ARTIFACT",
        "screenshot_proof_example_exists": examples["screenshot_proof"]["proof_role"] == "SCREENSHOT_PROOF",
        "app_automation_example_exists": examples["app_automation_request"]["app_automation_request"]["target_app"] == "Logic Pro",
        "unsafe_send_blocker_exists": examples["unsafe_automation_blocker"]["email_send_blocked"] is True,
        "all_live_authority_flags_false": _all_authority_flags_false(payload),
        "source_refs_hide_private_paths": _all_source_refs_hide_paths(payload),
        "raw_file_body_to_llm": False,
        "file_ingestion_performed": False,
        "raw_body_extraction_performed": False,
        "app_automation_performed": False,
        "file_mutation_performed": False,
        "external_app_control_performed": False,
        "email_send_performed": False,
        "project_edit_performed": False,
        "screenshot_capture_performed": False,
        "screen_recording_performed": False,
        "export_or_publish_performed": False,
        "agent_dispatch_performed": False,
        "model_call_performed": False,
        "external_action_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_generated_outputs": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_operator_file_intake_visual_workspace_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    contract = build_contract()
    examples = build_examples()
    blockers = build_blockers()
    report = build_elioperator_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "supported_file_types": SUPPORTED_FILE_TYPES,
        "intake_modes": INTAKE_MODES,
        "visual_modes": VISUAL_MODES,
        "target_surfaces": TARGET_SURFACES,
        "artifact_roles": ARTIFACT_ROLES,
        "open_modes": OPEN_MODES,
        "target_apps": TARGET_APPS,
        "automation_modes": AUTOMATION_MODES,
        "visual_transition_modes": VISUAL_TRANSITION_MODES,
        "blocker_types": BLOCKER_TYPES,
        "model_schemas": _model_schemas(),
        "operator_file_intake_contract": asdict(contract),
        "examples": examples,
        "file_visual_workspace_blockers_by_id": {
            blocker.blocker_id: asdict(blocker)
            for blocker in blockers
        },
        "elioperator_report": asdict(report),
        "authority_boundary": _local_authority_boundary(),
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["elioperator_report"]
    examples = payload["examples"]
    lines = [
        "# Operator File Intake + Visual Workspace Contract",
        "",
        f"Status: {payload['contract_status']}",
        "",
        "## ELIOPERATOR",
        "",
        report["plain_summary"],
        "",
        "What this enables:",
        f"- {report['what_this_enables']}",
        "",
        "What this does not do yet:",
        f"- {report['what_this_does_not_do_yet']}",
        "",
        "How it works:",
        f"- {report['how_file_intake_works']}",
        f"- {report['how_visual_workspace_requests_work']}",
        f"- {report['how_app_automation_is_gated']}",
        f"- {report['how_agents_see_file_refs']}",
        f"- {report['how_worker_routing_applies']}",
        "",
        "Example readbacks:",
        "- Album workspace: show the spreadsheet and related song notes as read-only source refs.",
        "- Invoice workspace: show invoice packet status, proof refs, missing items, and locked send/submit actions.",
        "- Protected proof: show safe proof refs while raw bodies stay hidden.",
        "- App boundary: Logic can be modeled as a visual/app request, but mutation and export remain gated.",
        "- Unsafe automation: Mail send is blocked until a governed email/approval adapter exists.",
        "",
        "Current examples present:",
        *[f"- {name}" for name in examples],
        "",
        "Authority boundary:",
        *[f"- {key}: {value}" for key, value in payload["authority_boundary"].items()],
        "",
        f"Next safe move: {report['next_safe_move']}",
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path) -> dict[str, str]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "operator_path": str(operator_path)}


def build_summary(payload: dict[str, Any], paths: dict[str, str]) -> dict[str, Any]:
    proof = payload["machine_proof"]
    return {
        "read_model_id": payload["read_model_id"],
        "schema_version": payload["schema_version"],
        "contract_status": payload["contract_status"],
        "json_path": paths["json_path"],
        "operator_path": paths["operator_path"],
        "content_hash": proof["content_hash"],
        "file_types_exist": proof["file_types_exist"],
        "intake_modes_exist": proof["intake_modes_exist"],
        "source_ref_model_exists": proof["source_ref_model_exists"],
        "visual_workspace_request_exists": proof["visual_workspace_request_exists"],
        "workspace_bundle_exists": proof["workspace_bundle_exists"],
        "artifact_binding_exists": proof["artifact_binding_exists"],
        "app_automation_request_exists": proof["app_automation_request_exists"],
        "visual_mode_transition_exists": proof["visual_mode_transition_exists"],
        "blockers_exist": proof["blockers_exist"],
        "album_spreadsheet_song_doc_example_exists": proof["album_spreadsheet_song_doc_example_exists"],
        "invoice_workspace_example_exists": proof["invoice_workspace_example_exists"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
        "raw_file_body_to_llm": proof["raw_file_body_to_llm"],
        "external_action_performed": proof["external_action_performed"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the operator file intake visual workspace contract.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    payload = build_operator_file_intake_visual_workspace_contract(generated_at=args.generated_at)
    paths = write_exports(payload, Path(args.export_root))
    output = build_summary(payload, paths) if args.format == "summary" else payload
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
