"""Repo B Chief Offline Worker Wrapper v0.

This deterministic Repo A read-model evaluates Repo B Chief control-plane,
routing, queue, status, validator, and watcher-style logic and wraps only the
safe offline reasoning/readback surface. Repo B contains useful routing tables,
approval-tier patterns, queue/status wording, validation checks, worker
recommendation ideas, and diagnostic report shapes. It also contains Telegram
listeners/senders, queue/state writes, runner subprocess discovery, watcher
loops, and repair/control behavior. This wrapper does not import or execute
Repo B code.

It does not dispatch workers, mutate queues, start listeners/watchers/daemons,
post Telegram output, run watchdog/repair, repair files, call models, execute
tools, access external systems, handle credentials, ingest raw private bodies,
mutate Mission Control Swift, sync/import Mac files, or push.
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
REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")

SCHEMA_VERSION = "repo_b_chief_offline_worker_wrapper_v0"
READ_MODEL_ID = "repo_b_chief_offline_worker_wrapper"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_BOUNDED_CHIEF_OFFLINE_WORKER_WRAPPER"

POSTURES = (
    "WRAP_AS_WORKER",
    "COMPUTE_ONLY",
    "READBACK_ONLY",
    "PROMOTE_SELECTED_MODULE",
    "REBUILD_SMALL_SUBSET_IN_REPO_A",
    "REFERENCE_ONLY",
    "UNSAFE_DO_NOT_CONNECT",
    "ALREADY_SUPERSEDED",
    "UNKNOWN_NEEDS_DEEPER_REVIEW",
)

CAPABILITY_TYPES = (
    "TASK_CLASSIFICATION",
    "ROUTE_SUGGESTION",
    "QUEUE_STATUS_SUMMARY",
    "WORK_PACKET_SHAPING",
    "NEXT_SAFE_MOVE",
    "BUILD_NOW_VS_HOLD",
    "DIAGNOSTIC_SUMMARY",
    "OPERATOR_BRIEFING",
    "WORKER_RECOMMENDATION",
    "MISSING_INFO_DETECTION",
    "UNKNOWN",
)

READBACK_STATUSES = (
    "CHIEF_READBACK_READY",
    "FIXTURE_READBACK_READY",
    "MISSING_INPUTS",
    "BLOCKED_PRIVACY_BOUNDARY",
    "BLOCKED_LIVE_DISPATCH",
    "BLOCKED_QUEUE_MUTATION",
    "WORKER_UNAVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "LIVE_DISPATCH_ATTEMPTED",
    "TELEGRAM_OUTPUT_ATTEMPTED",
    "LIVE_LISTENER_START_ATTEMPTED",
    "QUEUE_MUTATION_ATTEMPTED",
    "WATCHDOG_REPAIR_ATTEMPTED",
    "FILE_REPAIR_ATTEMPTED",
    "CREDENTIAL_OR_ENV_MUTATION_ATTEMPTED",
    "BROAD_FILESYSTEM_SCAN",
    "RAW_PRIVATE_BODY_INCLUDED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_chief_dispatch_allowed": False,
    "live_queue_mutation_allowed": False,
    "live_telegram_output_allowed": False,
    "live_listener_start_allowed": False,
    "live_watchdog_repair_allowed": False,
    "live_file_repair_allowed": False,
    "live_worker_execution_allowed": False,
    "live_model_call_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "repo_b_runtime_execution_allowed": False,
    "repo_b_service_start_allowed": False,
    "queue_read_live_allowed": False,
    "queue_write_allowed": False,
    "file_cleanup_allowed": False,
    "approval_execution_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "live Chief dispatch",
    "queue mutation",
    "Telegram input or output",
    "listener/watcher/daemon startup",
    "watchdog or repair loops",
    "file cleanup, archive, or rewrite actions",
    "worker execution",
    "model calls",
    "external actions",
    "credential or environment mutation",
    "raw private body ingestion",
)


@dataclass(frozen=True)
class RepoBChiefWorkerDecision:
    decision_id: str
    source_module: str
    source_path: str
    apparent_value: str
    dependencies: tuple[str, ...]
    recommended_posture: str
    wrapper_scope: tuple[str, ...]
    promotion_scope: tuple[str, ...]
    blocked_items: tuple[str, ...]
    privacy_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class ChiefOfflineCapability:
    capability_id: str
    source_module_ref: str
    capability_type: str
    description: str
    inputs_required: tuple[str, ...]
    outputs_produced: tuple[str, ...]
    deterministic: bool
    external_authority: bool
    queue_mutation_required: bool
    raw_private_data_required: bool
    wrapper_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ChiefOfflineWorkerRequest:
    request_id: str
    source_chat_request_ref: str
    world_ref: str
    folder_ref: str
    task_goal: str
    requested_capability: str
    source_context_refs: tuple[str, ...]
    source_readback_refs: tuple[str, ...]
    worker_candidates: tuple[str, ...]
    current_queue_summary_ref: str
    privacy_class: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class ChiefOfflineWorkerReadback:
    readback_id: str
    request_ref: str
    status: str
    safe_summary: str
    candidate_route: str
    candidate_worker: str
    candidate_next_safe_move: str
    missing_inputs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    warnings: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ChiefOfflineWorkerBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _repo_b_path(filename: str) -> str:
    return str(REPO_B_ROOT / filename)


def build_decisions() -> tuple[RepoBChiefWorkerDecision, ...]:
    return (
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_chief_router",
            source_module="chief_router.py",
            source_path=_repo_b_path("chief_router.py"),
            apparent_value="Large intent routing table, workflow sticky-session ideas, and fallback routing shape.",
            dependencies=("many Chief brain imports", "chief_llm.py", "session manager", "route log writes"),
            recommended_posture="REBUILD_SMALL_SUBSET_IN_REPO_A",
            wrapper_scope=("fixture-only task classification", "candidate route suggestion", "no Repo B import"),
            promotion_scope=("keyword route labels", "intent priority concepts", "fallback fail-closed posture"),
            blocked_items=("direct brain imports", "local LLM fallback", "route log writes", "approval decision writes", "external handler calls"),
            privacy_boundary="Chief offline receives scoped summaries and refs only, not raw chat transcripts or private bodies.",
            next_safe_move="Use Repo A worker routing and scoped context packages as truth; Chief offline can produce candidate route readbacks only.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_chief_listener",
            source_module="chief_listener.py",
            source_path=_repo_b_path("chief_listener.py"),
            apparent_value="Telegram-facing request loop and dispatch choreography.",
            dependencies=("Telegram bot token", "chief_router.py", "chief_sender paths", "subprocess inspection command"),
            recommended_posture="UNSAFE_DO_NOT_CONNECT",
            wrapper_scope=("none in v0",),
            promotion_scope=("operator-facing response sequencing concept",),
            blocked_items=("live Telegram listener", "Telegram replies", "subprocess inspection", "startup pending queue check", "external bot token dependency"),
            privacy_boundary="No Telegram messages or listener state are read or emitted by Repo A.",
            next_safe_move="Keep Mac chat and Repo A request processor as the operator surface; do not resurrect the Telegram listener path.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_session_manager",
            source_module="chief_session_manager.py",
            source_path=_repo_b_path("chief_session_manager.py"),
            apparent_value="Simple session-state schema and lifecycle vocabulary.",
            dependencies=("local state file", "file locks", "JSON state writes"),
            recommended_posture="PROMOTE_SELECTED_MODULE",
            wrapper_scope=("schema/reference only", "no state writes"),
            promotion_scope=("status labels", "active_workflow fields", "history/last question shape"),
            blocked_items=("live session load/save/reset", "state file mutation", "raw history exposure"),
            privacy_boundary="History and workflow_state bodies are not copied into generated read-models.",
            next_safe_move="Model session coordinates in Repo A memory/context packages instead of reading Repo B session state.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_queue_brain",
            source_module="chief_queue_brain.py",
            source_path=_repo_b_path("chief_queue_brain.py"),
            apparent_value="Queue item wording, pending/done status shape, and queue depth readback language.",
            dependencies=("queue log", "vault queue markdown", "chief_llm.py"),
            recommended_posture="READBACK_ONLY",
            wrapper_scope=("fixture queue/status summary", "no queue read/write in v0"),
            promotion_scope=("queue status labels", "pending item summary shape", "work packet wording"),
            blocked_items=("append queue", "mark done", "write queue markdown", "LLM item cleanup", "live queue file read"),
            privacy_boundary="No real queue rows or raw operator messages are read into the read-model.",
            next_safe_move="Use safe queue summary refs from Repo A when available; never mutate Repo B queue from this wrapper.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_reporter",
            source_module="chief_reporter_brain.py",
            source_path=_repo_b_path("chief_reporter_brain.py"),
            apparent_value="Operator briefing/digest shape and diagnostic counters.",
            dependencies=("worker logs", "watcher state", "chief_llm.py", "vault report writes"),
            recommended_posture="READBACK_ONLY",
            wrapper_scope=("safe fixture diagnostic summary", "operator briefing summary from readback refs"),
            promotion_scope=("briefing sections", "health warning language", "safe count summaries"),
            blocked_items=("raw log tail reads", "LLM report formatting", "vault report write", "listener/billing log inspection"),
            privacy_boundary="Only safe count summaries and readback refs are allowed; raw logs stay excluded.",
            next_safe_move="Feed Chief offline sanitized processor/readback status refs instead of raw logs.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_validator",
            source_module="chief_validator_brain.py",
            source_path=_repo_b_path("chief_validator_brain.py"),
            apparent_value="Reply sanity checks: traceback stripping, code-dump guard, length guard, and clean fallback messages.",
            dependencies=("chief_llm.py retry", "validation log", "output cleaner"),
            recommended_posture="PROMOTE_SELECTED_MODULE",
            wrapper_scope=("deterministic validation concepts only", "no LLM retry", "no log write"),
            promotion_scope=("traceback guard", "raw-code guard", "length guard", "safe fallback wording"),
            blocked_items=("LLM retry", "validation log writes", "Telegram-specific size assumptions as authority"),
            privacy_boundary="Validation examples do not include raw prompts or private reply bodies.",
            next_safe_move="Use these checks as local readback quality tests inside Repo A processors.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_watcher",
            source_module="chief_watcher_brain.py",
            source_path=_repo_b_path("chief_watcher_brain.py"),
            apparent_value="Alert detection and next-action-missing concepts for billing/album state.",
            dependencies=("billing tracker", "album state CSV", "approval pending file", "chief_sender subprocess", "infinite loop"),
            recommended_posture="REFERENCE_ONLY",
            wrapper_scope=("blocked in v0 except fixture warning labels",),
            promotion_scope=("alert type vocabulary", "missing next-action warning shape"),
            blocked_items=("infinite watcher loop", "Telegram send", "approval resend subprocess", "CSV reads", "watcher state writes"),
            privacy_boundary="No billing rows, album state rows, or watcher state files are read.",
            next_safe_move="If alerting is needed later, rebuild from Repo A receipts/readbacks with bounded run mode.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_approval_policy",
            source_module="chief_approval_policy.py",
            source_path=_repo_b_path("chief_approval_policy.py"),
            apparent_value="Approval tier classification patterns and fail-closed unknown-action posture.",
            dependencies=("environment flag", "autonomy mode file", "pattern lists"),
            recommended_posture="PROMOTE_SELECTED_MODULE",
            wrapper_scope=("classification concepts only", "no approval execution"),
            promotion_scope=("hard block patterns", "unknown defaults to high gate", "tier labels"),
            blocked_items=("live approval request", "Guardian/phone bridge", "autonomy mode file read"),
            privacy_boundary="Only generic policy categories are modeled, not pending approval bodies.",
            next_safe_move="Reference these policy ideas in Repo A Guardian/authority contracts without executing approvals.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_queue_balancer",
            source_module="queue_balancer.py",
            source_path=_repo_b_path("queue_balancer.py"),
            apparent_value="Build-now-vs-hold heuristics, task tier mix ideas, and queue health posture.",
            dependencies=("polish_loop tasks", "archive", "status json", "source/test tree scan", "logs"),
            recommended_posture="REBUILD_SMALL_SUBSET_IN_REPO_A",
            wrapper_scope=("fixture build-now-vs-hold readback", "candidate plan generation only"),
            promotion_scope=("tier vocabulary", "easy-win task shape", "queue health wording"),
            blocked_items=("task file generation", "broad repo scan", "archive reads", "status writes", "autopilot refill"),
            privacy_boundary="No task bodies, archive bodies, logs, or personal context docs are read.",
            next_safe_move="Use scoped work terrain/build cue readbacks instead of scanning the filesystem.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_runner_registry",
            source_module="runner_registry.py",
            source_path=_repo_b_path("runner_registry.py"),
            apparent_value="Worker recommendation vocabulary and runner capability inventory shape.",
            dependencies=("PATH scanning", "subprocess version/help calls", "plugin json", "runner cache writes"),
            recommended_posture="REFERENCE_ONLY",
            wrapper_scope=("static worker candidate labels only",),
            promotion_scope=("worker recommendation language", "runner strength/weakness tags"),
            blocked_items=("PATH scan", "subprocess runner discovery", "cache writes", "plugin loading"),
            privacy_boundary="No environment, PATH inventory, or plugin definitions are read by this wrapper.",
            next_safe_move="Use deterministic worker routing intelligence as current authority.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_queue_validator",
            source_module="queue_validator.py",
            source_path=_repo_b_path("queue_validator.py"),
            apparent_value="Pure markdown table validation state machine.",
            dependencies=("target queue markdown file if run as CLI",),
            recommended_posture="COMPUTE_ONLY",
            wrapper_scope=("future pure function over explicitly provided safe lines",),
            promotion_scope=("orphaned-row validation state machine",),
            blocked_items=("default queue file read", "raw task body exposure", "CLI mutation is not present but live file read remains gated"),
            privacy_boundary="The v0 wrapper does not read queue markdown bodies.",
            next_safe_move="Promote only a pure validator that accepts supplied safe text, if needed.",
        ),
        RepoBChiefWorkerDecision(
            decision_id="repo_b_chief_decision_live_workers",
            source_module="chief_worker.py / chief_state_worker.py / chief_memory_worker.py",
            source_path=_repo_b_path("chief_worker.py"),
            apparent_value="Legacy queue-to-state/memory worker loops.",
            dependencies=("input logs", "queue logs", "state CSV", "decision log", "infinite loops"),
            recommended_posture="UNSAFE_DO_NOT_CONNECT",
            wrapper_scope=("none in v0",),
            promotion_scope=("none in v0",),
            blocked_items=("infinite loop", "queue mutation", "state mutation", "memory log mutation", "raw input log read"),
            privacy_boundary="No legacy queue, state, memory, or input log bodies are read.",
            next_safe_move="Keep live worker-loop behavior out of Repo A; use bounded request processors and receipts instead.",
        ),
    )


def build_capabilities() -> tuple[ChiefOfflineCapability, ...]:
    rows: list[ChiefOfflineCapability] = [
        ChiefOfflineCapability(
            capability_id="chief_capability_task_classification",
            source_module_ref="repo_b_chief_decision_chief_router",
            capability_type="TASK_CLASSIFICATION",
            description="Classify a task goal into a candidate lane from safe text and scoped refs.",
            inputs_required=("task_goal_summary", "source_context_refs"),
            outputs_produced=("task_type_hint", "candidate_lane"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Use classification as advisory; Repo A router/readback remains current authority.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_route_suggestion",
            source_module_ref="repo_b_chief_decision_chief_router",
            capability_type="ROUTE_SUGGESTION",
            description="Suggest MAC_CODEX, PC_CODEX, GEMINI_AGY, Guardian, Cassandra, or workflow package compiler without dispatching.",
            inputs_required=("operator_goal", "worker_candidates", "current_scope_refs"),
            outputs_produced=("candidate_route", "candidate_worker", "warnings"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Return a candidate route card and require a separate package/worker lane to act.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_queue_status_summary",
            source_module_ref="repo_b_chief_decision_queue_brain",
            capability_type="QUEUE_STATUS_SUMMARY",
            description="Summarize safe queue metadata refs without reading or mutating live queues.",
            inputs_required=("current_queue_summary_ref",),
            outputs_produced=("queue_summary", "missing_queue_ref_warning"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Ask for a safe queue summary ref when no metadata is available.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_work_packet_shaping",
            source_module_ref="repo_b_chief_decision_queue_brain",
            capability_type="WORK_PACKET_SHAPING",
            description="Turn an operator goal into a bounded worker prompt outline for Repo A validation.",
            inputs_required=("task_goal", "scope_refs", "authority_boundary"),
            outputs_produced=("candidate_packet_outline", "validation_requirements", "blocked_actions"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Pass candidate outline through scoped context package/compiler contracts before use.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_next_safe_move",
            source_module_ref="repo_b_chief_decision_approval_policy",
            capability_type="NEXT_SAFE_MOVE",
            description="Recommend the next reversible, bounded move when a task is blocked or under-scoped.",
            inputs_required=("safe_summary", "blocked_items", "missing_inputs"),
            outputs_produced=("candidate_next_safe_move",),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Keep recommendations non-executing and proof/readback-based.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_build_now_vs_hold",
            source_module_ref="repo_b_chief_decision_queue_balancer",
            capability_type="BUILD_NOW_VS_HOLD",
            description="Suggest build-now, build-next, park, or clarify based on safe task metadata.",
            inputs_required=("task_goal", "known_context", "missing_inputs", "authority_risk"),
            outputs_produced=("candidate_posture", "reason", "next_safe_move"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Use as an advisory planning readback; do not create tasks automatically.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_diagnostic_summary",
            source_module_ref="repo_b_chief_decision_reporter",
            capability_type="DIAGNOSTIC_SUMMARY",
            description="Summarize safe readback/status refs into an operator diagnostic card.",
            inputs_required=("status_readback_refs", "error_summary_refs"),
            outputs_produced=("diagnostic_summary", "warning_list"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Use generated read-model refs, not raw logs.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_operator_briefing",
            source_module_ref="repo_b_chief_decision_reporter",
            capability_type="OPERATOR_BRIEFING",
            description="Produce a concise operator briefing from safe counts and readback refs.",
            inputs_required=("readback_refs", "safe_count_summaries"),
            outputs_produced=("operator_briefing",),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Keep briefing factual and grounded in readback refs.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_worker_recommendation",
            source_module_ref="repo_b_chief_decision_runner_registry",
            capability_type="WORKER_RECOMMENDATION",
            description="Recommend the appropriate worker type from static Repo A worker routing rules.",
            inputs_required=("task_type", "scope_refs", "blocked_workers"),
            outputs_produced=("candidate_worker", "alternate_workers"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Use Worker Routing Intelligence as the source of truth for final route.",
        ),
        ChiefOfflineCapability(
            capability_id="chief_capability_missing_info_detection",
            source_module_ref="repo_b_chief_decision_approval_policy",
            capability_type="MISSING_INFO_DETECTION",
            description="Identify missing inputs that prevent safe package compilation or execution claims.",
            inputs_required=("known_facts", "success_criteria", "required_proof"),
            outputs_produced=("missing_inputs", "blocked_items", "clarifying_question"),
            deterministic=True,
            external_authority=False,
            queue_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Ask the operator for missing proof/context instead of stuffing context or dispatching.",
        ),
    ]
    return tuple(rows)


def suggest_route(task_goal: str) -> tuple[str, str, str]:
    """Return candidate_route, candidate_worker, reason for fixture-safe text."""
    text = task_goal.lower()
    if "capital hilton" in text or "invoice workflow" in text:
        return (
            "workflow_execution_package_compiler / finance lane",
            "PC_CODEX",
            "Workflow preparation requires package planning, missing-piece navigation, and gated proof/readback checks.",
        )
    if any(word in text for word in ("swift", "mission control ui", "chat ui", "composer", "mac app")):
        return ("mac_app_ui_lane", "MAC_CODEX", "Apple/Mac-side app behavior belongs to Mac Codex.")
    if any(word in text for word in ("backend", "read-model", "readback", "python", "processor", "contract")):
        return ("repo_a_backend_lane", "PC_CODEX", "Repo A backend/read-model work belongs to PC Codex.")
    if any(word in text for word in ("audit", "review", "what should codex do", "scout")):
        return ("read_only_audit_lane", "GEMINI_AGY", "Read-only audit/prompt shaping belongs to Gemini/Agy.")
    if any(word in text for word in ("approval", "should this be allowed", "protected evidence")):
        return ("approval_boundary_lane", "GUARDIAN", "Sensitive boundary decisions belong to Guardian.")
    if any(word in text for word in ("draft", "email language", "client update")):
        return ("communications_draft_lane", "CASSANDRA", "Draft language belongs to Cassandra with no send authority.")
    return ("unknown_needs_routing", "UNKNOWN_NEEDS_ROUTING", "The request is too ambiguous for a safe worker choice.")


def build_packet_outline(task_goal: str) -> tuple[str, ...]:
    route, worker, reason = suggest_route(task_goal)
    return (
        f"Goal: {task_goal}",
        f"Candidate route: {route}",
        f"Candidate worker: {worker}",
        f"Reason: {reason}",
        "Include: scoped context refs, known facts, missing inputs, validation commands, expected return sections.",
        "Exclude: credentials, raw private bodies, queue mutation, live dispatch, external action.",
        "Return: STATUS, SUMMARY, RESULT, VALIDATION, COMMIT, BOUNDARY CHECK.",
    )


def build_request(fixture: str, generated_at: str = DEFAULT_GENERATED_AT) -> ChiefOfflineWorkerRequest:
    fixtures = {
        "route_suggestion": {
            "goal": "Where should this task go?",
            "capability": "ROUTE_SUGGESTION",
            "world_ref": "build",
            "folder_ref": "build/openclaw/routing",
            "context_refs": ("context_ref:operator_task_summary",),
            "readback_refs": ("readback_ref:worker_routing_intelligence",),
            "worker_candidates": ("MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "GUARDIAN", "CASSANDRA"),
            "queue_ref": "",
        },
        "queue_status": {
            "goal": "What work is currently active?",
            "capability": "QUEUE_STATUS_SUMMARY",
            "world_ref": "build",
            "folder_ref": "build/openclaw/work_queue",
            "context_refs": (),
            "readback_refs": ("readback_ref:request_processor_status",),
            "worker_candidates": ("PC_CODEX",),
            "queue_ref": "queue_summary_ref:fixture_safe_counts",
        },
        "work_packet": {
            "goal": "Turn this into a bounded worker prompt.",
            "capability": "WORK_PACKET_SHAPING",
            "world_ref": "build",
            "folder_ref": "build/openclaw/worker_packages",
            "context_refs": ("context_ref:scoped_task_summary",),
            "readback_refs": ("readback_ref:scoped_context_package_compiler",),
            "worker_candidates": ("PC_CODEX", "MAC_CODEX", "GEMINI_AGY"),
            "queue_ref": "",
        },
        "build_now_hold": {
            "goal": "Should we build this now or park it?",
            "capability": "BUILD_NOW_VS_HOLD",
            "world_ref": "build",
            "folder_ref": "build/openclaw/planning",
            "context_refs": ("context_ref:task_risk_summary",),
            "readback_refs": ("readback_ref:work_terrain_build_cue",),
            "worker_candidates": ("PC_CODEX", "GEMINI_AGY"),
            "queue_ref": "",
        },
        "capital_hilton": {
            "goal": "Make the Capital Hilton invoice workflow happen.",
            "capability": "ROUTE_SUGGESTION",
            "world_ref": "finance",
            "folder_ref": "finance/capital_hilton/invoices",
            "context_refs": ("context_ref:capital_hilton_readiness_summary",),
            "readback_refs": ("readback_ref:workflow_execution_package_compiler",),
            "worker_candidates": ("PC_CODEX", "CASSANDRA", "GUARDIAN"),
            "queue_ref": "",
        },
        "telegram_blocker": {
            "goal": "Post this update to Telegram.",
            "capability": "UNKNOWN",
            "world_ref": "build",
            "folder_ref": "build/openclaw/boundaries",
            "context_refs": (),
            "readback_refs": (),
            "worker_candidates": ("UNKNOWN_NEEDS_ROUTING",),
            "queue_ref": "",
        },
        "watchdog_blocker": {
            "goal": "Run the repair watcher and clean up broken files.",
            "capability": "UNKNOWN",
            "world_ref": "build",
            "folder_ref": "build/openclaw/boundaries",
            "context_refs": (),
            "readback_refs": (),
            "worker_candidates": ("UNKNOWN_NEEDS_ROUTING",),
            "queue_ref": "",
        },
    }
    if fixture not in fixtures:
        raise ValueError(f"Unsupported fixture: {fixture}")
    item = fixtures[fixture]
    return ChiefOfflineWorkerRequest(
        request_id=f"chief_offline_request_{fixture}_v0",
        source_chat_request_ref=f"fixture_chat:{fixture}",
        world_ref=item["world_ref"],
        folder_ref=item["folder_ref"],
        task_goal=item["goal"],
        requested_capability=item["capability"],
        source_context_refs=tuple(item["context_refs"]),
        source_readback_refs=tuple(item["readback_refs"]),
        worker_candidates=tuple(item["worker_candidates"]),
        current_queue_summary_ref=item["queue_ref"],
        privacy_class="operator_local_private",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        created_at=generated_at,
    )


def build_fixture_readback(request: ChiefOfflineWorkerRequest) -> ChiefOfflineWorkerReadback:
    fixture = request.request_id.replace("chief_offline_request_", "").replace("_v0", "")
    if fixture == "telegram_blocker":
        return ChiefOfflineWorkerReadback(
            readback_id="chief_offline_readback_telegram_blocked_v0",
            request_ref=request.request_id,
            status="BLOCKED_LIVE_DISPATCH",
            safe_summary="Chief offline blocked Telegram output. This wrapper cannot send, post, or start Telegram paths.",
            candidate_route="blocked_external_output",
            candidate_worker="UNKNOWN_NEEDS_ROUTING",
            candidate_next_safe_move="Route communications through a future governed adapter only after explicit approval.",
            missing_inputs=("approved communications adapter", "operator approval", "send/post receipt plan"),
            blocked_actions=("Telegram output", "external action", "live dispatch"),
            warnings=("No message was sent or posted.",),
            next_safe_move="Return a blocked card explaining that Telegram output is outside Chief offline v0.",
        )
    if fixture == "watchdog_blocker":
        return ChiefOfflineWorkerReadback(
            readback_id="chief_offline_readback_watchdog_blocked_v0",
            request_ref=request.request_id,
            status="BLOCKED_QUEUE_MUTATION",
            safe_summary="Chief offline blocked repair/watchdog behavior. It cannot run cleanup, repair, restart, or queue mutation loops.",
            candidate_route="blocked_repair_runtime",
            candidate_worker="UNKNOWN_NEEDS_ROUTING",
            candidate_next_safe_move="Create a bounded diagnostic package instead of running repair.",
            missing_inputs=("scoped diagnostic target", "non-destructive validation command", "approval for any future mutation"),
            blocked_actions=("watchdog repair", "file repair", "queue mutation", "listener start"),
            warnings=("No repair loop was started.", "No files or queues were changed."),
            next_safe_move="Ask the operator whether to prepare a read-only diagnostic package.",
        )
    if fixture == "queue_status":
        return ChiefOfflineWorkerReadback(
            readback_id="chief_offline_readback_queue_status_fixture_v0",
            request_ref=request.request_id,
            status="FIXTURE_READBACK_READY",
            safe_summary="Chief can summarize safe queue metadata refs, but it cannot read or mutate live queues in v0.",
            candidate_route="queue_status_readback_only",
            candidate_worker="PC_CODEX",
            candidate_next_safe_move="Use the existing request processor/status read-models or provide a safe queue summary ref.",
            missing_inputs=() if request.current_queue_summary_ref else ("safe queue summary ref",),
            blocked_actions=("queue mutation", "live queue read", "service control"),
            warnings=("This is a fixture/status-shape readback, not a live queue inspection.",),
            next_safe_move="Keep queue/status as readback-only until a governed queue metadata rail exists.",
        )
    if fixture == "work_packet":
        return ChiefOfflineWorkerReadback(
            readback_id="chief_offline_readback_work_packet_fixture_v0",
            request_ref=request.request_id,
            status="FIXTURE_READBACK_READY",
            safe_summary="Chief shaped a candidate worker prompt outline for Repo A to validate and package separately.",
            candidate_route="scoped_context_package_compiler",
            candidate_worker="PC_CODEX",
            candidate_next_safe_move="Compile the candidate outline through Repo A package/context rails before sending to any worker.",
            missing_inputs=("target worker", "exact file scope", "validation commands"),
            blocked_actions=("auto task creation", "queue mutation", "worker dispatch"),
            warnings=("Candidate packet only; Repo A package compiler remains authority.",),
            next_safe_move="Ask for target worker and file scope, then generate a scoped package plan.",
        )
    if fixture == "build_now_hold":
        return ChiefOfflineWorkerReadback(
            readback_id="chief_offline_readback_build_now_hold_fixture_v0",
            request_ref=request.request_id,
            status="FIXTURE_READBACK_READY",
            safe_summary="Chief recommends building now only when scope, proof, and validation are clear; otherwise park or clarify.",
            candidate_route="work_terrain_build_cue",
            candidate_worker="PC_CODEX",
            candidate_next_safe_move="Build now if bounded and reversible; park when missing scope or authority is broad.",
            missing_inputs=("acceptance criteria", "source refs", "authority boundary") ,
            blocked_actions=("autonomous task creation", "queue refill", "worker execution"),
            warnings=("Recommendation is advisory and non-executing.",),
            next_safe_move="Use Work Terrain / Build Cue readback to decide build-now vs hold.",
        )
    route, worker, reason = suggest_route(request.task_goal)
    if fixture == "capital_hilton":
        return ChiefOfflineWorkerReadback(
            readback_id="chief_offline_readback_capital_hilton_fixture_v0",
            request_ref=request.request_id,
            status="FIXTURE_READBACK_READY",
            safe_summary="Chief routes Capital Hilton make-it-happen intent to the workflow execution package compiler and finance lane.",
            candidate_route=route,
            candidate_worker=worker,
            candidate_next_safe_move="Compile readiness and package plans; do not send email, access Coupa, or request approval execution.",
            missing_inputs=("exact Coupa PO/reference", "confirmed Annette contact route", "final artifact/hash", "Guardian approval", "send/submit receipts"),
            blocked_actions=("email send", "Coupa access/submit", "approval execution", "workflow execution"),
            warnings=("This is routing guidance only; nothing has been sent or submitted.", reason),
            next_safe_move="Run or show the workflow execution package compiler readback for missing pieces and package plan.",
        )
    return ChiefOfflineWorkerReadback(
        readback_id="chief_offline_readback_route_suggestion_fixture_v0",
        request_ref=request.request_id,
        status="FIXTURE_READBACK_READY",
        safe_summary="Chief produced a candidate worker route without dispatching, executing, or mutating queues.",
        candidate_route=route,
        candidate_worker=worker,
        candidate_next_safe_move=reason,
        missing_inputs=("specific task content", "scope refs", "validation expectations"),
        blocked_actions=("live dispatch", "worker execution", "queue mutation"),
        warnings=("Candidate route only; Worker Routing Intelligence remains current authority.",),
        next_safe_move="Ask for the concrete task or pass the request to Worker Routing Intelligence for deterministic routing.",
    )


def build_blockers() -> tuple[ChiefOfflineWorkerBlocker, ...]:
    messages = {
        "LIVE_DISPATCH_ATTEMPTED": ("Dispatch this to a worker now.", "Chief offline cannot dispatch workers."),
        "TELEGRAM_OUTPUT_ATTEMPTED": ("Post this update to Telegram.", "Chief offline cannot send or post Telegram output."),
        "LIVE_LISTENER_START_ATTEMPTED": ("Start the Chief listener.", "Listener startup is blocked."),
        "QUEUE_MUTATION_ATTEMPTED": ("Add this to the queue or mark queue done.", "Queue mutation is blocked."),
        "WATCHDOG_REPAIR_ATTEMPTED": ("Run the watcher repair loop.", "Watchdog/repair loops are blocked."),
        "FILE_REPAIR_ATTEMPTED": ("Clean up or rewrite broken files.", "File repair/cleanup requires a separate approved lane."),
        "CREDENTIAL_OR_ENV_MUTATION_ATTEMPTED": ("Change bot token, env, or credentials.", "Credential/env mutation is blocked."),
        "BROAD_FILESYSTEM_SCAN": ("Scan the whole runtime for issues.", "Broad filesystem scans are blocked."),
        "RAW_PRIVATE_BODY_INCLUDED": ("Include raw logs, chats, queue bodies, or private text.", "Raw private bodies are blocked."),
        "EXTERNAL_ACTION_ATTEMPTED": ("Send, submit, approve, post, or access an external system.", "External action is blocked."),
        "UNKNOWN_FAIL_CLOSED": ("Unknown Chief worker action.", "Unknown actions fail closed."),
    }
    rows: list[ChiefOfflineWorkerBlocker] = []
    for blocker_type, (condition, warning) in messages.items():
        rows.append(
            ChiefOfflineWorkerBlocker(
                blocker_id=f"chief_offline_blocker_{blocker_type.lower()}",
                blocker_type=blocker_type,
                condition=condition,
                severity="critical" if blocker_type != "UNKNOWN_FAIL_CLOSED" else "high",
                elioperator_warning=warning,
                fail_closed=True,
                next_safe_move="Keep Chief offline to candidate readbacks, route suggestions, and safe package shaping.",
            )
        )
    return tuple(rows)


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    fixture_names = (
        "route_suggestion",
        "queue_status",
        "work_packet",
        "build_now_hold",
        "capital_hilton",
        "telegram_blocker",
        "watchdog_blocker",
    )
    examples: dict[str, Any] = {}
    for name in fixture_names:
        request = build_request(name, generated_at)
        readback = build_fixture_readback(request)
        examples[name] = {
            "operator_input": request.task_goal,
            "request": asdict(request),
            "readback": asdict(readback),
        }
    return {
        "route_suggestion": examples["route_suggestion"],
        "queue_status_summary": examples["queue_status"],
        "work_packet_shaping": examples["work_packet"],
        "build_now_vs_hold": examples["build_now_hold"],
        "capital_hilton_routing": examples["capital_hilton"],
        "telegram_output_blocker": examples["telegram_blocker"],
        "watchdog_repair_blocker": examples["watchdog_blocker"],
    }


def build_payload(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    selected_fixture: str | None = None,
) -> dict[str, Any]:
    decisions = build_decisions()
    capabilities = build_capabilities()
    blockers = build_blockers()
    examples = build_examples(generated_at)
    selected_request = build_request(selected_fixture, generated_at) if selected_fixture else None
    selected_readback = build_fixture_readback(selected_request) if selected_request else None
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "repo_b_root": str(REPO_B_ROOT),
        "postures": POSTURES,
        "capability_types": CAPABILITY_TYPES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "chief_worker_decisions": [asdict(row) for row in decisions],
        "offline_capabilities": [asdict(row) for row in capabilities],
        "chief_offline_blockers": [asdict(row) for row in blockers],
        "wrapper_plan": {
            "posture": "WRAP_AS_OFFLINE_READBACK_WORKER_WITH_PROMOTED_DETERMINISTIC_SUBSET",
            "safe_capabilities": tuple(cap.capability_id for cap in capabilities if cap.wrapper_allowed),
            "blocked_capabilities": tuple(blocker.blocker_type for blocker in blockers if blocker.blocker_type != "UNKNOWN_FAIL_CLOSED"),
            "repo_b_invocation": "none in v0",
            "fixture_mode": True,
            "source_ref_mode": True,
            "promotion_scope": (
                "routing labels and candidate route wording",
                "reply validation guard concepts",
                "approval-tier classification ideas",
                "queue/status readback shape",
                "build-now-vs-hold posture",
            ),
            "excluded_scope": COMMON_BLOCKED_ACTIONS,
            "next_safe_move": "Use Chief offline for candidate route/readback/package-shaping cards only; Repo A rails remain authority.",
        },
        "examples": examples,
        "selected_fixture": selected_fixture,
        "selected_request": asdict(selected_request) if selected_request else None,
        "selected_readback": asdict(selected_readback) if selected_readback else None,
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "repo_b_code_imported": False,
            "repo_b_runtime_executed": False,
            "live_chief_dispatch_performed": False,
            "queue_mutation_performed": False,
            "telegram_output_performed": False,
            "listener_started": False,
            "watchdog_repair_performed": False,
            "file_repair_performed": False,
            "worker_execution_performed": False,
            "model_call_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_private_body_exposure": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "Repo B Chief has useful routing, queue/status, validation, approval-policy, and briefing shapes, "
            "but v0 keeps it offline and fixture/source-ref based. Live dispatch, queue mutation, Telegram, "
            "listener startup, watchdog/repair, file repair, model calls, credentials, raw bodies, and external actions are blocked."
        ),
        "next_safe_move": "Use Chief offline as an advisory card generator behind Repo A request/context/package rails.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    selected = payload.get("selected_readback") or payload["examples"]["route_suggestion"]["readback"]
    lines = [
        "# Repo B Chief Offline Worker Wrapper",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Posture",
        f"- Wrapper posture: {payload['wrapper_plan']['posture']}",
        "- Repo B invocation: none in v0",
        "- Output type: candidate route/readback/package-shaping cards only",
        "",
        "## Safe Capabilities",
    ]
    for capability in payload["offline_capabilities"]:
        lines.append(f"- {capability['capability_type']}: {capability['description']}")
    lines += ["", "## Blocked Capabilities"]
    for blocker in payload["chief_offline_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Example Readback",
        f"- Status: {selected['status']}",
        f"- Candidate worker: {selected['candidate_worker']}",
        f"- Candidate route: {selected['candidate_route']}",
        f"- Next safe move: {selected['next_safe_move']}",
        "",
        "## Boundary",
        "No live Chief dispatch, no queue mutation, no Telegram output, no listener start, no watchdog/repair, no file repair, no worker execution, no model call, no external action, no credentials, no raw private body exposure.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    selected = payload.get("selected_readback")
    return {
        "read_model_id": payload["read_model_id"],
        "posture": payload["wrapper_plan"]["posture"],
        "selected_fixture": payload.get("selected_fixture"),
        "selected_status": selected["status"] if selected else None,
        "safe_capabilities": len(payload["wrapper_plan"]["safe_capabilities"]),
        "blocked_capabilities": len(payload["wrapper_plan"]["blocked_capabilities"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Repo B Chief offline worker wrapper read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument(
        "--fixture",
        choices=(
            "route_suggestion",
            "queue_status",
            "work_packet",
            "build_now_hold",
            "capital_hilton",
            "telegram_blocker",
            "watchdog_blocker",
        ),
        default=None,
        help="Include a selected fixture request/readback for run mode.",
    )
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(generated_at=args.generated_at, selected_fixture=args.fixture)
    write_exports(payload, export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(stable_json(_summary(payload, export_root)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
