"""Build-now-vs-hold queue posture v0.

This read-model connects safe operator-intent, dropped-intent, work-board, and
agent-work-packet evidence into a deterministic posture map. It is visibility
and routing substrate only: it does not execute builds, activate queues,
notify Telegram, call models, run repair loops, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from post_preflight_batch_gate import PASS, evaluate_post_preflight_lane


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "build_now_vs_hold_queue_posture_v0"
JSON_EXPORT_NAME = "build_now_vs_hold_queue_posture.json"
OPERATOR_EXPORT_NAME = "build_now_vs_hold_queue_posture_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

DEFAULT_CHIEF_STATUS_PATH = DEFAULT_EXPORT_ROOT / "chief_status_rail.json"
DEFAULT_SEGMENTATION_PATH = DEFAULT_EXPORT_ROOT / "chief_role_capability_segmentation_map.json"
DEFAULT_REPO_A_MAP_PATH = DEFAULT_EXPORT_ROOT / "repo_a_known_rail_completion_map.json"
DEFAULT_REPO_B_DELTA_PATH = DEFAULT_EXPORT_ROOT / "repo_b_remaining_capability_delta_map.json"
DEFAULT_INTENT_ROUTER_PATH = DEFAULT_EXPORT_ROOT / "intent_router.json"
DEFAULT_DROPPED_INTENTS_PATH = DEFAULT_EXPORT_ROOT / "dropped_intents.json"
DEFAULT_WORK_BOARD_PATH = DEFAULT_EXPORT_ROOT / "work_board.json"
DEFAULT_AGENT_WORK_PACKETS_PATH = DEFAULT_EXPORT_ROOT / "agent_work_packets.json"
DEFAULT_OPERATOR_ACTIONS_PATH = DEFAULT_EXPORT_ROOT / "operator_actions.json"

POSTURE_CATEGORIES = (
    "BUILD_NOW_READY",
    "HOLD_FOR_RIGHT_TIME",
    "NEEDS_CONTEXT",
    "NEEDS_PROOF",
    "NEEDS_OPERATOR_MEMORY_REVIEW",
    "ROUTE_TO_EXISTING_RAIL",
    "BLOCKED_AUTHORITY",
    "BLOCKED_SECURITY_THRESHOLD",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "build_execution_authority_added": False,
    "planner_builder_automation_activated": False,
    "repair_fix_loop_activated": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "telegram_send_triggered": False,
    "email_send_triggered": False,
    "llm_ollama_called": False,
    "tool_execution_authority_added": False,
    "arbitrary_shell_allowed": False,
    "browser_or_coupa_authority_added": False,
    "credential_or_pii_access_added": False,
    "gmail_calendar_coupa_credentials_accessed": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "chief_runtime_modules_imported": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "client_deployment_authority_added": False,
    "old_files_treated_as_truth": False,
    "queue_files_mutated": False,
}

AUTHORITY_KEYWORDS = (
    "send",
    "submit",
    "credential",
    "browser",
    "coupa",
    "gmail",
    "calendar",
    "telegram",
    "daemon",
    "watcher",
    "runtime",
    "execute",
    "shell",
    "repair",
    "fix loop",
    "ollama",
    "llm",
)

SECURITY_THRESHOLD_KEYWORDS = (
    "planner/builder",
    "builder",
    "autonomous",
    "self-repair",
    "protected broker",
    "pii",
    "oauth",
    "client deployment",
    "security threshold",
)

CONTEXT_KEYWORDS = (
    "context",
    "that new file",
    "recent file",
    "vague",
    "clearer target",
    "metadata",
)

PROOF_KEYWORDS = (
    "proof",
    "receipt",
    "approval",
    "confirm",
    "confirmation",
    "evidence",
    "operator action request",
)


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


SOURCE_READ_MODELS = (
    SourceReadModel("chief_status", str(DEFAULT_CHIEF_STATUS_PATH), "Chief status rail precondition"),
    SourceReadModel("segmentation", str(DEFAULT_SEGMENTATION_PATH), "Chief role/capability segmentation"),
    SourceReadModel("repo_a_map", str(DEFAULT_REPO_A_MAP_PATH), "Repo A known rail baseline"),
    SourceReadModel("repo_b_delta", str(DEFAULT_REPO_B_DELTA_PATH), "Repo B delta read-model reference only"),
    SourceReadModel("intent_router", str(DEFAULT_INTENT_ROUTER_PATH), "operator intent routing"),
    SourceReadModel("dropped_intents", str(DEFAULT_DROPPED_INTENTS_PATH), "deferred/unresolved intent preservation"),
    SourceReadModel("work_board", str(DEFAULT_WORK_BOARD_PATH), "work-board status surface"),
    SourceReadModel("agent_work_packets", str(DEFAULT_AGENT_WORK_PACKETS_PATH), "bounded work packet surface"),
    SourceReadModel("operator_actions", str(DEFAULT_OPERATOR_ACTIONS_PATH), "approval-gated operator action posture"),
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


def _safe_counts(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _norm_text(*parts: object) -> str:
    return " ".join(str(part or "") for part in parts).lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _authority_signal_text(text: str) -> str:
    cleaned = text
    for phrase in (
        "do not execute",
        "does not execute",
        "without executing",
        "no execution",
        "execution remains separate",
        "execution remains blocked",
        "not execution authority",
        "no telegram",
        "no sends",
        "do not send",
        "without sending",
        "not a daemon",
    ):
        cleaned = cleaned.replace(phrase, "")
    return cleaned


def _candidate_id(prefix: str, source_id: object, title: object) -> str:
    stable = str(source_id or title or "unknown").strip().lower().replace(" ", "_")
    cleaned = "".join(ch for ch in stable if ch.isalnum() or ch in {"_", "-"}).strip("_")
    return f"{prefix}_{cleaned[:80] or 'unknown'}"


def _candidate_from_agent_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": _candidate_id("agent_packet", packet.get("packet_id"), packet.get("goal")),
        "source_surface": "agent_work_packets",
        "source_id": packet.get("packet_id"),
        "title": packet.get("goal") or packet.get("packet_id"),
        "summary": packet.get("goal", ""),
        "current_status": packet.get("status", "unknown"),
        "agent_hint": packet.get("routed_agent_id"),
        "lane_hint": packet.get("routed_lane_id"),
        "intent_category": packet.get("intent_category"),
        "world_hint": packet.get("world_hint"),
        "execution_allowed": bool(packet.get("execution_allowed", False)),
        "approval_required": bool(packet.get("approval_required", True)),
        "next_safe_move": "Use this as a bounded work-packet prompt scaffold; execution remains separate.",
        "evidence_basis": "agent_work_packet_read_model",
    }


def _candidate_from_work_board_card(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": _candidate_id("work_board", card.get("card_id"), card.get("title")),
        "source_surface": "work_board",
        "source_id": card.get("card_id"),
        "title": card.get("title"),
        "summary": card.get("summary", ""),
        "current_status": card.get("board_column") or card.get("status", "unknown"),
        "agent_hint": card.get("agent_id"),
        "lane_hint": card.get("lane_id"),
        "intent_category": card.get("intent_category"),
        "world_hint": card.get("world_hint"),
        "execution_allowed": bool(card.get("execution_allowed", False)),
        "approval_required": bool(card.get("approval_required", True)),
        "next_safe_move": card.get("next_safe_move", ""),
        "evidence_basis": "work_board_read_model",
    }


def _candidate_from_dropped_intent(item: dict[str, Any], *, source_list: str) -> dict[str, Any]:
    return {
        "candidate_id": _candidate_id("dropped_intent", item.get("dropped_intent_id"), item.get("title")),
        "source_surface": f"dropped_intents.{source_list}",
        "source_id": item.get("dropped_intent_id"),
        "title": item.get("title"),
        "summary": item.get("short_summary", ""),
        "current_status": item.get("current_status", "unknown"),
        "agent_hint": item.get("agent_hint"),
        "lane_hint": item.get("lane_hint"),
        "intent_category": item.get("intent_category"),
        "world_hint": item.get("world_hint"),
        "execution_allowed": False,
        "approval_required": bool(item.get("approval_required", True)),
        "next_safe_move": item.get("suggested_next_question") or item.get("suggested_next_lane", ""),
        "evidence_basis": item.get("evidence_basis", "dropped_intent_read_model"),
        "raw_body_stored": bool(item.get("raw_body_stored", False)),
        "notification_sent": bool(item.get("notification_sent", False)),
    }


def _collect_candidates(
    *,
    work_board: dict[str, Any],
    agent_work_packets: dict[str, Any],
    dropped_intents: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for packet in agent_work_packets.get("packets", [])[:20]:
        if isinstance(packet, dict):
            candidates.append(_candidate_from_agent_packet(packet))
    for card in work_board.get("latest_cards", [])[:20]:
        if isinstance(card, dict):
            candidates.append(_candidate_from_work_board_card(card))
    for list_name in ("top_unresolved_items", "deferred_items", "unknown_review_items", "built_items"):
        for item in dropped_intents.get(list_name, [])[:20]:
            if isinstance(item, dict):
                candidates.append(_candidate_from_dropped_intent(item, source_list=list_name))
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        deduped.setdefault(candidate["candidate_id"], candidate)
    return list(deduped.values())


def classify_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Classify one queue candidate into the build-now-vs-hold posture.

    This is a deterministic visibility classification only. ``BUILD_NOW_READY``
    means ready for a bounded read-model/work-packet lane, not execution.
    """

    text = _norm_text(
        candidate.get("title"),
        candidate.get("summary"),
        candidate.get("current_status"),
        candidate.get("intent_category"),
        candidate.get("next_safe_move"),
        candidate.get("evidence_basis"),
    )
    source_surface = str(candidate.get("source_surface") or "")
    status = str(candidate.get("current_status") or "").lower()
    execution_allowed = bool(candidate.get("execution_allowed", False))
    reason = "unknown_failed_closed"
    category = "UNKNOWN_FAIL_CLOSED"
    route_target = candidate.get("lane_hint") or "operator_review"
    can_become_work_packet = False
    next_safe_move = candidate.get("next_safe_move") or "Ask operator for a clearer target before routing."

    authority_text = _authority_signal_text(text)

    if "unknown" in status or "unknown_review" in text:
        category = "UNKNOWN_FAIL_CLOSED"
        reason = "unknown_or_ambiguous_target"
        next_safe_move = "Ask operator for a clearer target, rail, or evidence source."
    elif execution_allowed or _contains_any(authority_text, AUTHORITY_KEYWORDS):
        if _contains_any(text, SECURITY_THRESHOLD_KEYWORDS):
            category = "BLOCKED_SECURITY_THRESHOLD"
            reason = "would_cross_security_or_live_authority_threshold"
        else:
            category = "BLOCKED_AUTHORITY"
            reason = "would_require_send_runtime_shell_model_tool_or_external_authority"
        next_safe_move = "Keep as blocked posture until a future gated authority lane exists."
    elif "deferred" in status:
        category = "HOLD_FOR_RIGHT_TIME"
        reason = "explicitly_deferred_or_future_timed"
        next_safe_move = candidate.get("next_safe_move") or "Preserve intent until prerequisites or timing improve."
    elif _contains_any(text, CONTEXT_KEYWORDS):
        category = "NEEDS_CONTEXT"
        reason = "missing_context_or_metadata_resolution"
        next_safe_move = candidate.get("next_safe_move") or "Create/read a bounded context read-model before work packet generation."
    elif _contains_any(text, PROOF_KEYWORDS):
        category = "NEEDS_PROOF"
        reason = "requires_evidence_receipt_or_operator_confirmation_before_progress"
        next_safe_move = candidate.get("next_safe_move") or "Capture proof/read-model evidence before changing posture."
    elif source_surface == "agent_work_packets" and status in {"draft", "proposed"}:
        category = "BUILD_NOW_READY"
        reason = "bounded_work_packet_already_exists"
        can_become_work_packet = True
    elif source_surface == "work_board" and status in {"routed", "planned"}:
        category = "ROUTE_TO_EXISTING_RAIL"
        reason = "already_routed_to_existing_lane_without_execution"
        can_become_work_packet = True
    elif "memory" in text or "operator" in text and "review" in text:
        category = "NEEDS_OPERATOR_MEMORY_REVIEW"
        reason = "operator_memory_or_decision_needed"
    else:
        category = "UNKNOWN_FAIL_CLOSED"
        reason = "no_deterministic_readiness_rule_matched"

    return {
        **candidate,
        "posture_category": category,
        "classification_reason": reason,
        "route_target": route_target,
        "can_become_work_packet": can_become_work_packet,
        "build_now_is_execution_authority": False,
        "next_safe_move": next_safe_move,
    }


def _category_rules() -> list[dict[str, Any]]:
    return [
        {
            "category": "BUILD_NOW_READY",
            "meaning": "Enough safe context exists to create or use a bounded work packet/read-model lane now.",
            "does_not_mean": "No execution, build run, shell, send, model call, or runtime activation.",
        },
        {
            "category": "HOLD_FOR_RIGHT_TIME",
            "meaning": "Intent is preserved, but timing or prerequisites make it wrong to build now.",
            "does_not_mean": "The system will remind, prompt, or activate later by itself.",
        },
        {
            "category": "NEEDS_CONTEXT",
            "meaning": "A bounded context/read-model resolver is needed before the request can be routed safely.",
            "does_not_mean": "Raw files, private logs, or broad drives may be scanned.",
        },
        {
            "category": "NEEDS_PROOF",
            "meaning": "Evidence, receipt, operator confirmation, or read-model proof is needed first.",
            "does_not_mean": "The system may fabricate confirmation or external evidence.",
        },
        {
            "category": "NEEDS_OPERATOR_MEMORY_REVIEW",
            "meaning": "Repo evidence is insufficient and Winship memory may be needed to decide.",
            "does_not_mean": "Operator memory becomes truth automatically.",
        },
        {
            "category": "ROUTE_TO_EXISTING_RAIL",
            "meaning": "The request maps to an existing safe rail/lane for planning or packet generation.",
            "does_not_mean": "The receiving rail can execute work.",
        },
        {
            "category": "BLOCKED_AUTHORITY",
            "meaning": "The request would need forbidden send/runtime/shell/model/tool/external authority.",
            "does_not_mean": "The request is rejected forever; it needs a future gated authority lane.",
        },
        {
            "category": "BLOCKED_SECURITY_THRESHOLD",
            "meaning": "The request crosses higher-power automation/security/client-deployment thresholds.",
            "does_not_mean": "A security pass has started.",
        },
        {
            "category": "UNKNOWN_FAIL_CLOSED",
            "meaning": "The request is too ambiguous for deterministic routing.",
            "does_not_mean": "The system should guess.",
        },
    ]


def _input_capture_model() -> list[dict[str, Any]]:
    return [
        {
            "input_kind": "operator_intent",
            "capture_surface": "intent_router",
            "allowed_storage": "short_preview_hash_metadata",
            "raw_body_stored": False,
            "safe_next_use": "route to existing rail or needs-review posture",
        },
        {
            "input_kind": "brain_dump_or_cue",
            "capture_surface": "dropped_intent_registry_or_future_governed_cue_parser",
            "allowed_storage": "bounded excerpt and source metadata only",
            "raw_body_stored": False,
            "safe_next_use": "preserve intent until context/proof/operator memory is available",
        },
        {
            "input_kind": "work_board_card",
            "capture_surface": "work_board",
            "allowed_storage": "status, route, blocker, next-safe-move metadata",
            "raw_body_stored": False,
            "safe_next_use": "visibility and planning status",
        },
        {
            "input_kind": "agent_work_packet",
            "capture_surface": "agent_work_packet",
            "allowed_storage": "bounded prompt scaffold and allowed/blocked surfaces",
            "raw_body_stored": False,
            "safe_next_use": "manual or future-gated worker prompt handoff",
        },
        {
            "input_kind": "operator_action_request",
            "capture_surface": "operator_action_inbox",
            "allowed_storage": "strict request JSON metadata only",
            "raw_body_stored": False,
            "safe_next_use": "approval-gated request record, never auto-execute",
        },
    ]


def _next_lane_recommendations() -> list[dict[str, Any]]:
    lanes = (
        (
            "Governed Cue Parser Delta v0",
            "Convert safe cue/brain-dump signals into bounded metadata classifications without LLM/file-move behavior.",
            "Winship needs rough ideas preserved without broad note ingestion.",
            "cue_intake_governance_gap",
            "build_now_vs_hold_queue_posture_v0",
            "Reusable cue-parser posture that feeds queue classification safely.",
            "Cue parser delta read-model with raw/private scans blocked.",
        ),
        (
            "Recent File Context Resolver v0",
            "Resolve vague file references from safe file-event metadata before turning them into work packets.",
            "Winship needs requests like 'that new file' to route without raw private file reads.",
            "missing_context_resolution_gap",
            "build_now_vs_hold_queue_posture_v0",
            "Reusable context resolver for vague operator cues.",
            "Metadata-only context resolution read-model.",
        ),
        (
            "Chief Domain Overlap Segmentation Review v0",
            "Map old Chief domain-brain concepts to current owned rails without activating domain brains.",
            "Winship needs Chief-overlap ideas routed to Cassandra, Niles, finance, Report Bridge, or custom-build rails.",
            "chief_domain_overlap_gap",
            "chief_role_capability_segmentation_map_v0",
            "Reusable ownership map for broad Chief concepts.",
            "Domain-overlap read-model with future lane recommendations.",
        ),
    )
    recommendations: list[dict[str, Any]] = []
    for lane_name, summary, workflow, bottleneck, contract, substrate, proof in lanes:
        gate = evaluate_post_preflight_lane(
            lane_name=lane_name,
            lane_summary=summary,
            named_operator_workflow=workflow,
            shared_bottleneck=bottleneck,
            steel_thread_contract_link=contract,
            reusable_substrate_improvement=substrate,
            workflow_proof_output=proof,
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Queue posture feeds the next bounded metadata/read-model lane only.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "reason": "Any module split discovered here should be captured as future work, not executed.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Read-model/metadata posture only.",
            },
            expected_artifacts=[
                {"artifact_kind": "read_model", "path_or_contract": "generated/read_models/<future>.json"},
                {"artifact_kind": "operator_packet", "path_or_contract": "generated/read_models/<future>_OPERATOR.md"},
                {"artifact_kind": "test_proof", "path_or_contract": "focused tests"},
            ],
            validation_required=("focused tests", "JSON validation", "authority flags"),
            synthetic_example=False,
        )
        recommendations.append(
            {
                "lane_name": lane_name,
                "why_next": summary,
                "post_preflight_batch_gate_evaluation": gate,
            }
        )
    return recommendations


def _eli5_summary(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "how_openclaw_decides_build_now_vs_hold": (
            "OpenClaw checks whether an idea already has enough safe context and a named rail. If it does, it can "
            "become a bounded work packet or read-model lane. If it is vague, early, risky, or missing proof, it is held, "
            "parked, or blocked instead of guessed."
        ),
        "what_can_safely_become_a_work_packet": (
            "Requests with a clear rail, safe metadata context, no forbidden authority, and a bounded next-safe move."
        ),
        "what_gets_parked": (
            "Deferred ideas, vague cues, memory-dependent ideas, missing-context requests, and items waiting for proof."
        ),
        "what_is_blocked_on_purpose": (
            "Items are blocked on purpose when they require execution, sends, shell, LLM/Ollama calls, planner/builder "
            "automation, repair loops, credentials, browser/Coupa, or client deployment."
        ),
        "what_still_needs_future_security_live_authority_pass": (
            "Live execution, automation loops, protected broker/PII work, external sends/submits, and client deployment."
        ),
        "next_1_to_3_sensible_lanes": [item["lane_name"] for item in recommendations[:3]],
    }


def build_build_now_vs_hold_queue_posture(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sources = {
        source.key: _read_json_if_present(source.path, repo_root=repo_root)
        for source in SOURCE_READ_MODELS
    }
    chief_status = sources["chief_status"]
    precondition_satisfied = (
        chief_status.get("schema_version") == "chief_status_rail_v0"
        and chief_status.get("rail_status") == "completed_visibility_planning_only"
    )
    candidates = _collect_candidates(
        work_board=sources["work_board"],
        agent_work_packets=sources["agent_work_packets"],
        dropped_intents=sources["dropped_intents"],
    )
    classified = [classify_candidate(candidate) for candidate in candidates]
    category_counts = Counter(item["posture_category"] for item in classified)
    recommendations = _next_lane_recommendations()
    gate_pass_count = sum(
        1
        for item in recommendations
        if item["post_preflight_batch_gate_evaluation"]["gate_status"] == PASS
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "chief_status_precondition": {
            "satisfied": precondition_satisfied,
            "path": str(DEFAULT_CHIEF_STATUS_PATH),
            "schema_version": chief_status.get("schema_version"),
            "rail_status": chief_status.get("rail_status"),
            "required_after_commit": "6c47f45dd582cd1fb2113c2d3c1e110424823f76",
        },
        "posture_scope": "visibility_routing_work_packet_posture_only",
        "build_now_is_execution_authority": False,
        "input_capture_model": _input_capture_model(),
        "posture_categories": list(POSTURE_CATEGORIES),
        "category_rules": _category_rules(),
        "classified_item_count": len(classified),
        "classification_counts": dict(sorted(category_counts.items())),
        "classified_items": classified,
        "items_by_category": {
            category: [item for item in classified if item["posture_category"] == category]
            for category in POSTURE_CATEGORIES
        },
        "routing_targets_visible": {
            "intent_router_counts_by_agent": _safe_counts(sources["intent_router"], "counts_by_agent"),
            "work_board_counts_by_agent": _safe_counts(sources["work_board"], "counts_by_agent"),
            "agent_work_packet_counts_by_agent": _safe_counts(sources["agent_work_packets"], "counts_by_agent"),
            "dropped_intent_counts_by_agent": _safe_counts(sources["dropped_intents"], "counts_by_agent"),
        },
        "safe_work_packet_posture": {
            "can_create_or_use_work_packet_when": (
                "a named rail exists, safe context/proof is present, and the next move is bounded review/planning work"
            ),
            "work_packet_execution_authority": False,
            "agent_activation_allowed": False,
            "model_call_allowed": False,
            "tool_execution_allowed": False,
            "approval_bypass_allowed": False,
        },
        "blocked_authority_summary": {
            "external_message_delivery": True,
            "browser_or_coupa": True,
            "credentials_or_pii": True,
            "runtime_or_shell": True,
            "planner_builder_automation": True,
            "repair_fix_loops": True,
            "llm_ollama_model_calls": True,
            "client_deployment": True,
        },
        "security_threshold_posture": "future_not_current",
        "future_lane_recommendations": recommendations,
        "recommended_next_lanes_all_gate_pass": gate_pass_count == len(recommendations),
        "operator_eli5_summary": _eli5_summary(recommendations),
        "source_read_models": [
            _source_record(source, repo_root=repo_root, payload=sources[source.key])
            for source in SOURCE_READ_MODELS
        ],
        "repo_a_only_inspection": True,
        "repo_b_delta_read_model_used": bool(sources["repo_b_delta"]),
        "unknown_items_fail_closed": True,
        "hold_for_later_preserves_intent_without_readiness": True,
        "routing_visibility_not_execution": True,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_build_now_vs_hold_queue_posture(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Build Now Vs Hold Queue Posture v0",
        "",
        "Status:",
        f"- Chief status precondition satisfied: `{str(payload['chief_status_precondition']['satisfied']).lower()}`.",
        "- Build-now posture is execution authority: `false`.",
        "- Security threshold posture: `future_not_current`.",
        "",
        "## ELI5 Summary",
        f"- How OpenClaw decides build now vs hold: {eli5['how_openclaw_decides_build_now_vs_hold']}",
        f"- What can safely become a work packet: {eli5['what_can_safely_become_a_work_packet']}",
        f"- What gets parked: {eli5['what_gets_parked']}",
        f"- What is blocked on purpose: {eli5['what_is_blocked_on_purpose']}",
        f"- What still needs a future security/live-authority pass: {eli5['what_still_needs_future_security_live_authority_pass']}",
        "",
        "## Classification Counts",
    ]
    for category in POSTURE_CATEGORIES:
        lines.append(f"- `{category}`: {payload['classification_counts'].get(category, 0)}")
    lines.extend(["", "## Example Classified Items"])
    for item in payload["classified_items"][:12]:
        lines.append(
            f"- `{item['posture_category']}`: {item.get('title') or item['candidate_id']} "
            f"-> {item['next_safe_move']}"
        )
    lines.extend(["", "## Next Sensible Lanes"])
    for item in payload["future_lane_recommendations"]:
        gate = item["post_preflight_batch_gate_evaluation"]
        lines.append(f"- `{item['lane_name']}`: gate `{gate['gate_status']}` - {item['why_next']}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "- No builds, queues, planner/builder loops, repair loops, Telegram/email sends, LLM/Ollama calls, shell, credentials, browser, Repo B execution, Mission Control code, or security pass were activated.",
            "- Build-now means ready for bounded read-model/work-packet work, not execution.",
        ]
    )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class BuildNowVsHoldQueuePostureExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    chief_status_precondition_satisfied: bool
    classified_item_count: int
    runtime_authority_added: bool
    build_execution_authority_added: bool


def export_build_now_vs_hold_queue_posture(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> BuildNowVsHoldQueuePostureExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_build_now_vs_hold_queue_posture(repo_root=repo_root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_build_now_vs_hold_queue_posture(payload), encoding="utf-8")
    return BuildNowVsHoldQueuePostureExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        chief_status_precondition_satisfied=payload["chief_status_precondition"]["satisfied"],
        classified_item_count=payload["classified_item_count"],
        runtime_authority_added=payload["runtime_authority_added"],
        build_execution_authority_added=payload["build_execution_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export build-now-vs-hold queue posture read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print JSON or operator Markdown.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_build_now_vs_hold_queue_posture(repo_root=args.repo_root, export_root=args.export_root)
    output_path = Path(args.repo_root) / args.export_root / (JSON_EXPORT_NAME if args.format == "json" else OPERATOR_EXPORT_NAME)
    print(output_path.read_text(encoding="utf-8"), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


if __name__ == "__main__":
    raise SystemExit(main())
