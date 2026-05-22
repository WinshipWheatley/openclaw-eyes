"""Security Pass Contract v0 Pass 1 + Pass 2 + Pass 3 for OpenClaw.

This read-model records scoped security pass decisions for read-only,
preview-only, metadata-only, capture-only, proof/detail, stable-map, and world
preview surfaces. Pass 2 adds worker-output intake and orphaned capability
detection metadata. Pass 3 adds Chief/Hermes trust-building,
FULL_TRUST_CLEARANCE modeling, and cross-off rules. It does not create live
execution, model calls, model router runtime, actor/agent activation, tool
execution, browser/OAuth/account access, Gmail/calendar/Coupa/Telegram access,
credentials, send/submit/approval, invoice generation, ledger writes, email
dispatch, queue/autonomy, planner/builder execution, Mac sync/import, network
operation, Repo B inspection, file organization, raw private body ingestion,
automatic activation of detected capabilities, automatic crossing off,
Chief/Hermes self-authorization, external dependency adoption, or PC
system-drive write authority.
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

SCHEMA_VERSION = "security_pass_contract_v0_pass_3"
JSON_EXPORT_NAME = "security_pass_contract.json"
OPERATOR_EXPORT_NAME = "security_pass_contract_OPERATOR.md"

SECURITY_DECISION_CATEGORIES = (
    "APPROVED_READ_ONLY",
    "APPROVED_PREVIEW_ONLY",
    "APPROVED_METADATA_ONLY",
    "APPROVED_CAPTURE_ONLY",
    "APPROVED_PROOF_DETAIL_ONLY",
    "APPROVED_STABLE_MAP_SURFACE",
    "APPROVED_WORLD_PREVIEW",
    "APPROVED_HOLDING_CELL_CLASSIFICATION",
    "REQUIRES_OPERATOR_APPROVAL",
    "REQUIRES_GUARDIAN_GATE",
    "REQUIRES_SECURITY_REVIEW",
    "REQUIRES_PROOF_METADATA",
    "FUTURE_GATED",
    "BLOCKED_SENSITIVE",
    "BLOCKED_AUTHORITY",
    "BLOCKED_CREDENTIAL",
    "BLOCKED_RAW_BODY",
    "BLOCKED_ACCOUNT",
    "BLOCKED_NETWORK",
    "BLOCKED_EXECUTION",
    "UNKNOWN_FAIL_CLOSED",
)

DECISION_REQUIRED_FIELDS = (
    "decision_id",
    "target_surface",
    "target_lane",
    "target_component",
    "approval_status",
    "allowed_posture",
    "blocked_posture",
    "required_gates",
    "source_refs",
    "proof_refs",
    "stable_map_refs",
    "authority_flags",
    "what_would_change_the_decision",
    "next_safe_move",
)

NO_ACTION_AUTHORITY_FLAGS = {
    "live_model_calls_allowed": False,
    "model_api_execution_allowed": False,
    "model_router_runtime_allowed": False,
    "actor_agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_autonomy_execution_allowed": False,
    "planner_builder_execution_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "gmail_calendar_coupa_telegram_access_allowed": False,
    "credential_handling_allowed": False,
    "send_submit_approval_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_write_allowed": False,
    "email_dispatch_allowed": False,
    "raw_private_body_ingestion_allowed": False,
    "raw_finance_body_ingestion_allowed": False,
    "raw_excel_body_ingestion_allowed": False,
    "raw_email_calendar_body_ingestion_allowed": False,
    "broad_markdown_body_ingestion_allowed": False,
    "broad_filesystem_indexing_allowed": False,
    "broad_private_file_inspection_allowed": False,
    "repo_b_execution_allowed": False,
    "repo_b_body_inspection_allowed": False,
    "file_move_delete_cleanup_remount_allowed": False,
    "network_operation_allowed": False,
    "hidden_memory_allowed": False,
    "hidden_surveillance_allowed": False,
    "automatic_promotion_allowed": False,
    "automatic_queueing_allowed": False,
    "automatic_activation_of_detected_capabilities_allowed": False,
    "automatic_cross_off_allowed": False,
    "automatic_world_transition_allowed": False,
    "chief_self_authorization_allowed": False,
    "hermes_self_authorization_allowed": False,
    "external_dependency_adoption_allowed": False,
    "pc_c_drive_artifact_write_allowed": False,
    "action_authority_granted": False,
    "runtime_execution_authority_granted": False,
    "tool_execution_authority_granted": False,
    "model_execution_authority_granted": False,
    "queue_execution_authority_granted": False,
    "account_authority_granted": False,
    "send_submit_approval_authority_granted": False,
    "operator_final_authority": True,
}

ALLOWED_AFTER_PASS = (
    "stable map display",
    "read-model display",
    "operator markdown display",
    "metadata-only terrain classification already built",
    "Markdown Knowledge Atlas metadata readback",
    "Approved Markdown Evidence bounded excerpt metadata readback",
    "package preview display",
    "tool adapter receipt display",
    "agent dossier display",
    "Capital Hilton proof metadata preview",
    "Finance World preview",
    "Security Readiness display",
    "memory candidate capture as future UI concept only if later implemented",
    "operator answer capture as future UI concept only if later implemented",
    "holding-cell classification as future concept only",
)

STILL_BLOCKED = (
    "live model calls",
    "model/API execution",
    "model router runtime",
    "actor/agent activation",
    "tool execution",
    "queue/autonomy execution",
    "planner/builder execution",
    "browser/OAuth/account access",
    "Gmail/calendar/Coupa/Telegram access",
    "credentials/tokens/cookies/API keys",
    "send/submit/approval",
    "invoice generation",
    "ledger writes",
    "email dispatch",
    "raw finance/private body ingestion",
    "raw Excel body ingestion",
    "raw email/calendar body ingestion",
    "broad Markdown body ingestion",
    "broad filesystem indexing",
    "broad private file inspection",
    "Repo B execution",
    "Repo B body inspection",
    "file delete/move/cleanup/remount",
    "network operation",
    "hidden memory",
    "hidden surveillance",
    "automatic promotion",
    "automatic queueing",
    "automatic activation of detected capabilities",
    "automatic crossing off",
    "automatic world transition",
    "Chief/Hermes self-authorization",
    "external dependency adoption without review",
    "C-drive artifact writes",
)

WORKER_OUTPUT_INTAKE_STATUSES = (
    "RECEIVED_UNVERIFIED",
    "RECEIPT_MATCHED",
    "PROOF_REFERENCED",
    "NEEDS_CLASSIFICATION",
    "NEEDS_SECURITY_REVIEW",
    "NEEDS_STABLE_MAP_PROMOTION",
    "NEEDS_APP_SURFACE",
    "DUPLICATE_EXISTING_CAPABILITY",
    "PARKED",
    "QUARANTINED",
    "REJECTED",
    "UNKNOWN_FAIL_CLOSED",
)

ORPHANED_CAPABILITY_STATUSES = (
    "KNOWN_AND_SURFACED",
    "KNOWN_NOT_SURFACED",
    "BUILT_NOT_REGISTERED",
    "REGISTERED_NOT_VISIBLE",
    "DUPLICATE",
    "STALE",
    "UNSAFE",
    "PARKED",
    "QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

ORPHANED_CAPABILITY_PROMOTION_DECISIONS = (
    "PROMOTE_TO_STABLE_MAP",
    "CREATE_APP_VISIBILITY_SURFACE",
    "ADD_TO_PACKAGE_REGISTRY",
    "ADD_TO_HOLDING_CELL",
    "MERGE_WITH_EXISTING_CAPABILITY",
    "KEEP_AS_PROOF_DETAIL",
    "PARK",
    "QUARANTINE",
    "REJECT_OBSOLETE",
    "UNKNOWN_FAIL_CLOSED",
)

WORKER_OUTPUT_INTAKE_FIELDS = (
    "worker_output_id",
    "worker_name",
    "worker_surface",
    "reported_task",
    "reported_status",
    "commit_hashes",
    "changed_files",
    "generated_artifacts",
    "test_commands",
    "test_results",
    "screenshots",
    "receipt_refs",
    "stable_map_refs",
    "security_relevance",
    "authority_claims",
    "boundary_claims",
    "intake_status",
    "operator_review_required",
    "security_review_required",
    "next_safe_move",
)

ORPHANED_CAPABILITY_FIELDS = (
    "capability_id",
    "display_name",
    "detected_from",
    "evidence_refs",
    "script_refs",
    "test_refs",
    "read_model_refs",
    "sqlite_table_refs",
    "stable_map_status",
    "mission_control_visibility_status",
    "package_visibility_status",
    "world_visibility_status",
    "capability_status",
    "safe_to_use_pre_security",
    "security_review_required",
    "operator_review_required",
    "recommended_action",
    "what_would_make_it_active",
    "what_keeps_it_inactive",
    "blocked_actions",
)

ORPHANED_CAPABILITY_PROMOTION_FIELDS = (
    "capability_id",
    "decision",
    "reason",
    "required_proof",
    "required_tests",
    "required_security_gates",
    "required_stable_map_refs",
    "required_app_surface",
    "operator_approval_required",
    "guardian_gate_required",
    "action_authority_granted",
    "next_safe_move",
)

TRUST_CLEARANCE_STATES = (
    "NO_TRUST",
    "LOW_TRUST",
    "PARTIAL_TRUST",
    "HIGH_TRUST_NEEDS_OPERATOR",
    "HIGH_TRUST_NEEDS_GUARDIAN",
    "HIGH_TRUST_NEEDS_HERMES",
    "FULL_TRUST_CLEARANCE",
    "QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

RECONCILIATION_STATES = (
    "NOT_RECONCILED",
    "MATCHED_TO_TASK",
    "MATCHED_TO_MARKDOWN_ITEM",
    "MATCHED_TO_CUE_CANDIDATE",
    "MATCHED_TO_STABLE_MAP_LANE",
    "COMPLETED_WITH_PROOF",
    "COMPLETED_NEEDS_VERIFICATION",
    "PARTIAL_REQUEUE_REQUIRED",
    "FAILED_REPAIR_REQUIRED",
    "BUILT_NOT_SURFACED",
    "DUPLICATE_OR_OVERLAP",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "PARKED_WITH_PROOF",
    "QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

TRUST_CLEARANCE_REQUIRED_FIELDS = (
    "trust_clearance_status",
    "full_trust_clearance_eligible",
    "trust_clearance_blockers",
    "trust_building_detour",
    "required_proof_refs",
    "required_tests",
    "required_receipts",
    "required_gates",
    "conflict_locks",
    "rollback_recovery_required",
    "operator_babysitting_required",
    "future_unattended_execution_eligible",
    "action_authority_granted",
)

SOURCE_READ_MODEL_REFS = (
    "generated/read_models/security_audit_readiness_packet.json",
    "generated/read_models/openclaw_map_snapshot.json",
    "generated/read_models/openclaw_map_manifest.json",
    "generated/read_models/sync_health.json",
    "generated/read_models/capital_hilton_proof_metadata_packet.json",
    "generated/read_models/package_preview_receipt_contract.json",
    "generated/read_models/tool_adapter_receipt_contract.json",
    "generated/read_models/memory_candidate_receipt_contract.json",
)

MARKDOWN_TERRAIN_SYSTEMS = (
    "markdown_knowledge_atlas.py",
    "scripts/build_markdown_knowledge_atlas.py",
    "markdown_evidence_ingestion.py",
    "scripts/ingest_approved_markdown_evidence.py",
    "corpus_atlas.py",
)

MARKDOWN_METADATA_COUNTS = {
    "corpus_paths": 43762,
    "corpus_path_labels": 434362,
    "markdown_documents": 598,
    "markdown_document_classifications": 2990,
    "markdown_document_links": 1794,
    "markdown_document_reorg_candidates": 598,
    "markdown_document_supersession": 9,
    "markdown_evidence_sources": 12,
    "markdown_evidence_items": 206,
}

CAPITAL_HILTON_PROOF_IDS = (
    "performance_date_proof_metadata",
    "rate_proof_metadata",
    "subtotal_proof_metadata",
    "coupa_po_or_payment_reference_metadata",
    "excel_workbook_reference_metadata",
    "invoice_source_card_metadata",
    "ap_recipient_route_metadata",
    "guardian_protected_access_gate_metadata",
    "operator_confirmation_metadata",
    "future_invoice_generation_receipt_requirement",
)

ACTOR_IDS = (
    "chief",
    "guardian",
    "cassandra",
    "hermes",
    "niles",
    "codex",
    "gemini_antigravity",
    "operator",
)

TOOL_ADAPTER_IDS = (
    "stable_map_reader",
    "package_preview_exporter",
    "memory_candidate_receipt_writer",
    "codex_scoped_build_verifier",
    "browser_oauth_adapter",
    "gmail_calendar_adapter",
    "coupa_adapter",
    "telegram_adapter",
    "repo_b_planner_builder_adapter",
)


@dataclass(frozen=True)
class SecurityDecision:
    decision_id: str
    target_surface: str
    target_lane: str
    target_component: str
    approval_status: str
    allowed_posture: list[str]
    blocked_posture: list[str]
    required_gates: list[str]
    source_refs: list[str]
    proof_refs: list[str]
    stable_map_refs: list[str]
    authority_flags: dict[str, bool]
    what_would_change_the_decision: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkerOutputReceiptIntake:
    worker_output_id: str
    worker_name: str
    worker_surface: str
    reported_task: str
    reported_status: str
    commit_hashes: list[str]
    changed_files: list[str]
    generated_artifacts: list[str]
    test_commands: list[str]
    test_results: list[str]
    screenshots: list[str]
    receipt_refs: list[str]
    stable_map_refs: list[str]
    security_relevance: str
    authority_claims: list[str]
    boundary_claims: list[str]
    intake_status: str
    operator_review_required: bool
    security_review_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class OrphanedCapabilityCandidate:
    capability_id: str
    display_name: str
    detected_from: list[str]
    evidence_refs: list[str]
    script_refs: list[str]
    test_refs: list[str]
    read_model_refs: list[str]
    sqlite_table_refs: list[str]
    stable_map_status: str
    mission_control_visibility_status: str
    package_visibility_status: str
    world_visibility_status: str
    capability_status: str
    safe_to_use_pre_security: bool
    security_review_required: bool
    operator_review_required: bool
    recommended_action: str
    what_would_make_it_active: str
    what_keeps_it_inactive: str
    blocked_actions: list[str]


@dataclass(frozen=True)
class OrphanedCapabilityPromotionDecision:
    capability_id: str
    decision: str
    reason: str
    required_proof: list[str]
    required_tests: list[str]
    required_security_gates: list[str]
    required_stable_map_refs: list[str]
    required_app_surface: str
    operator_approval_required: bool
    guardian_gate_required: bool
    action_authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class ChiefReconciliationRole:
    role_id: str
    display_name: str
    role_summary: str
    current_authority: str
    future_authority_condition: str
    can_self_authorize: bool
    allowed_current_actions: list[str]
    blocked_current_actions: list[str]
    future_gated_actions: list[str]
    reconciliation_responsibilities: list[str]
    test_harness_responsibilities: list[str]
    trust_gap_responsibilities: list[str]
    operator_babysitting_reduction_goal: str


@dataclass(frozen=True)
class HermesArchitectureReviewRole:
    role_id: str
    display_name: str
    role_summary: str
    current_authority: str
    recommendation_authority: str
    can_self_authorize: bool
    allowed_current_actions: list[str]
    blocked_current_actions: list[str]
    future_gated_actions: list[str]
    architecture_review_responsibilities: list[str]
    external_dependency_review_requirements: list[str]
    trust_gap_support_responsibilities: list[str]


@dataclass(frozen=True)
class TrustClearanceModel:
    trust_clearance_status: str
    full_trust_clearance_eligible: bool
    trust_clearance_blockers: list[str]
    trust_building_detour: str
    required_proof_refs: list[str]
    required_tests: list[str]
    required_receipts: list[str]
    required_gates: list[str]
    conflict_locks: list[str]
    rollback_recovery_required: bool
    operator_babysitting_required: bool
    future_unattended_execution_eligible: bool
    action_authority_granted: bool


@dataclass(frozen=True)
class SecurityPassContractExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    decision_count: int
    security_pass_completed: bool
    read_only_surfaces_approved: bool
    preview_surfaces_approved: bool
    worker_output_intake_approved: bool
    orphaned_capability_detection_approved: bool
    chief_reconciliation_approved: bool
    hermes_architecture_review_approved: bool
    trust_clearance_modeling_approved: bool
    worker_output_count: int
    orphaned_capability_count: int
    action_authority_granted: bool
    live_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _read_json_if_present(repo_root: str | Path, relative_path: str) -> dict[str, Any]:
    path = Path(repo_root) / relative_path
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _authority_flags() -> dict[str, bool]:
    return dict(NO_ACTION_AUTHORITY_FLAGS)


def _all_dangerous_authority_false() -> bool:
    return all(value is False for key, value in NO_ACTION_AUTHORITY_FLAGS.items() if key != "operator_final_authority")


def _decision(
    *,
    decision_id: str,
    target_surface: str,
    target_lane: str,
    target_component: str,
    approval_status: str,
    allowed_posture: list[str],
    blocked_posture: list[str],
    required_gates: list[str],
    source_refs: list[str],
    proof_refs: list[str],
    stable_map_refs: list[str],
    what_would_change_the_decision: str,
    next_safe_move: str,
) -> dict[str, Any]:
    return asdict(
        SecurityDecision(
            decision_id=decision_id,
            target_surface=target_surface,
            target_lane=target_lane,
            target_component=target_component,
            approval_status=approval_status,
            allowed_posture=allowed_posture,
            blocked_posture=blocked_posture,
            required_gates=required_gates,
            source_refs=source_refs,
            proof_refs=proof_refs,
            stable_map_refs=stable_map_refs,
            authority_flags=_authority_flags(),
            what_would_change_the_decision=what_would_change_the_decision,
            next_safe_move=next_safe_move,
        )
    )


def _stable_map_context(repo_root: str | Path) -> dict[str, Any]:
    snapshot = _read_json_if_present(repo_root, "generated/read_models/openclaw_map_snapshot.json")
    manifest = _read_json_if_present(repo_root, "generated/read_models/openclaw_map_manifest.json")
    sync_health = _read_json_if_present(repo_root, "generated/read_models/sync_health.json")
    app_status = sync_health.get("app_visible_map_status") if isinstance(sync_health.get("app_visible_map_status"), dict) else {}
    return {
        "snapshot": snapshot,
        "manifest": manifest,
        "sync_health": sync_health,
        "map_generation_id": str(
            manifest.get("map_generation_id")
            or snapshot.get("map_generation_id")
            or app_status.get("map_generation_id")
            or "map_generation_missing_fail_closed"
        ),
        "bundle_hash": str(
            manifest.get("bundle_hash")
            or app_status.get("bundle_hash")
            or "bundle_hash_missing_fail_closed"
        ),
        "app_visible_map_current": app_status.get("map_status") == "map_current" and app_status.get("app_visible") is True,
        "check_transmission_quiet": (
            (sync_health.get("check_transmission_display") or {}).get("lamp_state") == "QUIET"
            if isinstance(sync_health.get("check_transmission_display"), dict)
            else False
        ),
    }


def _capital_hilton_context(repo_root: str | Path, stable_context: dict[str, Any]) -> dict[str, Any]:
    snapshot = stable_context["snapshot"]
    summary = snapshot.get("capital_hilton_proof_metadata") if isinstance(snapshot.get("capital_hilton_proof_metadata"), dict) else {}
    packet = _read_json_if_present(repo_root, "generated/read_models/capital_hilton_proof_metadata_packet.json")
    machine = packet.get("machine_proof") if isinstance(packet.get("machine_proof"), dict) else {}
    missing = summary.get("missing_proof")
    missing_proof = [str(item) for item in missing] if isinstance(missing, list) and missing else list(CAPITAL_HILTON_PROOF_IDS)
    missing_count = int(summary.get("missing_proof_count") or machine.get("missing_proof_count") or len(missing_proof))
    protected_required = bool(summary.get("protected_proof_required", machine.get("protected_proof_required", True)))
    return {
        "current_phase": str(summary.get("current_phase") or "HELM_THRESHOLD_LANE"),
        "target_world": str(summary.get("target_world") or "Finance"),
        "lane_destiny": str(summary.get("lane_destiny") or "MOVE_TO_WORLD_ACTION"),
        "missing_proof": missing_proof,
        "missing_proof_count": missing_count,
        "protected_proof_required": protected_required,
        "candidate_facts_proven": False,
        "finance_world_preview_exists": True,
        "shared_execution_path_id": "protected_finance_proof_metadata_intake",
    }


def _security_readiness_context(repo_root: str | Path, stable_context: dict[str, Any]) -> dict[str, Any]:
    snapshot = stable_context["snapshot"]
    stable_summary = snapshot.get("security_audit_readiness") if isinstance(snapshot.get("security_audit_readiness"), dict) else {}
    packet = _read_json_if_present(repo_root, "generated/read_models/security_audit_readiness_packet.json")
    criteria = packet.get("security_pass_readiness_criteria") if isinstance(packet.get("security_pass_readiness_criteria"), dict) else {}
    return {
        "ready_for_security_pass": bool(stable_summary.get("ready_for_security_pass", criteria.get("ready_for_security_pass", True))),
        "security_approval_granted": bool(stable_summary.get("security_approval_granted", False)),
        "action_authority_granted": bool(stable_summary.get("action_authority_granted", False)),
        "coverage_gap_records_count": int(stable_summary.get("coverage_gap_summary", {}).get("coverage_gap_records_count", 5))
        if isinstance(stable_summary.get("coverage_gap_summary"), dict)
        else 5,
        "parked_breadcrumb_count": int(stable_summary.get("parked_breadcrumb_summary", {}).get("parked_breadcrumb_count", 15))
        if isinstance(stable_summary.get("parked_breadcrumb_summary"), dict)
        else 15,
    }


def _surface_security_decisions() -> list[dict[str, Any]]:
    common_sources = [
        "generated/read_models/security_audit_readiness_packet.json",
        "generated/read_models/openclaw_map_snapshot.json",
    ]
    return [
        _decision(
            decision_id="stable_map_bundle_read_only",
            target_surface="Stable Map Bundle",
            target_lane="stable_map_app_visibility",
            target_component="openclaw_map_snapshot",
            approval_status="APPROVED_STABLE_MAP_SURFACE",
            allowed_posture=["read-only app-facing reflection", "generation id/hash/receipt display", "app-visible current status"],
            blocked_posture=["source truth claim", "raw mirror as helm crisis when app map is current", "execution authority"],
            required_gates=["map generation id", "bundle hash", "Mac receipt readback"],
            source_refs=["generated/read_models/openclaw_map_snapshot.json", "generated/read_models/openclaw_map_manifest.json"],
            proof_refs=["generated/read_models/sync_health.json#app_visible_map_status"],
            stable_map_refs=["openclaw_map_snapshot"],
            what_would_change_the_decision="Missing receipt, stale generation, malformed bundle, or source/proof contradiction.",
            next_safe_move="Keep stable map as app-facing reflection and raw mirror mismatch in proof/detail.",
        ),
        _decision(
            decision_id="mission_control_mac_app_read_only",
            target_surface="Mission Control Mac App",
            target_lane="mission_control",
            target_component="stable_map_consuming_cockpit",
            approval_status="APPROVED_READ_ONLY",
            allowed_posture=["read-only cockpit", "sandboxed stable-map consumption", "operator orientation display"],
            blocked_posture=["direct backend execution", "network access", "live tools", "account flows"],
            required_gates=["stable map bundle boundary"],
            source_refs=common_sources,
            proof_refs=["generated/read_models/openclaw_map_manifest.json"],
            stable_map_refs=["openclaw_map_snapshot"],
            what_would_change_the_decision="Any UI control that dispatches models, tools, accounts, sends, submits, approvals, or backend mutations.",
            next_safe_move="Render read-only app-facing summaries only.",
        ),
        _decision(
            decision_id="agent_council_dossier_cards_preview",
            target_surface="Agent Council / Dossier Cards",
            target_lane="agent_council",
            target_component="agent_dossier_cards",
            approval_status="APPROVED_PREVIEW_ONLY",
            allowed_posture=["agent/persona display", "package support hints", "gate/receipt visibility"],
            blocked_posture=["live chat", "model launch", "agent activation", "self-authority", "hidden memory"],
            required_gates=["actor router references", "stable map agent dossier refs"],
            source_refs=["generated/read_models/agent_terrain_awareness_readback_contract.json", *common_sources],
            proof_refs=["generated/read_models/openclaw_map_manifest.json"],
            stable_map_refs=["agent_council.agent_dossier_cards"],
            what_would_change_the_decision="Any agent card acquiring launch, model, tool, memory-write, account, or self-authorization controls.",
            next_safe_move="Keep Agent Council as preview and dossier orientation.",
        ),
        _decision(
            decision_id="package_preview_tool_receipt_surface",
            target_surface="Package Preview / Tool Receipt Surface",
            target_lane="package_preview",
            target_component="package_preview_receipts_and_tool_adapter_receipts",
            approval_status="APPROVED_PREVIEW_ONLY",
            allowed_posture=["package preview display", "tool receipt proof/detail", "blocked adapter reasons"],
            blocked_posture=["dispatch", "tool execution", "model launch", "account/browser/send controls"],
            required_gates=["package preview receipt", "tool adapter receipt", "model selection receipt", "memory scope"],
            source_refs=["generated/read_models/package_preview_receipt_contract.json", "generated/read_models/tool_adapter_receipt_contract.json"],
            proof_refs=["generated/read_models/model_selection_receipt_contract.json", "generated/read_models/memory_candidate_receipt_contract.json"],
            stable_map_refs=["package_preview_receipts", "tool_adapter_receipts"],
            what_would_change_the_decision="Future security pass grants a receipted execution path; absent that, preview remains non-dispatchable.",
            next_safe_move="Show what is allowed, blocked, future-gated, and what proof is missing.",
        ),
        _decision(
            decision_id="finance_world_capital_hilton_preview",
            target_surface="Finance World / Capital Hilton Preview",
            target_lane="capital_hilton",
            target_component="capital_hilton_proof_metadata",
            approval_status="APPROVED_WORLD_PREVIEW",
            allowed_posture=["Finance World preview", "candidate facts with not-proven label", "proof metadata checklist"],
            blocked_posture=["Coupa access", "credentials", "invoice generation", "send/submit/approval", "raw finance body ingestion"],
            required_gates=["Guardian protected proof gate", "Operator final authority for future action", "security review for any execution"],
            source_refs=["generated/read_models/capital_hilton_proof_metadata_packet.json", *common_sources],
            proof_refs=["generated/read_models/security_audit_readiness_packet.json#capital_hilton_security_readiness"],
            stable_map_refs=["capital_hilton_proof_metadata"],
            what_would_change_the_decision="Proof metadata, Guardian gate, Operator final path, and a later explicit action-authority pass.",
            next_safe_move="Use preview/proof display only; no invoice action.",
        ),
        _decision(
            decision_id="security_readiness_eliwinship_surface",
            target_surface="Security Readiness / ELIWINSHIP Surface",
            target_lane="security_readiness",
            target_component="security_audit_readiness_summary",
            approval_status="APPROVED_READ_ONLY",
            allowed_posture=["read-only audit posture display", "ready-for-security-pass status", "operator-native explanation"],
            blocked_posture=["security approval as execution", "action authority", "live controls"],
            required_gates=["security pass contract scope", "operator final authority"],
            source_refs=["generated/read_models/security_audit_readiness_packet.json"],
            proof_refs=["generated/read_models/security_audit_readiness_packet_OPERATOR.md"],
            stable_map_refs=["security_audit_readiness"],
            what_would_change_the_decision="A later pass grants carefully scoped authority; this pass only approves read-only/preview surfaces.",
            next_safe_move="Show security decisions and keep action authority false.",
        ),
        _decision(
            decision_id="evidence_drawer_proof_rows",
            target_surface="Evidence Drawer / Proof Rows",
            target_lane="proof_detail",
            target_component="proof_rows",
            approval_status="APPROVED_PROOF_DETAIL_ONLY",
            allowed_posture=["collapsed proof/detail", "source refs", "receipt hashes", "operator drill-down"],
            blocked_posture=["raw private bodies", "credential material", "proof rows as execution authority"],
            required_gates=["redaction/protected proof rules", "Guardian gate for protected material"],
            source_refs=common_sources,
            proof_refs=["generated/read_models/*_receipt_contract.json"],
            stable_map_refs=["proof/detail summaries only"],
            what_would_change_the_decision="Protected proof body access would require Guardian/Operator gates and a future protected metadata contract.",
            next_safe_move="Keep proof detail secondary and raw bodies blocked.",
        ),
    ]


def _capital_hilton_security_pass_decision(capital: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_phase": capital["current_phase"],
        "target_world": capital["target_world"],
        "lane_destiny": capital["lane_destiny"],
        "missing_proof_count": capital["missing_proof_count"],
        "protected_proof_required": capital["protected_proof_required"],
        "candidate_facts_proven": capital["candidate_facts_proven"],
        "finance_world_preview_exists": capital["finance_world_preview_exists"],
        "shared_execution_path_id": capital["shared_execution_path_id"],
        "decision": {
            "finance_world_preview": "approved",
            "proof_metadata_display": "approved",
            "operator_questions_display": "approved",
            "candidate_facts_display": "approved_with_not_proven_label",
            "cassandra_review": "preview_only_future_gated_until_package_and_guardian_gates_mature",
            "security_pass_result": "approved_for_preview_proof_capture_planning_not_execution",
        },
        "blocked": {
            "invoice_generation": True,
            "coupa_access": True,
            "browser_oauth_account_access": True,
            "credentials": True,
            "gmail_calendar_email_account_access": True,
            "excel_raw_body_ingestion": True,
            "raw_finance_body_ingestion": True,
            "send_submit_approval": True,
        },
        "required_gates": {
            "guardian_gate": "required_for_protected_proof_metadata",
            "operator_final_authority": "required_for_future_action",
            "future_action_security_review": "required_before_any_execution_considered",
        },
        "authority_flags": _authority_flags(),
    }


def _markdown_system_presence(repo_root: str | Path) -> dict[str, bool]:
    root = Path(repo_root)
    return {relative: (root / relative).is_file() for relative in MARKDOWN_TERRAIN_SYSTEMS}


def _markdown_terrain_security_decision(repo_root: str | Path) -> dict[str, Any]:
    system_presence = _markdown_system_presence(repo_root)
    return {
        "markdown_backend_capability_status": "YES_READY" if all(system_presence.values()) else "PARTLY_MAPPED_NEEDS_SOURCE_CARD",
        "existing_systems": [
            {"path": path, "present": present, "authority_granted_by_presence": False}
            for path, present in system_presence.items()
        ],
        "safe_metadata_coverage": dict(MARKDOWN_METADATA_COUNTS),
        "decision": {
            "metadata_only_markdown_atlas_readback": "approved",
            "allowlisted_bounded_markdown_evidence_excerpts": "approved",
            "source_card_tagging_metadata_review": "approved_preview_only",
            "app_visibility_for_markdown_terrain": "future_gated_visibility_gap_not_security_blocker",
        },
        "blocked": {
            "broad_markdown_body_ingestion": True,
            "broad_doc_reorganization": True,
            "file_moves_deletes_renames": True,
            "stale_doctrine_promotion_without_proof": True,
            "vector_index_creation": True,
            "old_prompts_as_current_truth_unless_classified_proven": True,
        },
        "no_new_mapper_needed_now": True,
        "proof_substrate": "existing Markdown atlas/evidence infrastructure",
        "authority_flags": _authority_flags(),
    }


def _operator_answer_capture_security_decision() -> dict[str, Any]:
    return {
        "answer_schema": "approved",
        "display_of_answer_questions": "approved",
        "future_capture_ui": "approved_as_capture_only_concept",
        "captured_answers": "Memory Candidate Receipts only",
        "operator_answers_as_proof": "blocked",
        "automatic_truth_promotion": "blocked",
        "automatic_lane_quieting_without_receipt_or_proof": "blocked",
        "future_gated_modalities": [
            "screenshot_ref",
            "source_card_ref",
            "protected_proof_metadata_ref",
        ],
        "candidate_state_classifications_approved": [
            "i_dont_know",
            "park_this",
            "reject_obsolete",
            "move_to_world",
        ],
        "authority_flags": _authority_flags(),
    }


def _helm_focus_shared_path_security_decision() -> dict[str, Any]:
    return {
        "helm_issue_focus_mode_model": "approved_for_read_only_ui",
        "shared_execution_paths": "approved_as_non_executing_consolidation",
        "solving_once_updates_multiple_lanes": "future_gated_until_receipt_mechanics_exist",
        "duplicate_fix_path_display_reduction": "approved",
        "blocked": {
            "live_execute_buttons": True,
            "fake_confidence": True,
            "automatic_queueing_from_shared_path": True,
            "hidden_promotion_decisions": True,
        },
        "authority_flags": _authority_flags(),
    }


def _parked_breadcrumb_security_decision() -> dict[str, Any]:
    return {
        "parked_breadcrumb_review": "approved",
        "breadcrumb_preservation": "approved",
        "review_classification_tags": "approved",
        "auto_promotion": "blocked",
        "cue_creation": "future_gated",
        "holding_cell_creation": "future_gated_until_operator_attention_promotion_contract",
        "queue_execution": "blocked",
        "sleep_mode_queue_priority": "parked_future_gated",
        "lifecycle_telemetry_animation": "parked_future_gated",
        "chief_test_harness_receipt": "future_lane",
        "compromise_kill_switch_posture": "high_priority_future_lane",
        "authority_flags": _authority_flags(),
    }


def _actor_decision(actor_id: str) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "display_allowed": True,
        "package_preview_allowed": actor_id != "operator",
        "model_call_allowed": False,
        "live_agent_activation_allowed": False,
        "tool_use_allowed": False,
        "self_authority_allowed": False,
        "memory_write_allowed": False,
        "memory_candidate_proposals": "future_gated",
        "operator_final_authority": actor_id == "operator",
    }


def _adapter_decision(adapter_id: str) -> dict[str, Any]:
    if adapter_id == "stable_map_reader":
        posture = "read_only_approved"
        granted = "READ_METADATA"
    elif adapter_id == "package_preview_exporter":
        posture = "preview_receipt_metadata_approved"
        granted = "RECEIPT_WRITE"
    elif adapter_id == "memory_candidate_receipt_writer":
        posture = "candidate_only_future_gated"
        granted = "MEMORY_CANDIDATE_WRITE_CANDIDATE_ONLY"
    elif adapter_id == "codex_scoped_build_verifier":
        posture = "worker_prompt_only_not_openclaw_runtime"
        granted = "NO_OPENCLAW_RUNTIME_AUTHORITY"
    elif adapter_id == "repo_b_planner_builder_adapter":
        posture = "blocked_future_gated"
        granted = "NONE"
    else:
        posture = "blocked"
        granted = "NONE"
    return {
        "adapter_id": adapter_id,
        "posture": posture,
        "capability_granted": granted,
        "tool_execution_allowed": False,
        "network_allowed": False,
        "account_access_allowed": False,
        "browser_oauth_allowed": False,
        "send_submit_approval_allowed": False,
        "future_gated": posture.endswith("future_gated") or "future_gated" in posture,
    }


def _agent_model_tool_security_decision() -> dict[str, Any]:
    return {
        "actors": [_actor_decision(actor_id) for actor_id in ACTOR_IDS],
        "tool_adapters": [_adapter_decision(adapter_id) for adapter_id in TOOL_ADAPTER_IDS],
        "global_model_policy": {
            "model_call_allowed": False,
            "model_router_runtime_allowed": False,
            "hidden_model_routing_allowed": False,
            "model_display_policy_allowed": True,
        },
        "operator_final_authority": True,
        "authority_flags": _authority_flags(),
    }


def _record_reconciliation_extension(record_id: str) -> dict[str, Any]:
    defaults = {
        "original_task_ref": None,
        "source_markdown_ref": None,
        "source_cue_ref": None,
        "worker_report_ref": None,
        "commit_refs": [],
        "test_receipt_refs": [],
        "artifact_refs": [],
        "stable_map_refs": [],
        "chief_reconciliation_status": "NOT_RECONCILED",
        "chief_test_harness_required": True,
        "chief_recommendation": "classify_and_reconcile_before_any_cross_off",
        "hermes_architecture_review_required": False,
        "hermes_coherence_status": "not_reviewed",
        "hermes_recommendation": "advisory_review_only_if_architecture_relevant",
        "guardian_gate_required": False,
        "operator_final_decision_required": False,
        "trust_clearance_status": "PARTIAL_TRUST",
        "trust_clearance_blockers": ["not fully reconciled"],
        "trust_building_detour": "add proof refs, test receipts, and Chief reconciliation",
        "full_trust_clearance_eligible": False,
        "completion_status": "not_crossed_off",
        "cross_off_allowed": False,
        "requeue_required": False,
        "park_required": False,
        "quarantine_required": False,
        "next_safe_move": "reconcile metadata only; do not execute",
    }
    overrides: dict[str, Any] = {
        "markdown_knowledge_atlas": {
            "source_markdown_ref": "coverage_gap_unmapped_terrain_registry.markdown_document_terrain",
            "commit_refs": [],
            "test_receipt_refs": [],
            "artifact_refs": ["SQLite metadata counts", "Markdown atlas metadata"],
            "chief_reconciliation_status": "BUILT_NOT_SURFACED",
            "chief_test_harness_required": False,
            "chief_recommendation": "preserve existing metadata capability; do not build duplicate mapper",
            "hermes_architecture_review_required": True,
            "hermes_coherence_status": "integration_visibility_gap",
            "hermes_recommendation": "consider stable-map/app visibility later without broad body ingestion",
            "trust_clearance_status": "HIGH_TRUST_NEEDS_HERMES",
            "trust_clearance_blockers": ["no app visibility surface", "broad body/file mutation blocked"],
            "trust_building_detour": "add stable-map metadata summary or proof drawer surface later",
            "completion_status": "known_metadata_capability",
            "park_required": False,
            "next_safe_move": "keep as metadata substrate and evaluate visibility through Hermes/stable-map lane",
        },
        "security_audit_readiness_packet": {
            "commit_refs": ["ff1239f", "02ec429", "371c56d", "d31c91b"],
            "test_receipt_refs": ["tests/test_security_audit_readiness_packet.py"],
            "artifact_refs": ["generated/read_models/security_audit_readiness_packet.json"],
            "stable_map_refs": ["openclaw_map_snapshot.security_audit_readiness"],
            "chief_reconciliation_status": "COMPLETED_WITH_PROOF",
            "chief_test_harness_required": False,
            "chief_recommendation": "eligible for quiet-with-proof as read-only surface",
            "hermes_architecture_review_required": False,
            "hermes_coherence_status": "aligned",
            "hermes_recommendation": "keep read-only readiness posture",
            "trust_clearance_status": "HIGH_TRUST_NEEDS_OPERATOR",
            "trust_clearance_blockers": ["task class execution authority not granted"],
            "trust_building_detour": "no execution detour; retain read-only proof",
            "completion_status": "complete_read_only_surface",
            "cross_off_allowed": True,
            "next_safe_move": "create completion receipt if tied to an original source task",
        },
        "future_invoicing_state_machine_audit": {
            "worker_report_ref": "future_invoicing_state_machine_audit",
            "artifact_refs": ["worker-output audit summary"],
            "stable_map_refs": ["openclaw_map_snapshot.capital_hilton_proof_metadata"],
            "chief_reconciliation_status": "PARKED_WITH_PROOF",
            "chief_test_harness_required": True,
            "chief_recommendation": "park as stress-test artifact; do not implement active invoicing",
            "hermes_architecture_review_required": True,
            "hermes_coherence_status": "useful_future_architecture_stress_test",
            "hermes_recommendation": "extract missing contracts only when Finance/security lane promotes them",
            "guardian_gate_required": True,
            "operator_final_decision_required": True,
            "trust_clearance_status": "NO_TRUST",
            "trust_clearance_blockers": [
                "ledger write authority blocked",
                "email dispatch blocked",
                "invoice generation blocked",
                "missing deterministic invoicing contracts",
            ],
            "trust_building_detour": "park until invoice math, idempotency, ledger read/write, manual lock, and draft receipt contracts exist",
            "completion_status": "parked_not_implementation",
            "cross_off_allowed": False,
            "park_required": True,
            "next_safe_move": "Preserve as future Finance/invoicing stress-test reference; do not implement active invoicing.",
        },
        "capital_hilton_proof_metadata_packet": {
            "commit_refs": ["2a9bede", "b0c80f4"],
            "test_receipt_refs": ["tests/test_capital_hilton_proof_metadata_packet.py"],
            "artifact_refs": ["generated/read_models/capital_hilton_proof_metadata_packet.json"],
            "stable_map_refs": ["openclaw_map_snapshot.capital_hilton_proof_metadata"],
            "chief_reconciliation_status": "COMPLETED_NEEDS_VERIFICATION",
            "chief_test_harness_required": True,
            "chief_recommendation": "keep preview; require proof metadata before action",
            "hermes_architecture_review_required": True,
            "hermes_coherence_status": "aligned_with_finance_world_helm_boundary",
            "hermes_recommendation": "maintain preview-only Finance World lane",
            "guardian_gate_required": True,
            "operator_final_decision_required": True,
            "trust_clearance_status": "HIGH_TRUST_NEEDS_GUARDIAN",
            "trust_clearance_blockers": ["10 missing proof items", "protected proof required", "action authority false"],
            "trust_building_detour": "link proof metadata and Guardian/Operator gates",
            "completion_status": "preview_complete_action_blocked",
            "cross_off_allowed": False,
            "next_safe_move": "continue as preview/proof lane only",
        },
        "agent_council_dossier_surface": {
            "stable_map_refs": ["openclaw_map_snapshot.agent_council.agent_dossier_cards"],
            "chief_reconciliation_status": "COMPLETED_WITH_PROOF",
            "chief_test_harness_required": False,
            "chief_recommendation": "quiet with proof for preview-only dossier surface",
            "hermes_architecture_review_required": False,
            "hermes_coherence_status": "aligned",
            "trust_clearance_status": "HIGH_TRUST_NEEDS_OPERATOR",
            "trust_clearance_blockers": ["display-only surface; no activation authority"],
            "trust_building_detour": "none for read-only display",
            "completion_status": "complete_preview_surface",
            "cross_off_allowed": True,
            "next_safe_move": "retain preview boundary",
        },
        "package_preview_tool_receipt_surface": {
            "stable_map_refs": ["openclaw_map_snapshot.package_preview_receipts", "openclaw_map_snapshot.tool_adapter_receipts"],
            "chief_reconciliation_status": "COMPLETED_WITH_PROOF",
            "chief_test_harness_required": False,
            "chief_recommendation": "quiet with proof for preview/proof-detail surface",
            "hermes_architecture_review_required": False,
            "hermes_coherence_status": "aligned",
            "trust_clearance_status": "HIGH_TRUST_NEEDS_OPERATOR",
            "trust_clearance_blockers": ["dispatch/tool/model authority false"],
            "trust_building_detour": "future action pass if ever needed",
            "completion_status": "complete_preview_surface",
            "cross_off_allowed": True,
            "next_safe_move": "retain preview-only boundary",
        },
    }
    merged = dict(defaults)
    merged.update(overrides.get(record_id, {}))
    return merged


def _build_worker_output_intake() -> dict[str, Any]:
    future_invoicing = WorkerOutputReceiptIntake(
        worker_output_id="future_invoicing_state_machine_audit",
        worker_name="agy_gemini_future_invoicing_audit",
        worker_surface="external_worker_audit_readback",
        reported_task="Future automated invoicing pipeline state-machine stress test",
        reported_status="BLOCKED",
        commit_hashes=[],
        changed_files=[],
        generated_artifacts=[],
        test_commands=[],
        test_results=[
            "Stage 1 ingestion/data validation is partially supported by existing contracts",
            "Stage 2 ledger write/idempotency is blocked until future authority",
            "Stage 3 pre-flight reconciliation is missing deterministic contract",
            "Stage 4 contextual delivery/dispatch is blocked until future authority",
        ],
        screenshots=[],
        receipt_refs=[
            "generated/read_models/capital_hilton_proof_metadata_packet.json",
            "generated/read_models/security_audit_readiness_packet.json",
            "generated/read_models/package_preview_receipt_contract.json",
            "generated/read_models/tool_adapter_receipt_contract.json",
        ],
        stable_map_refs=[
            "openclaw_map_snapshot.capital_hilton_proof_metadata",
            "openclaw_map_snapshot.security_audit_readiness",
            "openclaw_map_snapshot.package_preview_receipts",
            "openclaw_map_snapshot.tool_adapter_receipts",
        ],
        security_relevance="high",
        authority_claims=[
            "no ledger writes",
            "no email dispatch",
            "no Coupa/browser/account/credential authority",
            "no invoice generation",
            "no send/submit/approval",
        ],
        boundary_claims=[
            "park as Security Pass stress-test artifact",
            "do not implement active invoicing now",
            "missing contracts must precede future automation",
            "future implementation requires security review",
        ],
        intake_status="PARKED",
        operator_review_required=False,
        security_review_required=True,
        next_safe_move="Preserve as future Finance/invoicing stress-test reference; do not implement active invoicing.",
    )
    future_record = asdict(future_invoicing)
    future_record.update(_record_reconciliation_extension("future_invoicing_state_machine_audit"))
    return {
        "model_id": "worker_output_intake_v0",
        "description": "Read-only metadata intake for worker outputs; output is not truth by itself.",
        "allowed_intake_statuses": list(WORKER_OUTPUT_INTAKE_STATUSES),
        "required_fields": list(WORKER_OUTPUT_INTAKE_FIELDS),
        "rules": {
            "worker_output_is_not_truth_by_itself": True,
            "candidate_proof_requires_links": [
                "commits",
                "tests",
                "receipts",
                "generated artifacts",
                "screenshots",
                "stable-map refs",
            ],
            "worker_output_must_not_activate_anything": True,
            "worker_output_must_not_create_queue_tasks": True,
            "worker_output_must_not_mutate_source_files": True,
            "worker_output_intake_is_metadata_only": True,
        },
        "records": [future_record],
        "authority_flags": _authority_flags(),
    }


def _capability(
    *,
    capability_id: str,
    display_name: str,
    detected_from: list[str],
    evidence_refs: list[str],
    script_refs: list[str],
    test_refs: list[str],
    read_model_refs: list[str],
    sqlite_table_refs: list[str],
    stable_map_status: str,
    mission_control_visibility_status: str,
    package_visibility_status: str,
    world_visibility_status: str,
    capability_status: str,
    safe_to_use_pre_security: bool,
    security_review_required: bool,
    operator_review_required: bool,
    recommended_action: str,
    what_would_make_it_active: str,
    what_keeps_it_inactive: str,
    blocked_actions: list[str],
) -> dict[str, Any]:
    record = asdict(
        OrphanedCapabilityCandidate(
            capability_id=capability_id,
            display_name=display_name,
            detected_from=detected_from,
            evidence_refs=evidence_refs,
            script_refs=script_refs,
            test_refs=test_refs,
            read_model_refs=read_model_refs,
            sqlite_table_refs=sqlite_table_refs,
            stable_map_status=stable_map_status,
            mission_control_visibility_status=mission_control_visibility_status,
            package_visibility_status=package_visibility_status,
            world_visibility_status=world_visibility_status,
            capability_status=capability_status,
            safe_to_use_pre_security=safe_to_use_pre_security,
            security_review_required=security_review_required,
            operator_review_required=operator_review_required,
            recommended_action=recommended_action,
            what_would_make_it_active=what_would_make_it_active,
            what_keeps_it_inactive=what_keeps_it_inactive,
            blocked_actions=blocked_actions,
        )
    )
    record.update(_record_reconciliation_extension(capability_id))
    return record


def _build_orphaned_capability_detection() -> dict[str, Any]:
    blocked_markdown = [
        "broad Markdown body ingestion",
        "file organization",
        "file moves/deletes/renames",
        "old docs as current truth without classification/proof",
    ]
    candidates = [
        _capability(
            capability_id="markdown_knowledge_atlas",
            display_name="Markdown Knowledge Atlas",
            detected_from=["markdown_knowledge_atlas.py", "scripts/build_markdown_knowledge_atlas.py"],
            evidence_refs=["SQLite metadata counts", "Markdown terrain capability readback"],
            script_refs=["scripts/build_markdown_knowledge_atlas.py"],
            test_refs=[],
            read_model_refs=[],
            sqlite_table_refs=[
                "markdown_documents",
                "markdown_document_classifications",
                "markdown_document_links",
                "markdown_document_reorg_candidates",
                "markdown_document_supersession",
            ],
            stable_map_status="partly_summarized_as_security_decision",
            mission_control_visibility_status="future_visibility_gap",
            package_visibility_status="metadata_reference_possible",
            world_visibility_status="not_world_specific",
            capability_status="KNOWN_NOT_SURFACED",
            safe_to_use_pre_security=True,
            security_review_required=False,
            operator_review_required=False,
            recommended_action="preserve existing capability, avoid duplicate mapper, consider stable-map/app visibility later",
            what_would_make_it_active="Stable-map/app visibility surface with metadata-only boundaries and proof refs.",
            what_keeps_it_inactive="No current app surface and broad body/file mutation remains blocked.",
            blocked_actions=blocked_markdown,
        ),
        _capability(
            capability_id="approved_markdown_evidence_ingestion",
            display_name="Approved Markdown Evidence Ingestion",
            detected_from=["markdown_evidence_ingestion.py", "scripts/ingest_approved_markdown_evidence.py"],
            evidence_refs=["12 approved markdown evidence sources", "206 bounded evidence items"],
            script_refs=["scripts/ingest_approved_markdown_evidence.py"],
            test_refs=[],
            read_model_refs=[],
            sqlite_table_refs=["markdown_evidence_sources", "markdown_evidence_items"],
            stable_map_status="proof_detail_candidate",
            mission_control_visibility_status="not_primary_surface",
            package_visibility_status="proof_detail_reference_possible",
            world_visibility_status="not_world_specific",
            capability_status="KNOWN_NOT_SURFACED",
            safe_to_use_pre_security=True,
            security_review_required=False,
            operator_review_required=False,
            recommended_action="keep as proof/detail capability and expose only bounded metadata later",
            what_would_make_it_active="Allowlisted proof/detail surface with source-card refs and redaction rules.",
            what_keeps_it_inactive="No app-facing proof drawer integration for this capability yet.",
            blocked_actions=[
                "broad body ingestion",
                "unrestricted summarization",
                "stale doctrine promotion",
            ],
        ),
        _capability(
            capability_id="corpus_atlas_engine",
            display_name="Corpus Atlas Engine",
            detected_from=["corpus_atlas.py", "SQLite corpus metadata"],
            evidence_refs=["43,762 corpus_paths rows", "434,362 corpus_path_labels rows"],
            script_refs=["corpus_atlas.py"],
            test_refs=[],
            read_model_refs=[],
            sqlite_table_refs=["corpus_paths", "corpus_path_labels"],
            stable_map_status="not_directly_surfaced",
            mission_control_visibility_status="hidden_by_design_until_classified",
            package_visibility_status="metadata_substrate_only",
            world_visibility_status="not_world_specific",
            capability_status="KNOWN_NOT_SURFACED",
            safe_to_use_pre_security=True,
            security_review_required=True,
            operator_review_required=False,
            recommended_action="treat as metadata substrate; avoid uncontrolled scans",
            what_would_make_it_active="Deterministic source-card/readback contract with scope and privacy boundaries.",
            what_keeps_it_inactive="Broad private body inspection and uncontrolled repo scans remain blocked.",
            blocked_actions=[
                "broad private body inspection",
                "uncontrolled repo scans",
                "runtime crawler activation",
            ],
        ),
        _capability(
            capability_id="security_audit_readiness_packet",
            display_name="Security Audit Readiness Packet",
            detected_from=["security_audit_readiness_packet.py", "generated/read_models/security_audit_readiness_packet.json"],
            evidence_refs=["ff1239f", "02ec429", "371c56d", "d31c91b"],
            script_refs=["scripts/export_security_audit_readiness_packet.py"],
            test_refs=["tests/test_security_audit_readiness_packet.py"],
            read_model_refs=["generated/read_models/security_audit_readiness_packet.json"],
            sqlite_table_refs=[],
            stable_map_status="surfaced",
            mission_control_visibility_status="surfaced",
            package_visibility_status="readiness/provenance/focus/coverage/breadcrumb doctrine",
            world_visibility_status="Helm",
            capability_status="KNOWN_AND_SURFACED",
            safe_to_use_pre_security=True,
            security_review_required=False,
            operator_review_required=False,
            recommended_action="keep as readiness/provenance/focus/coverage/breadcrumb doctrine",
            what_would_make_it_active="Already surfaced as read-only readiness; no runtime activation needed.",
            what_keeps_it_inactive="It is doctrine/readback, not execution authority.",
            blocked_actions=list(STILL_BLOCKED),
        ),
        _capability(
            capability_id="capital_hilton_proof_metadata_packet",
            display_name="Capital Hilton Proof Metadata Packet",
            detected_from=["capital_hilton_proof_metadata_packet.py", "generated/read_models/capital_hilton_proof_metadata_packet.json"],
            evidence_refs=["2a9bede", "b0c80f4", "map_fbda77b8af4e9c796c03"],
            script_refs=["scripts/export_capital_hilton_proof_metadata_packet.py"],
            test_refs=["tests/test_capital_hilton_proof_metadata_packet.py"],
            read_model_refs=["generated/read_models/capital_hilton_proof_metadata_packet.json"],
            sqlite_table_refs=[],
            stable_map_status="surfaced",
            mission_control_visibility_status="surfaced_in_finance_preview",
            package_visibility_status="Finance steel-thread proof metadata",
            world_visibility_status="Finance",
            capability_status="KNOWN_AND_SURFACED",
            safe_to_use_pre_security=True,
            security_review_required=True,
            operator_review_required=False,
            recommended_action="keep as Finance preview/proof metadata; do not convert to invoicing action",
            what_would_make_it_active="Proof metadata, Guardian gate, Operator path, and future action-authority pass.",
            what_keeps_it_inactive="Missing proof count remains 10 and action authority is false.",
            blocked_actions=[
                "invoice generation",
                "Coupa/browser/account access",
                "credentials",
                "send/submit/approval",
            ],
        ),
        _capability(
            capability_id="agent_council_dossier_surface",
            display_name="Agent Council Dossier Surface",
            detected_from=["stable map Agent Council summary", "Mac app checkpoint"],
            evidence_refs=["agent_council.agent_dossier_cards", "5d7f3c3b1d516f5c0eba9daf38b548c789640320"],
            script_refs=[],
            test_refs=["tests/test_operator_map_bundle_contract.py"],
            read_model_refs=["generated/read_models/openclaw_map_snapshot.json#agent_council"],
            sqlite_table_refs=[],
            stable_map_status="surfaced",
            mission_control_visibility_status="surfaced",
            package_visibility_status="actor/persona preview",
            world_visibility_status="Helm",
            capability_status="KNOWN_AND_SURFACED",
            safe_to_use_pre_security=True,
            security_review_required=False,
            operator_review_required=False,
            recommended_action="keep preview-only; no agent activation",
            what_would_make_it_active="Future explicit agent/model/tool authority pass, if ever granted.",
            what_keeps_it_inactive="Agent activation, model calls, tool use, and self-authority remain false.",
            blocked_actions=["live chat", "model launch", "agent activation", "tool use", "hidden memory"],
        ),
        _capability(
            capability_id="package_preview_tool_receipt_surface",
            display_name="Package Preview / Tool Receipt Surface",
            detected_from=["package_preview_receipt_contract.py", "tool_adapter_receipt_contract.py", "Mac app surface"],
            evidence_refs=["1a54dfd", "39eb210", "5d7f3c3b1d516f5c0eba9daf38b548c789640320"],
            script_refs=[
                "scripts/export_package_preview_receipt_contract.py",
                "scripts/export_tool_adapter_receipt_contract.py",
            ],
            test_refs=[
                "tests/test_package_preview_receipt_contract.py",
                "tests/test_tool_adapter_receipt_contract.py",
            ],
            read_model_refs=[
                "generated/read_models/package_preview_receipt_contract.json",
                "generated/read_models/tool_adapter_receipt_contract.json",
            ],
            sqlite_table_refs=[],
            stable_map_status="surfaced",
            mission_control_visibility_status="surfaced",
            package_visibility_status="package/tool preview",
            world_visibility_status="Helm",
            capability_status="KNOWN_AND_SURFACED",
            safe_to_use_pre_security=True,
            security_review_required=False,
            operator_review_required=False,
            recommended_action="keep preview/proof-detail only; no dispatch",
            what_would_make_it_active="Future receipted action-authority pass and per-adapter gate receipts.",
            what_keeps_it_inactive="Dispatch, model launch, tool execution, and account controls remain blocked.",
            blocked_actions=["dispatch", "tool execution", "model launch", "account/browser/send controls"],
        ),
    ]
    return {
        "model_id": "orphaned_capability_detection_v0",
        "description": "Read-only metadata model for finding useful built capability that is not yet surfaced or active.",
        "allowed_capability_statuses": list(ORPHANED_CAPABILITY_STATUSES),
        "required_fields": list(ORPHANED_CAPABILITY_FIELDS),
        "core_doctrine": {
            "built_thing_is_not_active_because_it_exists": True,
            "activation_requires_receipted_classified_gated_trusted_surfaced": True,
            "detection_does_not_execute_capability": True,
            "detection_does_not_create_queue_tasks": True,
            "detection_does_not_mutate_source_notes": True,
        },
        "candidates": candidates,
        "authority_flags": _authority_flags(),
    }


def _promotion_decision_for(candidate: dict[str, Any]) -> dict[str, Any]:
    capability_id = candidate["capability_id"]
    if capability_id in {"markdown_knowledge_atlas", "approved_markdown_evidence_ingestion", "corpus_atlas_engine"}:
        decision = "PROMOTE_TO_STABLE_MAP" if capability_id == "markdown_knowledge_atlas" else "KEEP_AS_PROOF_DETAIL"
        app_surface = "future metadata/proof drawer visibility"
        required_gates = ["metadata-only boundary", "no broad body ingestion"]
    elif candidate["capability_status"] == "KNOWN_AND_SURFACED":
        decision = "KEEP_AS_PROOF_DETAIL"
        app_surface = "already surfaced or proof/detail only"
        required_gates = ["preserve read-only/preview boundary"]
    else:
        decision = "PARK"
        app_surface = "future app surface only after security review"
        required_gates = ["security review"]
    return asdict(
        OrphanedCapabilityPromotionDecision(
            capability_id=capability_id,
            decision=decision,
            reason=candidate["recommended_action"],
            required_proof=candidate["evidence_refs"] + candidate["read_model_refs"],
            required_tests=candidate["test_refs"],
            required_security_gates=required_gates,
            required_stable_map_refs=[] if candidate["stable_map_status"] == "surfaced" else ["future stable-map summary if promoted"],
            required_app_surface=app_surface,
            operator_approval_required=False,
            guardian_gate_required=capability_id == "capital_hilton_proof_metadata_packet",
            action_authority_granted=False,
            next_safe_move="Record recommendation only; do not edit files, queue tasks, activate runtime, or run detected capability.",
        )
    )


def _build_orphaned_capability_promotion_decisions(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model_id": "orphaned_capability_promotion_decision_v0",
        "allowed_decisions": list(ORPHANED_CAPABILITY_PROMOTION_DECISIONS),
        "required_fields": list(ORPHANED_CAPABILITY_PROMOTION_FIELDS),
        "rules": {
            "promotion_decisions_are_recommendations_only": True,
            "must_not_trigger_file_edits": True,
            "must_not_queue_tasks": True,
            "must_not_activate_runtime": True,
            "must_not_run_detected_capability": True,
            "must_not_change_mission_control": True,
        },
        "decisions": [_promotion_decision_for(candidate) for candidate in candidates],
        "authority_flags": _authority_flags(),
    }


def _build_chief_role() -> dict[str, Any]:
    return asdict(
        ChiefReconciliationRole(
            role_id="chief_reconciliation_role",
            display_name="Chief Reconciliation Foreman",
            role_summary=(
                "Chief is the future lead foreman for cued agentic-loop tasks and outside-the-system built work. "
                "Chief reconciles work status and trust gaps but cannot self-authorize execution."
            ),
            current_authority="metadata_review_reconciliation_recommendation_only",
            future_authority_condition=(
                "FULL_TRUST_CLEARANCE plus explicit security-pass approval for the task class and required "
                "Guardian/Operator gates where applicable"
            ),
            can_self_authorize=False,
            allowed_current_actions=[
                "track requested/built/tested/verified/parked/rejected/blocked status",
                "reconcile worker reports against cue items, Markdown/task notes, lanes, receipts, tests, commits, screenshots, and artifacts",
                "identify orphaned capabilities or completed tasks built but not surfaced",
                "recommend cross-off, requeue, repair, park, quarantine, or promotion",
                "explain what prevents FULL_TRUST_CLEARANCE",
                "define trust-building requirements for future automation",
            ],
            blocked_current_actions=[
                "live execution",
                "queue execution",
                "repair execution",
                "tool execution",
                "model calls",
                "agent activation",
                "self-authorization",
                "automatic cross-off",
            ],
            future_gated_actions=[
                "test-harness receipt logic",
                "bounded non-babysat execution after security pass",
                "requeue/repair execution under queue doctrine",
            ],
            reconciliation_responsibilities=[
                "requested vs built",
                "tested vs untested",
                "verified vs reported",
                "completed vs partial vs failed vs duplicate",
                "built-not-surfaced capability detection",
            ],
            test_harness_responsibilities=[
                "future Chief Test Harness Receipt requirements",
                "validation receipt review",
                "failure triage recommendation",
            ],
            trust_gap_responsibilities=[
                "missing proof",
                "missing tests",
                "missing receipts",
                "unclear source task",
                "operator ambiguity",
                "Guardian/Hermes review need",
            ],
            operator_babysitting_reduction_goal=(
                "show the smallest trust-building detour so Winship is not forced to babysit every lane"
            ),
        )
    )


def _build_hermes_role() -> dict[str, Any]:
    return asdict(
        HermesArchitectureReviewRole(
            role_id="hermes_architecture_review_role",
            display_name="Hermes Architecture Review Consultant",
            role_summary=(
                "Hermes is the systems-engineer consultant for architecture, quality, coherence, and high-signal "
                "improvement options. Hermes recommends; Hermes does not execute."
            ),
            current_authority="advisory_architecture_review_metadata_only",
            recommendation_authority="architecture_quality_coherence_candidate_future_gated_or_blocked_recommendations",
            can_self_authorize=False,
            allowed_current_actions=[
                "identify what could be better in built work",
                "identify what should be built next or later",
                "detect architecture drift, duplicate systems, hidden coupling, and doctrine conflicts",
                "recommend high-signal open-source options as advisory candidates",
                "help define trust gaps that move tasks toward FULL_TRUST_CLEARANCE",
            ],
            blocked_current_actions=[
                "execution authority",
                "external dependency adoption",
                "network/API/credential use",
                "model/tool/agent activation",
                "self-authorization",
                "file mutation",
            ],
            future_gated_actions=[
                "architecture approval workflow",
                "external dependency adoption after review",
                "implementation handoff after Operator approval",
            ],
            architecture_review_responsibilities=[
                "coherence with North Star",
                "duplicate system detection",
                "hidden coupling detection",
                "slop and drift review",
                "safe improvement option classification",
            ],
            external_dependency_review_requirements=[
                "source trust review",
                "license review",
                "maintenance/activity review",
                "security risk review",
                "local compatibility review",
                "privacy/data-flow review",
                "Guardian review if sensitive/security-relevant",
                "Operator approval before adoption",
                "no network/API/credential use unless later authorized",
            ],
            trust_gap_support_responsibilities=[
                "recommend missing tests/proof",
                "recommend architecture simplification",
                "recommend merge/reject/park when a lane overlaps existing capability",
            ],
        )
    )


def _build_synergy() -> dict[str, Any]:
    return {
        "chief_question": "Was the work done, tested, reconciled, and ready to cross off or requeue?",
        "hermes_question": "Does this work fit the architecture, improve the system, avoid slop, and point toward the North Star?",
        "guardian_question": "Is this safe, gated, redacted, quarantined, or blocked?",
        "operator_question": "Do I approve this direction, authority, and risk?",
        "decision_order": [
            "Chief reconciliation",
            "Hermes architecture review when architecture relevance is high",
            "Guardian safety gate when sensitive/protected/security-relevant",
            "Operator final decision where required",
        ],
        "conflict_resolution": (
            "Safety blocks beat architecture preference; Operator final authority beats all non-emergency "
            "recommendations; unresolved conflict fails closed."
        ),
        "operator_final_authority": True,
    }


def _build_trust_clearance_model() -> dict[str, Any]:
    requirements = [
        "known task source",
        "known lane/world/package",
        "complete proof refs",
        "authority explicitly granted",
        "risk class allowed",
        "required tests passed",
        "receipts present",
        "conflict locks clear",
        "rollback/recovery path defined where relevant",
        "Chief verification path defined",
        "Guardian gate satisfied where sensitive/protected/security-relevant",
        "Operator gate satisfied where required",
        "no hidden memory/tool/model/account authority",
        "no unreviewed broad filesystem/private access",
        "no unresolved ambiguity that changes outcome or risk",
    ]
    example = TrustClearanceModel(
        trust_clearance_status="HIGH_TRUST_NEEDS_OPERATOR",
        full_trust_clearance_eligible=False,
        trust_clearance_blockers=[
            "action authority not granted",
            "task class security approval not defined",
            "Operator gate still required for future unattended execution",
        ],
        trust_building_detour="Define proof/test/receipt/gate requirements and capture Operator decision.",
        required_proof_refs=["source task ref", "changed artifact refs", "validation proof refs"],
        required_tests=["bounded focused tests for task class"],
        required_receipts=["completion receipt", "Chief verification receipt", "package/tool/model receipts when relevant"],
        required_gates=["Chief reconciliation", "Hermes if architecture-relevant", "Guardian if sensitive", "Operator where required"],
        conflict_locks=["no overlapping lane writes", "no unresolved duplicate capability"],
        rollback_recovery_required=True,
        operator_babysitting_required=True,
        future_unattended_execution_eligible=False,
        action_authority_granted=False,
    )
    return {
        "model_id": "trust_clearance_model_v0",
        "trust_clearance_states": list(TRUST_CLEARANCE_STATES),
        "required_fields": list(TRUST_CLEARANCE_REQUIRED_FIELDS),
        "full_trust_clearance_requirements": requirements,
        "example_record": asdict(example),
        "rules": {
            "full_trust_clearance_is_not_lm_confidence_score": True,
            "full_trust_clearance_does_not_itself_grant_execution_authority": True,
            "unattended_execution_requires_full_trust_and_task_class_approval": True,
            "below_full_trust_tasks_must_not_run_unattended": True,
            "future_autonomy_eligibility_requires_explicit_security_pass_approval_for_task_class": True,
        },
        "authority_flags": _authority_flags(),
    }


def _build_completion_cross_off_rule() -> dict[str, Any]:
    return {
        "rule_id": "completion_cross_off_rule_v0",
        "cross_off_allowed_only_when": [
            "original task/source ref is known",
            "changed artifacts are identified",
            "tests or validation receipts exist",
            "Chief reconciliation passes or marks sufficient proof",
            "Hermes review passes if architecture relevance is high",
            "Guardian gate passes if sensitive/protected/security-relevant",
            "Operator final decision is captured where required",
            "trust_clearance_status is sufficient for that task class",
        ],
        "cross_off_must_not": [
            "delete original note",
            "mutate source Markdown",
            "remove cue source",
            "hide evidence",
            "imply execution authority",
            "happen automatically in this lane",
        ],
        "cross_off_should_create": [
            "completion receipt",
            "completion candidate",
            "quiet-with-proof candidate",
        ],
        "automatic_cross_off_allowed": False,
        "source_markdown_mutation_allowed": False,
        "authority_flags": _authority_flags(),
    }


def _build_trust_building_detours() -> dict[str, Any]:
    return {
        "model_id": "trust_building_detours_v0",
        "trust_gap_types": [
            "missing proof",
            "missing tests",
            "missing receipt",
            "unclear source task",
            "ambiguous operator intent",
            "architecture review needed",
            "Guardian/security gate needed",
            "protected/sensitive material involved",
            "external dependency risk",
            "conflict with another lane",
            "stale terrain/map mismatch",
            "insufficient rollback/recovery path",
        ],
        "smallest_safe_detours": [
            "add proof ref",
            "run bounded test",
            "create receipt",
            "classify source task",
            "ask operator one question",
            "request Hermes architecture review",
            "request Guardian safety review",
            "park until dependency exists",
            "merge with existing lane",
            "reject as obsolete",
        ],
        "below_full_trust_action": "detour_or_operator_assist_or_park_or_block_fail_closed",
        "operator_babysitting_reduction_goal": (
            "show the smallest trust-building detour instead of repeatedly asking Winship to supervise undifferentiated work"
        ),
        "authority_flags": _authority_flags(),
    }


def _build_example_trust_reconciliation_records() -> list[dict[str, Any]]:
    return [
        {
            "record_id": "markdown_knowledge_atlas",
            "chief_reconciliation_status": "BUILT_NOT_SURFACED",
            "chief_summary": "known metadata capability with evidence and SQLite counts",
            "hermes_summary": "app visibility and integration could be improved later",
            "trust_clearance_status": "HIGH_TRUST_NEEDS_HERMES",
            "trust_clearance_scope": "high for metadata readback, not execution",
            "cross_off_allowed": False,
            "execution_authority_granted": False,
            "next_safe_move": "consider stable-map/app visibility later without duplicate mapper",
        },
        {
            "record_id": "security_readiness_surface",
            "chief_reconciliation_status": "COMPLETED_WITH_PROOF",
            "chief_summary": "app surface built with build/screenshot proof reported",
            "hermes_summary": "ELIWINSHIP polish passed",
            "trust_clearance_status": "HIGH_TRUST_NEEDS_OPERATOR",
            "trust_clearance_scope": "high for read-only display",
            "cross_off_allowed": True,
            "execution_authority_granted": False,
            "next_safe_move": "quiet with proof if tied to original task source",
        },
        {
            "record_id": "future_invoicing_state_machine_audit",
            "chief_reconciliation_status": "PARKED_WITH_PROOF",
            "chief_summary": "audit captured as blocked stress-test artifact",
            "hermes_summary": "useful future architecture stress test",
            "trust_clearance_status": "NO_TRUST",
            "trust_clearance_scope": "parked, not implementation",
            "cross_off_allowed": False,
            "execution_authority_granted": False,
            "next_safe_move": "preserve future contracts list; do not implement active invoicing",
        },
        {
            "record_id": "capital_hilton_finance_preview",
            "chief_reconciliation_status": "COMPLETED_NEEDS_VERIFICATION",
            "chief_summary": "Finance preview exists",
            "hermes_summary": "architecture aligns with Finance World / Helm boundary",
            "trust_clearance_status": "HIGH_TRUST_NEEDS_GUARDIAN",
            "trust_clearance_scope": "preview-only",
            "cross_off_allowed": False,
            "execution_authority_granted": False,
            "next_safe_move": "link protected proof metadata and preserve no-action boundary",
        },
    ]


def _build_chief_hermes_trust_building_reconciliation() -> dict[str, Any]:
    return {
        "model_id": "chief_hermes_trust_building_reconciliation_v0",
        "core_doctrine": {
            "chief_hermes_not_permanently_forbidden_future_authority": True,
            "currently_non_executing_until_deterministic_trust_is_earned": True,
            "full_trust_clearance_is_deterministic_not_lm_confidence": True,
            "operator_does_not_want_to_babysit_work": True,
            "system_should_show_smallest_trust_building_detour": True,
        },
        "chief_role": _build_chief_role(),
        "hermes_role": _build_hermes_role(),
        "trust_clearance_model": _build_trust_clearance_model(),
        "example_trust_reconciliation_records": _build_example_trust_reconciliation_records(),
        "authority_flags": _authority_flags(),
    }


def build_security_pass_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    stable_context = _stable_map_context(repo_root)
    capital = _capital_hilton_context(repo_root, stable_context)
    security_readiness = _security_readiness_context(repo_root, stable_context)
    surface_decisions = _surface_security_decisions()
    capital_decision = _capital_hilton_security_pass_decision(capital)
    markdown_decision = _markdown_terrain_security_decision(repo_root)
    operator_answer_decision = _operator_answer_capture_security_decision()
    shared_path_decision = _helm_focus_shared_path_security_decision()
    parked_decision = _parked_breadcrumb_security_decision()
    agent_tool_decision = _agent_model_tool_security_decision()
    worker_output_intake = _build_worker_output_intake()
    orphaned_capability_detection = _build_orphaned_capability_detection()
    orphaned_capability_promotion_decisions = _build_orphaned_capability_promotion_decisions(
        orphaned_capability_detection["candidates"]
    )
    chief_hermes = _build_chief_hermes_trust_building_reconciliation()
    synergy = _build_synergy()
    completion_cross_off_rule = _build_completion_cross_off_rule()
    trust_building_detours = _build_trust_building_detours()
    output_summary = {
        "security_pass_completed": True,
        "security_approval_granted_for_read_only_surfaces": True,
        "security_approval_granted_for_preview_surfaces": True,
        "security_approval_granted_for_metadata_only_surfaces": True,
        "security_approval_granted_for_worker_output_intake_metadata": True,
        "security_approval_granted_for_orphaned_capability_detection": True,
        "security_approval_granted_for_chief_reconciliation_metadata": True,
        "security_approval_granted_for_hermes_architecture_review_metadata": True,
        "security_approval_granted_for_trust_clearance_modeling": True,
        "security_approval_granted_for_execution": False,
        "action_authority_granted": False,
        "runtime_execution_authority_granted": False,
        "tool_execution_authority_granted": False,
        "model_execution_authority_granted": False,
        "queue_execution_authority_granted": False,
        "account_authority_granted": False,
        "send_submit_approval_authority_granted": False,
        "automatic_activation_of_detected_capabilities_allowed": False,
        "automatic_cross_off_allowed": False,
        "chief_self_authorization_allowed": False,
        "hermes_self_authorization_allowed": False,
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "security_pass_contract",
        "pass_id": "pass_1_core_security_decisions_authority_boundaries",
        "pass_2_id": "pass_2_worker_output_intake_orphaned_capability_detection",
        "pass_3_id": "pass_3_chief_hermes_full_trust_clearance",
        "generated_at": generated_at,
        **NO_ACTION_AUTHORITY_FLAGS,
        **output_summary,
        "contract_status": "deterministic_security_pass_pass_1_plus_pass_2_plus_pass_3_metadata_only",
        "operator_summary": (
            "Security Pass Contract v0 Pass 1 approves the current read-only, preview-only, metadata-only, "
            "proof/detail, stable-map, and world-preview surfaces. Pass 2 approves worker-output intake and "
            "orphaned capability detection as metadata. Pass 3 approves Chief/Hermes trust-building and "
            "FULL_TRUST_CLEARANCE modeling while keeping every live action authority false."
        ),
        "core_rule": {
            "security_pass_approval_is_not_action_authority": True,
            "read_only_and_preview_surfaces_can_be_approved_without_execution": True,
            "built_thing_is_not_active_because_it_exists": True,
            "built_thing_becomes_active_only_after_receipted_classified_gated_trusted_surfaced": True,
            "worker_output_is_not_truth_by_itself": True,
            "full_trust_clearance_is_not_lm_confidence": True,
            "full_trust_clearance_does_not_itself_grant_execution_authority": True,
            "unattended_execution_requires_full_trust_and_task_class_approval": True,
            "chief_and_hermes_cannot_self_authorize": True,
            "future_limited_execution_requires_separate_explicit_receipted_authority": True,
        },
        "security_decision_categories": list(SECURITY_DECISION_CATEGORIES),
        "security_decision_schema": {
            "required_fields": list(DECISION_REQUIRED_FIELDS),
            "unknown_or_missing_decision_result": "UNKNOWN_FAIL_CLOSED",
            "approval_category_must_not_imply_execution": True,
        },
        "global_authority_matrix": {
            "allowed_after_this_security_pass": list(ALLOWED_AFTER_PASS),
            "still_blocked": list(STILL_BLOCKED),
            "authority_flags": _authority_flags(),
            "operator_final_authority": True,
            "security_pass_readiness_source": {
                **security_readiness,
                "source_ref": "generated/read_models/security_audit_readiness_packet.json",
            },
        },
        "surface_security_decisions": surface_decisions,
        "capital_hilton_security_pass_decision": capital_decision,
        "markdown_terrain_security_decision": markdown_decision,
        "operator_answer_capture_security_decision": operator_answer_decision,
        "helm_focus_shared_path_security_decision": shared_path_decision,
        "parked_breadcrumb_security_decision": parked_decision,
        "agent_model_tool_security_decision": agent_tool_decision,
        "worker_output_intake": worker_output_intake,
        "orphaned_capability_detection": orphaned_capability_detection,
        "orphaned_capability_promotion_decisions": orphaned_capability_promotion_decisions,
        "chief_hermes_trust_building_reconciliation": chief_hermes,
        "chief_hermes_guardian_operator_synergy": synergy,
        "completion_cross_off_rule": completion_cross_off_rule,
        "trust_building_detours": trust_building_detours,
        "security_pass_output_summary": output_summary,
        "stable_map_integration": {
            "contract_generated_as_read_model": True,
            "summary_included_in_stable_map_now": False,
            "reason_not_included_now": "Pass 1 + Pass 2 + Pass 3 are standalone; stable-map refresh is a separate lane.",
            "next_map_bundle_refresh_requirement": "Next stable-map refresh should include Security Pass Contract v0 Pass 1 + Pass 2 + Pass 3 summary.",
            "safe_summary_for_next_refresh": {
                "security_pass_contract_id": "security_pass_contract",
                "security_pass_completed": True,
                "read_only_surfaces_approved": True,
                "preview_surfaces_approved": True,
                "worker_output_intake_metadata_approved": True,
                "orphaned_capability_detection_approved": True,
                "chief_reconciliation_metadata_approved": True,
                "hermes_architecture_review_metadata_approved": True,
                "trust_clearance_modeling_approved": True,
                "action_authority": False,
                "automatic_cross_off_allowed": False,
                "capital_hilton_preview_approved": True,
                "capital_hilton_execution_blocked": True,
                "markdown_terrain_metadata_approved": True,
                "broad_markdown_body_blocked": True,
                "future_invoicing_audit_parked": True,
                "next_recommended_lane": "stable_map_refresh_security_pass_summary",
            },
        },
        "recommended_next_lanes": [
            {
                "lane_id": "stable_map_refresh_security_pass_summary",
                "title": "Stable Map Refresh with Security Pass Summary",
                "purpose": "make scoped security pass decisions visible to Mission Control",
                "boundary": "stable-map summary only; no Mac sync/import in the contract lane",
            },
        ],
        "machine_proof": {
            "source_read_model_refs": list(SOURCE_READ_MODEL_REFS),
            "map_generation_id": stable_context["map_generation_id"],
            "bundle_hash": stable_context["bundle_hash"],
            "app_visible_map_current": stable_context["app_visible_map_current"],
            "check_transmission_quiet": stable_context["check_transmission_quiet"],
            "security_pass_completed": True,
            "read_only_surfaces_approved": True,
            "preview_surfaces_approved": True,
            "worker_output_intake_metadata_approved": True,
            "orphaned_capability_detection_approved": True,
            "chief_reconciliation_metadata_approved": True,
            "hermes_architecture_review_metadata_approved": True,
            "trust_clearance_modeling_approved": True,
            "worker_output_intake_record_count": len(worker_output_intake["records"]),
            "orphaned_capability_candidate_count": len(orphaned_capability_detection["candidates"]),
            "orphaned_capability_promotion_decision_count": len(orphaned_capability_promotion_decisions["decisions"]),
            "chief_can_self_authorize": False,
            "hermes_can_self_authorize": False,
            "full_trust_clearance_grants_authority_by_itself": False,
            "unattended_execution_requires_full_trust_and_task_class_approval": True,
            "below_full_trust_tasks_can_run_unattended": False,
            "automatic_cross_off_allowed": False,
            "future_invoicing_audit_status": "PARKED",
            "automatic_activation_of_detected_capabilities_allowed": False,
            "surface_decision_count": len(surface_decisions),
            "action_authority_granted": False,
            "runtime_execution_authority_granted": False,
            "model_execution_authority_granted": False,
            "tool_execution_authority_granted": False,
            "queue_execution_authority_granted": False,
            "account_authority_granted": False,
            "send_submit_approval_authority_granted": False,
            "all_dangerous_authority_flags_false": _all_dangerous_authority_false(),
            "stable_map_is_not_source_truth": True,
            "capital_hilton_execution_blocked": True,
            "markdown_metadata_approved_broad_body_blocked": True,
            "operator_answers_are_not_proof": True,
            "shared_paths_are_non_executing": True,
            "parked_breadcrumbs_do_not_auto_promote": True,
            "worker_output_intake_does_not_activate_capabilities": True,
            "orphaned_capability_detection_does_not_execute_capabilities": True,
            "promotion_decisions_are_recommendations_only": True,
            "future_invoicing_audit_does_not_authorize_invoice_generation": True,
            "future_invoicing_audit_does_not_authorize_ledger_writes": True,
            "future_invoicing_audit_does_not_authorize_email_dispatch": True,
            "agent_model_tool_activation_blocked": True,
            "raw_private_body_included": False,
            "credential_or_secret_included": False,
            "network_git_sync_mac_app_mutation_authority_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    summary = payload["security_pass_output_summary"]
    cap = payload["capital_hilton_security_pass_decision"]
    markdown = payload["markdown_terrain_security_decision"]
    worker = payload["worker_output_intake"]
    orphaned = payload["orphaned_capability_detection"]
    trust = payload["chief_hermes_trust_building_reconciliation"]
    chief = trust["chief_role"]
    hermes = trust["hermes_role"]
    clearance = trust["trust_clearance_model"]
    future_audit = {record["worker_output_id"]: record for record in worker["records"]}[
        "future_invoicing_state_machine_audit"
    ]
    lines = [
        "# Security Pass Contract v0 Pass 1 + Pass 2 + Pass 3",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Pass 1 approves the current cockpit as read-only, preview-only, metadata-only, proof/detail, stable-map, and world-preview safe. Pass 2 adds a way to remember worker outputs and already-built capabilities without activating them. Pass 3 defines how Chief and Hermes can help build trust without self-authorizing or running anything. It does not approve live action.",
        "",
        "## Approved",
        "",
        f"- Security pass completed: `{str(summary['security_pass_completed']).lower()}`.",
        f"- Read-only surfaces approved: `{str(summary['security_approval_granted_for_read_only_surfaces']).lower()}`.",
        f"- Preview surfaces approved: `{str(summary['security_approval_granted_for_preview_surfaces']).lower()}`.",
        f"- Metadata-only surfaces approved: `{str(summary['security_approval_granted_for_metadata_only_surfaces']).lower()}`.",
        f"- Worker-output intake metadata approved: `{str(summary['security_approval_granted_for_worker_output_intake_metadata']).lower()}`.",
        f"- Orphaned capability detection approved: `{str(summary['security_approval_granted_for_orphaned_capability_detection']).lower()}`.",
        f"- Chief reconciliation metadata approved: `{str(summary['security_approval_granted_for_chief_reconciliation_metadata']).lower()}`.",
        f"- Hermes architecture review metadata approved: `{str(summary['security_approval_granted_for_hermes_architecture_review_metadata']).lower()}`.",
        f"- Trust-clearance modeling approved: `{str(summary['security_approval_granted_for_trust_clearance_modeling']).lower()}`.",
        f"- Automatic activation of detected capabilities allowed: `{str(summary['automatic_activation_of_detected_capabilities_allowed']).lower()}`.",
        f"- Automatic cross-off allowed: `{str(summary['automatic_cross_off_allowed']).lower()}`.",
        "",
        "## Still Blocked",
        "",
    ]
    lines.extend(f"- {item}" for item in STILL_BLOCKED)
    lines.extend(
        [
            "",
            "## Helm Meaning",
            "",
            "- The helm can show stable-map truth, read-model summaries, proof/detail rows, Security Readiness, Agent Council, Package Preview, Tool Receipts, Finance preview, and Markdown terrain metadata.",
            "- The helm cannot execute work, launch models, activate agents, run tools, access accounts, or submit anything.",
            "",
            "## Finance / Capital Hilton",
            "",
            f"- Current phase: `{cap['current_phase']}`.",
            f"- Target world: `{cap['target_world']}`.",
            f"- Missing proof count: `{cap['missing_proof_count']}`.",
            f"- Protected proof required: `{str(cap['protected_proof_required']).lower()}`.",
            "- Finance World preview, proof metadata display, operator question display, and candidate facts with not-proven labels are approved.",
            "- Coupa, credentials, browser/OAuth/account access, Gmail/calendar/email access, raw Excel, raw finance bodies, invoice generation, and send/submit/approval remain blocked.",
            "",
            "## Markdown Terrain",
            "",
            f"- Backend capability: `{markdown['markdown_backend_capability_status']}`.",
            "- Existing Markdown atlas/evidence systems are the proof substrate.",
            "- Metadata readback and allowlisted bounded evidence excerpt metadata are approved.",
            "- Broad Markdown body ingestion, broad doc reorganization, file moves/deletes/renames, vector indexing, and stale doctrine promotion remain blocked.",
            "- App visibility is a future visibility gap, not a security blocker.",
            "",
            "## Worker Output Intake",
            "",
            "- Worker output can be received as metadata.",
            "- External worker output is not truth by itself.",
            "- Output becomes candidate proof only when linked to commits, tests, receipts, generated artifacts, screenshots, or stable-map refs.",
            "- Intake does not activate anything, create queue tasks, mutate source files, or run detected capabilities.",
            f"- Intake records: `{len(worker['records'])}`.",
            "",
            "## Orphaned Capabilities",
            "",
            "- An orphaned capability is something useful that exists but is not fully registered, surfaced, trusted, or active.",
            "- A built thing is not active because it exists.",
            "- Markdown Atlas is the reference example: it already exists and is safe for metadata readback, so OpenClaw should preserve it and avoid building a duplicate mapper.",
            f"- Capability candidates recorded: `{len(orphaned['candidates'])}`.",
            "- Promotion decisions are recommendations only; they do not trigger file edits, queues, runtime activation, or Mission Control changes.",
            "",
            "## Future Invoicing Audit",
            "",
            f"- Intake status: `{future_audit['intake_status']}`.",
            f"- Reported status: `{future_audit['reported_status']}`.",
            "- The audit is preserved as a future Finance/invoicing stress-test reference.",
            "- Active invoicing remains parked/blocked: no ledger writes, no email dispatch, no Coupa/browser/account/credential authority, no invoice generation, and no send/submit/approval.",
            "- Missing future contracts include deterministic invoice math, idempotency, ledger write/readback receipts, manual lock state, and communication draft receipts.",
            "",
            "## Chief",
            "",
            f"- Current authority: `{chief['current_authority']}`.",
            f"- Can self-authorize: `{str(chief['can_self_authorize']).lower()}`.",
            "- Chief can reconcile whether work was requested, built, tested, verified, parked, rejected, duplicated, or still blocked.",
            "- Chief cannot execute repairs, run queues, run tools, activate agents, or cross items off automatically.",
            "- Chief should show what prevents FULL_TRUST_CLEARANCE and the smallest trust-building detour.",
            "",
            "## Hermes",
            "",
            f"- Current authority: `{hermes['current_authority']}`.",
            f"- Can self-authorize: `{str(hermes['can_self_authorize']).lower()}`.",
            "- Hermes can advise on architecture quality, coherence, duplicate systems, hidden coupling, and high-signal improvement options.",
            "- Hermes cannot adopt dependencies, use network/API/credentials, mutate files, or execute implementation.",
            "- Open-source recommendations are advisory candidates until source, license, maintenance, security, compatibility, privacy, Guardian, and Operator review pass.",
            "",
            "## FULL_TRUST_CLEARANCE",
            "",
            "- FULL_TRUST_CLEARANCE is deterministic clearance, not an LM confidence score.",
            "- It does not grant execution authority by itself.",
            "- Future unattended execution would require FULL_TRUST_CLEARANCE plus explicit security-pass approval for that task class.",
            f"- Example clearance status: `{clearance['example_record']['trust_clearance_status']}`.",
            f"- Future unattended execution eligible: `{str(clearance['example_record']['future_unattended_execution_eligible']).lower()}`.",
            "- Below-threshold tasks detour to proof, tests, receipts, Hermes, Guardian, Operator, park, merge, reject, or fail-closed.",
            "",
            "## Cross-Off",
            "",
            "- Cross-off is a completion candidate, not source deletion.",
            "- It must not delete original notes, mutate Markdown, remove cue sources, hide evidence, imply execution authority, or happen automatically.",
            "- Cross-off should create a completion receipt, completion candidate, or quiet-with-proof candidate.",
            "- This is how the system can eventually reduce babysitting without hiding what happened.",
            "",
            "## Agents / Models / Tools",
            "",
            "- Agent/persona display and package preview are approved.",
            "- Model calls, model router runtime, live agent activation, tool execution, hidden routing, hidden memory, and self-authority remain blocked.",
            "- Stable map reader is read-only approved; package preview exporter is preview/receipt metadata approved; high-risk adapters remain blocked or future-gated.",
            "",
            "## Next",
            "",
            "- A later stable-map refresh should surface this Security Pass summary in Mission Control.",
            "",
            "## Authority Flags",
            "",
        ]
    )
    for key, value in NO_ACTION_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}` = `{value}`")
    return "\n".join(lines) + "\n"


def export_security_pass_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> SecurityPassContractExportResult:
    payload = build_security_pass_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return SecurityPassContractExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        decision_count=len(payload["surface_security_decisions"]),
        security_pass_completed=payload["security_pass_completed"],
        read_only_surfaces_approved=payload["security_approval_granted_for_read_only_surfaces"],
        preview_surfaces_approved=payload["security_approval_granted_for_preview_surfaces"],
        worker_output_intake_approved=payload["security_approval_granted_for_worker_output_intake_metadata"],
        orphaned_capability_detection_approved=payload["security_approval_granted_for_orphaned_capability_detection"],
        chief_reconciliation_approved=payload["security_approval_granted_for_chief_reconciliation_metadata"],
        hermes_architecture_review_approved=payload["security_approval_granted_for_hermes_architecture_review_metadata"],
        trust_clearance_modeling_approved=payload["security_approval_granted_for_trust_clearance_modeling"],
        worker_output_count=len(payload["worker_output_intake"]["records"]),
        orphaned_capability_count=len(payload["orphaned_capability_detection"]["candidates"]),
        action_authority_granted=payload["action_authority_granted"],
        live_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Security Pass Contract v0 Pass 1 + Pass 2 + Pass 3 read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_security_pass_contract(repo_root=args.repo_root, export_root=args.export_root)
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "decision_count": result.decision_count,
        "security_pass_completed": result.security_pass_completed,
        "read_only_surfaces_approved": result.read_only_surfaces_approved,
        "preview_surfaces_approved": result.preview_surfaces_approved,
        "worker_output_intake_approved": result.worker_output_intake_approved,
        "orphaned_capability_detection_approved": result.orphaned_capability_detection_approved,
        "chief_reconciliation_approved": result.chief_reconciliation_approved,
        "hermes_architecture_review_approved": result.hermes_architecture_review_approved,
        "trust_clearance_modeling_approved": result.trust_clearance_modeling_approved,
        "worker_output_count": result.worker_output_count,
        "orphaned_capability_count": result.orphaned_capability_count,
        "action_authority_granted": result.action_authority_granted,
        "live_authority_added": result.live_authority_added,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Security Pass Contract: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_ACTION_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "ORPHANED_CAPABILITY_PROMOTION_DECISIONS",
    "ORPHANED_CAPABILITY_STATUSES",
    "SCHEMA_VERSION",
    "SECURITY_DECISION_CATEGORIES",
    "STILL_BLOCKED",
    "RECONCILIATION_STATES",
    "TRUST_CLEARANCE_STATES",
    "WORKER_OUTPUT_INTAKE_STATUSES",
    "build_security_pass_contract",
    "export_security_pass_contract",
    "format_operator_markdown",
    "main",
    "stable_json",
]
