"""Bounded OpenClaw chat request processor v0.

This module processes one Mission Control request file through existing
deterministic rails and writes a human-readable operator response. It is not a
daemon, watcher, auto-dispatcher, model/runtime lane, workflow executor,
external action lane, or Mac sync/import path.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import chat_readback_card_mirror
import conversational_workflow_router_intake
import operator_file_metadata_intake
import worker_routing_intelligence
import workflow_execution_package_compiler


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")

SCHEMA_VERSION = "openclaw_chat_request_processor_v0"
STATUS_READ_MODEL_ID = "openclaw_chat_request_processor_status"
RESPONSE_READ_MODEL_ID = "openclaw_chat_response_for_mac"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
STATUS_OPERATOR_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}_OPERATOR.md"
RESPONSE_JSON_EXPORT_NAME = f"{RESPONSE_READ_MODEL_ID}.json"
RESPONSE_OPERATOR_EXPORT_NAME = f"{RESPONSE_READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "BOUNDED_NON_DAEMON_CHAT_REQUEST_PROCESSOR"

SUPPORTED_REQUEST_PATTERNS = (
    conversational_workflow_router_intake.REQUEST_FILENAME_PATTERN,
    operator_file_metadata_intake.REQUEST_FILENAME_PATTERN,
)

INTERNAL_STATUSES = (
    "REQUEST_FOUND",
    "REQUEST_PROCESSING",
    "RESPONSE_READY",
    "BLOCKED_WITH_REASON",
    "FAILED_WITH_REASON",
    "TIMED_OUT_WITH_REASON",
    "DUPLICATE_NOOP_WITH_READBACK",
    "NO_REQUEST_AVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

REQUEST_TYPES = (
    "CHAT_WORKFLOW_REQUEST",
    "FILE_METADATA_REQUEST",
    "UNKNOWN_REQUEST",
)

AUTHORITY_BOUNDARY = {
    "live_daemon_allowed": False,
    "live_watcher_allowed": False,
    "live_auto_dispatch_allowed": False,
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
    "network_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

RAW_BODY_KEYS = {
    "raw_body",
    "raw_private_body",
    "raw_message_body",
    "raw_email_body",
    "raw_file_body",
    "file_body",
    "body",
    "content",
    "contents",
    "raw_bytes",
    "file_bytes",
    "base64",
    "ocr_text",
    "pdf_text",
    "spreadsheet_rows",
    "image_pixels",
}

SECRET_KEYS = {
    "password",
    "passcode",
    "token",
    "oauth_token",
    "refresh_token",
    "api_key",
    "secret",
    "credential",
    "credentials",
    "cookie",
    "session_cookie",
}

VISUAL_COUPLED_KEYS = {
    "ui_coordinates",
    "button_id",
    "swiftui_view",
    "view_name",
    "frame",
    "screen_metadata",
    "tap_target",
    "accessibility_frame",
    "cursor_position",
}

CHAT_REQUIRED_FIELDS = conversational_workflow_router_intake.REQUIRED_REQUEST_FIELDS
FILE_REQUIRED_FIELDS = operator_file_metadata_intake.REQUIRED_REQUEST_FIELDS


@dataclass(frozen=True)
class ProcessorResponseForMac:
    source_request_id: str
    source_request_filename: str | None
    workflow_ref: str
    request_type: str
    internal_status: str
    operator_headline: str
    operator_message: str
    what_happened: tuple[str, ...]
    why_it_happened: str
    how_to_fix: str
    visible_cards: tuple[dict[str, Any], ...]
    cards_available: bool
    card_mirror_refs: tuple[str, ...]
    file_readback_refs: tuple[str, ...]
    worker_route_refs: tuple[dict[str, Any], ...]
    blocked_reason: str | None
    detail_disclosure: dict[str, Any]
    readback_files: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ProcessorStatusReadModel:
    processor_id: str
    bounded_mode: str
    approved_inbox_policy: str
    supported_request_patterns: tuple[str, ...]
    latest_processed_request: dict[str, Any] | None
    terminal_result: str
    operator_headline: str
    operator_message: str
    generated_readbacks: tuple[str, ...]
    errors_or_blockers: tuple[str, ...]
    next_safe_move: str
    authority_boundary: dict[str, bool]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _short_hash(*parts: Any) -> str:
    return hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:20]


def request_type_for_filename(filename: str) -> str:
    if fnmatch.fnmatch(filename, conversational_workflow_router_intake.REQUEST_FILENAME_PATTERN):
        return "CHAT_WORKFLOW_REQUEST"
    if fnmatch.fnmatch(filename, operator_file_metadata_intake.REQUEST_FILENAME_PATTERN):
        return "FILE_METADATA_REQUEST"
    return "UNKNOWN_REQUEST"


def list_supported_requests(inbox: Path = APPROVED_INBOX) -> tuple[Path, ...]:
    if not inbox.exists() or not inbox.is_dir():
        return ()
    matches = [
        path
        for path in inbox.iterdir()
        if path.is_file() and request_type_for_filename(path.name) != "UNKNOWN_REQUEST"
    ]
    return tuple(sorted(matches, key=lambda path: (path.stat().st_mtime_ns, path.name)))


def select_newest_request(inbox: Path = APPROVED_INBOX) -> Path | None:
    requests = list_supported_requests(inbox)
    return requests[-1] if requests else None


def _load_json_request(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request JSON must be an object")
    return value


def _walk_dict(value: Any, *, prefix: str = "") -> tuple[tuple[str, Any], ...]:
    entries: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            entries.append((path, item))
            entries.extend(_walk_dict(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            entries.extend(_walk_dict(item, prefix=f"{prefix}[{index}]"))
    return tuple(entries)


def _has_nonempty_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def preflight_request(raw_request: Mapping[str, Any], request_type: str) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    blockers: list[str] = []
    fixes: list[str] = []
    required = CHAT_REQUIRED_FIELDS if request_type == "CHAT_WORKFLOW_REQUEST" else FILE_REQUIRED_FIELDS
    missing = [field for field in required if field not in raw_request]
    if missing:
        blockers.append(f"Missing required field(s): {', '.join(missing)}.")
        fixes.append("Regenerate or resend the request with the required fields.")
    if not raw_request.get("idempotency_key"):
        blockers.append("Missing idempotency key.")
        fixes.append("Resend the request with idempotency_key set.")
    if not raw_request.get("payload_hash"):
        blockers.append("Missing payload hash.")
        fixes.append("Resend the request with payload_hash set.")
    authority = raw_request.get("authority_boundary")
    if not isinstance(authority, Mapping):
        blockers.append("Missing or invalid authority boundary.")
        fixes.append("Include an authority_boundary object with all live authority set false.")
    elif any(value is True for value in authority.values()):
        blockers.append("Request asks for live authority this processor cannot grant.")
        fixes.append("Resend as a deterministic request with all external/live authority false.")
    for path, value in _walk_dict(raw_request):
        key = path.rsplit(".", 1)[-1].lower()
        if key in RAW_BODY_KEYS and _has_nonempty_value(value):
            blockers.append(f"Raw body content is present at {key}.")
            fixes.append("Remove raw bodies and send a metadata-only request with sanitized summaries or source refs.")
            break
    for path, value in _walk_dict(raw_request):
        key = path.rsplit(".", 1)[-1].lower()
        if key in SECRET_KEYS and _has_nonempty_value(value):
            blockers.append(f"Credential-like material is present at {key}.")
            fixes.append("Use protected secret intake later; do not include secrets in chat requests.")
            break
    for path, value in _walk_dict(raw_request):
        key = path.rsplit(".", 1)[-1].lower()
        if key in VISUAL_COUPLED_KEYS and _has_nonempty_value(value):
            blockers.append(f"UI-coupled field is present at {key}.")
            fixes.append("Resend a visual-agnostic request without coordinates, view names, frames, or button IDs.")
            break
    return not blockers, tuple(dict.fromkeys(blockers)), tuple(dict.fromkeys(fixes))


def _read_existing_processor_status(export_root: Path) -> dict[str, Any] | None:
    path = export_root / STATUS_JSON_EXPORT_NAME
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _existing_duplicate_response(raw_request: Mapping[str, Any], export_root: Path) -> ProcessorResponseForMac | None:
    status = _read_existing_processor_status(export_root)
    response_path = export_root / RESPONSE_JSON_EXPORT_NAME
    if not status or not response_path.exists():
        return None
    latest = status.get("processor_status", {}).get("latest_processed_request")
    if not isinstance(latest, Mapping):
        return None
    request_id = str(raw_request.get("request_id") or "")
    if not request_id or latest.get("source_request_id") != request_id:
        return None
    if status.get("processor_status", {}).get("terminal_result") in {"FAILED_WITH_REASON", "NO_REQUEST_AVAILABLE"}:
        return None
    try:
        existing_response = json.loads(response_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    readback_files = tuple(existing_response.get("readback_files") or ())
    return ProcessorResponseForMac(
        source_request_id=request_id,
        source_request_filename=str(latest.get("source_request_filename") or ""),
        workflow_ref=str(raw_request.get("workflow_ref") or latest.get("workflow_ref") or "unknown"),
        request_type=str(latest.get("request_type") or "UNKNOWN_REQUEST"),
        internal_status="DUPLICATE_NOOP_WITH_READBACK",
        operator_headline="OpenClaw already processed this request",
        operator_message="OpenClaw already processed this request. No duplicate was written. Here is the existing readback.",
        what_happened=("Found an existing processor readback for the same request id.", "No duplicate source or workflow write was made."),
        why_it_happened="The generated processor status already matches this request id.",
        how_to_fix="Use the existing readback, or resend a new request with a new request id and idempotency key if the content changed.",
        visible_cards=tuple(existing_response.get("visible_cards") or ()),
        cards_available=bool(existing_response.get("cards_available")),
        card_mirror_refs=tuple(existing_response.get("card_mirror_refs") or ()),
        file_readback_refs=tuple(existing_response.get("file_readback_refs") or ()),
        worker_route_refs=tuple(existing_response.get("worker_route_refs") or ()),
        blocked_reason=None,
        detail_disclosure={
            "existing_response_ref": RESPONSE_JSON_EXPORT_NAME,
            "duplicate_result": "existing readback reused",
        },
        readback_files=readback_files,
        next_safe_move="Show the existing readback in Mac chat.",
    )


def _processor_status_from_response(
    response: ProcessorResponseForMac,
    *,
    blockers: tuple[str, ...] = (),
) -> ProcessorStatusReadModel:
    return ProcessorStatusReadModel(
        processor_id="openclaw_chat_request_processor_v0",
        bounded_mode="process one request and exit",
        approved_inbox_policy=f"default inbox is {APPROVED_INBOX.as_posix()}; scans immediate supported request files only",
        supported_request_patterns=SUPPORTED_REQUEST_PATTERNS,
        latest_processed_request={
            "source_request_id": response.source_request_id,
            "source_request_filename": response.source_request_filename,
            "workflow_ref": response.workflow_ref,
            "request_type": response.request_type,
        },
        terminal_result=response.internal_status,
        operator_headline=response.operator_headline,
        operator_message=response.operator_message,
        generated_readbacks=response.readback_files,
        errors_or_blockers=blockers,
        next_safe_move=response.next_safe_move,
        authority_boundary=AUTHORITY_BOUNDARY,
    )


def _visible_cards_from_chat_mirror(mirror_payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    cards = mirror_payload.get("chat_human_cards")
    if isinstance(cards, (list, tuple)):
        return tuple(card for card in cards if isinstance(card, Mapping))
    mirror = mirror_payload.get("chat_readback_card_mirror")
    if isinstance(mirror, Mapping) and isinstance(mirror.get("cards"), (list, tuple)):
        return tuple(card for card in mirror["cards"] if isinstance(card, Mapping))
    return ()


def _chat_operator_message(mirror_payload: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    cards = _visible_cards_from_chat_mirror(mirror_payload)
    titles = tuple(str(card.get("title") or "") for card in cards)
    if cards:
        understood = next((card for card in cards if card.get("title") == "OpenClaw understood"), cards[0])
        bullets = tuple(str(item) for item in understood.get("bullets") or ())
        return (
            "I found the PC readback",
            "I found the PC readback. Here's what OpenClaw understood, what is missing, and what remains locked.",
            titles or bullets,
        )
    return (
        "I found a PC readback, but no cards were available",
        "The backend produced a readback, but it did not include visible cards. I will not invent a result.",
        (),
    )


def _should_export_package_compiler(raw_request: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(raw_request.get(key) or "")
        for key in ("operator_message", "sanitized_message_summary", "operator_goal")
    ).lower()
    return "make" in text and "happen" in text


def _process_chat_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
) -> ProcessorResponseForMac:
    router_payload = conversational_workflow_router_intake.build_payload_from_request_file(
        request_path,
        generated_at=generated_at,
    )
    router_json, router_operator = conversational_workflow_router_intake.write_exports(router_payload, export_root)
    mirror_payload = chat_readback_card_mirror.build_chat_readback_card_mirror(
        source_readback_path=router_json,
        generated_at=generated_at,
    )
    mirror_json, mirror_operator = chat_readback_card_mirror.write_exports(mirror_payload, export_root)
    routing_decision = worker_routing_intelligence.route_request(
        str(raw_request.get("sanitized_message_summary") or raw_request.get("operator_message") or ""),
        source_chat_ref=str(raw_request.get("request_id") or request_path.name),
    )
    readback_files = [
        router_json.as_posix(),
        router_operator.as_posix(),
        mirror_json.as_posix(),
        mirror_operator.as_posix(),
    ]
    detail: dict[str, Any] = {
        "router_readback_ref": router_json.as_posix(),
        "card_mirror_ref": mirror_json.as_posix(),
        "worker_route": asdict(routing_decision),
        "external_actions_locked": True,
    }
    if _should_export_package_compiler(raw_request):
        compiler_payload = workflow_execution_package_compiler.build_workflow_execution_package_compiler(
            generated_at=generated_at
        )
        compiler_json, compiler_operator = workflow_execution_package_compiler.write_exports(compiler_payload, export_root)
        readback_files.extend([compiler_json.as_posix(), compiler_operator.as_posix()])
        detail["workflow_execution_package_compiler_ref"] = compiler_json.as_posix()
    parse_status = router_payload["intake_result"]["parse_status"]
    mirror_status = mirror_payload["chat_readback_card_mirror"]["mirror_status"]
    cards = _visible_cards_from_chat_mirror(mirror_payload)
    request_id = str(raw_request.get("request_id") or router_payload["intake_request"]["request_id"])
    workflow_ref = str(raw_request.get("workflow_ref") or router_payload["intake_request"]["workflow_ref"])
    if parse_status == "ROUTED_DRAFT_READY" and mirror_status == "READY_FOR_MAC_RENDER":
        headline, message, card_titles = _chat_operator_message(mirror_payload)
        return ProcessorResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=workflow_ref,
            request_type="CHAT_WORKFLOW_REQUEST",
            internal_status="RESPONSE_READY",
            operator_headline=headline,
            operator_message=message,
            what_happened=(
                "PC consumed the Mac chat request through the deterministic router intake.",
                "PC generated router readback cards and a Mac-readable card mirror.",
                "No external action occurred.",
            ),
            why_it_happened="The request passed validation and matched the deterministic chat router rail.",
            how_to_fix="No fix is needed. Review the cards; edit the understanding if it is wrong.",
            visible_cards=cards,
            cards_available=bool(cards),
            card_mirror_refs=(mirror_json.as_posix(),),
            file_readback_refs=(),
            worker_route_refs=(asdict(routing_decision),),
            blocked_reason=None,
            detail_disclosure={**detail, "card_titles": card_titles},
            readback_files=tuple(readback_files),
            next_safe_move=mirror_payload["chat_readback_card_mirror"]["next_safe_move"],
        )
    blockers = tuple(
        blocker.get("elioperator_warning") or blocker.get("condition") or blocker.get("blocker_type")
        for blocker in router_payload.get("active_blockers_by_id", {}).values()
    )
    reason = "; ".join(str(item) for item in blockers) or "The router could not produce a current response-ready readback."
    return ProcessorResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type="CHAT_WORKFLOW_REQUEST",
        internal_status="BLOCKED_WITH_REASON",
        operator_headline="OpenClaw needs a safer chat request",
        operator_message="I could not continue this chat request yet. The processor generated a blocked readback with the reason and next fix.",
        what_happened=("The request reached PC but did not produce a response-ready card mirror.", "Nothing external happened."),
        why_it_happened=reason,
        how_to_fix="Fix the request fields or resend from Mac chat with idempotency, payload hash, sanitized summary, and all live authority false.",
        visible_cards=cards,
        cards_available=bool(cards),
        card_mirror_refs=(mirror_json.as_posix(),),
        file_readback_refs=(),
        worker_route_refs=(asdict(routing_decision),),
        blocked_reason=reason,
        detail_disclosure=detail,
        readback_files=tuple(readback_files),
        next_safe_move="Fix the request shape and rerun the bounded processor.",
    )


def _process_file_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
) -> ProcessorResponseForMac:
    file_payload = operator_file_metadata_intake.build_payload_from_request_file(
        request_path,
        generated_at=generated_at,
    )
    file_json, file_operator = operator_file_metadata_intake.write_exports(file_payload, export_root)
    readback = file_payload["metadata_readback"]
    request_id = str(raw_request.get("request_id") or file_payload["intake_request"]["request_id"])
    workflow_ref = str(raw_request.get("workflow_ref") or file_payload["intake_request"]["workflow_ref"])
    source_ref = file_payload.get("source_ref_record")
    readback_files = (file_json.as_posix(), file_operator.as_posix())
    if readback["readback_status"] == "SOURCE_REF_CREATED":
        label = source_ref["safe_display_label"] if isinstance(source_ref, Mapping) else "the file"
        return ProcessorResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=workflow_ref,
            request_type="FILE_METADATA_REQUEST",
            internal_status="RESPONSE_READY",
            operator_headline="File reference captured",
            operator_message=f"OpenClaw captured a file reference for '{label}'. The file body was not read.",
            what_happened=(
                "PC validated the file metadata request.",
                "PC created a metadata-only source ref readback.",
                "No file body was read or parsed.",
            ),
            why_it_happened="The request passed metadata-only validation.",
            how_to_fix="No fix is needed. Use the source ref in a visual workspace later, or request governed extraction when that rail exists.",
            visible_cards=(
                {
                    "title": readback["headline"],
                    "bullets": readback["human_bullets"],
                    "status_tone": "ready",
                },
            ),
            cards_available=True,
            card_mirror_refs=(),
            file_readback_refs=(file_json.as_posix(),),
            worker_route_refs=(),
            blocked_reason=None,
            detail_disclosure={
                "file_readback_ref": file_json.as_posix(),
                "source_ref_id": source_ref["source_ref_id"] if isinstance(source_ref, Mapping) else None,
                "persistent_registry_write": file_payload["intake_receipt"]["persistent_registry_write"],
            },
            readback_files=readback_files,
            next_safe_move=readback["next_safe_move"],
        )
    blockers = tuple(
        blocker.get("elioperator_warning") or blocker.get("condition") or blocker.get("blocker_type")
        for blocker in file_payload.get("active_blockers_by_id", {}).values()
    )
    reason = "; ".join(str(item) for item in blockers) or "The file metadata request did not pass safe intake validation."
    return ProcessorResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type="FILE_METADATA_REQUEST",
        internal_status="BLOCKED_WITH_REASON",
        operator_headline="File reference blocked",
        operator_message="I could not capture that file reference yet. The file request was blocked before any body was read.",
        what_happened=("PC validated the metadata request and blocked it.", "No file body was read or parsed."),
        why_it_happened=reason,
        how_to_fix="Send a metadata-only file request with supported file type, idempotency key, payload hash, hidden path ref, and no raw body.",
        visible_cards=(
            {
                "title": readback["headline"],
                "bullets": readback["human_bullets"],
                "status_tone": "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(file_json.as_posix(),),
        worker_route_refs=(),
        blocked_reason=reason,
        detail_disclosure={"file_readback_ref": file_json.as_posix()},
        readback_files=readback_files,
        next_safe_move=readback["next_safe_move"],
    )


def _failed_response(
    *,
    request_path: Path | None,
    request_type: str,
    reason: str,
    how_to_fix: str,
    generated_files: tuple[str, ...] = (),
) -> ProcessorResponseForMac:
    return ProcessorResponseForMac(
        source_request_id="unknown_unparseable_request",
        source_request_filename=request_path.name if request_path else None,
        workflow_ref="unknown",
        request_type=request_type,
        internal_status="FAILED_WITH_REASON",
        operator_headline="OpenClaw could not process the request",
        operator_message="The PC request processor could not process the request. Nothing was changed.",
        what_happened=("The processor stopped before running request rails.", "No source request file was changed or deleted."),
        why_it_happened=reason,
        how_to_fix=how_to_fix,
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        blocked_reason=reason,
        detail_disclosure={"error": reason},
        readback_files=generated_files,
        next_safe_move="Fix the request and rerun the bounded processor.",
    )


def _no_request_response(inbox: Path) -> ProcessorResponseForMac:
    return ProcessorResponseForMac(
        source_request_id="no_request_available",
        source_request_filename=None,
        workflow_ref="unknown",
        request_type="UNKNOWN_REQUEST",
        internal_status="NO_REQUEST_AVAILABLE",
        operator_headline="No Mac request is waiting",
        operator_message="I checked the approved PC inbox and did not find a supported Mac chat or file request.",
        what_happened=("PC scanned only the approved inbox for supported request filenames.", "No request files were changed or deleted."),
        why_it_happened="No mission_control_chat_request_*.json or mission_control_file_intake_request_*.json file was present.",
        how_to_fix="Send a new message or attachment from Mac chat, or run with --file for a specific supported request fixture.",
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        blocked_reason=None,
        detail_disclosure={"approved_inbox": inbox.as_posix(), "supported_patterns": SUPPORTED_REQUEST_PATTERNS},
        readback_files=(),
        next_safe_move="Wait for Mac to emit a request, then rerun this bounded processor.",
    )


def process_request_path(
    request_path: Path,
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    duplicate_check: bool = True,
) -> ProcessorResponseForMac:
    request_type = request_type_for_filename(request_path.name)
    if request_type == "UNKNOWN_REQUEST":
        return _failed_response(
            request_path=request_path,
            request_type="UNKNOWN_REQUEST",
            reason="Unsupported request filename.",
            how_to_fix="Use mission_control_chat_request_*.json or mission_control_file_intake_request_*.json.",
        )
    try:
        raw_request = _load_json_request(request_path)
    except json.JSONDecodeError as exc:
        return _failed_response(
            request_path=request_path,
            request_type=request_type,
            reason=f"Malformed JSON: {exc.msg}.",
            how_to_fix="Regenerate the request from Mac chat or fix the JSON object before retrying.",
        )
    except OSError as exc:
        return _failed_response(
            request_path=request_path,
            request_type=request_type,
            reason=f"Could not read request file: {exc}.",
            how_to_fix="Check that the request file exists and is readable, then rerun.",
        )
    if duplicate_check:
        duplicate = _existing_duplicate_response(raw_request, export_root)
        if duplicate is not None:
            return duplicate
    ok, blockers, fixes = preflight_request(raw_request, request_type)
    if not ok:
        return ProcessorResponseForMac(
            source_request_id=str(raw_request.get("request_id") or "unknown_request"),
            source_request_filename=request_path.name,
            workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
            request_type=request_type,
            internal_status="BLOCKED_WITH_REASON",
            operator_headline="OpenClaw needs a safer request",
            operator_message="I found the request, but it is blocked before processing because the shape is not safe.",
            what_happened=("The processor validated the request before running any rail.", "Nothing external happened."),
            why_it_happened=" ".join(blockers),
            how_to_fix=" ".join(fixes) or "Regenerate the request with safe metadata and required fields.",
            visible_cards=(),
            cards_available=False,
            card_mirror_refs=(),
            file_readback_refs=(),
            worker_route_refs=(),
            blocked_reason=" ".join(blockers),
            detail_disclosure={"preflight_blockers": blockers, "fixes": fixes},
            readback_files=(),
            next_safe_move="Fix the request and rerun the bounded processor.",
        )
    if request_type == "CHAT_WORKFLOW_REQUEST":
        return _process_chat_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
        )
    if request_type == "FILE_METADATA_REQUEST":
        return _process_file_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
        )
    return _failed_response(
        request_path=request_path,
        request_type=request_type,
        reason="Unknown request type.",
        how_to_fix="Use a supported Mission Control request filename.",
    )


def process_once(
    *,
    inbox: Path = APPROVED_INBOX,
    request_file: Path | None = None,
    request_id: str | None = None,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ProcessorResponseForMac:
    if request_file is not None:
        return process_request_path(request_file, export_root=export_root, generated_at=generated_at)
    candidates = list_supported_requests(inbox)
    if request_id:
        for candidate in reversed(candidates):
            try:
                raw = _load_json_request(candidate)
            except (json.JSONDecodeError, OSError):
                continue
            if str(raw.get("request_id") or "") == request_id:
                return process_request_path(candidate, export_root=export_root, generated_at=generated_at)
        return _failed_response(
            request_path=None,
            request_type="UNKNOWN_REQUEST",
            reason=f"No supported request with request_id {request_id} was found.",
            how_to_fix="Check the request id or pass --file with the exact supported request file.",
        )
    latest = candidates[-1] if candidates else None
    if latest is None:
        return _no_request_response(inbox)
    return process_request_path(latest, export_root=export_root, generated_at=generated_at)


def _terminal_quality_errors(response: ProcessorResponseForMac) -> tuple[str, ...]:
    errors: list[str] = []
    if response.internal_status in {"BLOCKED_WITH_REASON", "FAILED_WITH_REASON", "TIMED_OUT_WITH_REASON"}:
        if not response.how_to_fix.strip():
            errors.append(f"{response.internal_status} lacks how_to_fix.")
    if response.internal_status == "RESPONSE_READY":
        text = (response.operator_headline + " " + response.operator_message).strip().lower()
        if text in {"response ready", "response_ready"} or (not response.cards_available and not response.readback_files):
            errors.append("RESPONSE_READY lacks actual readback/card content.")
    if response.internal_status == "DUPLICATE_NOOP_WITH_READBACK":
        text = (response.operator_headline + " " + response.operator_message).lower()
        if "existing readback" not in text or not response.readback_files:
            errors.append("DUPLICATE_NOOP_WITH_READBACK lacks existing readback.")
    return tuple(errors)


def _machine_proof(response: ProcessorResponseForMac, status: ProcessorStatusReadModel) -> dict[str, Any]:
    quality_errors = _terminal_quality_errors(response)
    return {
        "processor_bounded_once": status.bounded_mode == "process one request and exit",
        "supported_chat_pattern_present": conversational_workflow_router_intake.REQUEST_FILENAME_PATTERN in SUPPORTED_REQUEST_PATTERNS,
        "supported_file_pattern_present": operator_file_metadata_intake.REQUEST_FILENAME_PATTERN in SUPPORTED_REQUEST_PATTERNS,
        "source_request_id_propagated": bool(response.source_request_id),
        "human_operator_message_present": bool(response.operator_headline and response.operator_message),
        "response_ready_has_real_readback": response.internal_status != "RESPONSE_READY" or bool(response.readback_files or response.visible_cards),
        "blocked_has_how_to_fix": response.internal_status != "BLOCKED_WITH_REASON" or bool(response.how_to_fix.strip()),
        "failed_has_how_to_fix": response.internal_status != "FAILED_WITH_REASON" or bool(response.how_to_fix.strip()),
        "timed_out_has_how_to_fix": response.internal_status != "TIMED_OUT_WITH_REASON" or bool(response.how_to_fix.strip()),
        "duplicate_has_existing_readback": response.internal_status != "DUPLICATE_NOOP_WITH_READBACK" or bool(response.readback_files),
        "terminal_quality_passed": not quality_errors,
        "terminal_quality_errors": quality_errors,
        "broad_scan_performed": False,
        "request_deleted_or_mutated": False,
        "infinite_loop_possible": False,
        "daemon_started": False,
        "watcher_started": False,
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
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_generated_outputs": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_payloads(
    response: ProcessorResponseForMac,
    *,
    generated_at: str | None = None,
    blockers: tuple[str, ...] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = generated_at or utc_now()
    status = _processor_status_from_response(response, blockers=blockers)
    response_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": RESPONSE_READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        **asdict(response),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    status_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "internal_statuses": INTERNAL_STATUSES,
        "request_types": REQUEST_TYPES,
        "processor_status": asdict(status),
        "latest_response_ref": RESPONSE_JSON_EXPORT_NAME,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    status_payload["machine_proof"] = _machine_proof(response, status)
    response_payload["machine_proof"] = json.loads(stable_json(status_payload["machine_proof"]))
    status_payload["machine_proof"]["content_hash"] = _content_hash(status_payload)
    response_payload["machine_proof"]["content_hash"] = _content_hash(response_payload)
    return response_payload, status_payload


def format_response_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# OpenClaw Chat Response for Mac",
            "",
            f"## {payload['operator_headline']}",
            "",
            str(payload["operator_message"]),
            "",
            "What happened:",
            *[f"- {item}" for item in payload["what_happened"]],
            "",
            f"Why: {payload['why_it_happened']}",
            "",
            f"How to fix: {payload['how_to_fix']}",
            "",
            f"Next safe move: {payload['next_safe_move']}",
            "",
        ]
    )


def format_status_markdown(payload: Mapping[str, Any]) -> str:
    status = payload["processor_status"]
    return "\n".join(
        [
            "# OpenClaw Chat Request Processor Status",
            "",
            f"Status: {status['terminal_result']}",
            "",
            status["operator_message"],
            "",
            "Generated readbacks:",
            *[f"- {item}" for item in status["generated_readbacks"]],
            "",
            "Boundary:",
            "- Bounded one-request processor only.",
            "- No daemon, watcher, worker execution, workflow execution, model/tool execution, or external action.",
            "",
            f"Next safe move: {status['next_safe_move']}",
            "",
        ]
    )


def write_exports(
    response_payload: dict[str, Any],
    status_payload: dict[str, Any],
    export_root: Path,
) -> tuple[Path, Path, Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    response_json = export_root / RESPONSE_JSON_EXPORT_NAME
    response_operator = export_root / RESPONSE_OPERATOR_EXPORT_NAME
    status_json = export_root / STATUS_JSON_EXPORT_NAME
    status_operator = export_root / STATUS_OPERATOR_EXPORT_NAME
    response_json.write_text(stable_json(response_payload), encoding="utf-8")
    response_operator.write_text(format_response_markdown(response_payload), encoding="utf-8")
    status_json.write_text(stable_json(status_payload), encoding="utf-8")
    status_operator.write_text(format_status_markdown(status_payload), encoding="utf-8")
    return response_json, response_operator, status_json, status_operator


def build_summary(
    response_payload: Mapping[str, Any],
    status_payload: Mapping[str, Any],
    paths: tuple[Path, Path, Path, Path],
) -> dict[str, Any]:
    response_json, response_operator, status_json, status_operator = paths
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "response_json_path": response_json.as_posix(),
        "response_operator_path": response_operator.as_posix(),
        "status_json_path": status_json.as_posix(),
        "status_operator_path": status_operator.as_posix(),
        "source_request_id": response_payload["source_request_id"],
        "source_request_filename": response_payload["source_request_filename"],
        "request_type": response_payload["request_type"],
        "internal_status": response_payload["internal_status"],
        "operator_headline": response_payload["operator_headline"],
        "operator_message": response_payload["operator_message"],
        "how_to_fix": response_payload["how_to_fix"],
        "cards_available": response_payload["cards_available"],
        "readback_files": response_payload["readback_files"],
        "terminal_quality_passed": status_payload["machine_proof"]["terminal_quality_passed"],
        "all_live_authority_flags_false": status_payload["machine_proof"]["all_live_authority_flags_false"],
        "external_action_performed": status_payload["machine_proof"]["external_action_performed"],
        "content_hash": response_payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process one OpenClaw/Mission Control request and write human readback.")
    parser.add_argument("--once", action="store_true", help="Process one request and exit. This is the default.")
    parser.add_argument("--file", dest="request_file", default=None, help="Specific supported request file to process.")
    parser.add_argument("--request-id", default=None, help="Specific request_id to find in the approved inbox.")
    parser.add_argument("--inbox", default=str(APPROVED_INBOX))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    request_file = Path(args.request_file) if args.request_file else None
    response = process_once(
        inbox=Path(args.inbox),
        request_file=request_file,
        request_id=args.request_id,
        export_root=export_root,
        generated_at=args.generated_at,
    )
    quality_errors = _terminal_quality_errors(response)
    response_payload, status_payload = build_payloads(
        response,
        generated_at=args.generated_at,
        blockers=quality_errors,
    )
    paths = write_exports(response_payload, status_payload, export_root)
    output = response_payload if args.format == "json" else build_summary(response_payload, status_payload, paths)
    print(stable_json(output), end="")
    return 1 if quality_errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
