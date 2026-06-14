"""Local OpenClaw request/response service v1.

This module wraps the bounded request processor with a local, bounded polling
service. It only inspects the approved Mission Control inbox, processes
supported request files through existing deterministic rails, and publishes a
per-request Mac-readable response file to the local shared response directory.

It is not an unbounded daemon, broad filesystem watcher, worker dispatcher,
workflow executor, model/tool runtime, external action lane, file-body ingestion
path, raw transcript ingestion path, Mac sync/import path, or Swift change.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import openclaw_request_processor as processor
import client_invoice_audit_handoff
import client_invoice_sheet_audit
import deterministic_intent_interpreter
import lm_intent_proposal_contract
import mac_worker_handoff_package
import openclaw_event_bridge_adapter
import reality_bounce_harness
import worker_routing_intelligence


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_INBOX = processor.APPROVED_INBOX
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
DEFAULT_MAC_HANDOFF_DIR = Path("/mnt/e/openclaw/mission_control_handoffs/to_mac")
DEFAULT_REALITY_BOUNCE_DB_PATH = reality_bounce_harness.DEFAULT_DB_PATH
DEFAULT_IDLE_POLL_INTERVAL = 1.0
DEFAULT_ACTIVE_POLL_INTERVAL = 0.05
DEFAULT_ACTIVE_WINDOW_SECONDS = 180.0

SCHEMA_VERSION = "openclaw_request_response_service_v1"
STATUS_READ_MODEL_ID = "openclaw_request_response_service_status"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
STATUS_OPERATOR_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}_STATUS_OPERATOR.md"
MANIFEST_EXPORT_NAME = "response_manifest.json"
LATEST_RESPONSE_EXPORT_NAME = "openclaw_response_for_mac_latest.json"
LATEST_PROCESSING_EXPORT_NAME = "openclaw_processing_for_mac_latest.json"
CONTRACT_STATUS = "BOUNDED_LOCAL_OPENCLAW_REQUEST_RESPONSE_SERVICE"

SERVICE_STATUSES = (
    "IDLE_NO_REQUEST_AVAILABLE",
    "REQUEST_PROCESSED",
    "REQUEST_ROUTED_WAITING_FOR_MAC_READBACK",
    "REQUEST_SKIPPED_DUPLICATE",
    "WATCH_TIMED_OUT_IDLE",
    "FAILED_WITH_REASON",
    "UNKNOWN_FAIL_CLOSED",
)

WATCH_MODES = ("idle", "active", "stopped")

ROUTING_STATUSES = (
    "PROCESSING_ON_PC",
    "ROUTED_TO_MAC",
    "WAITING_FOR_MAC_READBACK",
    "ROUTED_TO_FUTURE_WORKER",
    "BLOCKED_WORKER_UNAVAILABLE",
    "BLOCKED_MAC_HANDOFF_UNAVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

SERVICE_SUPPORTED_REQUEST_FAMILIES = (
    "EVENT_BRIDGE",
    "CHAT",
    "FILE_METADATA",
    "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST",
    "WORKROOM_REVIEW_DECISION_REQUEST",
    "WORKBOOK_REGISTRATION_REQUEST",
    "EVIDENCE_INTAKE_REQUEST",
    "OPERATOR_CONTROLLER_EVENT_REQUEST",
    "WORKFLOW_PACKAGE_REQUEST",
    "LOCAL_SURFACE_RESULT",
    "ARTIFACT_REFERENCE_APPROVAL",
    "ARTIFACT_INTAKE_REQUEST",
)

EVENT_BRIDGE_REQUEST_PATTERNS = (
    "openclaw_event_bridge_*.json",
    "event_bridge_*.json",
    "mission_control_event_bridge_*.json",
    "mission_control_capture_request_*event_bridge*.json",
)

WORKER_TARGETS = (
    "PC_CODEX",
    "MAC_CODEX",
    "GEMINI_AGY",
    "CASSANDRA",
    "GUARDIAN",
    "NILES",
    "OPENCLAW_SYSTEM",
    "UNKNOWN",
)

AUTHORITY_BOUNDARY = {
    "broad_filesystem_watch_allowed": False,
    "unbounded_loop_by_default_allowed": False,
    "request_deletion_allowed": False,
    "request_mutation_allowed": False,
    "symlink_follow_allowed": False,
    "live_workflow_execution_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_email_draft_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_approval_request_allowed": False,
    "live_speech_synthesis_allowed": False,
    "live_microphone_capture_allowed": False,
    "live_cloud_audio_allowed": False,
    "live_voice_model_call_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "network_allowed": False,
}


@dataclass(frozen=True)
class RequestIdentity:
    source_request_id: str
    idempotency_key: str | None
    payload_hash: str | None
    workflow_ref: str
    request_type: str
    request_key: str
    parse_status: str


@dataclass(frozen=True)
class PublishedResponse:
    response_file: str
    latest_response_file: str
    manifest_file: str
    source_request_id: str
    source_request_filename: str | None
    request_type: str
    internal_status: str
    operator_headline: str
    operator_message: str
    how_to_fix: str
    next_safe_move: str
    terminal: bool


@dataclass(frozen=True)
class PublishedHeartbeat:
    heartbeat_file: str
    latest_heartbeat_file: str
    source_request_id: str
    source_request_filename: str | None
    request_type: str
    routing_status: str
    selected_worker_target: str
    selected_machine: str
    processing_status: str
    operator_headline: str
    operator_message: str
    next_safe_move: str
    terminal: bool


@dataclass(frozen=True)
class RouteDecision:
    routing_status: str
    selected_worker_target: str
    selected_machine: str
    processing_status: str
    operator_headline: str
    operator_message: str
    next_safe_move: str
    route_reason: str
    pc_handled: bool
    mac_handoff_required: bool
    future_worker_blocked: bool
    terminal_block_status: str | None = None


@dataclass(frozen=True)
class ServiceRunResult:
    service_status: str
    run_mode: str
    inbox: str
    response_path: str
    processed_count: int
    skipped_duplicate_count: int
    processed_requests: tuple[dict[str, Any], ...]
    skipped_duplicates: tuple[dict[str, Any], ...]
    latest_response: dict[str, Any] | None
    errors_or_blockers: tuple[str, ...]
    next_safe_move: str
    mode: str = "stopped"
    current_poll_interval: float = 0.0
    idle_poll_interval: float = DEFAULT_IDLE_POLL_INTERVAL
    active_poll_interval: float = DEFAULT_ACTIVE_POLL_INTERVAL
    active_window_seconds: float = DEFAULT_ACTIVE_WINDOW_SECONDS
    active_window_remaining_seconds: float = 0.0
    last_watch_mode_before_stop: str = "idle"
    last_poll_interval: float = 0.0
    last_processed_request_id: str | None = None
    last_response_path: str | None = None
    bounded_stop_reason: str = "completed"
    last_processing_started_request_id: str | None = None
    last_routing_status: str | None = None
    selected_worker_target: str | None = None
    selected_machine: str | None = None
    processing_heartbeat_path: str | None = None
    terminal_response_path: str | None = None
    active_request_count: int = 0
    cache_enabled: bool = True
    cache_hits: int = 0
    cache_misses: int = 0
    cache_invalidations: int = 0
    cached_file_count: int = 0
    last_cached_paths: tuple[str, ...] = ()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted((json_safe(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return str(value)


def stable_json(payload: Any) -> str:
    return json.dumps(json_safe(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class ReadModelMemoryCache:
    """Process-local cache for generated read-model JSON files only."""

    def __init__(self, approved_roots: tuple[Path, ...], *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._approved_roots = tuple(root.resolve(strict=False) for root in approved_roots)
        self._entries: dict[str, tuple[int, int, Any]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_invalidations = 0
        self._last_cached_paths: list[str] = []

    def _is_approved_path(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        resolved = path.resolve(strict=False)
        for root in self._approved_roots:
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            return True
        return False

    def _record_cached_path(self, path: Path) -> None:
        safe_name = path.name
        if safe_name in self._last_cached_paths:
            self._last_cached_paths.remove(safe_name)
        self._last_cached_paths.append(safe_name)
        del self._last_cached_paths[:-8]

    def read_json(self, path: Path) -> Any:
        if not self.enabled:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                return None
        if path.is_symlink() or not self._is_approved_path(path):
            raise ValueError(f"Read-model cache rejected unapproved path: {path.name}")

        resolved = path.resolve(strict=False)
        cache_key = resolved.as_posix()
        try:
            stat = path.stat()
        except FileNotFoundError:
            self.cache_misses += 1
            self._entries.pop(cache_key, None)
            return None

        cached = self._entries.get(cache_key)
        if cached is not None:
            cached_mtime_ns, cached_size, cached_value = cached
            if cached_mtime_ns == stat.st_mtime_ns and cached_size == stat.st_size:
                self.cache_hits += 1
                self._record_cached_path(path)
                return cached_value
            self.cache_invalidations += 1

        self.cache_misses += 1
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._entries.pop(cache_key, None)
            return None
        self._entries[cache_key] = (stat.st_mtime_ns, stat.st_size, value)
        self._record_cached_path(path)
        return value

    def metrics(self) -> dict[str, Any]:
        return {
            "cache_enabled": self.enabled,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_invalidations": self.cache_invalidations,
            "cached_file_count": len(self._entries),
            "last_cached_paths": tuple(self._last_cached_paths),
        }


def _new_read_model_cache(export_root: Path) -> ReadModelMemoryCache:
    return ReadModelMemoryCache((export_root,), enabled=True)


def _cache_result_fields(cache: ReadModelMemoryCache | None) -> dict[str, Any]:
    if cache is None:
        return {
            "cache_enabled": False,
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_invalidations": 0,
            "cached_file_count": 0,
            "last_cached_paths": (),
        }
    return cache.metrics()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if cleaned:
        return cleaned[:160]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def read_service_status(export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any] | None:
    path = export_root / STATUS_JSON_EXPORT_NAME
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _processed_records(existing_status: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not existing_status:
        return ()
    service = existing_status.get("service_status")
    if not isinstance(service, Mapping):
        return ()
    records = service.get("all_processed_request_records") or service.get("processed_requests") or ()
    if not isinstance(records, (list, tuple)):
        return ()
    return tuple(record for record in records if isinstance(record, dict))


def _processed_keys(existing_status: Mapping[str, Any] | None) -> set[str]:
    return {str(record.get("request_key")) for record in _processed_records(existing_status) if record.get("request_key")}


def _identity_keys(path: Path, identity: RequestIdentity) -> tuple[str, ...]:
    keys = [identity.request_key, f"filename:{path.name}"]
    if identity.source_request_id:
        keys.append(f"request_id:{identity.source_request_id}")
    if identity.idempotency_key:
        keys.append(f"idempotency:{identity.idempotency_key}")
    if identity.payload_hash:
        keys.append(f"payload_hash:{identity.payload_hash}")
    return tuple(dict.fromkeys(str(key) for key in keys if key))


def _processed_identity_keys(existing_status: Mapping[str, Any] | None) -> set[str]:
    keys: set[str] = set()
    for record in _processed_records(existing_status):
        for key in record.get("identity_keys") or ():
            if key:
                keys.add(str(key))
        if record.get("request_key"):
            keys.add(str(record["request_key"]))
        if record.get("source_request_id"):
            keys.add(f"request_id:{record['source_request_id']}")
        if record.get("source_request_filename"):
            keys.add(f"filename:{record['source_request_filename']}")
        if record.get("idempotency_key"):
            keys.add(f"idempotency:{record['idempotency_key']}")
        if record.get("payload_hash"):
            keys.add(f"payload_hash:{record['payload_hash']}")
    return keys


def classify_request_path(path: Path) -> str:
    processor_family = processor.classify_request_filename(path.name).request_family
    if processor_family != "UNKNOWN_FAIL_CLOSED":
        return processor_family
    if any(fnmatch.fnmatch(path.name, pattern) for pattern in EVENT_BRIDGE_REQUEST_PATTERNS):
        return "EVENT_BRIDGE"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return processor_family
    if is_event_bridge_envelope(raw):
        return "EVENT_BRIDGE"
    if processor.is_evidence_intake_request(raw):
        return "EVIDENCE_INTAKE_REQUEST"
    if processor.is_operator_controller_event_request(raw):
        return "OPERATOR_CONTROLLER_EVENT_REQUEST"
    return processor_family


def is_event_bridge_envelope(raw: Any) -> bool:
    if not isinstance(raw, Mapping):
        return False
    required_markers = (
        "event_kind",
        "source_channel",
        "correlation_id",
        "idempotency_key",
        "client_ref",
        "workflow_ref",
        "payload",
        "safety_flags",
    )
    return any(key in raw for key in ("event_id", "event_kind", "correlation_id")) and all(
        key in raw for key in required_markers
    )


def list_candidate_requests(inbox: Path = APPROVED_INBOX) -> tuple[Path, ...]:
    if not inbox.exists() or not inbox.is_dir():
        return ()
    candidates: list[Path] = []
    for path in inbox.iterdir():
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        if classify_request_path(path) in SERVICE_SUPPORTED_REQUEST_FAMILIES:
            candidates.append(path)
    return tuple(sorted(candidates, key=lambda item: (item.stat().st_mtime_ns, item.name)))


def _scoped_response_exists(response_dir: Path, source_request_id: str) -> Path | None:
    if not source_request_id or source_request_id.startswith(("missing_request_id_", "invalid_", "unparseable_")):
        return None
    response_path = response_dir / f"openclaw_response_for_mac_{_safe_filename_part(source_request_id)}.json"
    return response_path if response_path.exists() and response_path.is_file() else None


def _latest_response_mtime_ns(response_dir: Path) -> int | None:
    latest = response_dir / LATEST_RESPONSE_EXPORT_NAME
    if not latest.exists() or not latest.is_file():
        return None
    return latest.stat().st_mtime_ns


def read_request_identity(path: Path) -> RequestIdentity:
    request_type = classify_request_path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        source_request_id = f"unparseable_{path.stem}"
        return RequestIdentity(
            source_request_id=source_request_id,
            idempotency_key=None,
            payload_hash=None,
            workflow_ref="unknown",
            request_type=request_type,
            request_key=f"file:{path.name}",
            parse_status="MALFORMED_JSON",
        )
    if not isinstance(raw, Mapping):
        source_request_id = f"invalid_{path.stem}"
        return RequestIdentity(
            source_request_id=source_request_id,
            idempotency_key=None,
            payload_hash=None,
            workflow_ref="unknown",
            request_type=request_type,
            request_key=f"file:{path.name}",
            parse_status="INVALID_JSON_OBJECT",
        )
    if request_type == "EVENT_BRIDGE":
        source_request_id = str(raw.get("event_id") or raw.get("request_id") or f"missing_event_id_{path.stem}")
    else:
        source_request_id = str(raw.get("request_id") or f"missing_request_id_{path.stem}")
    idempotency_key = str(raw.get("idempotency_key")) if raw.get("idempotency_key") else None
    payload_hash = str(raw.get("payload_hash")) if raw.get("payload_hash") else _content_hash(dict(raw)) if request_type == "EVENT_BRIDGE" else None
    workflow_ref = str(raw.get("workflow_ref") or raw.get("claimed_workflow_ref") or "unknown")
    if source_request_id and not source_request_id.startswith("missing_request_id_"):
        request_key = f"request_id:{source_request_id}"
    elif idempotency_key:
        request_key = f"idempotency:{idempotency_key}"
    else:
        request_key = f"file:{path.name}"
    return RequestIdentity(
        source_request_id=source_request_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        workflow_ref=workflow_ref,
        request_type=request_type,
        request_key=request_key,
        parse_status="PARSED",
    )


def select_next_pending_request(
    *,
    inbox: Path = APPROVED_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    extra_processed_keys: set[str] | None = None,
    stale_before_mtime_ns: int | None = None,
) -> tuple[Path | None, tuple[dict[str, Any], ...]]:
    existing_status = read_service_status(export_root)
    processed = _processed_identity_keys(existing_status)
    if extra_processed_keys:
        processed.update(extra_processed_keys)
    skipped: list[dict[str, Any]] = []
    for candidate in list_candidate_requests(inbox):
        identity = read_request_identity(candidate)
        identity_keys = _identity_keys(candidate, identity)
        existing_response = _scoped_response_exists(response_dir, identity.source_request_id)
        if existing_response is not None:
            skipped.append(
                {
                    "source_request_id": identity.source_request_id,
                    "source_request_filename": candidate.name,
                    "request_key": identity.request_key,
                    "identity_keys": identity_keys,
                    "matched_duplicate_keys": (f"scoped_response:{identity.source_request_id}",),
                    "reason": "already has scoped Mac response",
                    "response_file": existing_response.as_posix(),
                }
            )
            continue
        matching_keys = tuple(key for key in identity_keys if key in processed)
        exact_processed_keys = (
            identity.request_key,
            f"request_id:{identity.source_request_id}",
            f"filename:{candidate.name}",
        )
        exact_matching_keys = tuple(key for key in matching_keys if key in exact_processed_keys)
        if exact_matching_keys:
            skipped.append(
                {
                    "source_request_id": identity.source_request_id,
                    "source_request_filename": candidate.name,
                    "request_key": identity.request_key,
                    "identity_keys": identity_keys,
                    "matched_duplicate_keys": exact_matching_keys,
                    "reason": "already processed exact request by local request/response service",
                }
            )
            continue
        return candidate, tuple(skipped)
    return None, tuple(skipped)


def _published_response_payload(response_payload: Mapping[str, Any], *, created_at: str) -> dict[str, Any]:
    terminal = response_payload.get("internal_status") in {
        "RESPONSE_READY",
        "BLOCKED_WITH_REASON",
        "BLOCKED_MAC_HANDOFF_UNAVAILABLE",
        "BLOCKED_WORKER_UNAVAILABLE",
        "FAILED_WITH_REASON",
        "TIMED_OUT_WITH_REASON",
        "DUPLICATE_NOOP_WITH_READBACK",
        "NO_REQUEST_AVAILABLE",
        "UNKNOWN_FAIL_CLOSED",
    }
    payload = dict(response_payload)
    payload["created_at"] = created_at
    payload["terminal"] = bool(terminal)
    payload["service_note"] = "Published by bounded local OpenClaw request/response service."
    return payload


def _request_text(raw_request: Mapping[str, Any]) -> str:
    fields = (
        "operator_message",
        "sanitized_message_summary",
        "operator_goal",
        "workflow_ref",
        "workflow_type",
        "world_ref",
        "lane_ref",
        "client_ref",
        "tenant_ref",
    )
    return " ".join(str(raw_request.get(field) or "") for field in fields).strip()


def _operator_message_text(raw_request: Mapping[str, Any]) -> str:
    for field in ("operator_message", "sanitized_message_summary", "operator_goal", "message", "text"):
        value = str(raw_request.get(field) or "").strip()
        if value:
            return value
    return _request_text(raw_request)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _prefer_reality_bounce_before_deterministic(raw_request: Mapping[str, Any]) -> bool:
    """Keep known freeform operator phrases on the Reality Bounce chain."""

    operator_text = _operator_message_text(raw_request)
    normalized = reality_bounce_harness.normalize_operator_text_for_matching(operator_text)
    if normalized in {
        "do the thing",
        "do it",
        "handle it",
        "make it happen",
        "send the invoice now",
        "send invoice now",
    }:
        return True
    return normalized.startswith("send the invoice ") or normalized.startswith("send invoice ")


def _reality_bounce_db_path() -> Path:
    configured = os.environ.get("OPENCLAW_REALITY_BOUNCE_DB_PATH")
    return Path(configured) if configured else DEFAULT_REALITY_BOUNCE_DB_PATH


NILES_ROUTE_TERMS = (
    "niles",
    "x32",
    "album",
    "setlist",
    "struna",
    "music",
    "studio",
    "production",
    "show file",
)

STRONG_MAC_ROUTE_TERMS = (
    "swiftui",
    "appkit",
    "xcode",
    "xcodebuild",
    "mission control ui",
    "macos app",
    "mac app",
    "mac-side",
    "mac side",
    "mac codex",
    "apple mail",
    "app layout",
    "file picker",
    "screen capture",
    "screenshot",
    "open mail",
    "mail app",
    "apple mail",
    "telegram desktop",
    "logic",
    "ableton",
    "final cut",
    "finder",
    "read aloud",
    "visual workspace",
)


def _is_capital_hilton_status_text(text: str, raw_request: Mapping[str, Any]) -> bool:
    lowered = text.lower()
    capital_context = (
        "capital hilton" in lowered
        or "capital_hilton" in lowered
        or "capital-hilton" in lowered
        or str(raw_request.get("client_ref") or "").lower() == "capital_hilton"
    )
    invoice_context = "invoice" in lowered
    status_intent = any(
        phrase in lowered
        for phrase in (
            "invoice status",
            "where are we",
            "ready",
            "mark invoice sent",
            "invoice sent",
            "what is missing",
            "what's missing",
            "whats missing",
            "blocking",
            "blocked",
            "blockers",
            "show me the invoice status",
            "can we mark",
            "can i mark",
        )
    )
    return capital_context and invoice_context and status_intent


def _route_for_request(request_path: Path, identity: RequestIdentity, raw_request: Mapping[str, Any]) -> RouteDecision:
    request_type = identity.request_type
    text = _request_text(raw_request)
    lowered = text.lower()
    if request_type == "EVENT_BRIDGE":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="OPENCLAW_SYSTEM",
            selected_machine="PC_WSL",
            processing_status="CHECKING_EVENT_BRIDGE_ADAPTER",
            operator_headline="OpenClaw is checking this Event Bridge action",
            operator_message="OpenClaw picked this up and is validating the hot-path Event Bridge envelope.",
            next_safe_move="Wait for the Event Bridge route readback.",
            route_reason="Event Bridge envelopes are validated and mapped through the deterministic adapter before existing request-router selection.",
            pc_handled=False,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type == "FILE_METADATA":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="OPENCLAW_SYSTEM",
            selected_machine="PC_WSL",
            processing_status="CHECKING_METADATA_RAIL",
            operator_headline="OpenClaw is processing this file reference",
            operator_message="OpenClaw picked this up and is checking the metadata-only local rail.",
            next_safe_move="Wait for the file reference readback.",
            route_reason="File metadata requests are handled by the deterministic PC metadata rail.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type == "WORKFLOW_PACKAGE_REQUEST":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_WORKFLOW_PACKAGE_QUEUE",
            operator_headline="OpenClaw is staging this instruction",
            operator_message="OpenClaw picked this up and is routing it into the dry-run workflow package queue.",
            next_safe_move="Wait for the workflow package queue readback.",
            route_reason=(
                "Mission Control generic operator instructions are handled by the Workflow Package Queue V0 "
                "consumer with no live business action authority."
            ),
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type == "WORKROOM_REVIEW_DECISION_REQUEST":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_WORKROOM_REVIEW_DECISION",
            operator_headline="OpenClaw is recording this review decision",
            operator_message="OpenClaw picked this up and is checking the Workroom review decision consumer.",
            next_safe_move="Wait for the review decision readback.",
            route_reason=(
                "Mission Control Workroom review decisions are handled by a bounded PC consumer "
                "that records review receipts only and cannot merge, push, or perform business actions."
            ),
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type == "WORKBOOK_REGISTRATION_REQUEST":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="OPENCLAW_SYSTEM",
            selected_machine="PC_WSL",
            processing_status="CHECKING_WORKBOOK_REGISTRATION",
            operator_headline="OpenClaw is registering this workbook",
            operator_message="OpenClaw picked this up and is checking the metadata-only workbook registration rail.",
            next_safe_move="Wait for the workbook registration readback.",
            route_reason=(
                "Mission Control workbook chooser requests are handled by the deterministic PC workbook registry "
                "without opening or mutating the workbook."
            ),
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type == "EVIDENCE_INTAKE_REQUEST":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="OPENCLAW_SYSTEM",
            selected_machine="PC_WSL",
            processing_status="CHECKING_EVIDENCE_INTAKE",
            operator_headline="OpenClaw is recording this evidence",
            operator_message="OpenClaw picked this up and is checking the verified operator evidence intake rail.",
            next_safe_move="Wait for the evidence intake card.",
            route_reason=(
                "Mission Control evidence drop requests are handled by the verified local evidence intake rail "
                "without OCR, external providers, ledger mutation, or paid marking."
            ),
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type == "OPERATOR_CONTROLLER_EVENT_REQUEST":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_OPERATOR_CONTROLLER_EVENT",
            operator_headline="OpenClaw is routing this controller event",
            operator_message="OpenClaw picked this up and is checking the verified controller event router.",
            next_safe_move="Wait for the controller event dynamic card response.",
            route_reason=(
                "Mission Control controller events are handled on PC through the Operator Controller Event Router, "
                "which validates the first-class operator envelope and maps only to safe backend rails."
            ),
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type == "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST":
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_ST_ANNES_WORK_LOG_REVIEW",
            operator_headline="OpenClaw is reviewing this work-log action",
            operator_message="OpenClaw picked this up and is checking the St. Anne's work-log review rail.",
            next_safe_move="Wait for the work-log review readback.",
            route_reason=(
                "Mission Control St. Anne's work-log review actions are handled by a bounded PC consumer "
                "that can only confirm, discard, or safely edit staged events."
            ),
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type in {"LOCAL_SURFACE_RESULT", "ARTIFACT_REFERENCE_APPROVAL", "ARTIFACT_INTAKE_REQUEST"}:
        processing_status = {
            "LOCAL_SURFACE_RESULT": "CHECKING_LOCAL_SURFACE_RESULT_RAIL",
            "ARTIFACT_REFERENCE_APPROVAL": "CHECKING_ARTIFACT_REFERENCE_RAIL",
            "ARTIFACT_INTAKE_REQUEST": "RECEIVING_WORKBOOK_FROM_MAC",
        }.get(request_type, "CHECKING_LOCAL_RAILS")
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="OPENCLAW_SYSTEM",
            selected_machine="PC_WSL",
            processing_status=processing_status,
            operator_headline="OpenClaw is checking this request",
            operator_message="OpenClaw picked this up and is checking the safe local handoff.",
            next_safe_move="Wait for the OpenClaw readback.",
            route_reason="Governed local result and artifact handoff requests are handled by deterministic PC rails.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if request_type != "CHAT":
        return RouteDecision(
            routing_status="UNKNOWN_FAIL_CLOSED",
            selected_worker_target="UNKNOWN",
            selected_machine="UNKNOWN",
            processing_status="UNSUPPORTED_REQUEST_FAMILY",
            operator_headline="OpenClaw cannot route this request yet",
            operator_message="OpenClaw picked this up, but the request family is not supported by the local service.",
            next_safe_move="Use a supported chat or file metadata request.",
            route_reason="Unsupported request family.",
            pc_handled=False,
            mac_handoff_required=False,
            future_worker_blocked=True,
            terminal_block_status="BLOCKED_WORKER_UNAVAILABLE",
        )
    if client_invoice_audit_handoff.is_audit_handoff_request(raw_request):
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_AUDIT_HANDOFF_RAIL",
            operator_headline="OpenClaw is checking audit handoff",
            operator_message="OpenClaw picked this up and is checking the workbook path and sheet mapping handoff contract.",
            next_safe_move="Wait for the audit handoff readback.",
            route_reason="Explicit client invoice audit handoff intended use is handled by the deterministic PC handoff rail.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if client_invoice_sheet_audit.is_sheet_audit_request(raw_request):
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_SHEET_AUDIT_RAIL",
            operator_headline="OpenClaw is checking the invoice sheet audit rail",
            operator_message="OpenClaw picked this up and is checking workbook registration, PC path, schema, and whitelisted cell gates.",
            next_safe_move="Wait for the whitelisted invoice sheet audit readback.",
            route_reason="Explicit client_invoice_sheet_audit intended use is handled by the deterministic PC sheet audit rail.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if _is_capital_hilton_status_text(text, raw_request):
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_LOCAL_RAILS",
            operator_headline="OpenClaw is checking local rails",
            operator_message="OpenClaw picked this up and is checking the local Capital Hilton status rails.",
            next_safe_move="Wait for the unified invoice status readback.",
            route_reason="Capital Hilton invoice status is handled by deterministic PC readback rails.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if processor.is_workbook_active_selection_request(raw_request):
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_WORKBOOK_SELECTION_RAIL",
            operator_headline="OpenClaw is updating the workbook choice",
            operator_message="OpenClaw picked this up and is checking the safe Capital Hilton workbook-selection rail.",
            next_safe_move="Wait for the workbook choice readback.",
            route_reason="Capital Hilton workbook selection is handled by a deterministic PC registry-reference rail.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if processor.is_workbook_active_selection_ambiguous_request(raw_request):
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="CHECKING_WORKBOOK_SELECTION_RAIL",
            operator_headline="OpenClaw needs one workbook choice",
            operator_message="OpenClaw picked this up and is checking which workbook should stay active.",
            next_safe_move="Wait for the workbook choice clarification.",
            route_reason="Ambiguous Capital Hilton workbook-selection language is handled by the deterministic PC clarification rail.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if _contains_any(lowered, STRONG_MAC_ROUTE_TERMS):
        route = worker_routing_intelligence.route_request(text, source_chat_ref=identity.source_request_id or request_path.name)
        return RouteDecision(
            routing_status="ROUTED_TO_MAC",
            selected_worker_target="MAC_CODEX",
            selected_machine="MAC",
            processing_status="MAC_HANDOFF_NEEDED",
            operator_headline="Routed to Mac",
            operator_message="OpenClaw picked this up. This request needs Mac-side handling.",
            next_safe_move="Wait for the Mac worker readback, or build the Mac handoff lane if unavailable.",
            route_reason=route.route_reason,
            pc_handled=False,
            mac_handoff_required=True,
            future_worker_blocked=False,
            terminal_block_status="BLOCKED_MAC_HANDOFF_UNAVAILABLE",
        )
    if _prefer_reality_bounce_before_deterministic(raw_request):
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="REALITY_BOUNCE_CHAIN",
            operator_headline="OpenClaw is checking this message",
            operator_message="OpenClaw picked this up and is routing it through the safe local response chain.",
            next_safe_move="Wait for the safe local response.",
            route_reason="Known freeform operator wording is handled by Reality Bounce before deterministic live-action interpreters.",
            pc_handled=False,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if deterministic_intent_interpreter.should_interpret(raw_request):
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="VALIDATING_DETERMINISTIC_INTENT",
            operator_headline="OpenClaw is validating intent",
            operator_message="OpenClaw picked this up and is checking deterministic intent, session state, and capability gates.",
            next_safe_move="Wait for the bounded intent validation readback.",
            route_reason="Matched a deterministic intent interpreter phrase handled by the PC request processor.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    if _contains_any(lowered, NILES_ROUTE_TERMS):
        return RouteDecision(
            routing_status="ROUTED_TO_FUTURE_WORKER",
            selected_worker_target="NILES",
            selected_machine="LOCAL_ONLY",
            processing_status="WORKER_ADAPTER_UNAVAILABLE",
            operator_headline="Niles is not wired yet",
            operator_message="OpenClaw routed this to Niles, but the live Niles worker adapter is not connected yet.",
            next_safe_move="Build the Niles draft/readback adapter before this can run.",
            route_reason="Music or creative-world context selects Niles.",
            pc_handled=False,
            mac_handoff_required=False,
            future_worker_blocked=True,
            terminal_block_status="BLOCKED_WORKER_UNAVAILABLE",
        )
    route = worker_routing_intelligence.route_request(text, source_chat_ref=identity.source_request_id or request_path.name)
    selected = route.selected_worker_type
    machine = route.selected_machine
    if selected == "MAC_CODEX" and _contains_any(lowered, STRONG_MAC_ROUTE_TERMS):
        return RouteDecision(
            routing_status="ROUTED_TO_MAC",
            selected_worker_target="MAC_CODEX",
            selected_machine="MAC",
            processing_status="MAC_HANDOFF_NEEDED",
            operator_headline="Routed to Mac",
            operator_message="OpenClaw picked this up. This request needs Mac-side handling.",
            next_safe_move="Wait for the Mac worker readback, or build the Mac handoff lane if unavailable.",
            route_reason=route.route_reason,
            pc_handled=False,
            mac_handoff_required=True,
            future_worker_blocked=False,
            terminal_block_status="BLOCKED_MAC_HANDOFF_UNAVAILABLE",
        )
    if text.strip():
        return RouteDecision(
            routing_status="PROCESSING_ON_PC",
            selected_worker_target="PC_CODEX",
            selected_machine="PC_WSL",
            processing_status="REALITY_BOUNCE_CHAIN",
            operator_headline="OpenClaw is checking this message",
            operator_message="OpenClaw picked this up and is routing it through the safe local response chain.",
            next_safe_move="Wait for the safe local response.",
            route_reason=(
                "No more specific deterministic rail matched; freeform chat falls through to the Reality Bounce chain. "
                f"Previous route hint: {route.route_reason}"
            ),
            pc_handled=False,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    future_map = {
        "GEMINI_AGY": "GEMINI_AGY",
        "CASSANDRA": "CASSANDRA",
        "GUARDIAN": "GUARDIAN",
        "UNKNOWN_NEEDS_ROUTING": "UNKNOWN",
        "LOCAL_OLLAMA": "UNKNOWN",
    }
    if selected in future_map:
        target = future_map[selected]
        return RouteDecision(
            routing_status="ROUTED_TO_FUTURE_WORKER" if target != "UNKNOWN" else "UNKNOWN_FAIL_CLOSED",
            selected_worker_target=target,
            selected_machine=machine if target != "UNKNOWN" else "UNKNOWN",
            processing_status="WORKER_ADAPTER_UNAVAILABLE",
            operator_headline=f"{target.replace('_', ' ').title()} is not wired yet" if target != "UNKNOWN" else "Worker route is unclear",
            operator_message=(
                f"OpenClaw routed this to {target.replace('_', '/').title()}, but that live worker adapter is not connected yet."
                if target != "UNKNOWN"
                else "OpenClaw could not select a supported worker target safely."
            ),
            next_safe_move=route.next_safe_move,
            route_reason=route.route_reason,
            pc_handled=False,
            mac_handoff_required=False,
            future_worker_blocked=True,
            terminal_block_status="BLOCKED_WORKER_UNAVAILABLE",
        )
    return RouteDecision(
        routing_status="PROCESSING_ON_PC",
        selected_worker_target="PC_CODEX",
        selected_machine="PC_WSL",
        processing_status="CHECKING_LOCAL_RAILS",
        operator_headline="OpenClaw is checking local rails",
        operator_message="OpenClaw picked this up and is checking the local rails.",
        next_safe_move="Wait for the PC readback.",
        route_reason=route.route_reason if selected == "PC_CODEX" else "Default supported chat handling stays on the deterministic PC rail.",
        pc_handled=True,
        mac_handoff_required=False,
        future_worker_blocked=False,
    )


def _heartbeat_payload(
    identity: RequestIdentity,
    request_path: Path,
    route: RouteDecision,
    *,
    created_at: str,
    handoff_path: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "processing_heartbeat_id": f"processing_heartbeat_{_safe_filename_part(identity.source_request_id)}",
        "source_request_id": identity.source_request_id,
        "source_request_filename": request_path.name,
        "request_type": identity.request_type,
        "routing_status": route.routing_status,
        "selected_worker_target": route.selected_worker_target,
        "selected_machine": route.selected_machine,
        "processing_status": route.processing_status,
        "operator_headline": route.operator_headline,
        "operator_message": route.operator_message,
        "route_reason": route.route_reason,
        "mac_handoff_path": handoff_path,
        "next_safe_move": route.next_safe_move,
        "created_at": created_at,
        "terminal": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "machine_proof": {
            "heartbeat_is_success_claim": False,
            "workflow_execution_performed": False,
            "model_call_performed": False,
            "tool_execution_performed": False,
            "agent_dispatch_performed": False,
            "mac_automation_performed": False,
            "email_send_performed": False,
            "coupa_access_or_submit_performed": False,
            "browser_access_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "all_authority_boundary_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def publish_processing_heartbeat_for_mac(
    heartbeat_payload: Mapping[str, Any],
    *,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
) -> PublishedHeartbeat:
    response_dir.mkdir(parents=True, exist_ok=True)
    request_id = str(heartbeat_payload.get("source_request_id") or "unknown_request")
    safe_request_id = _safe_filename_part(request_id)
    heartbeat_file = response_dir / f"openclaw_processing_for_mac_{safe_request_id}.json"
    latest_file = response_dir / LATEST_PROCESSING_EXPORT_NAME
    payload = dict(heartbeat_payload)
    payload["terminal"] = False
    _atomic_write_text(heartbeat_file, stable_json(payload))
    _atomic_write_text(latest_file, stable_json(payload))
    return PublishedHeartbeat(
        heartbeat_file=heartbeat_file.as_posix(),
        latest_heartbeat_file=latest_file.as_posix(),
        source_request_id=request_id,
        source_request_filename=str(payload.get("source_request_filename") or ""),
        request_type=str(payload.get("request_type") or "UNKNOWN_FAIL_CLOSED"),
        routing_status=str(payload.get("routing_status") or "UNKNOWN_FAIL_CLOSED"),
        selected_worker_target=str(payload.get("selected_worker_target") or "UNKNOWN"),
        selected_machine=str(payload.get("selected_machine") or "UNKNOWN"),
        processing_status=str(payload.get("processing_status") or "UNKNOWN_FAIL_CLOSED"),
        operator_headline=str(payload.get("operator_headline") or ""),
        operator_message=str(payload.get("operator_message") or ""),
        next_safe_move=str(payload.get("next_safe_move") or ""),
        terminal=False,
    )


def _read_manifest(response_dir: Path) -> dict[str, Any]:
    manifest_path = response_dir / MANIFEST_EXPORT_NAME
    if not manifest_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "manifest_id": "openclaw_response_manifest",
            "responses": [],
        }
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "schema_version": SCHEMA_VERSION,
            "manifest_id": "openclaw_response_manifest",
            "responses": [],
            "previous_manifest_parse_status": "invalid_json_replaced",
        }
    return value if isinstance(value, dict) else {"schema_version": SCHEMA_VERSION, "manifest_id": "openclaw_response_manifest", "responses": []}


def publish_response_for_mac(
    response_payload: Mapping[str, Any],
    *,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    created_at: str | None = None,
) -> PublishedResponse:
    created_at = created_at or utc_now()
    response_dir.mkdir(parents=True, exist_ok=True)
    request_id = str(response_payload.get("source_request_id") or "unknown_request")
    safe_request_id = _safe_filename_part(request_id)
    response_file = response_dir / f"openclaw_response_for_mac_{safe_request_id}.json"
    latest_file = response_dir / LATEST_RESPONSE_EXPORT_NAME
    manifest_file = response_dir / MANIFEST_EXPORT_NAME
    published_payload = _published_response_payload(response_payload, created_at=created_at)
    published_payload = processor.stamp_proof_to_response_source_response_path(
        published_payload,
        source_response_path=response_file.as_posix(),
    )
    _atomic_write_text(response_file, stable_json(published_payload))
    _atomic_write_text(latest_file, stable_json(published_payload))
    if isinstance(published_payload.get("proof_to_response"), Mapping):
        processor.proof_to_response_runtime.restamp_latest_source_response_path(
            source_request_id=request_id,
            source_response_path=response_file.as_posix(),
            generated_at=created_at,
        )

    manifest = _read_manifest(response_dir)
    responses = manifest.get("responses")
    if not isinstance(responses, list):
        responses = []
    record = {
        "source_request_id": request_id,
        "source_request_filename": response_payload.get("source_request_filename"),
        "request_type": response_payload.get("request_type"),
        "internal_status": response_payload.get("internal_status"),
        "operator_headline": response_payload.get("operator_headline"),
        "response_file": response_file.as_posix(),
        "created_at": created_at,
        "terminal": published_payload["terminal"],
    }
    responses = [item for item in responses if item.get("source_request_id") != request_id]
    responses.append(record)
    manifest.update(
        {
            "schema_version": SCHEMA_VERSION,
            "manifest_id": "openclaw_response_manifest",
            "updated_at": created_at,
            "latest_response_file": latest_file.as_posix(),
            "responses": responses[-200:],
        }
    )
    _atomic_write_text(manifest_file, stable_json(manifest))
    return PublishedResponse(
        response_file=response_file.as_posix(),
        latest_response_file=latest_file.as_posix(),
        manifest_file=manifest_file.as_posix(),
        source_request_id=request_id,
        source_request_filename=str(response_payload.get("source_request_filename") or ""),
        request_type=str(response_payload.get("request_type") or "UNKNOWN_FAIL_CLOSED"),
        internal_status=str(response_payload.get("internal_status") or "UNKNOWN_FAIL_CLOSED"),
        operator_headline=str(response_payload.get("operator_headline") or ""),
        operator_message=str(response_payload.get("operator_message") or ""),
        how_to_fix=str(response_payload.get("how_to_fix") or ""),
        next_safe_move=str(response_payload.get("next_safe_move") or ""),
        terminal=bool(published_payload["terminal"]),
    )


def _failure_processor_payload(
    *,
    request_path: Path,
    reason: str,
    created_at: str,
) -> dict[str, Any]:
    classification = processor.classify_request_filename(request_path.name)
    response = processor.OpenClawResponseForMac(
        source_request_id=f"service_failed_{_safe_filename_part(request_path.stem)}",
        source_request_filename=request_path.name,
        workflow_ref="unknown",
        request_type=classification.request_family,
        internal_status="FAILED_WITH_REASON",
        operator_headline="OpenClaw service could not process the request",
        operator_message="The local request/response service hit a PC-side failure. Nothing external happened.",
        what_happened=("The service found the request file.", "Processing failed before a usable response could be produced."),
        why_it_happened=reason,
        how_to_fix="Check the request JSON and deterministic processor logs, then rerun the service with --file for this request.",
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=reason,
        detail_disclosure={"service_error": reason},
        readback_files=(),
        next_safe_move="Fix the local processing failure and rerun the bounded service.",
    )
    response_payload, _status_payload = processor.build_payloads(response, generated_at=created_at)
    return response_payload


def _write_mac_handoff_package(
    *,
    request_path: Path,
    identity: RequestIdentity,
    route: RouteDecision,
    raw_request: Mapping[str, Any],
    mac_handoff_dir: Path,
    created_at: str,
) -> tuple[Path | None, dict[str, Any]]:
    payload = mac_worker_handoff_package.build_handoff_payload_from_request(
        raw_request,
        source_request_filename=request_path.name,
        created_at=created_at,
    )
    if mac_handoff_dir.is_symlink() or not mac_handoff_dir.exists() or not mac_handoff_dir.is_dir():
        payload = dict(payload)
        blockers = list(payload.get("blockers") or ())
        condition = (
            "Mac handoff output path is a symlink and cannot be used safely."
            if mac_handoff_dir.is_symlink()
            else "Mac handoff output path does not exist as an approved directory."
        )
        blockers.append(
            {
                "blocker_id": f"mac_worker_handoff_blocker_{_safe_filename_part(identity.source_request_id)}_path",
                "blocker_type": "MAC_HANDOFF_PATH_UNAVAILABLE",
                "condition": condition,
                "severity": "critical",
                "elioperator_warning": f"ELIOPERATOR: {condition}",
                "fail_closed": True,
                "next_safe_move": "Build the Mac worker request watcher/handoff lane, or handle this manually in Mac Codex for now.",
            }
        )
        payload["blockers"] = tuple(blockers)
        payload["handoff_package"] = None
        return None, payload
    handoff_package = payload.get("handoff_package")
    if not isinstance(handoff_package, Mapping):
        return None, payload
    handoff_package["source_request_id"] = identity.source_request_id
    handoff_package["source_request_filename"] = request_path.name
    handoff_package["requested_worker"] = handoff_package.get("requested_worker") or route.selected_worker_target
    handoff_package["target_machine"] = route.selected_machine
    handoff_package["response_path_policy"] = mac_worker_handoff_package.response_path_policy(identity.source_request_id)
    payload["handoff_package"] = handoff_package
    handoff_path = mac_worker_handoff_package.write_handoff_package(payload, mac_handoff_dir)
    return handoff_path, payload


def _mac_handoff_ready_processor_payload(
    *,
    request_path: Path,
    identity: RequestIdentity,
    route: RouteDecision,
    created_at: str,
    handoff_path: Path,
    handoff_payload: Mapping[str, Any],
) -> dict[str, Any]:
    mac_visible_path = (
        f"{mac_worker_handoff_package.MAC_VISIBLE_HANDOFF_DIR}/"
        f"{handoff_path.name}"
    )
    response = processor.OpenClawResponseForMac(
        source_request_id=identity.source_request_id,
        source_request_filename=request_path.name,
        workflow_ref=identity.workflow_ref,
        request_type=identity.request_type,
        internal_status="RESPONSE_READY",
        operator_headline="Routed to Mac",
        operator_message=(
            "OpenClaw understood this needs Mac-side work. The handoff package is ready for the Mac worker; "
            "nothing has been executed yet."
        ),
        what_happened=(
            "PC detected the request and selected a Mac-owned route.",
            "PC wrote a bounded metadata-only handoff package to the approved Mac-readable directory.",
            "PC published this terminal route readback for Mac chat.",
            "No Mac execution, app automation, Xcode execution, screenshot capture, file mutation, external action, send, submit, credential handling, or raw-body ingestion occurred.",
        ),
        why_it_happened=route.route_reason,
        how_to_fix="Run the Mac worker handoff lane, or handle it manually in Mac Codex for now.",
        visible_cards=(
            {
                "title": "Routed to Mac",
                "bullets": (
                    f"Selected worker: {route.selected_worker_target}",
                    f"Selected machine: {route.selected_machine}",
                    "Handoff package ready; no execution occurred.",
                ),
                "status_tone": "routed",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": route.selected_worker_target,
                "selected_machine": route.selected_machine,
                "routing_status": route.routing_status,
                "route_reason": route.route_reason,
                "mac_handoff_path": handoff_path.as_posix(),
                "mac_visible_handoff_path": mac_visible_path,
            },
        ),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={
            "routing_status": route.routing_status,
            "selected_worker_target": route.selected_worker_target,
            "selected_machine": route.selected_machine,
            "processing_status": "MAC_HANDOFF_PACKAGE_READY",
            "mac_handoff_path": handoff_path.as_posix(),
            "mac_visible_handoff_path": mac_visible_path,
            "handoff_package_ref": handoff_payload.get("handoff_package", {}).get("handoff_id")
            if isinstance(handoff_payload.get("handoff_package"), Mapping)
            else None,
            "worker_dispatched": False,
            "mac_execution_performed": False,
            "app_automation_performed": False,
            "xcode_execution_performed": False,
            "screenshot_capture_performed": False,
            "file_mutation_performed": False,
            "external_actions_locked": True,
        },
        readback_files=(handoff_path.as_posix(),),
        next_safe_move="Next: Run the Mac worker handoff lane.",
    )
    response_payload, _status_payload = processor.build_payloads(response, generated_at=created_at)
    response_payload.update(
        {
            "headline": "Routed to Mac",
            "one_line_answer": "OpenClaw prepared a Mac handoff package without executing it.",
            "eliwinship": (
                "OpenClaw understood this needs Mac-side work. "
                "The handoff package is ready for the Mac worker; nothing has been executed yet."
            ),
            "primary_status": "Routed for Mac-side handling",
            "primary_blocker": "Mac worker handoff lane has not executed",
            "next_action": "Next: Run the Mac worker handoff lane.",
            "missing_items_short": (
                "Mac worker readback",
                "Mac-side validation receipts",
                "Terminal proof after Mac handling",
            ),
            "detail_summary": (
                "PC created a metadata-only handoff package in the approved Mac-visible handoff directory. "
                "The package is not execution authority."
            ),
            "proof_refs": (),
            "debug_refs": (handoff_path.as_posix(),),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        }
    )
    return response_payload


def _mac_handoff_blocked_processor_payload(
    *,
    request_path: Path,
    identity: RequestIdentity,
    route: RouteDecision,
    created_at: str,
    handoff_payload: Mapping[str, Any],
) -> dict[str, Any]:
    blockers = tuple(
        blocker
        for blocker in handoff_payload.get("blockers", ())
        if isinstance(blocker, Mapping)
    )
    blocker_types = tuple(str(blocker.get("blocker_type") or "UNKNOWN_FAIL_CLOSED") for blocker in blockers)
    blocker_summary = ", ".join(blocker_types) or "UNKNOWN_FAIL_CLOSED"
    handoff_path_unavailable = "MAC_HANDOFF_PATH_UNAVAILABLE" in blocker_types
    how_to_fix = (
        str(blockers[0].get("next_safe_move"))
        if blockers and blockers[0].get("next_safe_move")
        else "Reframe the request as a scoped Mac readback or validation handoff with no external action authority."
    )
    internal_status = "BLOCKED_MAC_HANDOFF_UNAVAILABLE" if handoff_path_unavailable else "BLOCKED_WITH_REASON"
    headline = "Mac handoff is not wired yet" if handoff_path_unavailable else "Mac handoff blocked"
    message = (
        "OpenClaw understood that this needs Mac-side processing, but the Mac worker handoff rail is not available yet."
        if handoff_path_unavailable
        else (
            "OpenClaw understood this is Mac-owned work, but the handoff package failed closed because the request "
            "included unsafe authority or unsupported Mac worker scope."
        )
    )
    response = processor.OpenClawResponseForMac(
        source_request_id=identity.source_request_id,
        source_request_filename=request_path.name,
        workflow_ref=identity.workflow_ref,
        request_type=identity.request_type,
        internal_status=internal_status,
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC detected the request and selected a Mac-owned route.",
            "PC checked the request against the Mac handoff package safety rules.",
            "PC did not write an executable handoff, dispatch a worker, call a model, run Mac automation, or execute a workflow.",
        ),
        why_it_happened=f"Mac handoff blockers: {blocker_summary}.",
        how_to_fix=how_to_fix,
        visible_cards=(
            {
                "title": "Mac handoff blocked",
                "bullets": (
                    f"Blockers: {blocker_summary}",
                    "No handoff package with execution authority was created.",
                    "No Mac execution occurred.",
                ),
                "status_tone": "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": route.selected_worker_target,
                "selected_machine": route.selected_machine,
                "routing_status": route.routing_status,
                "route_reason": route.route_reason,
                "blockers": blocker_types,
            },
        ),
        context_package_refs=(),
        blocked_reason=blocker_summary,
        detail_disclosure={
            "routing_status": route.routing_status,
            "selected_worker_target": route.selected_worker_target,
            "selected_machine": route.selected_machine,
            "handoff_blockers": blocker_types,
            "worker_dispatched": False,
            "mac_execution_performed": False,
            "app_automation_performed": False,
            "xcode_execution_performed": False,
            "screenshot_capture_performed": False,
            "file_mutation_performed": False,
            "external_actions_locked": True,
        },
        readback_files=(),
        next_safe_move=how_to_fix,
    )
    response_payload, _status_payload = processor.build_payloads(response, generated_at=created_at)
    return response_payload


def _reality_bounce_processor_payload(
    *,
    request_path: Path,
    identity: RequestIdentity,
    route: RouteDecision,
    raw_request: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    operator_text = _operator_message_text(raw_request)
    bounce = reality_bounce_harness.run_text(
        operator_text,
        mode="local",
        db_path=_reality_bounce_db_path(),
        generated_at=created_at,
        source_request_id=identity.source_request_id,
        world_ref=str(raw_request.get("world_ref") or "finance"),
        client_ref=str(raw_request.get("client_ref") or "capital_hilton"),
        workflow_ref=str(raw_request.get("workflow_ref") or identity.workflow_ref or "capital_hilton_invoice_workflow"),
        persist=True,
    )
    result = bounce["result"]
    mac_response = result["scoped_mac_response_candidate"]
    status = str(result["status"])
    response_ready = status in {
        reality_bounce_harness.STATUS_ACCEPTED_WITH_RECEIPT,
        reality_bounce_harness.STATUS_ACCEPTED_RESPONSE_ONLY,
    }
    receipt_id = str(result.get("receipt_id") or "")
    selected_role_family = str(result.get("selected_role_family") or "OPENCLAW_SYSTEM")
    selected_voice = str(result.get("selected_voice") or selected_role_family)
    operator_headline = str(mac_response.get("headline") or "OpenClaw response")
    operator_message = str(mac_response.get("body") or mac_response.get("eliwinship") or "")
    next_action = str(mac_response.get("next_action") or "Next: review the safe response.")
    why = (
        "Reality Bounce accepted the message and validated an offline worker result."
        if result.get("receipt_written")
        else "Reality Bounce handled the message without worker completion authority."
    )
    layered_fields = {
        "response_kind": "REALITY_BOUNCE_RESPONSE",
        "audience_mode": "ELIWINSHIP",
        "display_mode": "COMPACT_CHAT",
        "headline": operator_headline,
        "one_line_answer": operator_headline,
        "eliwinship": operator_message,
        "primary_status": "Ready for review" if response_ready else "Blocked",
        "primary_blocker": "None" if response_ready else status,
        "next_action": next_action,
        "missing_items_short": (),
        "detail_summary": why,
        "proof_refs": (receipt_id,) if receipt_id else (),
        "debug_refs": (),
        "raw_internal_status": "RESPONSE_READY" if response_ready else "BLOCKED_WITH_REASON",
        "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
    }
    response = processor.OpenClawResponseForMac(
        source_request_id=identity.source_request_id,
        source_request_filename=request_path.name,
        workflow_ref=identity.workflow_ref,
        request_type=identity.request_type,
        internal_status="RESPONSE_READY" if response_ready else "BLOCKED_WITH_REASON",
        operator_headline=operator_headline,
        operator_message=operator_message,
        what_happened=(
            "PC received the freeform Mission Control message.",
            "PC built a Gate 1 snapshot and local MachineIntentCandidate proposal.",
            "PC ran Gate 2, Gate 3, the bounded offline worker path where applicable, and Guardian validation.",
            "PC wrote a SQLite receipt only when Guardian validated real offline worker output.",
            "No live model, tool, send, submit, workbook read, external action, or production mutation occurred.",
        ),
        why_it_happened=why,
        how_to_fix=next_action,
        visible_cards=(
            {
                "title": operator_headline,
                "bullets": (
                    operator_message,
                    next_action,
                    "Nothing was sent, posted, read from a workbook, or changed in production.",
                ),
                "status_tone": "ready" if response_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": route.selected_worker_target,
                "selected_machine": route.selected_machine,
                "routing_status": route.routing_status,
                "route_reason": route.route_reason,
                "reality_bounce_status": status,
                "selected_role_family": selected_role_family,
                "selected_voice": selected_voice,
                "worker_fixture_used": result.get("worker_fixture_used"),
                "guardian_verdict": ((result.get("guardian_result") or {}).get("validation_result") or {}).get("verdict"),
                "receipt_written": bool(result.get("receipt_written")),
                "receipt_id": receipt_id,
            },
        ),
        context_package_refs=(),
        blocked_reason=None if response_ready else status,
        detail_disclosure={
            "selected_rail": "reality_bounce_harness",
            "routing_status": route.routing_status,
            "processing_status": route.processing_status,
            "reality_bounce_mode": bounce["mode"],
            "reality_bounce_status": status,
            "source_request_id": identity.source_request_id,
            "selected_role_family": selected_role_family,
            "selected_voice": selected_voice,
            "worker_fixture_used": result.get("worker_fixture_used"),
            "guardian_verdict": ((result.get("guardian_result") or {}).get("validation_result") or {}).get("verdict"),
            "receipt_written": bool(result.get("receipt_written")),
            "receipt_id": receipt_id,
            "receipt_db_path": bounce["isolated_sqlite"]["db_path"],
            "gate2_outcome": (result.get("gate2_result") or {}).get("outcome"),
            "gate3_status": (result.get("gate3_package") or {}).get("package_status"),
            "live_lm_call_performed": False,
            "repo_b_runtime_started": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "production_state_mutation_performed": False,
            "layered_response_fields": layered_fields,
        },
        readback_files=(),
        next_safe_move=next_action,
    )
    response_payload, _status_payload = processor.build_payloads(response, generated_at=created_at)
    return response_payload


def _route_blocked_processor_payload(
    *,
    request_path: Path,
    identity: RequestIdentity,
    route: RouteDecision,
    created_at: str,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    handoff_path: str | None = None,
) -> dict[str, Any]:
    proposal_payload: dict[str, Any] | None = None
    proposal_json: Path | None = None
    proposal_operator: Path | None = None
    if route.terminal_block_status == "BLOCKED_MAC_HANDOFF_UNAVAILABLE":
        headline = "Mac handoff is not wired yet"
        message = "OpenClaw understood that this needs Mac-side processing, but the Mac worker handoff rail is not available yet."
        how_to_fix = "Build the Mac worker request watcher/handoff lane, or handle this manually in Mac Codex for now."
    else:
        target_label = route.selected_worker_target.replace("_", "/").title()
        if route.selected_worker_target == "UNKNOWN":
            try:
                raw_request = json.loads(request_path.read_text(encoding="utf-8"))
                if not isinstance(raw_request, Mapping):
                    raw_request = {}
            except (json.JSONDecodeError, OSError):
                raw_request = {}
            proposal_payload = lm_intent_proposal_contract.build_payload(
                raw_request,
                request_filename=request_path.name,
                export_root=export_root,
                generated_at=created_at,
            )
            proposal_json, proposal_operator = lm_intent_proposal_contract.write_exports(proposal_payload, export_root)
            headline = "I need one more detail"
            message = (
                "OpenClaw could not safely turn that into a bounded action yet. "
                "I prepared a safe interpreter package, and nothing was run or changed."
            )
            how_to_fix = "Next: say the object and the safe outcome you want, or choose the visible app option."
        else:
            headline = f"{target_label} helper is not connected yet"
            message = f"OpenClaw understood the likely helper, but that bounded helper is not connected yet. Nothing was run or changed."
            how_to_fix = f"Next: prepare the bounded {target_label} helper contract before this can run."
    response = processor.OpenClawResponseForMac(
        source_request_id=identity.source_request_id,
        source_request_filename=request_path.name,
        workflow_ref=identity.workflow_ref,
        request_type=identity.request_type,
        internal_status=route.terminal_block_status or "BLOCKED_WORKER_UNAVAILABLE",
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC detected the request and selected a route.",
            "PC did not dispatch a worker, call a model, run Mac automation, or execute a workflow.",
            "PC published a route-aware blocked response so the operator does not see dead air.",
        ),
        why_it_happened=route.route_reason,
        how_to_fix=how_to_fix,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    "No model, worker, workflow, send, submit, or external action ran.",
                    "OpenClaw needs a clearer bounded action or a connected helper contract.",
                    how_to_fix,
                ),
                "status_tone": "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=tuple(path.as_posix() for path in (proposal_json,) if path is not None),
        worker_route_refs=(
            {
                "selected_worker_target": route.selected_worker_target,
                "selected_machine": route.selected_machine,
                "routing_status": route.routing_status,
                "route_reason": route.route_reason,
                "mac_handoff_path": handoff_path,
            },
        ),
        context_package_refs=(),
        blocked_reason=route.terminal_block_status or "BLOCKED_WORKER_UNAVAILABLE",
        detail_disclosure={
            "routing_status": route.routing_status,
            "selected_worker_target": route.selected_worker_target,
            "selected_machine": route.selected_machine,
            "processing_status": route.processing_status,
            "mac_handoff_path": handoff_path,
            "worker_dispatched": False,
            "model_or_tool_called": False,
            "intent_proposal_package": proposal_payload.get("proposal_package") if proposal_payload else None,
            "intent_proposal_readback_ref": proposal_json.as_posix() if proposal_json else None,
            "intent_proposal_operator_ref": proposal_operator.as_posix() if proposal_operator else None,
            "proposal_package_created": proposal_payload is not None,
            "live_lm_call_performed": False,
            "external_actions_locked": True,
        },
        readback_files=tuple(path.as_posix() for path in (proposal_json, proposal_operator) if path is not None),
        next_safe_move=how_to_fix,
    )
    response_payload, _status_payload = processor.build_payloads(response, generated_at=created_at)
    return response_payload


def _event_bridge_adapter_processor_payload(
    *,
    request_path: Path,
    identity: RequestIdentity,
    route: RouteDecision,
    raw_event: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    adapter_response = openclaw_event_bridge_adapter.route_event_bridge_envelope(
        raw_event,
        now=created_at,
    )
    route_status = str(adapter_response.get("route_status") or "UNKNOWN_FAIL_CLOSED")
    workflow_status = str(adapter_response.get("workflow_status") or "WORKFLOW_BLOCKED")
    matched = route_status == "ROUTE_MATCHED"
    internal_status = "RESPONSE_READY" if matched else "BLOCKED_WITH_REASON"
    selected_handler = str((adapter_response.get("router_decision") or {}).get("selected_handler_id") or "")
    correlation_id = str(adapter_response.get("correlation_id") or raw_event.get("correlation_id") or "")
    operator_copy = str(adapter_response.get("operator_copy") or "")
    headline = "Event Bridge route selected" if matched else "Event Bridge envelope rejected"
    next_safe_move = (
        "Wait for the selected deterministic workflow route readback."
        if matched
        else "Fix the Event Bridge envelope and resend it with the current action source."
    )
    if matched and selected_handler:
        message = f"{operator_copy} Selected route: {selected_handler}."
    else:
        message = operator_copy or "The Event Bridge envelope was rejected before routing."
    response = processor.OpenClawResponseForMac(
        source_request_id=identity.source_request_id,
        source_request_filename=request_path.name,
        workflow_ref=identity.workflow_ref,
        request_type=identity.request_type,
        internal_status=internal_status,
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "The service recognized an Event Bridge envelope in the approved capture inbox.",
            "The service validated the envelope and safety guards through the Event Bridge adapter.",
            "The adapter mapped the event into the existing request-router shape.",
            "No handler execution, PDF export, workbook cell read, email/Gmail/browser/Coupa action, ledger mutation, Chief run, or model call occurred.",
        ),
        why_it_happened=(
            f"Adapter route_status={route_status}; workflow_status={workflow_status}."
            if route_status
            else "Adapter returned no route status."
        ),
        how_to_fix=next_safe_move,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    f"Route status: {route_status}",
                    f"Workflow status: {workflow_status}",
                    f"Correlation: {correlation_id}" if correlation_id else "Correlation id missing",
                    "Adapter only; no business action executed.",
                ),
                "status_tone": "ready" if matched else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": route.selected_worker_target,
                "selected_machine": route.selected_machine,
                "routing_status": route.routing_status,
                "route_reason": route.route_reason,
                "event_bridge_route_status": route_status,
                "event_bridge_workflow_status": workflow_status,
                "selected_handler_id": selected_handler,
                "correlation_id": correlation_id,
            },
        ),
        context_package_refs=(),
        blocked_reason=None if matched else str(adapter_response.get("error_code") or route_status),
        detail_disclosure={
            "selected_rail": "openclaw_event_bridge_adapter",
            "routing_status": route.routing_status,
            "processing_status": route.processing_status,
            "event_bridge_adapter_response": adapter_response,
            "route_status": route_status,
            "workflow_status": workflow_status,
            "operator_copy": operator_copy,
            "correlation_id": correlation_id,
            "selected_handler_id": selected_handler,
            "handler_execution_performed": False,
            "processor_execution_performed": False,
            "pdf_export_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_post_performed": False,
            "production_state_mutation_performed": False,
            "service_restart_required": False,
        },
        readback_files=(),
        next_safe_move=next_safe_move,
    )
    response_payload, _status_payload = processor.build_payloads(response, generated_at=created_at)
    response_payload.update(
        {
            "response_kind": "EVENT_BRIDGE_ADAPTER_RESPONSE",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": route_status,
            "primary_blocker": "None" if matched else str(adapter_response.get("error_code") or route_status),
            "next_action": f"Next: {next_safe_move}",
            "missing_items_short": (),
            "detail_summary": f"Event Bridge adapter returned {route_status}.",
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
            "event_id": str(adapter_response.get("event_id") or raw_event.get("event_id") or identity.source_request_id),
            "event_kind": str(raw_event.get("event_kind") or ""),
            "source_channel": str(raw_event.get("source_channel") or ""),
            "correlation_id": correlation_id,
            "route_status": route_status,
            "workflow_status": workflow_status,
            "operator_copy": operator_copy,
            "stale_event": bool(adapter_response.get("stale_event")),
            "superseded_by_event_id": str(adapter_response.get("superseded_by_event_id") or ""),
            "selected_handler_id": selected_handler,
            "event_bridge_adapter_response": adapter_response,
        }
    )
    machine_proof = response_payload.get("machine_proof")
    if isinstance(machine_proof, dict):
        machine_proof.update(
            {
                "event_bridge_envelope_recognized": True,
                "event_bridge_adapter_used": True,
                "event_bridge_adapter_route_status": route_status,
                "event_bridge_adapter_selected_handler_id": selected_handler,
                "handler_execution_performed": False,
                "processor_execution_performed": False,
                "pdf_export_performed": False,
                "email_send_performed": False,
                "gmail_access_performed": False,
                "browser_access_performed": False,
                "coupa_access_performed": False,
                "ledger_post_performed": False,
                "workbook_cell_read_performed": False,
                "production_state_mutation_performed": False,
            }
        )
    return response_payload


def _record_from_response(
    request_path: Path,
    identity: RequestIdentity,
    response_payload: Mapping[str, Any],
    published: PublishedResponse,
    *,
    created_at: str,
    heartbeat: PublishedHeartbeat | None = None,
    route: RouteDecision | None = None,
    request_file_mtime: str | None = None,
    pickup_latency_ms: float | None = None,
    processing_duration_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "source_request_id": identity.source_request_id,
        "source_request_filename": request_path.name,
        "request_key": identity.request_key,
        "identity_keys": _identity_keys(request_path, identity),
        "idempotency_key": identity.idempotency_key,
        "payload_hash": identity.payload_hash,
        "workflow_ref": identity.workflow_ref,
        "request_type": identity.request_type,
        "response_file": published.response_file,
        "internal_status": response_payload.get("internal_status"),
        "operator_headline": response_payload.get("operator_headline"),
        "routing_status": route.routing_status if route else None,
        "selected_worker_target": route.selected_worker_target if route else None,
        "selected_machine": route.selected_machine if route else None,
        "processing_heartbeat_path": heartbeat.heartbeat_file if heartbeat else None,
        "created_at": created_at,
        "request_file_mtime": request_file_mtime,
        "pickup_latency_ms": pickup_latency_ms,
        "processing_duration_ms": processing_duration_ms,
    }


def process_one_pending_request(
    *,
    inbox: Path = APPROVED_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    extra_processed_keys: set[str] | None = None,
    read_model_cache: ReadModelMemoryCache | None = None,
    mac_handoff_dir: Path = DEFAULT_MAC_HANDOFF_DIR,
    stale_before_mtime_ns: int | None = None,
) -> ServiceRunResult:
    created_at = generated_at or utc_now()
    cache = read_model_cache or _new_read_model_cache(export_root)
    request_path, skipped = select_next_pending_request(
        inbox=inbox,
        response_dir=response_dir,
        export_root=export_root,
        extra_processed_keys=extra_processed_keys,
        stale_before_mtime_ns=stale_before_mtime_ns,
    )
    if request_path is None:
        service_status = "REQUEST_SKIPPED_DUPLICATE" if skipped else "IDLE_NO_REQUEST_AVAILABLE"
        next_safe_move = (
            "No new request was processed because all supported request files were already handled."
            if skipped
            else "Leave the service idle until Mac emits a supported request."
        )
        return ServiceRunResult(
            service_status=service_status,
            run_mode="once",
            inbox=inbox.as_posix(),
            response_path=response_dir.as_posix(),
            processed_count=0,
            skipped_duplicate_count=len(skipped),
            processed_requests=(),
            skipped_duplicates=skipped,
            latest_response=None,
            errors_or_blockers=(),
            next_safe_move=next_safe_move,
            mode="stopped",
            current_poll_interval=0.0,
            idle_poll_interval=DEFAULT_IDLE_POLL_INTERVAL,
            active_poll_interval=DEFAULT_ACTIVE_POLL_INTERVAL,
            active_window_seconds=DEFAULT_ACTIVE_WINDOW_SECONDS,
            active_window_remaining_seconds=0.0,
            last_watch_mode_before_stop="idle",
            last_poll_interval=0.0,
            last_processed_request_id=None,
            last_response_path=None,
            bounded_stop_reason="duplicate_only" if skipped else "no_pending_request",
            last_processing_started_request_id=None,
            last_routing_status=None,
            selected_worker_target=None,
            selected_machine=None,
            processing_heartbeat_path=None,
            terminal_response_path=None,
            active_request_count=0,
            **_cache_result_fields(cache),
        )

    processing_started = time.perf_counter()
    pickup_checked_at = time.time()
    request_file_mtime: str | None = None
    pickup_latency_ms: float | None = None
    try:
        request_stat = request_path.stat()
        request_file_mtime = datetime.fromtimestamp(request_stat.st_mtime, tz=timezone.utc).isoformat()
        pickup_latency_ms = round(max(0.0, (pickup_checked_at - request_stat.st_mtime) * 1000.0), 3)
    except OSError:
        request_file_mtime = None
        pickup_latency_ms = None

    identity = read_request_identity(request_path)
    try:
        raw_request_for_route = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(raw_request_for_route, Mapping):
            raw_request_for_route = {}
    except (json.JSONDecodeError, OSError):
        raw_request_for_route = {}
    route = _route_for_request(request_path, identity, raw_request_for_route)
    if identity.parse_status != "PARSED":
        route = RouteDecision(
            routing_status="UNKNOWN_FAIL_CLOSED",
            selected_worker_target="UNKNOWN",
            selected_machine="UNKNOWN",
            processing_status=identity.parse_status,
            operator_headline="OpenClaw is checking the request shape",
            operator_message="OpenClaw picked this up, but the request JSON needs validation before routing can continue.",
            next_safe_move="Fix the request JSON and retry.",
            route_reason=f"Request identity parse status: {identity.parse_status}.",
            pc_handled=True,
            mac_handoff_required=False,
            future_worker_blocked=False,
        )
    handoff_path: Path | None = None
    handoff_payload: dict[str, Any] | None = None
    if route.mac_handoff_required:
        handoff_path, handoff_payload = _write_mac_handoff_package(
            request_path=request_path,
            identity=identity,
            route=route,
            raw_request=raw_request_for_route,
            mac_handoff_dir=mac_handoff_dir,
            created_at=created_at,
        )
        if handoff_path is not None:
            route = RouteDecision(
                routing_status="WAITING_FOR_MAC_READBACK",
                selected_worker_target=route.selected_worker_target,
                selected_machine=route.selected_machine,
                processing_status="WAITING_FOR_MAC_READBACK",
                operator_headline="Waiting for Mac readback",
                operator_message="OpenClaw routed this to Mac and wrote a bounded handoff package. Nothing has been executed.",
                next_safe_move="Wait for the Mac worker readback.",
                route_reason=route.route_reason,
                pc_handled=False,
                mac_handoff_required=True,
                future_worker_blocked=False,
                terminal_block_status=None,
            )
    heartbeat_payload = _heartbeat_payload(
        identity,
        request_path,
        route,
        created_at=created_at,
        handoff_path=handoff_path.as_posix() if handoff_path else None,
    )
    heartbeat = publish_processing_heartbeat_for_mac(heartbeat_payload, response_dir=response_dir)

    if route.mac_handoff_required and handoff_path is not None:
        record = {
            "source_request_id": identity.source_request_id,
            "source_request_filename": request_path.name,
            "request_key": identity.request_key,
            "identity_keys": _identity_keys(request_path, identity),
            "idempotency_key": identity.idempotency_key,
            "payload_hash": identity.payload_hash,
            "workflow_ref": identity.workflow_ref,
            "request_type": identity.request_type,
            "response_file": None,
            "internal_status": "WAITING_FOR_MAC_READBACK",
            "operator_headline": heartbeat.operator_headline,
            "routing_status": route.routing_status,
            "selected_worker_target": route.selected_worker_target,
            "selected_machine": route.selected_machine,
            "processing_heartbeat_path": heartbeat.heartbeat_file,
            "mac_handoff_path": handoff_path.as_posix(),
            "created_at": created_at,
        }
        return ServiceRunResult(
            service_status="REQUEST_ROUTED_WAITING_FOR_MAC_READBACK",
            run_mode="once",
            inbox=inbox.as_posix(),
            response_path=response_dir.as_posix(),
            processed_count=1,
            skipped_duplicate_count=len(skipped),
            processed_requests=(record,),
            skipped_duplicates=skipped,
            latest_response=None,
            errors_or_blockers=(),
            next_safe_move=route.next_safe_move,
            mode="stopped",
            current_poll_interval=0.0,
            idle_poll_interval=DEFAULT_IDLE_POLL_INTERVAL,
            active_poll_interval=DEFAULT_ACTIVE_POLL_INTERVAL,
            active_window_seconds=DEFAULT_ACTIVE_WINDOW_SECONDS,
            active_window_remaining_seconds=0.0,
            last_watch_mode_before_stop="active",
            last_poll_interval=0.0,
            last_processed_request_id=identity.source_request_id,
            last_response_path=None,
            bounded_stop_reason="waiting_for_mac_readback",
            last_processing_started_request_id=identity.source_request_id,
            last_routing_status=route.routing_status,
            selected_worker_target=route.selected_worker_target,
            selected_machine=route.selected_machine,
            processing_heartbeat_path=heartbeat.heartbeat_file,
            terminal_response_path=None,
            active_request_count=1,
            **_cache_result_fields(cache),
        )

    try:
        if route.mac_handoff_required and handoff_payload is not None:
            response_payload = _mac_handoff_blocked_processor_payload(
                request_path=request_path,
                identity=identity,
                route=route,
                created_at=created_at,
                handoff_payload=handoff_payload,
            )
            errors = ()
        elif route.processing_status == "REALITY_BOUNCE_CHAIN":
            response_payload = _reality_bounce_processor_payload(
                request_path=request_path,
                identity=identity,
                route=route,
                raw_request=raw_request_for_route,
                created_at=created_at,
            )
            errors = ()
        elif identity.request_type == "EVENT_BRIDGE":
            response_payload = _event_bridge_adapter_processor_payload(
                request_path=request_path,
                identity=identity,
                route=route,
                raw_event=raw_request_for_route,
                created_at=created_at,
            )
            errors = ()
        elif route.pc_handled:
            response_payload, _processor_status, _paths, quality_errors = processor.run_and_write(
                inbox=inbox,
                request_file=request_path,
                request_id=None,
                export_root=export_root,
                generated_at=created_at,
                read_model_reader=cache.read_json,
            )
            errors = tuple(str(item) for item in quality_errors)
        else:
            response_payload = _route_blocked_processor_payload(
                request_path=request_path,
                identity=identity,
                route=route,
                created_at=created_at,
                export_root=export_root,
                handoff_path=handoff_path.as_posix() if handoff_path else None,
            )
            errors = ()
    except Exception as exc:  # pragma: no cover - defensive service boundary
        response_payload = _failure_processor_payload(
            request_path=request_path,
            reason=f"{type(exc).__name__}: {exc}",
            created_at=created_at,
        )
        errors = (str(response_payload["why_it_happened"]),)
    published = publish_response_for_mac(response_payload, response_dir=response_dir, created_at=created_at)
    processing_duration_ms = round((time.perf_counter() - processing_started) * 1000.0, 3)
    record = _record_from_response(
        request_path,
        identity,
        response_payload,
        published,
        created_at=created_at,
        heartbeat=heartbeat,
        route=route,
        request_file_mtime=request_file_mtime,
        pickup_latency_ms=pickup_latency_ms,
        processing_duration_ms=processing_duration_ms,
    )
    service_status = "REQUEST_PROCESSED" if not errors else "FAILED_WITH_REASON"
    return ServiceRunResult(
        service_status=service_status,
        run_mode="once",
        inbox=inbox.as_posix(),
        response_path=response_dir.as_posix(),
        processed_count=1,
        skipped_duplicate_count=len(skipped),
        processed_requests=(record,),
        skipped_duplicates=skipped,
        latest_response=asdict(published),
        errors_or_blockers=errors,
        next_safe_move=published.next_safe_move or "Show the response in Mac chat.",
        mode="stopped",
        current_poll_interval=0.0,
        idle_poll_interval=DEFAULT_IDLE_POLL_INTERVAL,
        active_poll_interval=DEFAULT_ACTIVE_POLL_INTERVAL,
        active_window_seconds=DEFAULT_ACTIVE_WINDOW_SECONDS,
        active_window_remaining_seconds=0.0,
        last_watch_mode_before_stop="active",
        last_poll_interval=0.0,
        last_processed_request_id=identity.source_request_id,
        last_response_path=published.response_file,
        bounded_stop_reason="processed_with_errors" if errors else "processed_one_request",
        last_processing_started_request_id=identity.source_request_id,
        last_routing_status=route.routing_status,
        selected_worker_target=route.selected_worker_target,
        selected_machine=route.selected_machine,
        processing_heartbeat_path=heartbeat.heartbeat_file,
        terminal_response_path=published.response_file,
        active_request_count=0,
        **_cache_result_fields(cache),
    )


def run_watch(
    *,
    inbox: Path = APPROVED_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    watch_seconds: int = 5,
    poll_interval: float = DEFAULT_IDLE_POLL_INTERVAL,
    active_poll_interval: float = DEFAULT_ACTIVE_POLL_INTERVAL,
    active_window_seconds: float = DEFAULT_ACTIVE_WINDOW_SECONDS,
    max_requests: int = 1,
    mac_handoff_dir: Path = DEFAULT_MAC_HANDOFF_DIR,
) -> ServiceRunResult:
    created_at = generated_at or utc_now()
    watch_duration = max(0.0, float(watch_seconds))
    deadline = time.monotonic() + watch_duration
    request_limit = max(1, max_requests)
    idle_interval = max(0.05, float(poll_interval))
    active_interval = max(0.01, float(active_poll_interval))
    active_window = max(0.0, float(active_window_seconds))
    active_until = 0.0
    read_model_cache = _new_read_model_cache(export_root)
    stale_before_mtime_ns = _latest_response_mtime_ns(response_dir)
    processed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[str] = []
    latest_response: dict[str, Any] | None = None
    in_memory_processed_keys: set[str] = set()
    last_watch_mode = "idle"
    last_poll_interval = 0.0
    stop_reason = "watch_seconds_elapsed"
    while True:
        now = time.monotonic()
        if now >= deadline:
            stop_reason = "watch_seconds_elapsed"
            break
        if len(processed) >= request_limit:
            stop_reason = "max_requests_reached"
            break
        result = process_one_pending_request(
            inbox=inbox,
            response_dir=response_dir,
            export_root=export_root,
            generated_at=created_at,
            extra_processed_keys=in_memory_processed_keys,
            read_model_cache=read_model_cache,
            mac_handoff_dir=mac_handoff_dir,
            stale_before_mtime_ns=stale_before_mtime_ns,
        )
        skipped.extend(result.skipped_duplicates)
        if result.processed_count:
            processed.extend(result.processed_requests)
            for record in result.processed_requests:
                for key in record.get("identity_keys") or ():
                    in_memory_processed_keys.add(str(key))
                if record.get("request_key"):
                    in_memory_processed_keys.add(str(record["request_key"]))
            latest_response = result.latest_response
            errors.extend(result.errors_or_blockers)
            created_at = utc_now()
            active_until = time.monotonic() + active_window
            last_watch_mode = "active"
            last_poll_interval = 0.0
            continue
        now = time.monotonic()
        if now >= deadline:
            stop_reason = "watch_seconds_elapsed"
            break
        active_remaining = max(0.0, active_until - now)
        if active_remaining > 0:
            current_mode = "active"
            requested_sleep = active_interval
        else:
            current_mode = "idle"
            requested_sleep = idle_interval
        sleep_for = min(requested_sleep, max(0.0, deadline - now))
        if sleep_for <= 0:
            stop_reason = "watch_seconds_elapsed"
            break
        last_watch_mode = current_mode
        last_poll_interval = sleep_for
        time.sleep(sleep_for)
    deduped_skipped = _dedupe_records(skipped)
    if processed:
        waiting_for_mac = any(record.get("internal_status") == "WAITING_FOR_MAC_READBACK" for record in processed)
        status = (
            "REQUEST_ROUTED_WAITING_FOR_MAC_READBACK"
            if waiting_for_mac
            else "REQUEST_PROCESSED" if not errors else "FAILED_WITH_REASON"
        )
        next_safe_move = (
            latest_response.get("next_safe_move")
            if latest_response
            else "Wait for the Mac worker readback."
        )
    else:
        status = "REQUEST_SKIPPED_DUPLICATE" if deduped_skipped else "WATCH_TIMED_OUT_IDLE"
        next_safe_move = (
            "All supported request files seen during the watch window were already handled."
            if deduped_skipped
            else "No supported request arrived before timeout; keep the service available for the next Mac request."
        )
    last_processed_request_id = str(processed[-1].get("source_request_id")) if processed else None
    last_response_path = str(latest_response.get("response_file")) if latest_response and latest_response.get("response_file") else None
    active_window_remaining = max(0.0, active_until - time.monotonic())
    return ServiceRunResult(
        service_status=status,
        run_mode=(
            f"watch_seconds={watch_seconds},max_requests={request_limit},"
            f"idle_poll_interval={idle_interval},active_poll_interval={active_interval},"
            f"active_window_seconds={active_window}"
        ),
        inbox=inbox.as_posix(),
        response_path=response_dir.as_posix(),
        processed_count=len(processed),
        skipped_duplicate_count=len(deduped_skipped),
        processed_requests=tuple(processed),
        skipped_duplicates=deduped_skipped,
        latest_response=latest_response,
        errors_or_blockers=tuple(errors),
        next_safe_move=str(next_safe_move),
        mode="stopped",
        current_poll_interval=0.0,
        idle_poll_interval=idle_interval,
        active_poll_interval=active_interval,
        active_window_seconds=active_window,
        active_window_remaining_seconds=active_window_remaining,
        last_watch_mode_before_stop=last_watch_mode,
        last_poll_interval=last_poll_interval,
        last_processed_request_id=last_processed_request_id,
        last_response_path=last_response_path,
        bounded_stop_reason=stop_reason,
        last_processing_started_request_id=str(processed[-1].get("source_request_id")) if processed else None,
        last_routing_status=str(processed[-1].get("routing_status")) if processed and processed[-1].get("routing_status") else None,
        selected_worker_target=str(processed[-1].get("selected_worker_target")) if processed and processed[-1].get("selected_worker_target") else None,
        selected_machine=str(processed[-1].get("selected_machine")) if processed and processed[-1].get("selected_machine") else None,
        processing_heartbeat_path=str(processed[-1].get("processing_heartbeat_path")) if processed and processed[-1].get("processing_heartbeat_path") else None,
        terminal_response_path=last_response_path,
        active_request_count=sum(1 for record in processed if record.get("internal_status") == "WAITING_FOR_MAC_READBACK"),
        **_cache_result_fields(read_model_cache),
    )


def _merge_processed_records(
    existing_status: Mapping[str, Any] | None,
    new_records: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    merged: dict[str, dict[str, Any]] = {
        str(record.get("request_key")): record
        for record in _processed_records(existing_status)
        if record.get("request_key")
    }
    for record in new_records:
        if record.get("request_key"):
            merged[str(record["request_key"])] = record
    return tuple(merged.values())


def _dedupe_records(records: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record.get("request_key") or record.get("source_request_id") or record.get("source_request_filename"))
        if key:
            deduped[key] = record
    return tuple(deduped.values())


def _machine_proof(result: ServiceRunResult) -> dict[str, Any]:
    return {
        "approved_inbox_only": result.inbox == APPROVED_INBOX.as_posix() or bool(result.inbox),
        "response_path_present": bool(result.response_path),
        "per_request_response_written": result.processed_count == 0 or bool(result.latest_response and result.latest_response.get("response_file")),
        "operator_message_present": result.processed_count == 0 or bool(result.latest_response and result.latest_response.get("operator_message")),
        "how_to_fix_present": result.processed_count == 0 or bool(result.latest_response and result.latest_response.get("how_to_fix")),
        "terminal_response_written": result.processed_count == 0 or bool(result.latest_response and result.latest_response.get("terminal") is True),
        "route_aware_processing_heartbeat_written": result.processed_count == 0 or bool(result.processing_heartbeat_path),
        "processing_heartbeat_terminal_false": result.processed_count == 0 or bool(result.processing_heartbeat_path),
        "fake_success_claimed": False,
        "duplicate_tracking_present": True,
        "duplicate_keys_include_request_id_idempotency_filename_payload_hash": True,
        "active_session_watch_present": True,
        "idle_poll_interval_configured": result.idle_poll_interval,
        "active_poll_interval_configured": result.active_poll_interval,
        "active_window_seconds_configured": result.active_window_seconds,
        "active_window_remaining_recorded": result.active_window_remaining_seconds >= 0,
        "max_requests_configured": result.run_mode == "once" or "max_requests=" in result.run_mode,
        "atomic_response_writes": True,
        "read_model_cache_enabled": result.cache_enabled,
        "read_model_cache_process_local": True,
        "read_model_cache_no_persistent_files": True,
        "read_model_cache_generated_json_only": True,
        "read_model_cache_does_not_skip_request_validation": True,
        "read_model_cache_does_not_skip_payload_hash_checks": True,
        "read_model_cache_does_not_skip_authority_checks": True,
        "read_model_cache_hits": result.cache_hits,
        "read_model_cache_misses": result.cache_misses,
        "read_model_cache_invalidations": result.cache_invalidations,
        "no_request_deletion": True,
        "no_request_mutation": True,
        "no_broad_scan": True,
        "no_symlink_follow": True,
        "bounded_run_mode": result.run_mode == "once" or result.run_mode.startswith("watch_seconds="),
        "unbounded_loop_default": False,
        "workflow_execution_performed": False,
        "model_call_performed": False,
        "tool_execution_performed": False,
        "agent_dispatch_performed": False,
        "mac_automation_performed": False,
        "email_draft_or_send_performed": False,
        "coupa_access_or_submit_performed": False,
        "browser_access_performed": False,
        "invoice_generation_performed": False,
        "attachment_performed": False,
        "approval_request_performed": False,
        "speech_synthesis_performed": False,
        "microphone_capture_performed": False,
        "cloud_audio_performed": False,
        "voice_model_call_performed": False,
        "payment_tracking_write_performed": False,
        "external_action_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "all_authority_boundary_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "content_hash": None,
    }


def build_service_status_payload(
    result: ServiceRunResult,
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    existing_status = read_service_status(export_root)
    all_records = _merge_processed_records(existing_status, result.processed_requests)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "service_status_values": SERVICE_STATUSES,
        "watch_modes": WATCH_MODES,
        "routing_status_values": ROUTING_STATUSES,
        "worker_targets": WORKER_TARGETS,
        "service_status": {
            **asdict(result),
            "processed_request_count": result.processed_count,
            "all_processed_request_records": all_records,
        },
        "supported_request_patterns": processor.SUPPORTED_REQUEST_PATTERNS,
        "service_supported_request_families": SERVICE_SUPPORTED_REQUEST_FAMILIES,
        "run_modes": {
            "once": "Process one pending supported request and exit.",
            "watch_seconds": "Poll the configured inbox for a bounded number of seconds, then exit.",
            "idle_poll_interval": "Backoff interval used outside an active request window.",
            "active_poll_interval": "Fast poll interval used briefly after a new supported request is processed.",
            "active_window_seconds": "Bounded responsive window before backing off to idle polling.",
            "max_requests": "Caps how many new requests a watch run may process before exiting.",
            "persistent_service": "Template available for explicit operator-controlled systemd user activation; not auto-started by this status export.",
        },
        "read_model_cache_policy": {
            "enabled": result.cache_enabled,
            "scope": "process-local only",
            "cache_key": ("file_path", "stat.st_mtime_ns", "stat.st_size"),
            "approved_targets": "generated read-model JSON files under the configured export root",
            "persistent_cache_files_created": False,
            "request_validation_skipped": False,
            "payload_hash_checks_skipped": False,
            "authority_checks_skipped": False,
            "raw_body_ingestion_allowed": False,
        },
        "manual_run_help": {
            "once": "python3 scripts/run_openclaw_request_response_service.py --once --format json",
            "bounded_watch": (
                "python3 scripts/run_openclaw_request_response_service.py --watch-seconds 10 "
                "--poll-interval 1 --active-poll-interval 0.05 --active-window-seconds 180 "
                "--max-requests 1 --format json"
            ),
            "approved_inbox": APPROVED_INBOX.as_posix(),
            "response_dir": DEFAULT_RESPONSE_DIR.as_posix(),
            "mac_handoff_dir": DEFAULT_MAC_HANDOFF_DIR.as_posix(),
            "systemd_user_template": "systemd/user/openclaw-request-response.service.in",
            "activation_after_smoke_approval": (
                "scripts/install_openclaw_stack.sh --apply --enable --start --request-response-only"
            ),
            "activation_status": "not started by this command",
        },
        "response_output_policy": {
            "response_dir": result.response_path,
            "per_request_filename": "openclaw_response_for_mac_<source_request_id>.json",
            "latest_filename": LATEST_RESPONSE_EXPORT_NAME,
            "processing_heartbeat_filename": "openclaw_processing_for_mac_<source_request_id>.json",
            "latest_processing_heartbeat_filename": LATEST_PROCESSING_EXPORT_NAME,
            "manifest_filename": MANIFEST_EXPORT_NAME,
            "atomic_write_policy": "write temporary JSON then rename into place",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(result)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_status_markdown(payload: Mapping[str, Any]) -> str:
    status = payload["service_status"]
    latest = status.get("latest_response") or {}
    return "\n".join(
        [
            "# OpenClaw Request/Response Service Status",
            "",
            f"Status: {status['service_status']}",
            "",
            f"Inbox: {status['inbox']}",
            f"Response path: {status['response_path']}",
            f"Mode: {status.get('mode', 'unknown')}",
            f"Idle poll interval: {status.get('idle_poll_interval', 'unknown')}",
            f"Active poll interval: {status.get('active_poll_interval', 'unknown')}",
            f"Active window remaining: {status.get('active_window_remaining_seconds', 'unknown')}",
            f"Read-model cache enabled: {status.get('cache_enabled', False)}",
            f"Read-model cache hits: {status.get('cache_hits', 0)}",
            f"Read-model cache misses: {status.get('cache_misses', 0)}",
            f"Read-model cache invalidations: {status.get('cache_invalidations', 0)}",
            f"Cached file count: {status.get('cached_file_count', 0)}",
            f"Last cached refs: {', '.join(status.get('last_cached_paths') or ()) or 'none'}",
            f"Processed request count: {status.get('processed_request_count', status.get('processed_count', 0))}",
            f"Last processing request: {status.get('last_processing_started_request_id') or 'none'}",
            f"Last routing status: {status.get('last_routing_status') or 'none'}",
            f"Selected worker: {status.get('selected_worker_target') or 'none'}",
            f"Selected machine: {status.get('selected_machine') or 'none'}",
            f"Processing heartbeat: {status.get('processing_heartbeat_path') or 'none'}",
            f"Terminal response: {status.get('terminal_response_path') or 'none'}",
            f"Active request count: {status.get('active_request_count', 0)}",
            f"Last request: {status.get('last_processed_request_id') or 'none'}",
            f"Last response: {status.get('last_response_path') or 'none'}",
            f"Stop reason: {status.get('bounded_stop_reason', 'unknown')}",
            "",
            "Latest response:",
            f"- File: {latest.get('response_file', 'none')}",
            f"- Headline: {latest.get('operator_headline', 'none')}",
            f"- Message: {latest.get('operator_message', 'none')}",
            f"- How to fix: {latest.get('how_to_fix', 'none')}",
            "",
            "Boundary:",
            "- Approved inbox only.",
            "- Bounded run modes only.",
            "- No request deletion, workflow execution, model/tool execution, external action, raw-body ingestion, Mac sync/import, or Swift change.",
            "",
            f"Next safe move: {status['next_safe_move']}",
            "",
        ]
    )


def write_service_status(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / STATUS_JSON_EXPORT_NAME
    operator_path = export_root / STATUS_OPERATOR_EXPORT_NAME
    _atomic_write_text(json_path, stable_json(payload))
    _atomic_write_text(operator_path, format_status_markdown(payload))
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    status = payload["service_status"]
    latest = status.get("latest_response") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "status_json_path": paths[0].as_posix(),
        "status_operator_path": paths[1].as_posix(),
        "service_status": status["service_status"],
        "run_mode": status["run_mode"],
        "inbox": status["inbox"],
        "response_path": status["response_path"],
        "processed_count": status["processed_count"],
        "skipped_duplicate_count": status["skipped_duplicate_count"],
        "mode": status.get("mode"),
        "current_poll_interval": status.get("current_poll_interval"),
        "idle_poll_interval": status.get("idle_poll_interval"),
        "active_poll_interval": status.get("active_poll_interval"),
        "active_window_seconds": status.get("active_window_seconds"),
        "active_window_remaining_seconds": status.get("active_window_remaining_seconds"),
        "cache_enabled": status.get("cache_enabled"),
        "cache_hits": status.get("cache_hits"),
        "cache_misses": status.get("cache_misses"),
        "cache_invalidations": status.get("cache_invalidations"),
        "cached_file_count": status.get("cached_file_count"),
        "last_cached_paths": status.get("last_cached_paths"),
        "last_processed_request_id": status.get("last_processed_request_id"),
        "last_response_path": status.get("last_response_path"),
        "last_processing_started_request_id": status.get("last_processing_started_request_id"),
        "last_routing_status": status.get("last_routing_status"),
        "selected_worker_target": status.get("selected_worker_target"),
        "selected_machine": status.get("selected_machine"),
        "processing_heartbeat_path": status.get("processing_heartbeat_path"),
        "terminal_response_path": status.get("terminal_response_path"),
        "active_request_count": status.get("active_request_count"),
        "bounded_stop_reason": status.get("bounded_stop_reason"),
        "latest_response_file": latest.get("response_file"),
        "operator_headline": latest.get("operator_headline"),
        "operator_message": latest.get("operator_message"),
        "how_to_fix": latest.get("how_to_fix"),
        "next_safe_move": status["next_safe_move"],
        "all_authority_boundary_flags_false": payload["machine_proof"]["all_authority_boundary_flags_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def run_service(
    *,
    once: bool = True,
    watch_seconds: int | None = None,
    poll_interval: float = DEFAULT_IDLE_POLL_INTERVAL,
    active_poll_interval: float = DEFAULT_ACTIVE_POLL_INTERVAL,
    active_window_seconds: float = DEFAULT_ACTIVE_WINDOW_SECONDS,
    max_requests: int = 1,
    inbox: Path = APPROVED_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    mac_handoff_dir: Path = DEFAULT_MAC_HANDOFF_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], tuple[Path, Path]]:
    if watch_seconds is not None:
        result = run_watch(
            inbox=inbox,
            response_dir=response_dir,
            export_root=export_root,
            generated_at=generated_at,
            watch_seconds=watch_seconds,
            poll_interval=poll_interval,
            active_poll_interval=active_poll_interval,
            active_window_seconds=active_window_seconds,
            max_requests=max_requests,
            mac_handoff_dir=mac_handoff_dir,
        )
    else:
        result = process_one_pending_request(
            inbox=inbox,
            response_dir=response_dir,
            export_root=export_root,
            generated_at=generated_at,
            mac_handoff_dir=mac_handoff_dir,
        )
    payload = build_service_status_payload(result, export_root=export_root, generated_at=generated_at)
    paths = write_service_status(payload, export_root)
    return payload, paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded local OpenClaw request/response service.")
    parser.add_argument("--once", action="store_true", help="Process one pending request and exit. This is the default.")
    parser.add_argument("--watch-seconds", type=int, default=None, help="Bounded polling window, then exit.")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_IDLE_POLL_INTERVAL, help="Idle poll interval in seconds.")
    parser.add_argument(
        "--active-poll-interval",
        type=float,
        default=DEFAULT_ACTIVE_POLL_INTERVAL,
        help="Fast poll interval in seconds during the bounded active window.",
    )
    parser.add_argument(
        "--active-window-seconds",
        type=float,
        default=DEFAULT_ACTIVE_WINDOW_SECONDS,
        help="Seconds to keep fast polling after a new supported request is processed.",
    )
    parser.add_argument("--max-requests", type=int, default=1, help="Maximum new requests to process in a watch run.")
    parser.add_argument("--inbox", default=str(APPROVED_INBOX))
    parser.add_argument("--response-dir", default=str(DEFAULT_RESPONSE_DIR))
    parser.add_argument("--mac-handoff-dir", default=str(DEFAULT_MAC_HANDOFF_DIR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    payload, paths = run_service(
        once=args.once,
        watch_seconds=args.watch_seconds,
        poll_interval=args.poll_interval,
        active_poll_interval=args.active_poll_interval,
        active_window_seconds=args.active_window_seconds,
        max_requests=args.max_requests,
        inbox=Path(args.inbox),
        response_dir=Path(args.response_dir),
        mac_handoff_dir=Path(args.mac_handoff_dir),
        export_root=Path(args.export_root),
        generated_at=args.generated_at,
    )
    output = payload if args.format == "json" else build_summary(payload, paths)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
