"""Repo B Worker Boundary Harness v0.

This deterministic read-model defines the generic pattern for wrapping selected
Repo B subsystems as bounded Repo A workers. It models worker candidates, input
packages, output readbacks, timeout policy, authority boundaries, and quarantine
blockers. It does not start Repo B services, import unsafe live modules, call
workers, post Telegram messages, send email, write Google data, mutate files,
handle credentials, ingest raw bodies, dispatch agents, run workflows, mutate
Mission Control Swift, sync Mac, or push.
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

SCHEMA_VERSION = "repo_b_worker_boundary_harness_v0"
READ_MODEL_ID = "repo_b_worker_boundary_harness"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_REPO_B_WORKER_BOUNDARY_HARNESS"

WORKER_FAMILIES = (
    "CHIEF_ROUTER",
    "CASSANDRA_DRAFT",
    "GOOGLE_READ_BROKER",
    "CPA_BUDGET",
    "NILES_MUSIC_CREATIVE",
    "QUEUE_RUNNER",
    "TELEGRAM_INTAKE",
    "WATCHDOG_REPAIR",
    "UNKNOWN",
)

RECOMMENDED_POSTURES = (
    "WRAP_AS_WORKER",
    "BRIDGE_READ_ONLY",
    "DRAFT_ONLY",
    "COMPUTE_ONLY",
    "REFERENCE_ONLY",
    "PROMOTE_SELECTED_MODULE",
    "UNSAFE_DO_NOT_CONNECT",
    "UNKNOWN_NEEDS_DEEPER_REVIEW",
)

INVOCATION_MODES = (
    "FIXTURE_ONLY",
    "BOUNDED_SUBPROCESS",
    "READ_ONLY_BRIDGE",
    "DRAFT_ONLY_BRIDGE",
    "COMPUTE_ONLY_BRIDGE",
    "NONE",
)

READBACK_STATUSES = (
    "WORKER_READBACK_READY",
    "FIXTURE_READBACK_READY",
    "WORKER_UNAVAILABLE",
    "WORKER_TIMEOUT",
    "BLOCKED_UNSAFE_WORKER",
    "BLOCKED_EXTERNAL_ACTION",
    "BLOCKED_CREDENTIAL_REQUIRED",
    "BLOCKED_RAW_BODY_RISK",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "LIVE_SERVICE_START_ATTEMPTED",
    "TELEGRAM_OUTBOUND_ATTEMPTED",
    "EMAIL_SEND_ATTEMPTED",
    "GOOGLE_WRITE_ATTEMPTED",
    "CREDENTIAL_INCLUDED",
    "RAW_PRIVATE_BODY_INCLUDED",
    "UNSCOPED_CONTEXT_PACKAGE",
    "UNBOUNDED_RUNTIME",
    "WATCHDOG_REPAIR_ATTEMPTED",
    "BROAD_FILE_SCAN_ATTEMPTED",
    "DIRECT_IMPORT_OF_UNSAFE_MODULE",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_worker_execution_allowed": False,
    "live_repo_b_service_start_allowed": False,
    "live_telegram_output_allowed": False,
    "live_email_send_allowed": False,
    "live_google_write_allowed": False,
    "live_file_mutation_allowed": False,
    "live_watchdog_repair_allowed": False,
    "live_external_action_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_workflow_run_allowed": False,
    "live_model_call_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_ENV_FLAGS = {
    "OPENCLAW_WORKER_BOUNDARY": "1",
    "OPENCLAW_FIXTURE_ONLY": "1",
    "OPENCLAW_SEND_ALLOWED": "0",
    "OPENCLAW_WRITE_ALLOWED": "0",
    "OPENCLAW_TELEGRAM_ALLOWED": "0",
    "OPENCLAW_CREDENTIALS_ALLOWED": "0",
    "OPENCLAW_RAW_BODY_ALLOWED": "0",
    "OPENCLAW_EXTERNAL_ACTION_ALLOWED": "0",
}

COMMON_FORBIDDEN_ACTIONS = (
    "start Repo B service/listener/watcher/daemon",
    "send email",
    "post Telegram output",
    "write Google data",
    "handle credentials",
    "include raw private bodies",
    "mutate files outside generated readbacks",
    "run autonomous repair",
)


@dataclass(frozen=True)
class RepoBWorkerBoundaryHarness:
    harness_id: str
    doctrine: tuple[str, ...]
    repo_b_root: str
    worker_classification_policy: tuple[str, ...]
    wrapper_policy: tuple[str, ...]
    subprocess_policy: tuple[str, ...]
    fixture_policy: tuple[str, ...]
    timeout_policy: str
    tokenization_policy: tuple[str, ...]
    output_readback_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class LegacyWorkerCandidate:
    candidate_id: str
    repo_b_path: str
    worker_name: str
    worker_family: str
    apparent_value: str
    interdependencies: tuple[str, ...]
    recommended_posture: str
    allowed_invocation_mode: str
    forbidden_invocation_modes: tuple[str, ...]
    risk_level: str
    required_wrapper: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkerInputPackage:
    input_package_id: str
    target_worker_candidate_ref: str
    source_context_package_ref: str
    workflow_ref: str
    task_goal: str
    allowed_context_refs: tuple[str, ...]
    excluded_context: tuple[str, ...]
    tokenized_refs: tuple[str, ...]
    protected_refs: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    timeout_ms: int
    environment_flags: dict[str, str]
    next_safe_move: str


@dataclass(frozen=True)
class WorkerOutputReadback:
    readback_id: str
    worker_candidate_ref: str
    input_package_ref: str
    status: str
    safe_summary: str
    candidate_output_refs: tuple[str, ...]
    tokenized_outputs: tuple[str, ...]
    protected_refs: tuple[str, ...]
    blocked_items: tuple[str, ...]
    errors: tuple[str, ...]
    operator_message: str
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkerTimeoutPolicy:
    policy_id: str
    default_timeout_ms: int
    max_timeout_ms: int
    kill_on_timeout: bool
    timeout_readback_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkerAuthorityBoundary:
    boundary_id: str
    worker_candidate_ref: str
    external_action_allowed: bool
    network_allowed: bool
    credential_handling_allowed: bool
    raw_body_ingestion_allowed: bool
    file_mutation_allowed: bool
    send_allowed: bool
    submit_allowed: bool
    approval_required: bool
    allowed_side_effects: tuple[str, ...]
    forbidden_side_effects: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkerQuarantineBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class RepoBWorkerBoundaryElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: tuple[str, ...]
    what_this_does_not_do_yet: tuple[str, ...]
    how_repo_b_workers_are_wrapped: tuple[str, ...]
    how_outputs_return_to_chat: tuple[str, ...]
    how_safety_boundaries_work: tuple[str, ...]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _repo_b_path(name: str) -> str:
    return str(REPO_B_ROOT / name)


def build_harness() -> RepoBWorkerBoundaryHarness:
    return RepoBWorkerBoundaryHarness(
        harness_id="repo_b_worker_boundary_harness_v0",
        doctrine=(
            "Repo A remains the canonical deterministic substrate.",
            "Repo B workers are candidates, not current authority by default.",
            "Wrap useful Repo B subsystems behind scoped packages and safe readbacks.",
            "Worker outputs are candidate readbacks until Repo A validates or receipts them.",
            "Unsafe workers are quarantined instead of copied or started blindly.",
        ),
        repo_b_root=str(REPO_B_ROOT),
        worker_classification_policy=(
            "Classify by worker family, side effects, dependencies, credential needs, and output shape.",
            "Prefer fixture-only modeling until an explicit wrapper proves bounded behavior.",
            "Mark service/listener/watchdog workers unsafe unless a separate intake-only/read-only adapter exists.",
        ),
        wrapper_policy=(
            "Context packages are scoped and include explicit exclusions.",
            "No raw credentials, secrets, raw private bodies, or protected bodies cross the boundary.",
            "Repo B output is tokenized or summarized before normal Repo A read-model exposure.",
            "Every blocked/failed readback includes how_to_fix.",
        ),
        subprocess_policy=(
            "Use bounded subprocess only for approved callable workers.",
            "Set safe-mode environment flags before subprocess invocation.",
            "Default timeout is 5000ms and timeout requires a terminal readback.",
            "Do not directly import unsafe live modules into Repo A runtime.",
        ),
        fixture_policy=(
            "Fixture mode is the default for harness examples.",
            "Fixture readbacks prove shape and safety without executing Repo B.",
            "Fixture outputs must not imply live worker execution.",
        ),
        timeout_policy="worker_timeout_policy_default_5000ms",
        tokenization_policy=(
            "Token refs and protected refs may cross the boundary.",
            "Raw PII/private values must not be written to normal read-models.",
            "Legacy worker output is not chat-visible until sanitized.",
        ),
        output_readback_policy=(
            "Readbacks carry status, safe summary, candidate output refs, blockers, and how_to_fix.",
            "Mac chat receives human operator messages, not raw worker dumps.",
            "Repo A receipts/readbacks decide truth.",
        ),
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Use this harness to decide whether a Repo B subsystem should be fixture-only, wrapped, promoted, or quarantined.",
    )


def build_timeout_policy() -> WorkerTimeoutPolicy:
    return WorkerTimeoutPolicy(
        policy_id="worker_timeout_policy_default_5000ms",
        default_timeout_ms=5000,
        max_timeout_ms=15000,
        kill_on_timeout=True,
        timeout_readback_required=True,
        next_safe_move="If a worker exceeds timeout, kill the subprocess and return WORKER_TIMEOUT with a human fix path.",
    )


def build_candidates() -> tuple[LegacyWorkerCandidate, ...]:
    rows = (
        LegacyWorkerCandidate(
            candidate_id="repo_b_candidate_chief_offline_reasoning",
            repo_b_path=_repo_b_path("chief_router.py"),
            worker_name="Chief offline reasoning worker",
            worker_family="CHIEF_ROUTER",
            apparent_value="Candidate reasoning, queue summary, and task-shape suggestions from mature Chief routing context.",
            interdependencies=("chief_llm.py", "chief_queue_brain.py", "chief_worker.py", "approval and Telegram paths nearby"),
            recommended_posture="WRAP_AS_WORKER",
            allowed_invocation_mode="FIXTURE_ONLY",
            forbidden_invocation_modes=("live dispatch", "Telegram output", "queue mutation", "unbounded service start"),
            risk_level="medium_high",
            required_wrapper="offline_summary_fixture_or_future_bounded_subprocess_without_dispatch",
            next_safe_move="Keep output as candidate task/readback summary until Repo A validates it.",
        ),
        LegacyWorkerCandidate(
            candidate_id="repo_b_candidate_cassandra_draft_only",
            repo_b_path=_repo_b_path("cassandra_brain.py"),
            worker_name="Cassandra draft-only worker",
            worker_family="CASSANDRA_DRAFT",
            apparent_value="Candidate communication drafts from scoped/tokenized context.",
            interdependencies=("chief_email_brain.py", "cassandra_outreach.py", "chief_llm.py", "approval and Telegram paths nearby"),
            recommended_posture="DRAFT_ONLY",
            allowed_invocation_mode="DRAFT_ONLY_BRIDGE",
            forbidden_invocation_modes=("send", "live Gmail/Mail access", "Telegram output", "credential access", "raw email body exposure"),
            risk_level="medium",
            required_wrapper="cassandra_draft_worker_wrapper.py",
            next_safe_move="Use Repo A draft wrapper unless Repo B exposes a safe no-send draft callable later.",
        ),
        LegacyWorkerCandidate(
            candidate_id="repo_b_candidate_google_read_broker",
            repo_b_path=_repo_b_path("google_access_broker.py"),
            worker_name="Google read-only broker",
            worker_family="GOOGLE_READ_BROKER",
            apparent_value="Contacts, calendar, and Gmail metadata reads through existing broker policy.",
            interdependencies=("google_access_policy.py", "local protected Google token files", "Repo A tokenization wrapper"),
            recommended_posture="BRIDGE_READ_ONLY",
            allowed_invocation_mode="READ_ONLY_BRIDGE",
            forbidden_invocation_modes=("Gmail send", "calendar/contact write", "Gmail body read", "attachment read/download"),
            risk_level="high_if_unwrapped",
            required_wrapper="google_broker_readonly_wrapper.py",
            next_safe_move="Use only the audited read-only wrapper and tokenize output before chat/read-model exposure.",
        ),
        LegacyWorkerCandidate(
            candidate_id="repo_b_candidate_cpa_budget_compute",
            repo_b_path=_repo_b_path("budget_tracker.py"),
            worker_name="CPA budget calculator",
            worker_family="CPA_BUDGET",
            apparent_value="Local deterministic budget and CPA-style calculations.",
            interdependencies=("chief_cpa_brain.py", "chief_financial_brain.py", "business logs"),
            recommended_posture="COMPUTE_ONLY",
            allowed_invocation_mode="COMPUTE_ONLY_BRIDGE",
            forbidden_invocation_modes=("bank login", "payments", "tax filing", "credential access", "external account reads"),
            risk_level="medium",
            required_wrapper="future_budget_compute_wrapper_with_fixture_tests",
            next_safe_move="Promote pure calculation helpers or wrap compute-only functions with generated readbacks.",
        ),
        LegacyWorkerCandidate(
            candidate_id="repo_b_candidate_niles_music_creative",
            repo_b_path=_repo_b_path("chief_album_brain.py"),
            worker_name="Niles/music creative worker",
            worker_family="NILES_MUSIC_CREATIVE",
            apparent_value="Setlist, album, session, and creative suggestions from scoped music context.",
            interdependencies=("chief_album_batch.py", "chief_album_mixer.py", "chief_fundo_session.py", "music/project files nearby"),
            recommended_posture="WRAP_AS_WORKER",
            allowed_invocation_mode="FIXTURE_ONLY",
            forbidden_invocation_modes=("DAW mutation", "file mutation", "external posting", "broad media folder scans"),
            risk_level="medium",
            required_wrapper="future_music_creative_context_wrapper",
            next_safe_move="Use scoped music context summaries and no project/file mutation.",
        ),
        LegacyWorkerCandidate(
            candidate_id="repo_b_candidate_telegram_listener_intake",
            repo_b_path=_repo_b_path("cassandra_listener.py"),
            worker_name="Telegram listener intake",
            worker_family="TELEGRAM_INTAKE",
            apparent_value="Possible future operator intake or message normalization reference.",
            interdependencies=("chief_listener.py", "chief_sender.py", "cassandra_sender.py", "bot token environment"),
            recommended_posture="REFERENCE_ONLY",
            allowed_invocation_mode="NONE",
            forbidden_invocation_modes=("live listener", "outbound posting", "bot token access", "daemon start"),
            risk_level="high",
            required_wrapper="future_intake_only_adapter_if_explicitly_approved",
            next_safe_move="Reference shape only; do not start or post from this harness.",
        ),
        LegacyWorkerCandidate(
            candidate_id="repo_b_candidate_watchdog_repair",
            repo_b_path=_repo_b_path("loop_dashboard_watchdog.sh"),
            worker_name="Watchdog/repair worker",
            worker_family="WATCHDOG_REPAIR",
            apparent_value="Legacy repair/restart knowledge and operational heuristics.",
            interdependencies=("cassandra_watcher.py", "chief_watcher_brain.py", "polish_loop/orchestrator.py", "runner scripts"),
            recommended_posture="UNSAFE_DO_NOT_CONNECT",
            allowed_invocation_mode="NONE",
            forbidden_invocation_modes=("auto repair", "file mutation", "environment mutation", "restart loops", "daemon/watchdog activation"),
            risk_level="critical",
            required_wrapper="quarantine_only_reference_card",
            next_safe_move="Keep quarantined; extract lessons manually into Repo A contracts if useful.",
        ),
    )
    return rows


def build_input_package(candidate: LegacyWorkerCandidate) -> WorkerInputPackage:
    allowed_actions_by_family = {
        "CHIEF_ROUTER": ("produce offline candidate task/readback summary",),
        "CASSANDRA_DRAFT": ("produce candidate draft text from tokenized/scoped context",),
        "GOOGLE_READ_BROKER": ("return tokenized metadata through audited wrapper only",),
        "CPA_BUDGET": ("perform local deterministic calculations",),
        "NILES_MUSIC_CREATIVE": ("produce scoped creative suggestions",),
        "TELEGRAM_INTAKE": ("reference intake shape only",),
        "WATCHDOG_REPAIR": ("reference lessons only",),
    }
    mode_flags = dict(COMMON_ENV_FLAGS)
    if candidate.worker_family == "GOOGLE_READ_BROKER":
        mode_flags["OPENCLAW_GOOGLE_BRIDGE_MODE"] = "READ_ONLY"
        mode_flags["OPENCLAW_GOOGLE_BODY_ALLOWED"] = "0"
    if candidate.worker_family == "CASSANDRA_DRAFT":
        mode_flags["OPENCLAW_CASSANDRA_MODE"] = "DRAFT_ONLY"
        mode_flags["OPENCLAW_GMAIL_ALLOWED"] = "0"
    return WorkerInputPackage(
        input_package_id=f"repo_b_input_package_{candidate.candidate_id}",
        target_worker_candidate_ref=candidate.candidate_id,
        source_context_package_ref="generated/read_models/scoped_context_package_compiler_contract.json",
        workflow_ref=f"repo_b_boundary_example_{candidate.worker_family.lower()}",
        task_goal=candidate.apparent_value,
        allowed_context_refs=(
            "scoped_context_package_ref",
            "tokenized_source_refs",
            "repo_a_readback_refs",
        ),
        excluded_context=(
            "raw credentials",
            "raw secrets",
            "raw private bodies",
            "protected evidence bodies",
            "external account bodies",
            "unrelated project history",
        ),
        tokenized_refs=(f"tokenized_context_ref_{candidate.worker_family.lower()}",),
        protected_refs=(f"protected_boundary_ref_{candidate.worker_family.lower()}",),
        allowed_actions=allowed_actions_by_family.get(candidate.worker_family, ("none",)),
        forbidden_actions=COMMON_FORBIDDEN_ACTIONS,
        timeout_ms=5000,
        environment_flags=mode_flags,
        next_safe_move="Use fixture mode or a specifically approved wrapper; do not invoke live Repo B behavior from this harness.",
    )


def build_authority_boundary(candidate: LegacyWorkerCandidate) -> WorkerAuthorityBoundary:
    return WorkerAuthorityBoundary(
        boundary_id=f"repo_b_authority_boundary_{candidate.candidate_id}",
        worker_candidate_ref=candidate.candidate_id,
        external_action_allowed=False,
        network_allowed=False,
        credential_handling_allowed=False,
        raw_body_ingestion_allowed=False,
        file_mutation_allowed=False,
        send_allowed=False,
        submit_allowed=False,
        approval_required=candidate.worker_family in {"CASSANDRA_DRAFT", "GOOGLE_READ_BROKER", "TELEGRAM_INTAKE"},
        allowed_side_effects=("generated/read_models readback write only",),
        forbidden_side_effects=COMMON_FORBIDDEN_ACTIONS,
        next_safe_move="Keep boundary false by default; add a separate audited adapter before any live authority.",
    )


def build_output_readback(candidate: LegacyWorkerCandidate, package: WorkerInputPackage) -> WorkerOutputReadback:
    if candidate.recommended_posture == "UNSAFE_DO_NOT_CONNECT":
        status = "BLOCKED_UNSAFE_WORKER"
        blocked = ("Watchdog/repair workers are quarantined.",)
        operator_message = "This Repo B worker is useful as historical reference only; it must not be connected or started."
        how_to_fix = "Extract the lesson into a Repo A contract or create a new reviewed wrapper for one narrow behavior."
        refs: tuple[str, ...] = ()
    elif candidate.allowed_invocation_mode == "NONE":
        status = "BLOCKED_UNSAFE_WORKER"
        blocked = ("Live listener/intake activation is blocked in this harness.",)
        operator_message = "This worker is reference-only in v0. No live listener, token, or outbound posting is allowed."
        how_to_fix = "Create an intake-only adapter later with explicit operator approval and no outbound behavior."
        refs = ()
    else:
        status = "FIXTURE_READBACK_READY"
        blocked = ()
        operator_message = f"{candidate.worker_name} is modeled as a bounded candidate worker. No Repo B code ran."
        how_to_fix = "Use the required wrapper before any live invocation; keep the fixture readback as the safety shape."
        refs = (f"candidate_output_ref_{candidate.worker_family.lower()}",)
    return WorkerOutputReadback(
        readback_id=f"repo_b_worker_readback_{candidate.candidate_id}",
        worker_candidate_ref=candidate.candidate_id,
        input_package_ref=package.input_package_id,
        status=status,
        safe_summary=f"{candidate.worker_name}: {candidate.recommended_posture} / {candidate.allowed_invocation_mode}.",
        candidate_output_refs=refs,
        tokenized_outputs=(f"tokenized_output_ref_{candidate.worker_family.lower()}",) if refs else (),
        protected_refs=package.protected_refs,
        blocked_items=blocked,
        errors=(),
        operator_message=operator_message,
        how_to_fix=how_to_fix,
        next_safe_move=candidate.next_safe_move,
    )


def build_blockers() -> tuple[WorkerQuarantineBlocker, ...]:
    definitions = (
        ("LIVE_SERVICE_START_ATTEMPTED", "A wrapper tried to start a Repo B listener/service/daemon."),
        ("TELEGRAM_OUTBOUND_ATTEMPTED", "A worker tried to post or notify through Telegram."),
        ("EMAIL_SEND_ATTEMPTED", "A worker tried to send email or create send authority."),
        ("GOOGLE_WRITE_ATTEMPTED", "A worker tried to create/update/delete Google data."),
        ("CREDENTIAL_INCLUDED", "A package included raw credential material."),
        ("RAW_PRIVATE_BODY_INCLUDED", "A package included raw private body content."),
        ("UNSCOPED_CONTEXT_PACKAGE", "A package lacked scoped context and exclusions."),
        ("UNBOUNDED_RUNTIME", "A worker run lacked timeout or terminal readback."),
        ("WATCHDOG_REPAIR_ATTEMPTED", "A worker tried autonomous repair/restart behavior."),
        ("BROAD_FILE_SCAN_ATTEMPTED", "A worker tried broad filesystem scanning."),
        ("DIRECT_IMPORT_OF_UNSAFE_MODULE", "Repo A attempted to import an unsafe live Repo B module directly."),
        ("UNKNOWN_FAIL_CLOSED", "The worker boundary could not prove safety."),
    )
    return tuple(
        WorkerQuarantineBlocker(
            blocker_id=f"repo_b_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="high" if blocker_type != "UNKNOWN_FAIL_CLOSED" else "critical",
            elioperator_warning=condition,
            fail_closed=True,
            next_safe_move="Stop the worker path, return a blocked readback, and require a narrower wrapper or fixture.",
        )
        for blocker_type, condition in definitions
    )


def build_report() -> RepoBWorkerBoundaryElioperatorReport:
    return RepoBWorkerBoundaryElioperatorReport(
        report_id="repo_b_worker_boundary_elioperator_report_v0",
        plain_summary="Repo B can supply useful worker ideas and selected bounded workers, but Repo A must wrap, sanitize, time-limit, and receipt them before chat sees results.",
        what_this_enables=(
            "Classify legacy workers by value and risk.",
            "Generate scoped worker input packages with exclusions.",
            "Return token-safe candidate readbacks to Repo A and Mac chat.",
            "Quarantine unsafe services, listeners, and repair loops.",
        ),
        what_this_does_not_do_yet=(
            "No live Repo B worker execution.",
            "No service/watchdog/listener startup.",
            "No Telegram/email/Google write action.",
            "No credential handling or raw body ingestion.",
        ),
        how_repo_b_workers_are_wrapped=(
            "Repo A creates a scoped context package.",
            "The boundary wrapper selects fixture, read-only, draft-only, or compute-only posture.",
            "Future subprocess runs must carry safe env flags and timeout.",
            "Output is sanitized before normal read-model exposure.",
        ),
        how_outputs_return_to_chat=(
            "Worker output becomes a Repo A readback first.",
            "Mac chat receives safe summaries, blockers, and next steps.",
            "Raw worker dumps stay below deck.",
        ),
        how_safety_boundaries_work=(
            "Default live authority is false.",
            "Credentials, raw bodies, sends, posts, writes, and repairs are blocked.",
            "Unsafe candidates fail closed with how_to_fix.",
        ),
        next_safe_move="Use this harness as the common decision layer before adding any new Repo B wrapper.",
    )


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    candidates = build_candidates()
    packages = tuple(build_input_package(candidate) for candidate in candidates)
    package_by_candidate = {package.target_worker_candidate_ref: package for package in packages}
    readbacks = tuple(build_output_readback(candidate, package_by_candidate[candidate.candidate_id]) for candidate in candidates)
    boundaries = tuple(build_authority_boundary(candidate) for candidate in candidates)
    blockers = build_blockers()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "worker_families": WORKER_FAMILIES,
        "recommended_postures": RECOMMENDED_POSTURES,
        "allowed_invocation_modes": INVOCATION_MODES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "harness": asdict(build_harness()),
        "worker_timeout_policy": asdict(build_timeout_policy()),
        "worker_candidates": tuple(asdict(candidate) for candidate in candidates),
        "worker_input_packages": tuple(asdict(package) for package in packages),
        "worker_output_readbacks": tuple(asdict(readback) for readback in readbacks),
        "worker_authority_boundaries": tuple(asdict(boundary) for boundary in boundaries),
        "worker_quarantine_blockers": tuple(asdict(blocker) for blocker in blockers),
        "elioperator_report": asdict(build_report()),
        "examples": {
            "chief": "repo_b_candidate_chief_offline_reasoning",
            "cassandra": "repo_b_candidate_cassandra_draft_only",
            "google_broker": "repo_b_candidate_google_read_broker",
            "cpa_budget": "repo_b_candidate_cpa_budget_compute",
            "niles_music": "repo_b_candidate_niles_music_creative",
            "telegram": "repo_b_candidate_telegram_listener_intake",
            "watchdog_repair": "repo_b_candidate_watchdog_repair",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "machine_proof": {
            "models_present": True,
            "chief_example_exists": True,
            "cassandra_draft_example_exists": True,
            "google_read_broker_example_exists": True,
            "cpa_budget_compute_example_exists": True,
            "niles_music_example_exists": True,
            "telegram_outbound_blocked": any(blocker.blocker_type == "TELEGRAM_OUTBOUND_ATTEMPTED" for blocker in blockers),
            "watchdog_repair_blocked": any(blocker.blocker_type == "WATCHDOG_REPAIR_ATTEMPTED" for blocker in blockers),
            "timeout_policy_exists": True,
            "live_worker_execution_performed": False,
            "repo_b_service_start_performed": False,
            "telegram_output_performed": False,
            "email_send_performed": False,
            "google_write_performed": False,
            "file_mutation_performed": False,
            "watchdog_repair_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_run": False,
            "mission_control_swift_changed": False,
            "git_push_pull_fetch_run": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["elioperator_report"]
    candidates = payload["worker_candidates"]
    lines = [
        "# Repo B Worker Boundary Harness",
        "",
        report["plain_summary"],
        "",
        "What this enables:",
    ]
    lines.extend(f"- {item}" for item in report["what_this_enables"])
    lines.extend(["", "Worker examples:"])
    for candidate in candidates:
        lines.append(
            f"- {candidate['worker_name']}: {candidate['recommended_posture']} via {candidate['allowed_invocation_mode']}"
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- No Repo B worker executed.",
            "- No Repo B service/listener/watcher/daemon started.",
            "- Telegram output, email send, Google write, file mutation, watchdog repair, credentials, and raw bodies are blocked.",
            "",
            f"Next safe move: {report['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    candidates = payload["worker_candidates"]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "candidate_count": len(candidates),
        "postures": sorted({candidate["recommended_posture"] for candidate in candidates}),
        "blocked_examples": {
            "telegram": "repo_b_candidate_telegram_listener_intake",
            "watchdog_repair": "repo_b_candidate_watchdog_repair",
        },
        "timeout_ms": payload["worker_timeout_policy"]["default_timeout_ms"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "next_safe_move": payload["harness"]["next_safe_move"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Repo B worker boundary harness read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    paths = write_exports(payload, Path(args.export_root))
    output = payload if args.format == "json" else build_summary(payload, paths)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
