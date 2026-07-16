#!/usr/bin/env python3
"""Finite Phase-C worker runtime.

The control plane owns admission, leases, and acceptance. This module is the
small runtime bridge that turns one live lease into one bounded local builder
invocation, then reports candidate evidence or failure back to the ledger.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:  # pragma: no cover - package import
    from .control_plane import (
        LOOP_DIR,
        ControlPlaneLedger,
        TaskLease,
        iso_now,
    )
except ImportError:  # pragma: no cover - script import from polish_loop/
    from control_plane import (  # type: ignore
        LOOP_DIR,
        ControlPlaneLedger,
        TaskLease,
        iso_now,
    )

try:  # pragma: no cover - package import
    from .gpu_arbiter import DEFAULT_TTL_SECONDS as GPU_DEFAULT_TTL_SECONDS
    from .gpu_arbiter import GPUArbiter
except ImportError:  # pragma: no cover - script import from polish_loop/
    from gpu_arbiter import DEFAULT_TTL_SECONDS as GPU_DEFAULT_TTL_SECONDS  # type: ignore
    from gpu_arbiter import GPUArbiter  # type: ignore

try:  # pragma: no cover - package import
    from .capability_availability_router import route_build_capability
except ImportError:  # pragma: no cover - script import from polish_loop/
    from capability_availability_router import route_build_capability  # type: ignore

try:  # pragma: no cover - package import
    from .model_unload_adapter import DEFAULT_OLLAMA_BASE_URL, unload_model
except ImportError:  # pragma: no cover - script import from polish_loop/
    from model_unload_adapter import DEFAULT_OLLAMA_BASE_URL, unload_model  # type: ignore

try:  # pragma: no cover - package import
    from .build_lifecycle_registry import BuildLifecycleRegistry
except ImportError:  # pragma: no cover - script import from polish_loop/
    from build_lifecycle_registry import BuildLifecycleRegistry  # type: ignore


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
# Real, absolute defaults for the standalone/production entry point
# (WorkerRuntimeConfig.from_env()). Tests always construct WorkerRuntimeConfig
# directly with a tmp_path-scoped loop_dir, so lease_db_path/lifecycle_db_path stay
# None there and resolve underneath that tmp_path instead -- see
# _resolve_lease_db_path()/_resolve_lifecycle_db_path() below.
DEFAULT_GPU_LEASE_DB_PATH = Path("/home/openclaw/.openclaw/polish_loop/gpu_leases.sqlite")
DEFAULT_BUILD_LIFECYCLE_DB_PATH = Path("/home/openclaw/.openclaw/polish_loop/build_lifecycle.sqlite")
TASK_PACKAGE_FLAG = "OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1"
TASK_PACKAGE_FLAG_ON_VALUES = {"1", "true", "yes", "on"}
TASK_PACKAGE_SCHEMA_VERSION = "polish_loop_task_package_v1"
TASK_PACKAGE_REQUIRED_PAYLOAD_FIELDS = (
    "goal",
    "success_criteria",
    "tests_to_run",
    "allowed_files",
    "forbidden_actions",
    "stop_conditions",
)


class TaskPackageError(ValueError):
    """Raised when a ledger task cannot be safely materialized for a builder."""

    def __init__(self, message: str, *, missing_fields: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.missing_fields = tuple(missing_fields)


@dataclasses.dataclass(frozen=True)
class WorkerRuntimeConfig:
    """Paths and limits for one finite local builder invocation."""

    python: str = sys.executable
    local_builder_path: Path = LOOP_DIR / "local_builder.py"
    loop_dir: Path = LOOP_DIR
    task_path: Path = LOOP_DIR / "task.md"
    pc_output_path: Path = LOOP_DIR / "current" / "pc_output.md"
    artifact_dir: Path = LOOP_DIR / "current"
    repo_root: Path | None = None
    worktree: Path | None = None
    branch: str = "unknown"
    model: str = "qwen3:8b-q4_K_M"
    fallback_model: str = "ornith:9b"
    timeout_seconds: int = 3600
    subprocess_timeout_seconds: int | None = None
    extra_env: dict[str, str] = dataclasses.field(default_factory=dict)
    # Resource-aware GPU lease + build lifecycle provenance wiring. Left as None by
    # default (rather than defaulting to a real /home/openclaw path) so that any
    # config built directly -- which is what every existing test does -- resolves
    # these underneath loop_dir instead of touching real machine state. Only
    # from_env() (the true production entry point) resolves to the real default
    # paths above.
    lease_db_path: Path | None = None
    lifecycle_db_path: Path | None = None
    gpu_lease_ttl_seconds: int = GPU_DEFAULT_TTL_SECONDS
    gpu_heartbeat_interval_seconds: float = 120.0
    gpu_holder_id: str | None = None
    model_unload_base_url: str = DEFAULT_OLLAMA_BASE_URL

    def resolved_lease_db_path(self) -> Path:
        return Path(self.lease_db_path) if self.lease_db_path is not None else self.loop_dir / "gpu_leases.sqlite"

    def resolved_lifecycle_db_path(self) -> Path:
        return (
            Path(self.lifecycle_db_path)
            if self.lifecycle_db_path is not None
            else self.loop_dir / "build_lifecycle.sqlite"
        )

    @classmethod
    def from_env(cls) -> "WorkerRuntimeConfig":
        return cls(
            python=os.environ.get("PHASE_C_WORKER_PYTHON", sys.executable),
            local_builder_path=Path(
                os.environ.get("PHASE_C_LOCAL_BUILDER", str(LOOP_DIR / "local_builder.py"))
            ),
            loop_dir=Path(os.environ.get("PHASE_C_LOOP_DIR", str(LOOP_DIR))),
            task_path=Path(os.environ.get("PHASE_C_TASK_MD", str(LOOP_DIR / "task.md"))),
            pc_output_path=Path(
                os.environ.get("PHASE_C_PC_OUTPUT", str(LOOP_DIR / "current" / "pc_output.md"))
            ),
            artifact_dir=Path(
                os.environ.get("PHASE_C_ARTIFACT_DIR", str(LOOP_DIR / "current"))
            ),
            repo_root=(
                Path(os.environ["PHASE_C_REPO_ROOT"])
                if os.environ.get("PHASE_C_REPO_ROOT")
                else None
            ),
            worktree=(
                Path(os.environ["PHASE_C_WORKTREE"])
                if os.environ.get("PHASE_C_WORKTREE")
                else None
            ),
            branch=os.environ.get("PHASE_C_BRANCH", "unknown"),
            model=os.environ.get("PHASE_C_BUILDER_MODEL", "qwen3:8b-q4_K_M"),
            fallback_model=os.environ.get("PHASE_C_BUILDER_FALLBACK_MODEL", "ornith:9b"),
            timeout_seconds=int(os.environ.get("PHASE_C_BUILDER_TIMEOUT", "3600")),
            subprocess_timeout_seconds=(
                int(os.environ["PHASE_C_WORKER_SUBPROCESS_TIMEOUT"])
                if os.environ.get("PHASE_C_WORKER_SUBPROCESS_TIMEOUT")
                else None
            ),
            lease_db_path=Path(
                os.environ.get("PHASE_C_GPU_LEASE_DB", str(DEFAULT_GPU_LEASE_DB_PATH))
            ),
            lifecycle_db_path=Path(
                os.environ.get("PHASE_C_BUILD_LIFECYCLE_DB", str(DEFAULT_BUILD_LIFECYCLE_DB_PATH))
            ),
            gpu_lease_ttl_seconds=int(
                os.environ.get("PHASE_C_GPU_LEASE_TTL", str(GPU_DEFAULT_TTL_SECONDS))
            ),
            gpu_heartbeat_interval_seconds=float(
                os.environ.get("PHASE_C_GPU_HEARTBEAT_INTERVAL", "120")
            ),
            model_unload_base_url=os.environ.get(
                "PHASE_C_MODEL_UNLOAD_BASE_URL", DEFAULT_OLLAMA_BASE_URL
            ),
        )


def _installed_ollama_models() -> "set[str] | None":
    """Best-effort set of installed ollama model tags, or None if undeterminable."""
    import json
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as resp:
            data = json.loads(resp.read())
        return {m.get("name") for m in data.get("models", []) if m.get("name")}
    except Exception:
        return None


def select_builder_model(
    *,
    primary: str,
    fallback: "str | None",
    attempt_no: int,
    available_models: "set[str] | None" = None,
) -> str:
    """Select only box-safe builder models until a governor lease exists."""
    safe_models = frozenset({"qwen3:8b-q4_K_M", "ornith:9b"})
    safe_primary = str(primary or "").strip()
    if safe_primary not in safe_models:
        safe_primary = "qwen3:8b-q4_K_M"
    fb = (fallback or "").strip()
    if fb not in safe_models:
        fb = ""
    if not fb or int(attempt_no) < 2:
        return safe_primary
    if available_models is not None and fb not in available_models:
        return safe_primary
    return fb


@dataclasses.dataclass(frozen=True)
class WorkerRuntimeResult:
    task_id: str
    exit_code: int | None
    submitted_candidate: bool
    failure_recorded: bool
    artifact_path: Path
    pc_output_path: Path
    fingerprint: str | None = None
    task_md_path: Path | None = None
    # Honest resource-aware deferral: neither a success nor a failure. The local
    # model was never invoked because route_build_capability() or the GPU arbiter
    # said not to (interactive session active, or the lease was contended). Callers
    # must not record this as a builder failure -- see
    # orchestrator._record_local_builder_result()'s early deferred check.
    deferred: bool = False
    defer_reason: str | None = None


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _safe_id(value: str) -> str:
    return _SAFE_ID_RE.sub("_", value).strip("._") or "task"


def _tail(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def task_package_enabled(enabled: bool | None = None) -> bool:
    if enabled is not None:
        return bool(enabled)
    return os.environ.get(TASK_PACKAGE_FLAG, "").strip().lower() in TASK_PACKAGE_FLAG_ON_VALUES


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def _compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _payload_digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_compact_json(dict(payload)).encode("utf-8")).hexdigest()


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_nonempty(item) for item in value)
    return value is not None


def _payload_value(payload: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in payload:
            return payload.get(name)
    return default


def _list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, Mapping):
        return [f"{key}: {value[key]}" for key in sorted(value)]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _render_list(values: Sequence[str]) -> str:
    if not values:
        return "- not_specified"
    return "\n".join(f"- {value}" for value in values)


def _acceptance_ref_text(value: Any) -> str:
    if value in (None, ""):
        return "not_provided"
    if isinstance(value, (Mapping, list, tuple)):
        return _compact_json(value)
    return str(value)


_LEDGER_BUILD_CONTEXT_FACT_LIMIT = 8


def build_polish_loop_build_context_packet(
    *, goal: str = "", db_path: "str | Path | None" = None
) -> dict[str, Any]:
    """Ledger-grounded system-context packet for the polish-loop builder.

    Routes the builder's "what already exists / where things live" grounding through the SAME shared
    business-ops-ledger source the agents use (context_source), so the builder reasons over the real
    system and every fact carries ledger provenance -- enforced by the context-packet ledger contract.
    """
    import context_source

    return context_source.build_ledger_context_packet(
        question=goal,
        agent_id="polish_loop_builder",
        db_path=db_path,
        limit=_LEDGER_BUILD_CONTEXT_FACT_LIMIT,
        packet_id_prefix="polish_loop_build_context",
    )


def _render_ledger_system_context(goal: str = "") -> str:
    """A bounded, ledger-grounded 'System Context' section for the build package (fail-soft)."""
    try:
        facts = build_polish_loop_build_context_packet(goal=goal).get("facts") or []
    except Exception:  # never block a build on a ledger hiccup
        return "(ledger system-context unavailable; build proceeds without it)"
    if not facts:
        return "(no ledger system-context facts matched)"
    lines = []
    for fact in facts:
        label = str(fact.get("label") or fact.get("topic") or "").strip()
        value = str(fact.get("value") or "").strip()
        ref = str(fact.get("source_ref") or "")
        lines.append(f"- {label}: {value}" + (f" (source: {ref})" if ref else ""))
    return "\n".join(lines)


def build_task_package_markdown(
    row: Mapping[str, Any],
    lease: TaskLease,
    *,
    repo_root: str | Path,
    worktree: str | Path,
    branch: str,
) -> str:
    """Build a deterministic, nonce-bound task package for a live ledger lease."""

    payload_raw = row.get("payload") or {}
    if not isinstance(payload_raw, Mapping):
        raise TaskPackageError("task payload must be a JSON object", missing_fields=("payload",))
    payload = dict(payload_raw)

    missing = [
        field
        for field in TASK_PACKAGE_REQUIRED_PAYLOAD_FIELDS
        if not _nonempty(_payload_value(payload, field, "tests" if field == "tests_to_run" else field))
    ]
    if missing:
        raise TaskPackageError(
            f"task package missing required fields: {', '.join(missing)}",
            missing_fields=tuple(missing),
        )

    tests = _list_value(_payload_value(payload, "tests_to_run", "tests"))
    fields: list[tuple[str, str]] = [
        ("schema_version", TASK_PACKAGE_SCHEMA_VERSION),
        ("task_id", lease.task_id),
        ("task_type", str(row.get("type") or "")),
        ("source", str(row.get("source") or "")),
        ("ledger_db", str(row.get("ledger_db") or row.get("_ledger_db") or "not_provided")),
        ("lease_owner", lease.owner),
        ("lease_nonce", lease.lease_nonce),
        ("attempt_no", str(lease.attempt_no)),
        ("repo_root", str(repo_root)),
        ("worktree", str(worktree)),
        ("branch", str(branch or "unknown")),
        ("payload_digest", _payload_digest(payload)),
    ]
    for optional_field in ("failure_class", "class_scope"):
        value = _payload_value(payload, optional_field)
        if _nonempty(value):
            fields.append((optional_field, str(value).strip()))
    sibling_evidence = _payload_value(payload, "sibling_evidence", default=[])
    if _nonempty(sibling_evidence):
        fields.append(("sibling_evidence", _compact_json(sibling_evidence)))
    sections: list[tuple[str, str]] = [
        ("Goal", str(_payload_value(payload, "goal")).strip()),
        ("Scope", _render_list(_list_value(_payload_value(payload, "scope", default=[])))),
        ("Success Criteria", _render_list(_list_value(_payload_value(payload, "success_criteria")))),
        ("Allowed Files", _render_list(_list_value(_payload_value(payload, "allowed_files")))),
        ("Forbidden Files", _render_list(_list_value(_payload_value(payload, "forbidden_files", default=[])))),
        ("Allowed Actions", _render_list(_list_value(_payload_value(payload, "allowed_actions", default=[])))),
        ("Forbidden Actions", _render_list(_list_value(_payload_value(payload, "forbidden_actions")))),
        ("Tests To Run", _render_list(tests)),
        ("Acceptance Ref", _acceptance_ref_text(row.get("acceptance_ref"))),
        ("Stop Conditions", _render_list(_list_value(_payload_value(payload, "stop_conditions")))),
        ("Output Contract", _render_list(_list_value(_payload_value(payload, "output_contract", default=[])))),
        (
            "Help Or Escalation Route",
            _render_list(_list_value(_payload_value(payload, "help_or_escalation_route", default=[]))),
        ),
        (
            "Rollback Expectation",
            _render_list(_list_value(_payload_value(payload, "rollback_expectation", default=[]))),
        ),
        (
            "Production Prohibitions",
            _render_list(_list_value(_payload_value(payload, "production_prohibitions", default=[]))),
        ),
        ("Sibling Evidence", _acceptance_ref_text(sibling_evidence)),
        (
            "System Context (ledger-grounded)",
            _render_ledger_system_context(str(_payload_value(payload, "goal")).strip()),
        ),
    ]

    lines = [f"{name}: {value}" for name, value in fields]
    lines.extend(["", "# Polish Loop Task Package v1", ""])
    for title, body in sections:
        lines.extend([f"## {title}", "", body, ""])
    lines.extend(["## Payload JSON", "", "```json", _stable_json(payload), "```", ""])
    return "\n".join(lines)


def _task_markdown(row: dict[str, Any], lease: TaskLease) -> str:
    payload = row.get("payload") or {}
    return "\n".join(
        [
            f"task_id: {lease.task_id}",
            f"task_type: {row.get('type')}",
            f"source: {row.get('source')}",
            "execution_mode: phase-c-worker-runtime",
            f"lease_owner: {lease.owner}",
            f"attempt: {lease.attempt_no}",
            "",
            "# Phase-C Worker Runtime Task",
            "",
            "The SQLite control-plane ledger is authoritative for this task.",
            "Use this materialized file only as the finite worker input for the live lease.",
            "",
            "Payload JSON:",
            json.dumps(payload, indent=2, sort_keys=True),
            "",
            "Runtime rules:",
            "- Produce candidate evidence in pc_output.md.",
            "- Do not claim or inspect another task.",
            "- Do not send external messages, spend money, restart production, or access Legal material.",
        ]
    )


def _write_artifact(
    artifact_path: Path,
    *,
    lease: TaskLease,
    command: list[str],
    exit_code: int,
    stdout: str,
    stderr: str,
    pc_output_path: Path,
    detail: dict[str, Any] | None = None,
) -> None:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "task_id": lease.task_id,
                "owner": lease.owner,
                "attempt_no": lease.attempt_no,
                "finished_at": iso_now(),
                "command": command,
                "exit_code": exit_code,
                "pc_output_path": str(pc_output_path),
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
                "detail": detail or {},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def run_local_builder_worker(
    ledger: ControlPlaneLedger,
    lease: TaskLease,
    *,
    config: WorkerRuntimeConfig | None = None,
    runner: Runner = subprocess.run,
) -> WorkerRuntimeResult:
    """Run exactly one local builder process for an already-held lease."""

    cfg = config or WorkerRuntimeConfig.from_env()
    row = ledger.get_task(lease.task_id)
    if (
        row["status"] != "LEASED"
        or row["owner"] != lease.owner
        or row["lease_nonce"] != lease.lease_nonce
        or int(row["attempts"]) != int(lease.attempt_no)
    ):
        raise RuntimeError(f"lease is not live for task {lease.task_id}")

    cfg.task_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.pc_output_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.artifact_dir.mkdir(parents=True, exist_ok=True)
    package_row = dict(row)
    package_row["_ledger_db"] = str(ledger.path)
    if task_package_enabled():
        task_markdown = build_task_package_markdown(
            package_row,
            lease,
            repo_root=cfg.repo_root or cfg.loop_dir.parent,
            worktree=cfg.worktree or cfg.loop_dir.parent,
            branch=cfg.branch,
        )
    else:
        task_markdown = _task_markdown(row, lease)
    cfg.task_path.write_text(task_markdown, encoding="utf-8")
    cfg.pc_output_path.unlink(missing_ok=True)

    chosen_model = select_builder_model(
        primary=cfg.model,
        fallback=cfg.fallback_model,
        attempt_no=lease.attempt_no,
        available_models=_installed_ollama_models(),
    )
    command = [
        cfg.python,
        str(cfg.local_builder_path),
        "--model",
        chosen_model,
        "--timeout",
        str(cfg.timeout_seconds),
    ]
    artifact_path = (
        cfg.artifact_dir
        / f"worker_runtime_{_safe_id(lease.task_id)}_attempt_{lease.attempt_no}.json"
    )

    # --- Resource-aware GPU routing + leasing -------------------------------
    #
    # Before invoking a local model, ask the capability/availability router
    # whether this is even a good time to run (policy-level: defers while an
    # interactive GPU lease is active), then actually acquire a "build" GPU
    # lease (mechanism-level: catches races the router's snapshot read can't
    # see, e.g. another concurrent build already holding it). Both layers
    # honor "defer" by NOT invoking the model and NOT touching the ledger's
    # task/lease state -- the live lease is left exactly as claim_task() left
    # it, so it will either be retried by the caller or reclaimed by
    # ControlPlaneLedger.recover_expired_leases() when it naturally expires.
    # Every routing/leasing decision is recorded in the Build Lifecycle
    # Registry, including deferrals and denials, so the trail is honest even
    # when no build actually happened.
    build_unit_id = f"{lease.task_id}:{lease.attempt_no}"
    lifecycle = BuildLifecycleRegistry(cfg.resolved_lifecycle_db_path())
    lifecycle.record(
        build_unit_id,
        "requested",
        task_id=lease.task_id,
        attempt_no=lease.attempt_no,
        detail={"owner": lease.owner, "model": chosen_model},
    )

    lease_db_path = cfg.resolved_lease_db_path()
    routing_decision = route_build_capability(
        "",
        lease_db_path=lease_db_path,
        local_model=(chosen_model, "worker_runtime_selected_model"),
    )
    if routing_decision.get("status") == "defer":
        defer_reason = str(routing_decision.get("decision_reason") or "defer")
        lifecycle.record(
            build_unit_id,
            "deferred",
            task_id=lease.task_id,
            attempt_no=lease.attempt_no,
            reason=defer_reason,
            detail=routing_decision,
        )
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=None,
            submitted_candidate=False,
            failure_recorded=False,
            artifact_path=artifact_path,
            pc_output_path=cfg.pc_output_path,
            task_md_path=cfg.task_path,
            deferred=True,
            defer_reason=defer_reason,
        )
    lifecycle.record(
        build_unit_id,
        "routed",
        task_id=lease.task_id,
        attempt_no=lease.attempt_no,
        reason=str(routing_decision.get("decision_reason") or ""),
        detail=routing_decision,
    )

    arbiter = GPUArbiter(lease_db_path)
    gpu_holder_id = cfg.gpu_holder_id or f"polish_loop_build:{lease.owner}:{build_unit_id}"
    gpu_lease = arbiter.acquire("build", gpu_holder_id, ttl_seconds=cfg.gpu_lease_ttl_seconds)

    if gpu_lease.get("status") == "denied":
        defer_reason = f"gpu_lease_{gpu_lease.get('reason') or 'denied'}"
        lifecycle.record(
            build_unit_id,
            "lease_denied",
            task_id=lease.task_id,
            attempt_no=lease.attempt_no,
            reason=str(gpu_lease.get("reason") or ""),
            detail=gpu_lease,
        )
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=None,
            submitted_candidate=False,
            failure_recorded=False,
            artifact_path=artifact_path,
            pc_output_path=cfg.pc_output_path,
            task_md_path=cfg.task_path,
            deferred=True,
            defer_reason=defer_reason,
        )

    # Defensive: per the current arbiter policy a "build" acquire never carries
    # preemption_required itself (only an interactive acquire that preempts a
    # build does), but honor the flag generically and unconditionally in case
    # that policy widens later -- a builder that is told it preempted/should
    # yield unloads its own model before proceeding rather than assuming it
    # can never apply to itself.
    if gpu_lease.get("preemption_required") or gpu_lease.get("recommended_keep_alive") == "0":
        unload_model(chosen_model, base_url=cfg.model_unload_base_url)

    lifecycle.record(
        build_unit_id,
        "leased",
        task_id=lease.task_id,
        attempt_no=lease.attempt_no,
        detail=gpu_lease,
    )

    gpu_lease_nonce = str(gpu_lease.get("lease_nonce") or "")
    stop_heartbeat = threading.Event()
    was_preempted = threading.Event()

    def _heartbeat_loop() -> None:
        while not stop_heartbeat.wait(cfg.gpu_heartbeat_interval_seconds):
            beat = arbiter.heartbeat(gpu_holder_id, gpu_lease_nonce, ttl_seconds=cfg.gpu_lease_ttl_seconds)
            if beat.get("status") != "heartbeat_recorded":
                was_preempted.set()
                try:
                    unload_model(chosen_model, base_url=cfg.model_unload_base_url)
                except Exception:  # noqa: BLE001 - never let cleanup crash the build
                    pass
                break

    heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    lifecycle.record(build_unit_id, "running", task_id=lease.task_id, attempt_no=lease.attempt_no)

    env = os.environ.copy()
    env.update(cfg.extra_env)
    env.update(
        {
            "PHASE_C_LEDGER_DB": str(ledger.path),
            "PHASE_C_TASK_ID": lease.task_id,
            "PHASE_C_LEASE_OWNER": lease.owner,
            "PHASE_C_LEASE_NONCE": lease.lease_nonce,
            "PHASE_C_ATTEMPT_NO": str(lease.attempt_no),
            "PHASE_C_TASK_MD": str(cfg.task_path),
            "PHASE_C_PC_OUTPUT": str(cfg.pc_output_path),
        }
    )
    timeout = cfg.subprocess_timeout_seconds or max(cfg.timeout_seconds + 30, 30)

    try:
        try:
            completed = runner(
                command,
                cwd=str(cfg.loop_dir.parent),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            exit_code = int(completed.returncode)
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
        except FileNotFoundError as exc:
            exit_code = 127
            stdout = ""
            stderr = str(exc)
            _write_artifact(
                artifact_path,
                lease=lease,
                command=command,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                pc_output_path=cfg.pc_output_path,
                detail={"failed_to_start": True},
            )
            ledger.record_failed_to_start(
                lease.task_id,
                actor=lease.owner,
                detail={"reason": "local_builder_missing", "error": stderr},
            )
            lifecycle.record(
                build_unit_id,
                "failed",
                task_id=lease.task_id,
                attempt_no=lease.attempt_no,
                reason="local_builder_missing",
            )
            return WorkerRuntimeResult(
                task_id=lease.task_id,
                exit_code=exit_code,
                submitted_candidate=False,
                failure_recorded=True,
                artifact_path=artifact_path,
                pc_output_path=cfg.pc_output_path,
                fingerprint="worker_runtime_failed_to_start",
                task_md_path=cfg.task_path,
            )
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = (exc.stderr or "") + "\nworker runtime timed out"
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=max(cfg.gpu_heartbeat_interval_seconds, 1.0) + 5.0)
        release_result = arbiter.release(gpu_holder_id, gpu_lease_nonce)
        lifecycle.record(
            build_unit_id,
            "released",
            task_id=lease.task_id,
            attempt_no=lease.attempt_no,
            detail={"release_result": release_result, "preempted": was_preempted.is_set()},
        )
        if was_preempted.is_set():
            lifecycle.record(
                build_unit_id,
                "preempted",
                task_id=lease.task_id,
                attempt_no=lease.attempt_no,
                reason="gpu_lease_preempted_mid_run",
            )

    _write_artifact(
        artifact_path,
        lease=lease,
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        pc_output_path=cfg.pc_output_path,
    )

    if exit_code == 0 and cfg.pc_output_path.exists():
        ledger.submit_candidate_evidence(
            lease.task_id,
            owner=lease.owner,
            lease_nonce=lease.lease_nonce,
            evidence={
                "runner": "local_builder",
                "worker_runtime": "phase_c_pc1",
                "pc_output_path": str(cfg.pc_output_path),
                "runtime_artifact_path": str(artifact_path),
                "task_md_path": str(cfg.task_path),
                "exit_code": exit_code,
                "attempt_no": lease.attempt_no,
            },
        )
        lifecycle.record(build_unit_id, "verified", task_id=lease.task_id, attempt_no=lease.attempt_no)
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=exit_code,
            submitted_candidate=True,
            failure_recorded=False,
            artifact_path=artifact_path,
            pc_output_path=cfg.pc_output_path,
            task_md_path=cfg.task_path,
        )

    fingerprint = (
        f"worker_runtime_exit_{exit_code}_"
        f"{'missing_output' if not cfg.pc_output_path.exists() else 'nonzero'}"
    )
    ledger.record_failure(
        lease.task_id,
        owner=lease.owner,
        lease_nonce=lease.lease_nonce,
        failure_fingerprint=fingerprint,
        failure_detail={
            "runner": "local_builder",
            "worker_runtime": "phase_c_pc1",
            "pc_output_path": str(cfg.pc_output_path),
            "runtime_artifact_path": str(artifact_path),
            "task_md_path": str(cfg.task_path),
            "exit_code": exit_code,
            "attempt_no": lease.attempt_no,
        },
    )
    lifecycle.record(
        build_unit_id, "failed", task_id=lease.task_id, attempt_no=lease.attempt_no, reason=fingerprint
    )
    return WorkerRuntimeResult(
        task_id=lease.task_id,
        exit_code=exit_code,
        submitted_candidate=False,
        failure_recorded=True,
        artifact_path=artifact_path,
        pc_output_path=cfg.pc_output_path,
        fingerprint=fingerprint,
        task_md_path=cfg.task_path,
    )
