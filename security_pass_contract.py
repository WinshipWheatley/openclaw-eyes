"""Security Pass Contract v0 Pass 1 for OpenClaw.

This read-model records scoped security pass decisions for read-only,
preview-only, metadata-only, capture-only, proof/detail, stable-map, and world
preview surfaces. It does not create live execution, model calls, model router
runtime, actor/agent activation, tool execution, browser/OAuth/account access,
Gmail/calendar/Coupa/Telegram access, credentials, send/submit/approval,
invoice generation, queue/autonomy, planner/builder execution, Mac sync/import,
network operation, Repo B inspection, file organization, raw private body
ingestion, or PC system-drive write authority.
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

SCHEMA_VERSION = "security_pass_contract_v0_pass_1"
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
    "automatic_world_transition_allowed": False,
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
    "automatic world transition",
    "C-drive artifact writes",
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
class SecurityPassContractExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    decision_count: int
    security_pass_completed: bool
    read_only_surfaces_approved: bool
    preview_surfaces_approved: bool
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
    output_summary = {
        "security_pass_completed": True,
        "security_approval_granted_for_read_only_surfaces": True,
        "security_approval_granted_for_preview_surfaces": True,
        "security_approval_granted_for_metadata_only_surfaces": True,
        "security_approval_granted_for_execution": False,
        "action_authority_granted": False,
        "runtime_execution_authority_granted": False,
        "tool_execution_authority_granted": False,
        "model_execution_authority_granted": False,
        "queue_execution_authority_granted": False,
        "account_authority_granted": False,
        "send_submit_approval_authority_granted": False,
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "security_pass_contract",
        "pass_id": "pass_1_core_security_decisions_authority_boundaries",
        "generated_at": generated_at,
        **NO_ACTION_AUTHORITY_FLAGS,
        **output_summary,
        "contract_status": "deterministic_security_pass_pass_1_read_only_preview_approval_only",
        "operator_summary": (
            "Security Pass Contract v0 Pass 1 approves the current read-only, preview-only, metadata-only, "
            "proof/detail, stable-map, and world-preview surfaces while keeping every live action authority false."
        ),
        "core_rule": {
            "security_pass_approval_is_not_action_authority": True,
            "read_only_and_preview_surfaces_can_be_approved_without_execution": True,
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
        "security_pass_output_summary": output_summary,
        "stable_map_integration": {
            "contract_generated_as_read_model": True,
            "summary_included_in_stable_map_now": False,
            "reason_not_included_now": "Pass 1 is standalone; stable-map refresh is a separate lane.",
            "next_map_bundle_refresh_requirement": "Next stable-map refresh should include Security Pass Contract v0 Pass 1 summary.",
            "safe_summary_for_next_refresh": {
                "security_pass_contract_id": "security_pass_contract",
                "security_pass_completed": True,
                "read_only_surfaces_approved": True,
                "preview_surfaces_approved": True,
                "action_authority": False,
                "capital_hilton_preview_approved": True,
                "capital_hilton_execution_blocked": True,
                "markdown_terrain_metadata_approved": True,
                "broad_markdown_body_blocked": True,
                "next_recommended_lane": "security_pass_contract_v0_pass_2_worker_output_intake_or_orphaned_capability_detection",
            },
        },
        "recommended_next_lanes": [
            {
                "lane_id": "security_pass_contract_v0_pass_2_worker_output_intake",
                "title": "Security Pass Contract v0 Pass 2 - Worker Output Intake / Orphaned Capability Detection",
                "purpose": "classify worker outputs and orphaned capabilities without granting execution authority",
                "boundary": "read-model only; no intake daemon, queue, or automation",
            },
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
    lines = [
        "# Security Pass Contract v0 Pass 1",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Pass 1 approves the current cockpit as read-only, preview-only, metadata-only, proof/detail, stable-map, and world-preview safe. It does not approve live action.",
        "",
        "## Approved",
        "",
        f"- Security pass completed: `{str(summary['security_pass_completed']).lower()}`.",
        f"- Read-only surfaces approved: `{str(summary['security_approval_granted_for_read_only_surfaces']).lower()}`.",
        f"- Preview surfaces approved: `{str(summary['security_approval_granted_for_preview_surfaces']).lower()}`.",
        f"- Metadata-only surfaces approved: `{str(summary['security_approval_granted_for_metadata_only_surfaces']).lower()}`.",
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
            "## Agents / Models / Tools",
            "",
            "- Agent/persona display and package preview are approved.",
            "- Model calls, model router runtime, live agent activation, tool execution, hidden routing, hidden memory, and self-authority remain blocked.",
            "- Stable map reader is read-only approved; package preview exporter is preview/receipt metadata approved; high-risk adapters remain blocked or future-gated.",
            "",
            "## Next",
            "",
            "- Pass 2 should handle Worker Output Intake / Orphaned Capability Detection.",
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
        action_authority_granted=payload["action_authority_granted"],
        live_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Security Pass Contract v0 Pass 1 read-model.")
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
    "SCHEMA_VERSION",
    "SECURITY_DECISION_CATEGORIES",
    "STILL_BLOCKED",
    "build_security_pass_contract",
    "export_security_pass_contract",
    "format_operator_markdown",
    "main",
    "stable_json",
]
