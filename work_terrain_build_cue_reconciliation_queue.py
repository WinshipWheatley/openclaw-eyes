"""OpenClaw Work Terrain Build Cue / Reconciliation Queue v0.

This read-model defines candidate lanes, prompts, and priorities for turning
work terrain gaps into actionable execution. It is planning/read-model only:
it does not auto-build, auto-prompt, mutate files, refresh the stable map,
or grant live authority.
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

SCHEMA_VERSION = "work_terrain_build_cue_reconciliation_queue_v0"
READ_MODEL_ID = "work_terrain_build_cue_reconciliation_queue"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

QUERY_CONTRACT_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_query_contract.json"
RELATIONSHIP_INDEX_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_relationship_index.json"
CLASSIFICATION_CANDIDATE_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_classification_candidate.json"
GAP_DETECTOR_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_gap_detector.json"

CANDIDATE_TYPES = (
    "DOCTRINE_ONLY_BUILD_CANDIDATE",
    "PARTLY_BUILT_COMPLETION_CANDIDATE",
    "BUILT_NOT_SURFACED_CANDIDATE",
    "BUILT_MISSING_TESTS_CANDIDATE",
    "BUILT_MISSING_STABLE_MAP_CANDIDATE",
    "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT",
    "BUILT_ARTIFACT_LACKS_SOURCE_NOTE",
    "SOURCE_NOTE_LACKS_BUILT_ARTIFACT",
    "RELATIONSHIP_NEEDS_ENCODING",
    "SUPERSESSION_RECONCILIATION_CANDIDATE",
    "MISSION_CONTROL_SURFACE_CANDIDATE",
    "BELOW_DECK_ONLY_CANDIDATE",
    "PARKED_REVISIT_CANDIDATE",
    "QUARANTINE_REVIEW_CANDIDATE",
    "UNKNOWN_FAIL_CLOSED",
)

IMPLEMENTATION_STATUSES = (
    "DOCTRINE_ONLY",
    "PARTLY_BUILT",
    "IMPLEMENTED_CONTRACT",
    "IMPLEMENTED_TESTED",
    "IMPLEMENTED_STABLE_MAP_SURFACED",
    "IMPLEMENTED_MISSION_CONTROL_SURFACED",
    "BUILT_BUT_UNSAFE",
    "BUILT_BUT_UNWIRED",
    "SUPERSEDED",
    "STALE",
    "PARKED",
    "UNKNOWN_FAIL_CLOSED",
)

RECOMMENDED_PRIORITIES = (
    "BUILD_NOW",
    "BUILD_NEXT",
    "REVIEW_WITH_HERMES",
    "RECONCILE_WITH_CHIEF",
    "PARK_FOR_LATER",
    "BELOW_DECK_ONLY",
    "QUARANTINE_OR_SECURITY_REVIEW",
    "DO_NOT_BUILD_STALE",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
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
    "raw_body_ingestion_allowed": False,
}


@dataclass(frozen=True)
class WorkTerrainBuildCueCandidate:
    build_cue_id: str
    title: str
    source_idea_refs: tuple[str, ...]
    source_terrain_refs: tuple[str, ...]
    related_artifact_refs: tuple[str, ...]
    related_contract_refs: tuple[str, ...]
    related_read_model_refs: tuple[str, ...]
    related_test_refs: tuple[str, ...]
    related_stable_map_refs: tuple[str, ...]
    candidate_type: str
    implementation_status: str
    why_it_matters: str
    current_gap: str
    missing_pieces: tuple[str, ...]
    recommended_worker: str
    recommended_lane: str
    recommended_prompt_shape: str
    safety_boundary: str
    acceptance_test: str
    operator_decision_needed: bool
    ready_to_build: bool
    blocked_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainBuildCueQueue:
    queue_id: str
    queue_scope: str
    candidate_refs: tuple[str, ...]
    priority_order: tuple[str, ...]
    included_worlds: tuple[str, ...]
    included_lanes: tuple[str, ...]
    excluded_lanes: tuple[str, ...]
    stale_candidate_policy: str
    supersession_policy: str
    safety_filter_policy: str
    ready_to_build_count: int
    blocked_count: int
    parked_count: int
    below_deck_count: int
    next_recommended_candidate: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainBuildCuePriorityAssessment:
    priority_id: str
    build_cue_ref: str
    operator_value: str
    implementation_readiness: str
    dependency_clarity: str
    safety_risk: str
    scope_size: str
    staleness_risk: str
    reuse_potential: str
    current_mission_relevance: str
    recommended_priority: str
    priority_reason: str
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


def default_cue_candidates() -> tuple[WorkTerrainBuildCueCandidate, ...]:
    return (
        WorkTerrainBuildCueCandidate(
            build_cue_id="packet_compiler_relationship_cue",
            title="Agent Execution Packet Compiler Relationship Cue",
            source_idea_refs=("concept://agent_execution_packet_compiler",),
            source_terrain_refs=("agent_execution_packet_compiler_contract.py",),
            related_artifact_refs=("generated/read_models/agent_execution_packet_compiler_contract.json",),
            related_contract_refs=("agent_execution_packet_compiler_contract.py",),
            related_read_model_refs=("generated/read_models/agent_execution_packet_compiler_contract.json",),
            related_test_refs=("tests/test_agent_execution_packet_compiler_contract.py",),
            related_stable_map_refs=("stable_map.agent_execution_packet_compiler",),
            candidate_type="RELATIONSHIP_NEEDS_ENCODING",
            implementation_status="IMPLEMENTED_TESTED",
            why_it_matters="Ensures the relationship between the packet compiler and context selection is strictly represented.",
            current_gap="Structured upstream-substrate relationship not explicitly marked in relationship index.",
            missing_pieces=("relationship_record_in_relationship_index",),
            recommended_worker="PC Codex",
            recommended_lane="work_terrain_relationship_index",
            recommended_prompt_shape="Include RELATIONSHIP_NEEDS_ENCODING entry for packet compiler to context selection.",
            safety_boundary="No runtime action; support/read-model only.",
            acceptance_test="tests/test_openclaw_work_terrain_relationship_index.py",
            operator_decision_needed=False,
            ready_to_build=True,
            blocked_reason="",
            next_safe_move="Reconcile with Chief and Hermes, then add relationship record.",
        ),
        WorkTerrainBuildCueCandidate(
            build_cue_id="operator_question_assist_cue",
            title="Operator Question Assist / Scope Expansion Cue",
            source_idea_refs=("concept://operator_question_assist",),
            source_terrain_refs=(),
            related_artifact_refs=(),
            related_contract_refs=(),
            related_read_model_refs=(),
            related_test_refs=(),
            related_stable_map_refs=(),
            candidate_type="DOCTRINE_ONLY_BUILD_CANDIDATE",
            implementation_status="DOCTRINE_ONLY",
            why_it_matters="Winship wants smart help that expands scope and helps answer unfamiliar questions safely.",
            current_gap="High-level idea exists in notes but no implementation contract or mock exists.",
            missing_pieces=("operator_question_assist_contract.py", "tests/test_operator_question_assist.py"),
            recommended_worker="Agy",
            recommended_lane="operator_question_assist_lane_v0",
            recommended_prompt_shape="Build read-model contract modeling question assistance pathways.",
            safety_boundary="No live LLM calls, read-only scaffolding only.",
            acceptance_test="tests/test_operator_question_assist.py",
            operator_decision_needed=True,
            ready_to_build=False,
            blocked_reason="Requires operator scope confirmation before drafting contract.",
            next_safe_move="Present design choices to operator before building.",
        ),
        WorkTerrainBuildCueCandidate(
            build_cue_id="capital_hilton_capture_rail_cue",
            title="Capital Hilton Capture Rail Cue",
            source_idea_refs=("concept://capital_hilton_capture_rail",),
            source_terrain_refs=("capital_hilton_protected_proof_intake.py",),
            related_artifact_refs=(),
            related_contract_refs=("capital_hilton_protected_proof_intake.py",),
            related_read_model_refs=("generated/read_models/capital_hilton_protected_proof_intake.json",),
            related_test_refs=("tests/test_capital_hilton_protected_proof_intake.py",),
            related_stable_map_refs=("stable_map.capital_hilton_protected_proof_intake",),
            candidate_type="PARTLY_BUILT_COMPLETION_CANDIDATE",
            implementation_status="PARTLY_BUILT",
            why_it_matters="Connects the manual capture UI to backend proof metadata rails.",
            current_gap="Capture metadata forms exist but no backend guided capture writer contract exists.",
            missing_pieces=("capital_hilton_capture_rail_contract.py",),
            recommended_worker="PC Codex",
            recommended_lane="capital_hilton_capture_rail",
            recommended_prompt_shape="Build guided capture backend contract that updates proof receipts.",
            safety_boundary="Strictly no invoice transmission, local proof receipt writing only.",
            acceptance_test="tests/test_capital_hilton_capture_rail.py",
            operator_decision_needed=False,
            ready_to_build=True,
            blocked_reason="",
            next_safe_move="Implement safe guided capture writer contract.",
        ),
        WorkTerrainBuildCueCandidate(
            build_cue_id="starship_operating_model_cue",
            title="Starship Operating Model Stable-Map Cue",
            source_idea_refs=("concept://starship_operating_model",),
            source_terrain_refs=("operator_work_mode_schema_bandwidth_policy.py",),
            related_artifact_refs=("generated/read_models/operator_work_mode_schema_bandwidth_policy.json",),
            related_contract_refs=("operator_work_mode_schema_bandwidth_policy.py",),
            related_read_model_refs=("generated/read_models/operator_work_mode_schema_bandwidth_policy.json",),
            related_test_refs=("tests/test_operator_work_mode_schema_bandwidth_policy.py",),
            related_stable_map_refs=(),
            candidate_type="BUILT_MISSING_STABLE_MAP_CANDIDATE",
            implementation_status="IMPLEMENTED_TESTED",
            why_it_matters="Integrates Starship commands (Bridge, Worlds, Below Deck) into the dynamic stable-map mapping.",
            current_gap="Contracts and tests exist but stable-map representation is missing.",
            missing_pieces=("stable_map_section_definition",),
            recommended_worker="PC Codex",
            recommended_lane="integrated_stable_map_refresh",
            recommended_prompt_shape="Incorporate operator_work_mode_schema_bandwidth_policy into stable-map.",
            safety_boundary="No UI rendering until import/sync cycle.",
            acceptance_test="tests/test_sync_health.py",
            operator_decision_needed=False,
            ready_to_build=True,
            blocked_reason="",
            next_safe_move="Add stable-map definition and run stable-map refresh in final prompt.",
        ),
        WorkTerrainBuildCueCandidate(
            build_cue_id="screenshot_harness_accessibility_cue",
            title="Screenshot Harness / Accessibility Cue",
            source_idea_refs=("concept://screenshot_harness_accessibility",),
            source_terrain_refs=(),
            related_artifact_refs=(),
            related_contract_refs=(),
            related_read_model_refs=(),
            related_test_refs=(),
            related_stable_map_refs=(),
            candidate_type="PARKED_REVISIT_CANDIDATE",
            implementation_status="PARKED",
            why_it_matters="Leverages Mac accessibility IDs to perform screenshot verification.",
            current_gap="Accessibility IDs exist in Mac repo but are uncommitted and unlinked in PC repo.",
            missing_pieces=("mac_accessibility_bridge_contract.py",),
            recommended_worker="Agy",
            recommended_lane="screenshot_harness_accessibility_integration",
            recommended_prompt_shape="Park this cue until the Mac sync import layer is fully implemented.",
            safety_boundary="Do not mutate Mac code or execute arbitrary screenshots.",
            acceptance_test="tests/test_mac_mirror_atlas.py",
            operator_decision_needed=True,
            ready_to_build=False,
            blocked_reason="Requires active Mac sync/import layer which is currently blocked.",
            next_safe_move="Revisit after Mac-import layer is approved.",
        ),
    )


def default_cue_queue() -> WorkTerrainBuildCueQueue:
    return WorkTerrainBuildCueQueue(
        queue_id="reconciliation_queue_v0",
        queue_scope="openclaw_work_terrain_reconciliation",
        candidate_refs=(
            "packet_compiler_relationship_cue",
            "operator_question_assist_cue",
            "capital_hilton_capture_rail_cue",
            "starship_operating_model_cue",
            "screenshot_harness_accessibility_cue",
        ),
        priority_order=(
            "packet_compiler_relationship_cue",
            "starship_operating_model_cue",
            "capital_hilton_capture_rail_cue",
            "operator_question_assist_cue",
            "screenshot_harness_accessibility_cue",
        ),
        included_worlds=("Finance", "Build", "Operations", "Security"),
        included_lanes=("work_terrain_query_contract", "work_terrain_relationship_index", "work_terrain_classification_staleness_candidate"),
        excluded_lanes=(),
        stale_candidate_policy="Filter stale prompts from active queue; log them in historical logs only.",
        supersession_policy="Ensure old docs remain traceable but keep them out of active build priority.",
        safety_filter_policy="Strict safety gating: unsafe or unauthorized candidates are placed in quarantine.",
        ready_to_build_count=3,
        blocked_count=2,
        parked_count=1,
        below_deck_count=1,
        next_recommended_candidate="packet_compiler_relationship_cue",
        next_safe_move="Review priorities with Hermes and Chief before committing to prompts.",
    )


def default_priorities() -> tuple[WorkTerrainBuildCuePriorityAssessment, ...]:
    return (
        WorkTerrainBuildCuePriorityAssessment(
            priority_id="priority_packet_compiler_relationship",
            build_cue_ref="packet_compiler_relationship_cue",
            operator_value="High",
            implementation_readiness="Ready",
            dependency_clarity="High",
            safety_risk="Low",
            scope_size="Small",
            staleness_risk="Low",
            reuse_potential="Medium",
            current_mission_relevance="High",
            recommended_priority="BUILD_NOW",
            priority_reason="Easy, low-risk gap that properly structures compiler relationship.",
            next_safe_move="Reconcile with Chief, then add relationship index entry.",
        ),
        WorkTerrainBuildCuePriorityAssessment(
            priority_id="priority_operator_question_assist",
            build_cue_ref="operator_question_assist_cue",
            operator_value="High",
            implementation_readiness="Premature",
            dependency_clarity="Low",
            safety_risk="High",
            scope_size="Large",
            staleness_risk="Low",
            reuse_potential="High",
            current_mission_relevance="Medium",
            recommended_priority="REVIEW_WITH_HERMES",
            priority_reason="Unconstrained question assistance is high safety risk; needs Hermes review.",
            next_safe_move="Resolve design scope with operator before implementing.",
        ),
        WorkTerrainBuildCuePriorityAssessment(
            priority_id="priority_capital_hilton_capture_rail",
            build_cue_ref="capital_hilton_capture_rail_cue",
            operator_value="High",
            implementation_readiness="Ready",
            dependency_clarity="High",
            safety_risk="Medium",
            scope_size="Medium",
            staleness_risk="Low",
            reuse_potential="High",
            current_mission_relevance="High",
            recommended_priority="BUILD_NOW",
            priority_reason="Directly supports active Finance lane and proof quiting.",
            next_safe_move="Implement capture rail contract.",
        ),
        WorkTerrainBuildCuePriorityAssessment(
            priority_id="priority_starship_operating_model",
            build_cue_ref="starship_operating_model_cue",
            operator_value="High",
            implementation_readiness="Ready",
            dependency_clarity="High",
            safety_risk="Low",
            scope_size="Small",
            staleness_risk="Low",
            reuse_potential="High",
            current_mission_relevance="High",
            recommended_priority="BUILD_NOW",
            priority_reason="Clean, implemented contract that needs simple stable-map registration.",
            next_safe_move="Add stable-map definition and run refresh.",
        ),
        WorkTerrainBuildCuePriorityAssessment(
            priority_id="priority_screenshot_harness_accessibility",
            build_cue_ref="screenshot_harness_accessibility_cue",
            operator_value="Medium",
            implementation_readiness="Blocked",
            dependency_clarity="Low",
            safety_risk="High",
            scope_size="Medium",
            staleness_risk="Low",
            reuse_potential="High",
            current_mission_relevance="Low",
            recommended_priority="PARK_FOR_LATER",
            priority_reason="Requires active Mac integration layer which remains blocked.",
            next_safe_move="Revisit after Mac sync is approved.",
        ),
    )


def build_work_terrain_build_cue_reconciliation_queue(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidates = default_cue_candidates()
    queue = default_cue_queue()
    priorities = default_priorities()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "metadata_only_build_cue_reconciliation_queue_contract",
        "core_doctrine": {
            "terrain_records_broadly": True,
            "bodies_selectively": True,
            "truth_only_through_receipts": True,
            "candidates_do_not_execute_work": True,
            "candidates_do_not_mutate_files": True,
            "candidates_do_not_promote_doctrine": True,
            "candidates_produce_recommendations_only": True,
            "operator_final_authority": True,
            "stale_superseded_cues_not_build_now": True,
            "unsafe_cues_route_to_quarantine_or_review": True,
        },
        "build_cue_candidate_model": {
            "model_name": "WorkTerrainBuildCueCandidate",
            "fields": [
                "build_cue_id",
                "title",
                "source_idea_refs",
                "source_terrain_refs",
                "related_artifact_refs",
                "related_contract_refs",
                "related_read_model_refs",
                "related_test_refs",
                "related_stable_map_refs",
                "candidate_type",
                "implementation_status",
                "why_it_matters",
                "current_gap",
                "missing_pieces",
                "recommended_worker",
                "recommended_lane",
                "recommended_prompt_shape",
                "safety_boundary",
                "acceptance_test",
                "operator_decision_needed",
                "ready_to_build",
                "blocked_reason",
                "next_safe_move",
            ],
            "candidate_types": list(CANDIDATE_TYPES),
            "implementation_statuses": list(IMPLEMENTATION_STATUSES),
        },
        "build_cue_queue_model": {
            "model_name": "WorkTerrainBuildCueQueue",
            "fields": [
                "queue_id",
                "queue_scope",
                "candidate_refs",
                "priority_order",
                "included_worlds",
                "included_lanes",
                "excluded_lanes",
                "stale_candidate_policy",
                "supersession_policy",
                "safety_filter_policy",
                "ready_to_build_count",
                "blocked_count",
                "parked_count",
                "below_deck_count",
                "next_recommended_candidate",
                "next_safe_move",
            ],
        },
        "priority_assessment_model": {
            "model_name": "WorkTerrainBuildCuePriorityAssessment",
            "fields": [
                "priority_id",
                "build_cue_ref",
                "operator_value",
                "implementation_readiness",
                "dependency_clarity",
                "safety_risk",
                "scope_size",
                "staleness_risk",
                "reuse_potential",
                "current_mission_relevance",
                "recommended_priority",
                "priority_reason",
                "next_safe_move",
            ],
            "recommended_priorities": list(RECOMMENDED_PRIORITIES),
        },
        "default_candidates": [asdict(c) for c in candidates],
        "default_queue": asdict(queue),
        "default_priorities": [asdict(p) for p in priorities],
        "relationship_to_prior_lanes": {
            "openclaw_work_terrain_query_contract": {
                "read_model_ref": QUERY_CONTRACT_READ_MODEL_REF,
                "relationship": "Query contract defines search space.",
                "status": _prior_lane_status(repo_root, QUERY_CONTRACT_READ_MODEL_REF),
            },
            "openclaw_work_terrain_relationship_index": {
                "read_model_ref": RELATIONSHIP_INDEX_READ_MODEL_REF,
                "relationship": "Relationship index maps connections.",
                "status": _prior_lane_status(repo_root, RELATIONSHIP_INDEX_READ_MODEL_REF),
            },
            "openclaw_work_terrain_classification_candidate": {
                "read_model_ref": CLASSIFICATION_CANDIDATE_READ_MODEL_REF,
                "relationship": "Classification maps status categories.",
                "status": _prior_lane_status(repo_root, CLASSIFICATION_CANDIDATE_READ_MODEL_REF),
            },
            "openclaw_work_terrain_gap_detector": {
                "read_model_ref": GAP_DETECTOR_READ_MODEL_REF,
                "relationship": "Gap detector points out deficiencies.",
                "status": _prior_lane_status(repo_root, GAP_DETECTOR_READ_MODEL_REF),
            },
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_authority_flags_false": all(v is False for v in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "build_cue_candidate_model_exists": True,
            "build_cue_queue_model_exists": True,
            "priority_assessment_model_exists": True,
            "default_candidate_count": len(candidates),
            "safety_boundaries_all_false": all(v is False for v in AUTHORITY_BOUNDARY.values()),
            "packet_compiler_relationship_cue_represented": any(c.build_cue_id == "packet_compiler_relationship_cue" for c in candidates),
            "operator_question_assist_cue_represented": any(c.build_cue_id == "operator_question_assist_cue" for c in candidates),
            "capital_hilton_capture_rail_cue_represented": any(c.build_cue_id == "capital_hilton_capture_rail_cue" for c in candidates),
            "starship_operating_model_cue_represented": any(c.build_cue_id == "starship_operating_model_cue" for c in candidates),
            "screenshot_harness_accessibility_cue_represented": any(c.build_cue_id == "screenshot_harness_accessibility_cue" for c in candidates),
            "no_live_execution": True,
            "no_credentials": True,
            "no_raw_body_ingestion": True,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_work_terrain_build_cue_reconciliation_queue(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Work Terrain Build Cue / Reconciliation Queue v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This read-model converts Work Terrain gaps into structured candidates for active development or reconciliation.",
        "It prevents good ideas from floating in chat doctrine and solves the '1000 good ideas where nothing lands' problem.",
        "It is strictly planning/read-model only: no automatic building, file mutation, or active execution is allowed.",
        "",
        "## Default Candidates",
        "",
    ]
    for c in payload["default_candidates"]:
        lines.append(f"- **{c['title']}**: `{c['candidate_type']}` ({c['implementation_status']})")
        lines.append(f"  - *Why it matters*: {c['why_it_matters']}")
        lines.append(f"  - *Next Safe Move*: {c['next_safe_move']}")

    lines.extend(
        [
            "",
            "## Queue Definition",
            "",
            f"- Queue ID: `{payload['default_queue']['queue_id']}`",
            f"- Priority Order: " + ", ".join(payload["default_queue"]["priority_order"]),
            f"- Stale Candidate Policy: {payload['default_queue']['stale_candidate_policy']}",
            f"- Supersession Policy: {payload['default_queue']['supersession_policy']}",
            f"- Safety Filter Policy: {payload['default_queue']['safety_filter_policy']}",
            "",
            "## Safety and Authority Boundaries",
            "",
            "- All auto-build and auto-dispatch flags are strictly disabled (`false`).",
            "- No file mutations, stable-map promotions, or active tool/agent executions are permitted here.",
            "- The operator remains the final sovereign authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_work_terrain_build_cue_reconciliation_queue(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_work_terrain_build_cue_reconciliation_queue(
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
    operator_path.write_text(format_work_terrain_build_cue_reconciliation_queue(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export OpenClaw Build Cue Reconciliation Queue Contract.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    payload = export_work_terrain_build_cue_reconciliation_queue(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format in {"summary", "json"}:
        summary = {
            "schema_version": payload["schema_version"],
            "json_path": (Path(args.export_root) / JSON_EXPORT_NAME).as_posix(),
            "operator_path": (Path(args.export_root) / OPERATOR_EXPORT_NAME).as_posix(),
            "candidate_count": len(payload["default_candidates"]),
            "ready_to_build_count": payload["default_queue"]["ready_to_build_count"],
        }
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Build Cue Reconciliation Queue exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
