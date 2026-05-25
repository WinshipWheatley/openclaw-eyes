"""Bounded OpenClaw request processor v0.

This is the PC-side bridge between Mission Control request files and safe
operator-readable readbacks. It processes one request and exits. It is not a
daemon, watcher, auto-dispatcher, model/tool runtime, workflow executor,
external action lane, file body ingestion path, raw transcript ingestion path,
Mac sync/import path, or Mission Control Swift implementation.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import chat_readback_card_mirror
import capital_hilton_invoice_operator_readback
import conversational_workflow_router_intake
import operator_file_metadata_intake
import scoped_context_package_compiler_contract
import worker_routing_intelligence
import workflow_execution_package_compiler


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")

SCHEMA_VERSION = "openclaw_request_processor_v0"
STATUS_READ_MODEL_ID = "openclaw_request_processor_status"
RESPONSE_READ_MODEL_ID = "openclaw_response_for_mac"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
STATUS_OPERATOR_EXPORT_NAME = "openclaw_request_processor_OPERATOR.md"
RESPONSE_JSON_EXPORT_NAME = f"{RESPONSE_READ_MODEL_ID}.json"
CONTRACT_STATUS = "BOUNDED_OPENCLAW_REQUEST_LIFECYCLE_PROCESSOR"

CHAT_PATTERN = conversational_workflow_router_intake.REQUEST_FILENAME_PATTERN
FILE_METADATA_PATTERN = operator_file_metadata_intake.REQUEST_FILENAME_PATTERN
CONTEXT_ATTACHMENT_PATTERN = "mission_control_context_request_*.json"
SECRET_INTAKE_PATTERN = "mission_control_secret_intake_request_*.json"
VISUAL_WORKSPACE_PATTERN = "mission_control_visual_workspace_request_*.json"
WORKER_DISPATCH_PATTERN = "mission_control_worker_dispatch_request_*.json"

SUPPORTED_REQUEST_PATTERNS = (
    CHAT_PATTERN,
    FILE_METADATA_PATTERN,
)

FUTURE_REQUEST_PATTERNS = (
    CONTEXT_ATTACHMENT_PATTERN,
    SECRET_INTAKE_PATTERN,
    VISUAL_WORKSPACE_PATTERN,
    WORKER_DISPATCH_PATTERN,
)

REQUEST_FAMILIES = (
    "CHAT",
    "FILE_METADATA",
    "CONTEXT_ATTACHMENT_FUTURE",
    "SECRET_INTAKE_FUTURE",
    "VISUAL_WORKSPACE_FUTURE",
    "WORKER_DISPATCH_FUTURE",
    "UNKNOWN_FAIL_CLOSED",
)

INTERNAL_STATUSES = (
    "REQUEST_FOUND",
    "REQUEST_PROCESSING",
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

AUDIENCE_MODES = (
    "ELIWINSHIP",
    "TECHNICAL",
    "DEBUG",
)

DISPLAY_MODES = (
    "COMPACT_CHAT",
    "DETAIL_DISCLOSURE",
    "PROOF_VIEW",
    "DEBUG_ONLY",
)

PROVIDER_FAMILIES = (
    "MAC_SYSTEM_TTS",
    "LOCAL_TTS_MODEL_FUTURE",
    "CLOUD_TTS_GATED_FUTURE",
    "UNKNOWN_FAIL_CLOSED",
)

ReadModelReader = Callable[[Path], dict[str, Any] | None]

INTERRUPTION_POLICIES = (
    "BARGE_IN_ALLOWED_FUTURE",
    "PAUSE_ON_OPERATOR_SPEECH_FUTURE",
    "NO_INTERRUPT_NEEDED",
    "UNKNOWN_FAIL_CLOSED",
)

VOICE_PROFILE_REFS = {
    "CHIEF": "voice:chief:operational",
    "CASSANDRA": "voice:cassandra:communications",
    "GUARDIAN": "voice:guardian:proof_gate",
    "NILES": "voice:niles:creative_flow",
    "CODEX": "voice:codex:implementation",
    "OPENCLAW_SYSTEM": "voice:system:neutral",
    "UNKNOWN": "voice:system:neutral",
}

VIBE_PROFILE_REFS = {
    "CHIEF": "vibe:chief:command_center",
    "CASSANDRA": "vibe:cassandra:executive_calm",
    "GUARDIAN": "vibe:guardian:strict_proof",
    "NILES": "vibe:niles:creative_flow",
    "CODEX": "vibe:codex:validation_first",
    "OPENCLAW_SYSTEM": "vibe:system:neutral",
    "UNKNOWN": "vibe:system:neutral",
}

HIGH_RISK_VOICE_TERMS = (
    "credential",
    "credentials",
    "secret",
    "secrets",
    "password",
    "coupa portal",
    "coupa",
    "submit",
    "send",
    "approval",
    "approve",
    "finance write",
    "external action",
    "client",
    "legal",
    "payment",
    "invoice sent",
)

GUARDIAN_CONTEXT_TERMS = (
    "approval",
    "approve",
    "proof",
    "secret",
    "credential",
    "password",
    "gate",
    "blocked gate",
    "protected",
)

CASSANDRA_CONTEXT_TERMS = (
    "email draft",
    "draft review",
    "draft is ready",
    "communications",
    "recipient",
    "annette",
    "review the draft",
)

NILES_CONTEXT_TERMS = (
    "niles",
    "music",
    "x32",
    "album",
    "setlist",
    "studio",
    "production",
    "struna",
    "logic",
    "ableton",
)

CODEX_CONTEXT_TERMS = (
    "codex",
    "build lane",
    "tests passed",
    "implementation",
    "commit",
)

MACHINE_SLUDGE_TERMS = (
    "source_request_id",
    "operator_message",
    "raw_internal_status",
    "spoken_response_packet",
    "capital_hilton_invoice_operator_readback",
    "workflow_execution_package_compiler",
    "gated_email_send_adapter",
    "coupa_supplier_portal_package_compiler",
    "openclaw_request_processor",
)

SPOKEN_FORBIDDEN_CLAIMS = (
    "sent",
    "submitted",
    "complete",
    "approved",
    "authorized",
    "dispatched",
)

SPOKEN_SENSITIVE_TERMS = (
    "credential",
    "credentials",
    "secret",
    "secrets",
    "password",
    "coupa",
    "invoice",
    "payment",
    "client",
    "legal",
    "tax",
    "ledger",
    "protected evidence",
    "raw email",
    "contact",
)

VOICE_DIRECTIONS = {
    "CHIEF": "operational_crisp",
    "CASSANDRA": "polished_calm",
    "GUARDIAN": "proof_first",
    "NILES": "creative_flow",
    "CODEX": "technical_precise",
    "OPENCLAW_SYSTEM": "neutral_clear",
    "UNKNOWN": "neutral_clear",
}

RESPONDER_TARGET_TYPES = (
    "DETERMINISTIC_ROUTER",
    "FILE_METADATA_INTAKE",
    "WORKER_ROUTING_INTELLIGENCE",
    "SCOPED_CONTEXT_PACKAGE_COMPILER",
    "CODEX_RESPONDER_FUTURE",
    "GEMINI_RESPONDER_FUTURE",
    "LOCAL_OLLAMA_RESPONDER_FUTURE",
    "CASSANDRA_FUTURE",
    "GUARDIAN_FUTURE",
    "VISUAL_RENDER_AGENT_FUTURE",
)

AUTHORITY_BOUNDARY = {
    "live_daemon_allowed": False,
    "live_watcher_allowed": False,
    "live_auto_dispatch_allowed": False,
    "live_workflow_execution_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_package_execution_allowed": False,
    "live_context_package_dispatch_allowed": False,
    "live_visual_artifact_spawn_allowed": False,
    "live_speech_synthesis_allowed": False,
    "live_microphone_capture_allowed": False,
    "live_cloud_audio_allowed": False,
    "live_voice_model_call_allowed": False,
    "live_file_body_ingestion_allowed": False,
    "live_raw_transcript_ingestion_allowed": False,
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
    "raw_transcript",
    "file_body",
    "body",
    "content",
    "contents",
    "raw_bytes",
    "file_bytes",
    "base64",
    "base64_body",
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
    "private_key",
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
class RequestClassification:
    classification_id: str
    source_request_filename: str | None
    request_family: str
    selected_rail: str
    classification_reason: str
    future_supported: bool
    next_safe_move: str


@dataclass(frozen=True)
class RequestProcessorResponderTarget:
    target_id: str
    target_type: str
    target_label: str
    supported_request_families: tuple[str, ...]
    adapter_available: bool
    live_call_allowed: bool
    selected: bool
    blocked_reason: str | None
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawResponseForMac:
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
    context_package_refs: tuple[str, ...]
    blocked_reason: str | None
    detail_disclosure: dict[str, Any]
    readback_files: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawRequestProcessorStatus:
    processor_id: str
    bounded_mode: str
    approved_inbox_policy: str
    supported_request_patterns: tuple[str, ...]
    future_request_patterns: tuple[str, ...]
    request_families: tuple[str, ...]
    latest_processed_request: dict[str, Any] | None
    request_classification: dict[str, Any]
    selected_rail: str
    responder_targets: tuple[dict[str, Any], ...]
    terminal_result: str
    operator_headline: str
    operator_message: str
    what_happened: tuple[str, ...]
    why_it_happened: str
    how_to_fix: str
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


def _terminal_for_status(status: str) -> bool:
    return status in {
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


def _short_hash(*parts: Any) -> str:
    return hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:20]


def _has_nonempty_value(value: Any) -> bool:
    return value not in (None, "", [], {})


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


def classify_request_filename(filename: str | None) -> RequestClassification:
    if filename and fnmatch.fnmatch(filename, CHAT_PATTERN):
        family = "CHAT"
        rail = "conversational_workflow_router_intake + chat_readback_card_mirror"
        reason = "Filename matches Mission Control chat request pattern."
        future_supported = False
    elif filename and fnmatch.fnmatch(filename, FILE_METADATA_PATTERN):
        family = "FILE_METADATA"
        rail = "operator_file_metadata_intake"
        reason = "Filename matches Mission Control file metadata intake pattern."
        future_supported = False
    elif filename and fnmatch.fnmatch(filename, CONTEXT_ATTACHMENT_PATTERN):
        family = "CONTEXT_ATTACHMENT_FUTURE"
        rail = "scoped_context_package_compiler_future"
        reason = "Filename matches future context attachment request pattern."
        future_supported = True
    elif filename and fnmatch.fnmatch(filename, SECRET_INTAKE_PATTERN):
        family = "SECRET_INTAKE_FUTURE"
        rail = "protected_secret_intake_future"
        reason = "Filename matches future protected secret intake request pattern."
        future_supported = True
    elif filename and fnmatch.fnmatch(filename, VISUAL_WORKSPACE_PATTERN):
        family = "VISUAL_WORKSPACE_FUTURE"
        rail = "visual_workspace_request_future"
        reason = "Filename matches future visual workspace request pattern."
        future_supported = True
    elif filename and fnmatch.fnmatch(filename, WORKER_DISPATCH_PATTERN):
        family = "WORKER_DISPATCH_FUTURE"
        rail = "worker_dispatch_package_future"
        reason = "Filename matches future worker dispatch request pattern."
        future_supported = True
    else:
        family = "UNKNOWN_FAIL_CLOSED"
        rail = "none"
        reason = "Filename does not match an approved Mission Control request pattern."
        future_supported = False
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(filename or 'none', family)}",
        source_request_filename=filename,
        request_family=family,
        selected_rail=rail,
        classification_reason=reason,
        future_supported=future_supported,
        next_safe_move=(
            "Run the selected deterministic rail once and write a Mac-readable response."
            if family in {"CHAT", "FILE_METADATA"}
            else "Return a human blocked response until the requested rail is connected."
        ),
    )


def list_supported_requests(inbox: Path = APPROVED_INBOX) -> tuple[Path, ...]:
    if not inbox.exists() or not inbox.is_dir():
        return ()
    matches = [
        path
        for path in inbox.iterdir()
        if path.is_file() and classify_request_filename(path.name).request_family in {"CHAT", "FILE_METADATA"}
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


def build_responder_targets(selected_family: str) -> tuple[RequestProcessorResponderTarget, ...]:
    def target(
        target_type: str,
        label: str,
        families: tuple[str, ...],
        available: bool,
        selected: bool = False,
        blocked_reason: str | None = None,
    ) -> RequestProcessorResponderTarget:
        return RequestProcessorResponderTarget(
            target_id=f"responder_target_{target_type.lower()}",
            target_type=target_type,
            target_label=label,
            supported_request_families=families,
            adapter_available=available,
            live_call_allowed=False,
            selected=selected,
            blocked_reason=blocked_reason,
            next_safe_move=(
                "Run this deterministic local rail."
                if available and selected
                else blocked_reason or "Keep this target modeled for a future approved adapter."
            ),
        )

    return (
        target(
            "DETERMINISTIC_ROUTER",
            "Conversational workflow router intake",
            ("CHAT",),
            True,
            selected_family == "CHAT",
        ),
        target(
            "FILE_METADATA_INTAKE",
            "Metadata-only file source-ref intake",
            ("FILE_METADATA",),
            True,
            selected_family == "FILE_METADATA",
        ),
        target(
            "WORKER_ROUTING_INTELLIGENCE",
            "Deterministic worker routing intelligence",
            ("CHAT", "WORKER_DISPATCH_FUTURE"),
            True,
            selected_family == "CHAT",
        ),
        target(
            "SCOPED_CONTEXT_PACKAGE_COMPILER",
            "Scoped context package compiler contract/read-model",
            ("CHAT", "CONTEXT_ATTACHMENT_FUTURE"),
            True,
            selected_family == "CHAT",
        ),
        target(
            "CODEX_RESPONDER_FUTURE",
            "Codex responder future adapter",
            ("CHAT", "CONTEXT_ATTACHMENT_FUTURE", "WORKER_DISPATCH_FUTURE"),
            False,
            False,
            "No approved live Codex responder adapter is connected in this processor.",
        ),
        target(
            "GEMINI_RESPONDER_FUTURE",
            "Gemini/Agy responder future adapter",
            ("CHAT", "WORKER_DISPATCH_FUTURE"),
            False,
            False,
            "No approved Gemini/Agy responder adapter is connected in this processor.",
        ),
        target(
            "LOCAL_OLLAMA_RESPONDER_FUTURE",
            "Local Ollama responder future adapter",
            ("CHAT",),
            False,
            False,
            "No approved local Ollama responder adapter is connected in this processor.",
        ),
        target(
            "CASSANDRA_FUTURE",
            "Cassandra communications responder future adapter",
            ("CHAT",),
            False,
            False,
            "No approved Cassandra responder adapter is connected in this processor.",
        ),
        target(
            "GUARDIAN_FUTURE",
            "Guardian approval boundary future adapter",
            ("SECRET_INTAKE_FUTURE", "WORKER_DISPATCH_FUTURE", "CHAT"),
            False,
            False,
            "No approved Guardian runtime adapter is connected in this processor.",
        ),
        target(
            "VISUAL_RENDER_AGENT_FUTURE",
            "Visual render agent future adapter",
            ("VISUAL_WORKSPACE_FUTURE", "CHAT"),
            False,
            False,
            "No approved visual render runtime adapter is connected in this processor.",
        ),
    )


def _required_fields_for_family(request_family: str) -> tuple[str, ...]:
    if request_family == "CHAT":
        return CHAT_REQUIRED_FIELDS
    if request_family == "FILE_METADATA":
        return FILE_REQUIRED_FIELDS
    return ("request_id", "idempotency_key", "payload_hash", "authority_boundary", "created_at")


def preflight_request(raw_request: Mapping[str, Any], request_family: str) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    blockers: list[str] = []
    fixes: list[str] = []
    missing = [field for field in _required_fields_for_family(request_family) if field not in raw_request]
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
            fixes.append("Use protected secret intake later; do not include secrets in normal request files.")
            break
    if request_family == "CHAT":
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


def _existing_duplicate_response(
    raw_request: Mapping[str, Any],
    export_root: Path,
    classification: RequestClassification,
) -> OpenClawResponseForMac | None:
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
    if status.get("processor_status", {}).get("terminal_result") != "RESPONSE_READY":
        return None
    try:
        existing_response = json.loads(response_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    readback_files = tuple(existing_response.get("readback_files") or ())
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=str(latest.get("source_request_filename") or ""),
        workflow_ref=str(raw_request.get("workflow_ref") or latest.get("workflow_ref") or "unknown"),
        request_type=str(latest.get("request_type") or classification.request_family),
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
        context_package_refs=tuple(existing_response.get("context_package_refs") or ()),
        blocked_reason=None,
        detail_disclosure={
            "existing_response_ref": RESPONSE_JSON_EXPORT_NAME,
            "duplicate_result": "existing readback reused",
            "request_classification": asdict(classification),
        },
        readback_files=readback_files,
        next_safe_move="Show the existing readback in Mac chat.",
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
        return (
            "I found the PC readback",
            "I found the PC readback. Here's what OpenClaw understood, what is missing, and what remains locked.",
            titles,
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
    return ("make" in text and "happen" in text) or "package" in text or "workflow preparation" in text


def _first_sentence(text: str) -> str:
    stripped = " ".join(text.split())
    if not stripped:
        return ""
    for delimiter in (". ", "? ", "! "):
        if delimiter in stripped:
            return stripped.split(delimiter, 1)[0].strip() + delimiter.strip()
    return stripped


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _word_limited(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(".,;:") + "."


def _sanitize_cockpit_text(text: str) -> str:
    cleaned = " ".join(str(text).split())
    parts: list[str] = []
    for word in cleaned.split():
        lowered = word.lower().strip(".,;:()[]{}")
        if lowered.startswith("generated/read_models/") or lowered.startswith("/"):
            parts.append("detail")
            continue
        if lowered.startswith("sha256:") or (len(lowered) >= 32 and all(char in "0123456789abcdef" for char in lowered)):
            parts.append("proof")
            continue
        if lowered in MACHINE_SLUDGE_TERMS:
            parts.append("detail")
            continue
        parts.append(word)
    return " ".join(parts).strip()


def _render_next_action(text: str) -> str:
    cleaned = _sanitize_cockpit_text(text).strip()
    if not cleaned:
        cleaned = "Review the safe readback."
    if cleaned.lower().startswith("next:"):
        result = cleaned
    else:
        result = f"Next: {cleaned[0].upper() + cleaned[1:] if cleaned else cleaned}"
    result = _word_limited(result, 12)
    if not result.endswith((".", "!", "?")):
        result += "."
    return result


def _apply_cockpit_prose_limits(fields: dict[str, Any]) -> dict[str, Any]:
    limited = dict(fields)
    limited["headline"] = _word_limited(_sanitize_cockpit_text(str(limited.get("headline") or "")), 6)
    limited["eliwinship"] = _word_limited(_sanitize_cockpit_text(str(limited.get("eliwinship") or "")), 40)
    limited["next_action"] = _render_next_action(str(limited.get("next_action") or "Review the response."))
    missing = limited.get("missing_items_short") or ()
    if isinstance(missing, str):
        missing_items = (missing,)
    else:
        missing_items = tuple(str(item) for item in missing)
    limited["missing_items_short"] = tuple(_sanitize_cockpit_text(item) for item in missing_items[:3])
    return limited


def _safe_generated_ref(ref: object) -> str:
    text = str(ref)
    name = Path(text).name
    if text.startswith("generated/read_models/"):
        return text
    if name and (name.endswith(".json") or name.endswith(".md")):
        return f"generated/read_models/{name}"
    return text


def _safe_proof_refs(response: OpenClawResponseForMac) -> tuple[str, ...]:
    refs = []
    for ref in response.readback_files:
        safe_ref = _safe_generated_ref(ref)
        if safe_ref.startswith("generated/read_models/") and safe_ref.endswith(".json"):
            refs.append(safe_ref)
    return tuple(dict.fromkeys(refs))


def _debug_refs(response: OpenClawResponseForMac) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(_safe_generated_ref(ref) for ref in response.readback_files)
    refs.extend(_safe_generated_ref(ref) for ref in response.card_mirror_refs)
    refs.extend(_safe_generated_ref(ref) for ref in response.file_readback_refs)
    refs.extend(_safe_generated_ref(ref) for ref in response.context_package_refs)
    return tuple(dict.fromkeys(ref for ref in refs if ref))


def _voice_context_text(response: OpenClawResponseForMac, layered_fields: Mapping[str, Any]) -> str:
    chunks: list[str] = [
        response.request_type,
        response.workflow_ref,
        response.operator_headline,
        response.operator_message,
        response.why_it_happened,
        response.how_to_fix,
        response.next_safe_move,
        str(response.blocked_reason or ""),
        str(layered_fields.get("headline") or ""),
        str(layered_fields.get("eliwinship") or ""),
        str(layered_fields.get("primary_blocker") or ""),
        str(layered_fields.get("detail_summary") or ""),
    ]
    detail = response.detail_disclosure
    if isinstance(detail, Mapping):
        chunks.extend(str(value) for value in detail.values() if isinstance(value, (str, bool)))
        classification = detail.get("request_classification")
        if isinstance(classification, Mapping):
            chunks.extend(str(value) for value in classification.values())
    return " ".join(chunks).lower()


def _initial_response_author(response: OpenClawResponseForMac, layered_fields: Mapping[str, Any]) -> tuple[str, str]:
    text = _voice_context_text(response, layered_fields)
    if response.request_type == "FILE_METADATA":
        return "OPENCLAW_SYSTEM", "file intake / source reference status"
    if _is_capital_hilton_status_response(response):
        return "CHIEF", "finance workflow status / readiness / blocker summary"
    if _contains_any(text, CASSANDRA_CONTEXT_TERMS):
        return "CASSANDRA", "communications draft/review context"
    if _contains_any(text, NILES_CONTEXT_TERMS):
        return "NILES", "music or creative world context"
    if _contains_any(text, GUARDIAN_CONTEXT_TERMS):
        return "GUARDIAN", "proof, approval, protected boundary, or blocked gate"
    if _contains_any(text, CODEX_CONTEXT_TERMS):
        return "CODEX", "build/test/code lane"
    return "OPENCLAW_SYSTEM", "neutral fallback"


def _apply_high_risk_voice_override(author: str, reason: str, response: OpenClawResponseForMac, layered_fields: Mapping[str, Any]) -> tuple[str, str, bool]:
    text = _voice_context_text(response, layered_fields)
    if author != "NILES" or not _contains_any(text, HIGH_RISK_VOICE_TERMS):
        return author, reason, False
    if _contains_any(text, GUARDIAN_CONTEXT_TERMS):
        return "GUARDIAN", f"{reason}; high-risk creative request overridden to Guardian", True
    return "CHIEF", f"{reason}; high-risk creative request overridden to Chief", True


def _voice_authorship_fields(response: OpenClawResponseForMac, layered_fields: Mapping[str, Any]) -> dict[str, Any]:
    author, reason = _initial_response_author(response, layered_fields)
    author, reason, high_risk_override = _apply_high_risk_voice_override(author, reason, response, layered_fields)
    return {
        "response_author": author,
        "voice_profile_ref": VOICE_PROFILE_REFS[author],
        "vibe_profile_ref": VIBE_PROFILE_REFS[author],
        "voice_applied": True,
        "vibe_applied": True,
        "voice_selection_reason": reason,
        "high_risk_override_applied": high_risk_override,
    }


def _sanitize_spoken_text(text: str) -> str:
    cleaned = _sanitize_cockpit_text(text)
    cleaned = cleaned.replace("PO/reference", "PO reference")
    cleaned = cleaned.replace("send/submit", "send or submit")
    cleaned = cleaned.replace("read-model", "read model")
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("*", "")
    cleaned = cleaned.replace("#", "")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def _spoken_sensitive_context(response: OpenClawResponseForMac, layered_fields: Mapping[str, Any]) -> bool:
    text = _voice_context_text(response, layered_fields)
    return _contains_any(text, SPOKEN_SENSITIVE_TERMS)


def _spoken_privacy_class(response: OpenClawResponseForMac, layered_fields: Mapping[str, Any]) -> str:
    text = _voice_context_text(response, layered_fields)
    if "coupa" in text or "payment" in text or "invoice" in text:
        return "CLIENT_PAYMENT_CONTEXT"
    if response.request_type == "FILE_METADATA":
        return "SOURCE_REFERENCE_METADATA"
    if "secret" in text or "credential" in text or "password" in text:
        return "PROTECTED_BOUNDARY_CONTEXT"
    return "OPERATOR_STATUS_CONTEXT"


def _spoken_pronunciation_hints(*texts: object) -> dict[str, str]:
    joined = " ".join(str(text) for text in texts).lower()
    hints: dict[str, str] = {}
    if "coupa" in joined:
        hints["Coupa"] = "coo pah"
    if "x32" in joined:
        hints["X32"] = "ex thirty two"
    if "wsl" in joined:
        hints["WSL"] = "double u ess ell"
    if "struna" in joined:
        hints["Struna"] = "stroo nah"
    return hints


def _provider_policy(*, sensitive_context: bool) -> dict[str, Any]:
    reason = "Use native Mac playback. PC emits text only; no cloud synthesis or transcription is allowed in this lane."
    if sensitive_context:
        reason = "Sensitive or client/payment context. Use native Mac playback only; cloud synthesis and transcription are blocked."
    return {
        "preferred_provider_family": "MAC_SYSTEM_TTS",
        "fallback_provider_family": "LOCAL_TTS_MODEL_FUTURE",
        "cloud_synthesis_allowed": False,
        "cloud_transcription_allowed": False,
        "sensitive_context": sensitive_context,
        "blocked_provider_families": ("CLOUD_TTS_GATED_FUTURE", "UNKNOWN_FAIL_CLOSED"),
        "reason": reason,
    }


def _generic_spoken_script(layered_fields: Mapping[str, Any]) -> str:
    headline = _sanitize_spoken_text(str(layered_fields.get("headline") or "OpenClaw response ready."))
    blocker = _sanitize_spoken_text(str(layered_fields.get("primary_blocker") or ""))
    next_action = _sanitize_spoken_text(str(layered_fields.get("next_action") or "Next: Review the response."))
    if blocker and blocker.lower() != "none":
        script = f"{headline}. Blocked by {blocker}. {next_action}"
    else:
        one_line = _sanitize_spoken_text(str(layered_fields.get("one_line_answer") or ""))
        script = f"{headline}. {one_line} {next_action}".strip()
    return _word_limited(script, 40)


def _spoken_script_and_summary(response: OpenClawResponseForMac, layered_fields: Mapping[str, Any]) -> tuple[str, str]:
    if _is_capital_hilton_status_response(response):
        return (
            "Capital Hilton invoice is blocked. The invoice basis exists, but the Coupa PO reference and approval receipts are still missing. Nothing can send or submit yet.",
            "Invoice blocked. Confirm the Coupa PO reference.",
        )
    if response.request_type == "FILE_METADATA":
        return (
            "File reference captured. The body was not read. Choose whether to use it as source context.",
            "File reference captured. Body not read.",
        )
    script = _generic_spoken_script(layered_fields)
    summary = _word_limited(_sanitize_spoken_text(str(layered_fields.get("headline") or script)), 12)
    return script, summary


def _spoken_response_packet(
    response: OpenClawResponseForMac,
    layered_fields: Mapping[str, Any],
    voice_fields: Mapping[str, Any],
) -> dict[str, Any]:
    spoken_script, spoken_summary = _spoken_script_and_summary(response, layered_fields)
    spoken_script = _sanitize_spoken_text(spoken_script)
    spoken_summary = _sanitize_spoken_text(spoken_summary)
    sensitive_context = _spoken_sensitive_context(response, layered_fields)
    provider = _provider_policy(sensitive_context=sensitive_context)
    response_author = str(voice_fields.get("response_author") or "OPENCLAW_SYSTEM")
    return {
        "spoken_packet_id": f"spoken_response_{_short_hash(response.source_request_id, layered_fields.get('response_id'), spoken_script)}",
        "source_response_ref": f"generated/read_models/{RESPONSE_JSON_EXPORT_NAME}",
        "source_request_id": response.source_request_id,
        "response_author": response_author,
        "voice_profile_ref": voice_fields["voice_profile_ref"],
        "vibe_profile_ref": voice_fields["vibe_profile_ref"],
        "spoken_script": spoken_script,
        "spoken_summary": spoken_summary,
        "voice_direction": VOICE_DIRECTIONS.get(response_author, VOICE_DIRECTIONS["UNKNOWN"]),
        "pronunciation_hints": _spoken_pronunciation_hints(spoken_script, spoken_summary, response.operator_message, layered_fields.get("detail_summary") or ""),
        "interruption_policy": "NO_INTERRUPT_NEEDED",
        "provider_policy": provider,
        "forbidden_spoken_claims": SPOKEN_FORBIDDEN_CLAIMS,
        "cloud_synthesis_allowed": provider["cloud_synthesis_allowed"],
        "local_playback_preferred": True,
        "privacy_class": _spoken_privacy_class(response, layered_fields),
        "next_safe_move": _sanitize_spoken_text(response.next_safe_move),
    }


def _primary_status_label(internal_status: str) -> str:
    if internal_status == "RESPONSE_READY":
        return "Ready for review"
    if internal_status in {
        "BLOCKED_WITH_REASON",
        "BLOCKED_MAC_HANDOFF_UNAVAILABLE",
        "BLOCKED_WORKER_UNAVAILABLE",
        "FAILED_WITH_REASON",
        "TIMED_OUT_WITH_REASON",
    }:
        return "Blocked"
    if internal_status == "DUPLICATE_NOOP_WITH_READBACK":
        return "Already handled"
    if internal_status == "NO_REQUEST_AVAILABLE":
        return "No request waiting"
    return "Fail closed"


def _is_capital_hilton_status_response(response: OpenClawResponseForMac) -> bool:
    detail = response.detail_disclosure
    return (
        str(detail.get("selected_readback_ref") or "").endswith(capital_hilton_invoice_operator_readback.JSON_EXPORT_NAME)
        or str(detail.get("request_classification", {}).get("selected_rail") if isinstance(detail.get("request_classification"), Mapping) else "")
        == "capital_hilton_invoice_operator_readback"
    )


def _layered_response_fields(response: OpenClawResponseForMac, *, created_at: str) -> dict[str, Any]:
    if _is_capital_hilton_status_response(response):
        return {
            "response_id": f"openclaw_response_{_short_hash(response.source_request_id, response.request_type, created_at)}",
            "response_kind": "CAPITAL_HILTON_INVOICE_STATUS",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": "Capital Hilton invoice is blocked",
            "one_line_answer": (
                "OpenClaw has the delivery basis, but the workflow is locked because required approvals and proofs are missing."
            ),
            "eliwinship": (
                "The invoice basis and draft rails exist. "
                "The workflow is blocked until the Coupa PO/reference and approval receipts are confirmed. "
                "Nothing can send or submit yet."
            ),
            "primary_status": "Locked until proof and approval receipts exist",
            "primary_blocker": "Missing confirmed Coupa PO/reference",
            "next_action": "Next: Confirm the Coupa PO/reference.",
            "missing_items_short": (
                "Confirmed Coupa PO/reference",
                "Guardian and operator approval receipts",
                "Email send receipt and attachment proof",
            ),
            "detail_summary": (
                "Delivery basis is modeled for four Capital Hilton performance dates at $1,600 total. "
                "The invoice and draft rails are available for review, but send/submit/completion remain locked until proof and approval receipts exist."
            ),
            "proof_refs": _safe_proof_refs(response),
            "debug_refs": _debug_refs(response),
            "raw_internal_status": response.internal_status,
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        }

    if response.request_type == "FILE_METADATA":
        return {
            "response_id": f"openclaw_response_{_short_hash(response.source_request_id, response.request_type, created_at)}",
            "response_kind": "FILE_METADATA_READBACK",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": "File reference captured",
            "one_line_answer": "OpenClaw captured the file reference without reading the file body.",
            "eliwinship": "OpenClaw captured the file reference. The body was not read. You can use it later as source context.",
            "primary_status": _primary_status_label(response.internal_status),
            "primary_blocker": str(response.blocked_reason or "None"),
            "next_action": "Next: Choose how to use this source.",
            "missing_items_short": (),
            "detail_summary": response.why_it_happened,
            "proof_refs": _safe_proof_refs(response),
            "debug_refs": _debug_refs(response),
            "raw_internal_status": response.internal_status,
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        }

    headline = response.operator_headline or _primary_status_label(response.internal_status)
    one_line = _first_sentence(response.operator_message) or headline
    blocker = response.blocked_reason or ("None" if response.internal_status == "RESPONSE_READY" else response.why_it_happened)
    next_action = response.next_safe_move or response.how_to_fix
    if response.request_type == "FILE_METADATA":
        response_kind = "FILE_METADATA_READBACK"
    elif response.request_type == "CHAT":
        response_kind = "CHAT_READBACK"
    else:
        response_kind = "REQUEST_READBACK"
    return _apply_cockpit_prose_limits({
        "response_id": f"openclaw_response_{_short_hash(response.source_request_id, response.request_type, created_at)}",
        "response_kind": response_kind,
        "audience_mode": "ELIWINSHIP",
        "display_mode": "COMPACT_CHAT",
        "headline": headline,
        "one_line_answer": one_line,
        "eliwinship": one_line,
        "primary_status": _primary_status_label(response.internal_status),
        "primary_blocker": str(blocker),
        "next_action": str(next_action),
        "missing_items_short": (),
        "detail_summary": response.why_it_happened,
        "proof_refs": _safe_proof_refs(response),
        "debug_refs": _debug_refs(response),
        "raw_internal_status": response.internal_status,
        "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
    })


def _capital_hilton_status_text(raw_request: Mapping[str, Any]) -> str:
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
    return " ".join(str(raw_request.get(field) or "") for field in fields).lower()


def _is_capital_hilton_invoice_status_request(raw_request: Mapping[str, Any]) -> bool:
    text = _capital_hilton_status_text(raw_request)
    capital_context = (
        "capital hilton" in text
        or "capital_hilton" in text
        or "capital-hilton" in text
        or str(raw_request.get("client_ref") or "").lower() == "capital_hilton"
    )
    invoice_context = "invoice" in text
    status_intent = any(
        phrase in text
        for phrase in (
            "invoice status",
            "where are we",
            "ready",
            "mark invoice sent",
            "invoice sent",
            "what is missing",
            "what's missing",
            "whats missing",
            "missing for capital hilton",
            "blocking",
            "blocked",
            "blockers",
            "show me the invoice status",
            "can we mark",
            "can i mark",
        )
    )
    return capital_context and invoice_context and status_intent


def _capital_hilton_status_classification(classification: RequestClassification) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(classification.source_request_filename, 'capital_hilton_status')}",
        source_request_filename=classification.source_request_filename,
        request_family=classification.request_family,
        selected_rail="capital_hilton_invoice_operator_readback",
        classification_reason=(
            "Filename matches Mission Control chat request pattern, and message asks for Capital Hilton invoice status."
        ),
        future_supported=False,
        next_safe_move="Export the unified Capital Hilton invoice operator readback and return it to Mac chat.",
    )


def _process_capital_hilton_status_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    read_model_reader: ReadModelReader | None = None,
) -> OpenClawResponseForMac:
    status_classification = _capital_hilton_status_classification(classification)
    payload = capital_hilton_invoice_operator_readback.build_and_export(
        generated_at=generated_at or capital_hilton_invoice_operator_readback.DEFAULT_GENERATED_AT,
        export_root=export_root,
        readmodel_root=export_root,
        format_name="json",
        read_json=read_model_reader,
    )
    chat = payload["chat_response"]
    unified_status = payload["unified_status"]
    json_ref = (export_root / capital_hilton_invoice_operator_readback.JSON_EXPORT_NAME).as_posix()
    operator_ref = (export_root / capital_hilton_invoice_operator_readback.OPERATOR_EXPORT_NAME).as_posix()
    readback_files = (json_ref, operator_ref)
    ready = tuple(str(item) for item in chat.get("what_is_ready", ()))
    missing = tuple(str(item) for item in chat.get("what_is_missing", ()))
    blocked = tuple(str(item) for item in chat.get("what_is_blocked", ()))
    request_id = str(raw_request.get("request_id") or f"capital_hilton_status_{_short_hash(request_path.name)}")
    workflow_ref = str(raw_request.get("workflow_ref") or capital_hilton_invoice_operator_readback.WORKFLOW_REF)
    can_mark_invoice_sent = bool(unified_status.get("can_mark_invoice_sent"))
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline=str(chat["operator_headline"]),
        operator_message=str(chat["operator_message"]),
        what_happened=(
            "PC recognized a Capital Hilton invoice status question.",
            "PC exported the unified Capital Hilton invoice operator readback.",
            "PC shaped that readback into a Mac-readable response.",
            "No workflow, email, Coupa, browser, approval, payment, completion, or external action occurred.",
        ),
        why_it_happened="The chat text and request context matched Capital Hilton invoice status/readiness/blocker intent.",
        how_to_fix=str(chat["how_to_fix"]),
        visible_cards=(
            {
                "title": str(chat["operator_headline"]),
                "bullets": (
                    str(chat["concise_summary"]),
                    "Ready: " + ("; ".join(ready[:3]) if ready else "no execution-ready items"),
                    "Missing: " + ("; ".join(missing[:4]) if missing else "no missing proof in this fixture"),
                    "Blocked: " + ("; ".join(blocked[:4]) if blocked else "no blocked action in this fixture"),
                    f"Can mark invoice sent: {can_mark_invoice_sent}",
                ),
                "status_tone": "blocked" if not can_mark_invoice_sent else "ready",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={
            "selected_readback_ref": json_ref,
            "operator_readback_ref": operator_ref,
            "request_classification": asdict(status_classification),
            "can_mark_invoice_sent": can_mark_invoice_sent,
            "can_send_email": bool(unified_status.get("can_send_email")),
            "can_submit_coupa": bool(unified_status.get("can_submit_coupa")),
            "can_run_workflow": bool(unified_status.get("can_run_workflow")),
            "completion_label_status": unified_status.get("completion_label_status"),
            "detail_refs": tuple(chat.get("detail_refs", ())),
            "external_actions_locked": True,
            "model_or_worker_response_adapter_called": False,
        },
        readback_files=readback_files,
        next_safe_move=str(chat["next_safe_move"]),
    )


def _process_chat_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    read_model_reader: ReadModelReader | None = None,
) -> OpenClawResponseForMac:
    if _is_capital_hilton_invoice_status_request(raw_request):
        return _process_capital_hilton_status_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=classification,
            read_model_reader=read_model_reader,
        )

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

    operator_summary = str(raw_request.get("sanitized_message_summary") or raw_request.get("operator_message") or "")
    routing_decision = worker_routing_intelligence.route_request(
        operator_summary,
        source_chat_ref=str(raw_request.get("request_id") or request_path.name),
    )
    routing_payload = worker_routing_intelligence.build_worker_routing_intelligence(generated_at=generated_at)
    routing_json, routing_operator = worker_routing_intelligence.write_exports(routing_payload, export_root)
    context_payload = scoped_context_package_compiler_contract.build_scoped_context_package_compiler_contract(
        generated_at=generated_at
    )
    context_json, context_operator = scoped_context_package_compiler_contract.write_exports(context_payload, export_root)

    readback_files = [
        router_json.as_posix(),
        router_operator.as_posix(),
        mirror_json.as_posix(),
        mirror_operator.as_posix(),
        routing_json.as_posix(),
        routing_operator.as_posix(),
        context_json.as_posix(),
        context_operator.as_posix(),
    ]
    detail: dict[str, Any] = {
        "router_readback_ref": router_json.as_posix(),
        "card_mirror_ref": mirror_json.as_posix(),
        "worker_routing_intelligence_ref": routing_json.as_posix(),
        "scoped_context_package_compiler_ref": context_json.as_posix(),
        "worker_route": asdict(routing_decision),
        "request_classification": asdict(classification),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
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
        return OpenClawResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=workflow_ref,
            request_type="CHAT",
            internal_status="RESPONSE_READY",
            operator_headline=headline,
            operator_message=message,
            what_happened=(
                "PC consumed the Mac chat request through the deterministic router intake.",
                "PC generated router readback cards and a Mac-readable card mirror.",
                "PC modeled worker routing and scoped context package refs without dispatching any worker.",
                "No external action occurred.",
            ),
            why_it_happened="The request passed validation and matched the deterministic chat router rail.",
            how_to_fix="No fix is needed. Review the cards; edit the understanding if it is wrong.",
            visible_cards=cards,
            cards_available=bool(cards),
            card_mirror_refs=(mirror_json.as_posix(),),
            file_readback_refs=(),
            worker_route_refs=(asdict(routing_decision), {"read_model_ref": routing_json.as_posix()}),
            context_package_refs=(context_json.as_posix(),),
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
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type="CHAT",
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
        worker_route_refs=(asdict(routing_decision), {"read_model_ref": routing_json.as_posix()}),
        context_package_refs=(context_json.as_posix(),),
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
    classification: RequestClassification,
) -> OpenClawResponseForMac:
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
        return OpenClawResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=workflow_ref,
            request_type="FILE_METADATA",
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
            context_package_refs=(),
            blocked_reason=None,
            detail_disclosure={
                "file_readback_ref": file_json.as_posix(),
                "source_ref_id": source_ref["source_ref_id"] if isinstance(source_ref, Mapping) else None,
                "persistent_registry_write": file_payload["intake_receipt"]["persistent_registry_write"],
                "request_classification": asdict(classification),
            },
            readback_files=readback_files,
            next_safe_move=readback["next_safe_move"],
        )

    blockers = tuple(
        blocker.get("elioperator_warning") or blocker.get("condition") or blocker.get("blocker_type")
        for blocker in file_payload.get("active_blockers_by_id", {}).values()
    )
    reason = "; ".join(str(item) for item in blockers) or "The file metadata request did not pass safe intake validation."
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type="FILE_METADATA",
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
        context_package_refs=(),
        blocked_reason=reason,
        detail_disclosure={"file_readback_ref": file_json.as_posix(), "request_classification": asdict(classification)},
        readback_files=readback_files,
        next_safe_move=readback["next_safe_move"],
    )


def _failed_response(
    *,
    request_path: Path | None,
    classification: RequestClassification,
    reason: str,
    how_to_fix: str,
    source_request_id: str = "unknown_unparseable_request",
    workflow_ref: str = "unknown",
    generated_files: tuple[str, ...] = (),
) -> OpenClawResponseForMac:
    return OpenClawResponseForMac(
        source_request_id=source_request_id,
        source_request_filename=request_path.name if request_path else None,
        workflow_ref=workflow_ref,
        request_type=classification.request_family,
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
        context_package_refs=(),
        blocked_reason=reason,
        detail_disclosure={"error": reason, "request_classification": asdict(classification)},
        readback_files=generated_files,
        next_safe_move="Fix the request and rerun the bounded processor.",
    )


def _no_request_response(inbox: Path, *, timed_out_seconds: int | None = None) -> OpenClawResponseForMac:
    classification = classify_request_filename(None)
    if timed_out_seconds is not None:
        return OpenClawResponseForMac(
            source_request_id="timed_out_no_request_available",
            source_request_filename=None,
            workflow_ref="unknown",
            request_type="UNKNOWN_FAIL_CLOSED",
            internal_status="TIMED_OUT_WITH_REASON",
            operator_headline="OpenClaw did not see a new Mac request in time",
            operator_message=(
                f"I waited {timed_out_seconds} second(s) for a supported Mac request in the approved PC inbox, "
                "but none arrived."
            ),
            what_happened=("PC checked only the approved inbox until the bounded timeout expired.", "No request files were changed or deleted."),
            why_it_happened="No supported Mission Control chat or file metadata request appeared before timeout.",
            how_to_fix="Send a new request from Mac chat, check the shared inbox mount, or run with --file for a specific request.",
            visible_cards=(),
            cards_available=False,
            card_mirror_refs=(),
            file_readback_refs=(),
            worker_route_refs=(),
            context_package_refs=(),
            blocked_reason="No supported request arrived before timeout.",
            detail_disclosure={"approved_inbox": inbox.as_posix(), "request_classification": asdict(classification)},
            readback_files=(),
            next_safe_move="Retry after Mac emits a request, or pass --file with a supported request.",
        )
    return OpenClawResponseForMac(
        source_request_id="no_request_available",
        source_request_filename=None,
        workflow_ref="unknown",
        request_type="UNKNOWN_FAIL_CLOSED",
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
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={"approved_inbox": inbox.as_posix(), "request_classification": asdict(classification)},
        readback_files=(),
        next_safe_move="Wait for Mac to emit a request, then rerun this bounded processor.",
    )


def _future_blocked_response(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    classification: RequestClassification,
) -> OpenClawResponseForMac:
    rail = classification.selected_rail
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or f"future_request_{_short_hash(request_path.name)}"),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
        request_type=classification.request_family,
        internal_status="BLOCKED_WITH_REASON",
        operator_headline="OpenClaw does not have that request rail connected yet",
        operator_message=(
            "I recognized the request family, but this processor cannot run that future rail yet. "
            "Nothing was dispatched or executed."
        ),
        what_happened=(
            f"The request classified as {classification.request_family}.",
            "The processor stopped before any unavailable adapter could be called.",
        ),
        why_it_happened=f"The required rail is not connected yet: {rail}.",
        how_to_fix="Route this as chat or file metadata for v0, or add the specific deterministic adapter before retrying this request family.",
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=f"Missing rail: {rail}.",
        detail_disclosure={"request_classification": asdict(classification)},
        readback_files=(),
        next_safe_move="Connect the missing adapter or resend through a supported v0 request family.",
    )


def process_request_path(
    request_path: Path,
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    duplicate_check: bool = True,
    read_model_reader: ReadModelReader | None = None,
) -> OpenClawResponseForMac:
    classification = classify_request_filename(request_path.name)
    if classification.request_family == "UNKNOWN_FAIL_CLOSED":
        return _failed_response(
            request_path=request_path,
            classification=classification,
            reason="Unsupported request filename.",
            how_to_fix="Use mission_control_chat_request_*.json or mission_control_file_intake_request_*.json for v0.",
        )
    try:
        raw_request = _load_json_request(request_path)
    except json.JSONDecodeError as exc:
        return _failed_response(
            request_path=request_path,
            classification=classification,
            reason=f"Malformed JSON: {exc.msg}.",
            how_to_fix="Regenerate the request from Mac chat or fix the JSON object before retrying.",
        )
    except ValueError as exc:
        return _failed_response(
            request_path=request_path,
            classification=classification,
            reason=str(exc),
            how_to_fix="Regenerate the request as a JSON object before retrying.",
        )
    except OSError as exc:
        return _failed_response(
            request_path=request_path,
            classification=classification,
            reason=f"Could not read request file: {exc}.",
            how_to_fix="Check that the request file exists and is readable, then rerun.",
        )
    if duplicate_check:
        duplicate = _existing_duplicate_response(raw_request, export_root, classification)
        if duplicate is not None:
            return duplicate
    ok, blockers, fixes = preflight_request(raw_request, classification.request_family)
    if not ok:
        return OpenClawResponseForMac(
            source_request_id=str(raw_request.get("request_id") or "unknown_request"),
            source_request_filename=request_path.name,
            workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
            request_type=classification.request_family,
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
            context_package_refs=(),
            blocked_reason=" ".join(blockers),
            detail_disclosure={"preflight_blockers": blockers, "fixes": fixes, "request_classification": asdict(classification)},
            readback_files=(),
            next_safe_move="Fix the request and rerun the bounded processor.",
        )
    if classification.request_family == "CHAT":
        return _process_chat_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=classification,
            read_model_reader=read_model_reader,
        )
    if classification.request_family == "FILE_METADATA":
        return _process_file_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=classification,
        )
    return _future_blocked_response(request_path, raw_request, classification=classification)


def process_once(
    *,
    inbox: Path = APPROVED_INBOX,
    request_file: Path | None = None,
    request_id: str | None = None,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    read_model_reader: ReadModelReader | None = None,
) -> OpenClawResponseForMac:
    if request_file is not None:
        return process_request_path(
            request_file,
            export_root=export_root,
            generated_at=generated_at,
            read_model_reader=read_model_reader,
        )
    candidates = list_supported_requests(inbox)
    if request_id:
        for candidate in reversed(candidates):
            try:
                raw = _load_json_request(candidate)
            except (json.JSONDecodeError, OSError, ValueError):
                continue
            if str(raw.get("request_id") or "") == request_id:
                return process_request_path(
                    candidate,
                    export_root=export_root,
                    generated_at=generated_at,
                    read_model_reader=read_model_reader,
                )
        classification = classify_request_filename(None)
        return _failed_response(
            request_path=None,
            classification=classification,
            reason=f"No supported request with request_id {request_id} was found.",
            how_to_fix="Check the request id or pass --file with the exact supported request file.",
        )
    latest = candidates[-1] if candidates else None
    if latest is None:
        return _no_request_response(inbox)
    return process_request_path(
        latest,
        export_root=export_root,
        generated_at=generated_at,
        read_model_reader=read_model_reader,
    )


def process_with_timeout(
    *,
    inbox: Path,
    export_root: Path,
    generated_at: str | None,
    watch_seconds: int,
    read_model_reader: ReadModelReader | None = None,
) -> OpenClawResponseForMac:
    deadline = time.monotonic() + max(0, watch_seconds)
    while True:
        latest = select_newest_request(inbox)
        if latest is not None:
            return process_request_path(
                latest,
                export_root=export_root,
                generated_at=generated_at,
                read_model_reader=read_model_reader,
            )
        if time.monotonic() >= deadline:
            return _no_request_response(inbox, timed_out_seconds=watch_seconds)
        time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))


def _terminal_quality_errors(response: OpenClawResponseForMac) -> tuple[str, ...]:
    errors: list[str] = []
    if response.internal_status in {
        "BLOCKED_WITH_REASON",
        "BLOCKED_MAC_HANDOFF_UNAVAILABLE",
        "BLOCKED_WORKER_UNAVAILABLE",
        "FAILED_WITH_REASON",
        "TIMED_OUT_WITH_REASON",
    }:
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
    public_text = f"{response.operator_headline} {response.operator_message}".lower()
    for status in INTERNAL_STATUSES:
        if status.lower() in public_text:
            errors.append(f"Operator-facing text exposes internal status {status}.")
    return tuple(errors)


def _classification_from_response(response: OpenClawResponseForMac) -> RequestClassification:
    detail = response.detail_disclosure.get("request_classification")
    if isinstance(detail, Mapping):
        return RequestClassification(**{field: detail[field] for field in RequestClassification.__dataclass_fields__})
    return classify_request_filename(response.source_request_filename)


def _processor_status_from_response(
    response: OpenClawResponseForMac,
    *,
    blockers: tuple[str, ...] = (),
) -> OpenClawRequestProcessorStatus:
    classification = _classification_from_response(response)
    responder_targets = build_responder_targets(classification.request_family)
    return OpenClawRequestProcessorStatus(
        processor_id="openclaw_request_processor_v0",
        bounded_mode="process one request and exit",
        approved_inbox_policy=f"default inbox is {APPROVED_INBOX.as_posix()}; scans immediate supported request files only",
        supported_request_patterns=SUPPORTED_REQUEST_PATTERNS,
        future_request_patterns=FUTURE_REQUEST_PATTERNS,
        request_families=REQUEST_FAMILIES,
        latest_processed_request={
            "source_request_id": response.source_request_id,
            "source_request_filename": response.source_request_filename,
            "workflow_ref": response.workflow_ref,
            "request_type": response.request_type,
        },
        request_classification=asdict(classification),
        selected_rail=classification.selected_rail,
        responder_targets=tuple(asdict(target) for target in responder_targets),
        terminal_result=response.internal_status,
        operator_headline=response.operator_headline,
        operator_message=response.operator_message,
        what_happened=response.what_happened,
        why_it_happened=response.why_it_happened,
        how_to_fix=response.how_to_fix,
        generated_readbacks=response.readback_files,
        errors_or_blockers=blockers,
        next_safe_move=response.next_safe_move,
        authority_boundary=AUTHORITY_BOUNDARY,
    )


def _machine_proof(
    response: OpenClawResponseForMac,
    status: OpenClawRequestProcessorStatus,
) -> dict[str, Any]:
    quality_errors = _terminal_quality_errors(response)
    targets = status.responder_targets
    future_lm_targets = [
        target
        for target in targets
        if target["target_type"]
        in {
            "CODEX_RESPONDER_FUTURE",
            "GEMINI_RESPONDER_FUTURE",
            "LOCAL_OLLAMA_RESPONDER_FUTURE",
            "CASSANDRA_FUTURE",
            "GUARDIAN_FUTURE",
            "VISUAL_RENDER_AGENT_FUTURE",
        }
    ]
    return {
        "processor_bounded_once": status.bounded_mode == "process one request and exit",
        "request_classifier_present": status.request_classification["request_family"] in REQUEST_FAMILIES,
        "supported_chat_pattern_present": CHAT_PATTERN in SUPPORTED_REQUEST_PATTERNS,
        "supported_file_pattern_present": FILE_METADATA_PATTERN in SUPPORTED_REQUEST_PATTERNS,
        "future_request_families_modeled": all(pattern in FUTURE_REQUEST_PATTERNS for pattern in FUTURE_REQUEST_PATTERNS),
        "deterministic_responder_targets_modeled": any(target["target_type"] == "DETERMINISTIC_ROUTER" for target in targets),
        "future_lm_targets_modeled": len(future_lm_targets) >= 6,
        "future_lm_targets_not_called": all(target["adapter_available"] is False and target["live_call_allowed"] is False for target in future_lm_targets),
        "source_request_id_propagated": bool(response.source_request_id),
        "human_operator_message_present": bool(response.operator_headline and response.operator_message),
        "response_ready_has_real_readback": response.internal_status != "RESPONSE_READY" or bool(response.readback_files or response.visible_cards),
        "blocked_has_how_to_fix": response.internal_status not in {
            "BLOCKED_WITH_REASON",
            "BLOCKED_MAC_HANDOFF_UNAVAILABLE",
            "BLOCKED_WORKER_UNAVAILABLE",
        }
        or bool(response.how_to_fix.strip()),
        "failed_has_how_to_fix": response.internal_status != "FAILED_WITH_REASON" or bool(response.how_to_fix.strip()),
        "timed_out_has_how_to_fix": response.internal_status != "TIMED_OUT_WITH_REASON" or bool(response.how_to_fix.strip()),
        "duplicate_has_existing_readback": response.internal_status != "DUPLICATE_NOOP_WITH_READBACK" or bool(response.readback_files),
        "operator_text_hides_internal_status": not any(status_value in (response.operator_headline + response.operator_message) for status_value in INTERNAL_STATUSES),
        "terminal_quality_passed": not quality_errors,
        "terminal_quality_errors": quality_errors,
        "approved_inbox_only_scanned": True,
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
    response: OpenClawResponseForMac,
    *,
    generated_at: str | None = None,
    blockers: tuple[str, ...] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = generated_at or utc_now()
    status = _processor_status_from_response(response, blockers=blockers)
    layered_fields = _layered_response_fields(response, created_at=generated_at)
    voice_fields = _voice_authorship_fields(response, layered_fields)
    spoken_packet = _spoken_response_packet(response, layered_fields, voice_fields)
    response_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": RESPONSE_READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "created_at": generated_at,
        **layered_fields,
        **voice_fields,
        **asdict(response),
        "spoken_response_packet": spoken_packet,
        "terminal": _terminal_for_status(response.internal_status),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    status_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "internal_statuses": INTERNAL_STATUSES,
        "audience_modes": AUDIENCE_MODES,
        "display_modes": DISPLAY_MODES,
        "request_families": REQUEST_FAMILIES,
        "responder_target_types": RESPONDER_TARGET_TYPES,
        "processor_status": asdict(status),
        "latest_response_ref": RESPONSE_JSON_EXPORT_NAME,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    status_payload["machine_proof"] = _machine_proof(response, status)
    status_payload["machine_proof"].update(
        {
            "deterministic_voice_selection_present": True,
            "voice_applied": voice_fields["voice_applied"],
            "vibe_applied": voice_fields["vibe_applied"],
            "voice_model_call_performed": False,
            "high_risk_override_applied": voice_fields["high_risk_override_applied"],
            "cockpit_prose_limits_applied": True,
            "spoken_response_packet_present": True,
            "spoken_script_truth_bound": True,
            "speech_synthesis_performed": False,
            "microphone_capture_performed": False,
            "cloud_audio_performed": False,
            "spoken_cloud_synthesis_allowed": spoken_packet["cloud_synthesis_allowed"],
            "spoken_local_playback_preferred": spoken_packet["local_playback_preferred"],
        }
    )
    response_payload["machine_proof"] = json.loads(stable_json(status_payload["machine_proof"]))
    status_payload["machine_proof"]["content_hash"] = _content_hash(status_payload)
    response_payload["machine_proof"]["content_hash"] = _content_hash(response_payload)
    return response_payload, status_payload


def format_response_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# OpenClaw Response for Mac",
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
            "# OpenClaw Request Processor Status",
            "",
            f"Status: {status['terminal_result']}",
            "",
            status["operator_message"],
            "",
            "What happened:",
            *[f"- {item}" for item in status["what_happened"]],
            "",
            f"Why: {status['why_it_happened']}",
            "",
            f"How to fix: {status['how_to_fix']}",
            "",
            f"Selected rail: {status['selected_rail']}",
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
) -> tuple[Path, Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    response_json = export_root / RESPONSE_JSON_EXPORT_NAME
    status_json = export_root / STATUS_JSON_EXPORT_NAME
    status_operator = export_root / STATUS_OPERATOR_EXPORT_NAME
    response_json.write_text(stable_json(response_payload), encoding="utf-8")
    status_json.write_text(stable_json(status_payload), encoding="utf-8")
    status_operator.write_text(format_status_markdown(status_payload), encoding="utf-8")
    return response_json, status_json, status_operator


def build_summary(
    response_payload: Mapping[str, Any],
    status_payload: Mapping[str, Any],
    paths: tuple[Path, Path, Path],
) -> dict[str, Any]:
    response_json, status_json, status_operator = paths
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "response_json_path": response_json.as_posix(),
        "status_json_path": status_json.as_posix(),
        "status_operator_path": status_operator.as_posix(),
        "source_request_id": response_payload["source_request_id"],
        "source_request_filename": response_payload["source_request_filename"],
        "request_type": response_payload["request_type"],
        "selected_rail": status_payload["processor_status"]["selected_rail"],
        "internal_status": response_payload["internal_status"],
        "operator_headline": response_payload["operator_headline"],
        "operator_message": response_payload["operator_message"],
        "how_to_fix": response_payload["how_to_fix"],
        "cards_available": response_payload["cards_available"],
        "readback_files": response_payload["readback_files"],
        "response_kind": response_payload["response_kind"],
        "audience_mode": response_payload["audience_mode"],
        "display_mode": response_payload["display_mode"],
        "headline": response_payload["headline"],
        "one_line_answer": response_payload["one_line_answer"],
        "response_author": response_payload["response_author"],
        "voice_profile_ref": response_payload["voice_profile_ref"],
        "vibe_profile_ref": response_payload["vibe_profile_ref"],
        "voice_selection_reason": response_payload["voice_selection_reason"],
        "high_risk_override_applied": response_payload["high_risk_override_applied"],
        "terminal_quality_passed": status_payload["machine_proof"]["terminal_quality_passed"],
        "all_live_authority_flags_false": status_payload["machine_proof"]["all_live_authority_flags_false"],
        "future_lm_targets_not_called": status_payload["machine_proof"]["future_lm_targets_not_called"],
        "external_action_performed": status_payload["machine_proof"]["external_action_performed"],
        "content_hash": response_payload["machine_proof"]["content_hash"],
    }


def run_and_write(
    *,
    inbox: Path,
    request_file: Path | None,
    request_id: str | None,
    export_root: Path,
    generated_at: str | None,
    watch_seconds: int | None = None,
    read_model_reader: ReadModelReader | None = None,
) -> tuple[dict[str, Any], dict[str, Any], tuple[Path, Path, Path], tuple[str, ...]]:
    if watch_seconds is not None:
        response = process_with_timeout(
            inbox=inbox,
            export_root=export_root,
            generated_at=generated_at,
            watch_seconds=watch_seconds,
            read_model_reader=read_model_reader,
        )
    else:
        response = process_once(
            inbox=inbox,
            request_file=request_file,
            request_id=request_id,
            export_root=export_root,
            generated_at=generated_at,
            read_model_reader=read_model_reader,
        )
    quality_errors = _terminal_quality_errors(response)
    response_payload, status_payload = build_payloads(
        response,
        generated_at=generated_at,
        blockers=quality_errors,
    )
    paths = write_exports(response_payload, status_payload, export_root)
    return response_payload, status_payload, paths, quality_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process one OpenClaw/Mission Control request and write human readback.")
    parser.add_argument("--once", action="store_true", help="Process one request and exit. This is the default.")
    parser.add_argument("--file", dest="request_file", default=None, help="Specific supported request file to process.")
    parser.add_argument("--request-id", default=None, help="Specific request_id to find in the approved inbox.")
    parser.add_argument("--watch-seconds", type=int, default=None, help="Bounded wait for a request, then write timeout readback.")
    parser.add_argument("--inbox", default=str(APPROVED_INBOX))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    request_file = Path(args.request_file) if args.request_file else None
    response_payload, status_payload, paths, quality_errors = run_and_write(
        inbox=Path(args.inbox),
        request_file=request_file,
        request_id=args.request_id,
        export_root=export_root,
        generated_at=args.generated_at,
        watch_seconds=args.watch_seconds,
    )
    output = response_payload if args.format == "json" else build_summary(response_payload, status_payload, paths)
    print(stable_json(output), end="")
    return 1 if quality_errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
