"""OpenClaw Work Terrain Surface Map / Build Cue Scout v0.

This read-model implements a shallow, metadata-only surface mapping pass over
OpenClaw terrain. It groups files into logical clusters and recommends scoped,
safe deep dives. It is strictly planning/read-model only: no automatic building,
broad body ingestion, or active execution is allowed.
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

SCHEMA_VERSION = "work_terrain_surface_map_build_cue_scout_v0"
READ_MODEL_ID = "work_terrain_surface_map_build_cue_scout"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

QUERY_CONTRACT_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_query_contract.json"
RELATIONSHIP_INDEX_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_relationship_index.json"
CLASSIFICATION_CANDIDATE_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_classification_candidate.json"
GAP_DETECTOR_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_gap_detector.json"

ARTIFACT_TYPES = (
    "CONTRACT_CODE",
    "EXPORT_SCRIPT",
    "TEST_FILE",
    "GENERATED_READ_MODEL",
    "OPERATOR_MARKDOWN",
    "STABLE_MAP_SECTION",
    "SOURCE_NOTE",
    "OLD_PROMPT",
    "HANDOFF",
    "WORKER_REPORT",
    "APP_SURFACE",
    "VALIDATION_SCREENSHOT_METADATA",
    "SHUTTLE_ARTIFACT",
    "REFERENCE_REPO_ARTIFACT",
    "UNKNOWN_FAIL_CLOSED",
)

IMPLEMENTATION_HINTS = (
    "IMPLEMENTED_CONTRACT",
    "IMPLEMENTED_TESTED",
    "IMPLEMENTED_READ_MODEL",
    "IMPLEMENTED_STABLE_MAP_SURFACED",
    "IMPLEMENTED_APP_SURFACED",
    "PARTLY_BUILT",
    "DOCTRINE_ONLY",
    "OLD_PROMPT",
    "REFERENCE_ONLY",
    "STALE_OR_SUPERSEDED",
    "PARKED",
    "UNKNOWN_FAIL_CLOSED",
)

CLUSTER_TYPES = (
    "CONCEPT_CLUSTER",
    "IMPLEMENTATION_CLUSTER",
    "STALE_PROMPT_CLUSTER",
    "BUILT_NOT_SURFACED_CLUSTER",
    "DOCTRINE_ONLY_CLUSTER",
    "AGENT_WORKFLOW_CLUSTER",
    "UI_SURFACE_CLUSTER",
    "SECURITY_GOVERNANCE_CLUSTER",
    "WORK_TERRAIN_CLUSTER",
    "UNKNOWN_FAIL_CLOSED",
)

CANDIDATE_KINDS = (
    "BUILD_CUE_READY",
    "DEEP_DIVE_FIRST",
    "PARK_FOR_LATER",
    "RELATIONSHIP_NEEDS_ENCODING",
    "STABLE_MAP_SURFACE_CANDIDATE",
    "MISSION_CONTROL_SURFACE_CANDIDATE",
    "TEST_CHECKPOINT_CANDIDATE",
    "DO_NOT_BUILD_STALE",
    "QUARANTINE_REVIEW",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "deep_scan_allowed": False,
    "raw_body_ingestion_allowed": False,
    "auto_build_allowed": False,
    "auto_prompt_dispatch_allowed": False,
    "file_mutation_allowed": False,
    "archive_allowed": False,
    "doctrine_promotion_allowed": False,
    "stable_map_promotion_allowed": False,
    "mission_control_ui_change_allowed": False,
    "receipt_write_allowed": False,
    "state_write_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "network_allowed": False,
}


@dataclass(frozen=True)
class WorkTerrainSurfaceRecord:
    terrain_record_id: str
    title: str
    path_or_ref: str
    source_area: str
    artifact_type: str
    likely_world: str
    likely_lane: str
    likely_actor: str
    freshness_hint: str
    implementation_hint: str
    relationship_hint: str
    confidence: str
    body_not_ingested: bool
    safe_for_deep_dive_candidate: bool
    blocked_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainSurfaceCluster:
    cluster_id: str
    cluster_title: str
    cluster_type: str
    related_record_refs: tuple[str, ...]
    likely_theme: str
    likely_world: str
    likely_lane: str
    status_summary: str
    pattern_observed: str
    possible_gap: str
    recommended_next_action: str
    deep_dive_candidate: str
    build_cue_candidate: str
    safety_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainDeepDiveCandidate:
    deep_dive_id: str
    source_cluster_ref: str
    why_dive_matters: str
    questions_to_answer: tuple[str, ...]
    allowed_scope: str
    forbidden_scope: str
    expected_outputs: tuple[str, ...]
    recommended_worker: str
    estimated_risk: str
    operator_decision_needed: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainBuildCueScoutRecommendation:
    scout_recommendation_id: str
    source_cluster_ref: str
    candidate_title: str
    candidate_kind: str
    current_evidence_refs: tuple[str, ...]
    likely_missing_piece: str
    recommended_lane: str
    recommended_worker: str
    recommended_prompt_shape: str
    ready_for_build_cue_queue: bool
    needs_deep_dive_first: bool
    safety_boundary: str
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _prior_lane_status(repo_root: str | Path, ref: str) -> str:
    return "OBSERVED" if (Path(repo_root) / ref).is_file() else "NOT_OBSERVED_OR_PENDING"


def default_surface_records() -> tuple[WorkTerrainSurfaceRecord, ...]:
    return (
        WorkTerrainSurfaceRecord(
            terrain_record_id="workflow_block_intent_contract",
            title="Workflow Block Intent Live Draft Contract",
            path_or_ref="workflow_block_intent_live_draft_contract.py",
            source_area="Repo A canonical",
            artifact_type="CONTRACT_CODE",
            likely_world="Operations",
            likely_lane="agent_execution_packet",
            likely_actor="Codex",
            freshness_hint="Current",
            implementation_hint="IMPLEMENTED_CONTRACT",
            relationship_hint="describes workflow session block intent",
            confidence="high",
            body_not_ingested=True,
            safe_for_deep_dive_candidate=True,
            blocked_reason="",
            next_safe_move="Expose in surface map and group in packet cluster.",
        ),
        WorkTerrainSurfaceRecord(
            terrain_record_id="operator_question_assist_note",
            title="Operator Question Assist / Scope Expansion Note",
            path_or_ref="source_concept://operator_question_assist",
            source_area="doctrine only",
            artifact_type="SOURCE_NOTE",
            likely_world="Operations",
            likely_lane="operator_attention_promotion",
            likely_actor="Operator / Winship",
            freshness_hint="Active",
            implementation_hint="DOCTRINE_ONLY",
            relationship_hint="unimplemented operator help scope expansion",
            confidence="medium",
            body_not_ingested=True,
            safe_for_deep_dive_candidate=True,
            blocked_reason="",
            next_safe_move="Reconcile as doctrine-only build cue candidate.",
        ),
        WorkTerrainSurfaceRecord(
            terrain_record_id="capital_hilton_protected_proof_intake_contract",
            title="Capital Hilton Protected Proof Intake",
            path_or_ref="capital_hilton_protected_proof_intake.py",
            source_area="Repo A canonical",
            artifact_type="CONTRACT_CODE",
            likely_world="Finance",
            likely_lane="capital_hilton_proof_intake",
            likely_actor="Cassandra",
            freshness_hint="Current",
            implementation_hint="IMPLEMENTED_TESTED",
            relationship_hint="models missing dates and proof gaps",
            confidence="high",
            body_not_ingested=True,
            safe_for_deep_dive_candidate=True,
            blocked_reason="",
            next_safe_move="Expose in Hilton steel thread cluster.",
        ),
        WorkTerrainSurfaceRecord(
            terrain_record_id="starship_operating_model_contract",
            title="Starship Operating Model Contract",
            path_or_ref="operator_work_mode_schema_bandwidth_policy.py",
            source_area="Repo A canonical",
            artifact_type="CONTRACT_CODE",
            likely_world="Operations",
            likely_lane="operator_work_mode",
            likely_actor="Chief",
            freshness_hint="Current",
            implementation_hint="IMPLEMENTED_TESTED",
            relationship_hint="models bridge, helm, worlds and below deck structure",
            confidence="high",
            body_not_ingested=True,
            safe_for_deep_dive_candidate=True,
            blocked_reason="",
            next_safe_move="Expose in starship command cluster.",
        ),
        WorkTerrainSurfaceRecord(
            terrain_record_id="screenshot_harness_accessibility_harness",
            title="Screenshot Harness / Accessibility Harness Note",
            path_or_ref="concept://screenshot_harness_accessibility",
            source_area="external/Mac workspace",
            artifact_type="OLD_PROMPT",
            likely_world="Operations",
            likely_lane="mac_sync_import",
            likely_actor="Hermes",
            freshness_hint="Stale",
            implementation_hint="PARKED",
            relationship_hint="contains accessibility IDs and screenshot script outside PC",
            confidence="medium",
            body_not_ingested=True,
            safe_for_deep_dive_candidate=False,
            blocked_reason="Active Mac integration remains unapproved.",
            next_safe_move="Track as external reference only.",
        ),
    )


def default_surface_clusters() -> tuple[WorkTerrainSurfaceCluster, ...]:
    return (
        WorkTerrainSurfaceCluster(
            cluster_id="workflow_packet_cluster",
            cluster_title="Workflow Block / Agent Packet Cluster",
            cluster_type="AGENT_WORKFLOW_CLUSTER",
            related_record_refs=("workflow_block_intent_contract",),
            likely_theme="Agent and workflow packet rails are forming",
            likely_world="Operations",
            likely_lane="agent_execution_packet",
            status_summary="Contracts exist, but upstream relationship to compiler needs structured mapping.",
            pattern_observed="Agent handoff, routing, and block intent contracts are forming a clear execution framework.",
            possible_gap="Upstream context compiler relationship not explicitly mapped.",
            recommended_next_action="Reconcile with Chief and Hermes, then add index entry.",
            deep_dive_candidate="none_required",
            build_cue_candidate="packet_compiler_relationship_cue",
            safety_boundary="No live execution, read-model index only.",
            next_safe_move="Expose as RELATIONSHIP_NEEDS_ENCODING scout recommendation.",
        ),
        WorkTerrainSurfaceCluster(
            cluster_id="operator_question_assist_cluster",
            cluster_title="Operator Question Assist / Scope Expansion Cluster",
            cluster_type="DOCTRINE_ONLY_CLUSTER",
            related_record_refs=("operator_question_assist_note",),
            likely_theme="Doctrine exists in operator notes for scope expansion",
            likely_world="Operations",
            likely_lane="operator_attention_promotion",
            status_summary="High-level idea exists, but no implementation contract exists.",
            pattern_observed="Winship wants smart scope expansion assistance to answer unfamiliar questions.",
            possible_gap="No implementation contract or mock scaffolding.",
            recommended_next_action="Propose future operator question assist contract.",
            deep_dive_candidate="operator_question_assist_dive",
            build_cue_candidate="operator_question_assist_cue",
            safety_boundary="No live LLM calls, read-model schema scaffolding only.",
            next_safe_move="Expose as DEEP_DIVE_FIRST candidate.",
        ),
        WorkTerrainSurfaceCluster(
            cluster_id="capital_hilton_cluster",
            cluster_title="Capital Hilton Steel Thread Cluster",
            cluster_type="IMPLEMENTATION_CLUSTER",
            related_record_refs=("capital_hilton_protected_proof_intake_contract",),
            likely_theme="Mac UI and backend proof metadata alignment",
            likely_world="Finance",
            likely_lane="capital_hilton_proof_intake",
            status_summary="Verification forms exist, but backend capture intent writer contract is missing.",
            pattern_observed="Capital Hilton invoicing and dates blocks are mapped, but guided capture is manual-fallback only.",
            possible_gap="Guided capture rail is missing backend contract.",
            recommended_next_action="Propose Hilton capture rail contract.",
            deep_dive_candidate="none_required",
            build_cue_candidate="capital_hilton_capture_rail_cue",
            safety_boundary="Strictly no invoice transmission, local proof receipt writing only.",
            next_safe_move="Expose as BUILD_CUE_READY.",
        ),
        WorkTerrainSurfaceCluster(
            cluster_id="starship_operating_model_cluster",
            cluster_title="Starship Operating Model Cluster",
            cluster_type="SECURITY_GOVERNANCE_CLUSTER",
            related_record_refs=("starship_operating_model_contract",),
            likely_theme="Bridge, worlds, below deck, and shipyard architecture",
            likely_world="Operations",
            likely_lane="operator_work_mode",
            status_summary="Contracts and tests exist, but stable-map summary is missing.",
            pattern_observed=" Starship operating command model is fully validated in code, but app routing is unmapped.",
            possible_gap="Stable-map representation is missing.",
            recommended_next_action="Add stable-map definition and run refresh in final prompt.",
            deep_dive_candidate="none_required",
            build_cue_candidate="starship_operating_model_cue",
            safety_boundary="No UI rendering until import/sync cycle.",
            next_safe_move="Expose as STABLE_MAP_SURFACE_CANDIDATE.",
        ),
        WorkTerrainSurfaceCluster(
            cluster_id="screenshot_harness_cluster",
            cluster_title="Screenshot Harness / Accessibility Cluster",
            cluster_type="STALE_PROMPT_CLUSTER",
            related_record_refs=("screenshot_harness_accessibility_harness",),
            likely_theme="Mac-side accessibility and screen scraping references",
            likely_world="Operations",
            likely_lane="mac_sync_import",
            status_summary="Accessibility IDs are uncommitted/unlinked outside PC repo.",
            pattern_observed="Mac screenshot code exists but PC has no sync/import approval.",
            possible_gap="Mac sync import layer is currently blocked.",
            recommended_next_action="Track as external reference only; do not mutate Mac.",
            deep_dive_candidate="none_required",
            build_cue_candidate="screenshot_harness_accessibility_cue",
            safety_boundary="Do not mutate Mac code or execute arbitrary screenshots.",
            next_safe_move="Expose as PARK_FOR_LATER.",
        ),
    )


def default_deep_dives() -> tuple[WorkTerrainDeepDiveCandidate, ...]:
    return (
        WorkTerrainDeepDiveCandidate(
            deep_dive_id="operator_question_assist_dive",
            source_cluster_ref="operator_question_assist_cluster",
            why_dive_matters="Winship wants safe, smart scope expansion help. We must define boundaries before writing contracts.",
            questions_to_answer=(
                "What forms can question assistance take safely?",
                "How do we represent scope boundaries inside read-models?",
                "What feedback loops must be built into the command desk?"
            ),
            allowed_scope="Shallow metadata structure modeling of operator helper commands.",
            forbidden_scope="Direct browser-sessions, Coupa credentials, or live LLM dispatch.",
            expected_outputs=("operator_question_assist_contract_draft",),
            recommended_worker="Agy",
            estimated_risk="Medium",
            operator_decision_needed=True,
            next_safe_move="Acquire operator approval for questions allowable under assist contract.",
        ),
    )


def default_recommendations() -> tuple[WorkTerrainBuildCueScoutRecommendation, ...]:
    return (
        WorkTerrainBuildCueScoutRecommendation(
            scout_recommendation_id="rec_packet_compiler_relationship",
            source_cluster_ref="workflow_packet_cluster",
            candidate_title="Agent Execution Packet Compiler Relationship",
            candidate_kind="RELATIONSHIP_NEEDS_ENCODING",
            current_evidence_refs=("workflow_block_intent_live_draft_contract.py",),
            likely_missing_piece="relationship index entry mapping compiler to context selector",
            recommended_lane="work_terrain_relationship_index",
            recommended_worker="PC Codex",
            recommended_prompt_shape="Add RELATIONSHIP_NEEDS_ENCODING record for packet compiler.",
            ready_for_build_cue_queue=True,
            needs_deep_dive_first=False,
            safety_boundary="No active execution, read-model registry entry only.",
            next_safe_move="Include in immediate build queue.",
        ),
        WorkTerrainBuildCueScoutRecommendation(
            scout_recommendation_id="rec_operator_question_assist",
            source_cluster_ref="operator_question_assist_cluster",
            candidate_title="Operator Question Assist / Scope Expansion",
            candidate_kind="DEEP_DIVE_FIRST",
            current_evidence_refs=(),
            likely_missing_piece="operator_question_assist_contract.py",
            recommended_lane="operator_question_assist_lane_v0",
            recommended_worker="Agy",
            recommended_prompt_shape="Build read-model contract modeling question assistance pathways.",
            ready_for_build_cue_queue=False,
            needs_deep_dive_first=True,
            safety_boundary="No live LLM calls, read-only scaffolding only.",
            next_safe_move="Expose in deep dive queue before creating build cue.",
        ),
        WorkTerrainBuildCueScoutRecommendation(
            scout_recommendation_id="rec_capital_hilton_capture_rail",
            source_cluster_ref="capital_hilton_cluster",
            candidate_title="Capital Hilton Capture Rail",
            candidate_kind="BUILD_CUE_READY",
            current_evidence_refs=("capital_hilton_protected_proof_intake.py",),
            likely_missing_piece="capital_hilton_capture_rail_contract.py",
            recommended_lane="capital_hilton_capture_rail",
            recommended_worker="PC Codex",
            recommended_prompt_shape="Build guided capture backend contract that updates proof receipts.",
            ready_for_build_cue_queue=True,
            needs_deep_dive_first=False,
            safety_boundary="Strictly no invoice transmission, local proof receipt writing only.",
            next_safe_move="Include in build cue queue.",
        ),
        WorkTerrainBuildCueScoutRecommendation(
            scout_recommendation_id="rec_starship_operating_model",
            source_cluster_ref="starship_operating_model_cluster",
            candidate_title="Starship Operating Model",
            candidate_kind="STABLE_MAP_SURFACE_CANDIDATE",
            current_evidence_refs=("operator_work_mode_schema_bandwidth_policy.py",),
            likely_missing_piece="stable-map definition and refresh registration",
            recommended_lane="integrated_stable_map_refresh",
            recommended_worker="PC Codex",
            recommended_prompt_shape="Incorporate operator_work_mode_schema_bandwidth_policy into stable-map.",
            ready_for_build_cue_queue=True,
            needs_deep_dive_first=False,
            safety_boundary="No UI rendering until import/sync cycle.",
            next_safe_move="Add stable-map definition in final prompt.",
        ),
        WorkTerrainBuildCueScoutRecommendation(
            scout_recommendation_id="rec_screenshot_harness",
            source_cluster_ref="screenshot_harness_cluster",
            candidate_title="Screenshot Harness / Accessibility",
            candidate_kind="PARK_FOR_LATER",
            current_evidence_refs=(),
            likely_missing_piece="mac_accessibility_bridge_contract.py",
            recommended_lane="screenshot_harness_accessibility_integration",
            recommended_worker="Agy",
            recommended_prompt_shape="Park this cue until the Mac sync import layer is fully implemented.",
            ready_for_build_cue_queue=False,
            needs_deep_dive_first=False,
            safety_boundary="Do not mutate Mac code or execute arbitrary screenshots.",
            next_safe_move="Maintain as parked reference only.",
        ),
    )


def build_work_terrain_surface_map_build_cue_scout(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    records = default_surface_records()
    clusters = default_surface_clusters()
    dives = default_deep_dives()
    recs = default_recommendations()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "metadata_only_surface_map_build_cue_scout_contract",
        "core_doctrine": {
            "surface_map_broadly": True,
            "deep_dive_selectively": True,
            "truth_only_through_receipts": True,
            "build_only_through_explicit_cues": True,
            "records_are_shallow_metadata": True,
            "body_not_ingested_by_default": True,
            "classification_is_candidate_only": True,
            "clusters_identify_patterns_not_truth": True,
            "deep_dives_must_be_scoped": True,
            "no_automatic_build_or_mutation": True,
        },
        "surface_terrain_record_model": {
            "model_name": "WorkTerrainSurfaceRecord",
            "fields": [
                "terrain_record_id",
                "title",
                "path_or_ref",
                "source_area",
                "artifact_type",
                "likely_world",
                "likely_lane",
                "likely_actor",
                "freshness_hint",
                "implementation_hint",
                "relationship_hint",
                "confidence",
                "body_not_ingested",
                "safe_for_deep_dive_candidate",
                "blocked_reason",
                "next_safe_move",
            ],
            "artifact_types": list(ARTIFACT_TYPES),
            "implementation_hints": list(IMPLEMENTATION_HINTS),
        },
        "surface_cluster_model": {
            "model_name": "WorkTerrainSurfaceCluster",
            "fields": [
                "cluster_id",
                "cluster_title",
                "cluster_type",
                "related_record_refs",
                "likely_theme",
                "likely_world",
                "likely_lane",
                "status_summary",
                "pattern_observed",
                "possible_gap",
                "recommended_next_action",
                "deep_dive_candidate",
                "build_cue_candidate",
                "safety_boundary",
                "next_safe_move",
            ],
            "cluster_types": list(CLUSTER_TYPES),
        },
        "deep_dive_candidate_model": {
            "model_name": "WorkTerrainDeepDiveCandidate",
            "fields": [
                "deep_dive_id",
                "source_cluster_ref",
                "why_dive_matters",
                "questions_to_answer",
                "allowed_scope",
                "forbidden_scope",
                "expected_outputs",
                "recommended_worker",
                "estimated_risk",
                "operator_decision_needed",
                "next_safe_move",
            ],
        },
        "build_cue_scout_recommendation_model": {
            "model_name": "WorkTerrainBuildCueScoutRecommendation",
            "fields": [
                "scout_recommendation_id",
                "source_cluster_ref",
                "candidate_title",
                "candidate_kind",
                "current_evidence_refs",
                "likely_missing_piece",
                "recommended_lane",
                "recommended_worker",
                "recommended_prompt_shape",
                "ready_for_build_cue_queue",
                "needs_deep_dive_first",
                "safety_boundary",
                "next_safe_move",
            ],
            "candidate_kinds": list(CANDIDATE_KINDS),
        },
        "default_records": [asdict(r) for r in records],
        "default_clusters": [asdict(c) for c in clusters],
        "default_deep_dives": [asdict(d) for d in dives],
        "default_scout_recommendations": [asdict(rec) for rec in recs],
        "relationship_to_prior_lanes": {
            "openclaw_work_terrain_query_contract": {
                "read_model_ref": QUERY_CONTRACT_READ_MODEL_REF,
                "relationship": "Query contract defines search grammar.",
                "status": _prior_lane_status(repo_root, QUERY_CONTRACT_READ_MODEL_REF),
            },
            "openclaw_work_terrain_relationship_index": {
                "read_model_ref": RELATIONSHIP_INDEX_READ_MODEL_REF,
                "relationship": "Relationship index connects records.",
                "status": _prior_lane_status(repo_root, RELATIONSHIP_INDEX_READ_MODEL_REF),
            },
            "openclaw_work_terrain_classification_candidate": {
                "read_model_ref": CLASSIFICATION_CANDIDATE_READ_MODEL_REF,
                "relationship": "Classification candidates maps statuses.",
                "status": _prior_lane_status(repo_root, CLASSIFICATION_CANDIDATE_READ_MODEL_REF),
            },
            "openclaw_work_terrain_gap_detector": {
                "read_model_ref": GAP_DETECTOR_READ_MODEL_REF,
                "relationship": "Gap detector detects deficiencies.",
                "status": _prior_lane_status(repo_root, GAP_DETECTOR_READ_MODEL_REF),
            },
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_authority_flags_false": all(v is False for v in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "surface_terrain_record_model_exists": True,
            "surface_cluster_model_exists": True,
            "deep_dive_candidate_model_exists": True,
            "build_cue_scout_recommendation_model_exists": True,
            "shallow_first_doctrine_represented": True,
            "default_record_count": len(records),
            "safety_boundaries_all_false": all(v is False for v in AUTHORITY_BOUNDARY.values()),
            "workflow_packet_cluster_represented": any(c.cluster_id == "workflow_packet_cluster" for c in clusters),
            "operator_question_assist_cluster_represented": any(c.cluster_id == "operator_question_assist_cluster" for c in clusters),
            "capital_hilton_cluster_represented": any(c.cluster_id == "capital_hilton_cluster" for c in clusters),
            "starship_operating_model_cluster_represented": any(c.cluster_id == "starship_operating_model_cluster" for c in clusters),
            "screenshot_harness_cluster_represented": any(c.cluster_id == "screenshot_harness_cluster" for c in clusters),
            "no_live_execution": True,
            "no_credentials": True,
            "no_raw_body_ingestion": True,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_work_terrain_surface_map_build_cue_scout(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Work Terrain Surface Map / Build Cue Scout v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This read-model builds a shallow, metadata-only surface mapping over OpenClaw terrain.",
        "It discovers broad patterns, groups files into logical clusters, and defines scoped, safe deep dives.",
        "It prevents unconstrained AI crawls or early action promotion, keeping execution completely read-only.",
        "",
        "## Default Clusters",
        "",
    ]
    for c in payload["default_clusters"]:
        lines.append(f"- **{c['cluster_title']}**: `{c['cluster_type']}`")
        lines.append(f"  - *Pattern observed*: {c['pattern_observed']}")
        lines.append(f"  - *Next Safe Move*: {c['next_safe_move']}")

    lines.extend(
        [
            "",
            "## Deep Dive Candidates",
            "",
        ]
    )
    for d in payload["default_deep_dives"]:
        lines.append(f"- **Dive ID**: `{d['deep_dive_id']}`")
        lines.append(f"  - *Allowed Scope*: {d['allowed_scope']}")
        lines.append(f"  - *Forbidden Scope*: {d['forbidden_scope']}")

    lines.extend(
        [
            "",
            "## Safety and Authority Boundaries",
            "",
            "- All auto-build, deep-scan, and body-ingestion flags are strictly disabled (`false`).",
            "- No file mutations, stable-map promotions, or active tool/agent executions are permitted here.",
            "- The operator remains the final sovereign authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_work_terrain_surface_map_build_cue_scout(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_work_terrain_surface_map_build_cue_scout(
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
    operator_path.write_text(format_work_terrain_surface_map_build_cue_scout(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export OpenClaw Surface Map Build Cue Scout Contract.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    payload = export_work_terrain_surface_map_build_cue_scout(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format in {"summary", "json"}:
        summary = {
            "schema_version": payload["schema_version"],
            "json_path": (Path(args.export_root) / JSON_EXPORT_NAME).as_posix(),
            "operator_path": (Path(args.export_root) / OPERATOR_EXPORT_NAME).as_posix(),
            "record_count": len(payload["default_records"]),
            "cluster_count": len(payload["default_clusters"]),
        }
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Surface Map Build Cue Scout exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
