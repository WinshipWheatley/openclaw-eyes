"""Chief status rail v0.

This read-model completes the smallest safe Chief status rail from existing
Repo A evidence. It summarizes Chief's current proven status posture without
importing Chief runtime modules, activating services, sending notifications,
calling models, inspecting private logs, or granting execution authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from post_preflight_batch_gate import PASS, evaluate_post_preflight_lane


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "chief_status_rail_v0"
JSON_EXPORT_NAME = "chief_status_rail.json"
OPERATOR_EXPORT_NAME = "chief_status_rail_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

DEFAULT_SEGMENTATION_PATH = DEFAULT_EXPORT_ROOT / "chief_role_capability_segmentation_map.json"
DEFAULT_WORK_BOARD_PATH = DEFAULT_EXPORT_ROOT / "work_board.json"
DEFAULT_AGENT_WORK_PACKETS_PATH = DEFAULT_EXPORT_ROOT / "agent_work_packets.json"
DEFAULT_INTENT_ROUTER_PATH = DEFAULT_EXPORT_ROOT / "intent_router.json"
DEFAULT_DROPPED_INTENTS_PATH = DEFAULT_EXPORT_ROOT / "dropped_intents.json"
DEFAULT_FLEET_HEALTH_PATH = DEFAULT_EXPORT_ROOT / "chief_agent_fleet_health.json"

STATUS_CATEGORIES = (
    "proven",
    "partially_represented",
    "inferred_not_proven",
    "operator_memory_only",
    "unsafe_blocked",
    "future_security_threshold",
)

NO_AUTHORITY_FLAGS = {
    "chief_modeled_as_executor": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_execution_authority_added": False,
    "planner_builder_automation_activated": False,
    "repair_fix_loop_activated": False,
    "telegram_send_triggered": False,
    "telegram_notification_live": False,
    "llm_ollama_called": False,
    "llm_ollama_authority_added": False,
    "tool_execution_authority_added": False,
    "browser_or_coupa_authority_added": False,
    "credential_or_pii_access_added": False,
    "gmail_calendar_coupa_credentials_accessed": False,
    "arbitrary_shell_allowed": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "chief_runtime_modules_imported": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "client_deployment_authority_added": False,
    "old_files_treated_as_truth": False,
}


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


SOURCE_READ_MODELS = (
    SourceReadModel("segmentation", str(DEFAULT_SEGMENTATION_PATH), "Chief role/capability segmentation baseline"),
    SourceReadModel("work_board", str(DEFAULT_WORK_BOARD_PATH), "Chief-routed work-board status signals"),
    SourceReadModel("agent_work_packets", str(DEFAULT_AGENT_WORK_PACKETS_PATH), "Chief-routed work packet signals"),
    SourceReadModel("intent_router", str(DEFAULT_INTENT_ROUTER_PATH), "Chief-routed intent signals"),
    SourceReadModel("dropped_intents", str(DEFAULT_DROPPED_INTENTS_PATH), "Deferred/unresolved Chief-adjacent intent signals"),
    SourceReadModel("fleet_health", str(DEFAULT_FLEET_HEALTH_PATH), "Agent fleet health + sync posture + shipped milestones"),
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
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _source_record(source: SourceReadModel, *, repo_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = _rooted(source.path, repo_root=repo_root)
    return {
        "key": source.key,
        "path": source.path,
        "present": path.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": source.role,
        "truth_status": "repo_a_read_model_evidence_not_truth",
        "body_read": False,
        "repo_a_only": True,
    }


def _subareas_by_classification(segmentation: dict[str, Any], classifications: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "sub_area_id": item.get("sub_area_id"),
            "display_name": item.get("display_name"),
            "classification": item.get("classification"),
            "claim_level": item.get("claim_level"),
            "authority_boundary": item.get("authority_boundary"),
            "next_safe_lane": item.get("next_safe_lane"),
        }
        for item in segmentation.get("chief_sub_areas", [])
        if item.get("classification") in classifications
    ]


def _operator_memory_subareas(segmentation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "sub_area_id": item.get("sub_area_id"),
            "display_name": item.get("display_name"),
            "classification": item.get("classification"),
            "operator_memory_guidance": item.get("operator_memory_guidance", []),
            "needs_operator_memory_review": bool(item.get("needs_operator_memory_review")),
        }
        for item in segmentation.get("chief_sub_areas", [])
        if item.get("needs_operator_memory_review") or item.get("operator_memory_guidance")
    ]


def _safe_counts(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _chief_count(payload: dict[str, Any], key: str = "counts_by_agent") -> int:
    counts = _safe_counts(payload, key)
    try:
        return int(counts.get("chief", 0))
    except (TypeError, ValueError):
        return 0


def _surface_summary(
    *,
    work_board: dict[str, Any],
    agent_work_packets: dict[str, Any],
    intent_router: dict[str, Any],
    dropped_intents: dict[str, Any],
) -> dict[str, Any]:
    return {
        "work_board": {
            "present": bool(work_board),
            "chief_card_count": _chief_count(work_board),
            "counts_by_column": _safe_counts(work_board, "counts_by_column"),
            "direct_execution_allowed": bool(work_board.get("direct_execution_allowed", False)),
            "agent_activation_allowed": bool(work_board.get("agent_activation_allowed", False)),
            "model_call_allowed": bool(work_board.get("model_call_allowed", False)),
            "tool_execution_allowed": bool(work_board.get("tool_execution_allowed", False)),
            "status_signal": "chief_routed_cards_visible" if _chief_count(work_board) else "no_chief_cards_visible",
        },
        "agent_work_packets": {
            "present": bool(agent_work_packets),
            "chief_packet_count": _chief_count(agent_work_packets),
            "counts_by_status": _safe_counts(agent_work_packets, "counts_by_status"),
            "execution_allowed": bool(agent_work_packets.get("execution_allowed", False)),
            "agent_activation_allowed": bool(agent_work_packets.get("agent_activation_allowed", False)),
            "model_call_allowed": bool(agent_work_packets.get("model_call_allowed", False)),
            "tool_execution_allowed": bool(agent_work_packets.get("tool_execution_allowed", False)),
            "status_signal": "chief_packets_visible" if _chief_count(agent_work_packets) else "no_chief_packets_visible",
        },
        "intent_router": {
            "present": bool(intent_router),
            "chief_route_count": _chief_count(intent_router),
            "counts_by_category": _safe_counts(intent_router, "counts_by_category"),
            "direct_execution_allowed": bool(intent_router.get("direct_execution_allowed", False)),
            "runtime_authority": bool(intent_router.get("runtime_authority", False)),
            "model_execution_allowed": bool(intent_router.get("model_execution_allowed", False)),
            "tool_execution_allowed": bool(intent_router.get("tool_execution_allowed", False)),
            "source_posture": intent_router.get("source_posture", {}),
            "status_signal": "chief_intent_routes_visible" if _chief_count(intent_router) else "no_chief_routes_visible",
        },
        "dropped_intents": {
            "present": bool(dropped_intents),
            "chief_dropped_intent_count": _chief_count(dropped_intents),
            "counts_by_status": _safe_counts(dropped_intents, "counts_by_status"),
            "notification_allowed": bool(dropped_intents.get("notification_allowed", False)),
            "autonomous_prompting_allowed": bool(dropped_intents.get("autonomous_prompting_allowed", False)),
            "model_call_allowed": bool(dropped_intents.get("model_call_allowed", False)),
            "raw_private_scan_allowed": bool(dropped_intents.get("raw_private_scan_allowed", False)),
            "status_signal": "chief_deferred_or_unresolved_intents_visible"
            if _chief_count(dropped_intents)
            else "no_chief_dropped_intents_visible",
        },
    }


def _next_lane_gate() -> dict[str, Any]:
    return evaluate_post_preflight_lane(
        lane_name="Build Now Vs Hold Queue Posture v0",
        lane_summary="Model build-now-vs-hold timing from dropped-intent/work-board evidence without executing queues.",
        named_operator_workflow="Winship needs deferred ideas separated from work that is ready to build.",
        shared_bottleneck="queue_timing_decision_gap",
        steel_thread_contract_link="chief_status_rail_v0",
        reusable_substrate_improvement="Reusable timing posture for Chief/work-board planning.",
        workflow_proof_output="Queue posture read-model showing build-now, hold, and memory-review buckets.",
        detangling_scope={
            "serves_lane_directly": True,
            "opportunistic_only": True,
            "physical_module_extraction_requested": False,
            "client_repo_generation_requested": False,
            "detangling_required_before_workflow_proof": False,
            "notes": "Queue timing remains status/read-model work; no queue execution or automation.",
        },
        module_split_disposition={
            "disposition": "record_future_work",
            "recorded_future_work": True,
            "reason": "If queue concepts imply module splits, record them after the posture proof rather than extracting now.",
        },
        authority_change_requested={
            "requested": False,
            "authority_types": [],
            "reason": "Read-model/status work only.",
        },
        expected_artifacts=[
            {"artifact_kind": "read_model", "path_or_contract": "generated/read_models/build_now_vs_hold_queue_posture.json"},
            {"artifact_kind": "operator_packet", "path_or_contract": "generated/read_models/build_now_vs_hold_queue_posture_OPERATOR.md"},
            {"artifact_kind": "test_proof", "path_or_contract": "focused queue posture tests"},
        ],
        validation_required=("focused tests", "JSON validation", "authority flags"),
        synthetic_example=False,
    )


def _eli5_summary() -> dict[str, str]:
    return {
        "here_is_what_chief_currently_is": (
            "Chief is currently a safe coordination/status rail: it can show routed work, planning packets, "
            "and deferred or unresolved work signals."
        ),
        "here_is_what_chief_is_not_yet": (
            "Chief is not a live executor, Telegram sender, LLM/Ollama service, repair loop, browser operator, "
            "or credential holder."
        ),
        "here_is_what_chief_can_safely_help_with_now": (
            "Chief can help orient work: what is routed to Chief, what packet exists, what is deferred, "
            "and what remains blocked."
        ),
        "here_is_what_remains_blocked": (
            "Execution, planner/builder automation, repair loops, Telegram notification, model/tool calls, "
            "arbitrary shell, credentials, browser/Coupa, and client deployment stay blocked."
        ),
        "here_is_the_next_safe_move": (
            "Model the build-now-vs-hold queue posture as another read-model, without running queues."
        ),
    }


def _extract_fleet_health_facts(fleet_health: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract grounded facts from fleet-health read model for inclusion in the status rail."""
    return list(fleet_health.get("grounded_facts") or [])


def _fleet_health_summary(fleet_health: dict[str, Any]) -> dict[str, Any]:
    """Compact, provenance-carrying summary of fleet health for the status rail."""
    if not fleet_health:
        return {"available": False, "source_ref": str(DEFAULT_FLEET_HEALTH_PATH)}
    ah = fleet_health.get("agent_health") or {}
    sh = fleet_health.get("sync_health") or {}
    gm = fleet_health.get("git_milestones") or {}
    return {
        "available": True,
        "source_ref": str(DEFAULT_FLEET_HEALTH_PATH),
        "generated_at": fleet_health.get("generated_at") or "",
        "agent_health": {
            "online_count": ah.get("online_count"),
            "total_agents": ah.get("total_agents"),
            "online_agents": ah.get("online_agents") or [],
            "degraded_agents": ah.get("degraded_agents") or [],
            "offline_agents": ah.get("offline_agents") or [],
            "unexpected_offline_count": ah.get("unexpected_offline_count"),
            "summary": ah.get("summary") or "",
        } if ah else None,
        "sync_health": {
            "mirror_status": sh.get("mirror_status"),
            "display_status": sh.get("display_status"),
            "operator_action_required": sh.get("operator_action_required"),
            "last_mac_completion_time": sh.get("last_mac_completion_time"),
            "summary": sh.get("summary") or "",
        } if sh else None,
        "git_milestones": {
            "branch": gm.get("branch"),
            "count": gm.get("count"),
            "available": gm.get("available"),
            "latest_milestone": gm.get("milestones", [{}])[0] if gm.get("milestones") else None,
        } if gm else None,
        "grounded_fact_count": fleet_health.get("grounded_fact_count", 0),
    }


def build_chief_status_rail(
    *,
    repo_root: str | Path = ROOT,
    segmentation_path: str | Path = DEFAULT_SEGMENTATION_PATH,
    work_board_path: str | Path = DEFAULT_WORK_BOARD_PATH,
    agent_work_packets_path: str | Path = DEFAULT_AGENT_WORK_PACKETS_PATH,
    intent_router_path: str | Path = DEFAULT_INTENT_ROUTER_PATH,
    dropped_intents_path: str | Path = DEFAULT_DROPPED_INTENTS_PATH,
    fleet_health_path: str | Path = DEFAULT_FLEET_HEALTH_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    segmentation = _read_json_if_present(segmentation_path, repo_root=repo_root)
    work_board = _read_json_if_present(work_board_path, repo_root=repo_root)
    agent_work_packets = _read_json_if_present(agent_work_packets_path, repo_root=repo_root)
    intent_router = _read_json_if_present(intent_router_path, repo_root=repo_root)
    dropped_intents = _read_json_if_present(dropped_intents_path, repo_root=repo_root)
    fleet_health = _read_json_if_present(fleet_health_path, repo_root=repo_root)
    source_payloads = {
        "segmentation": segmentation,
        "work_board": work_board,
        "agent_work_packets": agent_work_packets,
        "intent_router": intent_router,
        "dropped_intents": dropped_intents,
        "fleet_health": fleet_health,
    }
    surfaces = _surface_summary(
        work_board=work_board,
        agent_work_packets=agent_work_packets,
        intent_router=intent_router,
        dropped_intents=dropped_intents,
    )
    next_gate = _next_lane_gate()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "rail_status": "completed_visibility_planning_only",
        "chief_current_status": "safe_status_read_model_only",
        "chief_current_proven_role": {
            "role_summary": (
                "Chief is currently proven as a request-only coordination/planning/status lane backed by "
                "Agent Lane Registry, Intent Router, Work Board, and Agent Work Packet read-models."
            ),
            "role_confidence": "high_for_visibility_and_planning_low_for_runtime",
            "source_basis": "Repo A read-models and contracts only",
            "executor": False,
            "runtime_or_send_authority": False,
        },
        "current_chief_related_substrates": [
            {
                "substrate": "agent_lane_registry",
                "status": "proven_request_only_role_metadata",
                "safe_use": "Chief can be routed as a coordination/planning lane.",
                "authority": "request_only_no_execution",
            },
            {
                "substrate": "intent_router",
                "status": surfaces["intent_router"]["status_signal"],
                "safe_use": "Chief-targeted operator intents can be represented as routes.",
                "authority": "routing_metadata_only",
            },
            {
                "substrate": "work_board",
                "status": surfaces["work_board"]["status_signal"],
                "safe_use": "Chief-routed work can be visible as board cards.",
                "authority": "visibility_and_planning_only",
            },
            {
                "substrate": "agent_work_packets",
                "status": surfaces["agent_work_packets"]["status_signal"],
                "safe_use": "Chief work can become bounded prompt scaffolding.",
                "authority": "packet_draft_only",
            },
            {
                "substrate": "dropped_intents",
                "status": surfaces["dropped_intents"]["status_signal"],
                "safe_use": "Chief-adjacent deferred/unresolved work can remain visible without prompting or notifying.",
                "authority": "metadata_only",
            },
        ],
        "visible_status_signals": surfaces,
        "work_packet_status_surfaces_available": {
            "work_board_available": bool(work_board),
            "agent_work_packets_available": bool(agent_work_packets),
            "intent_router_available": bool(intent_router),
            "dropped_intents_available": bool(dropped_intents),
            "chief_card_count": surfaces["work_board"]["chief_card_count"],
            "chief_packet_count": surfaces["agent_work_packets"]["chief_packet_count"],
            "chief_route_count": surfaces["intent_router"]["chief_route_count"],
            "chief_dropped_intent_count": surfaces["dropped_intents"]["chief_dropped_intent_count"],
        },
        "status_category_model": {
            "categories": list(STATUS_CATEGORIES),
            "proven": _subareas_by_classification(
                segmentation,
                {"TESTED_SUPPORTING_CONTRACT", "PROVEN_CANONICAL"},
            ),
            "partially_represented": _subareas_by_classification(segmentation, {"PARTIALLY_REPRESENTED"}),
            "inferred_not_proven": _subareas_by_classification(
                segmentation,
                {"INFERRED_NOT_PROVEN", "SEGMENTATION_REQUIRED"},
            ),
            "operator_memory_only": _operator_memory_subareas(segmentation),
            "unsafe_blocked": _subareas_by_classification(segmentation, {"UNSAFE_OR_BLOCKED", "LEGACY_OR_REFERENCE"}),
            "future_security_threshold": [
                "planner_builder_coordination",
                "automatic_fix_repair_loop_concepts",
                "protected_access_broker_concepts",
                "execution_security_threshold_boundaries",
            ],
        },
        "inferred_but_not_proven": [
            "Chief as a broader central orchestration spine",
            "Chief listener/router/session as current canonical flow",
            "Chief as domain-brain coordinator across Cassandra, Niles, finance, Report Bridge, website, or infrastructure",
            "Chief queue timing as a completed build-now-vs-hold workflow",
        ],
        "explicitly_blocked": {
            "execution": True,
            "planner_builder_automation": True,
            "repair_fix_loops": True,
            "telegram_notification_or_send": True,
            "llm_or_ollama_calls": True,
            "tool_execution": True,
            "arbitrary_shell": True,
            "browser_or_coupa": True,
            "credential_or_pii_access": True,
            "approval_execution": True,
            "client_deployment": True,
            "security_threshold_work": True,
        },
        "source_read_models": [
            _source_record(source, repo_root=repo_root, payload=source_payloads[source.key])
            for source in SOURCE_READ_MODELS
        ],
        # ── Grounded fleet-health facts (from agent_presence.json, sync_health.json, git log) ──
        "fleet_health_summary": _fleet_health_summary(fleet_health),
        "fleet_health_grounded_facts": _extract_fleet_health_facts(fleet_health),
        "next_safe_chief_lane": {
            "lane_name": "Build Now Vs Hold Queue Posture v0",
            "reason": "The status rail is now complete; the next bounded gap is timing posture for deferred versus ready Chief-adjacent work.",
            "gate_status": next_gate["gate_status"],
            "non_live": True,
            "no_queue_execution": True,
            "post_preflight_batch_gate_evaluation": next_gate,
        },
        "operator_eli5_summary": _eli5_summary(),
        "work_packets_are_visibility_review_planning_only": True,
        "unknown_chief_authority_fails_closed": True,
        "repo_a_only_inspection": True,
        "repo_b_delta_read_model_used": bool(segmentation.get("repo_b_delta_read_model_used")),
        "live_execution_recommended": False,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_chief_status_rail(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    status = payload["work_packet_status_surfaces_available"]
    lines = [
        "# Chief Status Rail v0",
        "",
        "Status:",
        f"- Rail status: `{payload['rail_status']}`.",
        "- Chief executor authority: `false`.",
        "- Runtime/send/model/tool authority: `false`.",
        "",
        "## ELI5 Summary",
        f"- Here is what Chief currently is: {eli5['here_is_what_chief_currently_is']}",
        f"- Here is what Chief is not yet: {eli5['here_is_what_chief_is_not_yet']}",
        f"- Here is what Chief can safely help with now: {eli5['here_is_what_chief_can_safely_help_with_now']}",
        f"- Here is what remains blocked: {eli5['here_is_what_remains_blocked']}",
        f"- Here is the next safe move: {eli5['here_is_the_next_safe_move']}",
        "",
        "## Visible Status Signals",
        f"- Chief work-board cards: `{status['chief_card_count']}`.",
        f"- Chief work packets: `{status['chief_packet_count']}`.",
        f"- Chief intent routes: `{status['chief_route_count']}`.",
        f"- Chief dropped/deferred intents: `{status['chief_dropped_intent_count']}`.",
        "",
        "## Fleet Health (Grounded)",
    ]
    fhs = payload.get("fleet_health_summary") or {}
    if fhs.get("available"):
        ah = fhs.get("agent_health") or {}
        sh = fhs.get("sync_health") or {}
        gm = fhs.get("git_milestones") or {}
        if ah:
            lines.append(f"- {ah.get('summary', '')}")
        if sh:
            lines.append(f"- {sh.get('summary', '')}")
        if gm and gm.get("available"):
            latest = gm.get("latest_milestone") or {}
            lines.append(
                f"- Shipped milestones: {gm.get('count')} on `{gm.get('branch')}`. "
                f"Latest: {latest.get('summary', 'n/a')} ({latest.get('commit', '')})."
            )
        lines.append(f"  source: `{fhs.get('source_ref', '')}`, as-of: {fhs.get('generated_at', 'unknown')}")
    else:
        lines.append("- Fleet health read-model not yet available (generate with chief_agent_fleet_health.py).")
    lines.extend([
        "",
        "## Proven Now",
    ])
    for item in payload["status_category_model"]["proven"]:
        lines.append(f"- {item['display_name']}: {item['authority_boundary']}")
    lines.extend(["", "## Partially Represented"])
    for item in payload["status_category_model"]["partially_represented"]:
        lines.append(f"- {item['display_name']}: {item['authority_boundary']}")
    lines.extend(["", "## Inferred, Not Proven"])
    for item in payload["inferred_but_not_proven"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Blocked"])
    for key, blocked in payload["explicitly_blocked"].items():
        if blocked:
            lines.append(f"- `{key}`")
    next_lane = payload["next_safe_chief_lane"]
    lines.extend(
        [
            "",
            "## Next Safe Chief Lane",
            f"- `{next_lane['lane_name']}`: gate `{next_lane['gate_status']}`.",
            f"- {next_lane['reason']}",
            "",
            "## Boundaries",
            "- No Chief runtime modules were imported.",
            "- No Repo B filesystem inspection was performed.",
            "- No Telegram, LLM/Ollama, planner/builder, repair-loop, shell, credential, browser, or deployment authority was added.",
        ]
    )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ChiefStatusRailExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    rail_status: str
    chief_card_count: int
    chief_packet_count: int
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def export_chief_status_rail(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ChiefStatusRailExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_chief_status_rail(repo_root=repo_root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_chief_status_rail(payload), encoding="utf-8")
    status = payload["work_packet_status_surfaces_available"]
    return ChiefStatusRailExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        rail_status=payload["rail_status"],
        chief_card_count=status["chief_card_count"],
        chief_packet_count=status["chief_packet_count"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Chief status rail read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print JSON or operator Markdown.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_chief_status_rail(repo_root=args.repo_root, export_root=args.export_root)
    output_path = Path(args.repo_root) / args.export_root / (JSON_EXPORT_NAME if args.format == "json" else OPERATOR_EXPORT_NAME)
    print(output_path.read_text(encoding="utf-8"), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


if __name__ == "__main__":
    raise SystemExit(main())
