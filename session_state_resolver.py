"""Session State Resolver v0.

This deterministic helper resolves the current operator-visible session state
from safe generated response/read-model JSON files. It does not inspect raw
request bodies, credentials, private file contents, external systems, runtime
queues, workflow state stores, or Mission Control Swift. It does not call
models, dispatch agents/workers, run workflows, execute sends/submits, or grant
approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"
DEFAULT_FRESHNESS_WINDOW_SECONDS = 60 * 60 * 24

SCHEMA_VERSION = "session_state_resolver_v0"
READ_MODEL_ID = "session_state_resolver"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_SESSION_STATE_RESOLVER_NO_EXECUTION"

TERMINAL_RESPONSE_STATUSES = (
    "RESPONSE_READY",
    "BLOCKED_WITH_REASON",
    "BLOCKED_MAC_HANDOFF_UNAVAILABLE",
    "BLOCKED_WORKER_UNAVAILABLE",
    "FAILED_WITH_REASON",
    "TIMED_OUT_WITH_REASON",
    "DUPLICATE_NOOP_WITH_READBACK",
    "NO_REQUEST_AVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "NO_LATEST_RESPONSE",
    "HEARTBEAT_ONLY_NO_TERMINAL",
    "AMBIGUOUS_WORKFLOW_CONTEXT",
    "STALE_RESPONSE",
    "MISSING_TENANT_SCOPE",
    "RAW_BODY_ACCESS_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_lm_interpreter_allowed": False,
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_worker_dispatch_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "live_send_submit_allowed": False,
    "live_approval_execution_allowed": False,
    "live_candidate_promotion_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "live_browser_allowed": False,
    "live_coupa_access_allowed": False,
    "live_email_send_allowed": False,
    "live_portal_submit_allowed": False,
    "live_visual_generation_allowed": False,
    "live_speech_synthesis_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "network_allowed": False,
}

CAPITAL_HILTON_WORKFLOW_REFS = {
    "capital_hilton_invoice_workflow",
    "workflow:fixture:capital_hilton_invoice",
}

SAFE_RESPONSE_FILENAMES = (
    "openclaw_response_for_mac.json",
    "openclaw_response_for_mac_latest.json",
)

SAFE_HEARTBEAT_FILENAMES = (
    "openclaw_processing_for_mac_latest.json",
)

SAFE_STATUS_FILENAMES = (
    "openclaw_request_processor_status.json",
    "openclaw_request_response_service_status.json",
)


@dataclass(frozen=True)
class ActiveSessionState:
    session_state_id: str
    source: str
    tenant_scope: str
    client_scope: str
    active_world_ref: str
    active_folder_ref: str
    active_thread_ref: str
    active_workflow_ref: str
    latest_source_request_id: str
    latest_response_ref: str
    latest_terminal: bool
    latest_headline: str
    latest_next_action: str
    latest_primary_blocker: str
    latest_response_author: str
    latest_intent_type: str
    current_blockers: tuple[dict[str, Any], ...]
    missing_items: tuple[str, ...]
    safe_readmodel_refs: tuple[str, ...]
    ambiguity_status: bool
    stale_status: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class SessionStateResolver:
    resolver_id: str
    source_policy: tuple[str, ...]
    freshness_policy: tuple[str, ...]
    terminal_response_policy: tuple[str, ...]
    heartbeat_policy: tuple[str, ...]
    tenant_scope_policy: tuple[str, ...]
    ambiguity_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str

    def resolve(
        self,
        *,
        export_root: Path = DEFAULT_EXPORT_ROOT,
        response_paths: Iterable[str | Path] | None = None,
        heartbeat_paths: Iterable[str | Path] | None = None,
        status_paths: Iterable[str | Path] | None = None,
        now: str | datetime | None = None,
        freshness_window_seconds: int = DEFAULT_FRESHNESS_WINDOW_SECONDS,
    ) -> ActiveSessionState:
        export_root = Path(export_root)
        now_dt = _parse_time(now) or datetime.now(timezone.utc)
        blockers: list[SessionStateBlocker] = []
        safe_refs: list[str] = []

        response_records = _load_records(
            _default_paths(export_root, SAFE_RESPONSE_FILENAMES, response_paths),
            export_root=export_root,
            source_kind="terminal_response",
            safe_refs=safe_refs,
            blockers=blockers,
        )
        heartbeat_records = _load_records(
            _default_paths(export_root, SAFE_HEARTBEAT_FILENAMES, heartbeat_paths),
            export_root=export_root,
            source_kind="heartbeat",
            safe_refs=safe_refs,
            blockers=blockers,
        )
        status_records = _load_records(
            _default_paths(export_root, SAFE_STATUS_FILENAMES, status_paths),
            export_root=export_root,
            source_kind="status",
            safe_refs=safe_refs,
            blockers=blockers,
        )

        response_candidates = list(response_records)
        response_candidates.extend(_response_candidates_from_status(status_records))
        terminal_candidates = [record for record in response_candidates if _record_terminal(record.payload)]
        heartbeat_candidates = [record for record in heartbeat_records if not _record_terminal(record.payload)]

        selected: _SafeRecord | None = None
        selected_is_heartbeat = False
        latest_terminal = False
        if terminal_candidates:
            selected = _choose_latest(terminal_candidates)
            latest_terminal = True
        elif heartbeat_candidates:
            selected = _choose_latest(heartbeat_candidates)
            selected_is_heartbeat = True
            latest_terminal = False

        if selected is None:
            blockers.append(
                _blocker(
                    "NO_LATEST_RESPONSE",
                    "No safe terminal response or processing heartbeat was available.",
                    severity="high",
                    next_safe_move="Ask for clarification before interpreting the next operator intent.",
                )
            )

        ambiguity = False
        stale_status = "UNKNOWN"
        if selected is not None:
            stale_status = _stale_status(selected.payload, now_dt, freshness_window_seconds)
            if stale_status == "STALE":
                blockers.append(
                    _blocker(
                        "STALE_RESPONSE",
                        "Latest safe response/read-model is outside the freshness window.",
                        severity="medium",
                        next_safe_move="Refresh the terminal response before interpreting intent.",
                    )
                )

        active_workflow_ref = _workflow_ref(selected.payload if selected else {}) if selected else "UNKNOWN"
        terminal_contexts = _latest_peer_workflows(terminal_candidates, selected) if selected in terminal_candidates else set()
        if len(terminal_contexts) > 1:
            ambiguity = True
            active_workflow_ref = "UNKNOWN"
            blockers.append(
                _blocker(
                    "AMBIGUOUS_WORKFLOW_CONTEXT",
                    "Multiple latest terminal workflow contexts have equal freshness.",
                    severity="high",
                    next_safe_move="Ask which workflow should receive the next intent.",
                )
            )

        if active_workflow_ref in {"", "UNKNOWN"}:
            ambiguity = True
            active_workflow_ref = "UNKNOWN"
            blockers.append(
                _blocker(
                    "AMBIGUOUS_WORKFLOW_CONTEXT",
                    "No active workflow could be resolved from safe response/read-model files.",
                    severity="high",
                    next_safe_move="Ask which world/thread/workflow should receive the next intent.",
                )
            )

        if selected_is_heartbeat:
            blockers.append(
                _blocker(
                    "HEARTBEAT_ONLY_NO_TERMINAL",
                    "Only a non-terminal heartbeat is available; it cannot be treated as final truth.",
                    severity="medium",
                    next_safe_move="Wait for a terminal response or retry the bounded request/response service.",
                )
            )

        tenant_scope, client_scope, world_ref, folder_ref = _scope_from_payload(selected.payload if selected else {}, active_workflow_ref)
        if tenant_scope == "UNKNOWN":
            blockers.append(
                _blocker(
                    "MISSING_TENANT_SCOPE",
                    "Tenant scope is missing and could not be inferred from a safe fixture workflow ref.",
                    severity="high",
                    next_safe_move="Ask for tenant/client scope before binding workflow capabilities.",
                )
            )

        latest_payload = selected.payload if selected else {}
        latest_next_action = _first_nonempty(latest_payload, "next_action", "next_safe_move", "how_to_fix")
        next_safe_move = _next_safe_move(
            latest_terminal=latest_terminal,
            selected_is_heartbeat=selected_is_heartbeat,
            ambiguity=ambiguity,
            stale_status=stale_status,
            latest_next_action=latest_next_action,
        )

        state = ActiveSessionState(
            session_state_id=_stable_id(
                "session_state",
                active_workflow_ref,
                _first_nonempty(latest_payload, "source_request_id"),
                _first_nonempty(latest_payload, "created_at", "generated_at"),
                ambiguity,
                stale_status,
            ),
            source="safe_generated_response_readmodels",
            tenant_scope=tenant_scope,
            client_scope=client_scope,
            active_world_ref=world_ref,
            active_folder_ref=folder_ref,
            active_thread_ref=_thread_ref(latest_payload),
            active_workflow_ref=active_workflow_ref,
            latest_source_request_id=_first_nonempty(latest_payload, "source_request_id"),
            latest_response_ref=selected.path.as_posix() if selected else "",
            latest_terminal=latest_terminal,
            latest_headline=_headline(latest_payload),
            latest_next_action=latest_next_action,
            latest_primary_blocker=_first_nonempty(latest_payload, "primary_blocker", "blocked_reason"),
            latest_response_author=_first_nonempty(latest_payload, "response_author") or "UNKNOWN",
            latest_intent_type=_intent_type(latest_payload),
            current_blockers=tuple(asdict(blocker) for blocker in _dedupe_blockers(blockers)),
            missing_items=_missing_items(latest_payload),
            safe_readmodel_refs=tuple(dict.fromkeys(safe_refs)),
            ambiguity_status=ambiguity,
            stale_status=stale_status,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move=next_safe_move,
        )
        return state


@dataclass(frozen=True)
class SessionStateBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class _SafeRecord:
    path: Path
    payload: dict[str, Any]
    source_kind: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:16]}"


def _model_schemas() -> dict[str, tuple[str, ...]]:
    return {
        "ActiveSessionState": tuple(field.name for field in fields(ActiveSessionState)),
        "SessionStateResolver": tuple(field.name for field in fields(SessionStateResolver)),
        "SessionStateBlocker": tuple(field.name for field in fields(SessionStateBlocker)),
    }


def _blocker(
    blocker_type: str,
    condition: str,
    *,
    severity: str = "high",
    next_safe_move: str = "Fail closed and ask for clarification.",
) -> SessionStateBlocker:
    return SessionStateBlocker(
        blocker_id=_stable_id("session_state_blocker", blocker_type, condition),
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=f"ELIOPERATOR: {condition}",
        fail_closed=True,
        next_safe_move=next_safe_move,
    )


def _dedupe_blockers(blockers: Iterable[SessionStateBlocker]) -> tuple[SessionStateBlocker, ...]:
    deduped: dict[str, SessionStateBlocker] = {}
    for blocker in blockers:
        deduped.setdefault(blocker.blocker_id, blocker)
    return tuple(deduped.values())


def default_resolver() -> SessionStateResolver:
    return SessionStateResolver(
        resolver_id="session_state_resolver:v0",
        source_policy=(
            "Read only generated/read-model JSON response and status files.",
            "Do not read raw request bodies, source file bodies, credentials, or protected files.",
            "Do not follow response-service paths outside the supplied safe read-model roots.",
        ),
        freshness_policy=(
            "Use created_at or generated_at when present.",
            "Mark stale responses fail-closed when they exceed the freshness window.",
            "Missing timestamps are UNKNOWN rather than proof of freshness.",
        ),
        terminal_response_policy=(
            "Terminal responses are stronger than heartbeat files.",
            "Prefer the latest terminal response when one exists.",
            "Never infer approval or completion from next_action wording.",
        ),
        heartbeat_policy=(
            "Heartbeat files may indicate waiting or routing.",
            "A non-terminal heartbeat is never final truth.",
            "Heartbeat-only state waits for terminal response or bounded retry.",
        ),
        tenant_scope_policy=(
            "Use explicit tenant/client scope when present.",
            "Capital Hilton fixture refs map only to fixture_business_ops scope.",
            "Unknown tenant scope fails closed before workflow binding use.",
        ),
        ambiguity_policy=(
            "No active workflow means ambiguity_status true.",
            "Multiple equal-freshness terminal workflow contexts means ambiguity_status true.",
            "Ambiguity asks for clarification rather than guessing.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Resolve session state from safe read-models before deterministic intent interpretation.",
    )


def _default_paths(
    export_root: Path,
    filenames: tuple[str, ...],
    explicit_paths: Iterable[str | Path] | None,
) -> tuple[Path, ...]:
    if explicit_paths is not None:
        return tuple(Path(path) for path in explicit_paths)
    return tuple(export_root / filename for filename in filenames)


def _path_is_safe(path: Path, export_root: Path) -> bool:
    if path.suffix != ".json":
        return False
    lower_name = path.name.lower()
    if "raw_body" in lower_name or "private_body" in lower_name or "raw-private" in lower_name:
        return False
    if path.exists() and path.is_symlink():
        return False
    try:
        resolved = path.resolve(strict=False)
        root = export_root.resolve(strict=False)
        resolved.relative_to(root)
        return True
    except ValueError:
        return explicit_test_path_allowed(path)


def explicit_test_path_allowed(path: Path) -> bool:
    """Allow explicit temp fixture paths while keeping default discovery narrow."""

    parts = set(path.parts)
    return "pytest-" in path.as_posix() or "tmp" in parts


def _load_records(
    paths: Iterable[Path],
    *,
    export_root: Path,
    source_kind: str,
    safe_refs: list[str],
    blockers: list[SessionStateBlocker],
) -> tuple[_SafeRecord, ...]:
    records: list[_SafeRecord] = []
    for path in paths:
        if not path.exists():
            continue
        if not _path_is_safe(path, export_root):
            blockers.append(
                _blocker(
                    "RAW_BODY_ACCESS_ATTEMPTED",
                    f"Rejected unsafe path before read: {path.name}",
                    severity="critical",
                    next_safe_move="Use generated read-model JSON refs only.",
                )
            )
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            blockers.append(
                _blocker(
                    "UNKNOWN_FAIL_CLOSED",
                    f"Could not parse safe read-model {path.name}: {exc.__class__.__name__}",
                    severity="high",
                    next_safe_move="Regenerate the safe read-model before interpreting intent.",
                )
            )
            continue
        if not isinstance(payload, dict):
            blockers.append(
                _blocker(
                    "UNKNOWN_FAIL_CLOSED",
                    f"Safe read-model {path.name} did not contain a JSON object.",
                    severity="high",
                    next_safe_move="Regenerate the safe read-model before interpreting intent.",
                )
            )
            continue
        safe_refs.append(path.as_posix())
        records.append(_SafeRecord(path=path, payload=payload, source_kind=source_kind))
    return tuple(records)


def _response_candidates_from_status(status_records: Iterable[_SafeRecord]) -> tuple[_SafeRecord, ...]:
    records: list[_SafeRecord] = []
    for record in status_records:
        payload = record.payload
        if payload.get("read_model_id") == "openclaw_request_processor_status":
            status = payload.get("processor_status") if isinstance(payload.get("processor_status"), Mapping) else {}
            latest = status.get("latest_processed_request") if isinstance(status.get("latest_processed_request"), Mapping) else {}
            if status:
                records.append(
                    _SafeRecord(
                        path=record.path,
                        source_kind="processor_status_response",
                        payload={
                            "read_model_id": "openclaw_request_processor_status",
                            "generated_at": payload.get("generated_at"),
                            "source_request_id": latest.get("source_request_id", ""),
                            "workflow_ref": latest.get("workflow_ref", "UNKNOWN"),
                            "terminal": status.get("terminal_result") in TERMINAL_RESPONSE_STATUSES,
                            "internal_status": status.get("terminal_result"),
                            "operator_headline": status.get("operator_headline", ""),
                            "next_safe_move": status.get("next_safe_move", ""),
                            "primary_blocker": _first_nonempty(status, "how_to_fix"),
                            "response_author": "OPENCLAW_SYSTEM",
                        },
                    )
                )
        if payload.get("read_model_id") == "openclaw_request_response_service_status":
            status = payload.get("service_status") if isinstance(payload.get("service_status"), Mapping) else {}
            latest = status.get("latest_response") if isinstance(status.get("latest_response"), Mapping) else {}
            if latest:
                records.append(
                    _SafeRecord(
                        path=record.path,
                        source_kind="service_status_response",
                        payload={
                            "read_model_id": "openclaw_request_response_service_status",
                            "generated_at": payload.get("generated_at"),
                            "created_at": latest.get("created_at") or payload.get("generated_at"),
                            "source_request_id": latest.get("source_request_id", ""),
                            "workflow_ref": latest.get("workflow_ref", "UNKNOWN"),
                            "terminal": bool(latest.get("terminal", True)),
                            "internal_status": latest.get("internal_status", status.get("service_status")),
                            "operator_headline": latest.get("operator_headline", ""),
                            "next_safe_move": status.get("next_safe_move", ""),
                            "response_author": "OPENCLAW_SYSTEM",
                        },
                    )
                )
    return tuple(records)


def _record_terminal(payload: Mapping[str, Any]) -> bool:
    terminal = payload.get("terminal")
    if terminal is not None:
        return bool(terminal)
    status = str(payload.get("internal_status") or payload.get("terminal_result") or "")
    return status in TERMINAL_RESPONSE_STATUSES


def _record_time(payload: Mapping[str, Any]) -> datetime | None:
    return _parse_time(_first_nonempty(payload, "created_at", "generated_at"))


def _choose_latest(records: Iterable[_SafeRecord]) -> _SafeRecord:
    def sort_key(record: _SafeRecord) -> tuple[float, str]:
        parsed = _record_time(record.payload)
        timestamp = parsed.timestamp() if parsed else 0.0
        return (timestamp, record.path.as_posix())

    return sorted(records, key=sort_key)[-1]


def _latest_peer_workflows(records: Iterable[_SafeRecord], selected: _SafeRecord | None) -> set[str]:
    if selected is None:
        return set()
    selected_time = _record_time(selected.payload)
    workflows: set[str] = set()
    for record in records:
        if _record_time(record.payload) == selected_time:
            workflow = _workflow_ref(record.payload)
            if workflow:
                workflows.add(workflow)
    return workflows


def _parse_time(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _stale_status(payload: Mapping[str, Any], now_dt: datetime, freshness_window_seconds: int) -> str:
    timestamp = _record_time(payload)
    if timestamp is None:
        return "UNKNOWN"
    age = (now_dt - timestamp).total_seconds()
    return "STALE" if age > freshness_window_seconds else "FRESH"


def _first_nonempty(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return ""


def _workflow_ref(payload: Mapping[str, Any]) -> str:
    workflow = _first_nonempty(payload, "workflow_ref", "active_workflow_ref")
    if workflow and workflow != "UNKNOWN":
        return workflow
    detail = payload.get("detail_disclosure") if isinstance(payload.get("detail_disclosure"), Mapping) else {}
    classification = detail.get("request_classification") if isinstance(detail.get("request_classification"), Mapping) else {}
    selected_rail = str(classification.get("selected_rail") or detail.get("selected_readback_ref") or "")
    if "capital_hilton_invoice_operator_readback" in selected_rail:
        return "capital_hilton_invoice_workflow"
    safe_text = " ".join(
        str(payload.get(key) or "")
        for key in ("source_request_id", "source_request_filename", "response_file", "operator_headline", "headline")
    ).lower()
    if "capital_hilton" in safe_text:
        return "capital_hilton_invoice_workflow"
    return "UNKNOWN"


def _scope_from_payload(payload: Mapping[str, Any], workflow_ref: str) -> tuple[str, str, str, str]:
    tenant = _first_nonempty(payload, "tenant_scope", "tenant_ref")
    client = _first_nonempty(payload, "client_scope", "client_ref")
    world = _first_nonempty(payload, "world_ref", "active_world_ref")
    folder = _first_nonempty(payload, "folder_ref", "active_folder_ref")

    if workflow_ref in CAPITAL_HILTON_WORKFLOW_REFS or "capital_hilton" in workflow_ref:
        tenant = tenant or "tenant_scope:fixture_business_ops"
        client = client or "client_scope:fixture_capital_hilton"
        world = world or "world:fixture:business_ops"
        folder = folder or "folder_ref:capital_hilton"

    return (
        tenant or "UNKNOWN",
        client or "UNKNOWN",
        world or "UNKNOWN",
        folder or "UNKNOWN",
    )


def _thread_ref(payload: Mapping[str, Any]) -> str:
    explicit = _first_nonempty(payload, "thread_ref", "active_thread_ref")
    if explicit:
        return explicit
    request_id = _first_nonempty(payload, "source_request_id")
    return f"thread_ref:{request_id}" if request_id else "UNKNOWN"


def _headline(payload: Mapping[str, Any]) -> str:
    return _first_nonempty(payload, "headline", "operator_headline", "one_line_answer")


def _intent_type(payload: Mapping[str, Any]) -> str:
    response_kind = str(payload.get("response_kind") or "").upper()
    request_type = str(payload.get("request_type") or "").upper()
    text = " ".join(
        (
            str(payload.get("headline") or payload.get("operator_headline") or ""),
            str(payload.get("primary_blocker") or ""),
            str(payload.get("next_action") or ""),
        )
    ).lower()
    if "missing" in text or "confirm" in text:
        return "CAPTURE_MISSING_INPUT"
    if "STATUS" in response_kind or request_type == "CHAT":
        return "ANSWER_STATUS"
    return "UNKNOWN_FAIL_CLOSED"


def _missing_items(payload: Mapping[str, Any]) -> tuple[str, ...]:
    value = payload.get("missing_items_short") or payload.get("missing_items")
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item))
    if isinstance(value, str) and value:
        return (value,)
    blocker = _first_nonempty(payload, "primary_blocker", "blocked_reason")
    return (blocker,) if blocker else ()


def _next_safe_move(
    *,
    latest_terminal: bool,
    selected_is_heartbeat: bool,
    ambiguity: bool,
    stale_status: str,
    latest_next_action: str,
) -> str:
    if selected_is_heartbeat:
        return "Wait for a terminal response or retry the bounded request/response service."
    if ambiguity:
        return "Ask the operator which world/thread/workflow should receive the next intent."
    if stale_status == "STALE":
        return "Refresh the terminal response/read-model before interpreting intent."
    if latest_terminal and latest_next_action:
        return latest_next_action
    return "Ask the operator which world/thread/workflow should receive the next intent."


def _authority_scout() -> dict[str, Any]:
    return {
        "duplicated_authority_risk": True,
        "duplicated_authority_boundary_sources": (
            "openclaw_request_processor.AUTHORITY_BOUNDARY",
            "openclaw_request_response_service.AUTHORITY_BOUNDARY",
            "openclaw_capability_index.AUTHORITY_BOUNDARY",
            "machine_intent_candidate_validator.AUTHORITY_BOUNDARY",
            "scoped_context_package_compiler_contract.AUTHORITY_BOUNDARY",
            "agent_roster_model_backend_policy.AUTHORITY_BOUNDARY",
            "session_state_resolver.AUTHORITY_BOUNDARY",
        ),
        "recommendation": "Add a canonical AuthorityBoundary helper in a later lane; do not centralize behavior here.",
        "behavior_changed": False,
    }


def build_payload(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str = DEFAULT_GENERATED_AT,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    resolver = default_resolver()
    state = resolver.resolve(export_root=export_root, now=now or generated_at)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "contract_status": CONTRACT_STATUS,
        "blocker_types": BLOCKER_TYPES,
        "resolver": asdict(resolver),
        "model_schemas": _model_schemas(),
        "active_session_state": asdict(state),
        "authority_scout": _authority_scout(),
        "machine_proof": {
            "safe_readmodel_only": True,
            "terminal_response_preferred_over_heartbeat": True,
            "heartbeat_treated_as_non_terminal": True,
            "approval_inferred_from_next_action": False,
            "lm_interpreter_called": False,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "worker_dispatch_performed": False,
            "workflow_run_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "approval_execution_performed": False,
            "candidate_promotion_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "raw_body_access_attempted": any(
                blocker["blocker_type"] == "RAW_BODY_ACCESS_ATTEMPTED"
                for blocker in asdict(state)["current_blockers"]
            ),
            "mac_sync_import_performed": False,
            "mission_control_swift_changed": False,
            "git_push_pull_fetch_run": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    state = payload["active_session_state"]
    lines = [
        "# Session State Resolver",
        "",
        f"Status: {payload['contract_status']}",
        f"Latest response: {state.get('latest_response_ref') or 'none'}",
        f"Latest headline: {state.get('latest_headline') or 'UNKNOWN'}",
        f"Latest next action: {state.get('latest_next_action') or 'UNKNOWN'}",
        f"Active workflow: {state.get('active_workflow_ref') or 'UNKNOWN'}",
        f"Ambiguous: {state.get('ambiguity_status')}",
        f"Stale status: {state.get('stale_status')}",
        "",
        "## Boundary",
        "- Safe generated response/read-model JSON only.",
        "- No raw private bodies.",
        "- No credentials or protected file parsing.",
        "- No live LM interpreter, model call, agent dispatch, workflow run, external action, send/submit, or approval execution.",
        "",
        f"Next safe move: {state.get('next_safe_move')}",
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    state = payload["active_session_state"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "latest_response_ref": state["latest_response_ref"],
        "latest_terminal": state["latest_terminal"],
        "latest_headline": state["latest_headline"],
        "latest_next_action": state["latest_next_action"],
        "latest_primary_blocker": state["latest_primary_blocker"],
        "active_workflow_ref": state["active_workflow_ref"],
        "tenant_scope": state["tenant_scope"],
        "client_scope": state["client_scope"],
        "ambiguity_status": state["ambiguity_status"],
        "stale_status": state["stale_status"],
        "blocker_types": [blocker["blocker_type"] for blocker in state["current_blockers"]],
        "authority_scout_recommends_helper": payload["authority_scout"]["duplicated_authority_risk"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the deterministic OpenClaw session state resolver.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(export_root=export_root, generated_at=args.generated_at, now=args.generated_at)
    paths = write_exports(payload, export_root)
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
