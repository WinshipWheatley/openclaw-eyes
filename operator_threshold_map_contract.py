"""OpenClaw Threshold Map Contract v0.

This deterministic read-model defines the pre-security threshold for active
helm lanes and the two current steel threads. It is a contract only: no live
queue, package dispatch, model call, agent activation, Repo B execution, app
mutation, sync repair, credential handling, or runtime authority is added.
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

SCHEMA_VERSION = "operator_threshold_map_contract_v0"
JSON_EXPORT_NAME = "operator_threshold_map_contract.json"
OPERATOR_EXPORT_NAME = "operator_threshold_map_contract_OPERATOR.md"

THRESHOLD_STATES = (
    "READY_FOR_SECURITY_AUDIT",
    "NEEDS_PROOF",
    "NEEDS_CONTEXT",
    "NEEDS_DISCOVERY_CLASSIFICATION",
    "PARKED_WITH_PROOF",
    "BLOCKED_NOT_AUTHORIZED",
    "UNKNOWN_FAIL_CLOSED",
    "READY_FOR_POST_SECURITY_ACTION",
    "NEEDS_SOURCE_TRUTH_RECONCILIATION",
)

RESOLUTION_ROUTES = (
    "QUIET_BACKEND_RESOLVED",
    "MOVE_TO_WORLD_ACTION",
    "PARK_WITH_PROOF",
    "HOLDING_CELL",
    "SECURITY_AUDIT_REQUIRED",
    "POST_SECURITY_AUTONOMY_CANDIDATE",
    "REQUEUE_FOR_SYSTEM_BUILD",
)

LANE_KINDS = (
    "helm_lane",
    "world_lane",
    "agent_character_lane",
    "check_light_lane",
    "resource_light_lane",
    "authority_light_lane",
    "confidence_light_lane",
    "future_domain_lane",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "contract_only": True,
    "package_preview_only": True,
    "live_package_dispatch_allowed": False,
    "package_runner_created": False,
    "autonomy_queue_created": False,
    "planner_builder_loop_created": False,
    "planner_builder_loop_executed": False,
    "model_calls_made": False,
    "external_model_apis_called": False,
    "agents_activated": False,
    "agent_launch_authority_added": False,
    "plugins_wired": False,
    "tool_execution_authority_added": False,
    "browser_oauth_or_account_access_enabled": False,
    "credentials_accessed": False,
    "credentials_stored": False,
    "gmail_calendar_coupa_telegram_accessed": False,
    "send_submit_or_approval_authority_added": False,
    "runtime_authority_added": False,
    "mission_control_app_changed": False,
    "repo_b_mutated": False,
    "repo_b_code_executed": False,
    "repo_b_private_bodies_inspected": False,
    "raw_private_content_inspected": False,
    "broad_private_chat_ingested": False,
    "delete_move_cleanup_remount_repair_authority_added": False,
    "hidden_monitoring_added": False,
    "pc_c_drive_artifact_written": False,
    "authority_escalation_added": False,
}

FORBIDDEN_ACTIONS = (
    "call live model APIs",
    "activate agents or launch planner/builder loops",
    "execute Repo B planner-builder systems",
    "mutate Repo B",
    "inspect unauthorized Repo B bodies",
    "mutate Mission Control app code",
    "access or store credentials",
    "open browser, OAuth, account, Gmail, calendar, Coupa, or Telegram flows",
    "send, submit, approve, save, upload, or perform account actions",
    "delete, move, cleanup, remount, repair, or add hidden monitoring",
    "write OpenClaw artifacts to the PC system drive",
    "turn package preview into live dispatch",
    "turn cue/autonomy into an active queue before security audit",
)


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class LaneSpec:
    lane_id: str
    display_name: str
    lane_kind: str
    owner: str
    readiness_state: str
    operator_summary: str
    current_status: str
    why_it_matters: str
    safe_next_move: str
    proof_refs: tuple[str, ...]
    missing_proof: tuple[str, ...]
    known: tuple[str, ...]
    partly_known: tuple[str, ...]
    known_unknown: tuple[str, ...]
    not_discovered: tuple[str, ...]
    operator_memory_needed: tuple[str, ...]
    package_preview_status: str
    detour_path: str
    makes_quiet: tuple[str, ...]
    surface_posture: str
    future_gated_until: str
    blocked_actions: tuple[str, ...]


@dataclass(frozen=True)
class OperatorThresholdMapExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    lane_count: int
    ready_for_security_audit_count: int
    blocked_or_unknown_count: int
    package_preview_only: bool
    runtime_authority_added: bool
    pc_c_drive_artifact_written: bool


SOURCE_READ_MODELS = (
    SourceReadModel(
        "sync_health",
        "generated/read_models/sync_health.json",
        "current PC-side mirror proof and lifecycle status",
    ),
    SourceReadModel(
        "system_health_lights_taxonomy",
        "generated/read_models/system_health_lights_taxonomy.json",
        "helm health-light taxonomy and current light state read-model",
    ),
    SourceReadModel(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "operator awareness layers and agent package preview spine",
    ),
    SourceReadModel(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "nested lane and mission package doctrine",
    ),
    SourceReadModel(
        "steel_thread_lane_template_registry",
        "generated/read_models/steel_thread_lane_template_registry.json",
        "reusable steel-thread lane template registry",
    ),
    SourceReadModel(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "package compiler contract and boundary validation",
    ),
    SourceReadModel(
        "mission_control_design_memory_inventory",
        "generated/read_models/mission_control_design_memory_inventory.json",
        "Mission Control design doctrine and known unknowns",
    ),
    SourceReadModel(
        "operator_question_journey_registry",
        "generated/read_models/operator_question_journey_registry.json",
        "operator question/correction doctrine candidates",
    ),
    SourceReadModel(
        "operator_mission_priority_helm_declutter",
        "generated/read_models/operator_mission_priority_helm_declutter.json",
        "helm declutter and mission priority taxonomy",
    ),
    SourceReadModel(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "workbench/actor host registry",
    ),
    SourceReadModel(
        "capital_hilton_actionable_review_packet",
        "generated/read_models/capital_hilton_actionable_review_packet.json",
        "Capital Hilton review-only packet posture",
    ),
    SourceReadModel(
        "capital_hilton_external_artifact_proof_capture",
        "generated/read_models/capital_hilton_external_artifact_proof_capture.json",
        "Capital Hilton protected/external artifact proof capture posture",
    ),
    SourceReadModel(
        "capital_hilton_operator_proof_input_packet",
        "generated/read_models/capital_hilton_operator_proof_input_packet.json",
        "Capital Hilton operator proof input packet",
    ),
    SourceReadModel(
        "capital_hilton_coupa_execution_path",
        "generated/read_models/capital_hilton_coupa_execution_path.json",
        "Capital Hilton Coupa execution path metadata and boundaries",
    ),
    SourceReadModel(
        "chief_check_engine_diagnostic_package",
        "generated/read_models/chief_check_engine_diagnostic_package.json",
        "Chief check-engine diagnostic package",
    ),
    SourceReadModel(
        "chief_check_engine_environment_posture",
        "generated/read_models/chief_check_engine_environment_posture.json",
        "Chief environment posture and workbench degradation signals",
    ),
    SourceReadModel(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "capability and skill registry metadata",
    ),
    SourceReadModel(
        "cross_repo_awareness_matrix",
        "generated/read_models/cross_repo_awareness_matrix.json",
        "cross-repo awareness matrix and Repo B leftovers posture",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _hash_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_record(source: SourceReadModel, *, repo_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = _rooted(source.path, repo_root=repo_root)
    return {
        "key": source.key,
        "path": source.path,
        "role": source.role,
        "present": path.exists() and bool(payload),
        "schema_version": payload.get("schema_version"),
        "read_model_id": payload.get("read_model_id"),
        "generated_at_omitted_for_stability": True,
        "raw_body_exported": False,
        "operator_memory_used_as_proof": False,
    }


def _source_state_summary(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sync = sources.get("sync_health", {})
    lights = sources.get("system_health_lights_taxonomy", {})
    cap = sources.get("capital_hilton_actionable_review_packet", {})
    return {
        "source_count": len(SOURCE_READ_MODELS),
        "sources_present": {source.key: bool(sources.get(source.key)) for source in SOURCE_READ_MODELS},
        "sync_health": {
            "present": bool(sync),
            "canonical_expected": sync.get("canonical_expected"),
            "observed": sync.get("observed"),
            "missing_expected": sync.get("missing_expected"),
            "hash_mismatch": sync.get("hash_mismatch"),
            "sync_lifecycle_state": sync.get("sync_lifecycle_state"),
            "trust_status": sync.get("trust_status"),
        },
        "system_health_lights": {
            "present": bool(lights),
            "current_light_states": lights.get("current_light_states", {}),
            "check_transmission_summary": lights.get("check_transmission_summary", {}),
        },
        "capital_hilton": {
            "actionable_review_packet_present": bool(cap),
            "actionable_for_manual_review": cap.get("actionable_for_manual_review"),
            "ready_for_submission": cap.get("ready_for_submission"),
            "review_only": (cap.get("no_authority_flags") or {}).get("review_only")
            if isinstance(cap.get("no_authority_flags"), dict)
            else cap.get("review_only"),
        },
    }


def _sync_is_trusted_current(sync: dict[str, Any]) -> bool:
    return (
        bool(sync)
        and sync.get("sync_lifecycle_state") == "trusted_current"
        and sync.get("canonical_expected") == sync.get("observed")
        and sync.get("missing_expected") == 0
        and sync.get("hash_mismatch") == 0
    )


def _taxonomy_transmission_status(lights: dict[str, Any]) -> str | None:
    states = lights.get("current_light_states")
    if isinstance(states, dict):
        value = states.get("check_transmission")
        return str(value) if value is not None else None
    summary = lights.get("check_transmission_summary")
    if isinstance(summary, dict):
        value = summary.get("current_status")
        return str(value) if value is not None else None
    return None


def _check_transmission_readiness(sources: dict[str, dict[str, Any]]) -> str:
    sync = sources.get("sync_health", {})
    lights = sources.get("system_health_lights_taxonomy", {})
    taxonomy_status = _taxonomy_transmission_status(lights)
    if _sync_is_trusted_current(sync) and taxonomy_status in {"ON", "WARNING"}:
        return "NEEDS_SOURCE_TRUTH_RECONCILIATION"
    if _sync_is_trusted_current(sync):
        return "READY_FOR_SECURITY_AUDIT"
    if sync:
        return "NEEDS_PROOF"
    return "UNKNOWN_FAIL_CLOSED"


def _authority_boundary(*, future_gated_reason: str) -> dict[str, Any]:
    return {
        "current_authority": "metadata_read_model_contract_only",
        "package_preview_allowed_now": True,
        "live_execution_allowed_now": False,
        "model_actor_execution_allowed_now": False,
        "agent_activation_allowed_now": False,
        "tool_plugin_execution_allowed_now": False,
        "send_submit_approval_allowed_now": False,
        "credentials_or_account_flow_allowed_now": False,
        "autonomy_queue_allowed_now": False,
        "future_gated_until": future_gated_reason,
        "operator_memory_can_authorize_execution": False,
    }


def _lane_destiny_for(lane_id: str) -> dict[str, Any]:
    destiny_by_lane: dict[str, dict[str, Any]] = {
        "system_awareness_discovery": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "REQUEUE_FOR_SYSTEM_BUILD",
            "target_world": None,
            "reason": "This parent lane remains on the helm until child lanes have threshold posture, proof shelves, package previews, and quiet conditions.",
            "helm_after_resolution": "Show only active system-awareness focus or quiet proof summary.",
        },
        "capital_hilton": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "MOVE_TO_WORLD_ACTION",
            "target_world": "Finance",
            "reason": "Once invoice workflow proof, package boundaries, protected proof metadata, and security requirements are mapped, Winship should stop debugging the system and use Finance World to execute invoice work.",
            "helm_after_resolution": "Show only a small quiet marker if global health or authority is affected.",
        },
        "chief": {
            "current_phase": "HELM_SYSTEM_LANE",
            "resolution_route": "QUIET_BACKEND_RESOLVED",
            "target_world": None,
            "reason": "Chief check-engine work is system/workbench reliability; verified diagnostics should quiet or remain as proof.",
            "helm_after_resolution": "Disappear from the helm unless Check Engine is materially on.",
        },
        "cassandra": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "MOVE_TO_WORLD_ACTION",
            "target_world": "Communications / Finance",
            "reason": "When draft/review boundaries and security gates are mapped, actual comms/finance work belongs inside the relevant world.",
            "helm_after_resolution": "Show only attention markers for blocked authority or system-wide risk.",
        },
        "guardian": {
            "current_phase": "HELM_SYSTEM_LANE",
            "resolution_route": "SECURITY_AUDIT_REQUIRED",
            "target_world": None,
            "reason": "Guardian boundaries are structurally auditable but cannot become actionable authority without security review.",
            "helm_after_resolution": "Remain as quiet authority proof unless a blocked/security condition needs attention.",
        },
        "niles_struna": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "MOVE_TO_WORLD_ACTION",
            "target_world": "Music / Art",
            "reason": "Once music metadata/proof boundaries are mapped, album/art work belongs in the Music / Art World.",
            "helm_after_resolution": "Show only quiet proof or attention flags for missing proof.",
        },
        "hermes": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "PARK_WITH_PROOF",
            "target_world": None,
            "reason": "Hermes should be parked with proof unless a specific advisory/bridge task needs it.",
            "helm_after_resolution": "Keep as quiet proof or briefing context.",
        },
        "repo_b_leftovers": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "PARK_WITH_PROOF",
            "target_world": None,
            "reason": "Classified leftovers should be tagged, blocked, or parked rather than treated as active work.",
            "helm_after_resolution": "Hide except review/briefing surfaces or trigger changes.",
        },
        "cue_parser_brain_dump_parser": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "POST_SECURITY_AUTONOMY_CANDIDATE",
            "target_world": None,
            "reason": "Cue parsing may become planner/builder/autonomy work only after threshold and security gates.",
            "helm_after_resolution": "Hold as future-gated capability, not a live queue.",
        },
        "tool_plugin_registry": {
            "current_phase": "HELM_SYSTEM_LANE",
            "resolution_route": "SECURITY_AUDIT_REQUIRED",
            "target_world": None,
            "reason": "Capability grants are metadata until security audit defines what can be enabled.",
            "helm_after_resolution": "Show as quiet proof unless a package requests blocked capability.",
        },
        "model_router": {
            "current_phase": "HELM_THRESHOLD_LANE",
            "resolution_route": "SECURITY_AUDIT_REQUIRED",
            "target_world": None,
            "reason": "Actor/model routing can be audited as metadata, but live routing waits for security and explicit integration gates.",
            "helm_after_resolution": "Show as package compiler detail, not a front-door lane.",
        },
        "future_domain_workflow_lanes": {
            "current_phase": "HELM_PARKED_LANE",
            "resolution_route": "HOLDING_CELL",
            "target_world": "Future worlds",
            "reason": "Future worlds are valid but premature until a trigger, dependency, or briefing condition makes them relevant.",
            "helm_after_resolution": "Do not clutter the helm; keep in worlds/briefing surfaces.",
        },
        "check_engine": {
            "current_phase": "HEALTH_LIGHT",
            "resolution_route": "QUIET_BACKEND_RESOLVED",
            "target_world": None,
            "reason": "Check Engine is a system/workbench light; verified completion should quiet it rather than move it to a domain world.",
            "helm_after_resolution": "Disappear or remain as quiet proof unless malfunction returns.",
        },
        "check_transmission": {
            "current_phase": "HEALTH_LIGHT",
            "resolution_route": "QUIET_BACKEND_RESOLVED",
            "target_world": None,
            "reason": "Bridge proof issues are backend/system transport issues; trusted_current proof should quiet the light.",
            "helm_after_resolution": "Disappear from the helm or remain only as quiet proof.",
        },
        "resources": {
            "current_phase": "HEALTH_LIGHT",
            "resolution_route": "QUIET_BACKEND_RESOLVED",
            "target_world": None,
            "reason": "Resource warnings should quiet after measured-safe posture or become maintenance proof.",
            "helm_after_resolution": "Show only if resource pressure materially affects operator action.",
        },
        "parking_brake": {
            "current_phase": "AUTHORITY_LIGHT",
            "resolution_route": "SECURITY_AUDIT_REQUIRED",
            "target_world": None,
            "reason": "Authority locks remain normal until security review grants or denies specific action gates.",
            "helm_after_resolution": "Remain as quiet normal authority posture, not a failure.",
        },
        "traction_control": {
            "current_phase": "CONFIDENCE_LIGHT",
            "resolution_route": "PARK_WITH_PROOF",
            "target_world": None,
            "reason": "Confidence/detour posture appears only when an action or package needs it.",
            "helm_after_resolution": "Quiet unless confidence materially affects a current action.",
        },
    }
    destiny = destiny_by_lane.get(lane_id)
    if not destiny:
        return {
            "current_phase": "UNKNOWN_THRESHOLD_LANE",
            "resolution_route": "REQUEUE_FOR_SYSTEM_BUILD",
            "target_world": None,
            "reason": "No lane destiny was declared; fail closed.",
            "helm_after_resolution": "Return to system build until classified.",
        }
    return {
        **destiny,
        "allowed_resolution_routes": list(RESOLUTION_ROUTES),
        "not_currently_executable": True,
        "live_dispatch_allowed_now": False,
    }


def _lane_record(spec: LaneSpec) -> dict[str, Any]:
    return {
        "lane_id": spec.lane_id,
        "display_name": spec.display_name,
        "lane_kind": spec.lane_kind,
        "owner": spec.owner,
        "readiness_state": spec.readiness_state,
        "operator_summary": spec.operator_summary,
        "current_status": spec.current_status,
        "why_it_matters": spec.why_it_matters,
        "safe_next_move": spec.safe_next_move,
        "proof_refs": list(spec.proof_refs),
        "missing_proof": list(spec.missing_proof),
        "awareness": {
            "known": list(spec.known),
            "partly_known": list(spec.partly_known),
            "known_unknown": list(spec.known_unknown),
            "not_discovered": list(spec.not_discovered),
        },
        "operator_memory_needed": list(spec.operator_memory_needed),
        "operator_memory_is_proof": False,
        "authority_boundary": _authority_boundary(future_gated_reason=spec.future_gated_until),
        "package_preview": {
            "status": spec.package_preview_status,
            "live_dispatch_allowed": False,
            "copy_or_export_metadata_allowed_only_if_existing_supports_it": True,
        },
        "detour_path": spec.detour_path,
        "what_would_make_quiet": list(spec.makes_quiet),
        "lane_destiny": _lane_destiny_for(spec.lane_id),
        "surface_posture": spec.surface_posture,
        "future_gated_until": spec.future_gated_until,
        "blocked_actions": list(spec.blocked_actions),
    }


def _lane_specs(sources: dict[str, dict[str, Any]]) -> tuple[LaneSpec, ...]:
    check_transmission_state = _check_transmission_readiness(sources)
    return (
        LaneSpec(
            lane_id="system_awareness_discovery",
            display_name="System Awareness / Discovery",
            lane_kind="helm_lane",
            owner="Chief / OpenClaw",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="The terrain-mapping lane shows what OpenClaw knows, partly knows, knows it does not know, and has not discovered yet.",
            current_status="Threshold structure exists; it does not need to know everything before audit.",
            why_it_matters="This is the parent lane that lets Winship compare system awareness against memory and safely point out missing terrain.",
            safe_next_move="Use the threshold map to review whether each child lane has orientation, proof posture, package preview, and a quiet condition.",
            proof_refs=(
                "generated/read_models/operator_awareness_agent_package_spine.json",
                "generated/read_models/operator_nested_lane_mission_package_spine.json",
                "generated/read_models/steel_thread_lane_template_registry.json",
                "generated/read_models/operator_question_journey_registry.json",
            ),
            missing_proof=("complete terrain inventory is intentionally not required before audit",),
            known=(
                "awareness should separate known, partly known, known unknown, and undiscovered terrain",
                "operator memory can identify gaps without becoming proof",
                "package/detour preview is allowed now",
            ),
            partly_known=("not every future domain or subsystem has a complete child lane",),
            known_unknown=("which old design/source artifacts remain outside approved Repo A evidence",),
            not_discovered=("future domain/workflow lanes not yet inventoried",),
            operator_memory_needed=("missing terrain labels", "whether remembered artifacts are worth mapping"),
            package_preview_status="available_preview_only",
            detour_path="Tell System What's Missing / Discovery Classification Packet preview",
            makes_quiet=(
                "active child lanes are classified ready, parked, blocked, or discovery-needed",
                "proof shelves exist or missing proof is explicit",
                "no live execution control is shown",
            ),
            surface_posture="helm_parent_lane",
            future_gated_until="security audit and explicit launch/workspace gate",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="capital_hilton",
            display_name="Capital Hilton Invoice Lane",
            lane_kind="world_lane",
            owner="Cassandra / Guardian / Chief",
            readiness_state="NEEDS_PROOF",
            operator_summary="Capital Hilton is the difficult invoice steel-thread candidate, but protected Coupa/Excel proof remains missing or metadata-only.",
            current_status="Review-only packet posture exists; no invoice execution, Coupa access, send, submit, or credential handling is allowed.",
            why_it_matters="A hard invoice lane proves the package/proof/security pattern before broader business execution.",
            safe_next_move="Capture or point to approved protected proof metadata without opening Coupa, reading private proof bodies, or submitting anything.",
            proof_refs=(
                "generated/read_models/capital_hilton_actionable_review_packet.json",
                "generated/read_models/capital_hilton_external_artifact_proof_capture.json",
                "generated/read_models/capital_hilton_operator_proof_input_packet.json",
                "generated/read_models/capital_hilton_coupa_execution_path.json",
            ),
            missing_proof=(
                "approved Coupa proof metadata",
                "approved Excel/workbook proof metadata",
                "protected proof reference receipts sufficient for security review",
                "post-security credential and account-flow design",
            ),
            known=(
                "Capital Hilton has existing review-only/read-model packets",
                "manual review can be represented without execution",
                "ready_for_submission is not established",
            ),
            partly_known=(
                "invoice workflow outline and candidate evidence surfaces",
                "future package would need Cassandra, Guardian, and possibly Chief roles",
            ),
            known_unknown=(
                "which protected proof artifacts are enough for audit",
                "whether Coupa/Excel context can be represented without private body ingestion",
            ),
            not_discovered=("full post-security action route and receipts",),
            operator_memory_needed=("where the correct Coupa/Excel proof should be represented", "why this invoice is hard"),
            package_preview_status="candidate_preview_only",
            detour_path="Capital Hilton Protected Proof Metadata Population",
            makes_quiet=(
                "missing proof is captured as metadata or explicitly blocked",
                "package preview states no current execution authority",
                "security concerns are queued for audit instead of demanding action",
            ),
            surface_posture="steel_thread_focus",
            future_gated_until="security audit, protected proof policy, and explicit financial action approval gate",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="chief",
            display_name="Chief",
            lane_kind="agent_character_lane",
            owner="Chief",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="Chief owns system/workbench diagnosis and orchestration posture, not live repair.",
            current_status="Check-engine posture and diagnostic packages exist as inspect-only contracts.",
            why_it_matters="Chief is where system malfunction becomes a bounded diagnostic package.",
            safe_next_move="Audit Chief's diagnostic package boundaries and receipt expectations.",
            proof_refs=(
                "generated/read_models/chief_check_engine_environment_posture.json",
                "generated/read_models/chief_check_engine_diagnostic_package.json",
            ),
            missing_proof=("future repair authority design is intentionally absent",),
            known=("Chief can diagnose workbench/system degradation", "Chief cannot repair or execute from this contract"),
            partly_known=("future Chief test harness requires classification",),
            known_unknown=("what exact post-security maintenance lanes Chief may run",),
            not_discovered=("approved safe maintenance autopilot policy",),
            operator_memory_needed=("which Chief artifacts matter for the security audit",),
            package_preview_status="available_preview_only",
            detour_path="Chief Diagnostic Package Review",
            makes_quiet=("diagnostic package is auditable", "repair remains blocked until security review"),
            surface_posture="helm_lane_when_check_engine_visible",
            future_gated_until="security audit and explicit maintenance authority",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="cassandra",
            display_name="Cassandra",
            lane_kind="agent_character_lane",
            owner="Cassandra / Guardian",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="Cassandra can expose safe review/draft packet visibility, while Gmail/calendar/Telegram/live send remains blocked.",
            current_status="Visibility and review packets are safe; live communications actions are not authorized.",
            why_it_matters="Communications and finance workflows need strict separation between draft visibility and external action.",
            safe_next_move="Audit draft/review package boundaries and missing identity/proof rails.",
            proof_refs=(
                "generated/read_models/cassandra_email_calendar_delta_detangle.json",
                "generated/read_models/cassandra_governed_review_packet_request_proof.json",
                "generated/read_models/cassandra_send_status_dry_run.json",
            ),
            missing_proof=("draft identity reference rail may still need hardening",),
            known=("review/draft packets are visibility-only", "send and account actions remain blocked"),
            partly_known=("which future comms packages need operator confirmation",),
            known_unknown=("calendar merge details requiring operator clarification",),
            not_discovered=("post-security external comms authority design",),
            operator_memory_needed=("identity/context clarification for drafts and calendars"),
            package_preview_status="available_preview_only",
            detour_path="Cassandra Draft Identity Reference Rail",
            makes_quiet=("safe review packets are auditable", "external sends remain visibly blocked"),
            surface_posture="agent_lane",
            future_gated_until="security audit and explicit send/account approval gates",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="guardian",
            display_name="Guardian",
            lane_kind="agent_character_lane",
            owner="Guardian",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="Guardian owns boundaries, protected access posture, and fail-closed rules.",
            current_status="Protected access receipt/gate specs exist; receipts are not keys, approvals, or execution.",
            why_it_matters="Guardian makes the security audit possible by keeping authority explicit.",
            safe_next_move="Audit boundary enums, protected evidence references, and blocked authority surfaces.",
            proof_refs=(
                "generated/read_models/protected_evidence_reference_receipt.json",
                "generated/read_models/guardian_protected_access_gate_spec.json",
                "generated/read_models/package_compiler_contract.json",
            ),
            missing_proof=("post-security approval policy remains future-gated",),
            known=("protected proof can be referenced", "protected receipt is not access authority"),
            partly_known=("which future protected workflows require richer clearance levels",),
            known_unknown=("full no-go data taxonomy after security audit",),
            not_discovered=("approved credential/account handling architecture",),
            operator_memory_needed=("security-review priorities and no-go examples"),
            package_preview_status="available_preview_only",
            detour_path="Guardian Boundary Validation Review",
            makes_quiet=("authority boundary is explicit", "blocked actions are not rendered as live controls"),
            surface_posture="agent_lane_and_authority_detail",
            future_gated_until="security audit",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="niles_struna",
            display_name="Niles / Struna",
            lane_kind="agent_character_lane",
            owner="Niles",
            readiness_state="NEEDS_PROOF",
            operator_summary="Niles/Struna exists as a music/art lane candidate, but real album metadata/proof remains incomplete.",
            current_status="Music lane can be mapped; it should not claim album truth without proof.",
            why_it_matters="Music/art is a key world, but taste and metadata must not be invented.",
            safe_next_move="Classify required album metadata and safe proof intake boundaries.",
            proof_refs=(
                "generated/read_models/niles_album_metadata_intake_packet.json",
                "generated/read_models/niles_album_evidence_intake_boundary.json",
            ),
            missing_proof=("real album metadata", "approved music/art source references"),
            known=("Niles is the music/art character", "Struna is associated with the music lane"),
            partly_known=("album review packet shapes exist",),
            known_unknown=("which source artifacts Winship remembers",),
            not_discovered=("complete music/art world package contract",),
            operator_memory_needed=("album/source pointers and taste context"),
            package_preview_status="candidate_preview_only",
            detour_path="Niles Album Metadata Proof Intake",
            makes_quiet=("metadata gaps are listed or parked", "no invented album truth appears"),
            surface_posture="world_lane_attention_when_missing_proof_matters",
            future_gated_until="approved proof/source intake and security audit",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="hermes",
            display_name="Hermes",
            lane_kind="agent_character_lane",
            owner="Hermes",
            readiness_state="NEEDS_CONTEXT",
            operator_summary="Hermes is a bridge/advisory character, but status and proof need memory/proof review.",
            current_status="Do not overclaim Hermes confidence until memory/proof is reviewed.",
            why_it_matters="Hermes may advise on big-picture bridge/state transfer, so its authority must be clear.",
            safe_next_move="Run a non-live Hermes Status Memory/Proof Review detour later.",
            proof_refs=("generated/read_models/operator_awareness_agent_package_spine.json",),
            missing_proof=("Hermes status proof", "operator memory comparison receipt"),
            known=("Hermes is a big-picture/advisory candidate",),
            partly_known=("relationship to bridge/state-transfer is partially mapped",),
            known_unknown=("which Hermes artifacts exist and matter",),
            not_discovered=("complete Hermes package boundaries",),
            operator_memory_needed=("what Winship remembers Hermes should own"),
            package_preview_status="candidate_preview_only",
            detour_path="Hermes Status Memory/Proof Review",
            makes_quiet=("Hermes is classified as ready, parked, or blocked with explicit proof posture"),
            surface_posture="agent_lane_attention",
            future_gated_until="memory/proof review and security audit",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="repo_b_leftovers",
            display_name="Repo B Leftovers",
            lane_kind="helm_lane",
            owner="Chief / Guardian",
            readiness_state="NEEDS_DISCOVERY_CLASSIFICATION",
            operator_summary="Repo B leftovers are known to exist but are not fully classified in this lane.",
            current_status="Do not inspect broad Repo B bodies or run Repo B code.",
            why_it_matters="Unclassified leftovers can confuse Mission Control if surfaced as active truth.",
            safe_next_move="Create a narrow classification packet later, with no broad private body inspection.",
            proof_refs=("generated/read_models/cross_repo_awareness_matrix.json",),
            missing_proof=("tagged leftover inventory", "safe classification receipts"),
            known=("Repo B leftovers are not fully classified",),
            partly_known=("some cross-repo awareness exists",),
            known_unknown=("which leftovers should be tagged, blocked, or ignored",),
            not_discovered=("full safe inventory under approved boundaries",),
            operator_memory_needed=("which leftovers Winship remembers and why they matter"),
            package_preview_status="candidate_preview_only",
            detour_path="Repo B Leftover Classification Packet",
            makes_quiet=("leftovers are tagged, blocked, or parked without broad Repo B inspection"),
            surface_posture="helm_detail_not_front_door",
            future_gated_until="explicit classification lane and security audit",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="cue_parser_brain_dump_parser",
            display_name="Cue Parser / Brain Dump Parser",
            lane_kind="helm_lane",
            owner="Chief",
            readiness_state="NEEDS_DISCOVERY_CLASSIFICATION",
            operator_summary="Cue parsing is a candidate future intake capability, not an active autonomy queue.",
            current_status="Discovery/classification only; no planner/builder loop or holding-cell automation is active.",
            why_it_matters="Cue intake could become powerful after threshold/security, so it must be classified before action.",
            safe_next_move="Define non-live cue parser intake classification and holding-cell rules.",
            proof_refs=("generated/read_models/package_compiler_contract.json",),
            missing_proof=("cue schema", "planner/builder boundaries", "security-approved holding cell mutation rules"),
            known=("cue/autonomy belongs post-threshold and post-security",),
            partly_known=("planner, builder, orchestrator, Chief harness, and holding cell are candidate terms",),
            known_unknown=("which cue forms should become durable inputs",),
            not_discovered=("safe execution and review lifecycle after audit",),
            operator_memory_needed=("examples of cue inputs and desired review behavior"),
            package_preview_status="future_candidate_preview_only",
            detour_path="Cue Parser Intake Classification",
            makes_quiet=("classified as future-gated with trigger conditions and no active queue"),
            surface_posture="holding_cell_candidate",
            future_gated_until="threshold review, security audit, and explicit autonomy authority lane",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="tool_plugin_registry",
            display_name="Tool / Plugin Registry",
            lane_kind="helm_lane",
            owner="Guardian / Chief",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="Tool/plugin registry metadata can be audited as metadata, not as enabled tools.",
            current_status="Registry metadata exists; plugin execution remains blocked.",
            why_it_matters="Mission packages must know allowed/forbidden capabilities before any launch.",
            safe_next_move="Audit capability classes and blocked-by-default posture.",
            proof_refs=(
                "generated/read_models/capability_skill_registry_metadata_delta.json",
                "generated/read_models/package_compiler_contract.json",
            ),
            missing_proof=("post-security plugin grant policy",),
            known=("capability metadata exists", "tools/plugins are not live authority"),
            partly_known=("which future workbenches may receive which capabilities",),
            known_unknown=("security-approved grant matrix",),
            not_discovered=("full plugin execution governance",),
            operator_memory_needed=("which tool families matter first"),
            package_preview_status="available_preview_only",
            detour_path="Capability Grant Review",
            makes_quiet=("metadata is auditable and execution remains blocked"),
            surface_posture="proof_detail_and_package_boundary",
            future_gated_until="security audit",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="model_router",
            display_name="Model Router",
            lane_kind="helm_lane",
            owner="Chief / Guardian",
            readiness_state="NEEDS_DISCOVERY_CLASSIFICATION",
            operator_summary="Actor/model routing doctrine exists, but live routing is future-gated.",
            current_status="Candidate labels and workbench hooks exist; no model APIs or launches are wired.",
            why_it_matters="The actor should never decide its own authority, tools, or workspace.",
            safe_next_move="Audit router metadata and unknown-actor fail-closed behavior.",
            proof_refs=(
                "generated/read_models/operator_workbench_actor_host_registry.json",
                "generated/read_models/package_compiler_contract.json",
            ),
            missing_proof=("approved actor availability checks", "security-reviewed model routing policy"),
            known=("model is actor", "agent is character", "package is deterministic mission payload"),
            partly_known=("candidate actors/workbenches are listed as labels",),
            known_unknown=("which actors are available and approved after security",),
            not_discovered=("live routing implementation, intentionally absent"),
            operator_memory_needed=("preferred actors for future lanes"),
            package_preview_status="available_preview_only",
            detour_path="Model Router Classification",
            makes_quiet=("router remains metadata-only or receives explicit post-security gate"),
            surface_posture="package_compiler_detail",
            future_gated_until="security audit and explicit actor-host integration lane",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="future_domain_workflow_lanes",
            display_name="Future Domain / Workflow Lanes",
            lane_kind="future_domain_lane",
            owner="OpenClaw",
            readiness_state="PARKED_WITH_PROOF",
            operator_summary="Future worlds can be visible as teleport targets but should not clutter the helm unless they need attention.",
            current_status="Parked until they block the current mission or need classification.",
            why_it_matters="The helm must stay calm while still preserving future terrain.",
            safe_next_move="Keep parked with dependency markers and review them in briefing surfaces.",
            proof_refs=("generated/read_models/operator_mission_priority_helm_declutter.json",),
            missing_proof=("domain-specific package contracts for most future worlds",),
            known=("worlds include music/art, finance, operations, security, build, research, communications, business development, and future domains",),
            partly_known=("domain attention should rise to the helm only when meaningful",),
            known_unknown=("which future world should be built next after helm finish",),
            not_discovered=("full world-specific workflows",),
            operator_memory_needed=("which parked worlds matter soon"),
            package_preview_status="not_required_until_unparked",
            detour_path="World Lane Classification when unparked",
            makes_quiet=("parked lanes stay out of the front door until trigger conditions fire"),
            surface_posture="world_teleport_target_not_top_card",
            future_gated_until="mission priority review",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="check_engine",
            display_name="Check Engine",
            lane_kind="check_light_lane",
            owner="Chief",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="Check Engine is for system/workbench malfunction, not normal domain attention.",
            current_status="Diagnostic packages exist; repair remains future-gated.",
            why_it_matters="System faults need a Chief package, not scattered lane clutter.",
            safe_next_move="Show the light only when system/workbench degradation materially affects work.",
            proof_refs=(
                "generated/read_models/system_health_lights_taxonomy.json",
                "generated/read_models/chief_check_engine_diagnostic_package.json",
            ),
            missing_proof=("future repair package policy",),
            known=("check-engine lane opens Chief diagnostic/system health lane",),
            partly_known=("current Mac/workbench friction may recur",),
            known_unknown=("which maintenance actions can later become safe autopilot",),
            not_discovered=("post-security repair gates",),
            operator_memory_needed=("symptoms not visible in Repo A proof"),
            package_preview_status="available_preview_only",
            detour_path="Chief Check-Engine Diagnostic Package",
            makes_quiet=("no active system/workbench degradation or degradation is parked with proof"),
            surface_posture="health_light",
            future_gated_until="security audit and maintenance authority lane",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="check_transmission",
            display_name="Check Transmission",
            lane_kind="check_light_lane",
            owner="Chief / Mirror Trust",
            readiness_state=check_transmission_state,
            operator_summary="Check Transmission is for PC-Mac bridge/sync/state-transfer proof, separate from Check Engine.",
            current_status="Current sync_health can be trusted only if Mission Control-visible state reads the same source truth.",
            why_it_matters="The helm must not say the drivetrain is broken when canonical PC proof is current.",
            safe_next_move="If app still shows red while sync_health is trusted/current, classify it as a Mac source-truth readback bug for Mac Codex later.",
            proof_refs=(
                "generated/read_models/sync_health.json",
                "generated/read_models/system_health_lights_taxonomy.json",
                "/mnt/e/openclaw/mac_generated_read_models_manifest.json",
            ),
            missing_proof=("Mac app visible state was not inspected in this lane",),
            known=("sync_health is the canonical PC proof source",),
            partly_known=("system health taxonomy or app may be stale if it still shows Check Transmission ON",),
            known_unknown=("whether visible app state currently reads stale taxonomy or stale mirror file",),
            not_discovered=("Mac UI readback fix details",),
            operator_memory_needed=("whether Winship sees a red Check Transmission light in the app"),
            package_preview_status="available_preview_only",
            detour_path="Mac Codex Sync Health Readback Fix later if conflict is visible",
            makes_quiet=("sync_health trusted_current with zero missing/hash mismatch and app-visible Check Transmission not stale-red"),
            surface_posture="health_light_and_source_truth_conflict_if_visible",
            future_gated_until="Mac app readback lane if visible conflict exists",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="resources",
            display_name="Resources / Low Fuel",
            lane_kind="resource_light_lane",
            owner="Chief",
            readiness_state="NEEDS_CONTEXT",
            operator_summary="Resource pressure needs a posture lane, but fresh measurements are not taken here.",
            current_status="Recent C-drive pressure was cleaned; ongoing resource posture should be monitored only after policy.",
            why_it_matters="Storage/credits/compute pressure can block work without being a domain bug.",
            safe_next_move="Define resource posture read-model thresholds without live monitoring or cleanup authority.",
            proof_refs=("generated/read_models/chief_check_engine_environment_posture.json",),
            missing_proof=("fresh resource posture measurements", "approved monitoring policy"),
            known=("recent C-drive pressure was not Repo A bloat", "OpenClaw artifacts should not be written to the PC system drive"),
            partly_known=("resource posture needs a future lane",),
            known_unknown=("thresholds for storage, credits, compute, and tool availability",),
            not_discovered=("non-invasive resource monitoring design",),
            operator_memory_needed=("which resource constraints matter most"),
            package_preview_status="candidate_preview_only",
            detour_path="Resource Posture Threshold Contract",
            makes_quiet=("resource thresholds and evidence cadence are explicit or parked"),
            surface_posture="health_light_when_material",
            future_gated_until="security audit and monitoring policy",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="parking_brake",
            display_name="Parking Brake",
            lane_kind="authority_light_lane",
            owner="Guardian",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="Parking Brake means authority is intentionally locked; it is normal, not a failure.",
            current_status="Execution/send/approval/runtime paths remain locked before security audit.",
            why_it_matters="The operator must understand intentional locks without mistaking them for errors.",
            safe_next_move="Render as ON_NORMAL or equivalent, with proof behind drill-in.",
            proof_refs=(
                "generated/read_models/package_compiler_contract.json",
                "generated/read_models/system_health_lights_taxonomy.json",
            ),
            missing_proof=("post-security gate policy",),
            known=("authority locks are deliberate", "not every visible lock is a fault"),
            partly_known=("which gates may later be relaxed",),
            known_unknown=("security approval gates after audit",),
            not_discovered=("post-security approval UX",),
            operator_memory_needed=("which locks should remain permanent"),
            package_preview_status="available_preview_only",
            detour_path="Authority Boundary Review",
            makes_quiet=("operator understands lock posture and no action is requested"),
            surface_posture="normal_authority_light",
            future_gated_until="security audit",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
        LaneSpec(
            lane_id="traction_control",
            display_name="Traction Control",
            lane_kind="confidence_light_lane",
            owner="Chief / Guardian",
            readiness_state="READY_FOR_SECURITY_AUDIT",
            operator_summary="Traction Control appears only when confidence/detour affects action.",
            current_status="No fake percentages; deterministic/full-trust states should be quiet.",
            why_it_matters="Confidence UI should prevent unsafe action without becoming theater.",
            safe_next_move="Audit confidence/detour fields in package and lane templates.",
            proof_refs=(
                "generated/read_models/steel_thread_lane_template_registry.json",
                "generated/read_models/package_compiler_contract.json",
            ),
            missing_proof=("post-security action failure reset policy",),
            known=("below deterministic confidence shows detours", "deterministic confidence hides noisy UI"),
            partly_known=("which future actions need confidence detours",),
            known_unknown=("detour receipts after live workflows exist",),
            not_discovered=("runtime failure reset implementation",),
            operator_memory_needed=("which detours Winship expects for low-confidence lanes"),
            package_preview_status="available_preview_only",
            detour_path="Confidence Detour Contract Review",
            makes_quiet=("no active package needs confidence repair or detour"),
            surface_posture="visible_only_when_material",
            future_gated_until="security audit and action workflow lanes",
            blocked_actions=FORBIDDEN_ACTIONS,
        ),
    )


def _threshold_definition() -> dict[str, Any]:
    required_fields = (
        "operator_summary",
        "current_status",
        "why_it_matters",
        "safe_next_move",
        "proof_refs",
        "missing_proof",
        "known_partly_known_known_unknown_not_discovered",
        "operator_memory_needed",
        "authority_boundary",
        "package_preview_availability",
        "detour_path",
        "what_would_make_quiet",
    )
    return {
        "meaning": "A lane crosses the pre-security threshold when it is auditable as a bounded contract, not when it is executable.",
        "ready_for_security_audit_does_not_mean_executable": True,
        "required_checklist": [
            {
                "field": field,
                "required_before_security_audit": True,
                "proof_may_be_explicitly_missing": field in {"missing_proof", "operator_memory_needed"},
            }
            for field in required_fields
        ],
        "states": list(THRESHOLD_STATES),
        "proof_memory_separation": {
            "operator_memory_can_identify_missing_terrain": True,
            "operator_memory_can_clarify_intent": True,
            "operator_memory_can_label_gap": True,
            "operator_memory_may_be_stored_as_bounded_summary": True,
            "operator_memory_is_machine_proof": False,
            "operator_memory_authorizes_execution": False,
            "operator_memory_replaces_security_audit": False,
        },
        "confidence_policy": {
            "fake_percentages_allowed": False,
            "deterministic_full_trust_ui_should_be_quiet": True,
            "below_deterministic_shows_reason_and_detour": True,
            "failed_job_resets_confidence_later": True,
        },
    }


def _group_lanes(lanes: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {state: [] for state in THRESHOLD_STATES}
    for lane in lanes:
        grouped.setdefault(lane["readiness_state"], []).append(lane["lane_id"])
    return {key: value for key, value in grouped.items() if value}


def _capital_hilton_steel_thread() -> dict[str, Any]:
    return {
        "steel_thread_id": "capital_hilton_invoice_lane",
        "purpose": "Prove a difficult real invoice workflow can be represented end-to-end before broader domain execution.",
        "current_readiness": "NEEDS_PROOF",
        "current_phase": "HELM_THRESHOLD_LANE",
        "intended_destiny": "MOVE_TO_WORLD_ACTION",
        "target_world": "Finance",
        "destiny_reason": "Once invoice workflow proof, package boundaries, protected proof metadata, and security requirements are mapped, Winship should stop debugging the system and use Finance World to execute invoice work.",
        "not_currently_executable": True,
        "known": [
            "Capital Hilton has existing review-only packet/read-model coverage.",
            "It is intentionally harder than ordinary invoice lanes.",
            "Coupa, Excel, credentials, protected proof, send, submit, and approval are not available in this lane.",
        ],
        "partly_known": [
            "Expected workflow can be outlined as review proof, compile package, audit authority, then possibly post-security action.",
            "Cassandra can handle communications/finance framing, Guardian owns protected access boundaries, and Chief can coordinate diagnostics.",
        ],
        "missing_proof": [
            "Coupa proof metadata.",
            "Excel/workbook proof metadata.",
            "Protected evidence reference receipts sufficient for audit.",
            "Post-security account/credential handling design.",
        ],
        "operator_memory_may_clarify": [
            "where the proof should exist",
            "why this invoice is difficult",
            "which fields are expected from memory",
        ],
        "operator_memory_is_not_proof": True,
        "future_package_candidate": {
            "package_type": "world_lane_work_package",
            "agent_characters": ["Cassandra", "Guardian", "Chief"],
            "actor_model_candidate": "future selected actor, not live",
            "target_workbench_or_actor_host": "future-gated after security audit",
            "context_included": [
                "approved read-model refs",
                "protected proof metadata refs",
                "operator-confirmed workflow outline",
                "authority boundary",
                "receipt requirements",
            ],
            "context_excluded": [
                "credentials",
                "raw Coupa pages",
                "raw spreadsheet bodies",
                "private message bodies",
                "bank/account data",
            ],
            "dispatch_allowed_now": False,
        },
        "authority_required_later": [
            "protected_context_required clearance",
            "explicit credential/account handling policy",
            "Guardian-approved proof capture",
            "operator approval gate for send/submit/account flows",
        ],
        "ready_for_security_audit_when": [
            "proof refs or missing-proof refs are explicit",
            "operator memory gaps are labelled but not treated as proof",
            "package preview contains deterministic boundaries and receipts",
            "Coupa/Excel/private bodies remain excluded",
        ],
        "ready_for_post_security_action_when": [
            "security audit grants narrow authority",
            "credential/account path is approved",
            "required receipts and validations are deterministic",
            "human confirmation gates are explicit",
        ],
        "what_makes_quiet": [
            "missing proof is captured as metadata or explicitly blocked",
            "the lane is parked with proof until security audit",
            "Mission Control does not show live invoice actions",
        ],
        "no_current_execution_boundary": dict(NO_AUTHORITY_FLAGS),
    }


def _system_awareness_steel_thread() -> dict[str, Any]:
    return {
        "steel_thread_id": "system_awareness_discovery_lane",
        "purpose": "Define how awareness lanes unfold with or without operator involvement.",
        "current_readiness": "READY_FOR_SECURITY_AUDIT",
        "lane_anatomy": [
            "operator orientation layer",
            "machine proof layer",
            "package/detour preview layer",
            "quiet condition",
            "authority boundary",
        ],
        "terrain_known": [
            "OpenClaw has a helm/developer mode doctrine.",
            "Nested lanes belong mostly in backend/read-models.",
            "Operator memory can identify missing terrain.",
            "Package previews are allowed; live dispatch is not.",
        ],
        "terrain_partly_known": [
            "Chief, Cassandra, Guardian, Niles, Hermes, Repo B leftovers, cue parser, tool registry, model router, and future worlds have uneven readiness.",
            "Some source-truth conflicts can occur when a derived UI/read-model lags canonical proof.",
        ],
        "terrain_unknown": [
            "complete future domain inventory",
            "all old source artifacts Winship remembers",
            "post-security autonomy design",
        ],
        "operator_memory_rule": {
            "can_help_by": [
                "pointing to missing X",
                "labeling a gap",
                "clarifying intent",
                "classifying a lane as worth mapping",
            ],
            "must_be_recorded_as": "operator-provided context or memory comparison need",
            "may_not": [
                "become proof by itself",
                "authorize execution",
                "replace machine contract",
                "bypass security audit",
                "imply private data ingestion",
            ],
        },
        "tell_system_whats_missing_now": {
            "meaning": "A non-live capture/package-preview affordance that records a gap label and proposed discovery lane.",
            "allowed_now": "preview/generate bounded context artifact only if existing support permits it",
            "not_allowed_now": "live write, live agent launch, broad scan, private ingestion, or execution",
        },
        "when_operator_chat_needed_later": [
            "operator memory comparison is required",
            "the system cannot classify a remembered artifact",
            "intent or taste is ambiguous",
            "human confirmation is required before protected context",
        ],
        "when_operator_chat_not_needed_later": [
            "machine proof is current and deterministic",
            "missing proof is already explicit and parked",
            "safe next move is already a static package preview",
        ],
        "ready_for_security_audit_when": [
            "each visible lane has orientation, proof/missing-proof posture, package preview, boundary, detour, and quiet condition",
            "operator memory is separated from proof",
            "live execution remains future-gated",
        ],
        "what_makes_quiet": [
            "lanes are ready, blocked, parked, or discovery-needed with no ambiguous front-door clutter",
            "confidence detours appear only when needed",
            "health lights reflect current source truth",
        ],
    }


def _package_preview_now_vs_later() -> dict[str, Any]:
    return {
        "package_preview_now_allowed": True,
        "package_export_or_copy_metadata_now": "allowed_only_if_existing_support_already_provides_it",
        "live_chat_or_workbench_launch_now": False,
        "model_actor_execution_now": False,
        "agent_activation_now": False,
        "plugin_or_tool_execution_now": False,
        "send_submit_approval_account_flows_now": False,
        "autonomy_queue_now": False,
        "autonomy_queue_after_security": "future-gated candidate only",
    }


def _cue_autonomy_placement() -> dict[str, Any]:
    return {
        "status": "post_threshold_post_security_candidate",
        "current_contract_may_mention": [
            "cue parser",
            "planner agent",
            "builder agent",
            "orchestrator",
            "Chief test harness",
            "holding cell",
        ],
        "current_classification": {
            "cue_parser": "NEEDS_DISCOVERY_CLASSIFICATION",
            "planner_agent": "future_gated_not_active_authority",
            "builder_agent": "future_gated_not_active_authority",
            "orchestrator": "coordination_role_only_not_runtime_loop",
            "chief_test_harness": "NEEDS_DISCOVERY_CLASSIFICATION",
            "holding_cell": "parking_rule_only_not_live_queue",
        },
        "not_created_by_this_contract": [
            "live queue",
            "planner/builder execution",
            "agent activation",
            "runtime actions",
            "tool/plugin calls",
            "hidden monitoring",
        ],
    }


def _holding_cell_rule() -> dict[str, Any]:
    return {
        "purpose": "Park valid but premature ideas without making them front-door clutter or live queue items.",
        "valid_trigger_conditions": [
            "blocked until security audit",
            "needs source artifact",
            "needs operator memory comparison",
            "depends on another lane crossing threshold",
            "future domain/workflow not needed for current mission",
        ],
        "metadata_markers": [
            "dependency_marker",
            "stale_or_obsolete_marker",
            "operator_review_marker",
            "briefing_candidate",
            "security_audit_dependency",
        ],
        "mutates_state_now": False,
        "live_queue_now": False,
    }


def _mission_control_rendering_guidance() -> dict[str, Any]:
    return {
        "show_now": [
            "current mission",
            "health lights",
            "one active parent lane",
            "one immediate focus child",
            "next safe move",
            "authority boundary",
            "package/detour preview only when relevant",
        ],
        "hide_or_collapse_now": [
            "full nested lane tree by default",
            "every read-model as an equal card",
            "raw machine proof until drill-in",
            "holding cell except review/briefing surfaces",
            "parked future worlds unless they need attention",
        ],
        "never_show_pre_security": [
            "fake confidence percentages",
            "100 percent confidence buttons",
            "live execution controls",
            "post-security autonomy queue controls",
            "send/submit/approval/account-flow controls",
        ],
        "steel_thread_flow_inside_lane": [
            "ELI5/operator orientation",
            "machine contract/proof",
            "package/detour/fix path",
        ],
    }


def _source_truth_note(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sync = sources.get("sync_health", {})
    lights = sources.get("system_health_lights_taxonomy", {})
    taxonomy_status = _taxonomy_transmission_status(lights)
    trusted = _sync_is_trusted_current(sync)
    conflict = trusted and taxonomy_status in {"ON", "WARNING"}
    missing_expected = sync.get("missing_expected") or 0
    if conflict:
        app_visible_interpretation = "If the app still shows red, classify it as a Mac Mission Control source-truth/readback conflict, not bridge failure."
        fix_owner = "Mac Codex"
        action_now = "classify only; do not mutate app code, repair sync, or run sync scripts from this threshold contract"
    elif sync and missing_expected:
        app_visible_interpretation = "If the app shows red now, it reflects the current canonical mirror gap until the normal Mac sync returns the missing files."
        fix_owner = "Mac read-model sync agent / PC import proof lifecycle"
        action_now = "use the normal read-model mirror lifecycle; do not mutate app code or fake mirror completion"
    else:
        app_visible_interpretation = "No Check Transmission source-truth conflict is detected from current Repo A proof."
        fix_owner = "none"
        action_now = "no threshold-map source-truth repair is needed"
    return {
        "note_id": "check_transmission_source_truth_note",
        "canonical_sync_health_status": {
            "sync_lifecycle_state": sync.get("sync_lifecycle_state"),
            "canonical_expected": sync.get("canonical_expected"),
            "observed": sync.get("observed"),
            "missing_expected": sync.get("missing_expected"),
            "hash_mismatch": sync.get("hash_mismatch"),
            "trusted_current": trusted,
        },
        "system_health_taxonomy_check_transmission_status": taxonomy_status,
        "visible_mac_app_state_observed_in_this_lane": False,
        "source_truth_conflict_detected_in_read_models": conflict,
        "app_visible_interpretation": app_visible_interpretation,
        "fix_owner_later": fix_owner,
        "action_now": action_now,
    }


def _before_after_security_boundary() -> dict[str, Any]:
    return {
        "before_security_audit_allowed": [
            "deterministic read-model contracts",
            "operator orientation text",
            "machine proof references",
            "explicit missing-proof lists",
            "package preview",
            "detour preview",
            "holding-cell metadata",
            "operator memory comparison markers",
        ],
        "before_security_audit_blocked": [
            "live model or agent execution",
            "package dispatch",
            "workflow execution",
            "browser/account/OAuth/Coupa/Gmail/calendar/Telegram actions",
            "send/submit/approval actions",
            "credential handling",
            "Repo B planner-builder execution",
            "autonomy queue",
        ],
        "after_security_audit_still_requires_explicit_lane": [
            "actor/model launch",
            "workbench session launch",
            "tool/plugin capability grant",
            "protected context handling",
            "external account actions",
            "automation/autonomy queue",
        ],
    }


def _helm_quiet_conditions() -> list[str]:
    return [
        "health lights reflect current source truth and are quiet unless material",
        "active parent lane and immediate focus child are clear",
        "every visible lane has threshold fields or is explicitly parked/blocked",
        "proof is behind drill-in rather than front-door clutter",
        "confidence/detour UI appears only when confidence affects action",
        "future-gated cue/autonomy controls are not rendered",
        "operator memory gaps are labelled without becoming proof",
    ]


def build_operator_threshold_map_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sources = {
        source.key: _read_json_if_present(source.path, repo_root=repo_root)
        for source in SOURCE_READ_MODELS
    }
    lane_records = [_lane_record(spec) for spec in _lane_specs(sources)]
    grouped = _group_lanes(lane_records)
    contract_hash = _hash_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "threshold_states": list(THRESHOLD_STATES),
            "lane_states": [(lane["lane_id"], lane["readiness_state"]) for lane in lane_records],
            "steel_threads": ["capital_hilton_invoice_lane", "system_awareness_discovery_lane"],
            "authority_flags": NO_AUTHORITY_FLAGS,
        }
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "operator_threshold_map_contract",
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "OpenClaw Threshold Map Contract v0",
        "contract_status": "pre_security_threshold_map_metadata_only",
        "purpose": "Define what active lanes must know, prove, expose, park, or classify before OpenClaw is ready for security audit.",
        "strategic_correction": {
            "not_autonomy_queue_implementation": True,
            "cue_autonomy_post_threshold_post_security": True,
            "packages_are_preview_contract_artifacts_only": True,
        },
        "core_doctrine": {
            "model_is_actor": True,
            "agent_is_character": True,
            "package_is_deterministic_mission_payload": True,
            "package_contains": [
                "context",
                "proof",
                "tools/capabilities metadata",
                "clearance",
                "steps",
                "stop conditions",
                "boundaries",
                "receipts",
            ],
            "package_executes_now": False,
        },
        "threshold_definition": _threshold_definition(),
        "threshold_state_vocab": list(THRESHOLD_STATES),
        "resolution_route_vocab": list(RESOLUTION_ROUTES),
        "lane_kind_vocab": list(LANE_KINDS),
        "lane_inventory": lane_records,
        "lane_count": len(lane_records),
        "lane_readiness_table": [
            {
                "lane_id": lane["lane_id"],
                "display_name": lane["display_name"],
                "readiness_state": lane["readiness_state"],
                "safe_next_move": lane["safe_next_move"],
                "package_preview_status": lane["package_preview"]["status"],
                "resolution_route": lane["lane_destiny"]["resolution_route"],
                "target_world": lane["lane_destiny"]["target_world"],
                "surface_posture": lane["surface_posture"],
            }
            for lane in lane_records
        ],
        "lane_destiny_resolution_routes": {
            lane["lane_id"]: lane["lane_destiny"] for lane in lane_records
        },
        "lane_ids_by_readiness_state": grouped,
        "first_steel_thread_capital_hilton": _capital_hilton_steel_thread(),
        "second_steel_thread_system_awareness_discovery": _system_awareness_steel_thread(),
        "package_preview_now_vs_live_package_later": _package_preview_now_vs_later(),
        "cue_autonomy_placement": _cue_autonomy_placement(),
        "holding_cell_rule": _holding_cell_rule(),
        "operator_memory_rule": _threshold_definition()["proof_memory_separation"],
        "mission_control_rendering_guidance": _mission_control_rendering_guidance(),
        "helm_to_world_transition_rule": {
            "helm_shows": [
                "lanes that affect system readiness",
                "proof, safety, mapping, or blockers",
                "health lights and current mission",
            ],
            "worlds_show": [
                "domain work that is ready to perform",
                "post-security workflows with approved authority",
                "operator work inside the correct domain world",
            ],
            "after_lane_moves_to_world": "Helm should only show a small quiet marker if global health or authority is affected.",
            "backend_only_after_verified_completion": "Backend-only issues should disappear from the helm or remain only as quiet proof.",
        },
        "check_transmission_source_truth_note": _source_truth_note(sources),
        "before_security_audit_vs_after_security_audit": _before_after_security_boundary(),
        "what_makes_the_helm_quiet": _helm_quiet_conditions(),
        "what_must_wait_until_security_audit": _before_after_security_boundary()[
            "before_security_audit_blocked"
        ],
        "what_must_wait_until_post_security_actionable_workflow_autonomy": [
            "autonomy queue",
            "planner/builder loops",
            "live package dispatch",
            "model/agent/chat launch",
            "tool/plugin execution",
            "external account actions",
        ],
        "source_state_summary": _source_state_summary(sources),
        "machine_proof": {
            "source_read_models": [
                _source_record(source, repo_root=repo_root, payload=sources[source.key])
                for source in SOURCE_READ_MODELS
            ],
            "generated_outputs": [
                f"generated/read_models/{JSON_EXPORT_NAME}",
                f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            ],
            "operator_memory_separated_from_proof": True,
            "raw_private_bodies_exported": False,
        },
        "static_validation_expectations": {
            "all_required_threshold_fields_present": True,
            "no_forbidden_authority_introduced": True,
            "operator_memory_separated_from_proof": True,
            "post_security_features_future_gated": True,
            "lane_states_in_vocab": True,
        },
        "sqlite_receipt_status": {
            "recorded_in_this_lane": False,
            "reason": "This threshold contract is read-model/output only; no SQLite mutation is required by the lane.",
        },
        "contract_hash": contract_hash,
        "next_recommended_worker": "Mac Codex to render the threshold map",
        "no_live_authority_statement": "This threshold map is a deterministic pre-security contract only; it does not add live package dispatch, model calls, agents, tools, browser/account access, Repo B execution, cleanup, repair, hidden monitoring, or runtime authority.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    return payload


def format_operator_threshold_map_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Threshold Map Contract v0",
        "",
        "Status:",
        "- Pre-security threshold contract.",
        "- Package previews only; no live model, agent, tool, workflow, browser/account, send/submit/approval, or autonomy authority.",
        "",
        "## Threshold Definition",
        payload["threshold_definition"]["meaning"],
        "",
        "Required before security audit:",
    ]
    for item in payload["threshold_definition"]["required_checklist"]:
        lines.append(f"- `{item['field']}`")
    lines.extend(["", "## Lane Readiness Table"])
    for lane in payload["lane_readiness_table"]:
        lines.append(
            f"- `{lane['lane_id']}`: `{lane['readiness_state']}` / `{lane['resolution_route']}`"
            f" -> {lane['target_world'] or 'helm/proof'} - {lane['safe_next_move']}"
        )
    lines.extend(["", "## Steel Thread 1 - Capital Hilton"])
    cap = payload["first_steel_thread_capital_hilton"]
    lines.append(f"- Readiness: `{cap['current_readiness']}`")
    lines.append(f"- Current phase: `{cap['current_phase']}`")
    lines.append(f"- Intended destiny: `{cap['intended_destiny']}`")
    lines.append(f"- Target world: `{cap['target_world']}`")
    lines.append("- Not currently executable; no Coupa access, credential handling, send/submit, approval, or account flow is allowed before security audit.")
    lines.append("- Missing proof:")
    for item in cap["missing_proof"]:
        lines.append(f"  - {item}")
    lines.append("- Next safe move: capture or point to approved protected proof metadata without execution.")
    lines.extend(["", "## Steel Thread 2 - System Awareness / Discovery"])
    sys_awareness = payload["second_steel_thread_system_awareness_discovery"]
    lines.append(f"- Readiness: `{sys_awareness['current_readiness']}`")
    lines.append("- Terrain posture:")
    for item in sys_awareness["terrain_known"]:
        lines.append(f"  - {item}")
    lines.append("- Operator memory can identify gaps, but it is not proof and does not authorize execution.")
    lines.extend(["", "## Before Security Audit"])
    for item in payload["before_security_audit_vs_after_security_audit"]["before_security_audit_allowed"]:
        lines.append(f"- allowed: {item}")
    for item in payload["before_security_audit_vs_after_security_audit"]["before_security_audit_blocked"]:
        lines.append(f"- blocked: {item}")
    lines.extend(["", "## Package Preview Now vs Live Package Later"])
    package = payload["package_preview_now_vs_live_package_later"]
    lines.append(f"- Package preview now: `{str(package['package_preview_now_allowed']).lower()}`")
    lines.append(f"- Live chat/workbench launch now: `{str(package['live_chat_or_workbench_launch_now']).lower()}`")
    lines.append(f"- Autonomy queue now: `{str(package['autonomy_queue_now']).lower()}`")
    lines.extend(["", "## Cue / Autonomy"])
    cue = payload["cue_autonomy_placement"]
    lines.append(f"- Status: `{cue['status']}`")
    for item in cue["not_created_by_this_contract"]:
        lines.append(f"- not created: {item}")
    lines.extend(["", "## Mission Control Rendering"])
    lines.append("- Show:")
    for item in payload["mission_control_rendering_guidance"]["show_now"]:
        lines.append(f"  - {item}")
    lines.append("- Hide/collapse:")
    for item in payload["mission_control_rendering_guidance"]["hide_or_collapse_now"]:
        lines.append(f"  - {item}")
    lines.append("- Do not show before security:")
    for item in payload["mission_control_rendering_guidance"]["never_show_pre_security"]:
        lines.append(f"  - {item}")
    lines.extend(["", "## Lane Destiny / Helm-To-World Transition"])
    transition = payload["helm_to_world_transition_rule"]
    lines.append("- Helm shows:")
    for item in transition["helm_shows"]:
        lines.append(f"  - {item}")
    lines.append("- Worlds show:")
    for item in transition["worlds_show"]:
        lines.append(f"  - {item}")
    lines.append(f"- After lane moves to world: {transition['after_lane_moves_to_world']}")
    lines.append(f"- Backend-only resolved issues: {transition['backend_only_after_verified_completion']}")
    lines.extend(["", "## Check Transmission Source-Truth Note"])
    note = payload["check_transmission_source_truth_note"]
    lines.append(
        f"- sync_health trusted/current: `{str(note['canonical_sync_health_status']['trusted_current']).lower()}`"
    )
    lines.append(
        f"- system health taxonomy Check Transmission status: `{note['system_health_taxonomy_check_transmission_status']}`"
    )
    lines.append(
        f"- source-truth conflict detected in read-models: `{str(note['source_truth_conflict_detected_in_read_models']).lower()}`"
    )
    lines.append(f"- App-visible interpretation: {note['app_visible_interpretation']}")
    lines.extend(["", "## What Makes The Helm Quiet"])
    for item in payload["what_makes_the_helm_quiet"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Boundary",
            "- No live model calls, agent activation, planner/builder execution, Repo B mutation, unauthorized Repo B body inspection, Mission Control app code changes, credentials, network/API calls, browser/OAuth/account integrations, Gmail/calendar/Coupa/Telegram actions, send/submit/approval actions, delete/move/cleanup/remount/repair authority, PC system-drive artifact writes, hidden monitoring, or authority escalation.",
            "",
            "## Next Recommended Worker",
            f"- {payload['next_recommended_worker']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_threshold_map_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorThresholdMapExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_operator_threshold_map_contract(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_threshold_map_contract(payload), encoding="utf-8")
    return OperatorThresholdMapExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path, repo_root=root),
        operator_path=_display_path(operator_path, repo_root=root),
        lane_count=payload["lane_count"],
        ready_for_security_audit_count=len(
            payload["lane_ids_by_readiness_state"].get("READY_FOR_SECURITY_AUDIT", [])
        ),
        blocked_or_unknown_count=len(
            payload["lane_ids_by_readiness_state"].get("BLOCKED_NOT_AUTHORIZED", [])
        )
        + len(payload["lane_ids_by_readiness_state"].get("UNKNOWN_FAIL_CLOSED", [])),
        package_preview_only=payload["package_preview_only"],
        runtime_authority_added=payload["runtime_authority_added"],
        pc_c_drive_artifact_written=payload["pc_c_drive_artifact_written"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Threshold Map Contract read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_threshold_map_contract(
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
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "THRESHOLD_STATES",
    "build_operator_threshold_map_contract",
    "export_operator_threshold_map_contract",
    "format_operator_threshold_map_contract",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
