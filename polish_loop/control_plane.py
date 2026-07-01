#!/usr/bin/env python3
"""Phase-C P0 deterministic control plane for the polish loop.

This module is the durable, single-host control-plane core. It deliberately
stays in the standard library: SQLite WAL is the source of truth, workers are
finite lease holders, and acceptance is decided by code plus the clean gate.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as _dt
import hashlib
import json
import os
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

try:  # pragma: no cover - exercised when imported as a package
    from .builder_output_validator import validate_candidate_evidence as validate_builder_output
except ImportError:  # pragma: no cover - exercised by legacy sys.path imports
    from builder_output_validator import validate_candidate_evidence as validate_builder_output

try:  # pragma: no cover - exercised when imported as a package
    from .task_routing import ROUTING_SCHEMA_VERSION, classify_task_routing
except ImportError:  # pragma: no cover - exercised by legacy sys.path imports
    try:
        from task_routing import ROUTING_SCHEMA_VERSION, classify_task_routing  # type: ignore
    except ImportError:  # pragma: no cover - old checkouts without the router
        ROUTING_SCHEMA_VERSION = "polish_loop_task_routing_v1"
        classify_task_routing = None  # type: ignore[assignment]


_MODULE_LOOP_DIR = Path(__file__).resolve().parent
LOOP_DIR = Path(os.environ.get("OPENCLAW_POLISH_LOOP_DIR", str(_MODULE_LOOP_DIR)))
DEFAULT_LEDGER_PATH = LOOP_DIR / "control_plane.sqlite3"
DEFAULT_GREEN_GATE = Path("/home/openclaw/scripts/green_gate.sh")
DEFAULT_AUTO_HEAL_STATE = Path("/home/openclaw/mac_eyes/loop_auto_heal_state.json")
INGEST_POLICY_PATH = LOOP_DIR / "ingest_policy.json"

READY_SOURCES = frozenset({"human_intent", "detector", "approved_followup"})
AGENT_ONLY_PROPOSED_SOURCES = frozenset(
    {"agent", "builder", "auditor", "orch", "orchestrator", "agent_suggestion"}
)
TERMINAL_STATUSES = frozenset({"DONE", "BLOCKED", "DEAD"})
ALLOWED_TRANSITIONS = {
    "PROPOSED": frozenset({"READY", "DEAD"}),
    "READY": frozenset({"LEASED", "BLOCKED", "DEAD"}),
    "LEASED": frozenset({"VERIFYING", "READY", "BLOCKED", "DEAD"}),
    "VERIFYING": frozenset({"DONE", "READY", "BLOCKED", "DEAD"}),
    "DONE": frozenset(),
    "BLOCKED": frozenset(),
    "DEAD": frozenset(),
}
HEAL_TASK_PAYLOAD_FIELDS = (
    "source_surface",
    "bad_exchange",
    "expected_behavior",
    "truth_inputs",
    "bounds",
    "allowed_tools_class",
    "pii_rules",
    "repro_prompts",
    "acceptance_tests",
    "rollback_no_send",
)
HEARTBEAT_TYPES = frozenset({"heartbeat", "alive", "status_heartbeat"})
HEARTBEAT_ONLY_TEXT = frozenset(
    {
        "alive",
        "still alive",
        "nothing to do",
        "no work",
        "no work to do",
        "idle",
        "heartbeat",
    }
)
DETECTOR_FORBIDDEN_ACTION_TEXT = frozenset(
    {"send", "sending", "sent", "pay", "payment", "money", "wire", "invoice payment"}
)
SIZE_ROUTER_FLAG = "OPENCLAW_POLISH_LOOP_SIZE_ROUTER_V1"
SIZE_ROUTER_FLAG_ON_VALUES = {"1", "true", "yes", "on"}


def _load_ingest_policies(policy_path: Path = INGEST_POLICY_PATH) -> list[dict[str, Any]]:
    try:
        data = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - ingestion must fail closed on policy loss/corruption.
        raise RuntimeError(f"Ingestion failed closed: missing or malformed {policy_path.name}: {exc}") from exc

    policies = data.get("policies") if isinstance(data, dict) else None
    if not isinstance(policies, list):
        raise RuntimeError(f"Ingestion failed closed: missing or malformed {policy_path.name}: policies must be a list")
    return [policy for policy in policies if isinstance(policy, dict)]


def _ingest_policy_block_reason(queue_name: str, task_id: str) -> str | None:
    for policy in _load_ingest_policies():
        match = policy.get("match", {})
        if not isinstance(match, dict):
            continue
        task_ids = match.get("task_ids", [])
        if match.get("queue") == queue_name and task_id in task_ids:
            return str(policy.get("reason") or "Blocked by ingest_policy.json")
    return None


class ControlPlaneError(RuntimeError):
    """Base class for deterministic control-plane failures."""


class InvalidTransition(ControlPlaneError):
    """Raised when a caller asks for a non-state-machine transition."""


class SourceNotAllowed(ControlPlaneError):
    """Raised when a non-allowlisted source tries to create dispatchable work."""


class TaskRejected(ControlPlaneError):
    """Raised when a task payload is structurally unsafe or useless."""


class LeaseError(ControlPlaneError):
    """Raised when a worker tries to mutate a task without the live lease."""


@dataclasses.dataclass(frozen=True)
class TaskLease:
    task_id: str
    owner: str
    lease_nonce: str
    lease_expiry: str
    attempt_no: int
    version: int


@dataclasses.dataclass(frozen=True)
class DispatchResult:
    dispatched: bool
    model_calls: int = 0
    task_id: str | None = None
    reason: str = "no_eligible_task"


@dataclasses.dataclass(frozen=True)
class AcceptanceDecision:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def iso_now() -> str:
    return utcnow().isoformat()


def parse_iso(value: str | None) -> _dt.datetime | None:
    if not value:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.UTC)
    return parsed.astimezone(_dt.UTC)


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_acceptance_ref(
    acceptance_path: str | Path,
    green_gate_path: str | Path = DEFAULT_GREEN_GATE,
    *,
    repo_ref: str = "HEAD",
    trusted_acceptance_ref: str | None = None,
    trusted_acceptance_paths: tuple[str, ...] = ("tests",),
) -> str:
    """Create the immutable acceptance reference stored with a task."""

    acceptance = Path(acceptance_path).resolve()
    gate = Path(green_gate_path).resolve()
    payload = {
        "acceptance_path": str(acceptance),
        "acceptance_sha256": sha256_file(acceptance),
        "green_gate_path": str(gate),
        "repo_ref": repo_ref,
        "trusted_acceptance_ref": trusted_acceptance_ref,
        "trusted_acceptance_paths": list(trusted_acceptance_paths),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _decode_json(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def _encode_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _semantic_text_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        if value.strip():
            values.append(value.strip())
    elif isinstance(value, dict):
        for child in value.values():
            values.extend(_semantic_text_values(child))
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            values.extend(_semantic_text_values(child))
    elif value is not None:
        values.append(str(value).strip())
    return [v for v in values if v]


def _normal_text(text: str) -> str:
    kept = [ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text]
    return " ".join("".join(kept).split())


def _payload_is_heartbeat_only(task_type: str, payload: Any) -> bool:
    values = _semantic_text_values(payload)
    if not values:
        return task_type.lower() in HEARTBEAT_TYPES
    normal = _normal_text(" ".join(values))
    return task_type.lower() in HEARTBEAT_TYPES or normal in HEARTBEAT_ONLY_TEXT


def _detector_payload_has_forbidden_action(payload: Any) -> bool:
    normal = _normal_text(" ".join(_semantic_text_values(payload)))
    tokens = set(normal.split())
    return any(
        phrase in normal if " " in phrase else phrase in tokens
        for phrase in DETECTOR_FORBIDDEN_ACTION_TEXT
    )


def _default_task_id(task_type: str, payload: dict[str, Any]) -> str:
    if task_type == "agent_heal":
        source_surface = str(payload.get("source_surface") or "").strip().lower()
        claim_type = str(payload.get("claim_type") or "").strip().lower()
        if source_surface and claim_type:
            key = json.dumps(
                {"source_surface": source_surface, "claim_type": claim_type},
                sort_keys=True,
                separators=(",", ":"),
            )
            return "heal-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"task-{uuid.uuid4().hex}"


def size_router_v1_enabled(enabled: bool | None = None) -> bool:
    if enabled is not None:
        return bool(enabled)
    return os.environ.get(SIZE_ROUTER_FLAG, "").strip().lower() in SIZE_ROUTER_FLAG_ON_VALUES


def _routing_input_payload(
    payload: dict[str, Any],
    *,
    task_type: str,
    acceptance_ref: str | dict[str, Any] | None,
) -> dict[str, Any]:
    routing_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"routing", "holding_reason"}
    }
    routing_payload.setdefault("task_type", task_type)
    if acceptance_ref is not None and "acceptance_ref" not in routing_payload:
        routing_payload["acceptance_ref"] = acceptance_ref
    return routing_payload


def _apply_size_routing(
    payload: dict[str, Any],
    *,
    task_type: str,
    acceptance_ref: str | dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if classify_task_routing is None:
        raise TaskRejected(f"{SIZE_ROUTER_FLAG} is enabled but task_routing is unavailable")
    routing = classify_task_routing(
        _routing_input_payload(payload, task_type=task_type, acceptance_ref=acceptance_ref)
    )
    routed_payload = dict(payload)
    routed_payload["routing"] = routing
    if not _routing_allows_ready(routing):
        routed_payload["holding_reason"] = _routing_holding_reason(routing)
    return routed_payload, routing


def _routing_allows_ready(routing: dict[str, Any] | None) -> bool:
    if not routing:
        return False
    return (
        routing.get("schema_version") == ROUTING_SCHEMA_VERSION
        and routing.get("readiness") == "ready"
        and not routing.get("risk_flags")
        and bool(routing.get("local_model_allowed"))
    )


def _routing_holding_reason(routing: dict[str, Any]) -> str:
    reason = str(routing.get("holding_reason") or "").strip()
    if reason:
        return reason
    readiness = str(routing.get("readiness") or "unknown")
    return f"routing_not_ready:{readiness}"


def _routing_event_detail(routing: dict[str, Any] | None) -> dict[str, Any] | None:
    if not routing:
        return None
    return {
        "schema_version": routing.get("schema_version"),
        "size_class": routing.get("size_class"),
        "readiness": routing.get("readiness"),
        "holding_reason": routing.get("holding_reason"),
        "risk_flags": routing.get("risk_flags", []),
        "target_runner_tier": routing.get("target_runner_tier"),
        "minimum_model_tier": routing.get("minimum_model_tier"),
        "local_model_allowed": bool(routing.get("local_model_allowed")),
        "cloud_allowed": bool(routing.get("cloud_allowed")),
        "decomposition_required": bool(routing.get("decomposition_required")),
    }


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["payload"] = _decode_json(data.get("payload"), {})
    data["candidate_evidence"] = _decode_json(data.get("candidate_evidence"), None)
    return data


class ControlPlaneLedger:
    """SQLite-WAL ledger with strict Phase-C P0 state transitions."""

    def __init__(
        self,
        path: str | Path = DEFAULT_LEDGER_PATH,
        *,
        status_view_path: str | Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if status_view_path is not None:
            self.status_view_path: Path | None = Path(status_view_path)
        elif self.path.resolve() == DEFAULT_LEDGER_PATH.resolve():
            self.status_view_path = LOOP_DIR / "status.json"
        else:
            self.status_view_path = self.path.with_name("status.json")
        self._ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    owner TEXT,
                    lease_nonce TEXT,
                    lease_expiry TEXT,
                    version INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    budget_spent REAL NOT NULL DEFAULT 0,
                    budget_cap REAL NOT NULL DEFAULT 0,
                    acceptance_ref TEXT,
                    candidate_evidence TEXT,
                    terminal_reason TEXT,
                    payload TEXT NOT NULL,
                    proposed_expires_at TEXT,
                    dispatchable INTEGER NOT NULL DEFAULT 0,
                    failure_fingerprint TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (status IN ('PROPOSED','READY','LEASED','VERIFYING','DONE','BLOCKED','DEAD'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(id),
                    attempt_no INTEGER NOT NULL,
                    owner TEXT NOT NULL,
                    lease_nonce TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    failure_fingerprint TEXT,
                    budget_spent REAL NOT NULL DEFAULT 0,
                    evidence TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    event_type TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT,
                    actor TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_ready ON tasks(status, dispatchable, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id, attempt_no)"
            )

    @contextlib.contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
            self.render_status_view()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def render_status_view(self) -> None:
        """Synchronously render the legacy status.json compatibility view.

        The SQLite ledger is authoritative, but existing readers still consume
        status.json. This view only uses legacy status names so current
        dashboards and bot status readers do not crash during the substrate
        migration.
        """

        if self.status_view_path is None:
            return
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM tasks
                ORDER BY updated_at DESC, created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            view = {
                "status": "idle",
                "task_name": None,
                "phase_c_status": "EMPTY",
                "phase_c_ledger": str(self.path),
                "last_updated": iso_now(),
            }
        else:
            phase_status = row["status"]
            if phase_status in {"LEASED", "VERIFYING"}:
                legacy_status = "pc_turn"
            elif phase_status == "DONE":
                legacy_status = "approved"
            elif phase_status in {"BLOCKED", "DEAD"}:
                legacy_status = "blocked"
            else:
                legacy_status = "idle"
            view = {
                "status": legacy_status,
                "task_name": row["id"],
                "pass": max(1, int(row["attempts"]) or 1),
                "approved": phase_status == "DONE",
                "block_reason": row["terminal_reason"] if legacy_status == "blocked" else None,
                "phase_c_status": phase_status,
                "phase_c_task_id": row["id"],
                "phase_c_owner": row["owner"],
                "phase_c_dispatchable": bool(row["dispatchable"]),
                "phase_c_ledger": str(self.path),
                "last_updated": row["updated_at"],
            }
        self.status_view_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.status_view_path.with_suffix(self.status_view_path.suffix + ".tmp")
        tmp.write_text(json.dumps(view, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.status_view_path)

    def _event(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str | None,
        event_type: str,
        actor: str,
        from_status: str | None = None,
        to_status: str | None = None,
        detail: Any = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO events(task_id, event_type, from_status, to_status, actor, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                event_type,
                from_status,
                to_status,
                actor,
                _encode_json(detail) if detail is not None else None,
                iso_now(),
            ),
        )

    def counts(self) -> dict[str, int]:
        with self.connect() as conn:
            return {
                "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                "attempts": conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
                "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            }

    def attempt_count(self, task_id: str) -> int:
        with self.connect() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM attempts WHERE task_id = ?", (task_id,)
                ).fetchone()[0]
            )

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        data = _row_to_dict(row)
        if data is None:
            raise KeyError(task_id)
        return data

    def list_tasks(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at, id").fetchall()
        return [dict(row) for row in rows]

    def admit_task(
        self,
        *,
        task_id: str | None = None,
        source: str,
        task_type: str,
        requested_status: str = "PROPOSED",
        payload: dict[str, Any] | None = None,
        acceptance_ref: str | dict[str, Any] | None = None,
        ttl_seconds: int = 3600,
        max_attempts: int = 3,
        budget_cap: float = 0.0,
    ) -> str:
        """Create a task, applying the source allowlist before dispatchability."""

        requested = requested_status.upper()
        if requested not in {"PROPOSED", "READY"}:
            raise InvalidTransition(f"cannot admit directly to {requested_status!r}")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        payload = payload or {}
        if _payload_is_heartbeat_only(task_type, payload):
            raise TaskRejected("heartbeat/alive/nothing-to-do payloads are not tasks")

        # Canonical API mutation sandbox policy check
        queue_name = None
        if isinstance(acceptance_ref, dict) and "queue" in acceptance_ref:
            queue_name = acceptance_ref["queue"]
        elif "queue_ref" in payload:
            queue_name = Path(payload["queue_ref"]).name

        task_id = task_id or _default_task_id(task_type, payload)

        if queue_name:
            reason = _ingest_policy_block_reason(str(queue_name), task_id)
            if reason:
                raise TaskRejected(f"Policy Blocked: {reason}")

        source_norm = source.strip().lower()
        if source_norm == "detector" and _detector_payload_has_forbidden_action(payload):
            raise TaskRejected("detectors cannot emit send, payment, or money work")
        routing: dict[str, Any] | None = None
        if size_router_v1_enabled():
            payload, routing = _apply_size_routing(
                payload,
                task_type=task_type,
                acceptance_ref=acceptance_ref,
            )

        if (
            requested == "READY"
            and source_norm in READY_SOURCES
            and (routing is None or _routing_allows_ready(routing))
        ):
            status = "READY"
            dispatchable = 1
            proposed_expires_at = None
        else:
            status = "PROPOSED"
            dispatchable = 0
            proposed_expires_at = (
                utcnow() + _dt.timedelta(seconds=max(1, ttl_seconds))
            ).isoformat()

        if requested == "READY" and source_norm not in READY_SOURCES:
            if source_norm not in AGENT_ONLY_PROPOSED_SOURCES:
                source_norm = "agent_suggestion"

        now = iso_now()
        if isinstance(acceptance_ref, dict):
            acceptance_ref_text = _encode_json(acceptance_ref)
        else:
            acceptance_ref_text = acceptance_ref

        with self._tx() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO tasks(
                        id, type, status, source, version, attempts, max_attempts,
                        budget_spent, budget_cap, acceptance_ref, payload,
                        proposed_expires_at, dispatchable, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 0, 0, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        task_type,
                        status,
                        source_norm,
                        max_attempts,
                        budget_cap,
                        acceptance_ref_text,
                        _encode_json(payload),
                        proposed_expires_at,
                        dispatchable,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                existing = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
                if existing is not None and existing["status"] not in TERMINAL_STATUSES:
                    self._event(
                        conn,
                        task_id=task_id,
                        event_type="TASK_DEDUPED",
                        actor=source_norm,
                        to_status=existing["status"],
                        detail={"reason": "active_agent_heal_duplicate"},
                    )
                    return task_id
                raise
            detail = {"requested_status": requested, "dispatchable": bool(dispatchable)}
            if routing is not None:
                detail.update(
                    {
                        "routing": _routing_event_detail(routing),
                        "routing_hold": not _routing_allows_ready(routing),
                    }
                )
            self._event(
                conn,
                task_id=task_id,
                event_type="TASK_ADMITTED",
                actor=source_norm,
                to_status=status,
                detail=detail,
            )
        return task_id

    def promote_to_ready(self, task_id: str, *, actor: str, source: str) -> None:
        source_norm = source.strip().lower()
        if source_norm not in READY_SOURCES:
            raise SourceNotAllowed(f"{source!r} cannot make a task dispatchable")
        promotion_hold_reason: str | None = None
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            current = row["status"]
            if current != "PROPOSED":
                raise InvalidTransition(f"cannot promote {current} to READY")
            expiry = parse_iso(row["proposed_expires_at"])
            if expiry is not None and expiry <= utcnow():
                self._terminalize_locked(
                    conn,
                    task_id,
                    current,
                    "DEAD",
                    actor,
                    "proposal_ttl_expired",
                )
                raise InvalidTransition("proposal TTL expired")
            now = iso_now()
            routing: dict[str, Any] | None = None
            payload = _decode_json(row["payload"], {})
            if not isinstance(payload, dict):
                payload = {}
            if size_router_v1_enabled():
                acceptance_ref = _decode_json(row["acceptance_ref"], row["acceptance_ref"])
                payload, routing = _apply_size_routing(
                    payload,
                    task_type=str(row["type"]),
                    acceptance_ref=acceptance_ref,
                )
                if not _routing_allows_ready(routing):
                    conn.execute(
                        """
                        UPDATE tasks
                        SET payload=?, version=version+1, updated_at=?
                        WHERE id=? AND status='PROPOSED'
                        """,
                        (_encode_json(payload), now, task_id),
                    )
                    self._event(
                        conn,
                        task_id=task_id,
                        event_type="TASK_PROMOTION_HELD",
                        actor=actor,
                        from_status="PROPOSED",
                        to_status="PROPOSED",
                        detail={"source": source_norm, "routing": _routing_event_detail(routing)},
                    )
                    promotion_hold_reason = _routing_holding_reason(routing)

            if promotion_hold_reason is None:
                if routing is None:
                    conn.execute(
                        """
                        UPDATE tasks
                        SET status='READY', dispatchable=1, version=version+1, updated_at=?
                        WHERE id=? AND status='PROPOSED'
                        """,
                        (now, task_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE tasks
                        SET status='READY', dispatchable=1, payload=?, version=version+1, updated_at=?
                        WHERE id=? AND status='PROPOSED'
                        """,
                        (_encode_json(payload), now, task_id),
                    )
                detail = {"source": source_norm}
                if routing is not None:
                    detail["routing"] = _routing_event_detail(routing)
                self._event(
                    conn,
                    task_id=task_id,
                    event_type="TASK_PROMOTED",
                    actor=actor,
                    from_status="PROPOSED",
                    to_status="READY",
                    detail=detail,
                )
        if promotion_hold_reason is not None:
            raise InvalidTransition(promotion_hold_reason)

    def transition(
        self,
        task_id: str,
        from_status: str,
        to_status: str,
        *,
        actor: str,
        expected_version: int | None = None,
    ) -> None:
        from_status = from_status.upper()
        to_status = to_status.upper()
        if to_status not in ALLOWED_TRANSITIONS.get(from_status, frozenset()):
            raise InvalidTransition(f"{from_status} -> {to_status} is not allowed")
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["status"] != from_status:
                raise InvalidTransition(
                    f"task is {row['status']}, not expected {from_status}"
                )
            if expected_version is not None and row["version"] != expected_version:
                raise InvalidTransition(
                    f"task version is {row['version']}, not expected {expected_version}"
                )
            now = iso_now()
            dispatchable = 1 if to_status == "READY" else 0
            conn.execute(
                """
                UPDATE tasks
                SET status=?, dispatchable=?, version=version+1, updated_at=?
                WHERE id=? AND status=?
                """,
                (to_status, dispatchable, now, task_id, from_status),
            )
            self._event(
                conn,
                task_id=task_id,
                event_type="TASK_TRANSITION",
                actor=actor,
                from_status=from_status,
                to_status=to_status,
            )

    def recover_expired_leases(self) -> int:
        now = iso_now()
        recovered = 0
        with self.connect() as conn:
            expired_ids = [
                row["id"]
                for row in conn.execute(
                    """
                    SELECT id FROM tasks
                    WHERE status='LEASED' AND lease_expiry IS NOT NULL AND lease_expiry <= ?
                    """,
                    (now,),
                ).fetchall()
            ]
        if not expired_ids:
            return 0
        with self._tx() as conn:
            placeholders = ",".join("?" for _ in expired_ids)
            rows = conn.execute(
                f"SELECT * FROM tasks WHERE id IN ({placeholders})",
                expired_ids,
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status='READY', owner=NULL, lease_nonce=NULL, lease_expiry=NULL,
                        dispatchable=1, version=version+1, updated_at=?
                    WHERE id=? AND status='LEASED'
                    """,
                    (now, row["id"]),
                )
                self._event(
                    conn,
                    task_id=row["id"],
                    event_type="LEASE_EXPIRED",
                    actor="control_plane",
                    from_status="LEASED",
                    to_status="READY",
                    detail={"owner": row["owner"]},
                )
                recovered += 1
        return recovered

    def record_failed_to_start(
        self,
        task_id: str,
        *,
        actor: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Record an explicit runner startup failure without scraping logs."""

        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["status"] in TERMINAL_STATUSES:
                raise InvalidTransition(f"task is already terminal: {row['status']}")
            self._terminalize_locked(
                conn,
                task_id,
                row["status"],
                "BLOCKED",
                actor,
                "failed_to_start",
                detail=detail or {"reason": "runner_failed_to_start"},
            )
            self._event(
                conn,
                task_id=task_id,
                event_type="FAILED_TO_START",
                actor=actor,
                from_status=row["status"],
                to_status="BLOCKED",
                detail=detail or {"reason": "runner_failed_to_start"},
            )

    def claim_task(
        self,
        task_id: str,
        *,
        owner: str,
        lease_seconds: int,
    ) -> TaskLease | None:
        self.recover_expired_leases()
        return self._claim(owner=owner, lease_seconds=lease_seconds, task_id=task_id)

    def claim_next_ready(self, *, owner: str, lease_seconds: int = 900) -> TaskLease | None:
        self.recover_expired_leases()
        if not self._has_ready_task():
            return None
        return self._claim(owner=owner, lease_seconds=lease_seconds, task_id=None)

    def _has_ready_task(self) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM tasks
                WHERE status='READY' AND dispatchable=1 AND owner IS NULL
                LIMIT 1
                """
            ).fetchone()
        return row is not None

    def _claim(
        self,
        *,
        owner: str,
        lease_seconds: int,
        task_id: str | None,
    ) -> TaskLease | None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be >= 1")
        nonce = uuid.uuid4().hex
        now_dt = utcnow()
        now = now_dt.isoformat()
        expiry = (now_dt + _dt.timedelta(seconds=lease_seconds)).isoformat()

        with self._tx() as conn:
            if task_id is None:
                row = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE status='READY' AND dispatchable=1 AND owner IS NULL
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                    """
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE id=? AND status='READY' AND dispatchable=1 AND owner IS NULL
                    """,
                    (task_id,),
                ).fetchone()
            if row is None:
                return None

            if int(row["attempts"]) >= int(row["max_attempts"]):
                self._terminalize_locked(
                    conn,
                    row["id"],
                    row["status"],
                    "BLOCKED",
                    "control_plane",
                    "max_attempts_exhausted",
                )
                return None

            attempt_no = int(row["attempts"]) + 1
            cur = conn.execute(
                """
                UPDATE tasks
                SET status='LEASED', owner=?, lease_nonce=?, lease_expiry=?,
                    attempts=?, dispatchable=0, version=version+1, updated_at=?
                WHERE id=? AND status='READY' AND owner IS NULL
                """,
                (owner, nonce, expiry, attempt_no, now, row["id"]),
            )
            if cur.rowcount != 1:
                return None
            conn.execute(
                """
                INSERT INTO attempts(task_id, attempt_no, owner, lease_nonce, started_at, status)
                VALUES (?, ?, ?, ?, ?, 'LEASED')
                """,
                (row["id"], attempt_no, owner, nonce, now),
            )
            self._event(
                conn,
                task_id=row["id"],
                event_type="TASK_CLAIMED",
                actor=owner,
                from_status="READY",
                to_status="LEASED",
                detail={"attempt_no": attempt_no, "lease_expiry": expiry},
            )
            version = int(row["version"]) + 1
            return TaskLease(
                task_id=row["id"],
                owner=owner,
                lease_nonce=nonce,
                lease_expiry=expiry,
                attempt_no=attempt_no,
                version=version,
            )

    def _require_live_lease_locked(
        self,
        conn: sqlite3.Connection,
        task_id: str,
        owner: str,
        lease_nonce: str,
    ) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        if (
            row["status"] != "LEASED"
            or row["owner"] != owner
            or row["lease_nonce"] != lease_nonce
        ):
            raise LeaseError("owner/nonce does not hold the live lease")
        expiry = parse_iso(row["lease_expiry"])
        if expiry is not None and expiry <= utcnow():
            raise LeaseError("lease expired")
        return row

    def submit_candidate_evidence(
        self,
        task_id: str,
        *,
        owner: str,
        lease_nonce: str,
        evidence: dict[str, Any],
    ) -> None:
        if not evidence:
            raise TaskRejected("candidate_evidence is required")
        with self._tx() as conn:
            row = self._require_live_lease_locked(conn, task_id, owner, lease_nonce)
            now = iso_now()
            conn.execute(
                """
                UPDATE tasks
                SET status='VERIFYING', candidate_evidence=?, version=version+1, updated_at=?
                WHERE id=? AND status='LEASED' AND owner=? AND lease_nonce=?
                """,
                (_encode_json(evidence), now, task_id, owner, lease_nonce),
            )
            conn.execute(
                """
                UPDATE attempts
                SET status='VERIFYING', evidence=?
                WHERE task_id=? AND attempt_no=?
                """,
                (_encode_json(evidence), task_id, row["attempts"]),
            )
            self._event(
                conn,
                task_id=task_id,
                event_type="CANDIDATE_SUBMITTED",
                actor=owner,
                from_status="LEASED",
                to_status="VERIFYING",
            )

    def record_failure(
        self,
        task_id: str,
        *,
        owner: str,
        lease_nonce: str,
        failure_fingerprint: str,
        budget_spent: float = 0.0,
        failure_detail: dict[str, Any] | None = None,
    ) -> None:
        with self._tx() as conn:
            row = self._require_live_lease_locked(conn, task_id, owner, lease_nonce)
            total_spent = float(row["budget_spent"]) + float(budget_spent)
            maxed_attempts = int(row["attempts"]) >= int(row["max_attempts"])
            repeated = bool(
                row["failure_fingerprint"]
                and row["failure_fingerprint"] == failure_fingerprint
            )
            over_budget = bool(row["budget_cap"] and total_spent >= float(row["budget_cap"]))
            if maxed_attempts:
                reason = "max_attempts_exhausted"
            elif repeated:
                reason = "repeated_failure_fingerprint"
            elif over_budget:
                reason = "budget_cap_exhausted"
            else:
                reason = ""

            now = iso_now()
            failure_receipt = None
            if failure_detail:
                failure_receipt = _encode_json(
                    {
                        "schema_version": "polish_loop_failure_receipt_v0",
                        "failure_fingerprint": failure_fingerprint,
                        "detail": failure_detail,
                    }
                )
            conn.execute(
                """
                UPDATE attempts
                SET status=?, finished_at=?, failure_fingerprint=?, budget_spent=?,
                    evidence=COALESCE(?, evidence)
                WHERE task_id=? AND attempt_no=?
                """,
                (
                    "BLOCKED" if reason else "READY",
                    now,
                    failure_fingerprint,
                    budget_spent,
                    failure_receipt,
                    task_id,
                    row["attempts"],
                ),
            )
            if reason:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status='BLOCKED', owner=NULL, lease_nonce=NULL, lease_expiry=NULL,
                        dispatchable=0, budget_spent=?, failure_fingerprint=?,
                        terminal_reason=?, version=version+1, updated_at=?
                    WHERE id=?
                    """,
                    (total_spent, failure_fingerprint, reason, now, task_id),
                )
                self._event(
                    conn,
                    task_id=task_id,
                    event_type="TASK_TERMINAL",
                    actor=owner,
                    from_status="LEASED",
                    to_status="BLOCKED",
                    detail={
                        "reason": reason,
                        "failure_fingerprint": failure_fingerprint,
                        **({"failure_detail": failure_detail} if failure_detail else {}),
                    },
                )
            else:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status='READY', owner=NULL, lease_nonce=NULL, lease_expiry=NULL,
                        dispatchable=1, budget_spent=?, failure_fingerprint=?,
                        version=version+1, updated_at=?
                    WHERE id=?
                    """,
                    (total_spent, failure_fingerprint, now, task_id),
                )
                self._event(
                    conn,
                    task_id=task_id,
                    event_type="TASK_REQUEUED",
                    actor=owner,
                    from_status="LEASED",
                    to_status="READY",
                    detail={
                        "failure_fingerprint": failure_fingerprint,
                        **({"failure_detail": failure_detail} if failure_detail else {}),
                    },
                )

    def decide_acceptance(
        self,
        task_id: str,
        *,
        gate_runner: Callable[..., AcceptanceDecision] | None = None,
        trusted_repo: str | Path | None = None,
    ) -> AcceptanceDecision:
        """Run the code-owned two-phase acceptance decision for VERIFYING work."""

        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        if row["status"] != "VERIFYING":
            raise InvalidTransition(f"task is {row['status']}, not VERIFYING")

        evidence = _decode_json(row["candidate_evidence"], {})
        output_path = evidence.get("pc_output_path")
        if not output_path:
            decision = AcceptanceDecision(2, "", "candidate evidence missing pc_output_path")
            self._block_after_acceptance(task_id, "candidate_evidence_missing_output", decision)
            _post_acceptance_notify(task_id, "BLOCKED", decision)
            return decision
        ok, reason = validate_builder_output(output_path)
        if not ok:
            decision = AcceptanceDecision(2, "", f"candidate output invalid: {reason}")
            self._block_after_acceptance(task_id, f"candidate_output_{reason}", decision)
            _post_acceptance_notify(task_id, "BLOCKED", decision)
            return decision

        acceptance_ref = _decode_json(row["acceptance_ref"], {})
        acceptance_path = Path(acceptance_ref.get("acceptance_path", ""))
        expected_sha = acceptance_ref.get("acceptance_sha256")
        green_gate_path = Path(
            acceptance_ref.get("green_gate_path") or str(DEFAULT_GREEN_GATE)
        )
        repo_ref = acceptance_ref.get("repo_ref") or "HEAD"
        trusted_acceptance_ref = acceptance_ref.get("trusted_acceptance_ref")
        trusted_acceptance_paths = tuple(
            acceptance_ref.get("trusted_acceptance_paths") or ("tests",)
        )
        if not acceptance_path.exists() or not expected_sha:
            decision = AcceptanceDecision(2, "", "acceptance ref missing trusted file")
            self._block_after_acceptance(task_id, "acceptance_ref_missing", decision)
            _post_acceptance_notify(task_id, "BLOCKED", decision)
            return decision
        actual_sha = sha256_file(acceptance_path)
        if actual_sha != expected_sha:
            decision = AcceptanceDecision(2, "", "trusted acceptance ref hash mismatch")
            self._block_after_acceptance(task_id, "acceptance_ref_hash_mismatch", decision)
            _post_acceptance_notify(task_id, "BLOCKED", decision)
            return decision

        cwd = Path(trusted_repo).resolve() if trusted_repo else green_gate_path.resolve().parents[1]
        runner = gate_runner or _default_gate_runner
        decision = runner(
            green_gate_path=green_gate_path,
            repo_ref=repo_ref,
            cwd=cwd,
            trusted_acceptance_ref=trusted_acceptance_ref,
            trusted_acceptance_paths=trusted_acceptance_paths,
        )
        if decision.ok:
            self._mark_done_after_acceptance(task_id, decision)
            _post_acceptance_notify(task_id, "DONE", decision)
        else:
            self._block_after_acceptance(task_id, "green_gate_failed", decision)
            _post_acceptance_notify(task_id, "BLOCKED", decision)
        return decision

    def _mark_done_after_acceptance(
        self,
        task_id: str,
        decision: AcceptanceDecision,
    ) -> None:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["status"] != "VERIFYING":
                raise InvalidTransition(f"task is {row['status']}, not VERIFYING")
            now = iso_now()
            conn.execute(
                """
                UPDATE tasks
                SET status='DONE', owner=NULL, lease_nonce=NULL, lease_expiry=NULL,
                    dispatchable=0, terminal_reason=NULL, version=version+1, updated_at=?
                WHERE id=? AND status='VERIFYING'
                """,
                (now, task_id),
            )
            conn.execute(
                """
                UPDATE attempts
                SET status='DONE', finished_at=?
                WHERE task_id=? AND attempt_no=?
                """,
                (now, task_id, row["attempts"]),
            )
            self._event(
                conn,
                task_id=task_id,
                event_type="TASK_ACCEPTED",
                actor="acceptance_gate",
                from_status="VERIFYING",
                to_status="DONE",
                detail={"green_gate_exit": decision.exit_code},
            )

    def _block_after_acceptance(
        self,
        task_id: str,
        reason: str,
        decision: AcceptanceDecision,
    ) -> None:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["status"] not in {"VERIFYING", "LEASED", "READY"}:
                return
            self._terminalize_locked(
                conn,
                task_id,
                row["status"],
                "BLOCKED",
                "acceptance_gate",
                reason,
                detail={
                    "green_gate_exit": decision.exit_code,
                    "stderr": decision.stderr[-500:],
                },
            )
            conn.execute(
                """
                UPDATE attempts
                SET status='BLOCKED', finished_at=?
                WHERE task_id=? AND attempt_no=?
                """,
                (iso_now(), task_id, row["attempts"]),
            )

    def _terminalize_locked(
        self,
        conn: sqlite3.Connection,
        task_id: str,
        from_status: str,
        to_status: str,
        actor: str,
        reason: str,
        detail: Any | None = None,
    ) -> None:
        if to_status not in TERMINAL_STATUSES:
            raise InvalidTransition(f"{to_status} is not terminal")
        now = iso_now()
        conn.execute(
            """
            UPDATE tasks
            SET status=?, owner=NULL, lease_nonce=NULL, lease_expiry=NULL,
                dispatchable=0, terminal_reason=?, version=version+1, updated_at=?
            WHERE id=?
            """,
            (to_status, reason, now, task_id),
        )
        self._event(
            conn,
            task_id=task_id,
            event_type="TASK_TERMINAL",
            actor=actor,
            from_status=from_status,
            to_status=to_status,
            detail=detail or {"reason": reason},
        )


def _default_gate_runner(
    *,
    green_gate_path: Path,
    repo_ref: str,
    cwd: Path,
    trusted_acceptance_ref: str | None = None,
    trusted_acceptance_paths: tuple[str, ...] = ("tests",),
) -> AcceptanceDecision:
    env = os.environ.copy()
    if trusted_acceptance_ref:
        env["OPENCLAW_TRUSTED_ACCEPTANCE_REF"] = trusted_acceptance_ref
        env["OPENCLAW_TRUSTED_ACCEPTANCE_PATHS"] = " ".join(trusted_acceptance_paths)
    completed = subprocess.run(
        [str(green_gate_path), repo_ref],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return AcceptanceDecision(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _auto_heal_state_path() -> Path:
    return Path(os.environ.get("OPENCLAW_AUTO_HEAL_STATE", str(DEFAULT_AUTO_HEAL_STATE)))


def _record_auto_heal_metric(status: str, decision: AcceptanceDecision) -> None:
    payload = _load_json_object(_auto_heal_state_path())
    metrics = payload.get("daily_metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    if status == "DONE":
        key = "silent_fix_pass"
    else:
        key = "silent_fix_fail"
    metrics[key] = int(metrics.get(key) or 0) + 1
    metrics["last_acceptance_status"] = status
    metrics["last_acceptance_exit_code"] = decision.exit_code
    metrics["last_acceptance_at"] = iso_now()
    payload["schema_version"] = payload.get("schema_version") or "loop_auto_heal_state_v0"
    payload["daily_metrics"] = metrics
    _write_json_object(_auto_heal_state_path(), payload)


def _post_acceptance_notify(task_id: str, status: str, decision: AcceptanceDecision) -> None:
    _record_auto_heal_metric(status, decision)
    try:
        import chief_notify
    except ImportError:
        return
    summary = decision.stderr.strip() or decision.stdout.strip() or "green gate accepted"
    text = (
        f"PC4 self-heal acceptance {status}\n"
        f"task: `{task_id}`\n"
        f"exit: `{decision.exit_code}`\n"
        f"proof: {summary[-500:]}"
    )
    chief_notify.send(text)


def run_control_plane_once(
    ledger: ControlPlaneLedger,
    *,
    owner: str,
    dispatch: Callable[[TaskLease], Any] | None = None,
    lease_seconds: int = 900,
) -> DispatchResult:
    """Claim and dispatch at most one eligible task, then exit quiescently.

    Empty eligible queues perform no writes: no lease is created, no attempt is
    recorded, and no synthetic heartbeat event is emitted.
    """

    lease = ledger.claim_next_ready(owner=owner, lease_seconds=lease_seconds)
    if lease is None:
        return DispatchResult(dispatched=False, model_calls=0)
    if dispatch is not None:
        dispatch(lease)
    return DispatchResult(
        dispatched=True,
        model_calls=1,
        task_id=lease.task_id,
        reason="dispatched",
    )
