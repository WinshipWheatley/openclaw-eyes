"""Operator awareness and agent package spine contract v0.

This read-model defines the Mission Control backend contract for showing what
OpenClaw knows, partly knows, knows it does not know, has not discovered yet,
and would package for a future agent/actor review. It is deterministic
read-model metadata only: it does not call models, activate agents, enable
tools, inspect Repo B, open browsers, access OAuth/credentials/Gmail/calendar/
Coupa, send messages, create a live chat, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "operator_awareness_agent_package_spine_v0"
JSON_EXPORT_NAME = "operator_awareness_agent_package_spine.json"
OPERATOR_EXPORT_NAME = "operator_awareness_agent_package_spine_OPERATOR.md"

CONFIDENCE_POSTURES = (
    "FULL_TRUST_DISPLAY_QUIET",
    "HIGH_TRUST",
    "MEDIUM_TRUST",
    "LOW_TRUST",
    "UNKNOWN_FAIL_CLOSED",
)

AWARENESS_STATES = (
    "KNOWN",
    "PARTLY_KNOWN",
    "KNOWN_UNKNOWN",
    "UNDISCOVERED",
    "OPERATOR_MEMORY_COMPARISON_NEEDED",
    "DISCOVERY_OR_CLASSIFICATION_NEEDED",
    "BLOCKED_ON_PURPOSE",
    "KNOWN_BUT_NOT_USABLE",
)

DETOUR_WORKSPACE_TYPES = (
    "MARKDOWN_OK",
    "HTML_WORKSPACE_RECOMMENDED",
    "STRUCTURED_FORM_RECOMMENDED",
    "OPERATOR_MEMORY_COMPARISON",
    "DISCOVERY_OR_CLASSIFICATION",
    "PROOF_CAPTURE",
    "CONTEXT_CAPTURE",
    "CLASSIFICATION_REVIEW",
)

BUTTON_INTERACTION_MODES = (
    "READ_ONLY",
    "CAPTURE_ONLY",
    "FUTURE_GATED",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "contract_only": True,
    "package_preview_only": True,
    "button_metadata_only": True,
    "confidence_posture_only": True,
    "detour_recommendation_only": True,
    "sqlite_schema_changed": False,
    "model_calls_made": False,
    "lm_called": False,
    "tools_enabled": False,
    "tool_execution_authority_added": False,
    "agents_activated": False,
    "agent_activation_authority_added": False,
    "live_chat_created": False,
    "browser_accessed": False,
    "browser_automation_added": False,
    "oauth_or_credentials_accessed": False,
    "credential_or_pii_access_added": False,
    "gmail_calendar_coupa_accessed": False,
    "email_send_triggered": False,
    "telegram_send_triggered": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "repo_b_modules_imported": False,
    "private_raw_content_inspected": False,
    "raw_protected_content_accessed": False,
    "calendar_cleanup_started": False,
    "coupa_accessed": False,
}


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class AwarenessGapSpec:
    gap_id: str
    title: str
    short_eli5_description: str
    why_it_matters: str
    current_awareness_state: str
    domain: str
    what_openclaw_knows: tuple[str, ...]
    what_openclaw_partly_knows: tuple[str, ...]
    what_openclaw_knows_it_does_not_know: tuple[str, ...]
    what_openclaw_has_not_discovered_yet: tuple[str, ...]
    what_winship_may_remember: tuple[str, ...]
    what_should_be_found_classified_next: tuple[str, ...]
    what_should_be_pulled_into_sqlite_read_models_next: tuple[str, ...]
    what_is_blocked: tuple[str, ...]
    recommended_agent_character: str
    recommended_actor_role_fit: str
    confidence_posture: str
    why_not_full_confidence: str
    what_would_raise_confidence: tuple[str, ...]
    detour_to_raise_confidence: str
    detour_workspace_type: str
    safe_next_move: str
    safe_to_proceed_at_lower_confidence: bool
    proceed_scope_if_safe: str
    blocked_actions: tuple[str, ...]
    source_read_model_refs: tuple[str, ...]
    machine_proof_refs: tuple[str, ...]


@dataclass(frozen=True)
class OperatorAwarenessAgentPackageSpineExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    awareness_gap_item_count: int
    package_preview_only: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel("cross_repo_awareness_matrix", "generated/read_models/cross_repo_awareness_matrix.json", "cross-repo awareness and Repo B delta classification surface"),
    SourceReadModel("capability_skill_registry_metadata_delta", "generated/read_models/capability_skill_registry_metadata_delta.json", "capability/skill metadata posture"),
    SourceReadModel("build_now_vs_hold_queue_posture", "generated/read_models/build_now_vs_hold_queue_posture.json", "ready/hold/blocked work posture"),
    SourceReadModel("chief_status_rail", "generated/read_models/chief_status_rail.json", "Chief status visibility rail"),
    SourceReadModel("chief_role_capability_segmentation_map", "generated/read_models/chief_role_capability_segmentation_map.json", "Chief role/capability segmentation"),
    SourceReadModel("protected_access_broker_concept", "generated/read_models/protected_access_broker_concept.json", "protected access concept"),
    SourceReadModel("protected_evidence_reference_receipt", "generated/read_models/protected_evidence_reference_receipt.json", "protected proof reference receipt contract"),
    SourceReadModel("guardian_protected_access_gate_spec", "generated/read_models/guardian_protected_access_gate_spec.json", "Guardian protected-access gate"),
    SourceReadModel("cassandra_email_calendar_delta_detangle", "generated/read_models/cassandra_email_calendar_delta_detangle.json", "Cassandra email/calendar detangle"),
    SourceReadModel("agent_work_packets", "generated/read_models/agent_work_packets.json", "bounded agent work-packet metadata"),
    SourceReadModel("operator_actions", "generated/read_models/operator_actions.json", "operator action posture"),
    SourceReadModel("intent_router", "generated/read_models/intent_router.json", "non-executing intent routing metadata"),
    SourceReadModel("dropped_intents", "generated/read_models/dropped_intents.json", "deferred/unresolved intent registry"),
    SourceReadModel("work_board", "generated/read_models/work_board.json", "Mission Control work-board substrate"),
    SourceReadModel("niles_album_review_packet", "generated/read_models/niles_album_review_packet.json", "Niles album review packet"),
    SourceReadModel("niles_album_metadata_intake_packet", "generated/read_models/niles_album_metadata_intake_packet.json", "Niles album metadata intake"),
    SourceReadModel("struna_obscura_project_capsule", "generated/read_models/struna_obscura_project_capsule.json", "Struna project capsule"),
    SourceReadModel("report_bridge", "generated/read_models/report_bridge.json", "Report Bridge visibility rail"),
    SourceReadModel("repo_a_known_rail_completion_map", "generated/read_models/repo_a_known_rail_completion_map.json", "Repo A rail baseline"),
    SourceReadModel("repo_b_remaining_capability_delta_map", "generated/read_models/repo_b_remaining_capability_delta_map.json", "Repo B delta read-model reference only"),
)

SOURCE_FILES = (
    "cross_repo_awareness_matrix.py",
    "capability_skill_registry_metadata_delta.py",
    "build_now_vs_hold_queue_posture.py",
    "chief_status_rail.py",
    "chief_role_capability_segmentation_map.py",
    "protected_access_broker_concept.py",
    "protected_evidence_reference_receipt.py",
    "guardian_protected_access_gate_spec.py",
    "cassandra_email_calendar_delta_detangle.py",
    "agent_work_packet.py",
    "work_board.py",
    "intent_router.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists() or target.suffix.lower() != ".json":
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _source_record(source: SourceReadModel, *, repo_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    target = _rooted(source.path, repo_root=repo_root)
    return {
        "key": source.key,
        "path": source.path,
        "present": target.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": source.role,
        "truth_status": "repo_a_read_model_evidence_not_operator_truth_by_itself",
        "repo_a_only": True,
        "repo_b_delta_read_model_used": source.key == "repo_b_remaining_capability_delta_map" and bool(payload),
        "repo_b_filesystem_inspected": False,
        "repo_b_code_executed": False,
        "raw_private_content_read": False,
        "executed_or_dispatched": False,
    }


def _source_file_record(path: str, *, repo_root: str | Path) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    return {
        "path": path,
        "present": target.exists(),
        "role": "source_contract_or_export_pattern_reference",
        "body_exported": False,
        "runtime_imported": False,
        "executed_or_dispatched": False,
    }


def _actor_metadata(agent: str, role_fit: str, risk_fit: str = "bounded_metadata_review") -> dict[str, Any]:
    return {
        "recommended_agent_character": agent,
        "actor_role_fit": role_fit,
        "task_fit": "read_model_interpretation_and_package_review_only",
        "risk_fit": risk_fit,
        "collaboration_fit": "can_work_with_guardian_or_chief_when_domain_boundary_requires_it",
        "availability_status": "metadata_only_unknown_until_future_actor_runtime_lane",
        "unavailable_or_unknown_actor_fails_closed": True,
        "model_execution_path": None,
        "api_key_or_endpoint_reference": None,
        "metadata_only_no_model_call": True,
    }


def _awareness_state_breakdown(spec: AwarenessGapSpec) -> dict[str, bool]:
    state = spec.current_awareness_state
    return {
        "known": bool(spec.what_openclaw_knows),
        "partly_known": bool(spec.what_openclaw_partly_knows) or state == "PARTLY_KNOWN",
        "known_unknown": bool(spec.what_openclaw_knows_it_does_not_know) or state == "KNOWN_UNKNOWN",
        "undiscovered": bool(spec.what_openclaw_has_not_discovered_yet) or state == "UNDISCOVERED",
        "operator_memory_comparison": bool(spec.what_winship_may_remember) or state == "OPERATOR_MEMORY_COMPARISON_NEEDED",
        "blocked": bool(spec.what_is_blocked) or state in {"BLOCKED_ON_PURPOSE", "KNOWN_BUT_NOT_USABLE"},
    }


def _button_ids_for_gap(spec: AwarenessGapSpec) -> list[str]:
    button_ids = [
        "INSPECT_LARGER_DESCRIPTION",
        "SHOW_PACKAGE_PREVIEW",
    ]
    if spec.confidence_posture != "FULL_TRUST_DISPLAY_QUIET":
        button_ids.extend(["WHY_NOT_FULL_CONFIDENCE", "DETOUR_TO_RAISE_CONFIDENCE"])
    if spec.safe_to_proceed_at_lower_confidence:
        button_ids.append("PROCEED_ANYWAY_IF_SAFE")
    if spec.what_winship_may_remember:
        button_ids.append("MARK_NEEDS_OPERATOR_MEMORY_COMPARISON")
    if spec.what_should_be_found_classified_next:
        button_ids.append("START_DISCOVERY_CLASSIFICATION")
    if spec.current_awareness_state in {"BLOCKED_ON_PURPOSE", "KNOWN_BUT_NOT_USABLE"} or spec.what_is_blocked:
        button_ids.append("KEEP_PARKED")
    return list(dict.fromkeys(button_ids))


def _gap_record(spec: AwarenessGapSpec) -> dict[str, Any]:
    if spec.current_awareness_state not in AWARENESS_STATES:
        raise ValueError(f"unknown awareness state: {spec.current_awareness_state}")
    if spec.confidence_posture not in CONFIDENCE_POSTURES:
        raise ValueError(f"unknown confidence posture: {spec.confidence_posture}")
    if spec.detour_workspace_type not in DETOUR_WORKSPACE_TYPES:
        raise ValueError(f"unknown detour workspace type: {spec.detour_workspace_type}")
    confidence_visible = spec.confidence_posture != "FULL_TRUST_DISPLAY_QUIET"
    return {
        "gap_id": spec.gap_id,
        "title": spec.title,
        "short_eli5_description": spec.short_eli5_description,
        "why_it_matters": spec.why_it_matters,
        "current_awareness_state": spec.current_awareness_state,
        "awareness_state_breakdown": _awareness_state_breakdown(spec),
        "domain": spec.domain,
        "what_openclaw_knows": list(spec.what_openclaw_knows),
        "what_openclaw_partly_knows": list(spec.what_openclaw_partly_knows),
        "what_openclaw_knows_it_does_not_know": list(spec.what_openclaw_knows_it_does_not_know),
        "what_openclaw_has_not_discovered_yet": list(spec.what_openclaw_has_not_discovered_yet),
        "what_winship_may_remember": list(spec.what_winship_may_remember),
        "operator_memory_comparison_mode": "memory_can_point_to_a_gap_but_does_not_become_truth_without_read_model_or_proof",
        "operator_memory_is_treated_as_truth": False,
        "what_should_be_found_classified_next": list(spec.what_should_be_found_classified_next),
        "what_should_be_pulled_into_sqlite_read_models_next": list(spec.what_should_be_pulled_into_sqlite_read_models_next),
        "what_is_blocked": list(spec.what_is_blocked),
        "recommended_agent_character": spec.recommended_agent_character,
        "recommended_actor_model_metadata": _actor_metadata(
            spec.recommended_agent_character,
            spec.recommended_actor_role_fit,
            "protected_or_low_power_metadata_review" if spec.what_is_blocked else "bounded_metadata_review",
        ),
        "confidence_posture": spec.confidence_posture,
        "confidence_should_be_visible_in_helm": confidence_visible,
        "confidence_display_should_be": "visible" if confidence_visible else "quiet",
        "why_not_full_confidence": spec.why_not_full_confidence,
        "what_would_raise_confidence": list(spec.what_would_raise_confidence),
        "detour_to_raise_confidence": {
            "lane_name": spec.detour_to_raise_confidence,
            "workspace_type": spec.detour_workspace_type,
            "bounded": True,
            "non_live": True,
            "preserves_blocked_authorities": True,
        },
        "detour_workspace_type": spec.detour_workspace_type,
        "safe_next_move": spec.safe_next_move,
        "safe_to_proceed_at_lower_confidence": spec.safe_to_proceed_at_lower_confidence,
        "proceed_scope_if_safe": spec.proceed_scope_if_safe,
        "blocked_actions": list(spec.blocked_actions),
        "source_read_model_refs": list(spec.source_read_model_refs),
        "machine_proof_refs": list(spec.machine_proof_refs),
        "future_button_ids": _button_ids_for_gap(spec),
        "button_ready_metadata": {
            "clickable_item_id": spec.gap_id,
            "display_title": spec.title,
            "default_button": "INSPECT_LARGER_DESCRIPTION",
            "show_confidence_affordance": confidence_visible,
            "show_package_preview_affordance": True,
            "mutates_state_now": False,
            "requires_future_receipt_if_mutated": True,
        },
        "package_preview_ref": "agent_package_spine_contract_layers.layer_4_full_agent_package_preview",
    }


def _gap_specs() -> tuple[AwarenessGapSpec, ...]:
    return (
        AwarenessGapSpec(
            gap_id="capital_hilton_coupa_excel_proof",
            title="Capital Hilton needs Coupa/Excel proof",
            short_eli5_description="OpenClaw can describe the finance proof lane, but it does not have the real protected Coupa or Excel proof metadata yet.",
            why_it_matters="The package should not ask Cassandra or Guardian to reason about invoice completion as if proof exists.",
            current_awareness_state="PARTLY_KNOWN",
            domain="comms_finance_protected_proof",
            what_openclaw_knows=(
                "Capital Hilton review, proof, and send-gate read-model rails exist.",
                "Protected proof must be represented as metadata or protected references only.",
            ),
            what_openclaw_partly_knows=(
                "The expected Coupa/Excel/PDF proof receipt shape is defined.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "The actual protected Coupa payment proof reference is missing.",
                "The actual Excel companion proof reference is missing.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "A validated protected reference receipt tied to the current Capital Hilton workflow.",
            ),
            what_winship_may_remember=(
                "Whether the Coupa portal and Excel/PDF evidence already exist outside the current read-models.",
            ),
            what_should_be_found_classified_next=(
                "Find or classify safe protected proof metadata fields, not raw proof bodies.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "protected_reference_id, artifact hash/identity, amount, PO/reference, validation status, and mismatch reasons.",
            ),
            what_is_blocked=(
                "Coupa access, browser automation, raw Excel/PDF bodies, Gmail/email send, spreadsheet mutation, and payment status changes.",
            ),
            recommended_agent_character="Cassandra with Guardian boundary review",
            recommended_actor_role_fit="finance_comms_packet_interpreter_with_safety_boundary",
            confidence_posture="MEDIUM_TRUST",
            why_not_full_confidence="The shape of the proof rail is known, but real protected proof metadata is absent.",
            what_would_raise_confidence=(
                "Populate protected proof metadata through a future protected-reference receipt lane.",
                "Confirm which artifact identities belong to this workflow.",
            ),
            detour_to_raise_confidence="Capital Hilton Protected Proof Metadata Population",
            detour_workspace_type="PROOF_CAPTURE",
            safe_next_move="Show the missing proof gap and prepare a protected-proof metadata capture lane.",
            safe_to_proceed_at_lower_confidence=True,
            proceed_scope_if_safe="read_only_package_preview_or_operator_inspection_only",
            blocked_actions=(
                "open Coupa",
                "open Excel/PDF proof",
                "send email",
                "submit invoice",
                "mutate spreadsheet",
            ),
            source_read_model_refs=(
                "capital_hilton_actionable_review_packet.json",
                "capital_hilton_external_artifact_proof_capture.json",
                "protected_evidence_reference_receipt.json",
                "guardian_protected_access_gate_spec.json",
            ),
            machine_proof_refs=(
                "protected_reference_receipt_contract",
                "guardian_protected_access_gate",
            ),
        ),
        AwarenessGapSpec(
            gap_id="niles_real_album_metadata",
            title="Niles needs real album metadata",
            short_eli5_description="OpenClaw can see Niles/Struna packet rails, but the real album metadata still has to be captured or verified.",
            why_it_matters="Music packages should not pretend track, release, personnel, or artifact metadata is known when it is only a rail shape.",
            current_awareness_state="PARTLY_KNOWN",
            domain="music",
            what_openclaw_knows=(
                "Niles/Struna review and metadata-intake read-models exist.",
            ),
            what_openclaw_partly_knows=(
                "The album review packet can hold bounded project metadata.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "Real album metadata completeness is not proven.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "Canonical track/release/personnel/artifact metadata for the current album workflow.",
            ),
            what_winship_may_remember=(
                "Which Struna/Niles album facts or files should be treated as canonical candidates.",
            ),
            what_should_be_found_classified_next=(
                "Classify real album metadata inputs as safe metadata, protected/private, stale, or blocked.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "album identity, track metadata, status, source references, and confidence notes.",
            ),
            what_is_blocked=(
                "Producer runtime, audio/file automation, public release execution, and raw private creative scans.",
            ),
            recommended_agent_character="Niles",
            recommended_actor_role_fit="music_metadata_interpreter",
            confidence_posture="MEDIUM_TRUST",
            why_not_full_confidence="The rail exists, but real metadata has not been verified as current truth.",
            what_would_raise_confidence=(
                "Capture current album metadata in a bounded Niles metadata intake lane.",
                "Separate canonical metadata from drafts, stale files, and private raw material.",
            ),
            detour_to_raise_confidence="Niles Real Album Metadata Intake",
            detour_workspace_type="STRUCTURED_FORM_RECOMMENDED",
            safe_next_move="Prepare a structured metadata intake/review packet for Niles.",
            safe_to_proceed_at_lower_confidence=True,
            proceed_scope_if_safe="read_only_album_packet_preview_only",
            blocked_actions=(
                "run producer bot",
                "move or transform audio files",
                "publish or release material",
            ),
            source_read_model_refs=(
                "niles_album_review_packet.json",
                "niles_album_metadata_intake_packet.json",
                "struna_obscura_project_capsule.json",
            ),
            machine_proof_refs=("niles_packet_metadata",),
        ),
        AwarenessGapSpec(
            gap_id="hermes_status_memory_proof_review",
            title="Hermes status needs memory/proof review",
            short_eli5_description="OpenClaw remembers Hermes as an advisory role, but it does not have proof of a completed Hermes steel-thread rail.",
            why_it_matters="Mission Control should not show Hermes as fully ready if the system only has memory and metadata hints.",
            current_awareness_state="OPERATOR_MEMORY_COMPARISON_NEEDED",
            domain="big_picture_advisory",
            what_openclaw_knows=(
                "Hermes is present as advisory metadata/reference.",
            ),
            what_openclaw_partly_knows=(
                "Repo A and delta read-models point to Hermes as a remembered or partial surface.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "No completed Hermes status/readiness rail is proven.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "Current Hermes responsibilities, proof sources, and readiness status.",
            ),
            what_winship_may_remember=(
                "Whether Hermes had a real advisory status, source set, or synthesis workflow that should be raised up.",
            ),
            what_should_be_found_classified_next=(
                "Classify Hermes as tracked, partial, parked, blocked, or obsolete from Repo A evidence plus operator memory comparison.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "Hermes status, evidence references, role boundary, and next-safe-lane classification.",
            ),
            what_is_blocked=(
                "Live advisory agent activation, LLM/model calls, external research/tool execution.",
            ),
            recommended_agent_character="Hermes",
            recommended_actor_role_fit="advisory_status_interpreter",
            confidence_posture="LOW_TRUST",
            why_not_full_confidence="Hermes is known as a concept, not as a proven current rail.",
            what_would_raise_confidence=(
                "Run a Hermes status memory/proof review lane.",
                "Attach Repo A read-model evidence or explicitly park Hermes as reference-only.",
            ),
            detour_to_raise_confidence="Hermes Status Memory/Proof Review",
            detour_workspace_type="OPERATOR_MEMORY_COMPARISON",
            safe_next_move="Ask Winship to compare the visible Hermes map against memory, then classify the result.",
            safe_to_proceed_at_lower_confidence=False,
            proceed_scope_if_safe="not_safe_to_send_as_work_package_until_status_is_classified",
            blocked_actions=(
                "activate Hermes",
                "call an advisory model",
                "run external research",
            ),
            source_read_model_refs=(
                "cross_repo_awareness_matrix.json",
                "capability_skill_registry_metadata_delta.json",
                "repo_a_known_rail_completion_map.json",
            ),
            machine_proof_refs=("operator_memory_gap_not_truth",),
        ),
        AwarenessGapSpec(
            gap_id="google_apple_calendar_merge_clarification",
            title="Google/Apple calendar merge needs clarification",
            short_eli5_description="OpenClaw has operator context about calendar confusion, but it has not read or normalized calendars.",
            why_it_matters="Calendar context can affect Cassandra packages, but memory about calendar behavior is not proof.",
            current_awareness_state="OPERATOR_MEMORY_COMPARISON_NEEDED",
            domain="comms_calendar",
            what_openclaw_knows=(
                "Cassandra email/calendar detangle records calendar discovery and normalization as blocked/future.",
            ),
            what_openclaw_partly_knows=(
                "Operator context says Google and Apple calendars are merged enough for iPhone while Mac Calendar is confusing.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "No live calendar evidence, source normalization proof, or account-state proof exists.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "Which calendar sources matter for a named workflow and what metadata is safe to record.",
            ),
            what_winship_may_remember=(
                "Which calendar is canonical enough for specific tasks and which confusion should be ignored or tracked.",
            ),
            what_should_be_found_classified_next=(
                "Clarify whether this is a real workflow blocker, parked context, or future protected-access lane.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "calendar context note, named workflow need, source labels, and proof/memory boundary.",
            ),
            what_is_blocked=(
                "Google Calendar read, Apple Calendar read, OAuth, event scraping, calendar mutation, and generic cleanup.",
            ),
            recommended_agent_character="Cassandra with Guardian boundary review",
            recommended_actor_role_fit="calendar_context_interpreter",
            confidence_posture="LOW_TRUST",
            why_not_full_confidence="The system has operator memory/context only and no calendar proof.",
            what_would_raise_confidence=(
                "Run a Calendar Context Discovery / Memory Comparison detour.",
                "Tie any calendar context to a named workflow before proof capture.",
            ),
            detour_to_raise_confidence="Calendar Context Discovery / Memory Comparison",
            detour_workspace_type="OPERATOR_MEMORY_COMPARISON",
            safe_next_move="Treat calendar context as memory to compare, not a fact to use.",
            safe_to_proceed_at_lower_confidence=False,
            proceed_scope_if_safe="not_safe_to_use_calendar_context_in_agent_package_until_clarified",
            blocked_actions=(
                "read calendars",
                "start OAuth",
                "normalize calendars",
                "mutate events",
            ),
            source_read_model_refs=(
                "cassandra_email_calendar_delta_detangle.json",
                "protected_access_broker_concept.json",
            ),
            machine_proof_refs=("calendar_memory_not_truth",),
        ),
        AwarenessGapSpec(
            gap_id="agentic_loop_workflow_classification",
            title="Agentic loop workflow needs discovery/classification",
            short_eli5_description="OpenClaw knows old automation-loop ideas exist, but they are not safe or classified as current runtime.",
            why_it_matters="Agentic loop language can accidentally imply execution authority unless it is classified as blocked, future, or bounded.",
            current_awareness_state="DISCOVERY_OR_CLASSIFICATION_NEEDED",
            domain="coordination_work_queue",
            what_openclaw_knows=(
                "Planner/builder and repair loops are represented as blocked or future-gated metadata.",
            ),
            what_openclaw_partly_knows=(
                "Chief and build-now-vs-hold rails can classify work posture without running it.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "Which remembered agentic loop workflow, if any, should be promoted as a safe non-live contract.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "A named, bounded, non-live workflow classification for agentic loops.",
            ),
            what_winship_may_remember=(
                "Which old loop ideas mattered and which should stay blocked or obsolete.",
            ),
            what_should_be_found_classified_next=(
                "Classify each loop idea as blocked automation, read-model posture, work-packet scaffold, or future security-threshold work.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "loop name, intended role, blocked authorities, safe substitute rail, and future lane recommendation.",
            ),
            what_is_blocked=(
                "Autonomous build execution, repair loops, shell/runtime activation, LLM/Ollama calls, and tool execution.",
            ),
            recommended_agent_character="Chief with Guardian boundary review",
            recommended_actor_role_fit="coordination_loop_classifier",
            confidence_posture="UNKNOWN_FAIL_CLOSED",
            why_not_full_confidence="Unknown or broad agentic-loop context could imply live authority, so it fails closed.",
            what_would_raise_confidence=(
                "Run an Agentic Loop Workflow Classification detour.",
                "Name the loop, classify authority boundaries, and map it to a non-live read-model if safe.",
            ),
            detour_to_raise_confidence="Agentic Loop Workflow Classification",
            detour_workspace_type="DISCOVERY_OR_CLASSIFICATION",
            safe_next_move="Keep loop ideas blocked until they are classified into bounded read-model/work-packet posture.",
            safe_to_proceed_at_lower_confidence=False,
            proceed_scope_if_safe="fail_closed_no_package_send",
            blocked_actions=(
                "activate autonomous loop",
                "execute shell",
                "call model",
                "run tools",
                "start repair",
            ),
            source_read_model_refs=(
                "build_now_vs_hold_queue_posture.json",
                "capability_skill_registry_metadata_delta.json",
                "chief_role_capability_segmentation_map.json",
            ),
            machine_proof_refs=("blocked_automation_metadata",),
        ),
        AwarenessGapSpec(
            gap_id="chief_test_harness_classification",
            title="Chief test harness needs discovery/classification",
            short_eli5_description="OpenClaw needs to classify what a Chief test harness means before treating it as ready work.",
            why_it_matters="A harness might be a safe test/read-model lane or a live runtime lane; unknown context must not be guessed.",
            current_awareness_state="DISCOVERY_OR_CLASSIFICATION_NEEDED",
            domain="coordination_work_queue",
            what_openclaw_knows=(
                "Chief status, work packets, intent router, and work board are visible as non-executing substrates.",
            ),
            what_openclaw_partly_knows=(
                "Chief can support bounded packet/status work.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "Whether the remembered Chief test harness is tests, fixtures, status proof, or runtime validation.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "A named harness contract and its allowed inputs/outputs.",
            ),
            what_winship_may_remember=(
                "What Chief test harness existed and what outcome it was meant to prove.",
            ),
            what_should_be_found_classified_next=(
                "Classify the harness as unit tests, read-model export proof, synthetic fixture, or blocked runtime test.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "harness purpose, source read-models, proof output, blocked authorities, and pass/fail posture.",
            ),
            what_is_blocked=(
                "Chief runtime imports, Telegram/listener activation, service starts, model/tool calls, and shell automation.",
            ),
            recommended_agent_character="Chief",
            recommended_actor_role_fit="chief_status_test_contract_classifier",
            confidence_posture="LOW_TRUST",
            why_not_full_confidence="The phrase is remembered, but the system lacks a classified harness contract.",
            what_would_raise_confidence=(
                "Run a Chief Test Harness Capability Classification detour.",
                "Separate deterministic tests from runtime/service validation.",
            ),
            detour_to_raise_confidence="Chief Test Harness Capability Classification",
            detour_workspace_type="CLASSIFICATION_REVIEW",
            safe_next_move="Create a non-live classification packet before writing or running any harness.",
            safe_to_proceed_at_lower_confidence=False,
            proceed_scope_if_safe="classification_first_no_runtime",
            blocked_actions=(
                "import Chief runtime modules",
                "start services",
                "send Telegram",
                "call model",
            ),
            source_read_model_refs=(
                "chief_status_rail.json",
                "chief_role_capability_segmentation_map.json",
                "agent_work_packets.json",
                "work_board.json",
            ),
            machine_proof_refs=("chief_non_executor_status",),
        ),
        AwarenessGapSpec(
            gap_id="brain_dump_cue_parser_classification",
            title="Brain-dump / cue parser needs discovery/classification",
            short_eli5_description="OpenClaw preserves dropped-intent metadata, but a governed cue parser is still future work.",
            why_it_matters="Cue parsing can be useful only if it avoids raw private scans, file moves, and model-driven truth promotion.",
            current_awareness_state="DISCOVERY_OR_CLASSIFICATION_NEEDED",
            domain="coordination_work_queue",
            what_openclaw_knows=(
                "Dropped intents and build-now-vs-hold posture preserve ideas without execution.",
            ),
            what_openclaw_partly_knows=(
                "A cue parser would likely feed intent routing and Chief posture.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "The governed cue parser boundary and input model are not complete.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "Which cue sources are allowed, what metadata can be stored, and how classification receipts would work.",
            ),
            what_winship_may_remember=(
                "Which brain-dump/cue workflow should be revived, parked, or discarded.",
            ),
            what_should_be_found_classified_next=(
                "Classify cue sources, storage rules, raw-body boundaries, and safe next moves.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "cue id, short sanitized preview/hash metadata, route target, confidence posture, and blocker metadata.",
            ),
            what_is_blocked=(
                "Broad Markdown ingestion, raw private note scans, LLM/Ollama parsing, file moves, and truth promotion.",
            ),
            recommended_agent_character="Chief",
            recommended_actor_role_fit="operator_cue_intake_classifier",
            confidence_posture="LOW_TRUST",
            why_not_full_confidence="The safe dropped-intent rail exists, but cue-parser governance is not proven.",
            what_would_raise_confidence=(
                "Run a Cue Parser Intake Classification detour.",
                "Define allowed cue inputs and receipt shape before any parser behavior.",
            ),
            detour_to_raise_confidence="Cue Parser Intake Classification",
            detour_workspace_type="DISCOVERY_OR_CLASSIFICATION",
            safe_next_move="Keep using dropped-intent metadata until a governed cue parser contract exists.",
            safe_to_proceed_at_lower_confidence=True,
            proceed_scope_if_safe="read_only_gap_inspection_and_contract_planning_only",
            blocked_actions=(
                "scan raw private notes",
                "call LLM/Ollama",
                "move files",
                "promote cues to truth automatically",
            ),
            source_read_model_refs=(
                "dropped_intents.json",
                "intent_router.json",
                "build_now_vs_hold_queue_posture.json",
            ),
            machine_proof_refs=("dropped_intent_metadata_only",),
        ),
        AwarenessGapSpec(
            gap_id="repo_b_leftovers_tag_or_block",
            title="Repo B leftovers need tagging or blocking",
            short_eli5_description="OpenClaw has a Repo A read-model saying some leftovers may exist, but this lane must not inspect or run Repo B.",
            why_it_matters="Mission Control should show leftovers as classification needs, not hidden capabilities.",
            current_awareness_state="KNOWN_UNKNOWN",
            domain="cross_repo_awareness",
            what_openclaw_knows=(
                "Cross-repo awareness and Repo B delta read-models can represent already-tracked, partial, blocked, and untagged leftovers.",
            ),
            what_openclaw_partly_knows=(
                "Some leftover path metadata may need future tagging or blocking.",
            ),
            what_openclaw_knows_it_does_not_know=(
                "Any unclassified leftover is not safe to treat as current Repo A capability.",
            ),
            what_openclaw_has_not_discovered_yet=(
                "The next specific leftover item Winship remembers but Mission Control is not seeing.",
            ),
            what_winship_may_remember=(
                "A named file, concept, or workflow from older Repo B work that should be classified safely.",
            ),
            what_should_be_found_classified_next=(
                "Use an explicit future classification packet to tag a named leftover as tracked, partial, obsolete, unsafe, or blocked.",
            ),
            what_should_be_pulled_into_sqlite_read_models_next=(
                "leftover id, source path metadata, classification, current Repo A equivalent, blocker, and next lane.",
            ),
            what_is_blocked=(
                "Repo B code execution, Repo B module imports, code migration, private raw content inspection, and live loop activation.",
            ),
            recommended_agent_character="Chief with Guardian boundary review",
            recommended_actor_role_fit="cross_repo_classification_interpreter",
            confidence_posture="UNKNOWN_FAIL_CLOSED",
            why_not_full_confidence="Unknown leftovers must be classified from safe metadata before being treated as facts or capabilities.",
            what_would_raise_confidence=(
                "Run a Repo B Leftover Classification Packet for one named leftover.",
                "Keep any unknown leftover fail-closed until classification is complete.",
            ),
            detour_to_raise_confidence="Repo B Leftover Classification Packet",
            detour_workspace_type="CLASSIFICATION_REVIEW",
            safe_next_move="Ask Winship for the missing X, then classify it from safe Repo A/read-model metadata in a future lane.",
            safe_to_proceed_at_lower_confidence=False,
            proceed_scope_if_safe="fail_closed_no_repo_b_inspection_or_package_send",
            blocked_actions=(
                "inspect Repo B body content",
                "run Repo B code",
                "import Repo B modules",
                "migrate code",
                "activate old loops",
            ),
            source_read_model_refs=(
                "cross_repo_awareness_matrix.json",
                "repo_b_remaining_capability_delta_map.json",
            ),
            machine_proof_refs=("repo_b_reference_only_delta",),
        ),
    )


def _button_behavior_contract() -> dict[str, Any]:
    button_specs = (
        (
            "INSPECT_LARGER_DESCRIPTION",
            "Inspect Larger Description",
            "visible_for_every_awareness_gap_item",
            "Expanded ELI5, operator detail, source refs, and blockers.",
            "It must not read raw private content, inspect Repo B, call models, or mutate state.",
            "READ_ONLY",
            "not_required_read_only",
        ),
        (
            "SHOW_PACKAGE_PREVIEW",
            "Show Package Preview",
            "visible_when_a_gap_can_be_mapped_to_a_package_or_future_package",
            "The exact reviewable package body placeholder, included/excluded surfaces, allowed/blocked actions, and receipt instructions.",
            "It must not dispatch a package, activate an agent, call an actor/model, or create a live chat.",
            "READ_ONLY",
            "not_required_read_only",
        ),
        (
            "WHY_NOT_FULL_CONFIDENCE",
            "Why Not Full Confidence?",
            "visible_when_confidence_posture_is_not_FULL_TRUST_DISPLAY_QUIET",
            "Missing memory, context, proof, read-models, blockers, and why the helm is showing confidence.",
            "It must not fabricate certainty or hide missing context.",
            "READ_ONLY",
            "not_required_read_only",
        ),
        (
            "DETOUR_TO_RAISE_CONFIDENCE",
            "Detour to Raise Confidence",
            "visible_when_a_bounded_detour_lane_is_available",
            "A bounded non-live lane recommendation and workspace type.",
            "It must not start the detour, run tools, access accounts, or mutate read-models without a future receipt.",
            "FUTURE_GATED",
            "detour_lane_start_receipt_if_future_mutation_occurs",
        ),
        (
            "PROCEED_ANYWAY_IF_SAFE",
            "Proceed Anyway, if safe",
            "visible_only_when_safe_to_proceed_at_lower_confidence_is_true",
            "The limited read-only or capture-only scope that remains safe despite lower confidence.",
            "It must not bypass blocked authorities or send to an agent when fail-closed is required.",
            "FUTURE_GATED",
            "lower_confidence_proceed_receipt_if_future_mutation_occurs",
        ),
        (
            "KEEP_PARKED",
            "Keep Parked",
            "visible_when_an_item_is_blocked_deferred_or_not_usable",
            "Why the item stays parked and what would change the posture later.",
            "It must not silently delete, hide, or mark the item solved.",
            "CAPTURE_ONLY",
            "parked_posture_receipt_if_future_state_changes",
        ),
        (
            "MARK_NEEDS_OPERATOR_MEMORY_COMPARISON",
            "Mark Needs Operator Memory Comparison",
            "visible_when_operator_memory_may_identify_missing_context",
            "A capture target for Winship memory comparison, explicitly labeled memory-not-truth.",
            "It must not promote memory into truth or proof by itself.",
            "CAPTURE_ONLY",
            "operator_memory_comparison_receipt_if_future_state_changes",
        ),
        (
            "START_DISCOVERY_CLASSIFICATION",
            "Start Discovery/Classification",
            "visible_when_the_next_move_is_find_or_classify",
            "The future classification lane, allowed evidence sources, and fail-closed defaults.",
            "It must not inspect Repo B, run tools, call models, access accounts, or broaden scope automatically.",
            "FUTURE_GATED",
            "discovery_classification_receipt_if_future_state_changes",
        ),
    )
    return {
        "buttons_are_metadata_only": True,
        "buttons_mutate_state_now": False,
        "button_interaction_modes": list(BUTTON_INTERACTION_MODES),
        "button_types": [
            {
                "button_id": button_id,
                "label": label,
                "visible_condition": visible_condition,
                "what_it_should_show": should_show,
                "what_it_must_not_do": must_not_do,
                "interaction_mode": mode,
                "required_future_receipt_if_it_ever_mutates_state": receipt,
            }
            for (
                button_id,
                label,
                visible_condition,
                should_show,
                must_not_do,
                mode,
                receipt,
            ) in button_specs
        ],
    }


def _agent_actor_routing_metadata() -> dict[str, Any]:
    return {
        "metadata_only": True,
        "domain_to_likely_agents": [
            {"domain": "music", "likely_agents": ["Niles"]},
            {"domain": "comms/finance", "likely_agents": ["Cassandra", "Guardian"]},
            {"domain": "safety/security", "likely_agents": ["Guardian"]},
            {"domain": "coordination/work queue", "likely_agents": ["Chief"]},
            {"domain": "big-picture/advisory", "likely_agents": ["Hermes"]},
            {"domain": "client/reporting", "likely_agents": ["Report Bridge", "Chief"]},
        ],
        "possible_chat_modes": [
            {
                "mode": "ONE_AGENT",
                "metadata_meaning": "one character receives a future package preview",
                "live_chat_created_now": False,
            },
            {
                "mode": "TWO_SIDE_BY_SIDE_AGENTS",
                "metadata_meaning": "two characters can be compared without letting either execute",
                "live_chat_created_now": False,
            },
            {
                "mode": "GROUP_CHAT",
                "metadata_meaning": "future grouped review, not current runtime",
                "live_chat_created_now": False,
            },
            {
                "mode": "ORDERED_MULTI_AGENT_RESPONSE",
                "metadata_meaning": "future deterministic ordering, for example Cassandra then Guardian",
                "live_chat_created_now": False,
            },
            {
                "mode": "DETERMINISTIC_ORDER_BASED_ON_TASK_RISK_DOMAIN",
                "metadata_meaning": "routing order is derived from domain and risk before any actor selection",
                "live_chat_created_now": False,
            },
        ],
        "actor_model_recommendation_metadata_fields": [
            "actor_role_fit",
            "task_fit",
            "risk_fit",
            "collaboration_fit",
            "availability_status",
            "unavailable_or_unknown_actor_fails_closed",
        ],
        "unavailable_or_unknown_actor_fails_closed": True,
        "no_real_api_key_credential_endpoint_or_execution_path": True,
    }


def _operator_eli5_summary() -> dict[str, str]:
    return {
        "openclaw_remembers_in_sqlite_read_models": "OpenClaw remembers durable facts and posture in SQLite-backed records and generated read-models.",
        "mission_control_shows_known_unknown": "Mission Control should show what OpenClaw knows, partly knows, knows it does not know, and has not discovered yet.",
        "winship_compares_memory": "Winship compares that map against memory to spot missing X without memory becoming truth by itself.",
        "missing_things_can_be_found_classified": "Missing things become safe discovery/classification work, then tracked read-model data or explicit blockers.",
        "agents_interpret_domain_context": "Agents/characters such as Chief, Cassandra, Guardian, Niles, Hermes, and Report Bridge interpret domain context.",
        "actors_models_perform_role": "Actors/models are only future performers of a role; this contract stores recommendation metadata, not execution.",
        "mission_control_shows_human_truth": "Mission Control should display deterministic human-readable truth from the package, not hand-authored Swift guesses.",
        "proof_sits_underneath": "Machine proof stays underneath as source read-models, receipts, classifications, blockers, and boundaries.",
        "package_preview_shows_exact_context": "The package preview shows what context would be sent later, including included and excluded surfaces.",
        "confidence_quiet_when_full": "When trust is full, confidence stays display-quiet.",
        "confidence_explains_missing_when_not_full": "When trust is not full, the helm should explain what is missing and what would raise confidence.",
        "detour_raises_confidence": "A detour is a small bounded workspace for adding memory, context, proof, or classification before running or sending anything.",
        "nothing_live_runs_from_this_contract": "Nothing live runs from this contract: no model call, tool, agent, browser, OAuth, Gmail, calendar, Coupa, send, or runtime authority.",
    }


def _layer_1(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "layer_id": "layer_1_eli5_current_truth",
        "what_openclaw_knows": [
            "Capital Hilton, Cassandra, Chief, Guardian, Niles/Struna, protected proof references, work packets, and cross-repo awareness are visible as read-model-backed surfaces.",
            "Review packets, proof rails, approval request specs, work-board cards, dropped intents, and capability metadata can be shown as deterministic posture.",
        ],
        "what_openclaw_partly_knows": [
            record["title"]
            for record in records
            if record["awareness_state_breakdown"]["partly_known"]
        ],
        "what_openclaw_knows_it_does_not_know": [
            record["title"]
            for record in records
            if record["awareness_state_breakdown"]["known_unknown"]
        ],
        "what_openclaw_has_not_discovered_yet": [
            record["title"]
            for record in records
            if record["awareness_state_breakdown"]["undiscovered"]
            or record["current_awareness_state"] == "DISCOVERY_OR_CLASSIFICATION_NEEDED"
        ],
        "what_winship_may_remember_that_system_is_not_seeing": [
            record["title"]
            for record in records
            if record["awareness_state_breakdown"]["operator_memory_comparison"]
        ],
        "what_needs_to_be_found_classified": [
            record["title"]
            for record in records
            if record["what_should_be_found_classified_next"]
        ],
        "what_is_blocked": [
            record["title"]
            for record in records
            if record["awareness_state_breakdown"]["blocked"]
        ],
        "next_safe_move": "Show the awareness map, let Winship identify missing X, then use a bounded non-live detour to classify or capture proof before package use.",
    }


def _layer_2(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "layer_id": "layer_2_human_operator_detail",
        "machine_proof_is_primary_human_layer": False,
        "ready_to_inspect": [record["gap_id"] for record in records if record["what_openclaw_knows"]],
        "ready_for_bounded_work": [
            record["gap_id"]
            for record in records
            if record["safe_to_proceed_at_lower_confidence"]
        ],
        "parked_on_purpose": [
            record["gap_id"]
            for record in records
            if record["current_awareness_state"] in {"BLOCKED_ON_PURPOSE", "KNOWN_BUT_NOT_USABLE"}
            or "KEEP_PARKED" in record["future_button_ids"]
        ],
        "needs_context": [
            record["gap_id"]
            for record in records
            if record["detour_workspace_type"] in {"CONTEXT_CAPTURE", "OPERATOR_MEMORY_COMPARISON"}
        ],
        "needs_proof": [
            record["gap_id"]
            for record in records
            if record["detour_workspace_type"] == "PROOF_CAPTURE" or "proof" in record["why_not_full_confidence"].lower()
        ],
        "needs_operator_memory_comparison": [
            record["gap_id"]
            for record in records
            if record["awareness_state_breakdown"]["operator_memory_comparison"]
        ],
        "needs_discovery_classification": [
            record["gap_id"]
            for record in records
            if record["what_should_be_found_classified_next"]
        ],
        "blocked_on_purpose": [
            record["gap_id"]
            for record in records
            if record["blocked_actions"]
        ],
        "known_but_not_usable": [
            record["gap_id"]
            for record in records
            if record["confidence_posture"] == "UNKNOWN_FAIL_CLOSED" or not record["safe_to_proceed_at_lower_confidence"]
        ],
        "still_to_raise_up": [
            record["gap_id"]
            for record in records
            if record["confidence_posture"] != "FULL_TRUST_DISPLAY_QUIET"
        ],
    }


def _layer_3(
    *,
    source_records: list[dict[str, Any]],
    source_file_records: list[dict[str, Any]],
    records: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "layer_id": "layer_3_machine_proof",
        "machine_proof_is_not_main_human_layer": True,
        "read_model_references": source_records,
        "source_files": source_file_records,
        "receipts": [
            "protected_evidence_reference_receipt.json",
            "guardian_protected_access_gate_spec.json",
            "operator_actions.json",
        ],
        "classifications": {
            "confidence_postures": list(CONFIDENCE_POSTURES),
            "awareness_states": list(AWARENESS_STATES),
            "cross_repo_classification_counts": sources.get("cross_repo_awareness_matrix", {}).get("classification_counts", {}),
            "gap_classification_summary": [
                {
                    "gap_id": record["gap_id"],
                    "current_awareness_state": record["current_awareness_state"],
                    "confidence_posture": record["confidence_posture"],
                }
                for record in records
            ],
        },
        "blockers": sorted({blocked for record in records for blocked in record["blocked_actions"]}),
        "authority_boundaries": dict(NO_AUTHORITY_FLAGS),
        "generated_outputs": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
    }


def _package_preview(records: list[dict[str, Any]]) -> dict[str, Any]:
    included_read_models = sorted(
        {
            ref
            for record in records
            for ref in record["source_read_model_refs"]
        }
    )
    package_body = {
        "package_contract_id": SCHEMA_VERSION,
        "selected_surface_domain": "operator_awareness_agent_package_spine",
        "task_goal": "Explain current system awareness, gaps, proof, package preview, and confidence repair path without execution.",
        "agent_character_recommendation": "Chief primary for awareness map; route domain slices to Cassandra, Guardian, Niles, Hermes, or Report Bridge as metadata.",
        "actor_model_recommendation_metadata": {
            "actor_role_fit": "read_model_interpreter_and_future_package_reviewer",
            "task_fit": "summarize_deterministic_package_and_missing_inputs",
            "risk_fit": "metadata_only_no_live_authority",
            "collaboration_fit": "ordered_by_domain_and_risk_with_guardian_for_protected_or_blocked_surfaces",
            "availability_status": "unknown_until_future_runtime_lane",
            "unavailable_or_unknown_actor_fails_closed": True,
        },
        "included_read_models": included_read_models,
        "excluded_sensitive_surfaces": [
            "raw Gmail bodies",
            "raw calendar bodies",
            "Coupa portal access",
            "raw Excel/PDF proof bodies",
            "credentials/OAuth tokens",
            "Repo B code or raw private content",
        ],
        "allowed_actions": [
            "read generated Repo A read-model metadata",
            "show human operator summary",
            "show machine proof references",
            "show package preview",
            "recommend bounded detour lane",
        ],
        "blocked_actions": [
            "call any model",
            "activate any agent",
            "enable tools",
            "start browser/OAuth/account access",
            "send email or Telegram",
            "submit Coupa or payment work",
            "inspect Repo B",
            "grant runtime authority",
        ],
        "expected_output": "Mission Control-readable awareness map, gap list, proof layer, package preview, confidence posture, and bounded detour recommendation.",
        "receipt_storage_instructions": "Future mutations require explicit receipts; this v0 package preview writes only generated read-model JSON and operator Markdown.",
        "copyable_reviewable_package_body_placeholder": "This body is inspectable text for future handoff review only; it is not sent or executed.",
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    digest = hashlib.sha256(stable_json(package_body).encode("utf-8")).hexdigest()
    return {
        "layer_id": "layer_4_full_agent_package_preview",
        "package_preview_exists_without_executing_anything": True,
        "selected_surface_domain": package_body["selected_surface_domain"],
        "task_goal": package_body["task_goal"],
        "agent_character_recommendation": package_body["agent_character_recommendation"],
        "actor_model_recommendation_metadata": package_body["actor_model_recommendation_metadata"],
        "included_read_models": included_read_models,
        "excluded_sensitive_surfaces": package_body["excluded_sensitive_surfaces"],
        "allowed_actions": package_body["allowed_actions"],
        "blocked_actions": package_body["blocked_actions"],
        "expected_output": package_body["expected_output"],
        "receipt_storage_instructions": package_body["receipt_storage_instructions"],
        "package_hash_or_deterministic_placeholder": f"sha256:{digest}",
        "copyable_reviewable_package_body_placeholder": stable_json(package_body),
        "model_call_allowed": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }


def _repair_path(
    missing: str,
    detour: str,
    workspace_type: str,
    safe_to_proceed: bool,
) -> dict[str, Any]:
    return {
        "missing_input_or_confidence_reason": missing,
        "suggested_detour_lane": detour,
        "detour_workspace_type": workspace_type,
        "bounded": True,
        "non_live": True,
        "safe_to_proceed_at_lower_confidence": safe_to_proceed,
        "fail_closed": not safe_to_proceed,
        "preserve_blocked_authorities": True,
        "does_not_pretend_missing_context_exists": True,
    }


def _confidence_repair_behavior(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "confidence_postures": list(CONFIDENCE_POSTURES),
        "full_trust_display_policy": {
            "posture": "FULL_TRUST_DISPLAY_QUIET",
            "confidence_should_be_visible_in_helm": False,
            "meaning": "No noisy confidence affordance when the package is fully supported by deterministic read-model/proof posture.",
        },
        "below_full_trust_policy": {
            "confidence_should_be_visible_in_helm": True,
            "must_surface_why_not_full": True,
            "must_list_missing_inputs": True,
            "must_propose_bounded_detour": True,
            "must_preserve_blocked_authorities": True,
            "must_not_pretend_missing_context_exists": True,
        },
        "default_unknown_or_missing_context": {
            "confidence_posture": "UNKNOWN_FAIL_CLOSED",
            "fail_closed": True,
            "safe_to_proceed_at_lower_confidence": False,
        },
        "repair_paths": [
            _repair_path("Missing Hermes confidence", "Hermes Status Memory/Proof Review", "OPERATOR_MEMORY_COMPARISON", False),
            _repair_path("Missing calendar proof", "Calendar Context Discovery / Memory Comparison", "OPERATOR_MEMORY_COMPARISON", False),
            _repair_path("Missing Coupa proof", "Capital Hilton Protected Proof Metadata Population", "PROOF_CAPTURE", True),
            _repair_path("Unknown Repo B leftover", "Repo B Leftover Classification Packet", "CLASSIFICATION_REVIEW", False),
            _repair_path("Missing draft identity", "Cassandra Draft Identity Reference Rail", "STRUCTURED_FORM_RECOMMENDED", True),
            _repair_path("Agentic loop unclear", "Agentic Loop Workflow Classification", "DISCOVERY_OR_CLASSIFICATION", False),
            _repair_path("Chief test harness unclear", "Chief Test Harness Capability Classification", "CLASSIFICATION_REVIEW", False),
            _repair_path("Brain-dump/cue parser unclear", "Cue Parser Intake Classification", "DISCOVERY_OR_CLASSIFICATION", True),
        ],
        "gap_level_confidence": [
            {
                "gap_id": record["gap_id"],
                "confidence_posture": record["confidence_posture"],
                "confidence_should_be_visible_in_helm": record["confidence_should_be_visible_in_helm"],
                "why_not_full_confidence": record["why_not_full_confidence"],
                "what_would_raise_confidence": record["what_would_raise_confidence"],
                "detour": record["detour_to_raise_confidence"],
                "safe_to_proceed_at_lower_confidence": record["safe_to_proceed_at_lower_confidence"],
            }
            for record in records
        ],
    }


def _layer_5(records: list[dict[str, Any]]) -> dict[str, Any]:
    not_full = [
        record
        for record in records
        if record["confidence_posture"] != "FULL_TRUST_DISPLAY_QUIET"
    ]
    return {
        "layer_id": "layer_5_confidence_raise_confidence_path",
        "confidence_posture": "MEDIUM_TRUST",
        "confidence_should_be_visible_in_helm": True,
        "reasons_confidence_is_not_full": [
            record["why_not_full_confidence"]
            for record in not_full
        ],
        "missing_memory_context_proof_read_models": [
            {
                "gap_id": record["gap_id"],
                "missing": record["what_openclaw_knows_it_does_not_know"]
                + record["what_openclaw_has_not_discovered_yet"],
            }
            for record in not_full
        ],
        "suggested_detour_to_raise_confidence": "Use each gap item's bounded detour lane before package dispatch.",
        "safe_to_proceed_at_lower_confidence": False,
        "fail_closed_for_unknown_or_live_authority": True,
        "detour_workspace_types": list(DETOUR_WORKSPACE_TYPES),
        "detour_workspace_type_policy": {
            "MARKDOWN_OK": "Use for simple read-only review notes.",
            "HTML_WORKSPACE_RECOMMENDED": "Use only when dense comparison or structured controls are needed.",
            "STRUCTURED_FORM_RECOMMENDED": "Use when exact fields must be captured.",
            "OPERATOR_MEMORY_COMPARISON": "Use when Winship memory must be compared against read-model evidence without becoming truth.",
            "DISCOVERY_OR_CLASSIFICATION": "Use when a missing item needs safe classification.",
            "PROOF_CAPTURE": "Use when protected proof metadata must be collected.",
            "CONTEXT_CAPTURE": "Use when non-proof context is missing.",
            "CLASSIFICATION_REVIEW": "Use when an item must be tagged, parked, blocked, or promoted.",
        },
    }


def _current_awareness_examples(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cross_repo_awareness": {
            "aware_of": ["Capital Hilton", "Cassandra", "Chief", "Guardian", "Niles/Struna"],
            "repo_b_leftovers_not_fully_classified": "represented_as_gap_item_not_fact",
            "hermes_status_needs_memory_proof_review": "represented_as_operator_memory_comparison_needed",
            "google_apple_calendar_merge_needs_clarification": "represented_as_memory_context_not_calendar_truth",
        },
        "chief_queue_work_board": {
            "ready_to_inspect": True,
            "bounded_work_packet_exists": True,
            "parked_or_deferred_work_exists": True,
            "execution_authority": False,
        },
        "protected_access": {
            "protected_proof_can_be_referenced": True,
            "receipt_is_key_approval_or_execution": False,
            "guardian_gate_blocks_access_now": True,
        },
        "cassandra": {
            "review_draft_packets_safe_as_visibility": True,
            "gmail_calendar_telegram_live_send_blocked": True,
        },
        "gap_item_ids": [record["gap_id"] for record in records],
    }


def build_operator_awareness_agent_package_spine(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sources = {
        source.key: _read_json_if_present(source.path, repo_root=repo_root)
        for source in SOURCE_READ_MODELS
    }
    source_records = [
        _source_record(source, repo_root=repo_root, payload=sources[source.key])
        for source in SOURCE_READ_MODELS
    ]
    source_file_records = [
        _source_file_record(path, repo_root=repo_root)
        for path in SOURCE_FILES
    ]
    gap_records = [_gap_record(spec) for spec in _gap_specs()]
    package_preview = _package_preview(gap_records)
    layers = {
        "layer_1_eli5_current_truth": _layer_1(gap_records),
        "layer_2_human_operator_detail": _layer_2(gap_records),
        "layer_3_machine_proof": _layer_3(
            source_records=source_records,
            source_file_records=source_file_records,
            records=gap_records,
            sources=sources,
        ),
        "layer_4_full_agent_package_preview": package_preview,
        "layer_5_confidence_raise_confidence_path": _layer_5(gap_records),
    }
    confidence_repair = _confidence_repair_behavior(gap_records)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Operator Awareness + Agent Package Spine Contract v0",
        "spine_status": "deterministic_read_model_contract_only",
        "mission_control_primary_human_layers": [
            "layer_1_eli5_current_truth",
            "layer_2_human_operator_detail",
        ],
        "machine_proof_stays_underneath": True,
        "agent_package_spine_contract_layers": layers,
        "operator_eli5_summary": _operator_eli5_summary(),
        "awareness_states": list(AWARENESS_STATES),
        "awareness_gap_items_are_button_ready": True,
        "awareness_gap_items": gap_records,
        "button_behavior_contract": _button_behavior_contract(),
        "agent_actor_routing_metadata": _agent_actor_routing_metadata(),
        "confidence_repair_behavior": confidence_repair,
        "detour_workspace_types": list(DETOUR_WORKSPACE_TYPES),
        "current_awareness_examples_from_existing_read_models": _current_awareness_examples(gap_records),
        "output_supports_aware_of_x_not_y": {
            "aware_of_x": layers["layer_1_eli5_current_truth"]["what_openclaw_knows"],
            "not_yet_aware_or_not_classified_y": layers["layer_1_eli5_current_truth"]["what_openclaw_has_not_discovered_yet"],
            "operator_memory_items_are_discovery_needs_not_facts": True,
        },
        "no_live_authority_statement": "No model/tool/agent/browser/OAuth/credential/Gmail/calendar/Coupa/send/runtime authority is added.",
        "source_read_models": source_records,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lanes": [
            "Hermes Status Memory/Proof Review",
            "Calendar Context Discovery / Memory Comparison",
            "Repo B Leftover Classification Packet",
        ],
    }


def format_operator_awareness_agent_package_spine(payload: dict[str, Any]) -> str:
    summary = payload["operator_eli5_summary"]
    layer_1 = payload["agent_package_spine_contract_layers"]["layer_1_eli5_current_truth"]
    layer_5 = payload["agent_package_spine_contract_layers"]["layer_5_confidence_raise_confidence_path"]
    lines = [
        "# Operator Awareness + Agent Package Spine Contract v0",
        "",
        "Status:",
        "- Deterministic read-model contract only.",
        "- Primary human layers: ELI5 current truth and human operator detail.",
        "- Machine proof stays underneath.",
        "- Package preview exists, but no agent, actor, model, tool, browser, OAuth, account, send, or runtime authority is added.",
        "",
        "## ELI5 Summary",
    ]
    for value in summary.values():
        lines.append(f"- {value}")
    lines.extend(
        [
            "",
            "## Current Truth",
            "- Knows: " + " ".join(layer_1["what_openclaw_knows"]),
            "- Partly knows: " + ", ".join(layer_1["what_openclaw_partly_knows"]),
            "- Knows it does not know: " + ", ".join(layer_1["what_openclaw_knows_it_does_not_know"]),
            "- Has not discovered yet: " + ", ".join(layer_1["what_openclaw_has_not_discovered_yet"]),
            "- Winship memory comparison: " + ", ".join(layer_1["what_winship_may_remember_that_system_is_not_seeing"]),
            "- Blocked: " + ", ".join(layer_1["what_is_blocked"]),
            f"- Next safe move: {layer_1['next_safe_move']}",
            "",
            "## Awareness Gap Items",
        ]
    )
    for item in payload["awareness_gap_items"]:
        lines.append(
            f"- `{item['gap_id']}`: {item['title']} | confidence `{item['confidence_posture']}` | detour `{item['detour_to_raise_confidence']['lane_name']}`"
        )
    lines.extend(
        [
            "",
            "## Button Metadata",
        ]
    )
    for button in payload["button_behavior_contract"]["button_types"]:
        lines.append(f"- `{button['button_id']}`: {button['label']} ({button['interaction_mode']})")
    lines.extend(
        [
            "",
            "## Package And Confidence",
            f"- Package hash placeholder: `{payload['agent_package_spine_contract_layers']['layer_4_full_agent_package_preview']['package_hash_or_deterministic_placeholder']}`.",
            f"- Overall confidence posture: `{layer_5['confidence_posture']}`.",
            f"- Confidence visible in helm: `{str(layer_5['confidence_should_be_visible_in_helm']).lower()}`.",
            "- Full trust display policy: confidence is quiet when posture is `FULL_TRUST_DISPLAY_QUIET`.",
            "",
            "## Boundaries",
            "- Operator memory may identify gaps, but it is not treated as proof or truth.",
            "- Unknown or missing context fails closed.",
            "- Detours are bounded and non-live.",
            "- No Repo B body inspection, Repo B execution, tools, agents, models, browser, OAuth, credentials, Gmail, calendar, Coupa, sends, Mission Control app changes, security pass, or runtime authority were added.",
            "",
            "## Next Recommended Lanes",
        ]
    )
    for lane in payload["next_recommended_lanes"]:
        lines.append(f"- {lane}")
    return "\n".join(lines) + "\n"


def export_operator_awareness_agent_package_spine(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorAwarenessAgentPackageSpineExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_operator_awareness_agent_package_spine(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_awareness_agent_package_spine(payload), encoding="utf-8")
    return OperatorAwarenessAgentPackageSpineExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        awareness_gap_item_count=len(payload["awareness_gap_items"]),
        package_preview_only=payload["package_preview_only"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export operator awareness and agent package spine read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_awareness_agent_package_spine(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


__all__ = [
    "AWARENESS_STATES",
    "CONFIDENCE_POSTURES",
    "DETOUR_WORKSPACE_TYPES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_operator_awareness_agent_package_spine",
    "export_operator_awareness_agent_package_spine",
    "format_operator_awareness_agent_package_spine",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
