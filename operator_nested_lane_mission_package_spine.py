"""Operator nested lane and mission package spine contract v0.

This read-model captures the Mission Control helm doctrine for nested lanes,
mission packages, actor/agent separation, confidence repair, and future-gated
workspace launch posture. It extends the existing Operator Awareness + Agent
Package Spine contract by adding lane topology and package-builder grammar.

It is deterministic metadata only. It does not activate agents, call models,
enable plugins/tools, inspect Repo B, open browsers, access OAuth/credentials,
Gmail/calendar/Coupa/Telegram, create live chat, mutate the Mission Control
app, send/submit/approve anything, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger, record_receipt
from operator_awareness_agent_package_spine import (
    CONFIDENCE_POSTURES,
    DETOUR_WORKSPACE_TYPES,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "operator_nested_lane_mission_package_spine_v0"
JSON_EXPORT_NAME = "operator_nested_lane_mission_package_spine.json"
OPERATOR_EXPORT_NAME = "operator_nested_lane_mission_package_spine_OPERATOR.md"

HELM_MODES = (
    "DEVELOPER_MODE_BUILD_MODE",
    "QUIET_OPERATIONAL_HELM",
)

LANE_KINDS = (
    "TOP_LEVEL_SYSTEM_DISCOVERY",
    "AGENT_CHARACTER_SUBLANE",
    "DOMAIN_WORKFLOW_SUBLANE",
    "DESIGN_MEMORY_SUBLANE",
    "FUTURE_DOMAIN_LANE",
)

LANE_ATTENTION_FLAGS = (
    "QUIET",
    "NEEDS_OPERATOR_ATTENTION",
    "NEEDS_CONTEXT",
    "NEEDS_PROOF",
    "NEEDS_OPERATOR_MEMORY_COMPARISON",
    "NEEDS_DISCOVERY_CLASSIFICATION",
    "BLOCKED_NOT_AUTHORIZED",
)

CHECK_ENGINE_STATES = (
    "NO_CHECK_ENGINE",
    "SYSTEM_MALFUNCTION",
    "STALE_OR_UNTRUSTED_SELF_REPORT",
    "UNSAFE_OR_AUTHORITY_CONFLICT",
    "BLOCKED_AUTHORITY_ATTEMPTED",
    "INTERNAL_INCONSISTENCY",
    "PROOF_OR_TRUST_FAILURE",
)

WORKSPACE_TARGET_TYPES = (
    "NO_WORKSPACE_NOW",
    "MARKDOWN_CONTEXT_UPDATE",
    "HTML_WORKSPACE_FUTURE_GATED",
    "STRUCTURED_FORM_FUTURE_GATED",
    "CLASSIFICATION_REVIEW",
    "CHAT_PREVIEW_FUTURE_GATED",
    "DOMAIN_WORKSPACE_FUTURE_GATED",
)

MISSION_PACKAGE_FIELDS = (
    "actor_model_candidate",
    "agent_character",
    "mission",
    "stakes_why_it_matters",
    "context_included",
    "context_excluded",
    "plugins_capabilities_allowed",
    "plugins_capabilities_forbidden",
    "security_clearance",
    "steps",
    "stop_conditions",
    "proof_receipt_requirements",
    "confidence_inputs",
    "detour_path_if_confidence_insufficient",
    "chat_workspace_target",
    "authority_boundary",
)

CANDIDATE_MODEL_ACTOR_LABELS = (
    "Gemini 5.4 / 5.5",
    "Gemini 3.1 Pro",
    "Gemini Flash",
    "Gemini Flash Lite",
)

DEFAULT_SUBLANE_EXPOSURE_FIELDS = (
    "known",
    "partly_known",
    "known_unknown",
    "not_discovered",
    "needs_winship_memory_comparison",
    "blocked_not_authorized",
    "safe_next_detour",
    "confidence_level",
    "package_available",
    "what_would_make_lane_quiet",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "contract_only": True,
    "metadata_only": True,
    "package_preview_only": True,
    "lane_topology_only": True,
    "button_or_launch_metadata_only": True,
    "sqlite_receipt_metadata_only": True,
    "sqlite_schema_changed": False,
    "model_calls_made": False,
    "lm_called": False,
    "candidate_models_are_live_integrations": False,
    "tools_enabled": False,
    "plugins_wired": False,
    "tool_execution_authority_added": False,
    "agents_activated": False,
    "agent_activation_authority_added": False,
    "live_chat_created": False,
    "chat_launch_authority_added": False,
    "browser_accessed": False,
    "browser_automation_added": False,
    "oauth_or_credentials_accessed": False,
    "credential_or_pii_access_added": False,
    "gmail_calendar_coupa_accessed": False,
    "telegram_send_triggered": False,
    "email_send_triggered": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "mission_control_app_changed": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "repo_b_modules_imported": False,
    "private_raw_content_inspected": False,
    "raw_design_archive_ingested": False,
}


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class NestedLaneSpec:
    lane_id: str
    title: str
    parent_lane_id: str | None
    lane_kind: str
    domain: str
    recommended_agent_character: str
    awareness_state: str
    confidence_posture: str
    lane_attention_flag: str
    check_engine_state: str
    package_available: bool
    known: tuple[str, ...]
    partly_known: tuple[str, ...]
    known_unknown: tuple[str, ...]
    not_discovered: tuple[str, ...]
    needs_winship_memory_comparison: tuple[str, ...]
    blocked_not_authorized: tuple[str, ...]
    safe_next_detour: str
    what_would_make_lane_quiet: tuple[str, ...]
    source_refs: tuple[str, ...]
    workspace_target_type: str


@dataclass(frozen=True)
class OperatorNestedLaneMissionPackageSpineExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    nested_lane_count: int
    mission_package_field_count: int
    sqlite_receipt_supported: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "parent five-layer awareness/gap/package/confidence spine",
    ),
    SourceReadModel(
        "operator_awareness_agent_package_spine_operator",
        "generated/read_models/operator_awareness_agent_package_spine_OPERATOR.md",
        "parent operator-readable awareness spine",
    ),
    SourceReadModel(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "metadata-only capability and skill posture",
    ),
    SourceReadModel(
        "agent_work_packets",
        "generated/read_models/agent_work_packets.json",
        "bounded future work-packet substrate",
    ),
    SourceReadModel(
        "operator_actions",
        "generated/read_models/operator_actions.json",
        "operator action posture and receipt boundary",
    ),
    SourceReadModel(
        "intent_router",
        "generated/read_models/intent_router.json",
        "non-executing intent routing metadata",
    ),
    SourceReadModel(
        "work_board",
        "generated/read_models/work_board.json",
        "Mission Control work-board visibility",
    ),
    SourceReadModel(
        "business_ops_ledger",
        "business_ops_ledger.py",
        "existing SQLite ledger receipt pattern",
    ),
)

SOURCE_FILES = (
    "operator_awareness_agent_package_spine.py",
    "capability_skill_registry_metadata_delta.py",
    "agent_work_packet.py",
    "intent_router.py",
    "work_board.py",
    "business_ops_ledger.py",
)

DOCTRINE_SOURCE_LABELS = (
    "operator_prompt: Operator Awareness Nested Lane + Mission Package Spine v0",
    "existing_contract: Operator Awareness + Agent Package Spine Contract v0",
    "repo_a_runtime_law: OPENCLAW_RUNTIME.md",
    "operator_identity_context: USER.md",
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
        "truth_status": "repo_a_source_or_read_model_evidence_not_operator_truth_by_itself",
        "repo_a_only": True,
        "body_exported": False,
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
        "role": "source_contract_or_existing_pattern_reference",
        "body_exported": False,
        "runtime_imported_for_execution": False,
        "executed_or_dispatched": False,
    }


def _package_hash(package_body: dict[str, Any]) -> str:
    digest = hashlib.sha256(stable_json(package_body).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _nested_lane_record(spec: NestedLaneSpec) -> dict[str, Any]:
    if spec.lane_kind not in LANE_KINDS:
        raise ValueError(f"unknown lane kind: {spec.lane_kind}")
    if spec.confidence_posture not in CONFIDENCE_POSTURES:
        raise ValueError(f"unknown confidence posture: {spec.confidence_posture}")
    if spec.lane_attention_flag not in LANE_ATTENTION_FLAGS:
        raise ValueError(f"unknown lane attention flag: {spec.lane_attention_flag}")
    if spec.check_engine_state not in CHECK_ENGINE_STATES:
        raise ValueError(f"unknown check-engine state: {spec.check_engine_state}")
    if spec.workspace_target_type not in WORKSPACE_TARGET_TYPES:
        raise ValueError(f"unknown workspace target type: {spec.workspace_target_type}")

    confidence_visible = spec.confidence_posture != "FULL_TRUST_DISPLAY_QUIET"
    check_engine_active = spec.check_engine_state != "NO_CHECK_ENGINE"
    return {
        "lane_id": spec.lane_id,
        "title": spec.title,
        "parent_lane_id": spec.parent_lane_id,
        "lane_kind": spec.lane_kind,
        "domain": spec.domain,
        "recommended_agent_character": spec.recommended_agent_character,
        "awareness_state": spec.awareness_state,
        "confidence_posture": spec.confidence_posture,
        "confidence_should_be_visible_in_helm": confidence_visible,
        "lane_attention_flag": spec.lane_attention_flag,
        "lane_attention_is_system_malfunction": False,
        "check_engine_state": spec.check_engine_state,
        "check_engine_active": check_engine_active,
        "check_engine_becomes_chief_diagnostic_package": check_engine_active,
        "package_available": spec.package_available,
        "package_preview_available_not_dispatchable": spec.package_available,
        "must_expose": list(DEFAULT_SUBLANE_EXPOSURE_FIELDS),
        "known": list(spec.known),
        "partly_known": list(spec.partly_known),
        "known_unknown": list(spec.known_unknown),
        "not_discovered": list(spec.not_discovered),
        "needs_winship_memory_comparison": list(spec.needs_winship_memory_comparison),
        "operator_memory_is_truth": False,
        "blocked_not_authorized": list(spec.blocked_not_authorized),
        "safe_next_detour": spec.safe_next_detour,
        "what_would_make_lane_quiet": list(spec.what_would_make_lane_quiet),
        "source_refs": list(spec.source_refs),
        "workspace_target_type": spec.workspace_target_type,
        "workspace_launch_future_gated": spec.workspace_target_type != "NO_WORKSPACE_NOW",
        "live_workspace_or_chat_created_now": False,
        "authority_boundary_preserved": True,
    }


def _nested_lane_specs() -> tuple[NestedLaneSpec, ...]:
    return (
        NestedLaneSpec(
            lane_id="system_awareness_discovery",
            title="System Awareness / Discovery",
            parent_lane_id=None,
            lane_kind="TOP_LEVEL_SYSTEM_DISCOVERY",
            domain="system_awareness",
            recommended_agent_character="Chief with Guardian boundary review when blocked authority appears",
            awareness_state="developer_mode_noisy_because_openclaw_is_still_being_assembled",
            confidence_posture="MEDIUM_TRUST",
            lane_attention_flag="NEEDS_DISCOVERY_CLASSIFICATION",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "OpenClaw can show known, partly known, known-unknown, undiscovered, blocked, and confidence-repair posture through the parent awareness spine.",
                "The top lane exists to help Winship compare the system map against memory and identify missing X.",
            ),
            partly_known=(
                "Several sublanes have read-model rails but not all real context, proof, or quiet conditions.",
            ),
            known_unknown=(
                "Some remembered domains and old workflows still need safe classification before becoming tracked facts.",
            ),
            not_discovered=(
                "The next specific Winship-remembered missing item that the current system does not show.",
            ),
            needs_winship_memory_comparison=(
                "Winship may know which expected lane, artifact, or workflow is absent from the visible awareness map.",
            ),
            blocked_not_authorized=(
                "Live model/tool/agent/browser/account/send/runtime work remains blocked.",
            ),
            safe_next_detour="Operator Memory Comparison or Discovery/Classification detour for one named missing item.",
            what_would_make_lane_quiet=(
                "Every sublane is either fully tracked, intentionally parked, or explicitly blocked with proof and no active check-engine state.",
            ),
            source_refs=("operator_awareness_agent_package_spine.json", "work_board.json", "intent_router.json"),
            workspace_target_type="MARKDOWN_CONTEXT_UPDATE",
        ),
        NestedLaneSpec(
            lane_id="chief",
            title="Chief",
            parent_lane_id="system_awareness_discovery",
            lane_kind="AGENT_CHARACTER_SUBLANE",
            domain="coordination_build_queue",
            recommended_agent_character="Chief",
            awareness_state="partly_known_needs_classification_for_system_wide_fix_run_authority",
            confidence_posture="MEDIUM_TRUST",
            lane_attention_flag="NEEDS_DISCOVERY_CLASSIFICATION",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "Chief has status, role segmentation, work-board, intent-router, and bounded work-packet read-model surfaces.",
            ),
            partly_known=(
                "Chief can organize and diagnose work as metadata; full run/fix authority is not granted here.",
            ),
            known_unknown=(
                "Chief test harness meaning and any remembered system-wide fix/run authority need classification.",
            ),
            not_discovered=(
                "A complete inventory of Chief-owned artifacts, missing artifacts, and blocked authorities.",
            ),
            needs_winship_memory_comparison=(
                "Whether a remembered Chief test harness or Chief authority rail exists outside current read-model visibility.",
            ),
            blocked_not_authorized=(
                "Chief runtime imports, service starts, live agents, model calls, shell automation, and Telegram sends.",
            ),
            safe_next_detour="Chief Test Harness Capability Classification",
            what_would_make_lane_quiet=(
                "Chief ownership, non-ownership, harness status, package clearance, and blocked authorities are classified.",
            ),
            source_refs=("chief_status_rail.json", "chief_role_capability_segmentation_map.json", "agent_work_packets.json", "work_board.json"),
            workspace_target_type="STRUCTURED_FORM_FUTURE_GATED",
        ),
        NestedLaneSpec(
            lane_id="cassandra",
            title="Cassandra",
            parent_lane_id="system_awareness_discovery",
            lane_kind="AGENT_CHARACTER_SUBLANE",
            domain="communications_finance",
            recommended_agent_character="Cassandra with Guardian boundary review",
            awareness_state="partly_known_review_packet_safe_live_accounts_blocked",
            confidence_posture="MEDIUM_TRUST",
            lane_attention_flag="NEEDS_PROOF",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "Cassandra review/draft packet rails can be shown safely as visibility.",
                "Capital Hilton and email/calendar detangle surfaces preserve blocked live account authority.",
            ),
            partly_known=(
                "Draft identity, protected proof metadata, and calendar context are only partly represented.",
            ),
            known_unknown=(
                "The system does not know live Gmail/calendar/Coupa facts from this contract.",
            ),
            not_discovered=(
                "Safe proof metadata and named draft identity references for specific workflows.",
            ),
            needs_winship_memory_comparison=(
                "Which calendar source or draft identity matters for a named Cassandra workflow.",
            ),
            blocked_not_authorized=(
                "Gmail, calendar, Telegram, OAuth, Coupa, send, submit, account reads, and raw private bodies.",
            ),
            safe_next_detour="Cassandra Draft Identity Reference Rail or Capital Hilton Protected Proof Metadata Population",
            what_would_make_lane_quiet=(
                "Each Cassandra workflow has either safe proof/read-model metadata, an explicit memory comparison need, or an intentional blocker.",
            ),
            source_refs=("cassandra_email_calendar_delta_detangle.json", "capital_hilton_external_artifact_proof_capture.json", "guardian_protected_access_gate_spec.json"),
            workspace_target_type="STRUCTURED_FORM_FUTURE_GATED",
        ),
        NestedLaneSpec(
            lane_id="guardian",
            title="Guardian",
            parent_lane_id="system_awareness_discovery",
            lane_kind="AGENT_CHARACTER_SUBLANE",
            domain="safety_security",
            recommended_agent_character="Guardian",
            awareness_state="known_for_boundaries_but_no_live_clearance_granted",
            confidence_posture="HIGH_TRUST",
            lane_attention_flag="QUIET",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "Guardian gates and protected-access specs define blocked authorities and future approval boundaries.",
            ),
            partly_known=(
                "Future approval workflows may need exact receipt requirements per lane.",
            ),
            known_unknown=(
                "No generic approval, send, or protected access authority exists in this lane.",
            ),
            not_discovered=(),
            needs_winship_memory_comparison=(),
            blocked_not_authorized=(
                "Protected access, approval bypass, credential access, send/submit authority, and live security pass.",
            ),
            safe_next_detour="Guardian package review only when a future lane asks for clearance metadata.",
            what_would_make_lane_quiet=(
                "Guardian remains quiet unless a lane tries to cross an authority boundary or needs clearance classification.",
            ),
            source_refs=("guardian_protected_access_gate_spec.json", "protected_access_broker_concept.json"),
            workspace_target_type="NO_WORKSPACE_NOW",
        ),
        NestedLaneSpec(
            lane_id="niles",
            title="Niles",
            parent_lane_id="system_awareness_discovery",
            lane_kind="AGENT_CHARACTER_SUBLANE",
            domain="music_art",
            recommended_agent_character="Niles",
            awareness_state="partly_known_needs_real_album_metadata",
            confidence_posture="MEDIUM_TRUST",
            lane_attention_flag="NEEDS_CONTEXT",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "Niles/Struna review and metadata-intake rails are visible.",
            ),
            partly_known=(
                "The rail can hold album/project metadata, but real current metadata is not fully verified.",
            ),
            known_unknown=(
                "Canonical track, release, personnel, and artifact status are not fully proven here.",
            ),
            not_discovered=(
                "The current real album metadata set that should become the canonical read-model candidate.",
            ),
            needs_winship_memory_comparison=(
                "Which music facts or files Winship remembers should be treated as candidate metadata sources.",
            ),
            blocked_not_authorized=(
                "Audio/file automation, producer runtime, public release execution, and raw private creative scans.",
            ),
            safe_next_detour="Niles Real Album Metadata Intake",
            what_would_make_lane_quiet=(
                "Album metadata is captured as safe metadata, marked stale/private, or explicitly blocked.",
            ),
            source_refs=("niles_album_review_packet.json", "niles_album_metadata_intake_packet.json", "struna_obscura_project_capsule.json"),
            workspace_target_type="STRUCTURED_FORM_FUTURE_GATED",
        ),
        NestedLaneSpec(
            lane_id="hermes",
            title="Hermes",
            parent_lane_id="system_awareness_discovery",
            lane_kind="AGENT_CHARACTER_SUBLANE",
            domain="big_picture_advisory",
            recommended_agent_character="Hermes",
            awareness_state="operator_memory_comparison_needed",
            confidence_posture="LOW_TRUST",
            lane_attention_flag="NEEDS_OPERATOR_MEMORY_COMPARISON",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=False,
            known=(
                "Hermes exists as a remembered advisory role or partial metadata reference.",
            ),
            partly_known=(
                "The current readiness/status rail is not proven.",
            ),
            known_unknown=(
                "No completed Hermes status or responsibility rail is established by this contract.",
            ),
            not_discovered=(
                "Hermes source set, current responsibility boundary, and proof of readiness.",
            ),
            needs_winship_memory_comparison=(
                "Whether Hermes had a real advisory status, source set, or synthesis workflow that should be raised up.",
            ),
            blocked_not_authorized=(
                "Live advisory agent activation, model calls, external research, and tool execution.",
            ),
            safe_next_detour="Hermes Status Memory/Proof Review",
            what_would_make_lane_quiet=(
                "Hermes is classified as tracked, parked, obsolete, blocked, or backed by source read-model proof.",
            ),
            source_refs=("operator_awareness_agent_package_spine.json", "capability_skill_registry_metadata_delta.json"),
            workspace_target_type="MARKDOWN_CONTEXT_UPDATE",
        ),
        NestedLaneSpec(
            lane_id="repo_b_leftovers",
            title="Repo B leftovers",
            parent_lane_id="system_awareness_discovery",
            lane_kind="DOMAIN_WORKFLOW_SUBLANE",
            domain="cross_repo_awareness",
            recommended_agent_character="Chief with Guardian boundary review",
            awareness_state="known_unknown_reference_only",
            confidence_posture="UNKNOWN_FAIL_CLOSED",
            lane_attention_flag="NEEDS_DISCOVERY_CLASSIFICATION",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=False,
            known=(
                "Repo A read-models can represent Repo B leftovers as already tracked, partial, blocked, or unclassified references.",
            ),
            partly_known=(
                "Some leftovers may need tagging or blocking.",
            ),
            known_unknown=(
                "Unclassified leftovers are not current Repo A capabilities.",
            ),
            not_discovered=(
                "The next named leftover Winship remembers but Mission Control does not show.",
            ),
            needs_winship_memory_comparison=(
                "Which named older file, concept, or workflow should be classified.",
            ),
            blocked_not_authorized=(
                "Repo B filesystem inspection, Repo B code execution/import, migration, and old loop activation.",
            ),
            safe_next_detour="Repo B Leftover Classification Packet",
            what_would_make_lane_quiet=(
                "Each named leftover is tagged tracked, partial, obsolete, unsafe, blocked, or not relevant.",
            ),
            source_refs=("cross_repo_awareness_matrix.json", "repo_b_remaining_capability_delta_map.json"),
            workspace_target_type="CLASSIFICATION_REVIEW",
        ),
        NestedLaneSpec(
            lane_id="mission_control_design_memory",
            title="Mission Control design memory",
            parent_lane_id="system_awareness_discovery",
            lane_kind="DESIGN_MEMORY_SUBLANE",
            domain="mission_control_design",
            recommended_agent_character="Chief",
            awareness_state="operator_doctrine_captured_no_broad_archive_ingest",
            confidence_posture="HIGH_TRUST",
            lane_attention_flag="NEEDS_CONTEXT",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "The helm/world/domain, noisy developer mode, quiet helm, nested lane, and mission package doctrine are captured as bounded metadata in this contract.",
            ),
            partly_known=(
                "Old design archives may contain additional useful memory, but broad ingestion is explicitly out of scope here.",
            ),
            known_unknown=(
                "Which old .md/chat/design artifacts should be classified later is not known here.",
            ),
            not_discovered=(
                "A future narrow list of design-memory artifacts safe to classify.",
            ),
            needs_winship_memory_comparison=(
                "Which Mission Control design memories Winship expects the system to show next.",
            ),
            blocked_not_authorized=(
                "Broad raw chat/design archive ingestion and Mission Control app mutation.",
            ),
            safe_next_detour="Mission Control Design Memory Classification Packet",
            what_would_make_lane_quiet=(
                "Design doctrine is either represented by current contracts or queued as named classification work.",
            ),
            source_refs=("operator_nested_lane_mission_package_spine.json", "operator_awareness_agent_package_spine.json"),
            workspace_target_type="MARKDOWN_CONTEXT_UPDATE",
        ),
        NestedLaneSpec(
            lane_id="capital_hilton",
            title="Capital Hilton",
            parent_lane_id="system_awareness_discovery",
            lane_kind="DOMAIN_WORKFLOW_SUBLANE",
            domain="finance_operations",
            recommended_agent_character="Cassandra with Guardian boundary review",
            awareness_state="partly_known_needs_protected_proof_metadata",
            confidence_posture="MEDIUM_TRUST",
            lane_attention_flag="NEEDS_PROOF",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "Capital Hilton review/proof/send-gate rails exist.",
            ),
            partly_known=(
                "The proof shape exists but actual protected Coupa/Excel metadata is missing.",
            ),
            known_unknown=(
                "Real protected Coupa/Excel proof references are not present in this contract.",
            ),
            not_discovered=(
                "Validated protected proof metadata for the current workflow.",
            ),
            needs_winship_memory_comparison=(
                "Whether the proof already exists outside the current read-models.",
            ),
            blocked_not_authorized=(
                "Coupa access, Excel/PDF raw bodies, payment mutation, email send, and browser/account access.",
            ),
            safe_next_detour="Capital Hilton Protected Proof Metadata Population",
            what_would_make_lane_quiet=(
                "Protected proof metadata exists, is explicitly missing with blocker, or the lane is parked.",
            ),
            source_refs=("capital_hilton_actionable_review_packet.json", "capital_hilton_external_artifact_proof_capture.json"),
            workspace_target_type="STRUCTURED_FORM_FUTURE_GATED",
        ),
        NestedLaneSpec(
            lane_id="struna",
            title="Struna",
            parent_lane_id="system_awareness_discovery",
            lane_kind="DOMAIN_WORKFLOW_SUBLANE",
            domain="music_art",
            recommended_agent_character="Niles",
            awareness_state="partly_known_project_capsule_visible",
            confidence_posture="MEDIUM_TRUST",
            lane_attention_flag="NEEDS_CONTEXT",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "Struna is visible as a project/music surface through Niles read-model references.",
            ),
            partly_known=(
                "Project capsule and album metadata need real current source classification.",
            ),
            known_unknown=(
                "Canonical project/artifact status is not fully proven.",
            ),
            not_discovered=(
                "The current Struna artifact/project metadata set.",
            ),
            needs_winship_memory_comparison=(
                "Which Struna facts Winship remembers as canonical candidates.",
            ),
            blocked_not_authorized=(
                "Raw private creative scans, audio automation, publishing, and file movement.",
            ),
            safe_next_detour="Struna Project Metadata Classification",
            what_would_make_lane_quiet=(
                "Project metadata is captured, parked, or blocked with proof/context boundaries.",
            ),
            source_refs=("struna_obscura_project_capsule.json", "niles_album_review_packet.json"),
            workspace_target_type="STRUCTURED_FORM_FUTURE_GATED",
        ),
        NestedLaneSpec(
            lane_id="cue_parser_brain_dump_parser",
            title="Cue parser / brain dump parser",
            parent_lane_id="system_awareness_discovery",
            lane_kind="DOMAIN_WORKFLOW_SUBLANE",
            domain="operator_intake",
            recommended_agent_character="Chief",
            awareness_state="discovery_classification_needed",
            confidence_posture="LOW_TRUST",
            lane_attention_flag="NEEDS_DISCOVERY_CLASSIFICATION",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=False,
            known=(
                "Dropped intents and intent router preserve some operator cues as metadata.",
            ),
            partly_known=(
                "A future parser would likely feed intent routing and work posture.",
            ),
            known_unknown=(
                "Allowed cue sources, storage rules, and receipt shape are not yet defined.",
            ),
            not_discovered=(
                "Governed input model for cue parsing without raw private scans or model-driven truth promotion.",
            ),
            needs_winship_memory_comparison=(
                "Which brain-dump/cue workflow should be revived, parked, or discarded.",
            ),
            blocked_not_authorized=(
                "Broad Markdown ingestion, raw private note scans, LLM/Ollama parsing, file moves, and automatic truth promotion.",
            ),
            safe_next_detour="Cue Parser Intake Classification",
            what_would_make_lane_quiet=(
                "Cue parser is specified as a safe metadata intake or explicitly parked/blocked.",
            ),
            source_refs=("dropped_intents.json", "intent_router.json"),
            workspace_target_type="CLASSIFICATION_REVIEW",
        ),
        NestedLaneSpec(
            lane_id="tool_plugin_registry",
            title="Tool/plugin registry",
            parent_lane_id="system_awareness_discovery",
            lane_kind="DOMAIN_WORKFLOW_SUBLANE",
            domain="capability_registry",
            recommended_agent_character="Chief with Guardian boundary review",
            awareness_state="metadata_only_registry_visible",
            confidence_posture="HIGH_TRUST",
            lane_attention_flag="NEEDS_CONTEXT",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "Capability/skill registry metadata can label available, blocked, gated, and unknown capability surfaces.",
            ),
            partly_known=(
                "Future plugin/capability launch wiring is not represented as authority.",
            ),
            known_unknown=(
                "Unknown or unavailable capabilities fail closed.",
            ),
            not_discovered=(
                "Which future plugin/capability lanes Winship wants raised into explicit package templates.",
            ),
            needs_winship_memory_comparison=(
                "Which remembered capability should be classified next.",
            ),
            blocked_not_authorized=(
                "Plugin wiring, tool execution, OAuth, credentials, browser automation, and live account access.",
            ),
            safe_next_detour="Tool/Plugin Registry Capability Classification",
            what_would_make_lane_quiet=(
                "Each capability is visible as metadata, intentionally blocked, or queued for a specific gated lane.",
            ),
            source_refs=("capability_skill_registry_metadata_delta.json",),
            workspace_target_type="MARKDOWN_CONTEXT_UPDATE",
        ),
        NestedLaneSpec(
            lane_id="model_router",
            title="Model router",
            parent_lane_id="system_awareness_discovery",
            lane_kind="DOMAIN_WORKFLOW_SUBLANE",
            domain="actor_routing",
            recommended_agent_character="Chief with Guardian boundary review",
            awareness_state="candidate_labels_only_no_integration",
            confidence_posture="LOW_TRUST",
            lane_attention_flag="NEEDS_DISCOVERY_CLASSIFICATION",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=True,
            known=(
                "The router doctrine says the system chooses actor, agent character, context, capabilities, clearance, steps, stops, receipts, and workspace before launch.",
                "Winship mentioned candidate model actor labels for future evaluation.",
            ),
            partly_known=(
                "Actor labels are remembered candidates only and not live integrations.",
            ),
            known_unknown=(
                "Actual availability, endpoint, cost, fit, and risk posture are unknown until a future model-router lane.",
            ),
            not_discovered=(
                "A governed model actor evaluation/read-model contract.",
            ),
            needs_winship_memory_comparison=(
                "Which actor labels should remain candidate labels and which should be removed or renamed.",
            ),
            blocked_not_authorized=(
                "API wiring, API keys, endpoint references, model calls, auto-routing to live actors, and cost-bearing execution.",
            ),
            safe_next_detour="Model Actor Candidate Classification",
            what_would_make_lane_quiet=(
                "Every actor candidate is metadata-only classified as available, unavailable, unknown-fail-closed, or removed.",
            ),
            source_refs=("operator_nested_lane_mission_package_spine.json",),
            workspace_target_type="CLASSIFICATION_REVIEW",
        ),
        NestedLaneSpec(
            lane_id="future_domain_workflow_lanes",
            title="Future domain/workflow lanes",
            parent_lane_id="system_awareness_discovery",
            lane_kind="FUTURE_DOMAIN_LANE",
            domain="future_worlds",
            recommended_agent_character="Chief routes to future domain character when classified",
            awareness_state="expected_not_discovered_yet",
            confidence_posture="UNKNOWN_FAIL_CLOSED",
            lane_attention_flag="NEEDS_DISCOVERY_CLASSIFICATION",
            check_engine_state="NO_CHECK_ENGINE",
            package_available=False,
            known=(
                "Mission Control may later enter worlds/domains such as operations, research, business development, or gardening.",
            ),
            partly_known=(
                "Future domains need lane grammar before they become active surfaces.",
            ),
            known_unknown=(
                "No future domain gets authority merely because it is named.",
            ),
            not_discovered=(
                "The actual future domain lane inventory and owning agent characters.",
            ),
            needs_winship_memory_comparison=(
                "Which future domains Winship wants raised first.",
            ),
            blocked_not_authorized=(
                "Live workspace launch, tool/plugin wiring, model calls, external account access, and automation.",
            ),
            safe_next_detour="Future Domain Lane Classification",
            what_would_make_lane_quiet=(
                "Future domains are either absent by design, classified as desired lanes, or explicitly parked.",
            ),
            source_refs=("operator_nested_lane_mission_package_spine.json",),
            workspace_target_type="MARKDOWN_CONTEXT_UPDATE",
        ),
    )


def _domain_world_catalog() -> dict[str, Any]:
    return {
        "helm_metaphor": "Mission Control helm routes, prepares, stages upgrades, and packages work before the operator enters a world/domain workspace.",
        "operator_visual_inspiration": "Doom Eternal space station/base metaphor, stored only as bounded operator-provided design doctrine.",
        "operator_at_helm_when_not_inside_world": True,
        "domain_worlds_current_or_expected": [
            "music/art",
            "finance",
            "operations",
            "security",
            "build",
            "research",
            "communications",
            "business development",
            "gardening",
        ],
        "world_entry_posture": {
            "teleport_metaphor": "operator enters a bounded domain/workspace after helm orientation",
            "actual_live_workspace_launch_now": False,
            "future_gated": True,
        },
    }


def _helm_mode_contract() -> dict[str, Any]:
    return {
        "current_mode": "DEVELOPER_MODE_BUILD_MODE",
        "available_modes": list(HELM_MODES),
        "developer_mode_build_mode": {
            "helm_is_noisy": True,
            "why_noisy": "OpenClaw is still being assembled and must expose known, partly known, known-unknown, undiscovered, blocked, and memory-comparison needs.",
            "operator_workflow": "Winship compares the visible awareness map against memory and names missing X for safe classification.",
        },
        "quiet_operational_helm": {
            "helm_is_noisy": False,
            "condition": "All lanes are fully tracked, parked on purpose, or blocked with proof, and no check-engine state is active.",
            "confidence_display_policy": "When posture is FULL_TRUST_DISPLAY_QUIET, confidence affordances mostly disappear.",
        },
        "quiet_helm_does_not_mean_everything_runs": "Quiet means no attention is needed; it does not grant execution, account, send, approval, or runtime authority.",
    }


def _check_engine_contract() -> dict[str, Any]:
    return {
        "lane_attention_flag": {
            "meaning": "A domain/workflow needs operator attention, more classification, more context, proof, or build-out.",
            "is_system_malfunction": False,
            "examples": [
                "Niles needs real album metadata",
                "Capital Hilton needs protected proof metadata",
                "Repo B leftovers need tagging or blocking",
            ],
        },
        "check_engine_state": {
            "meaning": "The OpenClaw system itself is malfunctioning, stale, unsafe, blocked, internally inconsistent, or failing proof/trust.",
            "becomes": "Chief diagnostic/package problem",
            "examples": [
                "stale or untrusted sync health",
                "unsafe authority conflict",
                "internal read-model inconsistency",
                "proof/trust failure",
            ],
        },
        "states": list(CHECK_ENGINE_STATES),
        "mission_control_should_not_conflate_attention_with_malfunction": True,
    }


def _actor_agent_doctrine() -> dict[str, Any]:
    return {
        "actor_model_definition": "The language model is the actor.",
        "agent_character_definition": "The agent is the character/persona the actor plays, such as Chief, Cassandra, Guardian, Niles, or Hermes.",
        "package_definition": "The package is the script, role sheet, context, tools/capabilities metadata, clearance, steps, stop conditions, boundaries, and proof/receipt requirements.",
        "wow_comes_from_package_not_improvisation": True,
        "candidate_model_actor_labels": [
            {
                "label": label,
                "status": "candidate_label_only",
                "live_integration_available": False,
                "api_key_or_endpoint_reference": None,
                "model_call_allowed": False,
                "unavailable_or_unknown_fails_closed": True,
            }
            for label in CANDIDATE_MODEL_ACTOR_LABELS
        ],
        "agent_character_roles": [
            {"agent_character": "Chief", "domain_fit": "coordination, work queue, diagnostics, build posture"},
            {"agent_character": "Cassandra", "domain_fit": "communications, finance review packets, draft/proof visibility"},
            {"agent_character": "Guardian", "domain_fit": "safety, security, authority boundaries, clearance review"},
            {"agent_character": "Niles", "domain_fit": "music/art metadata and creative project context"},
            {"agent_character": "Hermes", "domain_fit": "big-picture advisory once status is classified"},
            {"agent_character": "Report Bridge", "domain_fit": "client/reporting package visibility"},
        ],
    }


def _deterministic_router_requirements() -> dict[str, Any]:
    return {
        "router_package_builder_should_be_as_deterministic_as_possible": True,
        "model_must_not_decide_own_authority_context_plugins_clearance_or_lane": True,
        "prelaunch_decisions": [
            "Pick the right model actor as metadata.",
            "Attach the right agent character.",
            "Attach only allowed context.",
            "Attach allowed plugins/capabilities as metadata.",
            "Attach security clearance.",
            "Attach steps and stop conditions.",
            "Attach proof/receipt requirements.",
            "Open or recommend the right chat/workspace only when a future lane grants that authority.",
        ],
        "unknown_actor_or_missing_context": {
            "confidence_posture": "UNKNOWN_FAIL_CLOSED",
            "safe_to_launch": False,
        },
    }


def _mission_package_template() -> dict[str, Any]:
    package_body = {
        "package_contract_id": SCHEMA_VERSION,
        "actor_model_candidate": "metadata_only_candidate_label_or_UNKNOWN_FAIL_CLOSED",
        "agent_character": "Chief/Cassandra/Guardian/Niles/Hermes/Report Bridge/etc.",
        "mission": "Safely classify or raise confidence for one named awareness gap without execution.",
        "stakes_why_it_matters": "Mission Control should show what is missing, what would be sent, what is blocked, and what would make the lane quiet.",
        "context_included": [
            "generated Repo A read-model metadata",
            "source read-model references",
            "operator memory comparison labels",
            "blocked authority metadata",
        ],
        "context_excluded": [
            "raw private content",
            "Repo B filesystem/body content",
            "credentials/OAuth tokens",
            "Gmail/calendar/Coupa/Telegram live account data",
            "unclassified old .md/chat/design archive bodies",
        ],
        "plugins_capabilities_allowed": [
            "metadata-only capability labels from read-models",
            "future capture or review affordance labels",
        ],
        "plugins_capabilities_forbidden": [
            "plugin wiring",
            "tool execution",
            "browser/OAuth/account access",
            "send/submit/approval execution",
        ],
        "security_clearance": "metadata_review_only_no_runtime_authority",
        "steps": [
            "Show the current awareness lane.",
            "Name what is known, partial, known-unknown, undiscovered, memory-comparison-needed, and blocked.",
            "Recommend the agent character and actor candidate metadata.",
            "Show allowed/excluded context and blocked actions.",
            "List missing confidence inputs.",
            "Recommend one bounded detour or fail closed.",
            "Require receipt before any future state mutation.",
        ],
        "stop_conditions": [
            "Missing context would require raw private data.",
            "Any step would inspect Repo B, call a model, enable a tool, access an account, send, submit, approve, or execute.",
            "Actor/model availability is unknown and the package needs live execution.",
        ],
        "proof_receipt_requirements": [
            "Future state mutation requires a metadata-only receipt.",
            "Operator memory comparison must be labeled memory-not-truth until proof/read-model evidence exists.",
            "Protected proof capture must store metadata/reference only.",
        ],
        "confidence_inputs": [
            "source read-model presence",
            "classified awareness state",
            "blocked authority list",
            "operator memory comparison status",
            "proof or context references",
        ],
        "detour_path_if_confidence_insufficient": "bounded non-live detour workspace recommendation",
        "chat_workspace_target": "future_gated_chat_or_workspace_preview_only",
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
    }
    return {
        "package_template_fields": list(MISSION_PACKAGE_FIELDS),
        "package_body_placeholder": package_body,
        "package_hash_or_deterministic_placeholder": _package_hash(package_body),
        "package_preview_only": True,
        "model_call_allowed": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }


def _confidence_detour_contract(lane_records: list[dict[str, Any]]) -> dict[str, Any]:
    attention_lanes = [
        lane for lane in lane_records if lane["lane_attention_flag"] != "QUIET"
    ]
    return {
        "confidence_postures": list(CONFIDENCE_POSTURES),
        "detour_workspace_types_reused_from_awareness_spine": list(DETOUR_WORKSPACE_TYPES),
        "below_deterministic_confidence": {
            "show_why_missing": True,
            "list_missing_context_or_proof": True,
            "offer_bounded_detour": True,
            "preserve_blocked_authorities": True,
            "do_not_pretend_missing_context_exists": True,
        },
        "full_deterministic_trust": {
            "posture": "FULL_TRUST_DISPLAY_QUIET",
            "confidence_ui_should_mostly_disappear": True,
            "lane_should_not_keep_demanding_attention": True,
        },
        "safe_detour_examples": [
            {"missing": "Missing Hermes confidence", "detour": "Hermes Status Memory/Proof Review", "workspace_type": "OPERATOR_MEMORY_COMPARISON"},
            {"missing": "Missing calendar proof", "detour": "Calendar Context Discovery / Memory Comparison", "workspace_type": "OPERATOR_MEMORY_COMPARISON"},
            {"missing": "Missing Coupa proof", "detour": "Capital Hilton Protected Proof Metadata Population", "workspace_type": "PROOF_CAPTURE"},
            {"missing": "Unknown Repo B leftover", "detour": "Repo B Leftover Classification Packet", "workspace_type": "CLASSIFICATION_REVIEW"},
            {"missing": "Agentic loop unclear", "detour": "Agentic Loop Workflow Classification", "workspace_type": "DISCOVERY_OR_CLASSIFICATION"},
            {"missing": "Chief test harness unclear", "detour": "Chief Test Harness Capability Classification", "workspace_type": "CLASSIFICATION_REVIEW"},
            {"missing": "Brain-dump/cue parser unclear", "detour": "Cue Parser Intake Classification", "workspace_type": "DISCOVERY_OR_CLASSIFICATION"},
        ],
        "lane_confidence_repair": [
            {
                "lane_id": lane["lane_id"],
                "confidence_posture": lane["confidence_posture"],
                "why_not_quiet": lane["known_unknown"] + lane["not_discovered"] + lane["needs_winship_memory_comparison"],
                "safe_next_detour": lane["safe_next_detour"],
                "workspace_target_type": lane["workspace_target_type"],
                "non_live": True,
            }
            for lane in attention_lanes
        ],
    }


def _chat_workspace_launch_posture() -> dict[str, Any]:
    return {
        "future_gated": True,
        "live_chat_created_now": False,
        "workspace_opened_now": False,
        "launch_authority_added": False,
        "allowed_now": [
            "define metadata/read-model/package-preview structures",
            "generate operator Markdown",
            "describe a future HTML or Markdown context/update artifact",
        ],
        "must_not_do": [
            "create a live chat",
            "wire plugins",
            "call models",
            "start tools/browser/OAuth/accounts",
            "send/submit/approve/execute",
            "mutate Mission Control app files",
        ],
        "workspace_choice_policy": {
            "markdown_when_enough": True,
            "html_only_when_structured_controls_are_needed": True,
            "structured_form_when_exact_fields_must_be_captured": True,
        },
    }


def _operator_doctrine_metadata() -> dict[str, Any]:
    summary = {
        "doctrine_id": SCHEMA_VERSION,
        "doctrine_source_labels": list(DOCTRINE_SOURCE_LABELS),
        "raw_operator_prompt_stored": False,
        "broad_chat_or_design_archive_ingested": False,
        "summary_only": True,
        "captured_points": [
            "Mission Control helm is noisy in Developer/Build Mode and quiet when lanes no longer need attention.",
            "System Awareness / Discovery is a top-level lane that contains sublanes.",
            "Lane attention is distinct from check-engine malfunction.",
            "Actor/model, agent/character, and mission package are separate deterministic concepts.",
            "Package builder decides authority/context/plugins/clearance before any future launch.",
            "Confidence below deterministic requires missing-input explanation and bounded detour.",
            "Chat/workspace launch is future-gated and non-live in this lane.",
        ],
    }
    return {
        **summary,
        "summary_hash": _package_hash(summary),
    }


def _sqlite_receipt_contract(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    contract_hash = _package_hash(payload or {"schema_version": SCHEMA_VERSION})
    return {
        "supported_by_existing_pattern": True,
        "pattern": "business_ops_ledger.record_receipt",
        "receipt_type": "generated_status",
        "authority_status": "generated_status_only",
        "sqlite_meaning": "receipt_record_only",
        "metadata_only": True,
        "raw_prompt_or_archive_body_stored": False,
        "runtime_activation": False,
        "schema_changed": False,
        "default_db_path": DEFAULT_DB_PATH,
        "contract_hash": contract_hash,
        "receipt_writer_function": "record_operator_nested_lane_mission_package_doctrine_receipt",
    }


def build_operator_nested_lane_mission_package_spine(
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
    lane_records = [_nested_lane_record(spec) for spec in _nested_lane_specs()]
    top_lane = next(lane for lane in lane_records if lane["lane_id"] == "system_awareness_discovery")
    sublanes = [lane for lane in lane_records if lane["parent_lane_id"] == "system_awareness_discovery"]
    mission_package_template = _mission_package_template()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Operator Awareness Nested Lane + Mission Package Spine v0",
        "spine_status": "deterministic_nested_lane_mission_package_contract_only",
        "relationship_to_existing_spine": {
            "extends_existing_operator_awareness_spine": True,
            "does_not_replace_or_duplicate_gap_item_spine": True,
            "parent_contract_id": "operator_awareness_agent_package_spine_v0",
            "parent_read_model": "generated/read_models/operator_awareness_agent_package_spine.json",
            "added_scope": "nested_lane_topology_actor_agent_mission_package_router_and_workspace_posture",
        },
        "helm_mode_contract": _helm_mode_contract(),
        "domain_world_catalog": _domain_world_catalog(),
        "top_level_system_awareness_discovery_lane": top_lane,
        "nested_lanes": lane_records,
        "nested_lane_count": len(lane_records),
        "current_or_expected_sublanes": [lane["lane_id"] for lane in sublanes],
        "sublane_exposure_contract": {
            "each_sublane_should_eventually_expose": list(DEFAULT_SUBLANE_EXPOSURE_FIELDS),
            "operator_memory_comparison_is_not_truth": True,
            "blocked_authority_stays_visible": True,
            "package_available_does_not_mean_dispatchable": True,
        },
        "check_engine_vs_lane_attention_contract": _check_engine_contract(),
        "actor_model_agent_character_doctrine": _actor_agent_doctrine(),
        "deterministic_router_package_builder_requirements": _deterministic_router_requirements(),
        "mission_package_contract": mission_package_template,
        "confidence_detour_contract": _confidence_detour_contract(lane_records),
        "chat_workspace_launch_posture": _chat_workspace_launch_posture(),
        "operator_provided_design_doctrine_metadata": _operator_doctrine_metadata(),
        "sqlite_ledger_receipt_contract": {},
        "machine_proof": {
            "source_read_models": source_records,
            "source_files": source_file_records,
            "parent_awareness_spine_present": bool(sources["operator_awareness_agent_package_spine"]),
            "ledger_pattern_present": _rooted("business_ops_ledger.py", repo_root=repo_root).exists(),
            "generated_outputs": [
                f"generated/read_models/{JSON_EXPORT_NAME}",
                f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            ],
        },
        "what_mission_control_can_show_now": [
            "The System Awareness / Discovery top lane.",
            "Nested sublanes and their known/partial/known-unknown/undiscovered/blocked posture.",
            "Actor/model versus agent/character distinction.",
            "Mission package fields and package-preview-only body.",
            "Confidence and bounded detour recommendations.",
            "Check-engine versus normal lane-attention distinction.",
            "Future-gated chat/workspace target metadata.",
        ],
        "what_remains_future_gated": [
            "live chat/workspace launch",
            "model actor execution",
            "agent activation",
            "plugin/tool wiring",
            "browser/OAuth/account access",
            "Gmail/calendar/Coupa/Telegram access",
            "send/submit/approval/runtime authority",
            "broad old .md/chat/design archive ingestion",
            "Mission Control app code changes",
        ],
        "next_safe_lane": "Mission Control Nested Lane Readback and Awareness Map Surface v0",
        "no_live_authority_statement": "No live model/tool/agent/browser/OAuth/credential/Gmail/calendar/Coupa/Telegram/send/submit/approval/runtime authority is added.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["sqlite_ledger_receipt_contract"] = _sqlite_receipt_contract(payload)
    return payload


def format_operator_nested_lane_mission_package_spine(payload: dict[str, Any]) -> str:
    top = payload["top_level_system_awareness_discovery_lane"]
    actor = payload["actor_model_agent_character_doctrine"]
    package = payload["mission_package_contract"]
    check_engine = payload["check_engine_vs_lane_attention_contract"]
    helm = payload["helm_mode_contract"]
    lines = [
        "# Operator Awareness Nested Lane + Mission Package Spine v0",
        "",
        "Status:",
        "- Deterministic nested-lane and mission-package read-model contract only.",
        "- Extends the existing Operator Awareness + Agent Package Spine; it does not replace the gap-item spine.",
        "- No live chat, agent, actor/model, tool, plugin, browser, OAuth, account, send, submit, approval, Mission Control app, Repo B, or runtime authority is added.",
        "",
        "## Top-Level Lane",
        f"- `{top['lane_id']}`: {top['title']}.",
        "- Job: show what OpenClaw knows, partly knows, knows it does not know, has not discovered, needs Winship memory comparison for, and must classify or block.",
        f"- Current helm mode: `{helm['current_mode']}`; noisy because OpenClaw is still being assembled.",
        f"- Next safe detour: {top['safe_next_detour']}",
        "",
        "## Nested Lanes",
    ]
    for lane in payload["nested_lanes"]:
        if lane["lane_id"] == top["lane_id"]:
            continue
        lines.append(
            f"- `{lane['lane_id']}`: {lane['title']} | attention `{lane['lane_attention_flag']}` | confidence `{lane['confidence_posture']}` | detour `{lane['safe_next_detour']}`"
        )
    lines.extend(
        [
            "",
            "## Sublane Exposure",
            "- Each sublane should expose: " + ", ".join(payload["sublane_exposure_contract"]["each_sublane_should_eventually_expose"]) + ".",
            "- Operator memory comparison may identify a gap, but it is not truth by itself.",
            "- Package available means previewable metadata; it does not mean dispatchable execution.",
            "",
            "## Actor / Agent / Package",
            f"- Actor/model: {actor['actor_model_definition']}",
            f"- Agent/character: {actor['agent_character_definition']}",
            f"- Package: {actor['package_definition']}",
            "- Candidate model labels are metadata only: " + ", ".join(item["label"] for item in actor["candidate_model_actor_labels"]) + ".",
            "",
            "## Mission Package Fields",
            "- " + ", ".join(package["package_template_fields"]) + ".",
            f"- Package hash placeholder: `{package['package_hash_or_deterministic_placeholder']}`.",
            "",
            "## Deterministic vs Future-Gated",
            "- Deterministic now: nested lane grammar, package field contract, confidence/detour posture, source references, and operator Markdown.",
            "- Future-gated: live chat/workspace launch, actor/model execution, agents, plugins/tools, accounts, sends, approvals, and runtime execution.",
            "",
            "## Check-Engine vs Lane Attention",
            f"- Lane attention: {check_engine['lane_attention_flag']['meaning']}",
            f"- Check-engine: {check_engine['check_engine_state']['meaning']}",
            "- Check-engine becomes a Chief diagnostic/package problem.",
            "",
            "## Quiet Helm",
            f"- Quiet condition: {helm['quiet_operational_helm']['condition']}",
            "- A quiet lane is fully understood, intentionally parked, or explicitly blocked, and does not keep demanding operator attention.",
            "",
            "## Mission Control Can Show Now",
        ]
    )
    lines.extend(f"- {item}" for item in payload["what_mission_control_can_show_now"])
    lines.extend(["", "## Future-Gated"])
    lines.extend(f"- {item}" for item in payload["what_remains_future_gated"])
    lines.extend(
        [
            "",
            "## SQLite / Ledger Receipt",
            "- Existing safe pattern: `business_ops_ledger.record_receipt`.",
            "- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.",
            "- Raw prompt/chat/design archive bodies are not stored.",
            "",
            "## Next Safe Lane",
            f"- {payload['next_safe_lane']}",
        ]
    )
    return "\n".join(lines) + "\n"


def export_operator_nested_lane_mission_package_spine(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorNestedLaneMissionPackageSpineExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_operator_nested_lane_mission_package_spine(
        repo_root=root,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_nested_lane_mission_package_spine(payload), encoding="utf-8")
    return OperatorNestedLaneMissionPackageSpineExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        nested_lane_count=payload["nested_lane_count"],
        mission_package_field_count=len(payload["mission_package_contract"]["package_template_fields"]),
        sqlite_receipt_supported=payload["sqlite_ledger_receipt_contract"]["supported_by_existing_pattern"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def _load_existing_receipt_payloads(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(db_path or DEFAULT_DB_PATH)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                """
SELECT e.ts, p.packet_json_safe
FROM events e
JOIN packets p ON p.event_id = e.event_id
WHERE e.event_type = 'generated_status'
ORDER BY e.ts DESC
LIMIT 500
""".strip()
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []

    payloads: list[dict[str, Any]] = []
    for ts, packet_json_safe in rows:
        try:
            packet = json.loads(packet_json_safe or "{}")
        except json.JSONDecodeError:
            continue
        packet["_event_ts"] = ts
        payloads.append(packet)
    return payloads


def _find_existing_doctrine_receipt(
    *,
    contract_hash: str,
    commit_hash: str | None,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    for packet in _load_existing_receipt_payloads(db_path):
        payload_json = packet.get("payload_json")
        if not isinstance(payload_json, dict):
            continue
        if payload_json.get("contract_id") != SCHEMA_VERSION:
            continue
        if payload_json.get("contract_hash") != contract_hash:
            continue
        if commit_hash and packet.get("commit_hash") != commit_hash:
            continue
        return packet
    return None


def record_operator_nested_lane_mission_package_doctrine_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a metadata-only doctrine receipt in the existing ledger.

    The receipt stores bounded labels, contract IDs, hashes, generated read-model
    paths, and no-authority flags. It stores no raw prompt, chat, design archive,
    private content, credentials, or runtime activation.
    """
    root = Path(repo_root)
    payload = build_operator_nested_lane_mission_package_spine(
        repo_root=root,
        generated_at=generated_at,
    )
    contract_hash = _package_hash(payload)
    if ensure:
        existing = _find_existing_doctrine_receipt(
            contract_hash=contract_hash,
            commit_hash=commit_hash,
            db_path=db_path,
        )
        if existing:
            return str(existing.get("receipt_id") or existing.get("packet_id") or "")

    init_business_ops_ledger(str(db_path) if db_path else None)
    receipt_payload = {
        "contract_id": SCHEMA_VERSION,
        "contract_hash": contract_hash,
        "generated_read_model_paths": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
        "doctrine_source_labels": list(DOCTRINE_SOURCE_LABELS),
        "doctrine_summary_hash": payload["operator_provided_design_doctrine_metadata"]["summary_hash"],
        "metadata_only": True,
        "raw_prompt_stored": False,
        "raw_chat_or_design_archive_body_stored": False,
        "runtime_activation": False,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    return record_receipt(
        receipt_type="generated_status",
        payload=receipt_payload,
        commit_hash=commit_hash,
        artifact_type="operator_design_doctrine_contract",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=list(DOCTRINE_SOURCE_LABELS),
        actor="operator_nested_lane_mission_package_spine_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export operator nested lane and mission package spine read-model."
    )
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    parser.add_argument(
        "--record-receipt",
        action="store_true",
        help="Also record a metadata-only generated_status receipt in the existing ledger.",
    )
    parser.add_argument("--db", help="SQLite ledger path. Defaults to the Business Ops ledger.")
    parser.add_argument("--commit-hash", help="Optional commit hash to bind to the metadata receipt.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_nested_lane_mission_package_spine(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_operator_nested_lane_mission_package_doctrine_receipt(
            repo_root=args.repo_root,
            db_path=args.db,
            commit_hash=args.commit_hash,
            ensure=True,
        )

    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        summary = result.__dict__.copy()
        if args.record_receipt:
            summary["sqlite_receipt_id"] = receipt_id
            summary["sqlite_receipt_recorded"] = bool(receipt_id)
        print(stable_json(summary), end="")
    return 0 if result.schema_version == SCHEMA_VERSION and (not args.record_receipt or receipt_id) else 1


__all__ = [
    "CANDIDATE_MODEL_ACTOR_LABELS",
    "CHECK_ENGINE_STATES",
    "HELM_MODES",
    "JSON_EXPORT_NAME",
    "LANE_ATTENTION_FLAGS",
    "MISSION_PACKAGE_FIELDS",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "WORKSPACE_TARGET_TYPES",
    "build_operator_nested_lane_mission_package_spine",
    "export_operator_nested_lane_mission_package_spine",
    "format_operator_nested_lane_mission_package_spine",
    "record_operator_nested_lane_mission_package_doctrine_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
