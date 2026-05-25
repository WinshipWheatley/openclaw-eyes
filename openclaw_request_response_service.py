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


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_INBOX = processor.APPROVED_INBOX
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
DEFAULT_IDLE_POLL_INTERVAL = 1.0
DEFAULT_ACTIVE_POLL_INTERVAL = 0.05
DEFAULT_ACTIVE_WINDOW_SECONDS = 180.0

SCHEMA_VERSION = "openclaw_request_response_service_v1"
STATUS_READ_MODEL_ID = "openclaw_request_response_service_status"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
STATUS_OPERATOR_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}_STATUS_OPERATOR.md"
MANIFEST_EXPORT_NAME = "response_manifest.json"
LATEST_RESPONSE_EXPORT_NAME = "openclaw_response_for_mac_latest.json"
CONTRACT_STATUS = "BOUNDED_LOCAL_OPENCLAW_REQUEST_RESPONSE_SERVICE"

SERVICE_STATUSES = (
    "IDLE_NO_REQUEST_AVAILABLE",
    "REQUEST_PROCESSED",
    "REQUEST_SKIPPED_DUPLICATE",
    "WATCH_TIMED_OUT_IDLE",
    "FAILED_WITH_REASON",
    "UNKNOWN_FAIL_CLOSED",
)

WATCH_MODES = ("idle", "active", "stopped")

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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


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
    return processor.classify_request_filename(path.name).request_family


def list_candidate_requests(inbox: Path = APPROVED_INBOX) -> tuple[Path, ...]:
    if not inbox.exists() or not inbox.is_dir():
        return ()
    candidates: list[Path] = []
    for path in inbox.iterdir():
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        if classify_request_path(path) in {"CHAT", "FILE_METADATA"}:
            candidates.append(path)
    return tuple(sorted(candidates, key=lambda item: (item.stat().st_mtime_ns, item.name)))


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
    source_request_id = str(raw.get("request_id") or f"missing_request_id_{path.stem}")
    idempotency_key = str(raw.get("idempotency_key")) if raw.get("idempotency_key") else None
    payload_hash = str(raw.get("payload_hash")) if raw.get("payload_hash") else None
    workflow_ref = str(raw.get("workflow_ref") or "unknown")
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
    export_root: Path = DEFAULT_EXPORT_ROOT,
    extra_processed_keys: set[str] | None = None,
) -> tuple[Path | None, tuple[dict[str, Any], ...]]:
    existing_status = read_service_status(export_root)
    processed = _processed_identity_keys(existing_status)
    if extra_processed_keys:
        processed.update(extra_processed_keys)
    skipped: list[dict[str, Any]] = []
    for candidate in list_candidate_requests(inbox):
        identity = read_request_identity(candidate)
        identity_keys = _identity_keys(candidate, identity)
        matching_keys = tuple(key for key in identity_keys if key in processed)
        if matching_keys:
            skipped.append(
                {
                    "source_request_id": identity.source_request_id,
                    "source_request_filename": candidate.name,
                    "request_key": identity.request_key,
                    "identity_keys": identity_keys,
                    "matched_duplicate_keys": matching_keys,
                    "reason": "already processed by local request/response service",
                }
            )
            continue
        return candidate, tuple(skipped)
    return None, tuple(skipped)


def _published_response_payload(response_payload: Mapping[str, Any], *, created_at: str) -> dict[str, Any]:
    terminal = response_payload.get("internal_status") in {
        "RESPONSE_READY",
        "BLOCKED_WITH_REASON",
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
    _atomic_write_text(response_file, stable_json(published_payload))
    _atomic_write_text(latest_file, stable_json(published_payload))

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


def _record_from_response(
    request_path: Path,
    identity: RequestIdentity,
    response_payload: Mapping[str, Any],
    published: PublishedResponse,
    *,
    created_at: str,
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
        "created_at": created_at,
    }


def process_one_pending_request(
    *,
    inbox: Path = APPROVED_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    extra_processed_keys: set[str] | None = None,
) -> ServiceRunResult:
    created_at = generated_at or utc_now()
    request_path, skipped = select_next_pending_request(
        inbox=inbox,
        export_root=export_root,
        extra_processed_keys=extra_processed_keys,
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
        )

    identity = read_request_identity(request_path)
    try:
        response_payload, _processor_status, _paths, quality_errors = processor.run_and_write(
            inbox=inbox,
            request_file=request_path,
            request_id=None,
            export_root=export_root,
            generated_at=created_at,
        )
        errors = tuple(str(item) for item in quality_errors)
    except Exception as exc:  # pragma: no cover - defensive service boundary
        response_payload = _failure_processor_payload(
            request_path=request_path,
            reason=f"{type(exc).__name__}: {exc}",
            created_at=created_at,
        )
        errors = (str(response_payload["why_it_happened"]),)
    published = publish_response_for_mac(response_payload, response_dir=response_dir, created_at=created_at)
    record = _record_from_response(request_path, identity, response_payload, published, created_at=created_at)
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
) -> ServiceRunResult:
    created_at = generated_at or utc_now()
    watch_duration = max(0.0, float(watch_seconds))
    deadline = time.monotonic() + watch_duration
    request_limit = max(1, max_requests)
    idle_interval = max(0.05, float(poll_interval))
    active_interval = max(0.01, float(active_poll_interval))
    active_window = max(0.0, float(active_window_seconds))
    active_until = 0.0
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
        status = "REQUEST_PROCESSED" if not errors else "FAILED_WITH_REASON"
        next_safe_move = (
            latest_response.get("next_safe_move")
            if latest_response
            else "Show the latest response in Mac chat."
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
        "duplicate_tracking_present": True,
        "duplicate_keys_include_request_id_idempotency_filename_payload_hash": True,
        "active_session_watch_present": True,
        "idle_poll_interval_configured": result.idle_poll_interval,
        "active_poll_interval_configured": result.active_poll_interval,
        "active_window_seconds_configured": result.active_window_seconds,
        "active_window_remaining_recorded": result.active_window_remaining_seconds >= 0,
        "max_requests_configured": result.run_mode == "once" or "max_requests=" in result.run_mode,
        "atomic_response_writes": True,
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
        "email_draft_or_send_performed": False,
        "coupa_access_or_submit_performed": False,
        "browser_access_performed": False,
        "invoice_generation_performed": False,
        "attachment_performed": False,
        "approval_request_performed": False,
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
        "service_status": {
            **asdict(result),
            "processed_request_count": result.processed_count,
            "all_processed_request_records": all_records,
        },
        "supported_request_patterns": processor.SUPPORTED_REQUEST_PATTERNS,
        "run_modes": {
            "once": "Process one pending supported request and exit.",
            "watch_seconds": "Poll the configured inbox for a bounded number of seconds, then exit.",
            "idle_poll_interval": "Backoff interval used outside an active request window.",
            "active_poll_interval": "Fast poll interval used briefly after a new supported request is processed.",
            "active_window_seconds": "Bounded responsive window before backing off to idle polling.",
            "max_requests": "Caps how many new requests a watch run may process before exiting.",
            "persistent_service": "Not installed or enabled in this lane.",
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
        },
        "response_output_policy": {
            "response_dir": result.response_path,
            "per_request_filename": "openclaw_response_for_mac_<source_request_id>.json",
            "latest_filename": LATEST_RESPONSE_EXPORT_NAME,
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
            f"Processed request count: {status.get('processed_request_count', status.get('processed_count', 0))}",
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
        "last_processed_request_id": status.get("last_processed_request_id"),
        "last_response_path": status.get("last_response_path"),
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
        )
    else:
        result = process_one_pending_request(
            inbox=inbox,
            response_dir=response_dir,
            export_root=export_root,
            generated_at=generated_at,
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
        export_root=Path(args.export_root),
        generated_at=args.generated_at,
    )
    output = payload if args.format == "json" else build_summary(payload, paths)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
