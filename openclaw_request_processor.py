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
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import chat_readback_card_mirror
import chat_workflow_visual_event_package_compiler
import capital_hilton_invoice_operator_readback
import client_invoice_audit_handoff
import client_invoice_sheet_audit
import client_invoice_workbook_registry
import conversational_workflow_router_intake
import deterministic_intent_interpreter
import evidence_intake
import guardian_output_gate
import invoice_review_action_request_handler
import local_surface_request_contract
import operator_file_metadata_intake
import global_run_mode_context
import maestro_cassandra_responder
import operator_controller_event_router
import openclaw_request_router
import proof_to_response_runtime
import local_artifact_reference
import scoped_context_package_compiler_contract
import st_annes_work_log_review
import workroom_review_decision_consumer
import worker_routing_intelligence
import workflow_package_request_consumer
import workflow_execution_package_compiler


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
RESPONSE_BRIDGE_ROOT_ENV_VAR = "OPENCLAW_RESPONSE_BRIDGE_ROOT"
DEFAULT_RESPONSE_DIR = Path(
    os.environ.get(RESPONSE_BRIDGE_ROOT_ENV_VAR, "/mnt/e/openclaw/mission_control_responses/to_mac")
)

SCHEMA_VERSION = "openclaw_request_processor_v0"
STATUS_READ_MODEL_ID = "openclaw_request_processor_status"
RESPONSE_READ_MODEL_ID = "openclaw_response_for_mac"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
STATUS_OPERATOR_EXPORT_NAME = "openclaw_request_processor_OPERATOR.md"
RESPONSE_JSON_EXPORT_NAME = f"{RESPONSE_READ_MODEL_ID}.json"
LATEST_RESPONSE_EXPORT_NAME = "openclaw_response_for_mac_latest.json"
RESPONSE_MANIFEST_EXPORT_NAME = "response_manifest.json"
CONTRACT_STATUS = "BOUNDED_OPENCLAW_REQUEST_LIFECYCLE_PROCESSOR"

CHAT_PATTERN = conversational_workflow_router_intake.REQUEST_FILENAME_PATTERN
FILE_METADATA_PATTERN = operator_file_metadata_intake.REQUEST_FILENAME_PATTERN
LOCAL_SURFACE_RESULT_PATTERNS = (
    "mission_control_local_surface_result_*.json",
    "mission_control_surface_result_*.json",
    "mission_control_local_surface_request_result_*.json",
    "mission_control_field_mapping_result_*.json",
    "mission_control_capture_request_*local_surface_result*.json",
)
ARTIFACT_REFERENCE_APPROVAL_PATTERNS = (
    "mission_control_artifact_reference_approval_*.json",
    "mission_control_approved_artifact_reference_*.json",
    "mission_control_capture_request_*artifact_reference*.json",
)
ARTIFACT_INTAKE_REQUEST_PATTERNS = (
    "mission_control_artifact_intake_request_*.json",
    "mission_control_approved_artifact_intake_*.json",
    "mission_control_capture_request_*artifact_intake*.json",
)
INVOICE_REVIEW_ACTION_PATTERNS = (
    "mission_control_invoice_review_action_*.json",
    "mission_control_capture_request_*invoice_review_action*.json",
)
INVOICE_REVIEW_ACTION_RESULT_PATTERNS = (
    "mission_control_invoice_review_action_result_*.json",
    "mission_control_capture_request_*invoice_review_action_result*.json",
)
WORKBOOK_REGISTRATION_REQUEST_PATTERNS = (
    "mission_control_workbook_registration_request_*.json",
    "mission_control_capture_request_*workbook_registration*.json",
)
EVIDENCE_INTAKE_REQUEST_PATTERNS = (
    "mission_control_evidence_intake_request_*.json",
    "mission_control_evidence_drop_request_*.json",
    "mission_control_capture_request_*evidence_intake*.json",
    "mission_control_capture_request_*evidence_drop*.json",
)
OPERATOR_CONTROLLER_EVENT_REQUEST_PATTERNS = operator_controller_event_router.REQUEST_FILENAME_PATTERNS
CONTEXT_ATTACHMENT_PATTERN = "mission_control_context_request_*.json"
SECRET_INTAKE_PATTERN = "mission_control_secret_intake_request_*.json"
VISUAL_WORKSPACE_PATTERN = "mission_control_visual_workspace_request_*.json"
WORKER_DISPATCH_PATTERN = "mission_control_worker_dispatch_request_*.json"
WORKFLOW_PACKAGE_REQUEST_PATTERNS = workflow_package_request_consumer.REQUEST_FILENAME_PATTERNS
ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST_PATTERNS = st_annes_work_log_review.REQUEST_FILENAME_PATTERNS
WORKROOM_REVIEW_DECISION_REQUEST_PATTERNS = workroom_review_decision_consumer.REQUEST_FILENAME_PATTERNS

SUPPORTED_REQUEST_PATTERNS = (
    CHAT_PATTERN,
    FILE_METADATA_PATTERN,
    *ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST_PATTERNS,
    *WORKROOM_REVIEW_DECISION_REQUEST_PATTERNS,
    *WORKFLOW_PACKAGE_REQUEST_PATTERNS,
    *LOCAL_SURFACE_RESULT_PATTERNS,
    *ARTIFACT_REFERENCE_APPROVAL_PATTERNS,
    *ARTIFACT_INTAKE_REQUEST_PATTERNS,
    *INVOICE_REVIEW_ACTION_PATTERNS,
    *INVOICE_REVIEW_ACTION_RESULT_PATTERNS,
    *WORKBOOK_REGISTRATION_REQUEST_PATTERNS,
    *EVIDENCE_INTAKE_REQUEST_PATTERNS,
    *OPERATOR_CONTROLLER_EVENT_REQUEST_PATTERNS,
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
    "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST",
    "WORKROOM_REVIEW_DECISION_REQUEST",
    "WORKBOOK_REGISTRATION_REQUEST",
    "EVIDENCE_INTAKE_REQUEST",
    "OPERATOR_CONTROLLER_EVENT_REQUEST",
    "WORKFLOW_PACKAGE_REQUEST",
    "LOCAL_SURFACE_RESULT",
    "INVOICE_REVIEW_ACTION_RESULT",
    "ARTIFACT_REFERENCE_APPROVAL",
    "ARTIFACT_INTAKE_REQUEST",
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
    "MAESTRO": "voice:maestro:conductor",
    "CHIEF": "voice:chief:operational",
    "CASSANDRA": "voice:cassandra:communications",
    "CLARA": "voice:clara:client_safe_draft",
    "GUARDIAN": "voice:guardian:proof_gate",
    "NILES": "voice:niles:creative_flow",
    "HERMES": "voice:hermes:audit",
    "OPENCLAW_SYSTEM": "voice:system:neutral",
    "UNKNOWN": "voice:system:neutral",
}

VIBE_PROFILE_REFS = {
    "MAESTRO": "vibe:maestro:conductor",
    "CHIEF": "vibe:chief:command_center",
    "CASSANDRA": "vibe:cassandra:executive_calm",
    "CLARA": "vibe:clara:client_safe_calm",
    "GUARDIAN": "vibe:guardian:strict_proof",
    "NILES": "vibe:niles:creative_flow",
    "HERMES": "vibe:hermes:architecture_critic",
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

HERMES_CONTEXT_TERMS = (
    "hermes",
    "architecture",
    "architectural",
    "audit",
    "systems auditor",
    "architecture critic",
    "strategic advisor",
    "second opinion",
    "pattern-aware",
    "pattern risk",
)

CODE_BUILD_CONTEXT_TERMS = (
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
    "visual_event_package",
    "capital_hilton_invoice_operator_readback",
    "workflow_execution_package_compiler",
    "gated_email_send_adapter",
    "coupa_supplier_portal_package_compiler",
    "openclaw_request_processor",
    "openclaw_request_response_service",
    "openclaw_response_for_mac",
    "generated/read_models",
    "sqlite",
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
    "MAESTRO": "composed_authoritative",
    "CHIEF": "operational_crisp",
    "CASSANDRA": "polished_calm",
    "CLARA": "client_safe_polished_calm",
    "GUARDIAN": "proof_first",
    "NILES": "creative_flow",
    "HERMES": "skeptical_architecture_review",
    "OPENCLAW_SYSTEM": "neutral_clear",
    "UNKNOWN": "neutral_clear",
}

COMPACT_RESPONSE_FIELDS = (
    "headline",
    "one_line_answer",
    "eliwinship",
    "primary_status",
    "primary_blocker",
    "next_action",
)

BAD_PHRASE_REPLACEMENTS = (
    ("basically sent", "not complete"),
    ("ready to send", "not cleared to send"),
    ("looks ready to send", "not cleared to send"),
    ("deployed", "validated locally"),
    ("100% correct", "validated against current proof"),
    ("flawless", "validated against current proof"),
    ("don't worry about the gate", "the gate remains required"),
    ("dont worry about the gate", "the gate remains required"),
    ("I fixed it", "local change prepared"),
    ("I sent", "send not claimed"),
    ("sent it", "send not claimed"),
    ("I submitted", "submit not claimed"),
    ("submitted it", "submit not claimed"),
    ("submitted without submit receipt", "not submitted without receipt"),
)

BAD_PHRASES = tuple(phrase for phrase, _replacement in BAD_PHRASE_REPLACEMENTS)

HUMOR_DEGRADED_TERMS = (
    "couldn't reach",
    "could not reach",
    "can't reach",
    "cannot reach",
    "unreachable",
    "re-run --auth",
    "rerun --auth",
    "auth failed",
    "authentication failed",
    "authorization failed",
    "permission denied",
    "broken",
    "degraded",
    "failed",
    "failure",
    "error",
    "errored",
    "blocked",
    "not ready",
    "offline",
    "crash-loop",
    "crash loop",
    "timed out",
    "timeout",
    "fallback",
)

HUMOR_GROUNDING_FAILURE_KEYS = (
    "grounding_failed",
    "grounding_violation",
    "ungrounded_output_blocked",
    "validation_failed",
    "role_output_blocked",
)

HUMOR_AUTO_HEAL_KEYS = (
    "auto_heal_landed",
    "auto_healed",
    "self_heal_landed",
    "self_heal_completed",
    "self_heal_succeeded",
)

AGENT_TASTE_FORBIDDEN = {
    "CHIEF": (
        "you got this",
        "awesome",
        "crush it",
        "unstoppable",
        "motivational",
        "no worries",
    ),
    "CASSANDRA": (
        "i sent",
        "sent it",
        "emailed",
        "delivered to",
        "ready to send",
    ),
    "CLARA": (
        "i sent",
        "sent it",
        "emailed",
        "delivered to",
        "ready to send",
    ),
    "GUARDIAN": (
        "panic",
        "catastrophe",
        "disaster",
        "terrifying",
        "emergency!!!",
    ),
    "NILES": (
        "i fixed the routing",
        "updated the show file",
        "saved the session",
        "sent",
        "submitted",
    ),
    "HERMES": (
        "i approved",
        "i executed",
        "guardian is optional",
        "replace guardian",
        "ignore guardian",
    ),
    "OPENCLAW_SYSTEM": (
        "buddy",
        "pal",
        "awesome",
        "crush",
    ),
}

RESPONDER_TARGET_TYPES = (
    "DETERMINISTIC_ROUTER",
    "FILE_METADATA_INTAKE",
    "LOCAL_SURFACE_RESULT_INTAKE",
    "WORKFLOW_PACKAGE_QUEUE",
    "WORKBOOK_REGISTRATION",
    "EVIDENCE_INTAKE",
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
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "push_allowed": False,
    "merge_allowed": False,
    "sent": False,
    "paid": False,
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
    proof_to_response: dict[str, Any] = field(default_factory=dict)
    proof_to_response_status: str = ""


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


# ── Conversation-continuity flag (ADDITIVE, default OFF) ──────────────────────
def _continuity_enabled() -> bool:
    """Return True only when OPENCLAW_CONTINUITY_CAPSULE is "1" or "true".

    Cheap + import-safe: reads env at call time, no side-effects.
    """
    return os.environ.get("OPENCLAW_CONTINUITY_CAPSULE", "0").lower() in ("1", "true")


# Task 144 (CLASS #5): the operator-surface leak guard in _enrich_operator_surface used to
# be piggybacked on _continuity_enabled() (an unrelated conversation-memory feature flag
# that defaults OFF) -- meaning the ONE real substitute-on-leak block anywhere in the fleet
# was dormant by default. Split into its own flag, default ON (doctrine: "no raw internals,
# ever, anywhere" -- not "only when an unrelated memory feature happens to be on").
def _operator_surface_guard_enabled() -> bool:
    """Return False only when OPENCLAW_OPERATOR_SURFACE_GUARD is explicitly disabled."""
    return os.environ.get("OPENCLAW_OPERATOR_SURFACE_GUARD", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


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


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{time.monotonic_ns()}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


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


def _safe_filename_part(value: object) -> str:
    text = str(value or "")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    if cleaned:
        return cleaned[:160]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _path_is_relative_to(path: Path | None, root: Path) -> bool:
    if path is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def default_response_publication_dir(*, inbox: Path, request_file: Path | None) -> Path | None:
    """Publish by default only for the approved Mac/PC shared inbox."""

    if _path_is_relative_to(request_file, APPROVED_INBOX):
        return DEFAULT_RESPONSE_DIR
    if _same_path(inbox, APPROVED_INBOX):
        return DEFAULT_RESPONSE_DIR
    return None


def is_evidence_intake_request(raw_request: Mapping[str, Any]) -> bool:
    return evidence_intake.is_evidence_intake_request(raw_request)


def is_operator_controller_event_request(raw_request: Mapping[str, Any]) -> bool:
    request_type = str(raw_request.get("request_type") or raw_request.get("kind") or raw_request.get("type") or "").strip().upper()
    return request_type in {
        operator_controller_event_router.REQUEST_TYPE,
        global_run_mode_context.RUN_MODE_SET_REQUEST_SCHEMA,
    }


def _valid_publication_source_request_id(value: object) -> bool:
    request_id = str(value or "").strip()
    if not request_id:
        return False
    blocked_exact = {
        "unknown_request",
        "unknown_unparseable_request",
        "no_request_available",
        "timed_out_no_request_available",
    }
    if request_id in blocked_exact:
        return False
    if request_id.startswith(("missing_request_id_", "unknown_")):
        return False
    return True


def _read_response_manifest(response_dir: Path) -> dict[str, Any]:
    manifest_path = response_dir / RESPONSE_MANIFEST_EXPORT_NAME
    if not manifest_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "manifest_id": "openclaw_response_manifest",
            "responses": [],
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "schema_version": SCHEMA_VERSION,
            "manifest_id": "openclaw_response_manifest",
            "previous_manifest_parse_status": "invalid_json_replaced",
            "responses": [],
        }
    if isinstance(manifest, dict):
        return manifest
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_id": "openclaw_response_manifest",
        "responses": [],
    }


def stamp_proof_to_response_source_response_path(
    response_payload: Mapping[str, Any],
    *,
    source_response_path: str,
) -> dict[str, Any]:
    """Stamp request-scoped proof responses with the final Mac response path."""

    def stamp(value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        stamped = dict(value)
        stamped["source_response_path"] = source_response_path
        stamped["response_content_hash"] = proof_to_response_runtime._content_hash(
            {key: item for key, item in stamped.items() if key != "response_content_hash"}
        )
        return stamped

    payload = dict(response_payload)
    if isinstance(payload.get("proof_to_response"), Mapping):
        payload["proof_to_response"] = stamp(payload["proof_to_response"])

    detail = payload.get("detail_disclosure")
    if isinstance(detail, Mapping):
        stamped_detail = dict(detail)
        if isinstance(stamped_detail.get("proof_to_response"), Mapping):
            stamped_detail["proof_to_response"] = stamp(stamped_detail["proof_to_response"])
        layered = stamped_detail.get("layered_response_fields")
        if isinstance(layered, Mapping):
            stamped_layered = dict(layered)
            if isinstance(stamped_layered.get("proof_to_response"), Mapping):
                stamped_layered["proof_to_response"] = stamp(stamped_layered["proof_to_response"])
            stamped_detail["layered_response_fields"] = stamped_layered
        payload["detail_disclosure"] = stamped_detail
    return payload


def publish_response_for_mac_outbox(
    response_payload: Mapping[str, Any],
    *,
    response_dir: Path | None,
    published_at: str | None = None,
) -> dict[str, Any]:
    if response_dir is None:
        return {
            "published": False,
            "blocked_reason": "RESPONSE_PUBLICATION_NOT_CONFIGURED",
            "response_file": None,
            "latest_response_file": None,
            "manifest_file": None,
        }
    source_request_id = str(response_payload.get("source_request_id") or "").strip()
    if not _valid_publication_source_request_id(source_request_id):
        return {
            "published": False,
            "blocked_reason": "MISSING_VALID_SOURCE_REQUEST_ID",
            "response_file": None,
            "latest_response_file": None,
            "manifest_file": None,
        }
    if not _same_path(response_dir, DEFAULT_RESPONSE_DIR):
        return {
            "published": False,
            "blocked_reason": "UNAPPROVED_RESPONSE_DIR",
            "response_file": None,
            "latest_response_file": None,
            "manifest_file": None,
        }

    published_at = published_at or utc_now()
    response_dir.mkdir(parents=True, exist_ok=True)
    response_file = response_dir / f"openclaw_response_for_mac_{_safe_filename_part(source_request_id)}.json"
    latest_file = response_dir / LATEST_RESPONSE_EXPORT_NAME
    manifest_file = response_dir / RESPONSE_MANIFEST_EXPORT_NAME
    published_payload = stamp_proof_to_response_source_response_path(
        response_payload,
        source_response_path=response_file.as_posix(),
    )
    published_payload["published_at"] = published_at
    published_payload["terminal"] = bool(response_payload.get("terminal"))
    published_payload["service_note"] = "Published by bounded OpenClaw processor for Mac scoped response lookup."

    _atomic_write_text(response_file, stable_json(published_payload))
    _atomic_write_text(latest_file, stable_json(published_payload))
    if isinstance(published_payload.get("proof_to_response"), Mapping):
        proof_to_response_runtime.restamp_latest_source_response_path(
            source_request_id=source_request_id,
            source_response_path=response_file.as_posix(),
            generated_at=published_at,
        )

    manifest = _read_response_manifest(response_dir)
    responses = manifest.get("responses")
    if not isinstance(responses, list):
        responses = []
    record = {
        "source_request_id": source_request_id,
        "source_request_filename": response_payload.get("source_request_filename"),
        "request_type": response_payload.get("request_type"),
        "internal_status": response_payload.get("internal_status"),
        "operator_headline": response_payload.get("operator_headline"),
        "headline": response_payload.get("headline"),
        "response_file": response_file.as_posix(),
        "published_at": published_at,
        "terminal": published_payload["terminal"],
    }
    responses = [item for item in responses if item.get("source_request_id") != source_request_id]
    responses.append(record)
    manifest.update(
        {
            "schema_version": SCHEMA_VERSION,
            "manifest_id": "openclaw_response_manifest",
            "updated_at": published_at,
            "latest_response_file": latest_file.as_posix(),
            "responses": responses[-200:],
        }
    )
    _atomic_write_text(manifest_file, stable_json(manifest))
    return {
        "published": True,
        "blocked_reason": None,
        "response_file": response_file.as_posix(),
        "latest_response_file": latest_file.as_posix(),
        "manifest_file": manifest_file.as_posix(),
        "source_request_id": source_request_id,
        "source_request_filename": response_payload.get("source_request_filename"),
        "terminal": published_payload["terminal"],
    }


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
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST_PATTERNS):
        family = "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST"
        rail = "st_annes_work_log_review.action_consumer"
        reason = "Filename matches Mission Control St. Anne's work-log review action pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in WORKROOM_REVIEW_DECISION_REQUEST_PATTERNS):
        family = "WORKROOM_REVIEW_DECISION_REQUEST"
        rail = "workroom_review_decision_consumer"
        reason = "Filename matches Mission Control Workroom review decision request pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in WORKBOOK_REGISTRATION_REQUEST_PATTERNS):
        family = "WORKBOOK_REGISTRATION_REQUEST"
        rail = "client_invoice_workbook_registry"
        reason = "Filename matches Mission Control workbook registration request pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in EVIDENCE_INTAKE_REQUEST_PATTERNS):
        family = "EVIDENCE_INTAKE_REQUEST"
        rail = "verified_operator_evidence_intake"
        reason = "Filename matches Mission Control evidence intake request pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in OPERATOR_CONTROLLER_EVENT_REQUEST_PATTERNS):
        family = "OPERATOR_CONTROLLER_EVENT_REQUEST"
        rail = "operator_controller_event_router"
        reason = "Filename matches Mission Control operator controller event request pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in WORKFLOW_PACKAGE_REQUEST_PATTERNS):
        family = "WORKFLOW_PACKAGE_REQUEST"
        rail = "workflow_package_request_consumer"
        reason = "Filename matches Mission Control generic operator instruction package pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in LOCAL_SURFACE_RESULT_PATTERNS):
        family = "LOCAL_SURFACE_RESULT"
        rail = "local_surface_result_intake"
        reason = "Filename matches Mission Control local surface result pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in ARTIFACT_REFERENCE_APPROVAL_PATTERNS):
        family = "ARTIFACT_REFERENCE_APPROVAL"
        rail = "approved_readable_artifact_reference"
        reason = "Filename matches Mission Control artifact reference approval pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in ARTIFACT_INTAKE_REQUEST_PATTERNS):
        family = "ARTIFACT_INTAKE_REQUEST"
        rail = "register_or_resolve_invoice_workbook_artifact"
        reason = "Filename matches Mission Control artifact intake request pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in INVOICE_REVIEW_ACTION_RESULT_PATTERNS):
        family = "INVOICE_REVIEW_ACTION_RESULT"
        rail = "invoice_record_selection_result"
        reason = "Filename matches Mission Control invoice review action result pattern."
        future_supported = False
    elif filename and any(fnmatch.fnmatch(filename, pattern) for pattern in INVOICE_REVIEW_ACTION_PATTERNS):
        family = "LOCAL_SURFACE_RESULT"
        rail = "invoice_review_action_request"
        reason = "Filename matches Mission Control invoice review guided action pattern."
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
            if family in {
                "CHAT",
                "FILE_METADATA",
                "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST",
                "WORKROOM_REVIEW_DECISION_REQUEST",
                "WORKBOOK_REGISTRATION_REQUEST",
                "EVIDENCE_INTAKE_REQUEST",
                "WORKFLOW_PACKAGE_REQUEST",
                "LOCAL_SURFACE_RESULT",
                "ARTIFACT_REFERENCE_APPROVAL",
                "ARTIFACT_INTAKE_REQUEST",
            }
            else "Return a human blocked response until the requested rail is connected."
        ),
    )


def list_supported_requests(inbox: Path = APPROVED_INBOX) -> tuple[Path, ...]:
    if not inbox.exists() or not inbox.is_dir():
        return ()
    matches = [
        path
        for path in inbox.iterdir()
        if path.is_file() and classify_request_filename(path.name).request_family in {
            "CHAT",
            "FILE_METADATA",
            "WORKFLOW_PACKAGE_REQUEST",
            "WORKROOM_REVIEW_DECISION_REQUEST",
            "WORKBOOK_REGISTRATION_REQUEST",
            "EVIDENCE_INTAKE_REQUEST",
            "LOCAL_SURFACE_RESULT",
            "ARTIFACT_REFERENCE_APPROVAL",
            "ARTIFACT_INTAKE_REQUEST",
            "INVOICE_REVIEW_ACTION_RESULT",
        }
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


# ── Continuity-identity stamping for brain/CHAT responses (ADDITIVE) ──────────
# Bug: brain/CHAT responses (answer_frontdoor_chat + interpreter diverts) were
# emitted WITHOUT conversation_id / turn / agent / thread identifiers, so the
# continuity capsule and any downstream correlation are starved even when the
# message reached the brain. The conversation_id stamp previously lived only in
# the continuity write-back block (flag-gated AND requiring a non-empty minted
# conversation_id AND a loaded capsule) — so a brain CHAT turn with no minted id
# (or with continuity off) carried no identifiers at all.
#
# This stamper is FLAG-INDEPENDENT and applies ONLY to CHAT responses. It never
# loads/writes a capsule (that stays continuity-flag-gated and unchanged); it
# only ATTACHES correlation identifiers to the response detail + the brain card's
# machine_proof. For non-CHAT responses it returns the response unchanged.

def _derive_conversation_id(raw_request: Mapping[str, Any]) -> str:
    """Return a stable conversation_id for this request.

    Prefers an explicit minted ``conversation_id``. Otherwise derives a stable
    FALLBACK from per-conversation-stable request keys (channel + chat/thread),
    deliberately WITHOUT a per-message timestamp so two turns in the same
    conversation get the SAME fallback id (continuity across follow-ups).
    """
    explicit = str(raw_request.get("conversation_id") or "").strip()
    if explicit:
        return explicit
    channel = str(raw_request.get("source_channel") or "maestro_listener").strip()
    # chat/thread anchor: prefer the per-chat ref, fall back to thread/surface.
    chat_anchor = str(
        raw_request.get("telegram_chat_ref")
        or raw_request.get("thread_ref")
        or raw_request.get("current_thread_ref")
        or raw_request.get("active_surface_ref")
        or raw_request.get("active_entity_ref")
        or "operator_maestro_chat"
    ).strip()
    return "conv_fallback_" + _short_hash("continuity_fallback", channel, chat_anchor)


_FRONTDOOR_AGENT_FIELDS = (
    "agent",
    "agent_id",
    "target_agent",
    "target_agent_id",
    "selected_agent",
    "selected_agent_id",
    "active_agent",
    "active_agent_id",
    "response_agent",
    "response_agent_id",
)
_FRONTDOOR_AGENT_ALIASES = {
    "maestro": "maestro",
    "cassandra": "cassandra",
    "clara": "clara",
    "clara_reid": "clara",
    "clara reid": "clara",
    "chief": "chief",
    "guardian": "guardian",
    "niles": "niles",
    "hermes": "hermes",
}


def _normalize_frontdoor_agent(value: object) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return ""
    key = key.replace("-", "_")
    return _FRONTDOOR_AGENT_ALIASES.get(key, "")


def _frontdoor_agent_from_mapping(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    for field in _FRONTDOOR_AGENT_FIELDS:
        agent = _normalize_frontdoor_agent(payload.get(field))
        if agent:
            return agent
    for field in ("context", "current_context", "event", "payload", "session"):
        nested = payload.get(field)
        if isinstance(nested, Mapping):
            agent = _frontdoor_agent_from_mapping(nested)
            if agent:
                return agent
    return ""


def _resolved_frontdoor_agent(
    raw_request: Mapping[str, Any],
    *,
    session: Mapping[str, Any] | None = None,
    _capsule: Any | None = None,
) -> str:
    return (
        _frontdoor_agent_from_mapping(raw_request)
        or _frontdoor_agent_from_mapping(session)
        or _normalize_frontdoor_agent(getattr(_capsule, "agent_id", ""))
        or "maestro"
    )


def _continuity_identity_for_request(raw_request: Mapping[str, Any]) -> dict[str, str]:
    """Build the continuity-identity bundle attached to brain/CHAT responses."""
    conversation_id = _derive_conversation_id(raw_request)
    operator_id = str(
        raw_request.get("actor") or raw_request.get("speaker") or "operator"
    ).strip() or "operator"
    thread_id = str(
        raw_request.get("thread_ref")
        or raw_request.get("current_thread_ref")
        or raw_request.get("active_surface_ref")
        or "operator_maestro_chat"
    ).strip() or "operator_maestro_chat"
    # turn_id is per-message (request-scoped); conversation_id is per-conversation.
    # Prefer request_id; fall back to other per-message-unique anchors so two turns
    # in the same conversation never collide to the same turn_id even on degraded
    # input where request_id/source_request_id are both absent (payload_hash and
    # created_at are per-message; the listener always sets payload_hash).
    request_anchor = str(
        raw_request.get("request_id")
        or raw_request.get("source_request_id")
        or raw_request.get("payload_hash")
        or raw_request.get("created_at")
        or ""
    ).strip()
    turn_id = "turn_" + _short_hash("continuity_turn", conversation_id, request_anchor)
    return {
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "operator_id": operator_id,
        "agent_id": _resolved_frontdoor_agent(raw_request),
        "thread_id": thread_id,
        "conversation_id_source": "minted" if str(raw_request.get("conversation_id") or "").strip() else "fallback",
    }


def _stamp_continuity_identity(
    response: "OpenClawResponseForMac",
    raw_request: Mapping[str, Any],
) -> "OpenClawResponseForMac":
    """Attach continuity identifiers to a brain/CHAT response (additive, CHAT-only).

    - Non-CHAT responses: returned UNCHANGED (byte-identical).
    - CHAT responses: detail_disclosure gains conversation_id/turn_id/operator_id/
      agent_id/thread_id; the brain card's proof.machine_proof gains conversation_id
      + turn_id so the receipt carries the same correlation. Never raises.
    """
    try:
        if response is None or str(getattr(response, "request_type", "")) != "CHAT":
            return response
        ids = _continuity_identity_for_request(raw_request)
        detail = dict(response.detail_disclosure) if isinstance(response.detail_disclosure, dict) else {}
        # Do not clobber an already-present (e.g. continuity write-back) conversation_id.
        for key in ("conversation_id", "turn_id", "operator_id", "agent_id", "thread_id"):
            detail.setdefault(key, ids[key])
        detail.setdefault("continuity_identity", dict(ids))

        # Mirror conversation_id + turn_id into the brain card's machine_proof so the
        # receipt carries the same correlation ids (acceptance criterion 2).
        card = detail.get("dynamic_card_response")
        if isinstance(card, dict):
            proof = card.get("proof")
            if isinstance(proof, dict):
                mp = proof.get("machine_proof")
                if isinstance(mp, dict):
                    mp.setdefault("conversation_id", detail["conversation_id"])
                    mp.setdefault("turn_id", detail["turn_id"])
        return replace(response, detail_disclosure=detail)
    except Exception:
        return response  # never block response delivery


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
            "LOCAL_SURFACE_RESULT_INTAKE",
            "Device-local surface result intake",
            ("LOCAL_SURFACE_RESULT",),
            True,
            selected_family == "LOCAL_SURFACE_RESULT",
        ),
        target(
            "WORKFLOW_PACKAGE_QUEUE",
            "Workflow package queue request consumer",
            ("WORKFLOW_PACKAGE_REQUEST",),
            True,
            selected_family == "WORKFLOW_PACKAGE_REQUEST",
        ),
        target(
            "WORKROOM_REVIEW_DECISION_CONSUMER",
            "Workroom review decision consumer",
            ("WORKROOM_REVIEW_DECISION_REQUEST",),
            True,
            selected_family == "WORKROOM_REVIEW_DECISION_REQUEST",
        ),
        target(
            "WORKBOOK_REGISTRATION",
            "Client invoice workbook registration",
            ("WORKBOOK_REGISTRATION_REQUEST",),
            True,
            selected_family == "WORKBOOK_REGISTRATION_REQUEST",
        ),
        target(
            "EVIDENCE_INTAKE",
            "Verified operator evidence intake",
            ("EVIDENCE_INTAKE_REQUEST",),
            True,
            selected_family == "EVIDENCE_INTAKE_REQUEST",
        ),
        target(
            "ARTIFACT_REFERENCE_APPROVAL",
            "Approved readable artifact reference intake",
            ("LOCAL_SURFACE_RESULT", "ARTIFACT_REFERENCE_APPROVAL"),
            True,
            selected_family == "ARTIFACT_REFERENCE_APPROVAL",
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
            "MAESTRO_CASSANDRA_RESPONDER",
            "Maestro front-door Cassandra specialist responder",
            ("CHAT",),
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
    if request_family == "WORKFLOW_PACKAGE_REQUEST":
        return (
            "request_id",
            "idempotency_key",
            "payload_hash",
            "authority_boundary",
            "created_at",
            "source_surface",
            "source_text",
            "requested_mode",
            "result_receipt_required",
        )
    if request_family == "WORKROOM_REVIEW_DECISION_REQUEST":
        return (
            "request_type",
            "source_surface",
            "requested_mode",
            "authority_boundary",
            "review_packet_id",
            "decision_action",
        )
    if request_family == "WORKBOOK_REGISTRATION_REQUEST":
        return (
            "request_id",
            "idempotency_key",
            "payload_hash",
            "authority_boundary",
            "created_at",
            "source_surface",
            "client_ref",
            "workflow_ref",
            "selected_local_path",
        )
    if request_family == "EVIDENCE_INTAKE_REQUEST":
        return (
            "request_type",
            "source_surface",
            "current_world_ref",
            "current_thread_ref",
            "artifact_kind",
            "operator_note",
            "intended_use",
            "authority_boundary",
        )
    if request_family == "OPERATOR_CONTROLLER_EVENT_REQUEST":
        return (
            "request_type",
            "source_surface",
            "controller_event_type",
            "authority_requested",
            "authority_boundary",
        )
    if request_family == "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST":
        return (
            "request_id",
            "idempotency_key",
            "payload_hash",
            "authority_boundary",
            "created_at",
            "source_surface",
            "requested_mode",
            "result_receipt_required",
            "event_id",
            "review_action",
        )
    if request_family in {"LOCAL_SURFACE_RESULT", "ARTIFACT_REFERENCE_APPROVAL", "ARTIFACT_INTAKE_REQUEST"}:
        return ("request_id", "idempotency_key", "payload_hash", "authority_boundary", "created_at", "intended_use")
    return ("request_id", "idempotency_key", "payload_hash", "authority_boundary", "created_at")


def preflight_request(raw_request: Mapping[str, Any], request_family: str) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    blockers: list[str] = []
    fixes: list[str] = []
    missing = [field for field in _required_fields_for_family(request_family) if field not in raw_request]
    if missing:
        blockers.append(f"Missing required field(s): {', '.join(missing)}.")
        fixes.append("Regenerate or resend the request with the required fields.")
    envelope_verified_families = {
        "WORKROOM_REVIEW_DECISION_REQUEST",
        "EVIDENCE_INTAKE_REQUEST",
        "OPERATOR_CONTROLLER_EVENT_REQUEST",
    }
    if request_family not in envelope_verified_families and not raw_request.get("idempotency_key"):
        blockers.append("Missing idempotency key.")
        fixes.append("Resend the request with idempotency_key set.")
    if request_family not in envelope_verified_families and not raw_request.get("payload_hash"):
        blockers.append("Missing payload hash.")
        fixes.append("Resend the request with payload_hash set.")
    authority = raw_request.get("authority_boundary")
    if not isinstance(authority, Mapping):
        blockers.append("Missing or invalid authority boundary.")
        fixes.append("Include an authority_boundary object with all live authority set false.")
    elif request_family != "WORKROOM_REVIEW_DECISION_REQUEST" and any(value is True for value in authority.values()):
        blockers.append("Request asks for live authority this processor cannot grant.")
        fixes.append("Resend as a deterministic request with all external/live authority false.")
    if request_family == "EVIDENCE_INTAKE_REQUEST" and not str(raw_request.get("artifact_path") or raw_request.get("bridge_artifact_ref") or "").strip():
        blockers.append("Missing artifact_path or bridge_artifact_ref.")
        fixes.append("Resend the evidence intake request with an artifact reference.")
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


def _replace_bad_phrases(text: str) -> str:
    cleaned = str(text)
    for phrase, replacement in BAD_PHRASE_REPLACEMENTS:
        cleaned = re.sub(re.escape(phrase), replacement, cleaned, flags=re.IGNORECASE)
    return cleaned


def _sanitize_cockpit_text(text: str) -> str:
    cleaned = " ".join(_replace_bad_phrases(str(text)).split())
    parts: list[str] = []
    for word in cleaned.split():
        lowered = word.lower().strip(".,;:()[]{}")
        if lowered.startswith("generated/read_models/") or lowered.startswith("/") or "\\" in lowered:
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
    result = _word_limited(result, 16)
    if not result.endswith((".", "!", "?")):
        result += "."
    return result


def _apply_cockpit_prose_limits(fields: dict[str, Any]) -> dict[str, Any]:
    limited = dict(fields)
    limited["headline"] = _word_limited(_sanitize_cockpit_text(str(limited.get("headline") or "")), 6)
    limited["one_line_answer"] = _word_limited(_sanitize_cockpit_text(str(limited.get("one_line_answer") or "")), 30)
    limited["eliwinship"] = _word_limited(_sanitize_cockpit_text(str(limited.get("eliwinship") or "")), 40)
    limited["primary_status"] = _word_limited(_sanitize_cockpit_text(str(limited.get("primary_status") or "")), 12)
    limited["primary_blocker"] = _word_limited(_first_sentence(_sanitize_cockpit_text(str(limited.get("primary_blocker") or "None"))), 12)
    limited["next_action"] = _render_next_action(str(limited.get("next_action") or "Review the response."))
    missing = limited.get("missing_items_short") or ()
    if isinstance(missing, str):
        missing_items = (missing,)
    else:
        missing_items = tuple(str(item) for item in missing)
    limited["missing_items_short"] = tuple(_sanitize_cockpit_text(item) for item in missing_items[:3])
    return limited


def _field_limit_errors(fields: Mapping[str, Any], spoken_packet: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    errors: list[str] = []
    limits = {
        "headline": 6,
        "eliwinship": 40,
        "next_action": 16,
    }
    for field_name, max_words in limits.items():
        value = str(fields.get(field_name) or "")
        if len(value.split()) > max_words:
            errors.append(f"FIELD_TOO_LONG:{field_name}")
    next_action = str(fields.get("next_action") or "")
    if next_action and not next_action.startswith("Next:"):
        errors.append("NEXT_ACTION_MISSING_PREFIX")
    missing = fields.get("missing_items_short") or ()
    if isinstance(missing, str):
        missing_count = 1
    else:
        missing_count = len(tuple(missing))
    if missing_count > 3:
        errors.append("TOO_MANY_MISSING_ITEMS")
    primary_blocker = str(fields.get("primary_blocker") or "")
    if primary_blocker.count(".") > 1 or primary_blocker.count(";") > 0:
        errors.append("PRIMARY_BLOCKER_NOT_SINGLE_CLEAR_BLOCKER")
    if spoken_packet:
        script = str(spoken_packet.get("spoken_script") or "")
        if len(script.split()) > 40:
            errors.append("SPOKEN_SCRIPT_TOO_LONG")
    return tuple(errors)


def _machine_sludge_hits(fields: Mapping[str, Any]) -> tuple[str, ...]:
    hits: list[str] = []
    for field_name in COMPACT_RESPONSE_FIELDS:
        text = str(fields.get(field_name) or "")
        lowered = text.lower()
        if any(term in lowered for term in MACHINE_SLUDGE_TERMS):
            hits.append(f"MACHINE_SLUDGE:{field_name}")
        if "generated/read_models" in lowered or "mission_control_" in lowered or "request_id" in lowered:
            hits.append(f"MACHINE_REF:{field_name}")
        if any(status in text for status in INTERNAL_STATUSES):
            hits.append(f"INTERNAL_STATUS:{field_name}")
        for token in text.split():
            stripped = token.strip(".,;:()[]{}").lower()
            if stripped.startswith("/") or "\\" in stripped:
                hits.append(f"FILE_PATH:{field}")
                break
            if stripped.startswith("sha256:") or (len(stripped) >= 32 and all(char in "0123456789abcdef" for char in stripped)):
                hits.append(f"HASH:{field}")
                break
            if stripped.endswith(".py") or stripped.endswith(".sqlite"):
                hits.append(f"TECHNICAL_ARTIFACT:{field}")
                break
    return tuple(dict.fromkeys(hits))


def _bad_phrase_hits(text: str) -> tuple[str, ...]:
    lowered = str(text).lower()
    return tuple(phrase for phrase in BAD_PHRASES if phrase.lower() in lowered)


def _agent_taste_errors(author: str, text: str, *, high_risk_override_applied: bool = False) -> tuple[str, ...]:
    role = author if author in AGENT_TASTE_FORBIDDEN else "OPENCLAW_SYSTEM"
    lowered = text.lower()
    errors = [f"{role}_FORBIDDEN:{phrase}" for phrase in AGENT_TASTE_FORBIDDEN[role] if phrase in lowered]
    if role == "NILES" and high_risk_override_applied:
        errors.append("NILES_HIGH_RISK_PLAYFUL_VIBE_NOT_SUPPRESSED")
    return tuple(errors)


def _sentence_fingerprints(text: str) -> tuple[str, ...]:
    fingerprints: list[str] = []
    for sentence in re.split(r"[.!?]+", str(text)):
        words = [word.strip(".,;:()[]{}").lower() for word in sentence.split()]
        words = [word for word in words if word]
        if len(words) > 6:
            fingerprints.append(" ".join(words))
    return tuple(fingerprints)


def _duplicate_sentence_hits(payload: Mapping[str, Any]) -> tuple[str, ...]:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    spoken = payload.get("spoken_response_packet") if isinstance(payload.get("spoken_response_packet"), Mapping) else {}
    fields = {
        "operator_message": payload.get("operator_message"),
        "how_to_fix": payload.get("how_to_fix"),
        "next_safe_move": payload.get("next_safe_move"),
        "eliwinship": payload.get("eliwinship"),
        "spoken_script": spoken.get("spoken_script") if isinstance(spoken, Mapping) else "",
    }
    for field_name, value in fields.items():
        for fingerprint in _sentence_fingerprints(str(value or "")):
            if fingerprint in seen:
                duplicates.append(f"DUPLICATE_SENTENCE:{seen[fingerprint]}:{field_name}")
            else:
                seen[fingerprint] = field_name
    return tuple(duplicates)


def _enforce_layered_response_taste(fields: dict[str, Any]) -> dict[str, Any]:
    return _apply_cockpit_prose_limits(fields)


def _enforce_spoken_packet_taste(packet: dict[str, Any]) -> dict[str, Any]:
    clean = dict(packet)
    clean["spoken_script"] = _word_limited(_sanitize_spoken_text(str(clean.get("spoken_script") or "")), 40)
    clean["spoken_summary"] = _word_limited(_sanitize_spoken_text(str(clean.get("spoken_summary") or "")), 12)
    clean["next_safe_move"] = _sanitize_spoken_text(str(clean.get("next_safe_move") or "Review the response."))
    return clean


def _response_taste_guardrails(payload: Mapping[str, Any]) -> dict[str, Any]:
    compact_text = " ".join(str(payload.get(field) or "") for field in COMPACT_RESPONSE_FIELDS)
    spoken_packet = payload.get("spoken_response_packet") if isinstance(payload.get("spoken_response_packet"), Mapping) else {}
    spoken_text = str(spoken_packet.get("spoken_script") or "") if isinstance(spoken_packet, Mapping) else ""
    bad_phrases = tuple(dict.fromkeys(_bad_phrase_hits(compact_text) + _bad_phrase_hits(spoken_text)))
    machine_sludge = _machine_sludge_hits(payload)
    field_errors = _field_limit_errors(payload, spoken_packet if isinstance(spoken_packet, Mapping) else None)
    author = str(payload.get("response_author") or "OPENCLAW_SYSTEM")
    agent_errors = _agent_taste_errors(
        author,
        f"{compact_text} {spoken_text}",
        high_risk_override_applied=bool(payload.get("high_risk_override_applied")),
    )
    duplicates = _duplicate_sentence_hits(payload)
    errors = tuple(dict.fromkeys(field_errors + machine_sludge + tuple(f"BAD_PHRASE:{hit}" for hit in bad_phrases) + agent_errors + duplicates))
    return {
        "field_limits": {
            "headline_max_words": 6,
            "eliwinship_max_words": 40,
            "next_action_max_words": 16,
            "missing_items_short_max_items": 3,
            "spoken_script_max_words": 40,
        },
        "compact_fields_checked": COMPACT_RESPONSE_FIELDS,
        "field_limits_passed": not field_errors,
        "machine_sludge_filtered": not machine_sludge,
        "machine_sludge_hits": machine_sludge,
        "bad_phrase_blockers_passed": not bad_phrases,
        "bad_phrase_blockers": bad_phrases,
        "agent_voice_rules_passed": not agent_errors,
        "agent_voice_errors": agent_errors,
        "duplicate_sentence_reduction_passed": not duplicates,
        "duplicate_sentence_hits": duplicates,
        "taste_errors": errors,
        "taste_passed": not errors,
        "next_safe_move": "Use compact fields for Mac chat; keep debug refs in detail-only surfaces.",
    }


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
    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    speaker_map = {
        "maestro": "MAESTRO",
        "chief": "CHIEF",
        "cassandra": "CASSANDRA",
        "clara": "CLARA",
        "guardian": "GUARDIAN",
        "niles": "NILES",
        "hermes": "HERMES",
        "openclaw": "OPENCLAW_SYSTEM",
    }
    display = layered_fields.get("operator_display") if isinstance(layered_fields.get("operator_display"), Mapping) else None
    if display is None and isinstance(detail.get("operator_display"), Mapping):
        display = detail.get("operator_display")
    if display is None and isinstance(detail.get("workflow_package_request_consumer"), Mapping):
        receipt_display = detail["workflow_package_request_consumer"].get("operator_display")
        display = receipt_display if isinstance(receipt_display, Mapping) else None
    speaker_ref = str(display.get("speaker_ref") or "").strip().lower() if isinstance(display, Mapping) else ""
    if speaker_ref in speaker_map:
        return speaker_map[speaker_ref], "deterministic agent voice routing"
    selected_voice = str(detail.get("selected_voice") or "").strip().upper()
    if selected_voice in VOICE_PROFILE_REFS and selected_voice not in {"UNKNOWN", "OPENCLAW_SYSTEM"}:
        return selected_voice, "offline worker selected voice"
    selected_role_family = str(detail.get("selected_role_family") or "").strip().upper()
    if selected_role_family in VOICE_PROFILE_REFS and selected_role_family not in {"UNKNOWN", "OPENCLAW_SYSTEM"}:
        return selected_role_family, "offline worker selected role"
    interpreter = detail.get("deterministic_intent_interpreter") if isinstance(detail.get("deterministic_intent_interpreter"), Mapping) else {}
    forced_author = str(interpreter.get("response_author") or "") if interpreter else ""
    if forced_author in VOICE_PROFILE_REFS:
        return forced_author, "deterministic intent interpreter response plan"
    text = _voice_context_text(response, layered_fields)
    if response.request_type == "FILE_METADATA":
        return "OPENCLAW_SYSTEM", "file intake / source reference status"
    if response.request_type == "EVIDENCE_INTAKE_REQUEST":
        return "CHIEF", "verified payment evidence intake status"
    if response.request_type in {"LOCAL_SURFACE_RESULT", "ARTIFACT_REFERENCE_APPROVAL"}:
        return "OPENCLAW_SYSTEM", "local surface result intake status"
    if (
        response.request_type == "CHAT"
        and str(layered_fields.get("response_kind") or "") == "CHAT_READBACK"
        and isinstance(detail, Mapping)
        and bool(detail.get("router_readback_ref"))
        and bool(detail.get("card_mirror_ref"))
    ):
        return "OPENCLAW_SYSTEM", "deterministic chat readback status"
    if _is_capital_hilton_status_response(response):
        return "CHIEF", "finance workflow status / readiness / blocker summary"
    if _contains_any(text, CASSANDRA_CONTEXT_TERMS):
        return "CASSANDRA", "communications draft/review context"
    if _contains_any(text, NILES_CONTEXT_TERMS):
        return "NILES", "music or creative world context"
    if _contains_any(text, HERMES_CONTEXT_TERMS):
        return "HERMES", "systems audit / architecture critique context"
    if _contains_any(text, GUARDIAN_CONTEXT_TERMS):
        return "GUARDIAN", "proof, approval, protected boundary, or blocked gate"
    if _contains_any(text, CODE_BUILD_CONTEXT_TERMS):
        return "CHIEF", "build/test/code lane using Codex backend"
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
    model_fields = _model_backend_selection_fields(author, reason, response, layered_fields)
    return {
        "agent_role": author,
        "response_author": author,
        "voice_profile_ref": VOICE_PROFILE_REFS[author],
        "vibe_profile_ref": VIBE_PROFILE_REFS[author],
        "voice_applied": True,
        "vibe_applied": True,
        "voice_selection_reason": reason,
        "high_risk_override_applied": high_risk_override,
        **model_fields,
    }


def _brain_receipt_for_response(response: OpenClawResponseForMac) -> dict[str, Any]:
    proof_response = response.proof_to_response if isinstance(response.proof_to_response, Mapping) else {}
    if proof_response and (
        proof_response.get("protected_generate_called") is True
        or "model_call_performed" in proof_response
        or proof_response.get("protected_generate_route")
        or proof_response.get("route")
    ):
        return dict(proof_response)
    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    card = detail.get("dynamic_card_response") if isinstance(detail.get("dynamic_card_response"), Mapping) else {}
    proof = card.get("proof") if isinstance(card.get("proof"), Mapping) else {}
    machine_proof = proof.get("machine_proof") if isinstance(proof.get("machine_proof"), Mapping) else {}
    if machine_proof and (
        machine_proof.get("protected_generate_called") is True
        or "model_call_performed" in machine_proof
        or machine_proof.get("protected_generate_route")
        or machine_proof.get("route")
    ):
        return dict(machine_proof)
    return {}


def _brain_receipt_route(receipt: Mapping[str, Any]) -> str:
    return str(receipt.get("protected_generate_route") or receipt.get("route") or "").strip()


def _brain_receipt_model_id(receipt: Mapping[str, Any]) -> str:
    return str(
        receipt.get("protected_generate_model_selected")
        or receipt.get("model_selected")
        or receipt.get("model_id")
        or receipt.get("model")
        or ""
    ).strip()


def _brain_receipt_model_performed(receipt: Mapping[str, Any]) -> bool:
    return receipt.get("model_call_performed") is True


def _brain_receipt_local_invoked(receipt: Mapping[str, Any]) -> bool:
    route = _brain_receipt_route(receipt)
    return bool(receipt.get("local_model_invoked") is True or route.startswith("local_ollama"))


def _brain_receipt_external_invoked(receipt: Mapping[str, Any]) -> bool:
    route = _brain_receipt_route(receipt)
    return bool(receipt.get("external_llm_invoked") is True or route.startswith("external"))


def _any_truthy_key(mappings: tuple[Mapping[str, Any], ...], keys: tuple[str, ...]) -> bool:
    for mapping in mappings:
        for key in keys:
            if mapping.get(key) is True:
                return True
    return False


def _humor_health_gate(
    response: OpenClawResponseForMac,
    layered_fields: Mapping[str, Any],
    response_author: str,
) -> dict[str, Any]:
    """Return the health receipt that gates conversational comedy.

    This intentionally reads the same protected-generate receipt used for model
    telemetry. Humor is only a diagnostic signal when the current turn is truly
    healthy; fallback/error/degraded reports must stay plain.
    """
    import operator_surface_guard

    author = str(response_author or "OPENCLAW_SYSTEM").strip().upper() or "OPENCLAW_SYSTEM"
    receipt = _brain_receipt_for_response(response)
    route = _brain_receipt_route(receipt)
    fallback_reason = str(receipt.get("model_fallback_reason") or "").strip()
    deterministic_fallback_used = bool(receipt.get("deterministic_fallback_used") is True)
    model_call_performed = _brain_receipt_model_performed(receipt)
    model_output_delivered_raw = receipt.get("model_output_delivered")
    model_output_delivered = model_output_delivered_raw is not False
    model_ok = bool(
        model_call_performed
        and model_output_delivered
        and not deterministic_fallback_used
        and fallback_reason in {"", "model_ok"}
    )

    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    proof_response = response.proof_to_response if isinstance(response.proof_to_response, Mapping) else {}
    auto_heal_landed = _any_truthy_key((receipt, proof_response, detail), HUMOR_AUTO_HEAL_KEYS)
    grounding_intact = not _any_truthy_key((receipt, proof_response, detail), HUMOR_GROUNDING_FAILURE_KEYS)
    if fallback_reason in {"validation_failed", "truncated"}:
        grounding_intact = False

    health_text = " ".join(
        str(item or "")
        for item in (
            response.operator_headline,
            response.operator_message,
            response.why_it_happened,
            response.how_to_fix,
            response.blocked_reason,
            layered_fields.get("headline"),
            layered_fields.get("one_line_answer"),
            layered_fields.get("eliwinship"),
            layered_fields.get("primary_status"),
            layered_fields.get("primary_blocker"),
            layered_fields.get("detail_summary"),
        )
    )
    degraded_text_present = _contains_any(health_text, HUMOR_DEGRADED_TERMS)
    subsystem_functioning = bool(
        response.internal_status == "RESPONSE_READY"
        and not str(response.blocked_reason or "").strip()
        and not degraded_text_present
    )
    if auto_heal_landed and response.internal_status == "RESPONSE_READY":
        subsystem_functioning = True

    agent_humor_rank = operator_surface_guard.FUNNY_RANKING.get(author, 0)
    agent_allows_humor = agent_humor_rank >= operator_surface_guard.COMEDY_RANK_FLOOR

    suppression_reasons: list[str] = []
    if str(response.request_type or "").upper() != "CHAT":
        suppression_reasons.append("non_chat_surface")
    if not model_ok:
        if deterministic_fallback_used or "fallback" in route:
            suppression_reasons.append("deterministic_fallback")
        else:
            suppression_reasons.append("model_not_ok")
    if not grounding_intact:
        suppression_reasons.append("grounding_not_intact")
    if not subsystem_functioning:
        suppression_reasons.append("subsystem_degraded")
    if not agent_allows_humor:
        suppression_reasons.append("agent_humor_rank_below_floor")

    health_allows_humor = not suppression_reasons
    comedy_gate = operator_surface_guard.check_comedy_gate(
        agent_role=author,
        error_flags=0 if grounding_intact and subsystem_functioning else 1,
        process_hung=False,
        high_risk_context=not health_allows_humor,
        payload_hash=str(response.source_request_id or layered_fields.get("response_id") or ""),
    )
    return {
        "schema_version": "humor_health_gate_v0",
        "health_allows_humor": health_allows_humor,
        "plain_register_required": not health_allows_humor,
        "suppression_reasons": tuple(dict.fromkeys(suppression_reasons)),
        "model_ok": model_ok,
        "model_call_performed": model_call_performed,
        "model_output_delivered": model_output_delivered,
        "deterministic_fallback_used": deterministic_fallback_used,
        "protected_generate_route": route,
        "model_fallback_reason": fallback_reason,
        "grounding_intact": grounding_intact,
        "subsystem_functioning": subsystem_functioning,
        "subsystem_degraded_terms_present": degraded_text_present,
        "auto_heal_landed": auto_heal_landed,
        "response_author": author,
        "agent_humor_rank": agent_humor_rank,
        "per_agent_calibration_source": "operator_surface_guard.FUNNY_RANKING",
        "comedy_gate": {
            "comedy_eligible": comedy_gate.comedy_eligible,
            "comedy_hard_locked": comedy_gate.comedy_hard_locked,
            "kill_switch_reason": comedy_gate.kill_switch_reason,
            "agent_humor_rank": comedy_gate.agent_humor_rank,
            "golden_ratio_passed": comedy_gate.golden_ratio_passed,
            "machine_proof": dict(comedy_gate.machine_proof),
        },
        "machine_proof": {
            "real_brain_receipt_used": bool(receipt),
            "model_health_read_from_receipt": True,
            "per_agent_calibration_reused": True,
            "humor_text_mutation_performed": False,
            "humor_external_action_performed": False,
        },
    }


def _model_backend_selection_from_brain_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not receipt or (
        receipt.get("protected_generate_called") is not True
        and "model_call_performed" not in receipt
        and not _brain_receipt_route(receipt)
    ):
        return {}
    route = _brain_receipt_route(receipt)
    model_id = _brain_receipt_model_id(receipt)
    model_performed = _brain_receipt_model_performed(receipt)
    if model_performed:
        if _brain_receipt_local_invoked(receipt):
            backend = "LOCAL_OLLAMA"
            budget = "Local Ollama front-door brain answered this turn; no postpaid cloud model credits were used."
        elif _brain_receipt_external_invoked(receipt):
            backend = "EXTERNAL_LLM"
            budget = "External model use must be explicitly gated and budgeted; this field mirrors the protected-generate receipt."
        else:
            backend = "PROTECTED_GENERATE"
            budget = "Protected-generate receipt reported a model answer; backend family was not more specific."
        return {
            "selected_model_backend": backend,
            "selected_model_id": model_id,
            "selected_worker_type": route or backend,
            "allowed_tools_plugins": (),
            "model_selection_reason": (
                "The protected Maestro/Cassandra brain answered this turn; "
                f"receipt route={route or 'unknown'}"
                + (f", model={model_id}." if model_id else ".")
            ),
            "credit_budget_policy": budget,
        }
    return {
        "selected_model_backend": "NONE_DETERMINISTIC",
        "selected_model_id": model_id,
        "selected_worker_type": route or "PROTECTED_GENERATE_FALLBACK",
        "allowed_tools_plugins": (),
        "model_selection_reason": (
            "The protected-generate receipt reported no delivered model answer; "
            f"deterministic fallback handled this response (route={route or 'unknown'})."
        ),
        "credit_budget_policy": "No model credits used by this deterministic fallback response.",
    }


def _model_backend_selection_fields(
    author: str,
    voice_reason: str,
    response: OpenClawResponseForMac,
    layered_fields: Mapping[str, Any],
) -> dict[str, Any]:
    proof_response = response.proof_to_response if isinstance(response.proof_to_response, Mapping) else {}
    proof_backend = str(proof_response.get("selected_model_backend") or "").strip()
    proof_candidate_source = str(proof_response.get("candidate_source") or "").strip()
    if (
        proof_backend
        and proof_candidate_source == "lm2_room_backed_worker_structured_output_retry"
        and proof_response.get("model_call_performed") is False
    ):
        return {
            "selected_model_backend": proof_backend,
            "selected_worker_type": "LOCAL_OLLAMA_REUSED_PROOF_RESPONSE",
            "allowed_tools_plugins": (),
            "model_selection_reason": (
                "Existing verified room-backed LM2 proof-to-response output was reused for this scoped controller response; "
                "no new model call, runtime connection, prompt send, or proof bundle send occurred."
            ),
            "credit_budget_policy": "No new model credits or local runtime call were used; the response cites an existing verified LM2 result.",
        }
    brain_receipt_fields = _model_backend_selection_from_brain_receipt(
        _brain_receipt_for_response(response)
    )
    if brain_receipt_fields:
        return brain_receipt_fields
    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    interpreter = detail.get("deterministic_intent_interpreter") if isinstance(detail.get("deterministic_intent_interpreter"), Mapping) else {}
    if interpreter:
        return {
            "selected_model_backend": "NONE_DETERMINISTIC",
            "selected_worker_type": str(interpreter.get("selected_worker_type") or "PC_CODEX"),
            "allowed_tools_plugins": (),
            "model_selection_reason": (
                "Deterministic intent interpreter handled this response; "
                "agent voice is authorship only and no model/backend call is selected."
            ),
            "credit_budget_policy": "No model credits used by this deterministic interpreter path.",
        }
    text = _voice_context_text(response, layered_fields)
    if author == "CHIEF" and _contains_any(text, CODE_BUILD_CONTEXT_TERMS):
        return {
            "selected_model_backend": "CODEX",
            "selected_worker_type": "PC_CODEX",
            "allowed_tools_plugins": ("repo_read", "local_tests", "generated_readmodel_write"),
            "model_selection_reason": "Chief remains the agent; Codex is selected as the code/build backend for local validation work.",
            "credit_budget_policy": "Use only bounded local repo/test tooling in this processor; no cloud model credits are spent.",
        }
    if author == "HERMES":
        return {
            "selected_model_backend": "GEMINI_AGY",
            "selected_worker_type": "GEMINI_AGY",
            "allowed_tools_plugins": (),
            "model_selection_reason": "Hermes remains the advisory agent; Gemini/Agy is modeled as a future audit backend only.",
            "credit_budget_policy": "Cloud audit backends require explicit privacy and credit gates before use.",
        }
    if author in {"CASSANDRA", "CLARA"}:
        return {
            "selected_model_backend": "GPT",
            "selected_worker_type": author,
            "allowed_tools_plugins": ("draft_readback_only",),
            "model_selection_reason": f"{author.title()} may use a writing backend for drafts; send tools remain ungranted.",
            "credit_budget_policy": "Writing backend use must pass privacy and credit gates; no send authority is included.",
        }
    if author == "GUARDIAN":
        return {
            "selected_model_backend": "LOCAL_OLLAMA",
            "selected_worker_type": "GUARDIAN",
            "allowed_tools_plugins": ("proof_ref_readback_only",),
            "model_selection_reason": "Guardian may use local explanation support, but deterministic gates remain authority.",
            "credit_budget_policy": "Prefer local models for protected contexts; cloud requires explicit privacy and credit gates.",
        }
    if author == "NILES":
        return {
            "selected_model_backend": "GPT",
            "selected_worker_type": "NILES",
            "allowed_tools_plugins": ("creative_planning_only",),
            "model_selection_reason": "Niles may use a creative backend for ideation only; file or DAW mutation tools are ungranted.",
            "credit_budget_policy": "Creative backend use must stay low-cost and non-mutating unless separately approved.",
        }
    return {
        "selected_model_backend": "NONE_DETERMINISTIC",
        "selected_worker_type": "OPENCLAW_SYSTEM",
        "allowed_tools_plugins": (),
        "model_selection_reason": f"No live model backend selected; deterministic processor handled this response ({voice_reason}).",
        "credit_budget_policy": "No model credits used by this deterministic response path.",
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
    headline_sentence = headline.rstrip(".!?")
    if blocker and blocker.lower() != "none":
        script = f"{headline_sentence}. Blocked by {blocker}. {next_action}"
    else:
        one_line = _sanitize_spoken_text(str(layered_fields.get("one_line_answer") or ""))
        if one_line.rstrip(".!?").lower() == headline_sentence.lower():
            script = f"{headline_sentence}. {next_action}"
        else:
            script = f"{headline_sentence}. {one_line} {next_action}".strip()
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


VISUAL_SUCCESS_EVENT_TYPES = {
    "SUCCESS_CONFIRMED",
    "COMPLETION_CONFIRMED",
}

VISUAL_FORBIDDEN_TEXT_PATTERNS = (
    "actual secret",
    "raw private body",
    "raw credential",
    "credential value",
    "token value",
    "password value",
    "raw email address",
    "provider id value",
    "/users/",
    "/home/",
    "/mnt/",
    "c:\\",
    "sha256:",
)


def _completion_receipts_present(response: OpenClawResponseForMac) -> bool:
    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    return bool(
        detail.get("completion_allowed") is True
        and (
            detail.get("all_required_receipts_present") is True
            or detail.get("completion_receipts_present") is True
            or detail.get("completion_label_status") == "COMPLETION_CONFIRMED"
        )
    )


def _visual_examples() -> Mapping[str, Any]:
    return chat_workflow_visual_event_package_compiler.build_examples()


def _sanitized_visual_package(
    package: Mapping[str, Any],
    *,
    response: OpenClawResponseForMac,
    layered_fields: Mapping[str, Any],
    voice_fields: Mapping[str, Any],
    allowed_visual_facts: tuple[str, ...] | None = None,
    forbidden_visual_claims: tuple[str, ...] | None = None,
    proof_refs: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    clean = dict(package)
    clean["source_response_ref"] = f"generated/read_models/{RESPONSE_JSON_EXPORT_NAME}"
    clean["workflow_ref"] = response.workflow_ref
    clean["response_author"] = str(voice_fields.get("response_author") or clean.get("response_author") or "OPENCLAW_SYSTEM")
    clean["agent_vibe"] = str(voice_fields.get("vibe_profile_ref") or clean.get("agent_vibe") or "vibe:system:neutral")
    clean["proof_refs"] = tuple(proof_refs if proof_refs is not None else layered_fields.get("proof_refs") or clean.get("proof_refs") or ())
    if allowed_visual_facts is not None:
        clean["allowed_visual_facts"] = allowed_visual_facts
    if forbidden_visual_claims is not None:
        clean["forbidden_visual_claims"] = tuple(dict.fromkeys(forbidden_visual_claims))

    provider = dict(clean.get("provider_policy") or {})
    provider["cloud_generation_allowed"] = False
    provider["local_asset_preferred"] = True
    provider.setdefault("preferred_provider_family", "STATIC_VISUAL_CARD")
    provider.setdefault("allowed_provider_families", ("MAC_ANIMATION_NATIVE", "STATIC_VISUAL_CARD"))
    provider.setdefault(
        "blocked_provider_families",
        ("VIDEO_MODEL_CLOUD_GATED", "IMAGE_MODEL_CLOUD_GATED", "UNKNOWN_FAIL_CLOSED"),
    )
    clean["provider_policy"] = provider
    return {
        "visual_package_id": str(clean.get("visual_package_id") or ""),
        "source_event_ref": str(clean.get("source_event_ref") or ""),
        "source_response_ref": str(clean.get("source_response_ref") or ""),
        "workflow_ref": str(clean.get("workflow_ref") or ""),
        "client_ref": str(clean.get("client_ref") or "client_ref:unknown_or_local"),
        "tenant_ref": str(clean.get("tenant_ref") or "tenant_ref:winship"),
        "response_author": str(clean.get("response_author") or "OPENCLAW_SYSTEM"),
        "agent_vibe": str(clean.get("agent_vibe") or "vibe:system:neutral"),
        "truth_state": str(clean.get("truth_state") or "UNKNOWN_FAIL_CLOSED"),
        "visual_event_type": str(clean.get("visual_event_type") or "UNKNOWN_FAIL_CLOSED"),
        "allowed_visual_facts": tuple(str(item) for item in clean.get("allowed_visual_facts") or ()),
        "forbidden_visual_claims": tuple(str(item) for item in clean.get("forbidden_visual_claims") or ()),
        "metaphor_style": str(clean.get("metaphor_style") or "lane_under_maintenance"),
        "style_direction": str(clean.get("style_direction") or "truth-backed static status only"),
        "duration_seconds": int(clean.get("duration_seconds") or 3),
        "aspect_ratio": str(clean.get("aspect_ratio") or "16:9"),
        "target_surface": str(clean.get("target_surface") or "MAC_CHAT_COMPACT"),
        "privacy_class": str(clean.get("privacy_class") or "OPERATOR_LOCAL"),
        "provider_policy": provider,
        "proof_refs": tuple(str(item) for item in clean.get("proof_refs") or ()),
        "next_safe_move": str(clean.get("next_safe_move") or "Render a local truth-backed visual status only."),
    }


def _visual_package_is_safe(response: OpenClawResponseForMac, package: Mapping[str, Any]) -> bool:
    event_type = str(package.get("visual_event_type") or "")
    if event_type in VISUAL_SUCCESS_EVENT_TYPES and not _completion_receipts_present(response):
        return False
    if event_type in VISUAL_SUCCESS_EVENT_TYPES and not tuple(package.get("proof_refs") or ()):
        return False
    provider = package.get("provider_policy")
    if not isinstance(provider, Mapping) or provider.get("cloud_generation_allowed") is not False:
        return False
    visible = stable_json(package).lower()
    if any(pattern in visible for pattern in VISUAL_FORBIDDEN_TEXT_PATTERNS):
        return False
    if "@" in visible:
        return False
    if event_type == "UNKNOWN_FAIL_CLOSED":
        return False
    return True


def _visual_event_package(
    response: OpenClawResponseForMac,
    layered_fields: Mapping[str, Any],
    voice_fields: Mapping[str, Any],
) -> dict[str, Any] | None:
    examples = _visual_examples()
    proof_refs = tuple(str(ref) for ref in layered_fields.get("proof_refs") or ())

    if _is_capital_hilton_status_response(response):
        package = _sanitized_visual_package(
            examples["capital_hilton_missing_po"]["visual_package"],
            response=response,
            layered_fields=layered_fields,
            voice_fields=voice_fields,
            allowed_visual_facts=("invoice basis exists", "Coupa PO/reference missing"),
            proof_refs=proof_refs,
        )
        return package if _visual_package_is_safe(response, package) else None

    if response.request_type == "FILE_METADATA":
        package = _sanitized_visual_package(
            examples["file_reference_captured"]["visual_package"],
            response=response,
            layered_fields=layered_fields,
            voice_fields=voice_fields,
            forbidden_visual_claims=(
                "file analyzed",
                "file body read",
                "file parsed",
                "OCR complete",
                "contents extracted",
            ),
            proof_refs=proof_refs,
        )
        return package if _visual_package_is_safe(response, package) else None

    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    interpreter = detail.get("deterministic_intent_interpreter") if isinstance(detail.get("deterministic_intent_interpreter"), Mapping) else {}
    if interpreter.get("visual_event_package_requested") is True:
        package = _sanitized_visual_package(
            {
                "visual_package_id": f"visual_package_{_short_hash(response.source_request_id, 'deterministic_intent')}",
                "source_event_ref": "deterministic_intent_interpreter",
                "truth_state": "SAFE_VISUAL_PACKAGE_ONLY",
                "visual_event_type": "SAFE_VISUAL_PACKAGE",
                "allowed_visual_facts": (
                    "safe visual event package available",
                    "live video provider blocked",
                    "no provider call occurred",
                ),
                "forbidden_visual_claims": (
                    "video generated",
                    "image generated",
                    "provider called",
                    "workflow completed",
                    "invoice sent",
                    "Coupa invoice submitted",
                ),
                "metaphor_style": "status_card_only",
                "style_direction": "truth-backed local status card only",
                "duration_seconds": 3,
                "aspect_ratio": "16:9",
                "target_surface": "MAC_CHAT_COMPACT",
                "privacy_class": "OPERATOR_LOCAL",
                "provider_policy": {
                    "preferred_provider_family": "STATIC_VISUAL_CARD",
                    "allowed_provider_families": ("STATIC_VISUAL_CARD",),
                    "blocked_provider_families": (
                        "VIDEO_MODEL_CLOUD_GATED",
                        "IMAGE_MODEL_CLOUD_GATED",
                        "UNKNOWN_FAIL_CLOSED",
                    ),
                    "cloud_generation_allowed": False,
                    "local_asset_preferred": True,
                },
                "next_safe_move": "Render a local truth-backed status card only.",
            },
            response=response,
            layered_fields=layered_fields,
            voice_fields=voice_fields,
            proof_refs=proof_refs,
        )
        return package if _visual_package_is_safe(response, package) else None

    if _completion_receipts_present(response):
        package = _sanitized_visual_package(
            examples["completion_confirmed_fixture"]["visual_package"],
            response=response,
            layered_fields=layered_fields,
            voice_fields=voice_fields,
            proof_refs=proof_refs,
        )
        return package if _visual_package_is_safe(response, package) else None

    return None


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
    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    explicit_layered = detail.get("layered_response_fields") if isinstance(detail.get("layered_response_fields"), Mapping) else None
    if explicit_layered is not None:
        fields = dict(explicit_layered)
        fields.setdefault("response_id", f"openclaw_response_{_short_hash(response.source_request_id, response.request_type, created_at)}")
        fields.setdefault("response_kind", "DETERMINISTIC_INTENT_RESPONSE")
        fields.setdefault("audience_mode", "ELIWINSHIP")
        fields.setdefault("display_mode", "COMPACT_CHAT")
        fields.setdefault("proof_refs", _safe_proof_refs(response))
        fields.setdefault("debug_refs", _debug_refs(response))
        fields.setdefault("raw_internal_status", response.internal_status)
        fields.setdefault("mac_render_hint", "COMPACT_WITH_DISCLOSURE")
        return _apply_cockpit_prose_limits(fields)

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


def _is_capital_hilton_mark_sent_status_question(raw_request: Mapping[str, Any]) -> bool:
    text = _capital_hilton_status_text(raw_request)
    return _is_capital_hilton_invoice_status_request(raw_request) and any(
        phrase in text
        for phrase in (
            "can we mark",
            "can i mark",
            "mark invoice sent",
            "invoice sent",
        )
    )


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


def _deterministic_intent_classification(
    classification: RequestClassification,
    *,
    match_id: str,
    request_path: Path,
) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, match_id, 'deterministic_intent')}",
        source_request_filename=classification.source_request_filename,
        request_family=classification.request_family,
        selected_rail="deterministic_intent_interpreter",
        classification_reason=(
            "Filename matches Mission Control chat request pattern, and operator text matched a bounded deterministic intent phrase."
        ),
        future_supported=False,
        next_safe_move="Return a validated non-executing intent response; do not dispatch workers or run workflows.",
    )


def _sheet_audit_classification(
    classification: RequestClassification,
    *,
    request_path: Path,
) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'client_invoice_sheet_audit')}",
        source_request_filename=classification.source_request_filename,
        request_family=classification.request_family,
        selected_rail="client_invoice_sheet_audit",
        classification_reason=(
            "Request explicitly set intended_use to client_invoice_sheet_audit, selecting the whitelisted invoice sheet audit rail."
        ),
        future_supported=False,
        next_safe_move="Return a terminal whitelisted sheet audit readback; do not run workflows or external actions.",
    )


def _audit_handoff_classification(
    classification: RequestClassification,
    *,
    request_path: Path,
) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'client_invoice_audit_handoff')}",
        source_request_filename=classification.source_request_filename,
        request_family=classification.request_family,
        selected_rail="client_invoice_audit_handoff",
        classification_reason=(
            "Request explicitly set a client invoice audit handoff intended_use, selecting the path/schema handoff rail."
        ),
        future_supported=False,
        next_safe_move="Record approved path/schema handoff contracts only; do not read workbook cells or run the audit.",
    )


def _local_surface_result_classification(
    classification: RequestClassification,
    *,
    request_path: Path,
    route_decision: Mapping[str, Any] | None = None,
) -> RequestClassification:
    selected_rail = str((route_decision or {}).get("selected_handler_id") or "local_surface_result_intake")
    reason = str(
        (route_decision or {}).get("rejected_reason")
        or "Request is a LOCAL_SURFACE_RESULT for client_invoice_sheet_schema_mapping, selecting the guided mapping intake rail."
    )
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'local_surface_schema_mapping_result')}",
        source_request_filename=classification.source_request_filename,
        request_family="LOCAL_SURFACE_RESULT",
        selected_rail=selected_rail,
        classification_reason=reason,
        future_supported=False,
        next_safe_move="Record operator-provided mapping guidance only; do not read workbook cells or run the audit.",
    )


def _classification_from_router_decision(
    classification: RequestClassification,
    *,
    request_path: Path,
    decision: Mapping[str, Any],
) -> RequestClassification:
    request_kind = str(decision.get("request_kind") or classification.request_family)
    if request_kind not in REQUEST_FAMILIES:
        request_kind = classification.request_family
    selected_rail = str(decision.get("selected_handler_id") or classification.selected_rail)
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, request_kind, selected_rail)}",
        source_request_filename=classification.source_request_filename,
        request_family=request_kind,
        selected_rail=selected_rail,
        classification_reason=(
            "Payload-level request router selected this request family/handler from request kind, intended_use, and scope."
        ),
        future_supported=False,
        next_safe_move=str(decision.get("next_safe_move") or classification.next_safe_move),
    )


def _maestro_frontdoor_classification(
    classification: RequestClassification,
    *,
    request_path: Path,
) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'maestro_frontdoor_chat')}",
        source_request_filename=classification.source_request_filename,
        request_family="CHAT",
        selected_rail="MAESTRO_CASSANDRA_RESPONDER",
        classification_reason=(
            "Payload is a general Maestro front-door operator instruction; selecting the gated Maestro "
            "Cassandra responder before workflow-package staging."
        ),
        future_supported=False,
        next_safe_move="Return the gated Maestro answer when available; otherwise keep default staging.",
    )


def _workflow_package_request_classification(classification: RequestClassification) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(classification.source_request_filename, 'workflow_package_request')}",
        source_request_filename=classification.source_request_filename,
        request_family="WORKFLOW_PACKAGE_REQUEST",
        selected_rail="workflow_package_request_consumer",
        classification_reason="Request envelope is a Mission Control WORKFLOW_PACKAGE_REQUEST_V0 operator instruction.",
        future_supported=False,
        next_safe_move="Record the instruction as a dry-run package queue item and return a Mac readback.",
    )


def _st_annes_work_log_review_action_classification(classification: RequestClassification) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(classification.source_request_filename, 'st_annes_work_log_review_action')}",
        source_request_filename=classification.source_request_filename,
        request_family="ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST",
        selected_rail="st_annes_work_log_review.action_consumer",
        classification_reason="Request envelope is a Mission Control St. Anne's work-log review action.",
        future_supported=False,
        next_safe_move="Record the bounded work-log review action and return a Mac readback.",
    )


def _workroom_review_decision_request_classification(classification: RequestClassification) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(classification.source_request_filename, 'workroom_review_decision')}",
        source_request_filename=classification.source_request_filename,
        request_family="WORKROOM_REVIEW_DECISION_REQUEST",
        selected_rail="workroom_review_decision_consumer",
        classification_reason="Request envelope is a Mission Control Workroom review decision.",
        future_supported=False,
        next_safe_move="Record the review decision receipt only and return a Mac readback.",
    )


def _process_workroom_review_decision_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
) -> OpenClawResponseForMac:
    bridge_export_root = (
        workroom_review_decision_consumer.DEFAULT_BRIDGE_EXPORT_ROOT
        if _same_path(export_root, DEFAULT_EXPORT_ROOT)
        else None
    )
    wiki_path = (
        workroom_review_decision_consumer.DEFAULT_WIKI_PATH
        if _same_path(export_root, DEFAULT_EXPORT_ROOT)
        else export_root.parent / "wiki" / "Workroom Review Decision Consumer.md"
    )
    result = workroom_review_decision_consumer.consume_workroom_review_decision_request(
        raw_request,
        source_request_filename=request_path.name,
        generated_at=generated_at,
        read_model_root=DEFAULT_EXPORT_ROOT,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        wiki_path=wiki_path,
    )
    receipt = result.receipt
    internal_status = str(receipt.get("raw_internal_status") or ("RESPONSE_READY" if result.status == "RECORDED" else "BLOCKED_WITH_REASON"))
    blocker = "; ".join(str(item) for item in receipt.get("blockers") or ())
    operator_display = dict(receipt.get("operator_display") or {})
    operator_display.setdefault("voice_profile_ref", f"agent_voice_profile:{operator_display.get('speaker_ref') or 'chief'}")
    headline = str(operator_display.get("headline") or "Review decision recorded")
    message = str(operator_display.get("plain_summary") or "Chief recorded the review decision only. No merge or push ran.")
    status_tone = str(operator_display.get("tone") or ("blocked" if blocker else "calm"))
    next_safe_action = str(operator_display.get("next_safe_action") or result.next_safe_action)
    response_classification = _workroom_review_decision_request_classification(classification)
    paths = receipt.get("read_model_paths") if isinstance(receipt.get("read_model_paths"), Mapping) else {}
    readback_files = tuple(
        str(path)
        for path in (
            paths.get("local_status_path"),
            paths.get("bridge_status_path"),
            paths.get("wiki_path"),
        )
        if path
    )
    packet_summary = receipt.get("review_packet_summary") if isinstance(receipt.get("review_packet_summary"), Mapping) else {}
    worker_ref = str(receipt.get("worker_ref") or packet_summary.get("worker_ref") or "")
    proof_refs = tuple(str(ref) for ref in receipt.get("proof_refs") or () if ref)
    layered_fields = {
        "response_kind": "WORKROOM_REVIEW_DECISION_RESPONSE",
        "audience_mode": "ELIWINSHIP",
        "display_mode": "COMPACT_CHAT",
        "operator_display": operator_display,
        "speaker_ref": str(operator_display.get("speaker_ref") or "chief"),
        "voice_profile_ref": str(operator_display.get("voice_profile_ref") or "agent_voice_profile:chief"),
        "voice_mode": str(operator_display.get("voice_mode") or "diagnostic"),
        "audience": str(operator_display.get("audience") or "internal_operator"),
        "routing_reason": str(operator_display.get("routing_reason") or ""),
        "headline": headline,
        "one_line_answer": message,
        "eliwinship": message,
        "primary_status": str(operator_display.get("status_label") or result.response_primary_status),
        "primary_blocker": blocker or "None",
        "next_action": f"Next: {next_safe_action}",
        "missing_items_short": tuple(str(item) for item in receipt.get("blockers") or ()),
        "detail_summary": (
            f"Review decision {receipt.get('decision_action')} returned {receipt.get('status')}. "
            "The consumer wrote a decision receipt only; no merge, push, worker spawn, or business action ran."
        ),
        "proof_refs": proof_refs,
        "debug_refs": readback_files,
        "raw_internal_status": internal_status,
        "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        "request_ref": result.request_id,
        "workflow_ref": workroom_review_decision_consumer.WORKFLOW_REF,
        "review_packet_id": str(receipt.get("review_packet_id") or ""),
        "decision_action": str(receipt.get("decision_action") or ""),
        "decision_status": str(receipt.get("status") or ""),
        "worker_ref": worker_ref,
        "worker_ref_is_speaker": False,
        "blocker": blocker,
        "no_external_authority_granted": True,
    }
    return OpenClawResponseForMac(
        source_request_id=result.request_id,
        source_request_filename=request_path.name,
        workflow_ref=workroom_review_decision_consumer.WORKFLOW_REF,
        request_type="WORKROOM_REVIEW_DECISION_REQUEST",
        internal_status=internal_status,
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC recognized a Mission Control Workroom review decision envelope.",
            "PC validated the review packet id, decision action, and authority boundary through the local consumer.",
            (
                "PC recorded a generated review decision receipt only."
                if result.status == "RECORDED"
                else "PC blocked the review decision before recording approval."
            ),
            "No merge, git push, worker spawn, child agent run, email, Gmail, browser, Coupa, workbook mutation, PDF export, ledger mutation, submit, paid marking, or business action occurred.",
        ),
        why_it_happened=(
            f"Review decision status: {receipt.get('status')}."
            if result.status == "RECORDED"
            else f"Review decision blockers: {blocker or 'unknown blocker'}."
        ),
        how_to_fix=next_safe_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    message,
                    f"Next: {next_safe_action}",
                ),
                "status_tone": status_tone,
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=readback_files,
        worker_route_refs=(
            {
                "selected_worker_target": "PC_CODEX",
                "selected_machine": "PC_WSL",
                "routing_status": "PROCESSING_ON_PC",
                "selected_rail": "workroom_review_decision_consumer",
                "review_packet_id": receipt.get("review_packet_id") or "",
                "decision_action": receipt.get("decision_action") or "",
                "decision_status": receipt.get("status") or "",
                "worker_ref": worker_ref,
                "worker_ref_is_speaker": False,
            },
        ),
        context_package_refs=(),
        blocked_reason=blocker or None,
        detail_disclosure={
            "request_classification": asdict(response_classification),
            "workroom_review_decision_consumer": receipt,
            "operator_display": operator_display,
            "review_packet_summary": packet_summary,
            "live_worker_executed": False,
            "worker_spawn_performed": False,
            "merge_performed": False,
            "git_push_performed": False,
            "business_state_mutation_performed": False,
            "external_actions_locked": True,
            "layered_response_fields": layered_fields,
        },
        readback_files=readback_files,
        next_safe_move=next_safe_action,
    )


def _process_st_annes_work_log_review_action_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
) -> OpenClawResponseForMac:
    bridge_export_root = (
        st_annes_work_log_review.DEFAULT_BRIDGE_EXPORT_ROOT
        if _same_path(export_root, DEFAULT_EXPORT_ROOT)
        else None
    )
    result = st_annes_work_log_review.consume_review_action_request(
        raw_request,
        source_request_filename=request_path.name,
        generated_at=generated_at,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
    )
    receipt = result.receipt
    action = str(receipt.get("review_action") or raw_request.get("review_action") or "")
    event_id = str(receipt.get("event_id") or raw_request.get("event_id") or "")
    internal_status = str(receipt.get("raw_internal_status") or ("RESPONSE_READY" if result.status == "RECORDED" else "BLOCKED_WITH_REASON"))
    blocker = str(receipt.get("blocked_reason") or "")
    operator_display = dict(receipt.get("operator_display") or {})
    operator_display.setdefault("voice_profile_ref", f"agent_voice_profile:{operator_display.get('speaker_ref') or 'openclaw'}")
    headline = str(operator_display.get("headline") or "St. Anne's work-log review updated")
    message = str(operator_display.get("plain_summary") or "I processed the local work-log review action. No external action ran.")
    status_tone = str(operator_display.get("tone") or ("blocked" if blocker else "calm"))
    next_safe_action = str(operator_display.get("next_safe_action") or result.next_safe_action)
    response_classification = _st_annes_work_log_review_action_classification(classification)
    paths = receipt.get("read_model_paths") if isinstance(receipt.get("read_model_paths"), Mapping) else {}
    readback_files = tuple(
        str(path)
        for path in (
            paths.get("events_read_model_path"),
            paths.get("review_surface_path"),
            paths.get("bridge_events_read_model_path"),
            paths.get("bridge_review_surface_path"),
        )
        if path
    )
    layered_fields = {
        "response_kind": "ST_ANNES_WORK_LOG_REVIEW_ACTION_RESPONSE",
        "audience_mode": "ELIWINSHIP",
        "display_mode": "COMPACT_CHAT",
        "operator_display": operator_display,
        "speaker_ref": str(operator_display.get("speaker_ref") or "openclaw"),
        "voice_profile_ref": str(operator_display.get("voice_profile_ref") or "agent_voice_profile:openclaw"),
        "voice_mode": str(operator_display.get("voice_mode") or "operator_calm"),
        "audience": str(operator_display.get("audience") or "internal_operator"),
        "routing_reason": str(operator_display.get("routing_reason") or operator_display.get("voice_routing_reason") or ""),
        "headline": headline,
        "one_line_answer": message,
        "eliwinship": message,
        "primary_status": str(operator_display.get("status_label") or ("Done" if result.status == "RECORDED" else "Blocked")),
        "primary_blocker": blocker or "None",
        "next_action": f"Next: {next_safe_action}",
        "missing_items_short": (blocker,) if blocker else (),
        "detail_summary": (
            f"Review action {action or 'unknown'} for event {event_id or 'unknown'} returned {receipt.get('review_status')}. "
            "Only St. Anne's work-log SQLite/read-model state was eligible to change."
        ),
        "proof_refs": readback_files,
        "debug_refs": (),
        "raw_internal_status": internal_status,
        "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        "request_ref": result.request_id,
        "workflow_ref": st_annes_work_log_review.intake.WORKFLOW_REF,
        "client_ref": st_annes_work_log_review.intake.CLIENT_REF,
        "review_action": action,
        "event_id": event_id,
        "review_status": str(receipt.get("review_status") or ""),
        "event_status": str(receipt.get("event_status") or ""),
        "invoice_inclusion_status": str(receipt.get("invoice_inclusion_status") or ""),
        "operator_confirmed": bool(receipt.get("operator_confirmed") is True),
        "blocker": blocker,
        "no_external_authority_granted": True,
    }
    return OpenClawResponseForMac(
        source_request_id=result.request_id,
        source_request_filename=request_path.name,
        workflow_ref=st_annes_work_log_review.intake.WORKFLOW_REF,
        request_type="ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST",
        internal_status=internal_status,
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC recognized a Mission Control St. Anne's work-log review action envelope.",
            "PC validated source surface, operator mode, receipt requirement, event id, review action, and false authority boundaries.",
            (
                "PC updated only the St. Anne's work-log event state."
                if result.status == "RECORDED"
                else "PC blocked the review action before changing a work-log event."
            ),
            "No Telegram live connection, Excel, invoice creation, PDF export, email, Gmail, browser, Coupa, ledger mutation, paid marking, submit, or external business action occurred.",
        ),
        why_it_happened=(
            f"Review action {action} produced {receipt.get('review_status')} for event {event_id}."
            if result.status == "RECORDED"
            else f"Review action blockers: {blocker or 'unknown blocker'}."
        ),
        how_to_fix=next_safe_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    str(operator_display.get("subheadline") or "Saved for operator review."),
                    str(operator_display.get("primary_fact") or "No external action ran."),
                    *tuple(str(item) for item in operator_display.get("secondary_facts") or ()),
                    f"Next: {next_safe_action}",
                ),
                "status_tone": status_tone,
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=readback_files,
        worker_route_refs=(
            {
                "selected_worker_target": "PC_CODEX",
                "selected_machine": "PC_WSL",
                "routing_status": "PROCESSING_ON_PC",
                "selected_rail": "st_annes_work_log_review.action_consumer",
                "workflow_ref": st_annes_work_log_review.intake.WORKFLOW_REF,
                "client_ref": st_annes_work_log_review.intake.CLIENT_REF,
                "review_action": action,
                "event_id": event_id,
            },
        ),
        context_package_refs=(),
        blocked_reason=blocker or None,
        detail_disclosure={
            "request_classification": asdict(response_classification),
            "st_annes_work_log_review_action_consumer": receipt,
            "operator_display": operator_display,
            "review_result": receipt,
            "live_worker_executed": False,
            "business_state_mutation_performed": False,
            "external_actions_locked": True,
            "layered_response_fields": layered_fields,
        },
        readback_files=readback_files,
        next_safe_move=next_safe_action,
    )


def _process_workflow_package_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None,
    classification: RequestClassification,
    lm1_shared_seam: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    result = workflow_package_request_consumer.consume_workflow_package_request(
        raw_request,
        source_request_filename=request_path.name,
        generated_at=generated_at,
        lm1_shared_seam=lm1_shared_seam,
    )
    receipt = result.receipt
    package = result.package or {}
    package_status = str(receipt.get("package_status") or "NOT_CREATED")
    workflow_ref = str(receipt.get("workflow_ref") or raw_request.get("workflow_ref") or "unknown")
    client_ref = receipt.get("client_ref")
    capability_status = str(receipt.get("capability_gate_status") or "NOT_EVALUATED")
    receipt_proof_refs = list(receipt.get("proof_refs") or [])
    current_world_ref = str(receipt.get("current_world_ref") or "")
    current_thread_ref = str(receipt.get("current_thread_ref") or "")
    target_world_ref = str(receipt.get("target_world_ref") or "")
    target_thread_ref = str(receipt.get("target_thread_ref") or "")
    cross_lane_routed = bool(receipt.get("cross_lane_routed") is True)
    routing_note = str(receipt.get("routing_note") or "")
    package_recorded = result.package is not None
    system_question_answered = (
        workflow_ref == "system_question_answer"
        and str(receipt.get("raw_internal_status") or "") == "RESPONSE_READY"
    )
    response_ready = package_recorded or system_question_answered
    internal_status = "RESPONSE_READY" if response_ready else "BLOCKED_WITH_REASON"
    blocker = str(receipt.get("blocker") or "")
    operator_display = (
        dict(receipt.get("operator_display"))
        if isinstance(receipt.get("operator_display"), Mapping)
        else {
            "headline": "Workflow package staged" if package_recorded else "Instruction needs a safety fix",
            "subheadline": "Saved for operator review." if package_recorded else "The request envelope did not pass local checks.",
            "status_label": "Needs review" if package_recorded else "Blocked",
            "tone": "calm" if package_recorded else "blocked",
            "plain_summary": (
                "I staged this as a dry-run package. No business action ran."
                if package_recorded
                else "I could not stage this instruction because the safe request envelope is incomplete."
            ),
            "next_safe_action": result.next_safe_action,
            "why_it_matters": "Operator review separates captured intent from live execution.",
            "primary_fact": "No external action ran.",
            "secondary_facts": ("No email will be sent.", "No ledger entry was touched."),
            "proof_caption": "Proof available",
            "show_machine_details_by_default": False,
            "speaker_ref": "openclaw",
            "voice_profile_ref": "agent_voice_profile:openclaw",
            "voice_mode": "operator_calm",
            "audience": "internal_operator",
            "routing_reason": "neutral cockpit/system orientation",
        }
    )
    operator_display.setdefault("voice_profile_ref", f"agent_voice_profile:{operator_display.get('speaker_ref') or 'openclaw'}")
    headline = str(operator_display.get("headline") or "Workflow package staged")
    message = str(operator_display.get("plain_summary") or "I staged this as a dry-run package. No business action ran.")
    status_tone = str(operator_display.get("tone") or ("blocked" if blocker else "calm"))
    next_safe_action = str(operator_display.get("next_safe_action") or result.next_safe_action)
    response_classification = _workflow_package_request_classification(classification)
    layered_fields = {
        "response_kind": "WORKFLOW_PACKAGE_REQUEST_RESPONSE",
        "audience_mode": "ELIWINSHIP",
        "display_mode": "COMPACT_CHAT",
        "operator_display": operator_display,
        "speaker_ref": str(operator_display.get("speaker_ref") or "openclaw"),
        "voice_mode": str(operator_display.get("voice_mode") or "operator_calm"),
        "audience": str(operator_display.get("audience") or "internal_operator"),
        "routing_reason": str(operator_display.get("routing_reason") or operator_display.get("voice_routing_reason") or ""),
        "headline": headline,
        "one_line_answer": message,
        "eliwinship": message,
        "primary_status": str(operator_display.get("status_label") or ("Needs review" if package_recorded else "Blocked")),
        "primary_blocker": blocker or "None",
        "next_action": f"Next: {next_safe_action}",
        "missing_items_short": (blocker,) if blocker else (),
        "detail_summary": (
            "System question answered from local read models, wiki refs, and SQLite metadata; no package queue row was written."
            if system_question_answered
            else (
                f"Package status {package_status}; capability gate {capability_status}. "
                "The queue recorded only a no-op worker result and a closed business action gate."
            )
        ),
        "proof_refs": receipt_proof_refs,
        "debug_refs": (),
        "raw_internal_status": internal_status,
        "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        "request_ref": result.request_id,
        "package_id": str(receipt.get("package_id") or ""),
        "workflow_ref": workflow_ref,
        "client_ref": client_ref,
        "package_status": package_status,
        "current_world_ref": current_world_ref,
        "current_thread_ref": current_thread_ref,
        "target_world_ref": target_world_ref,
        "target_thread_ref": target_thread_ref,
        "cross_lane_routed": cross_lane_routed,
        "routing_note": routing_note,
        "blocker": blocker,
        "no_external_authority_granted": True,
    }
    return OpenClawResponseForMac(
        source_request_id=result.request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type="WORKFLOW_PACKAGE_REQUEST",
        internal_status=internal_status,
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC recognized a Mission Control WORKFLOW_PACKAGE_REQUEST_V0 envelope.",
            "PC validated source surface, operator mode, receipt requirement, and false authority boundaries.",
            (
                "PC detected system-question intent and routed it to the local system_question_answer workflow."
                if system_question_answered
                else "PC routed the instruction into the Workflow Package Queue V0 dry-run registry."
            ),
            (
                "PC returned a speaker-shaped operator display with proof refs collapsed."
                if system_question_answered
                else "PC returned a scoped Mac response with the package status."
            ),
            "No Telegram live connection, email, Gmail, browser, Coupa, workbook mutation, PDF export, ledger mutation, submit, paid marking, or business-state mutation occurred.",
        ),
        why_it_happened=(
            "System-question intent matched the local deterministic answer workflow."
            if system_question_answered
            else (
            f"Workflow Package Queue classified the instruction as {workflow_ref} with package status {package_status}."
            if package_recorded
            else f"Envelope validation blockers: {blocker}."
            )
        ),
        how_to_fix=next_safe_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    message,
                    f"Next: {next_safe_action}",
                ),
                "status_tone": status_tone,
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": "PC_CODEX",
                "selected_machine": "PC_WSL",
                "routing_status": "PROCESSING_ON_PC",
                "selected_rail": "workflow_package_request_consumer",
                "package_id": receipt.get("package_id") or "",
                "workflow_ref": workflow_ref,
                "current_world_ref": current_world_ref,
                "current_thread_ref": current_thread_ref,
                "target_world_ref": target_world_ref,
                "target_thread_ref": target_thread_ref,
                "cross_lane_routed": cross_lane_routed,
                "routing_note": routing_note,
                "package_status": package_status,
                "capability_gate_status": capability_status,
                "noop_worker_only": not system_question_answered,
                "system_question_answer_local_only": system_question_answered,
            },
        ),
        context_package_refs=(),
        blocked_reason=blocker or None,
        detail_disclosure={
            "request_classification": asdict(response_classification),
            "workflow_package_request_consumer": receipt,
            "lm1_shared_request_seam": _lm1_shared_request_seam_summary(lm1_shared_seam),
            "package": package,
            "system_question_answer": receipt.get("system_question_answer") if system_question_answered else None,
            "operator_display": operator_display,
            "package_queue_sqlite_path": receipt.get("sqlite_path"),
            "source_request_metadata": package.get("source_request_metadata") if isinstance(package, Mapping) else None,
            "live_worker_executed": False,
            "business_state_mutation_performed": False,
            "external_actions_locked": True,
            "layered_response_fields": layered_fields,
        },
        readback_files=(),
        next_safe_move=next_safe_action,
    )


def _process_client_invoice_audit_handoff_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
) -> OpenClawResponseForMac | None:
    if not client_invoice_audit_handoff.is_audit_handoff_request(raw_request):
        return None

    handoff_payload = client_invoice_audit_handoff.process_handoff_request(
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
    )
    handoff_json, handoff_operator = client_invoice_audit_handoff.write_exports(handoff_payload, export_root)
    readback = handoff_payload["audit_handoff_readback"]
    live_ready = bool(handoff_payload["live_audit_ready"])
    handoff_classification = _audit_handoff_classification(classification, request_path=request_path)
    headline = str(readback["operator_headline"])
    message = str(readback["operator_message"])
    next_action = str(readback["next_action"])
    missing_items = tuple(str(item) for item in readback.get("missing_items") or ())
    primary_blocker = "None" if live_ready else (missing_items[0] if missing_items else str(readback["status"]))
    detail = {
        "client_invoice_audit_handoff": {
            "handoff_readback_ref": handoff_json.as_posix(),
            "operator_readback_ref": handoff_operator.as_posix(),
            "path_approval_request": handoff_payload["path_approval_request"],
            "schema_mapping_request": handoff_payload["schema_mapping_request"],
            "approved_workbook_path_ref": handoff_payload.get("approved_workbook_path_ref") or {},
            "schema_mapping": handoff_payload.get("schema_mapping") or {},
            "formula_promotion_policy": handoff_payload["formula_promotion_policy"],
            "audit_handoff_readback": readback,
            "live_audit_ready": live_ready,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "schema_inference_performed": False,
            "mac_path_translation_guessed": False,
            "formula_evaluation_performed": False,
            "external_action_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "CLIENT_INVOICE_AUDIT_HANDOFF",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": str(readback["status"]).replace("_", " ").title(),
            "primary_blocker": primary_blocker,
            "next_action": next_action,
            "missing_items_short": missing_items,
            "detail_summary": (
                f"Path: {readback.get('path_approval_status')}. "
                f"Schema: {readback.get('schema_mapping_status')}. "
                f"Ready: {live_ready}."
            ),
            "proof_refs": (f"generated/read_models/{client_invoice_audit_handoff.JSON_EXPORT_NAME}",),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(handoff_classification),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or readback["hidden_refs"]["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
        request_type=classification.request_family,
        internal_status="RESPONSE_READY" if live_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC selected the client invoice audit handoff rail.",
            "PC recorded only approved path/schema contract data.",
            "PC did not open a workbook, read spreadsheet cells, infer schema, translate a Mac path, evaluate formulas, or run the audit.",
        ),
        why_it_happened=(
            "The handoff now has a workbook record, approved PC-readable path/ref, and explicit sheet mapping."
            if live_ready
            else "The handoff is still missing at least one required gate before the sheet audit can run."
        ),
        how_to_fix="No fix is needed. Run the whitelisted sheet audit when ready." if live_ready else next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    f"Path: {readback.get('path_approval_status')}",
                    f"Schema: {readback.get('schema_mapping_status')}",
                    f"Formula policy: {readback.get('formula_policy_status')}",
                    next_action,
                ),
                "status_tone": "ready" if live_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(handoff_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if live_ready else primary_blocker,
        detail_disclosure=detail,
        readback_files=(handoff_json.as_posix(), handoff_operator.as_posix()),
        next_safe_move=next_action,
    )


def _process_local_surface_result_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    local_classification = _local_surface_result_classification(
        classification,
        request_path=request_path,
        route_decision=route_decision,
    )
    if not client_invoice_audit_handoff.is_local_surface_schema_mapping_result(raw_request):
        return OpenClawResponseForMac(
            source_request_id=str(raw_request.get("request_id") or "unknown_local_surface_result"),
            source_request_filename=request_path.name,
            workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
            request_type=classification.request_family,
            internal_status="BLOCKED_WITH_REASON",
            operator_headline="Local result not supported",
            operator_message="OpenClaw received a local surface result, but this processor only accepts invoice sheet mapping results in this lane.",
            what_happened=("PC validated the local surface result envelope.", "No local result was applied."),
            why_it_happened="The intended_use or result kind did not match client_invoice_sheet_schema_mapping.",
            how_to_fix="Resend a LOCAL_SURFACE_RESULT with intended_use=client_invoice_sheet_schema_mapping.",
            visible_cards=(),
            cards_available=False,
            card_mirror_refs=(),
            file_readback_refs=(),
            worker_route_refs=(),
            context_package_refs=(),
            blocked_reason="Unsupported local surface result.",
            detail_disclosure={"request_classification": asdict(local_classification)},
            readback_files=(),
            next_safe_move="Next: resend a supported local field mapping result.",
        )

    handoff_payload = client_invoice_audit_handoff.process_local_surface_schema_mapping_result(
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
    )
    handoff_json, handoff_operator = client_invoice_audit_handoff.write_exports(handoff_payload, export_root)
    readback = handoff_payload["audit_handoff_readback"]
    receipt = handoff_payload.get("local_surface_result_receipt") if isinstance(handoff_payload.get("local_surface_result_receipt"), Mapping) else {}
    schema_request = handoff_payload["schema_mapping_request"]
    live_ready = bool(handoff_payload["live_audit_ready"])
    schema_captured = schema_request.get("validation_status") == "SHEET_AUDIT_SCHEMA_CAPTURED"
    validation_errors = tuple(str(item) for item in receipt.get("validation_errors") or ())
    missing_mapping_fields = tuple(str(item) for item in receipt.get("missing_mapping_fields") or ())
    missing_items = missing_mapping_fields or tuple(str(item) for item in readback.get("missing_items") or ())
    primary_blocker = "None" if live_ready else (missing_items[0] if missing_items else str(readback["status"]))
    headline = str(readback["operator_headline"])
    if validation_errors:
        message = str(readback["operator_message"])
    elif schema_captured and live_ready:
        message = (
            "OpenClaw captured the operator-confirmed invoice field mapping as schema guidance. "
            "It did not read the workbook body or cells. The whitelisted audit is now ready."
        )
    elif schema_captured:
        message = (
            "OpenClaw captured the operator-confirmed invoice field mapping as schema guidance. "
            "It did not read the workbook body or cells. It still needs approved PC-readable workbook access before audit."
        )
    elif missing_mapping_fields:
        message = (
            "OpenClaw received the operator-confirmed field mapping, but it is missing required mapping fields: "
            + ", ".join(missing_mapping_fields)
            + "."
        )
    else:
        message = str(readback["operator_message"])
    operator_message = (
        "Field mapping captured as schema guidance. Workbook cells were not read."
        if not validation_errors
        else "Field mapping result blocked before any workbook or cell read."
    )
    next_action = str(readback["next_action"])
    detail = {
        "client_invoice_audit_handoff": {
            "handoff_readback_ref": handoff_json.as_posix(),
            "operator_readback_ref": handoff_operator.as_posix(),
            "path_approval_request": handoff_payload["path_approval_request"],
            "schema_mapping_request": schema_request,
            "approved_workbook_path_ref": handoff_payload.get("approved_workbook_path_ref") or {},
            "schema_mapping": handoff_payload.get("schema_mapping") or {},
            "formula_promotion_policy": handoff_payload["formula_promotion_policy"],
            "audit_handoff_readback": readback,
            "local_surface_result_receipt": receipt,
            "live_audit_ready": live_ready,
            "operator_provided_schema_guidance": bool(receipt.get("mapping_classification") == "operator_provided_schema_guidance"),
            "verified_sheet_data": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "schema_inference_performed": False,
            "mac_path_translation_guessed": False,
            "formula_evaluation_performed": False,
            "external_action_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "LOCAL_SURFACE_SCHEMA_MAPPING_RESULT",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": str(readback["status"]).replace("_", " ").title(),
            "primary_blocker": primary_blocker,
            "next_action": next_action,
            "missing_items_short": missing_items,
            "detail_summary": (
                f"Schema: {readback.get('schema_mapping_status')}. "
                f"Ready: {live_ready}. "
                "Mapping is operator-provided guidance, not verified sheet data."
            ),
            "proof_refs": (f"generated/read_models/{client_invoice_audit_handoff.JSON_EXPORT_NAME}",),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(local_classification),
        "request_router_decision": dict(route_decision or {}),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or readback["hidden_refs"]["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
        request_type=classification.request_family,
        internal_status="RESPONSE_READY" if live_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=operator_message,
        what_happened=(
            "PC consumed the local surface field mapping result.",
            "PC recorded the mapping as operator-provided schema guidance only.",
            "PC did not open a workbook, read spreadsheet cells, run OCR, call a model, or run the audit.",
        ),
        why_it_happened=(
            "The local surface result was operator-provided, operator-confirmed, and all read/action safety flags were false."
            if not validation_errors
            else "The local surface result failed a required safety, confirmation, or binding check."
        ),
        how_to_fix="No fix is needed. Run the whitelisted sheet audit when ready." if live_ready else next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    "Mapping stored as operator-provided schema guidance.",
                    "Workbook body and cells were not read.",
                    f"Ready for audit: {live_ready}.",
                    next_action,
                ),
                "status_tone": "ready" if live_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(handoff_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if live_ready else primary_blocker,
        detail_disclosure=detail,
        readback_files=(handoff_json.as_posix(), handoff_operator.as_posix()),
        next_safe_move=next_action,
    )


def _artifact_approval_classification(
    classification: RequestClassification,
    *,
    request_path: Path,
    route_decision: Mapping[str, Any] | None = None,
) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'approve_readable_artifact_reference')}",
        source_request_filename=classification.source_request_filename,
        request_family=str((route_decision or {}).get("request_kind") or classification.request_family),
        selected_rail=str((route_decision or {}).get("selected_handler_id") or "approve_readable_artifact_reference.generic"),
        classification_reason="Generic request router selected the approved readable artifact reference rail.",
        future_supported=False,
        next_safe_move="Persist the artifact approval receipt and recompute downstream readiness without opening the artifact.",
    )


def _is_artifact_reference_approval_route(route_decision: Mapping[str, Any]) -> bool:
    return str(route_decision.get("selected_handler_id") or "") == "approve_readable_artifact_reference.generic"


def _process_artifact_reference_approval_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    approval_classification = _artifact_approval_classification(
        classification,
        request_path=request_path,
        route_decision=route_decision,
    )
    if not local_artifact_reference.is_artifact_approval_request(raw_request):
        return OpenClawResponseForMac(
            source_request_id=str(raw_request.get("request_id") or "unknown_artifact_approval"),
            source_request_filename=request_path.name,
            workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
            request_type=approval_classification.request_family,
            internal_status="BLOCKED_WITH_REASON",
            operator_headline="Artifact approval blocked",
            operator_message="OpenClaw received an artifact approval request, but the request kind or intended use did not match the approved contract.",
            what_happened=("PC routed the request to artifact approval intake.", "No artifact approval was recorded."),
            why_it_happened="The request must use kind/type LOCAL_SURFACE_RESULT or ARTIFACT_REFERENCE_APPROVAL with intended_use=approve_readable_artifact_reference.",
            how_to_fix="Resend the artifact approval request with the supported kind and intended_use.",
            visible_cards=(),
            cards_available=False,
            card_mirror_refs=(),
            file_readback_refs=(),
            worker_route_refs=(),
            context_package_refs=(),
            blocked_reason="Unsupported artifact approval request.",
            detail_disclosure={
                "request_classification": asdict(approval_classification),
                "request_router_decision": dict(route_decision or {}),
                "external_actions_locked": True,
            },
            readback_files=(),
            next_safe_move="Next: resend a supported artifact approval request.",
        )

    expected_scope = {
        "world_ref": str(raw_request.get("world_ref") or ""),
        "workflow_ref": str(raw_request.get("workflow_ref") or ""),
        "client_ref": str(raw_request.get("client_ref") or ""),
        "project_ref": str(raw_request.get("project_ref") or ""),
    }
    artifact_payload = local_artifact_reference.evaluate_artifact_reference(
        raw_request,
        expected_scope=expected_scope,
        artifact_kind_default=str(raw_request.get("artifact_kind") or "local_artifact"),
        intended_use_default=str(raw_request.get("artifact_intended_use") or "local_artifact_reference"),
        generated_at=generated_at,
    )
    artifact_json, artifact_operator = local_artifact_reference.write_exports(artifact_payload, export_root)
    readiness = artifact_payload["artifact_readiness_state"]
    receipt = artifact_payload["artifact_approval_receipt"]
    approved_artifact = artifact_payload.get("approved_readable_artifact") or {}
    artifact_ready = bool(readiness.get("live_read_ready"))

    handoff_payload: Mapping[str, Any] | None = None
    handoff_json: Path | None = None
    handoff_operator: Path | None = None
    handoff_readback: Mapping[str, Any] = {}
    target_use = str(raw_request.get("artifact_intended_use") or raw_request.get("target_intended_use") or "")
    if target_use == "client_invoice_sheet_audit" or str(raw_request.get("artifact_kind") or "") in {"invoice_workbook", "spreadsheet_workbook"}:
        handoff_payload = client_invoice_audit_handoff.process_handoff_request(
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
        )
        handoff_json, handoff_operator = client_invoice_audit_handoff.write_exports(dict(handoff_payload), export_root)
        handoff_readback = handoff_payload["audit_handoff_readback"]

    handoff_live_ready = bool((handoff_payload or {}).get("live_audit_ready"))
    missing_items = tuple(
        str(item)
        for item in (
            (handoff_readback.get("missing_items") if handoff_readback else None)
            or readiness.get("missing_items")
            or readiness.get("blocking_reasons")
            or ()
        )
    )
    primary_blocker = "None" if (artifact_ready and not missing_items) or handoff_live_ready else (missing_items[0] if missing_items else str(readiness["readiness_status"]))
    if handoff_live_ready:
        headline = str(handoff_readback["operator_headline"])
        message = (
            "OpenClaw approved the scoped PC-readable artifact reference and found the existing field mapping. "
            "It did not read the workbook body or cells. The whitelisted audit is ready."
        )
        next_action = str(handoff_readback["next_action"])
    elif artifact_ready:
        client_ref = str(raw_request.get("client_ref") or "")
        client_name = "Capital Hilton" if client_ref == "capital_hilton" else str(raw_request.get("artifact_label") or "Artifact")
        headline = f"{client_name} artifact approved" if client_ref != "capital_hilton" else "Capital Hilton workbook approved"
        message = "OpenClaw recorded the approved PC-readable artifact reference. It did not read the artifact body or extract content."
        next_action = str((handoff_readback or {}).get("next_action") or "Next: provide the missing workflow context.")
    else:
        headline = "Artifact approval blocked"
        message = "OpenClaw did not approve the artifact reference because a required scope, approval, path, or read-only safety gate failed."
        next_action = "Next: resend the artifact approval with matching scope, verified PC-readable path, and read-only flags."
    detail = {
        "local_artifact_reference": {
            "artifact_readback_ref": artifact_json.as_posix(),
            "operator_readback_ref": artifact_operator.as_posix(),
            "local_artifact_reference": artifact_payload["local_artifact_reference"],
            "approved_readable_artifact": approved_artifact,
            "artifact_approval_receipt": receipt,
            "artifact_readiness_state": readiness,
            "artifact_ready": artifact_ready,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "content_extracted": False,
            "external_action_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "APPROVED_READABLE_ARTIFACT_REFERENCE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": str(readiness["readiness_status"]).replace("_", " ").title(),
            "primary_blocker": primary_blocker,
            "next_action": next_action,
            "missing_items_short": missing_items,
            "detail_summary": f"Artifact ready: {artifact_ready}. Audit ready: {handoff_live_ready}.",
            "proof_refs": (artifact_json.as_posix(),)
            + ((handoff_json.as_posix(),) if handoff_json is not None else ()),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(approval_classification),
        "request_router_decision": dict(route_decision or {}),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    if handoff_payload is not None:
        detail["client_invoice_audit_handoff"] = {
            "handoff_readback_ref": handoff_json.as_posix() if handoff_json else "",
            "operator_readback_ref": handoff_operator.as_posix() if handoff_operator else "",
            "path_approval_request": handoff_payload["path_approval_request"],
            "schema_mapping_request": handoff_payload["schema_mapping_request"],
            "approved_workbook_path_ref": handoff_payload.get("approved_workbook_path_ref") or {},
            "approved_readable_artifact": handoff_payload.get("approved_readable_artifact") or {},
            "schema_mapping": handoff_payload.get("schema_mapping") or {},
            "audit_handoff_readback": handoff_readback,
            "live_audit_ready": handoff_live_ready,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "schema_inference_performed": False,
            "mac_path_translation_guessed": False,
            "external_action_performed": False,
        }
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or receipt["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
        request_type=approval_classification.request_family,
        internal_status="RESPONSE_READY" if artifact_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC consumed the artifact approval request through the generic router.",
            "PC recorded only scoped artifact reference approval and readiness metadata.",
            "PC did not open the artifact, read workbook cells, run OCR, call a model, or run the audit.",
        ),
        why_it_happened=(
            "The artifact reference matched the requested scope and passed the read-only approval gates."
            if artifact_ready
            else "The artifact reference failed a scope, approval, path, or read-only gate."
        ),
        how_to_fix="No fix is needed. Run the whitelisted sheet audit when ready." if handoff_live_ready else next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    f"Artifact ready: {artifact_ready}.",
                    f"Audit ready: {handoff_live_ready}.",
                    "Artifact body and cells were not read.",
                    next_action,
                ),
                "status_tone": "ready" if artifact_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(artifact_json.as_posix(),) + ((handoff_json.as_posix(),) if handoff_json is not None else ()),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if artifact_ready else primary_blocker,
        detail_disclosure=detail,
        readback_files=(artifact_json.as_posix(), artifact_operator.as_posix())
        + ((handoff_json.as_posix(), handoff_operator.as_posix()) if handoff_json is not None and handoff_operator is not None else ()),
        next_safe_move=next_action,
    )


def _is_artifact_intake_route(route_decision: Mapping[str, Any]) -> bool:
    return str(route_decision.get("selected_handler_id") or "") == "register_or_resolve_invoice_workbook_artifact.generic"


def _is_invoice_review_action_route(route_decision: Mapping[str, Any], raw_request: Mapping[str, Any]) -> bool:
    return (
        str(route_decision.get("selected_handler_id") or "") == "invoice_review_action_request.capital_hilton"
        or invoice_review_action_request_handler.is_invoice_review_action_request(raw_request)
    )


def _is_invoice_record_selection_result_route(route_decision: Mapping[str, Any], raw_request: Mapping[str, Any]) -> bool:
    return (
        str(route_decision.get("selected_handler_id") or "") == "invoice_record_selection_result.capital_hilton"
        or invoice_review_action_request_handler.is_invoice_record_selection_result(raw_request)
    )


def _is_source_workbook_selection_result_route(route_decision: Mapping[str, Any], raw_request: Mapping[str, Any]) -> bool:
    return (
        str(route_decision.get("selected_handler_id") or "") == "source_workbook_selection_result.capital_hilton"
        or invoice_review_action_request_handler.is_source_workbook_selection_result(raw_request)
    )



def _is_selected_invoice_pdf_export_completed_candidate_result_route(route_decision: Mapping[str, Any], raw_request: Mapping[str, Any]) -> bool:
    return (
        str(route_decision.get("selected_handler_id") or "") == "selected_invoice_pdf_export_completed_candidate.live_arts_md"
        or invoice_review_action_request_handler.is_selected_invoice_pdf_export_completed_candidate_result(raw_request)
    )

def _invoice_review_action_classification(
    classification: RequestClassification,
    *,
    request_path: Path,
    route_decision: Mapping[str, Any] | None = None,
) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'invoice_review_action_request')}",
        source_request_filename=classification.source_request_filename,
        request_family=classification.request_family,
        selected_rail=str((route_decision or {}).get("selected_handler_id") or "invoice_review_action_request.capital_hilton"),
        classification_reason="Generic request router selected the invoice review guided action rail.",
        future_supported=False,
        next_safe_move="Return guided fix-path copy without external action authority.",
    )


def _process_invoice_record_selection_result_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    action_classification = RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'invoice_record_selection_result')}",
        source_request_filename=classification.source_request_filename,
        request_family=str((route_decision or {}).get("request_kind") or classification.request_family),
        selected_rail=str((route_decision or {}).get("selected_handler_id") or "invoice_record_selection_result.capital_hilton"),
        classification_reason="Request is an operator-provided invoice record selection result.",
        future_supported=False,
        next_safe_move="Record the invoice page/period labels without workbook or cell reads.",
    )
    default_export_root = invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_EXPORT_ROOT.resolve()
    bridge_export_root = (
        invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT
        if export_root.resolve() == default_export_root
        else None
    )
    db_path = (
        invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_DB_PATH
        if export_root.resolve() == default_export_root
        else export_root.parent / "invoice_review_state.sqlite"
    )
    event_db_path = (
        invoice_review_action_request_handler.operator_action_event_journal.DEFAULT_DB_PATH
        if export_root.resolve() == default_export_root
        else export_root.parent / "operator_action_events.sqlite"
    )
    payload = invoice_review_action_request_handler.process_invoice_record_selection_result_request(
        raw_request,
        generated_at=generated_at,
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        event_db_path=event_db_path,
        event_export_root=export_root,
    )
    action_json, action_operator = invoice_review_action_request_handler.write_exports(payload, export_root)
    status = str(payload["status"])
    response_ready = status == "GUIDED_RESULT_RECORDED"
    headline = str(payload["headline"])
    body = str(payload["body"])
    next_action = str(payload["next_action"])
    receipt = payload["action_start_receipt"]
    state_progress = payload.get("state_machine_progress") if isinstance(payload.get("state_machine_progress"), Mapping) else {}
    local_surface_result = payload.get("local_surface_result") if isinstance(payload.get("local_surface_result"), Mapping) else {}
    detail = {
        "invoice_record_selection_result": {
            "readback_ref": action_json.as_posix(),
            "operator_readback_ref": action_operator.as_posix(),
            "action_kind": payload["action_kind"],
            "status": status,
            "selection_receipt": receipt,
            "state_machine_progress": state_progress,
            "local_surface_result": dict(local_surface_result),
            "refreshed_bundle_path": state_progress.get("source_bundle_path"),
            "bridge_bundle_path": state_progress.get("bridge_bundle_path"),
            "bridge_mirror_written": bool(state_progress.get("bridge_mirror_written")),
            "external_action_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "ocr_performed": False,
            "invoice_generation_performed": False,
            "artifact_linked": False,
            "attachment_ready": False,
            "approval_ready": False,
        },
        "layered_response_fields": {
            "response_kind": "INVOICE_RECORD_SELECTION_RESULT_RESPONSE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": body,
            "eliwinship": body,
            "primary_status": status.replace("_", " ").title(),
            "primary_blocker": "None" if response_ready else status,
            "next_action": next_action,
            "missing_items_short": tuple(payload.get("expected_receipt_types") or ()),
            "detail_summary": str(payload["detail"]),
            "proof_refs": (receipt["receipt_id"], action_json.as_posix()),
            "refreshed_bundle_path": state_progress.get("source_bundle_path"),
            "bridge_bundle_path": state_progress.get("bridge_bundle_path"),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(action_classification),
        "request_router_decision": dict(route_decision or {}),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=str(payload["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "capital_hilton_invoice_workflow"),
        request_type=classification.request_family,
        internal_status="RESPONSE_READY" if response_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=body,
        what_happened=(
            "PC consumed the invoice record selection result.",
            "PC recorded only operator-provided page/period labels.",
            "PC refreshed the invoice review bundle.",
            "PC did not read workbook cells, generate invoices, link artifacts, send, submit, or mutate production state.",
        ),
        why_it_happened=str(payload["detail"]),
        how_to_fix=next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    body,
                    next_action,
                    "No workbook body or cells were read.",
                ),
                "status_tone": "ready" if response_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(action_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if response_ready else status,
        detail_disclosure=detail,
        readback_files=(action_json.as_posix(), action_operator.as_posix()),
        next_safe_move=next_action,
    )


def _process_source_workbook_selection_result_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    action_classification = RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'source_workbook_selection_result')}",
        source_request_filename=classification.source_request_filename,
        request_family=str((route_decision or {}).get("request_kind") or classification.request_family),
        selected_rail=str((route_decision or {}).get("selected_handler_id") or "source_workbook_selection_result.capital_hilton"),
        classification_reason="Request is an operator-provided source workbook selection result.",
        future_supported=False,
        next_safe_move="Record the source workbook reference without workbook or cell reads.",
    )
    default_export_root = invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_EXPORT_ROOT.resolve()
    bridge_export_root = (
        invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT
        if export_root.resolve() == default_export_root
        else None
    )
    db_path = (
        invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_DB_PATH
        if export_root.resolve() == default_export_root
        else export_root.parent / "invoice_review_state.sqlite"
    )
    event_db_path = (
        invoice_review_action_request_handler.operator_action_event_journal.DEFAULT_DB_PATH
        if export_root.resolve() == default_export_root
        else export_root.parent / "operator_action_events.sqlite"
    )
    payload = invoice_review_action_request_handler.process_source_workbook_selection_result_request(
        raw_request,
        generated_at=generated_at,
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        event_db_path=event_db_path,
        event_export_root=export_root,
    )
    action_json, action_operator = invoice_review_action_request_handler.write_exports(payload, export_root)
    status = str(payload["status"])
    response_ready = status == "GUIDED_RESULT_RECORDED"
    headline = str(payload["headline"])
    body = str(payload["body"])
    next_action = str(payload["next_action"])
    receipt = payload["action_start_receipt"]
    state_progress = payload.get("state_machine_progress") if isinstance(payload.get("state_machine_progress"), Mapping) else {}
    detail = {
        "source_workbook_selection_result": {
            "readback_ref": action_json.as_posix(),
            "operator_readback_ref": action_operator.as_posix(),
            "action_kind": payload["action_kind"],
            "status": status,
            "selection_receipt": receipt,
            "state_machine_progress": state_progress,
            "local_surface_result": dict(payload.get("local_surface_result") or {}),
            "refreshed_bundle_path": state_progress.get("source_bundle_path"),
            "bridge_bundle_path": state_progress.get("bridge_bundle_path"),
            "bridge_mirror_written": bool(state_progress.get("bridge_mirror_written")),
            "external_action_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "invoice_generation_performed": False,
            "artifact_linked": False,
            "attachment_ready": False,
            "approval_ready": False,
        },
        "layered_response_fields": {
            "response_kind": "SOURCE_WORKBOOK_SELECTION_RESULT_RESPONSE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": body,
            "eliwinship": body,
            "primary_status": status.replace("_", " ").title(),
            "primary_blocker": "None" if response_ready else status,
            "next_action": next_action,
            "proof_refs": (receipt["receipt_id"], action_json.as_posix()),
            "refreshed_bundle_path": state_progress.get("source_bundle_path"),
            "bridge_bundle_path": state_progress.get("bridge_bundle_path"),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(action_classification),
        "request_router_decision": dict(route_decision or {}),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=str(payload["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "capital_hilton_invoice_workflow"),
        request_type=classification.request_family,
        internal_status="RESPONSE_READY" if response_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=body,
        what_happened=(
            "PC consumed the source workbook selection result.",
            "PC recorded only the operator-provided workbook reference.",
            "PC refreshed the invoice review bundle.",
            "PC did not read workbook cells, generate invoices, send, submit, or mutate production state.",
        ),
        why_it_happened=str(payload["detail"]),
        how_to_fix=next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (body, next_action, "No workbook body or cells were read."),
                "status_tone": "ready" if response_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(action_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if response_ready else status,
        detail_disclosure=detail,
        readback_files=(action_json.as_posix(), action_operator.as_posix()),
        next_safe_move=next_action,
    )



def _process_selected_invoice_pdf_export_completed_result_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    payload = invoice_review_action_request_handler.process_selected_invoice_pdf_export_completed_candidate_result_request(
        raw_request,
        generated_at=generated_at,
        export_root=export_root,
        bridge_export_root=invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT if export_root.resolve() == invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_EXPORT_ROOT.resolve() else None,
    )
    action_json, action_operator = invoice_review_action_request_handler.write_exports(payload, export_root)
    status = str(payload["status"])
    result_recorded = status in {"GUIDED_RESULT_RECORDED", "GUIDED_FAILURE_RECORDED"}
    failure_recorded = status == "GUIDED_FAILURE_RECORDED"
    receipt = payload["action_start_receipt"]
    state_progress = payload.get("state_machine_progress") or {}
    local_surface_result = payload.get("local_surface_result") if isinstance(payload.get("local_surface_result"), Mapping) else {}

    detail = {
        "pdf_export_completed_result": {
            "readback_ref": action_json.as_posix(),
            "operator_readback_ref": action_operator.as_posix(),
            "status": status,
            "receipt": receipt,
            "state_machine_progress": state_progress,
            "local_surface_result": dict(local_surface_result),
            "attachment_ready": False,
            "approval_ready": False,
            "ledger_posting_allowed": False,
        }
    }

    return OpenClawResponseForMac(
        source_request_id=payload["source_request_id"],
        source_request_filename=request_path.name,
        workflow_ref="live_arts_md_invoice_workflow",
        request_type="LOCAL_SURFACE_RESULT",
        internal_status="RESPONSE_READY" if result_recorded and not failure_recorded else "BLOCKED_WITH_REASON",
        operator_headline=(
            "PDF Export Candidate Recorded"
            if result_recorded and not failure_recorded
            else "PDF Export Failed"
            if failure_recorded
            else "PDF Export Blocked"
        ),
        operator_message=payload["body"],
        what_happened=(
            "Validated PDF result",
            "Recorded the Mac helper failure receipt without promoting the artifact.",
        )
        if failure_recorded
        else ("Validated PDF result",),
        why_it_happened=(
            str(receipt.get("failure_message") or receipt.get("failure_code") or "Mac helper reported export failure.")
            if failure_recorded
            else "Valid"
            if result_recorded
            else "Invalid"
        ),
        how_to_fix=payload["next_action"] if failure_recorded else "Provide valid PDF." if not result_recorded else "Proceed to operator review.",
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(action_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if result_recorded and not failure_recorded else str(receipt.get("failure_code") or "Invalid pdf export"),
        detail_disclosure=detail,
        readback_files=(action_json.as_posix(),),
        next_safe_move=payload["next_action"],
    )

def _process_invoice_review_action_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    action_classification = _invoice_review_action_classification(
        classification,
        request_path=request_path,
        route_decision=route_decision,
    )
    default_export_root = invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_EXPORT_ROOT.resolve()
    bridge_export_root = (
        invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT
        if export_root.resolve() == default_export_root
        else None
    )
    db_path = (
        invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_DB_PATH
        if export_root.resolve() == default_export_root
        else export_root.parent / "invoice_review_state.sqlite"
    )
    event_db_path = (
        invoice_review_action_request_handler.operator_action_event_journal.DEFAULT_DB_PATH
        if export_root.resolve() == default_export_root
        else export_root.parent / "operator_action_events.sqlite"
    )
    payload = invoice_review_action_request_handler.process_action_request(
        raw_request,
        generated_at=generated_at,
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        event_db_path=event_db_path,
        event_export_root=export_root,
    )
    action_json, action_operator = invoice_review_action_request_handler.write_exports(payload, export_root)
    status = str(payload["status"])
    response_ready = status in {"GUIDED_ACTION_STARTED", "GUIDED_RESULT_RECORDED"}
    headline = str(payload["headline"])
    body = str(payload["body"])
    detail_text = str(payload["detail"])
    operator_body = body if detail_text in body else f"{body} {detail_text}"
    next_action = str(payload["next_action"])
    receipt = payload["action_start_receipt"]
    operator_event = payload.get("operator_action_event") if isinstance(payload.get("operator_action_event"), Mapping) else None
    operator_event_journal = payload.get("operator_action_event_journal") if isinstance(payload.get("operator_action_event_journal"), Mapping) else {}
    state_progress = payload.get("state_machine_progress") if isinstance(payload.get("state_machine_progress"), Mapping) else {}
    local_surface_request = payload.get("local_surface_request") if isinstance(payload.get("local_surface_request"), Mapping) else None
    completion_written = bool(payload.get("machine_proof", {}).get("completion_receipt_written")) if isinstance(payload.get("machine_proof"), Mapping) else False
    blocker_completed = bool(payload.get("machine_proof", {}).get("underlying_blocker_completed")) if isinstance(payload.get("machine_proof"), Mapping) else False
    detail = {
        "invoice_review_action_request": {
            "readback_ref": action_json.as_posix(),
            "operator_readback_ref": action_operator.as_posix(),
            "action_kind": payload["action_kind"],
            "status": status,
            "action_start_receipt": receipt,
            "operator_action_event": dict(operator_event) if operator_event else None,
            "operator_action_event_journal": dict(operator_event_journal),
            "state_machine_progress": state_progress,
            "local_surface_request": dict(local_surface_request) if local_surface_request else None,
            "expected_receipt_types": payload["expected_receipt_types"],
            "underlying_blocker_completed": blocker_completed,
            "completion_receipt_written": completion_written,
            "refreshed_bundle_path": state_progress.get("source_bundle_path"),
            "bridge_bundle_path": state_progress.get("bridge_bundle_path"),
            "bridge_mirror_written": bool(state_progress.get("bridge_mirror_written")),
            "external_action_performed": False,
            "email_send_performed": False,
            "coupa_browser_automation_performed": False,
            "ledger_posting_performed": False,
            "invoice_generation_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "INVOICE_REVIEW_ACTION_RESPONSE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": operator_body,
            "eliwinship": operator_body,
            "primary_status": status.replace("_", " ").title(),
            "primary_blocker": "None" if response_ready else status,
            "next_action": next_action,
            "missing_items_short": tuple(_ for _ in payload.get("expected_receipt_types") or ()),
            "detail_summary": detail_text,
            "proof_refs": (receipt["receipt_id"], action_json.as_posix()),
            "refreshed_bundle_path": state_progress.get("source_bundle_path"),
            "bridge_bundle_path": state_progress.get("bridge_bundle_path"),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
            "local_surface_request": dict(local_surface_request) if local_surface_request else None,
        },
        "request_classification": asdict(action_classification),
        "request_router_decision": dict(route_decision or {}),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=str(payload["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "capital_hilton_invoice_workflow"),
        request_type=classification.request_family,
        internal_status="RESPONSE_READY" if response_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=operator_body,
        what_happened=(
            "PC consumed the invoice review action request.",
            "PC validated the bundle, workflow, client, action, and no-external-action boundary.",
            "PC wrote a guided action receipt/readback and refreshed the invoice review bundle.",
            "PC did not perform any external action.",
        ),
        why_it_happened=str(payload["detail"]),
        how_to_fix=next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    operator_body,
                    next_action,
                    "Nothing was sent, submitted, generated, read from a workbook, posted, or changed in production.",
                ),
                "status_tone": "ready" if response_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(action_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if response_ready else status,
        detail_disclosure=detail,
        readback_files=(action_json.as_posix(), action_operator.as_posix()),
        next_safe_move=next_action,
    )


def _artifact_intake_classification(
    classification: RequestClassification,
    *,
    request_path: Path,
    route_decision: Mapping[str, Any] | None = None,
) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(request_path.name, 'register_or_resolve_invoice_workbook_artifact')}",
        source_request_filename=classification.source_request_filename,
        request_family=str((route_decision or {}).get("request_kind") or classification.request_family),
        selected_rail=str((route_decision or {}).get("selected_handler_id") or "register_or_resolve_invoice_workbook_artifact.generic"),
        classification_reason="Generic request router selected the register or resolve invoice workbook artifact rail.",
        future_supported=False,
        next_safe_move="Consume Mac artifact intake package and resolve PC-readable reference safely.",
    )


def _artifact_intake_operator_copy(
    *,
    resolution_status: str,
    validation_errors: tuple[str, ...],
    artifact_ready: bool,
    handoff_live_ready: bool,
    client_ref: str,
    next_action_from_handoff: str,
) -> tuple[str, str, str, tuple[str, ...]]:
    client_label = "Capital Hilton" if client_ref == "capital_hilton" else "invoice"
    if resolution_status == "APPROVED_PC_PATH_CAPTURED":
        headline = f"{client_label} workbook received" if client_ref == "capital_hilton" else "Workbook received"
        if handoff_live_ready:
            return (
                headline,
                "OpenClaw received the workbook and found the invoice field map. It is ready for the next safe step.",
                "Next: run the whitelisted invoice sheet audit.",
                (),
            )
        return (
            headline,
            "OpenClaw received the workbook and kept it sealed. The workbook body and cells were not read.",
            next_action_from_handoff or "Next: tell OpenClaw where the invoice fields are.",
            (),
        )
    if resolution_status == "ARTIFACT_APPROVAL_REQUIRED":
        return (
            "Workbook confirmation needed",
            "OpenClaw received the workbook, but it still needs one confirmation before audit.",
            "Next: confirm the workbook in the Mac app.",
            ("workbook confirmation",),
        )
    if resolution_status in {"ARTIFACT_WRITE_AUTHORITY_BLOCKED", "ARTIFACT_BODY_OR_CONTENT_ALREADY_READ_BLOCKED"}:
        return (
            "Workbook handoff blocked",
            "OpenClaw could not use this workbook handoff because it included work outside this safe step.",
            "Next: choose the workbook again in the Mac app without reading or editing it.",
            ("safe workbook handoff",),
        )
    if resolution_status == "ARTIFACT_PATH_TRANSLATION_GUESSED_BLOCKED":
        return (
            "Workbook handoff blocked",
            "OpenClaw could not use a guessed workbook location. Please choose the workbook again in the Mac app.",
            "Next: choose the workbook again in the Mac app.",
            ("workbook handoff",),
        )
    joined_errors = " ".join(validation_errors).lower()
    if "outside the approved bridge" in joined_errors:
        return (
            "Workbook outside OpenClaw bridge",
            "The workbook was outside the approved OpenClaw bridge. Please choose it again in the Mac app.",
            "Next: choose the workbook again in the Mac app.",
            ("OpenClaw bridge copy",),
        )
    if "request-scoped package layout" in joined_errors or "source_request_id" in joined_errors:
        return (
            "Workbook package incomplete",
            "OpenClaw received the workbook request, but the workbook copy was incomplete.",
            "Next: choose the workbook again in the Mac app.",
            ("workbook copy",),
        )
    if "path_mapping_verified" in joined_errors:
        return (
            "Workbook confirmation needed",
            "OpenClaw received the workbook request, but the Mac app still needs to confirm the safe handoff.",
            "Next: choose the workbook again in the Mac app.",
            ("workbook handoff confirmation",),
        )
    if "artifact scope binding required" in joined_errors or "workflow_ref=" in joined_errors or "client_ref=" in joined_errors:
        return (
            "Which workflow is this for?",
            "OpenClaw received the workbook, but it needs the client and workflow before using it.",
            "Next: choose the workbook again from the correct workflow in the Mac app.",
            ("client or workflow",),
        )
    if resolution_status == "WORKBOOK_NOT_SPREADSHEET":
        return (
            "Workbook type not supported",
            "OpenClaw received a file, but it does not look like a supported invoice workbook.",
            "Next: choose an Excel or CSV workbook in the Mac app.",
            ("supported workbook file",),
        )
    if resolution_status == "WORKBOOK_NOT_FOUND":
        return (
            "OpenClaw could not receive the workbook",
            "OpenClaw did not find the workbook copy in the approved bridge.",
            "Next: choose the workbook again in the Mac app.",
            ("workbook copy",),
        )
    return (
        "OpenClaw could not receive the workbook",
        "OpenClaw could not use this workbook handoff yet. Please choose the workbook again in the Mac app.",
        "Next: choose the workbook again in the Mac app.",
        ("workbook handoff",) if not artifact_ready else (),
    )


def _process_artifact_intake_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    intake_classification = _artifact_intake_classification(
        classification,
        request_path=request_path,
        route_decision=route_decision,
    )

    expected_scope = {
        "world_ref": str(raw_request.get("world_ref") or ""),
        "workflow_ref": str(raw_request.get("workflow_ref") or ""),
        "client_ref": str(raw_request.get("client_ref") or ""),
        "project_ref": str(raw_request.get("project_ref") or ""),
    }

    artifact_payload = local_artifact_reference.evaluate_artifact_reference(
        raw_request,
        expected_scope=expected_scope,
        artifact_kind_default=str(raw_request.get("artifact_kind") or "invoice_workbook"),
        intended_use_default=str(raw_request.get("intended_use") or "register_or_resolve_invoice_workbook_artifact"),
        generated_at=generated_at,
    )
    artifact_json, artifact_operator = local_artifact_reference.write_exports(artifact_payload, export_root)
    readiness = artifact_payload["artifact_readiness_state"]
    receipt = artifact_payload["artifact_resolution_receipt"]
    approved_artifact = artifact_payload.get("approved_readable_artifact") or {}
    artifact_ready = bool(readiness.get("live_read_ready"))

    handoff_payload: Mapping[str, Any] | None = None
    handoff_json: Path | None = None
    handoff_operator: Path | None = None
    handoff_readback: Mapping[str, Any] = {}
    target_use = str(raw_request.get("artifact_intended_use") or raw_request.get("target_intended_use") or "")
    if target_use == "client_invoice_sheet_audit" or str(raw_request.get("artifact_kind") or "") in {"invoice_workbook", "spreadsheet_workbook"}:
        handoff_payload = client_invoice_audit_handoff.process_handoff_request(
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
        )
        handoff_json, handoff_operator = client_invoice_audit_handoff.write_exports(dict(handoff_payload), export_root)
        handoff_readback = handoff_payload["audit_handoff_readback"]

    handoff_live_ready = bool((handoff_payload or {}).get("live_audit_ready"))
    res_status = receipt.get("resolution_status")

    headline, message, next_action, operator_missing_items = _artifact_intake_operator_copy(
        resolution_status=str(res_status or ""),
        validation_errors=tuple(str(item) for item in receipt.get("validation_errors") or ()),
        artifact_ready=artifact_ready,
        handoff_live_ready=handoff_live_ready,
        client_ref=expected_scope.get("client_ref") or "",
        next_action_from_handoff=str((handoff_readback or {}).get("next_action") or ""),
    )
    display_missing_items = operator_missing_items or (() if artifact_ready or handoff_live_ready else ("workbook handoff",))
    primary_blocker = "None" if (artifact_ready and not display_missing_items) or handoff_live_ready else (display_missing_items[0] if display_missing_items else "workbook handoff")

    detail = {
        "local_artifact_reference": {
            "artifact_readback_ref": artifact_json.as_posix(),
            "operator_readback_ref": artifact_operator.as_posix(),
            "local_artifact_reference": artifact_payload["local_artifact_reference"],
            "approved_readable_artifact": approved_artifact,
            "artifact_approval_receipt": artifact_payload["artifact_approval_receipt"],
            "artifact_readiness_state": readiness,
            "artifact_intake_request": artifact_payload.get("artifact_intake_request"),
            "artifact_intake_package": artifact_payload.get("artifact_intake_package"),
            "artifact_resolution_receipt": receipt,
            "artifact_ready": artifact_ready,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "content_extracted": False,
            "external_action_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "APPROVED_READABLE_ARTIFACT_REFERENCE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": str(readiness["readiness_status"]).replace("_", " ").title(),
            "primary_blocker": primary_blocker,
            "next_action": next_action,
            "missing_items_short": display_missing_items,
            "detail_summary": f"Artifact ready: {artifact_ready}. Audit ready: {handoff_live_ready}.",
            "proof_refs": (artifact_json.as_posix(),)
            + ((handoff_json.as_posix(),) if handoff_json is not None else ()),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(intake_classification),
        "request_router_decision": dict(route_decision or {}),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }

    if handoff_payload is not None:
        detail["client_invoice_audit_handoff"] = {
            "handoff_readback_ref": handoff_json.as_posix() if handoff_json else "",
            "operator_readback_ref": handoff_operator.as_posix() if handoff_operator else "",
            "path_approval_request": handoff_payload["path_approval_request"],
            "schema_mapping_request": handoff_payload["schema_mapping_request"],
            "approved_workbook_path_ref": handoff_payload.get("approved_workbook_path_ref") or {},
            "approved_readable_artifact": handoff_payload.get("approved_readable_artifact") or {},
            "schema_mapping": handoff_payload.get("schema_mapping") or {},
            "audit_handoff_readback": handoff_readback,
            "live_audit_ready": handoff_live_ready,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "schema_inference_performed": False,
            "mac_path_translation_guessed": False,
            "external_action_performed": False,
        }

    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or receipt["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
        request_type=intake_classification.request_family,
        internal_status="RESPONSE_READY" if artifact_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "OpenClaw received the workbook handoff from Mission Control.",
            "OpenClaw checked the approved workbook bridge copy and request scope.",
            "OpenClaw used only request metadata and filesystem metadata; it did not read cells, parse spreadsheets, or invoke models.",
        ),
        why_it_happened=(
            "The workbook arrived through the approved OpenClaw bridge and the Mac app marked it for this workflow."
            if artifact_ready
            else "The workbook copy is missing or did not match the safe Mission Control handoff."
        ),
        how_to_fix="No fix is needed. Run the whitelisted sheet audit when ready." if handoff_live_ready else next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    f"Workbook status: {res_status.replace('_', ' ').title()}",
                    message,
                    f"Audit ready: {handoff_live_ready}.",
                    next_action,
                ),
                "status_tone": "ready" if artifact_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(artifact_json.as_posix(),) + ((handoff_json.as_posix(),) if handoff_json is not None else ()),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if artifact_ready else primary_blocker,
        detail_disclosure=detail,
        readback_files=(artifact_json.as_posix(), artifact_operator.as_posix())
        + ((handoff_json.as_posix(), handoff_operator.as_posix()) if handoff_json is not None and handoff_operator is not None else ()),
        next_safe_move=next_action,
    )


def _evidence_response_card(record: Mapping[str, Any]) -> dict[str, Any]:
    card = dict(record.get("dynamic_card") or {})
    summary = "This appears to show payment processing. Ledger remains untouched until payment is confirmed."
    card["headline"] = "Payment proof received"
    card["summary"] = summary
    card["plain_summary"] = summary
    card["status_label"] = "Processing evidence"
    card["trust_state"] = str(card.get("trust_state") or "operator_reported")
    card["authority_boundary"] = dict(evidence_intake.AUTHORITY_BOUNDARY)
    card.setdefault("machine_proof", {})
    card["machine_proof"].update(
        {
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
        }
    )
    return card


def _process_evidence_intake_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any],
) -> OpenClawResponseForMac:
    generated_at = generated_at or utc_now()
    record = evidence_intake.record_evidence_intake(
        raw_request,
        sqlite_path=evidence_intake.DEFAULT_SQLITE_PATH,
        artifact_lineage_sqlite_path=evidence_intake.DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
        generated_at=generated_at,
    )
    request_id = str(raw_request.get("request_id") or raw_request.get("request_hash") or f"missing_request_id_{request_path.stem}")
    workflow_ref = str(raw_request.get("claimed_workflow_ref") or raw_request.get("workflow_ref") or "evidence_intake")
    if record.get("status") == evidence_intake.VERIFICATION_REQUIRED_STATUS:
        return OpenClawResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=workflow_ref,
            request_type=classification.request_family,
            internal_status="BLOCKED_WITH_REASON",
            operator_headline="Operator verification required",
            operator_message="Mission Control needs a verified operator envelope before this evidence can be recorded.",
            what_happened=(
                "OpenClaw recognized an evidence intake request.",
                "The operator envelope was missing, incomplete, unverified, or hash-invalid.",
                "No evidence row, ledger mutation, paid marking, OCR, provider call, or external action occurred.",
            ),
            why_it_happened=evidence_intake.VERIFICATION_REQUIRED_STATUS,
            how_to_fix="Resend the evidence request with operator_ref, app_instance_ref, device_ref, session_ref, request_hash, created_at, source_surface=mission_control, and operator_verified=true.",
            visible_cards=(),
            cards_available=False,
            card_mirror_refs=(),
            file_readback_refs=(),
            worker_route_refs=(),
            context_package_refs=(),
            blocked_reason=evidence_intake.VERIFICATION_REQUIRED_STATUS,
            detail_disclosure={
                "request_classification": asdict(classification),
                "request_router_decision": dict(route_decision),
                "evidence_intake": {
                    "status": record.get("status"),
                    "blockers": record.get("blockers") or (),
                    "candidate_evidence_recorded": False,
                    "ledger_mutation_performed": False,
                    "paid_marking_performed": False,
                    "raw_ocr_text_stored": False,
                    "external_provider_connected": False,
                },
            },
            readback_files=(),
            next_safe_move="Resend with a verified operator envelope.",
        )

    if record.get("status") != evidence_intake.READY_STATUS:
        return OpenClawResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=workflow_ref,
            request_type=classification.request_family,
            internal_status="BLOCKED_WITH_REASON",
            operator_headline="Evidence intake blocked",
            operator_message="OpenClaw recognized the evidence request, but it did not pass the local intake checks.",
            what_happened=(
                "OpenClaw validated the evidence request locally.",
                "The request was blocked before evidence recording.",
                "No ledger mutation, paid marking, OCR, provider call, or external action occurred.",
            ),
            why_it_happened=" ".join(str(item) for item in record.get("blockers") or ("EVIDENCE_INTAKE_REQUEST_BLOCKED",)),
            how_to_fix="Fix the evidence request fields and resend with all authority boundary values false.",
            visible_cards=(),
            cards_available=False,
            card_mirror_refs=(),
            file_readback_refs=(),
            worker_route_refs=(),
            context_package_refs=(),
            blocked_reason=str(record.get("status") or "EVIDENCE_INTAKE_REQUEST_BLOCKED"),
            detail_disclosure={
                "request_classification": asdict(classification),
                "request_router_decision": dict(route_decision),
                "evidence_intake": {
                    "status": record.get("status"),
                    "blockers": record.get("blockers") or (),
                    "candidate_evidence_recorded": False,
                    "ledger_mutation_performed": False,
                    "paid_marking_performed": False,
                    "raw_ocr_text_stored": False,
                    "external_provider_connected": False,
                },
            },
            readback_files=(),
            next_safe_move="Fix the evidence request and retry.",
        )

    publish_result = evidence_intake.publish_evidence_intake_status(
        record,
        export_root=export_root,
        bridge_root=evidence_intake.DEFAULT_BRIDGE_ROOT,
        wiki_path=evidence_intake.DEFAULT_WIKI_PATH,
        sqlite_path=evidence_intake.DEFAULT_SQLITE_PATH,
        artifact_lineage_sqlite_path=evidence_intake.DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
        generated_at=generated_at,
    )
    card = _evidence_response_card(record)
    layered_fields = {
        "response_id": f"openclaw_response_{_short_hash(request_id, evidence_intake.REQUEST_TYPE, generated_at)}",
        "response_kind": "EVIDENCE_INTAKE_DYNAMIC_CARD",
        "audience_mode": "ELIWINSHIP",
        "display_mode": "COMPACT_CHAT",
        "headline": "Payment proof received",
        "one_line_answer": "This appears to show payment processing. Ledger remains untouched until payment is confirmed.",
        "eliwinship": "OpenClaw recorded this as payment-processing evidence only. It is not paid proof, and nothing touched the ledger.",
        "primary_status": "Processing evidence",
        "primary_blocker": "Payment is not confirmed",
        "next_action": "Next: Review the evidence card.",
        "missing_items_short": ("Payment or ledger confirmation",),
        "detail_summary": "Verified operator evidence intake recorded candidate evidence locally with financial-sensitive, local-only handling.",
        "proof_refs": ("generated/read_models/evidence_intake_status.json",),
        "debug_refs": ("generated/read_models/evidence_intake_status.json",),
        "raw_internal_status": "RESPONSE_READY",
        "mac_render_hint": "DYNAMIC_CARD_WITH_DISCLOSURE",
    }
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type=classification.request_family,
        internal_status="RESPONSE_READY",
        operator_headline="Payment proof received",
        operator_message="This appears to show payment processing. Ledger remains untouched until payment is confirmed.",
        what_happened=(
            "OpenClaw validated the verified operator envelope.",
            "Candidate evidence was recorded and attached to the current world/thread.",
            "A dynamic card response is ready for Mission Control.",
        ),
        why_it_happened="The request type is EVIDENCE_INTAKE_REQUEST_V0 and the authority boundary stayed false.",
        how_to_fix="No fix is needed. Keep watching for payment or ledger confirmation before any paid or ledger action.",
        visible_cards=(card,),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=("generated/read_models/evidence_intake_status.json",),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={
            "request_classification": asdict(classification),
            "request_router_decision": dict(route_decision),
            "layered_response_fields": layered_fields,
            "evidence_intake": {
                "status": record.get("status"),
                "evidence_status": record.get("evidence_status"),
                "artifact_ref": record.get("artifact_ref"),
                "current_world_ref": record.get("current_world_ref"),
                "current_thread_ref": record.get("current_thread_ref"),
                "claimed_client_ref": record.get("claimed_client_ref"),
                "privacy": record.get("privacy"),
                "payment": record.get("payment"),
                "dynamic_card": card,
                "publish_result": publish_result,
                "candidate_evidence_recorded": True,
                "ledger_mutation_performed": False,
                "paid_marking_performed": False,
                "raw_ocr_text_stored": False,
                "external_provider_connected": False,
                "external_llm_invoked": False,
                "local_model_runtime_connected": False,
            },
        },
        readback_files=("generated/read_models/evidence_intake_status.json",),
        next_safe_move="Review the evidence card and wait for payment or ledger confirmation before paid truth.",
    )


def _controller_event_dynamic_card(receipt: Mapping[str, Any]) -> dict[str, Any]:
    card = dict(receipt.get("dynamic_card_response") or {})
    if not card:
        card = {
            "schema_version": "operator_controller_dynamic_card_response_v0",
            "card_id": f"dynamic_card.operator_controller_event.{_short_hash(receipt.get('receipt_id'), 'fallback')}",
            "card_type": "controller_event_response",
            "headline": "Controller event processed",
            "plain_summary": "OpenClaw processed the controller event without business execution.",
            "summary": "OpenClaw processed the controller event without business execution.",
            "status_label": str(receipt.get("route_status") or "Controller event"),
        }
    card.setdefault("controller_event_type", str(receipt.get("controller_event_type") or ""))
    card.setdefault("authority_boundary", dict(operator_controller_event_router.AUTHORITY_BOUNDARY))
    card.setdefault("machine_proof", {})
    card["machine_proof"].update(
        {
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
        }
    )
    return card


def _process_operator_controller_event_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any],
) -> OpenClawResponseForMac:
    generated_at = generated_at or utc_now()
    default_paths = _same_path(export_root, DEFAULT_EXPORT_ROOT)
    bridge_root = operator_controller_event_router.DEFAULT_BRIDGE_ROOT if default_paths else export_root.parent / "bridge"
    wiki_path = (
        operator_controller_event_router.DEFAULT_WIKI_PATH
        if default_paths
        else export_root.parent / "wiki" / "Operator Controller Event Router.md"
    )
    workroom_wiki_path = (
        workroom_review_decision_consumer.DEFAULT_WIKI_PATH
        if default_paths
        else export_root.parent / "wiki" / "Workroom Review Decision Consumer.md"
    )
    sqlite_path = (
        operator_controller_event_router.DEFAULT_SQLITE_PATH
        if default_paths
        else export_root.parent / "system_knowledge" / "operator_controller_event_router.sqlite"
    )
    evidence_sqlite_path = (
        evidence_intake.DEFAULT_SQLITE_PATH
        if default_paths
        else export_root.parent / "system_knowledge" / "evidence_intake.sqlite"
    )
    artifact_lineage_sqlite_path = (
        evidence_intake.DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH
        if default_paths
        else export_root.parent / "system_knowledge" / "artifact_lineage_registry.sqlite"
    )
    proof_to_response_sqlite_path = (
        proof_to_response_runtime.DEFAULT_SQLITE_PATH
        if default_paths
        else export_root.parent / "system_knowledge" / "proof_to_response_runtime.sqlite"
    )
    receipt = operator_controller_event_router.route_controller_event(
        raw_request,
        source_request_filename=request_path.name,
        read_model_root=export_root,
        export_root=export_root,
        bridge_root=bridge_root,
        wiki_path=wiki_path,
        workroom_wiki_path=workroom_wiki_path,
        sqlite_path=sqlite_path,
        evidence_sqlite_path=evidence_sqlite_path,
        artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
        proof_to_response_sqlite_path=proof_to_response_sqlite_path,
        generated_at=generated_at,
    )
    request_id = str(receipt.get("request_id") or raw_request.get("request_id") or f"missing_request_id_{request_path.stem}")
    event_type = str(receipt.get("controller_event_type") or raw_request.get("controller_event_type") or "")
    internal_status = str(receipt.get("raw_internal_status") or "BLOCKED_WITH_REASON")
    route_status = str(receipt.get("route_status") or "")
    card = _controller_event_dynamic_card(receipt)
    primary_response = receipt.get("proof_to_response") if isinstance(receipt.get("proof_to_response"), Mapping) else {}
    proof_to_response_status = str(
        receipt.get("proof_to_response_status")
        or primary_response.get("verification_status")
        or "unavailable"
    )
    headline = str(
        primary_response.get("headline")
        or receipt.get("one_line_answer")
        or card.get("headline")
        or ("Controller event routed" if internal_status == "RESPONSE_READY" else "Controller event blocked")
    )
    message = str(
        primary_response.get("body")
        or receipt.get("plain_summary")
        or card.get("plain_summary")
        or card.get("summary")
        or "OpenClaw handled the controller event locally."
    )
    blockers = tuple(str(item) for item in receipt.get("blockers") or () if item)
    rejected = tuple(str(item) for item in receipt.get("rejected_reasons") or () if item)
    proof_refs = tuple(str(ref) for ref in receipt.get("proof_refs") or () if ref)
    local_readbacks = (
        "generated/read_models/operator_controller_event_router_status.json",
        "generated/read_models/operator_controller_event_router_contract.json",
    )
    readback_files = tuple(dict.fromkeys(local_readbacks + proof_refs))
    next_safe_move = str(primary_response.get("next_step") or "") or (
        "Render the returned dynamic card in Mission Control."
        if internal_status == "RESPONSE_READY"
        else "Fix verification, selected action payload, or event type and resend."
    )
    layered_fields = {
        "response_kind": "OPERATOR_CONTROLLER_EVENT_RESPONSE",
        "audience_mode": "ELIWINSHIP",
        "display_mode": "COMPACT_CHAT",
        "headline": headline,
        "one_line_answer": str(receipt.get("one_line_answer") or message),
        "plain_summary": message,
        "eliwinship": message,
        "primary_status": str(card.get("status_label") or route_status or internal_status),
        "primary_blocker": "; ".join(blockers or rejected) or "None",
        "next_action": f"Next: {next_safe_move}",
        "missing_items_short": blockers + rejected,
        "detail_summary": (
            f"Controller event {event_type or 'unknown'} returned {route_status or internal_status} "
            f"through {receipt.get('backend_route') or 'fail_closed'}."
        ),
        "proof_refs": proof_refs,
        "primary_response_kind": str(receipt.get("primary_response_kind") or "dynamic_card_response"),
        "proof_to_response": primary_response,
        "proof_to_response_status": proof_to_response_status,
        "debug_refs": readback_files,
        "raw_internal_status": internal_status,
        "mac_render_hint": str(receipt.get("mac_render_hint") or card.get("mac_render_hint") or "DYNAMIC_CARD_WITH_DISCLOSURE"),
        "request_ref": request_id,
        "controller_event_type": event_type,
        "route_status": route_status,
        "route_ref": str(receipt.get("route_ref") or ""),
        "route_receipt_ref": str(receipt.get("route_receipt_ref") or ""),
        "no_external_authority_granted": True,
    }
    current_world = str(receipt.get("current_world_ref") or raw_request.get("current_world_ref") or "unknown")
    current_thread = str(receipt.get("current_thread_ref") or raw_request.get("current_thread_ref") or "unknown")
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=f"{current_world}/{current_thread}",
        request_type="OPERATOR_CONTROLLER_EVENT_REQUEST",
        internal_status=internal_status,
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "OpenClaw recognized a Mission Control controller event.",
            "The event was routed through the Operator Controller Event Router.",
            "The router returned a verified concise agent response with the dynamic card kept as support.",
            "No email, Gmail, browser, Coupa, submit, ledger, workbook, PDF, paid, push, external LLM, local model runtime, or business execution occurred.",
        ),
        why_it_happened=(
            f"Controller event {event_type} routed to {receipt.get('backend_route')}."
            if internal_status == "RESPONSE_READY"
            else "; ".join(blockers or rejected or (route_status or "controller_event_blocked",))
        ),
        how_to_fix=next_safe_move if internal_status == "RESPONSE_READY" else " ".join(blockers or rejected) or next_safe_move,
        visible_cards=(card,),
        cards_available=bool(card),
        card_mirror_refs=(),
        file_readback_refs=readback_files,
        worker_route_refs=(
            {
                "selected_worker_target": "PC_CODEX",
                "selected_machine": "PC_WSL",
                "routing_status": "PROCESSING_ON_PC",
                "selected_rail": "operator_controller_event_router",
                "controller_event_type": event_type,
                "route_status": route_status,
                "backend_route": str(receipt.get("backend_route") or ""),
            },
        ),
        context_package_refs=(),
        blocked_reason=None if internal_status == "RESPONSE_READY" else "; ".join(blockers or rejected) or route_status,
        detail_disclosure={
            "request_classification": asdict(classification),
            "request_router_decision": dict(route_decision),
            "layered_response_fields": layered_fields,
            "operator_controller_event_router": receipt,
            "proof_to_response": primary_response,
            "proof_to_response_status": proof_to_response_status,
            "dynamic_card_response": card,
            "live_external_provider_action_performed": False,
            "business_action_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "paid_marking_performed": False,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
        },
        readback_files=readback_files,
        next_safe_move=next_safe_move,
        proof_to_response=dict(primary_response),
        proof_to_response_status=proof_to_response_status,
    )


def _normalized_request_kind(raw_request: Mapping[str, Any]) -> str:
    return str(
        raw_request.get("kind")
        or raw_request.get("type")
        or raw_request.get("request_type")
        or raw_request.get("requestType")
        or ""
    ).strip().upper()


def _maestro_frontdoor_surface(raw_request: Mapping[str, Any]) -> str:
    return str(raw_request.get("active_surface_ref") or raw_request.get("activeSurfaceRef") or "").strip()


def _is_maestro_frontdoor_operator_instruction(raw_request: Mapping[str, Any]) -> bool:
    if _maestro_frontdoor_surface(raw_request) != "operator_maestro_chat":
        return False
    if str(raw_request.get("controller_event_type") or raw_request.get("controller_action_type") or "").strip():
        return False
    if _normalized_request_kind(raw_request) not in {"OPERATOR_INSTRUCTION_PACKAGE_REQUEST", "WORKFLOW_PACKAGE_REQUEST_V0"}:
        return False
    if not maestro_cassandra_responder.operator_text_from_request(raw_request):
        return False
    authority = raw_request.get("authority_boundary")
    return isinstance(authority, Mapping) and not any(value is True for value in authority.values())


def _maestro_frontdoor_workflow_intent(raw_request: Mapping[str, Any]) -> dict[str, Any]:
    if not _is_maestro_frontdoor_operator_instruction(raw_request):
        return {}
    operator_text = maestro_cassandra_responder.operator_text_from_request(raw_request)
    if not operator_text:
        return {}
    try:
        import workflow_package_queue

        intent = workflow_package_queue.classify_intent(operator_text)
    except Exception:
        return {}
    workflow_ref = str(intent.get("workflow_ref") or "")
    if workflow_ref and workflow_ref != "diagnostic_package_gate_smoke":
        return dict(intent)
    return {}


def _process_maestro_frontdoor_operator_instruction(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    classification: RequestClassification,
    route_decision: Mapping[str, Any],
    _capsule: Any | None = None,
) -> OpenClawResponseForMac | None:
    if not _is_maestro_frontdoor_operator_instruction(raw_request):
        return None
    if _maestro_frontdoor_workflow_intent(raw_request):
        return None

    operator_text = maestro_cassandra_responder.operator_text_from_request(raw_request)
    session = maestro_cassandra_responder.session_from_request(raw_request)
    source_surface = _maestro_frontdoor_surface(raw_request) or "operator_maestro_chat"
    agent = _resolved_frontdoor_agent(raw_request, session=session, _capsule=_capsule)
    try:
        result = maestro_cassandra_responder.answer_frontdoor_chat(
            operator_text,
            session=session,
            source_surface=source_surface,
            _capsule=_capsule,
            agent=agent,
        )
    except TypeError as exc:
        if "source_surface" not in str(exc):
            raise
        result = maestro_cassandra_responder.answer_frontdoor_chat(operator_text, session=session)
    if result.status != "ANSWER_READY":
        return None

    backend_route = maestro_cassandra_responder.backend_route_for_result(result)
    proof_refs = maestro_cassandra_responder.proof_refs_for_result(
        result,
        "generated/read_models/openclaw_request_processor_status.json",
    )
    external_llm_invoked = maestro_cassandra_responder.external_llm_invoked_for_result(result)
    result_payload = maestro_cassandra_responder.result_dict_for_receipt(result)
    machine_proof = maestro_cassandra_responder.machine_proof_for_result(result)
    local_model_invoked = bool(machine_proof.get("local_model_invoked", False))
    model_call_performed = bool(machine_proof.get("model_call_performed", False))
    response_adapter_called = bool(
        result.allowed_to_call_handle
        or machine_proof.get("protected_generate_called")
        or machine_proof.get("cassandra_handle_called")
    )
    request_id = str(raw_request.get("request_id") or raw_request.get("source_request_id") or f"missing_request_id_{request_path.stem}")
    current_world = str(
        raw_request.get("current_world_ref")
        or raw_request.get("currentWorldRef")
        or raw_request.get("world_ref")
        or raw_request.get("worldRef")
        or raw_request.get("world")
        or "general"
    )
    current_thread = str(
        raw_request.get("current_thread_ref")
        or raw_request.get("currentThreadRef")
        or raw_request.get("thread_ref")
        or raw_request.get("threadRef")
        or _maestro_frontdoor_surface(raw_request)
        or "operator_maestro_chat"
    )
    response_classification = _maestro_frontdoor_classification(classification, request_path=request_path)
    response_provenance = {
        "speaker": "Maestro",
        "lane": "telegram_pc_maestro_listener",
        "relay_origin": None,
        "actor": "maestro",
        "surface_ref": source_surface,
        "message_role": "final_agent_reply",
        "source_request_id": request_id,
    }
    card = {
        "schema_version": "maestro_frontdoor_answer_card_v0",
        "card_id": f"maestro_frontdoor_answer_{_short_hash(request_id, result.one_line_answer)}",
        "card_type": "MAESTRO_CASSANDRA_ANSWER",
        "title": result.one_line_answer or "Maestro response",
        "summary": result.plain_summary,
        "status_label": "Maestro",
        "route_status": "TEXT_RESPONSE_READY",
        "mac_render_hint": result.mac_render_hint,
        "actions": [],
        "provenance": response_provenance,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "proof": {
            "proof_refs": list(proof_refs),
            "machine_proof": machine_proof,
        },
    }
    detail = {
        "message_provenance": response_provenance,
        "request_message_provenance": raw_request.get("message_provenance")
        if isinstance(raw_request.get("message_provenance"), Mapping)
        else {
            "speaker": "Winship",
            "lane": "telegram_pc_maestro_listener",
            "relay_origin": None,
            "actor": "operator_winship",
            "surface_ref": source_surface,
            "message_role": "operator_prompt",
        },
        "correlation": {
            "source_request_id": request_id,
            "request_filename": request_path.name,
            "thread_ref": current_thread,
            "world_ref": current_world,
        },
        "operator_display": {"speaker_ref": "maestro"},
        "request_classification": asdict(response_classification),
        "original_request_classification": asdict(classification),
        "request_router_decision": dict(route_decision),
        "maestro_frontdoor_routing": {
            "source_surface": _maestro_frontdoor_surface(raw_request),
            "workflow_package_staged": False,
            "default_deny_preserved": True,
            "route_to_staging_when_not_answer_ready": True,
        },
        "maestro_cassandra_responder": result_payload,
        "dynamic_card_response": card,
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": response_adapter_called,
        "workflow_package_staged": False,
        "workflow_package_request_v0_emitted": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "telegram_send_triggered": False,
        "business_action_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "paid_marking_performed": False,
        "external_llm_invoked": external_llm_invoked,
        "local_model_runtime_connected": local_model_invoked,
    }
    model_runtime_sentence = (
        "No external LLM, local model runtime, worker, or business execution occurred."
        if not (external_llm_invoked or local_model_invoked or model_call_performed)
        else (
            "The protected Maestro generation path recorded model_call_performed="
            f"{model_call_performed}, external_llm_invoked={external_llm_invoked}, "
            f"local_model_invoked={local_model_invoked}; no worker or business execution occurred."
        )
    )
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=f"{current_world}/{current_thread}",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline=result.one_line_answer or "Maestro response",
        operator_message=result.plain_summary,
        what_happened=(
            "OpenClaw recognized the general Maestro front-door chat surface.",
            "The gated Maestro Cassandra responder answered before workflow-package staging.",
            "No workflow package was staged for this allowed answer.",
            "No email, Gmail, browser, Coupa, submit, ledger, workbook, PDF, paid marking, or external business action occurred.",
            model_runtime_sentence,
        ),
        why_it_happened=f"The Maestro intent gate allowed {result.intent_class} through {backend_route}.",
        how_to_fix="No fix is needed. Review the Maestro answer and ask a follow-up if needed.",
        visible_cards=(card,),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": "PC_CODEX",
                "selected_machine": "PC_WSL",
                "routing_status": "PROCESSING_ON_PC",
                "selected_rail": "MAESTRO_CASSANDRA_RESPONDER",
                "controller_event_type": "chat_goal",
                "route_status": "TEXT_RESPONSE_READY",
                "backend_route": backend_route,
            },
        ),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure=detail,
        readback_files=(),
        next_safe_move="Ask Maestro a follow-up if you need more.",
        proof_to_response=dict(machine_proof),
    )


def _interpreter_enabled() -> bool:
    """Return True only when OPENCLAW_INTERPRETER_LM is "1" or "true".

    Thin wrapper so tests can monkeypatch this location without touching the
    interpreter_lm module directly.
    """
    import os
    return os.environ.get("OPENCLAW_INTERPRETER_LM", "0").lower() in ("1", "true")


def _lm1_shared_seam_enabled() -> bool:
    return os.environ.get("OPENCLAW_LM1_SHARED_SEAM", "0").lower() in ("1", "true")


def _lm1_source_text(raw_request: Mapping[str, Any]) -> str:
    text = maestro_cassandra_responder.operator_text_from_request(raw_request)
    if text:
        return text
    for key in ("source_text", "operator_message", "sanitized_message_summary", "operator_goal", "message", "text"):
        value = str(raw_request.get(key) or "").strip()
        if value:
            return value
    return ""


def _lm1_interpretation_dict(result: Any, *, source: str, workflow_intent: Mapping[str, Any] | None = None) -> dict[str, Any]:
    workflow_intent = dict(workflow_intent or {})
    confidence = getattr(result, "confidence", workflow_intent.get("confidence", 0.0))
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    route = str(getattr(result, "route", workflow_intent.get("route") or "WORKFLOW") or "").upper()
    intent = str(getattr(result, "intent", workflow_intent.get("intent") or "") or "")
    client = str(getattr(result, "client", workflow_intent.get("client_ref") or workflow_intent.get("client") or "") or "")
    workflow_ref = str(workflow_intent.get("workflow_ref") or "")
    if not workflow_ref and route == "WORKFLOW":
        workflow_ref = _lm1_workflow_ref_from_interpretation(intent=intent, client=client)
    return {
        "source": source,
        "route": route,
        "fact_selection": list(getattr(result, "fact_selection", workflow_intent.get("fact_selection") or []) or []),
        "confidence": confidence_value,
        "reason": str(getattr(result, "reason", workflow_intent.get("intent_reason") or "") or ""),
        "intent": intent,
        "client": client,
        "contact": str(getattr(result, "contact", workflow_intent.get("contact") or "") or ""),
        "description": str(getattr(result, "description", workflow_intent.get("description") or "") or ""),
        "date": str(getattr(result, "date", workflow_intent.get("date") or "") or ""),
        "workflow_ref": workflow_ref,
        "world": str(workflow_intent.get("world") or ""),
        "client_ref": str(workflow_intent.get("client_ref") or client or ""),
    }


def _lm1_workflow_ref_from_interpretation(*, intent: str, client: str) -> str:
    intent_key = str(intent or "").strip().lower().replace("-", "_")
    client_key = str(client or "").strip().lower().replace("_", "-")
    if intent_key == "invoice_send":
        if client_key in {"st-annes", "st-anne", "st-anne-s", "st-annes-annapolis"}:
            return "st_annes_monthly_invoice_rollup"
        if client_key in {"capital-hilton", "capitalhilton"}:
            return "capital_hilton_invoice_operator_assist"
    if intent_key == "capture_gig" and client_key in {"st-annes", "st-anne", "st-anne-s", "st-annes-annapolis"}:
        return "st_annes_work_log_event"
    return ""


def _lm1_deterministic_workflow_interpretation(source_text: str) -> dict[str, Any] | None:
    try:
        import workflow_package_queue

        intent = workflow_package_queue.classify_intent(source_text)
    except Exception:
        return None
    workflow_ref = str(intent.get("workflow_ref") or "")
    if workflow_ref == "diagnostic_package_gate_smoke":
        return None
    return _lm1_interpretation_dict(
        None,
        source="deterministic_workflow_classifier",
        workflow_intent={
            **dict(intent),
            "route": "WORKFLOW",
            "intent": "",
            "fact_selection": [],
        },
    )


def _lm1_workflow_authority_boundary() -> dict[str, bool]:
    try:
        import cross_machine_worker_dispatch_package as dispatch_contract

        authority = {str(key): False for key in dispatch_contract.AUTHORITY_BOUNDARY}
    except Exception:
        authority = {}
    authority.update(
        {
            "email_send_allowed": False,
            "gmail_allowed": False,
            "ledger_posting_allowed": False,
            "ledger_mutation_allowed": False,
            "browser_access_allowed": False,
            "coupa_allowed": False,
            "portal_submit_allowed": False,
            "paid": False,
            "sent": False,
            "raw_body_ingestion_allowed": False,
            "tool_execution_allowed": False,
            "model_call_allowed": False,
            "runtime_dispatch_allowed": False,
        }
    )
    return authority


def _lm1_workflow_context_packet(rich_packet: Mapping[str, Any], interpretation: Mapping[str, Any]) -> dict[str, Any]:
    selected = {str(item) for item in interpretation.get("fact_selection", ()) if str(item).strip()}
    bounded_facts: list[dict[str, Any]] = []
    for fact in rich_packet.get("facts", ()) if isinstance(rich_packet.get("facts"), list) else ():
        if not isinstance(fact, Mapping):
            continue
        source_ref = str(fact.get("source_ref") or "")
        if selected and not any(item in source_ref for item in selected):
            continue
        pii_tier = str(fact.get("pii_tier") or "PUBLIC").upper()
        if pii_tier not in {"PUBLIC", "LIGHT"}:
            continue
        bounded_facts.append(
            {
                "fact_id": str(fact.get("fact_id") or ""),
                "topic": str(fact.get("topic") or ""),
                "label": str(fact.get("label") or ""),
                "value": str(fact.get("value") or "")[:360],
                "source_ref": source_ref,
                "provenance": str(fact.get("provenance") or ""),
                "pii_tier": pii_tier,
            }
        )
        if len(bounded_facts) >= 8:
            break
    return {
        "schema_version": "lm1_shared_workflow_context_packet_v0",
        "packet_id": str(rich_packet.get("packet_id") or ""),
        "source_surface": str(rich_packet.get("source_surface") or ""),
        "question_hash": hashlib.sha256(str(rich_packet.get("question") or "").encode("utf-8")).hexdigest(),
        "interpretation": dict(interpretation),
        "facts": bounded_facts,
        "source_refs": [str(ref) for ref in rich_packet.get("source_refs", ()) if str(ref).strip()][:12],
        "authority_boundary": _lm1_workflow_authority_boundary(),
        "excluded_context": [
            "packet_text",
            "full daemon context",
            "raw private bodies",
            "credentials",
            "send or payment authority",
        ],
        "machine_proof": {
            "rich_packet_id": str(rich_packet.get("packet_id") or ""),
            "packet_text_excluded": True,
            "bounded_fact_count": len(bounded_facts),
            "authority_flags_all_false": all(value is False for value in _lm1_workflow_authority_boundary().values()),
        },
    }


def _lm1_result_from_seam(lm1_shared_seam: Mapping[str, Any] | None) -> Any | None:
    if not isinstance(lm1_shared_seam, Mapping):
        return None
    result = lm1_shared_seam.get("interpret_result")
    if result is not None:
        return result
    interpretation = lm1_shared_seam.get("interpretation")
    if not isinstance(interpretation, Mapping):
        return None
    try:
        from interpreter_lm import InterpretResult

        return InterpretResult(
            route=str(interpretation.get("route") or "UNCERTAIN"),
            fact_selection=[str(item) for item in interpretation.get("fact_selection", ()) if str(item).strip()],
            confidence=float(interpretation.get("confidence") or 0.0),
            reason=str(interpretation.get("reason") or ""),
            intent=str(interpretation.get("intent") or ""),
            client=str(interpretation.get("client") or interpretation.get("client_ref") or ""),
            contact=str(interpretation.get("contact") or ""),
            description=str(interpretation.get("description") or ""),
            date=str(interpretation.get("date") or ""),
        )
    except Exception:
        return None


def _lm1_shared_request_seam_summary(lm1_shared_seam: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(lm1_shared_seam, Mapping):
        return None
    workflow_packet = lm1_shared_seam.get("workflow_context_packet")
    rich_packet = lm1_shared_seam.get("rich_context_packet")
    workflow_packet = workflow_packet if isinstance(workflow_packet, Mapping) else {}
    rich_packet = rich_packet if isinstance(rich_packet, Mapping) else {}
    interpretation = lm1_shared_seam.get("interpretation")
    return {
        "status": str(lm1_shared_seam.get("status") or ""),
        "interpretation": dict(interpretation) if isinstance(interpretation, Mapping) else {},
        "workflow_packet_id": str(workflow_packet.get("packet_id") or ""),
        "rich_packet_id": str(rich_packet.get("packet_id") or ""),
        "packet_error": str(lm1_shared_seam.get("packet_error") or ""),
    }


def _build_lm1_shared_request_seam(
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    _capsule: Any | None = None,
) -> dict[str, Any]:
    if not _lm1_shared_seam_enabled():
        return {"status": "DISABLED", "machine_proof": {"lm1_shared_seam_enabled": False}}
    operator_text = _lm1_source_text(raw_request)
    if not operator_text:
        return {"status": "NO_TEXT", "machine_proof": {"lm1_shared_seam_enabled": True, "operator_text_present": False}}

    deterministic = _lm1_deterministic_workflow_interpretation(operator_text)
    interp_result = None
    interpreter_called = False
    if deterministic is not None:
        interpretation = deterministic
    elif _interpreter_enabled():
        try:
            interp_result = _interpret_for_request(operator_text)
            interpreter_called = True
            interpretation = _lm1_interpretation_dict(interp_result, source="lm1_shared_interpreter")
        except Exception:
            interpretation = {
                "source": "lm1_shared_interpreter_exception",
                "route": "UNCERTAIN",
                "fact_selection": [],
                "confidence": 0.0,
                "reason": "interpreter_exception",
                "intent": "",
                "client": "",
                "contact": "",
                "description": "",
                "date": "",
                "workflow_ref": "",
                "world": "",
                "client_ref": "",
            }
    else:
        return {
            "status": "INTERPRETER_DISABLED",
            "machine_proof": {
                "lm1_shared_seam_enabled": True,
                "interpreter_lm_called": False,
                "deterministic_workflow_resolved": False,
            },
        }

    session = maestro_cassandra_responder.session_from_request(raw_request)
    if interpretation.get("fact_selection"):
        session = {**session, "interpreter_fact_selection": list(interpretation.get("fact_selection") or [])}
    rich_packet: dict[str, Any] = {}
    workflow_packet: dict[str, Any] = {}
    packet_error = ""
    try:
        from maestro_context_packet import build_maestro_context_packet

        rich_packet = dict(
            build_maestro_context_packet(
                question=operator_text,
                session=session,
                source_surface=_maestro_frontdoor_surface(raw_request) or str(raw_request.get("source_surface") or "mission_control"),
                require_real_truth=True,
                capsule=_capsule if _continuity_enabled() else None,
                fact_selection=list(interpretation.get("fact_selection") or []),
            )
        )
        machine_proof = dict(rich_packet.get("machine_proof") or {})
        machine_proof["lm1_shared_seam_built"] = True
        machine_proof["lm1_shared_seam_generated_at"] = generated_at or utc_now()
        rich_packet["machine_proof"] = machine_proof
        workflow_packet = _lm1_workflow_context_packet(rich_packet, interpretation)
    except Exception as exc:
        packet_error = type(exc).__name__

    return {
        "schema_version": "lm1_shared_request_seam_v0",
        "status": "READY" if rich_packet and workflow_packet else "INTERPRETATION_READY_PACKET_UNAVAILABLE",
        "generated_at": generated_at or utc_now(),
        "interpret_result": interp_result,
        "interpretation": interpretation,
        "rich_context_packet": rich_packet,
        "workflow_context_packet": workflow_packet,
        "packet_error": packet_error,
        "machine_proof": {
            "lm1_shared_seam_enabled": True,
            "operator_text_present": True,
            "deterministic_workflow_resolved": deterministic is not None,
            "interpreter_lm_called": interpreter_called,
            "rich_context_packet_built": bool(rich_packet),
            "workflow_context_packet_built": bool(workflow_packet),
            "workflow_packet_authority_bounded": bool(workflow_packet)
            and all(value is False for value in (workflow_packet.get("authority_boundary") or {}).values()),
        },
    }


# Per-request memoization of the interpreter result so the BRAIN divert and the
# ACTION/BLOCKED divert read the SAME classification from a SINGLE LM call. Without
# this, each divert would independently call interpret_operator_message → two
# stochastic LM calls per request that could disagree (a BRAIN<0.75 followed by an
# ACTION>0.75 would otherwise produce an advisory the first call never made).
# Keyed on the operator text; returns UNCERTAIN on any error (deterministic fallback).
_INTERPRETER_RESULT_CACHE: "dict[str, Any]" = {}
_INTERPRETER_RESULT_CACHE_MAX = 256


def _interpret_for_request(operator_text: str) -> Any:
    """Compute (once, memoized by operator_text) the interpreter result for this
    message. Both diverts call this so exactly one LM call happens per request.
    Returns an InterpretResult; UNCERTAIN on any error → deterministic fallback."""
    from interpreter_lm import interpret_operator_message, InterpretResult, ROUTE_UNCERTAIN

    key = operator_text
    cached = _INTERPRETER_RESULT_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        result = interpret_operator_message(operator_text)
    except Exception:  # noqa: BLE001 — interpreter error → deterministic path
        result = InterpretResult(route=ROUTE_UNCERTAIN, reason="interpreter_exception")
    # Bound the cache so a long-running process does not grow unboundedly.
    if len(_INTERPRETER_RESULT_CACHE) >= _INTERPRETER_RESULT_CACHE_MAX:
        _INTERPRETER_RESULT_CACHE.clear()
    _INTERPRETER_RESULT_CACHE[key] = result
    return result


def _try_interpreter_brain_divert(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    classification: RequestClassification,
    route_decision: Mapping[str, Any],
    _capsule: Any | None = None,
    lm1_shared_seam: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac | None:
    """Flag-gated interpreter-LM routing augmentation.

    DISCIPLINE
    ----------
    - Only runs when OPENCLAW_INTERPRETER_LM="1".  When off → returns None
      immediately (zero side effects, byte-identical downstream behaviour).
    - Only applies to messages on the operator_maestro_chat surface that the
      DETERMINISTIC gate would NOT handle (i.e. the deterministic check
      returned None).  We never override or block a brain route that already
      fired.
    - ADVISORY ONLY: the interpreter can ADD a brain diversion; it can NEVER
      block the brain, escalate authority, or trigger an action.
    - NO authority effect: the interpreter result is never consulted by
      authority_gate, action_runtime, or any SEND_HOLD path.
    - Fallback: any exception or low-confidence result → returns None so the
      caller falls through to the deterministic workflow consumer path.
    """
    if not _interpreter_enabled():
        return None

    # Only augment the maestro frontdoor surface
    if _maestro_frontdoor_surface(raw_request) != "operator_maestro_chat":
        return None

    # Defense-in-depth: only augment messages the DETERMINISTIC gate declined.
    # The dispatch already calls us only after _process_maestro_frontdoor_operator_instruction
    # returned None, but we re-assert here so a future refactor cannot let the
    # interpreter override a request the deterministic gate owns.
    if _is_maestro_frontdoor_operator_instruction(raw_request):
        return None

    # Only apply when there IS operator text to interpret
    operator_text = maestro_cassandra_responder.operator_text_from_request(raw_request)
    if not operator_text:
        return None

    interp_result = _lm1_result_from_seam(lm1_shared_seam)
    if interp_result is None:
        if (
            isinstance(lm1_shared_seam, Mapping)
            and str((lm1_shared_seam.get("interpretation") or {}).get("source") or "")
            == "deterministic_workflow_classifier"
        ):
            return None
        try:
            interp_result = _interpret_for_request(operator_text)
        except Exception:  # noqa: BLE001 — interpreter error → deterministic path
            return None

    if not interp_result.is_high_confidence_brain():
        return None  # UNCERTAIN or WORKFLOW or low-confidence → deterministic path

    # Interpreter says BRAIN with high confidence → route to answer_frontdoor_chat.
    # We build the fact_selection list from the interpreter result and pass it
    # to answer_frontdoor_chat via the session so build_maestro_context_packet
    # can elevate the right read-models.
    session = maestro_cassandra_responder.session_from_request(raw_request)
    # Inject fact_selection into the session so it flows through to the packet builder.
    # The key "interpreter_fact_selection" is read by the answer_frontdoor_chat
    # wrapper below; it does NOT affect authority_gate or action_runtime.
    augmented_session: dict[str, Any] = dict(session or {})
    if interp_result.fact_selection:
        augmented_session["interpreter_fact_selection"] = list(interp_result.fact_selection)
    if isinstance(lm1_shared_seam, Mapping) and isinstance(lm1_shared_seam.get("rich_context_packet"), Mapping):
        augmented_session["lm1_shared_rich_context_packet"] = dict(lm1_shared_seam["rich_context_packet"])

    source_surface = _maestro_frontdoor_surface(raw_request) or "operator_maestro_chat"
    agent = _resolved_frontdoor_agent(raw_request, session=augmented_session, _capsule=_capsule)
    try:
        result = maestro_cassandra_responder.answer_frontdoor_chat(
            operator_text,
            session=augmented_session,
            source_surface=source_surface,
            _capsule=_capsule,
            agent=agent,
        )
    except TypeError as exc:
        if "source_surface" not in str(exc):
            raise
        result = maestro_cassandra_responder.answer_frontdoor_chat(
            operator_text, session=augmented_session
        )
    except Exception:  # noqa: BLE001 — answer error → fall through
        return None

    if result.status != "ANSWER_READY":
        return None  # brain said no → fall through to workflow consumer

    # Re-use the existing frontdoor response builder (same code path, different
    # entry — ensures the machine proof, receipt, and render hint are consistent).
    backend_route = maestro_cassandra_responder.backend_route_for_result(result)
    proof_refs = maestro_cassandra_responder.proof_refs_for_result(
        result,
        "generated/read_models/openclaw_request_processor_status.json",
        "interpreter_lm:divert",
    )
    external_llm_invoked = maestro_cassandra_responder.external_llm_invoked_for_result(result)
    result_payload = maestro_cassandra_responder.result_dict_for_receipt(result)
    machine_proof = maestro_cassandra_responder.machine_proof_for_result(result)
    machine_proof = {
        **machine_proof,
        "interpreter_lm_divert": True,
        "interpreter_route": interp_result.route,
        "interpreter_confidence": interp_result.confidence,
        "interpreter_reason": interp_result.reason,
        "interpreter_fact_selection": list(interp_result.fact_selection),
        "lm1_shared_seam_used": isinstance(lm1_shared_seam, Mapping)
        and bool(lm1_shared_seam.get("rich_context_packet")),
        "lm1_shared_packet_id": str(
            ((lm1_shared_seam or {}).get("rich_context_packet") or {}).get("packet_id")
            if isinstance(lm1_shared_seam, Mapping)
            else ""
        ),
    }
    local_model_invoked = bool(machine_proof.get("local_model_invoked", False))
    model_call_performed = bool(machine_proof.get("model_call_performed", False))
    response_adapter_called = bool(
        result.allowed_to_call_handle
        or machine_proof.get("protected_generate_called")
        or machine_proof.get("cassandra_handle_called")
    )
    request_id = str(raw_request.get("request_id") or raw_request.get("source_request_id") or f"missing_request_id_{request_path.stem}")
    current_world = str(
        raw_request.get("current_world_ref")
        or raw_request.get("currentWorldRef")
        or raw_request.get("world_ref")
        or raw_request.get("worldRef")
        or raw_request.get("world")
        or "general"
    )
    current_thread = str(
        raw_request.get("current_thread_ref")
        or raw_request.get("currentThreadRef")
        or raw_request.get("thread_ref")
        or raw_request.get("threadRef")
        or _maestro_frontdoor_surface(raw_request)
        or "operator_maestro_chat"
    )
    response_classification = _maestro_frontdoor_classification(classification, request_path=request_path)
    response_provenance = {
        "speaker": "Maestro",
        "lane": "telegram_pc_maestro_listener",
        "relay_origin": None,
        "actor": "maestro",
        "surface_ref": source_surface,
        "message_role": "final_agent_reply",
        "source_request_id": request_id,
    }
    card = {
        "schema_version": "maestro_frontdoor_answer_card_v0",
        "card_id": f"maestro_frontdoor_answer_{_short_hash(request_id, result.one_line_answer)}",
        "card_type": "MAESTRO_CASSANDRA_ANSWER",
        "title": result.one_line_answer or "Maestro response",
        "summary": result.plain_summary,
        "status_label": "Maestro",
        "route_status": "TEXT_RESPONSE_READY",
        "mac_render_hint": result.mac_render_hint,
        "actions": [],
        "provenance": response_provenance,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "proof": {
            "proof_refs": list(proof_refs),
            "machine_proof": machine_proof,
        },
    }
    detail = {
        "message_provenance": response_provenance,
        "request_message_provenance": raw_request.get("message_provenance")
        if isinstance(raw_request.get("message_provenance"), Mapping)
        else {
            "speaker": "Winship",
            "lane": "telegram_pc_maestro_listener",
            "relay_origin": None,
            "actor": "operator_winship",
            "surface_ref": source_surface,
            "message_role": "operator_prompt",
        },
        "correlation": {
            "source_request_id": request_id,
            "request_filename": request_path.name,
            "thread_ref": current_thread,
            "world_ref": current_world,
        },
        "operator_display": {"speaker_ref": "maestro"},
        "request_classification": asdict(response_classification),
        "original_request_classification": asdict(classification),
        "request_router_decision": dict(route_decision),
        "maestro_frontdoor_routing": {
            "source_surface": _maestro_frontdoor_surface(raw_request),
            "workflow_package_staged": False,
            "default_deny_preserved": True,
            "route_to_staging_when_not_answer_ready": True,
            "interpreter_lm_divert": True,
        },
        "lm1_shared_request_seam": _lm1_shared_request_seam_summary(lm1_shared_seam),
        "maestro_cassandra_responder": result_payload,
        "dynamic_card_response": card,
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": response_adapter_called,
        "workflow_package_staged": False,
        "workflow_package_request_v0_emitted": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "telegram_send_triggered": False,
        "business_action_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "paid_marking_performed": False,
        "external_llm_invoked": external_llm_invoked,
        "local_model_runtime_connected": local_model_invoked,
    }
    model_runtime_sentence = (
        "No external LLM, local model runtime, worker, or business execution occurred."
        if not (external_llm_invoked or local_model_invoked or model_call_performed)
        else (
            "The protected Maestro generation path recorded model_call_performed="
            f"{model_call_performed}, external_llm_invoked={external_llm_invoked}, "
            f"local_model_invoked={local_model_invoked}; no worker or business execution occurred."
        )
    )
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=f"{current_world}/{current_thread}",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline=result.one_line_answer or "Maestro response",
        operator_message=result.plain_summary,
        what_happened=(
            "OpenClaw recognized the general Maestro front-door chat surface.",
            "The interpreter LM classified this as a conversational message (BRAIN route).",
            "The gated Maestro Cassandra responder answered via interpreter divert.",
            "No workflow package was staged for this allowed answer.",
            "No email, Gmail, browser, Coupa, submit, ledger, workbook, PDF, paid marking, or external business action occurred.",
            model_runtime_sentence,
        ),
        why_it_happened=(
            f"The interpreter LM diverted a message that the deterministic gate would have sent to the workflow consumer. "
            f"Confidence: {interp_result.confidence:.2f}. Reason: {interp_result.reason}. "
            f"Brain intent: {result.intent_class} via {backend_route}."
        ),
        how_to_fix="No fix is needed. Review the Maestro answer and ask a follow-up if needed.",
        visible_cards=(card,),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": "PC_CODEX",
                "selected_machine": "PC_WSL",
                "routing_status": "PROCESSING_ON_PC",
                "selected_rail": "MAESTRO_CASSANDRA_RESPONDER",
                "controller_event_type": "chat_goal",
                "route_status": "TEXT_RESPONSE_READY",
                "backend_route": backend_route,
                "interpreter_lm_divert": True,
            },
        ),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure=detail,
        readback_files=(),
        next_safe_move="Ask Maestro a follow-up if you need more.",
        proof_to_response=dict(machine_proof),
    )


def _try_interpreter_action_blocked_divert(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    classification: RequestClassification,
    route_decision: Mapping[str, Any],
    _capsule: Any | None = None,
    lm1_shared_seam: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac | None:
    """Flag-gated interpreter-LM routing for ACTION and BLOCKED routes.

    DISCIPLINE
    ----------
    - Only runs when OPENCLAW_INTERPRETER_LM="1".  OFF → returns None immediately.
    - Only applies to operator_maestro_chat surface messages that the DETERMINISTIC
      gate AND the BRAIN divert both declined (deterministic path returned None).
    - ADVISORY ONLY:
      * ACTION (high-conf): consults authority_gate.decide() for the verdict
        (ALLOW/HITL_REQUIRED/DENY).  The interpreter NEVER decides authority —
        the gate decides.  NO execution, no executor call, no real side effect.
        external_actions_locked / email_send_performed / ledger_mutation_performed
        are all False (same as the brain divert).
      * BLOCKED (high-conf): surfaces "blocked / needs approval" to the operator.
        No execution, no executor call.
    - Fallback: any exception, low-confidence, or UNCERTAIN result → None so the
      caller falls through to the deterministic workflow consumer path.
    - The interpreter result carries NO authority/allow/send/action field and is
      NEVER consulted by authority_gate for a gate pass — it only identifies that
      the gate should be consulted.
    """
    if not _interpreter_enabled():
        return None

    if _maestro_frontdoor_surface(raw_request) != "operator_maestro_chat":
        return None

    # Defense-in-depth: only augment messages the DETERMINISTIC gate declined.
    if _is_maestro_frontdoor_operator_instruction(raw_request):
        return None

    operator_text = maestro_cassandra_responder.operator_text_from_request(raw_request)
    if not operator_text:
        return None

    interp_result = _lm1_result_from_seam(lm1_shared_seam)
    if interp_result is None:
        if (
            isinstance(lm1_shared_seam, Mapping)
            and str((lm1_shared_seam.get("interpretation") or {}).get("source") or "")
            == "deterministic_workflow_classifier"
        ):
            return None
        try:
            interp_result = _interpret_for_request(operator_text)
        except Exception:  # noqa: BLE001 — interpreter error → deterministic path
            return None

    # Only handle ACTION and BLOCKED here; BRAIN is handled by _try_interpreter_brain_divert.
    if not (interp_result.is_high_confidence_action() or interp_result.is_high_confidence_blocked()):
        return None

    # Common fields for both response types
    request_id = str(
        raw_request.get("request_id")
        or raw_request.get("source_request_id")
        or f"missing_request_id_{request_path.stem}"
    )
    current_world = str(
        raw_request.get("current_world_ref")
        or raw_request.get("currentWorldRef")
        or raw_request.get("world_ref")
        or raw_request.get("worldRef")
        or raw_request.get("world")
        or "general"
    )
    current_thread = str(
        raw_request.get("current_thread_ref")
        or raw_request.get("currentThreadRef")
        or raw_request.get("thread_ref")
        or raw_request.get("threadRef")
        or _maestro_frontdoor_surface(raw_request)
        or "operator_maestro_chat"
    )
    source_surface = _maestro_frontdoor_surface(raw_request) or "operator_maestro_chat"
    response_classification = _maestro_frontdoor_classification(classification, request_path=request_path)
    response_provenance = {
        "speaker": "Maestro",
        "lane": "telegram_pc_maestro_listener",
        "relay_origin": None,
        "actor": "maestro",
        "surface_ref": source_surface,
        "message_role": "final_agent_reply",
        "source_request_id": request_id,
    }
    base_machine_proof = {
        "interpreter_lm_divert": True,
        "interpreter_route": interp_result.route,
        "interpreter_confidence": interp_result.confidence,
        "interpreter_reason": interp_result.reason,
        "interpreter_fact_selection": list(interp_result.fact_selection),
        "lm1_shared_seam_used": isinstance(lm1_shared_seam, Mapping)
        and bool(lm1_shared_seam.get("rich_context_packet")),
        "lm1_shared_packet_id": str(
            ((lm1_shared_seam or {}).get("rich_context_packet") or {}).get("packet_id")
            if isinstance(lm1_shared_seam, Mapping)
            else ""
        ),
        "external_llm_invoked": False,
        "local_model_invoked": False,
        "model_call_performed": False,
        "protected_generate_called": False,
        "external_actions_locked": True,
        "email_send_performed": False,
        "ledger_mutation_performed": False,
    }
    base_detail = {
        "message_provenance": response_provenance,
        "request_message_provenance": raw_request.get("message_provenance")
        if isinstance(raw_request.get("message_provenance"), Mapping)
        else {
            "speaker": "Winship",
            "lane": "telegram_pc_maestro_listener",
            "relay_origin": None,
            "actor": "operator_winship",
            "surface_ref": source_surface,
            "message_role": "operator_prompt",
        },
        "correlation": {
            "source_request_id": request_id,
            "request_filename": request_path.name,
            "thread_ref": current_thread,
            "world_ref": current_world,
        },
        "operator_display": {"speaker_ref": "maestro"},
        "request_classification": asdict(response_classification),
        "original_request_classification": asdict(classification),
        "request_router_decision": dict(route_decision),
        "maestro_frontdoor_routing": {
            "source_surface": source_surface,
            "workflow_package_staged": False,
            "default_deny_preserved": True,
            "route_to_staging_when_not_answer_ready": True,
            "interpreter_lm_divert": True,
        },
        "lm1_shared_request_seam": _lm1_shared_request_seam_summary(lm1_shared_seam),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
        "workflow_package_staged": False,
        "workflow_package_request_v0_emitted": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "telegram_send_triggered": False,
        "business_action_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "paid_marking_performed": False,
        "external_llm_invoked": False,
        "local_model_runtime_connected": False,
    }

    # ── ACTION route: consult authority_gate; surface verdict; NO execution ────
    if interp_result.is_high_confidence_action():
        try:
            from authority_gate import decide as _gate_decide

            gate_decision = _gate_decide(
                "interpreter_action_proposal",
                surface="interpreter_action_proposal",
            )
            gate_verdict = gate_decision.verdict.value if hasattr(gate_decision.verdict, "value") else str(gate_decision.verdict)
            gate_reason = str(gate_decision.reason or "")
        except Exception:  # noqa: BLE001 — gate consult error → still surface safely
            gate_verdict = "DENY"
            gate_reason = "authority_gate_consult_error"

        operator_msg = (
            f"Treated as an action proposal. Authority gate: {gate_verdict} — {gate_reason}. "
            f"Interpreter reason: {interp_result.reason}. "
            "No action was executed. Operator approval required before any execution."
        )
        card = {
            "schema_version": "maestro_frontdoor_answer_card_v0",
            "card_id": f"maestro_interp_action_{_short_hash(request_id, operator_msg)}",
            "card_type": "MAESTRO_ACTION_PROPOSAL_ADVISORY",
            "title": f"Action proposal — gate: {gate_verdict}",
            "summary": operator_msg,
            "status_label": "Action Proposal",
            "route_status": "ACTION_PROPOSAL_SURFACED",
            "mac_render_hint": "advisory",
            "actions": [],
            "provenance": response_provenance,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
            "proof": {
                "proof_refs": [],
                "machine_proof": {
                    **base_machine_proof,
                    "authority_gate_consulted": True,
                    "authority_gate_verdict": gate_verdict,
                    "authority_gate_reason": gate_reason,
                    "action_executed": False,
                    "no_executor_called": True,
                },
            },
        }
        what_happened = (
            "OpenClaw recognized the general Maestro front-door chat surface.",
            f"The interpreter LM classified this as an ACTION proposal (confidence: {interp_result.confidence:.2f}).",
            f"The authority gate was consulted and returned: {gate_verdict} — {gate_reason}.",
            "No action was executed. No executor, workflow, or business action was called.",
            "No email, Gmail, browser, Coupa, submit, ledger, workbook, PDF, paid marking, or external business action occurred.",
        )
        why_it_happened = (
            f"Interpreter classified route=ACTION with confidence {interp_result.confidence:.2f}. "
            f"Reason: {interp_result.reason}. Authority gate verdict: {gate_verdict}."
        )
        detail = {
            **base_detail,
            "dynamic_card_response": card,
            "interpreter_action_proposal": {
                "authority_gate_consulted": True,
                "authority_gate_verdict": gate_verdict,
                "authority_gate_reason": gate_reason,
                "action_executed": False,
                "no_executor_called": True,
            },
        }
        return OpenClawResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=f"{current_world}/{current_thread}",
            request_type="CHAT",
            internal_status="RESPONSE_READY",
            operator_headline=f"Action proposal — gate: {gate_verdict}",
            operator_message=operator_msg,
            what_happened=what_happened,
            why_it_happened=why_it_happened,
            how_to_fix="Review the authority gate verdict. No action was executed. Provide explicit approval if needed.",
            visible_cards=(card,),
            cards_available=True,
            card_mirror_refs=(),
            file_readback_refs=(),
            worker_route_refs=(
                {
                    "selected_worker_target": "PC_CODEX",
                    "selected_machine": "PC_WSL",
                    "routing_status": "PROCESSING_ON_PC",
                    "selected_rail": "INTERPRETER_ACTION_ADVISORY",
                    "controller_event_type": "action_proposal",
                    "route_status": "ACTION_PROPOSAL_SURFACED",
                    "backend_route": "interpreter_action_advisory",
                    "interpreter_lm_divert": True,
                },
            ),
            context_package_refs=(),
            blocked_reason=None,
            detail_disclosure=detail,
            readback_files=(),
            next_safe_move="Review the authority gate verdict and provide explicit approval if you want the action to proceed.",
        )

    # ── BLOCKED route: surface the block to the operator; NO execution ─────────
    operator_msg = (
        f"This request needs operator approval or is blocked: {interp_result.reason}. "
        "No action was executed. Please provide explicit approval to proceed."
    )
    card = {
        "schema_version": "maestro_frontdoor_answer_card_v0",
        "card_id": f"maestro_interp_blocked_{_short_hash(request_id, operator_msg)}",
        "card_type": "MAESTRO_BLOCKED_ADVISORY",
        "title": "Blocked — operator approval required",
        "summary": operator_msg,
        "status_label": "Blocked",
        "route_status": "BLOCKED_PENDING_APPROVAL",
        "mac_render_hint": "advisory",
        "actions": [],
        "provenance": response_provenance,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "proof": {
            "proof_refs": [],
            "machine_proof": {
                **base_machine_proof,
                "action_executed": False,
                "no_executor_called": True,
            },
        },
    }
    what_happened = (
        "OpenClaw recognized the general Maestro front-door chat surface.",
        f"The interpreter LM classified this as BLOCKED/needs-approval (confidence: {interp_result.confidence:.2f}).",
        "No action was executed. No executor, workflow, or business action was called.",
        "No email, Gmail, browser, Coupa, submit, ledger, workbook, PDF, paid marking, or external business action occurred.",
    )
    why_it_happened = (
        f"Interpreter classified route=BLOCKED with confidence {interp_result.confidence:.2f}. "
        f"Reason: {interp_result.reason}."
    )
    detail = {
        **base_detail,
        "dynamic_card_response": card,
        "interpreter_blocked": {
            "action_executed": False,
            "no_executor_called": True,
            "block_reason": interp_result.reason,
        },
    }
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=f"{current_world}/{current_thread}",
        request_type="CHAT",
        internal_status="BLOCKED_WITH_REASON",
        operator_headline="Blocked — operator approval required",
        operator_message=operator_msg,
        what_happened=what_happened,
        why_it_happened=why_it_happened,
        how_to_fix="Provide explicit operator approval if you want this to proceed.",
        visible_cards=(card,),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_worker_target": "PC_CODEX",
                "selected_machine": "PC_WSL",
                "routing_status": "BLOCKED",
                "selected_rail": "INTERPRETER_BLOCKED_ADVISORY",
                "controller_event_type": "blocked_approval_required",
                "route_status": "BLOCKED_PENDING_APPROVAL",
                "backend_route": "interpreter_blocked_advisory",
                "interpreter_lm_divert": True,
            },
        ),
        context_package_refs=(),
        blocked_reason=interp_result.reason,
        detail_disclosure=detail,
        readback_files=(),
        next_safe_move="Provide explicit operator approval if you want this to proceed.",
    )


def _process_parked_router_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    classification: RequestClassification,
    route_decision: Mapping[str, Any],
) -> OpenClawResponseForMac:
    routed_classification = _classification_from_router_decision(
        classification,
        request_path=request_path,
        decision=route_decision,
    )
    reason = str(route_decision.get("rejected_reason") or "No registered request handler matched this request.")
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or route_decision.get("source_request_id") or "unknown_request"),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or route_decision.get("workflow_ref") or "unknown"),
        request_type=routed_classification.request_family,
        internal_status="BLOCKED_WITH_REASON",
        operator_headline="OpenClaw needs a registered handler",
        operator_message="OpenClaw received the request, but no bounded backend handler is registered for that request contract yet.",
        what_happened=(
            "PC loaded the request through the governed intake path.",
            "The generic request router parked it before any handler could run.",
            "No external action, model call, worker dispatch, or workflow execution occurred.",
        ),
        why_it_happened=reason,
        how_to_fix="Register a bounded handler for this request kind, intended use, and scope before retrying.",
        visible_cards=(
            {
                "title": "Handler needed",
                "bullets": (
                    f"Kind: {route_decision.get('request_kind')}",
                    f"Intended use: {route_decision.get('intended_use')}",
                    "No handler executed.",
                ),
                "status_tone": "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=reason,
        detail_disclosure={
            "request_router_decision": dict(route_decision),
            "request_classification": asdict(routed_classification),
            "external_actions_locked": True,
        },
        readback_files=(),
        next_safe_move="Next: register a bounded handler or resend a supported request contract.",
    )


def _process_client_invoice_sheet_audit_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
) -> OpenClawResponseForMac | None:
    if not client_invoice_sheet_audit.is_sheet_audit_request(raw_request):
        return None

    audit_payload = client_invoice_sheet_audit.run_audit(
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
    )
    audit_json, audit_operator = client_invoice_sheet_audit.write_exports(audit_payload, export_root)
    audit_request = audit_payload["audit_request"]
    audit_result = audit_payload["audit_result"]
    audit_readback = audit_payload["audit_readback"]
    status = str(audit_readback["status"])
    terminal_ready = status == "SHEET_AUDIT_COMPLETE"
    sheet_classification = _sheet_audit_classification(classification, request_path=request_path)
    headline = str(audit_readback["operator_headline"])
    message = str(audit_readback["operator_message"])
    next_action = str(audit_readback["next_action"])
    missing_items = tuple(str(item) for item in audit_readback.get("missing_items") or ())
    primary_blocker = "None" if terminal_ready else (missing_items[0] if missing_items else status)
    detail = {
        "client_invoice_sheet_audit": {
            "audit_readback_ref": audit_json.as_posix(),
            "operator_readback_ref": audit_operator.as_posix(),
            "audit_request": audit_request,
            "audit_result": audit_result,
            "audit_readback": audit_readback,
            "schema_explicit": bool(audit_result.get("schema_explicit")),
            "path_pc_readable": bool(audit_result.get("path_pc_readable")),
            "workbook_path_known_and_approved": bool(audit_result.get("workbook_path_known_and_approved")),
            "whitelisted_cells_read": bool(audit_payload["machine_proof"]["whitelisted_cells_read"]),
            "body_ingested": False,
            "arbitrary_parse": False,
            "inferred_schema": False,
            "full_sheet_dump": False,
            "formula_evaluated": False,
            "macro_processed": False,
            "external_links_followed": False,
            "external_action_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "CLIENT_INVOICE_SHEET_AUDIT",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": status.replace("_", " ").title(),
            "primary_blocker": primary_blocker,
            "next_action": next_action,
            "missing_items_short": missing_items,
            "detail_summary": f"Fields read: {len(audit_result.get('fields_read') or ())}. PO/reference: {audit_result.get('po_reference_status')}.",
            "proof_refs": (f"generated/read_models/{client_invoice_sheet_audit.JSON_EXPORT_NAME}",),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(sheet_classification),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or audit_request["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or audit_request["workflow_ref"]),
        request_type=classification.request_family,
        internal_status="RESPONSE_READY" if terminal_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC selected the whitelisted client invoice sheet audit rail.",
            "PC required a registered workbook, an approved PC-readable path, and an explicit schema before any cell read.",
            "PC read only whitelisted cells when all gates were present.",
            "No arbitrary workbook parsing, formula evaluation, PDF generation, email, Coupa, browser, workflow, agent, or external action occurred.",
        ),
        why_it_happened=(
            "The sheet audit gates were present and the whitelisted fields were checked."
            if terminal_ready
            else "The sheet audit gate failed closed before any unsafe workbook action."
        ),
        how_to_fix="No fix is needed. Continue with the next governed invoice lane." if terminal_ready else next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    str(audit_readback.get("client_summary") or ""),
                    str(audit_readback.get("workbook_summary") or ""),
                    f"PO/reference status: {audit_result.get('po_reference_status')}",
                    next_action,
                ),
                "status_tone": "ready" if terminal_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(audit_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if terminal_ready else primary_blocker,
        detail_disclosure=detail,
        readback_files=(audit_json.as_posix(), audit_operator.as_posix()),
        next_safe_move=next_action,
    )


def _process_deterministic_intent_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
) -> OpenClawResponseForMac | None:
    interpretation = deterministic_intent_interpreter.interpret_request(
        raw_request,
        request_filename=request_path.name,
        export_root=export_root,
        generated_at=generated_at,
    )
    if not interpretation.matched or interpretation.response_plan is None or interpretation.candidate is None:
        return None

    interpreter_payload = deterministic_intent_interpreter.build_payload_from_interpretation(
        interpretation,
        generated_at=generated_at,
    )
    interpreter_json, interpreter_operator = deterministic_intent_interpreter.write_exports(interpreter_payload, export_root)
    intent_classification = _deterministic_intent_classification(
        classification,
        match_id=interpretation.match_id,
        request_path=request_path,
    )
    plan = interpretation.response_plan
    candidate = interpretation.candidate
    validation = interpretation.validation_result or {}
    session_state = interpretation.session_state
    readback_files = (interpreter_json.as_posix(), interpreter_operator.as_posix())
    blocked_reason = plan.primary_blocker if plan.internal_status != "RESPONSE_READY" else None
    detail = {
        "deterministic_intent_interpreter": {
            "interpreter_readback_ref": interpreter_json.as_posix(),
            "operator_readback_ref": interpreter_operator.as_posix(),
            "matched": True,
            "match_id": interpretation.match_id,
            "candidate": asdict(candidate),
            "validation_result": validation,
            "missing_requirements": interpretation.missing_requirements,
            "build_cues": interpretation.build_cues,
            "context_gaps": interpretation.context_gaps,
            "blockers": interpretation.blockers,
            "session_state": session_state,
            "capability_query_trace": interpretation.capability_query_trace,
            "session_resolver_used": True,
            "capability_query_used": True,
            "validator_used": True,
            "response_author": plan.response_author,
            "selected_worker_type": "PC_CODEX",
            "visual_event_package_requested": plan.visual_event_package_requested,
            "authority_scout": interpretation.authority_scout,
            "external_actions_locked": True,
            "model_or_worker_response_adapter_called": False,
            "live_lm_interpreter_called": False,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "worker_dispatch_performed": False,
            "workflow_run_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "approval_execution_performed": False,
            "candidate_promotion_performed": False,
            "registry_mutation_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "DETERMINISTIC_INTENT_RESPONSE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": plan.headline,
            "one_line_answer": plan.one_line_answer,
            "eliwinship": plan.eliwinship,
            "primary_status": plan.primary_status,
            "primary_blocker": plan.primary_blocker,
            "next_action": plan.next_action,
            "missing_items_short": plan.missing_items_short,
            "detail_summary": plan.detail_summary,
            "proof_refs": (f"generated/read_models/{deterministic_intent_interpreter.JSON_EXPORT_NAME}",),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(intent_classification),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=interpretation.source_request_id,
        source_request_filename=request_path.name,
        workflow_ref=candidate.target_workflow_ref,
        request_type="CHAT",
        internal_status=plan.internal_status,
        operator_headline=plan.operator_headline,
        operator_message=plan.operator_message,
        what_happened=plan.what_happened,
        why_it_happened=plan.why_it_happened,
        how_to_fix=plan.how_to_fix,
        visible_cards=plan.visible_cards,
        cards_available=bool(plan.visible_cards),
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(
            {
                "selected_agent_role": candidate.target_agent_role,
                "selected_worker_type": candidate.target_worker_type,
                "live_agent_dispatch_allowed": False,
                "live_worker_dispatch_allowed": False,
                "read_model_ref": interpreter_json.as_posix(),
            },
        ),
        context_package_refs=(),
        blocked_reason=blocked_reason,
        detail_disclosure=detail,
        readback_files=readback_files,
        next_safe_move=plan.next_safe_move,
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
    audit_handoff = _process_client_invoice_audit_handoff_request(
        request_path,
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
        classification=classification,
    )
    if audit_handoff is not None:
        return audit_handoff

    sheet_audit = _process_client_invoice_sheet_audit_request(
        request_path,
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
        classification=classification,
    )
    if sheet_audit is not None:
        return sheet_audit

    if _is_capital_hilton_mark_sent_status_question(raw_request):
        return _process_capital_hilton_status_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=classification,
            read_model_reader=read_model_reader,
        )

    interpreted = _process_deterministic_intent_request(
        request_path,
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
        classification=classification,
    )
    if interpreted is not None:
        return interpreted

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


def _is_workbook_candidate_keep_choice_request(raw_request: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(raw_request.get(field) or "")
        for field in ("operator_message", "sanitized_message_summary", "operator_goal")
    ).lower()
    if str(raw_request.get("client_ref") or "") != "capital_hilton":
        return False
    if str(raw_request.get("workflow_ref") or "") != "capital_hilton_invoice_workflow":
        return False
    if str(raw_request.get("world_ref") or "") != "finance":
        return False
    return (
        "workbook" in text
        and "candidate" in text
        and ("replacement" in text or "replace" in text)
        and ("cancel" in text or "leave" in text or "keep" in text)
    )


def _operator_text(raw_request: Mapping[str, Any]) -> str:
    return " ".join(
        str(raw_request.get(field) or "")
        for field in ("operator_message", "sanitized_message_summary", "operator_goal", "message", "text")
    )


def _compact_operator_text(raw_request: Mapping[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _operator_text(raw_request).lower()).strip()


def _is_capital_hilton_workbook_scope(raw_request: Mapping[str, Any]) -> bool:
    if str(raw_request.get("client_ref") or "") != "capital_hilton":
        return False
    if str(raw_request.get("workflow_ref") or "") != "capital_hilton_invoice_workflow":
        return False
    if str(raw_request.get("world_ref") or "") != "finance":
        return False
    return True


def _has_any_phrase(compact_text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in compact_text for phrase in phrases)


def _has_workbook_selection_negative(compact_text: str) -> bool:
    return _has_any_phrase(
        compact_text,
        (
            "do not replace",
            "dont replace",
            "don t replace",
            "cancel replace",
            "cancel replacement",
            "leave candidate",
            "keep candidate",
            "leave the test workbook as a candidate",
            "keep the test workbook as a candidate",
        ),
    )


def is_workbook_active_selection_request(raw_request: Mapping[str, Any]) -> bool:
    """Detect safe operator intent to make the recent workbook the active reference.

    This is intentionally scoped to the current Capital Hilton steel-thread refs
    and only updates OpenClaw's active workbook reference. It never means
    physical file deletion.
    """

    compact = _compact_operator_text(raw_request)
    if not _is_capital_hilton_workbook_scope(raw_request):
        return False
    if _has_workbook_selection_negative(compact):
        return False
    has_workbook_or_file = _has_any_phrase(
        compact,
        (
            "workbook",
            "workbok",
            "work book",
            "spreadsheet",
            "file",
        ),
    )
    has_recent_or_selected_ref = _has_any_phrase(
        compact,
        (
            "this is",
            "this should",
            "this one",
            "file i just gave",
            "file i just added",
            "file just gave",
            "file just added",
            "just told",
            "already gave",
            "already provided",
            "already told",
            "just gave",
            "just added",
            "new workbook",
            "new workbok",
            "new file",
            "newest workbook",
            "newest file",
            "latest workbook",
            "latest file",
            "this workbook",
            "this workbok",
            "this file",
            "selected workbook",
            "selected file",
            "make this",
            "set this",
        ),
    )
    has_real_or_current_intent = _has_any_phrase(
        compact,
        (
            "actual workbook",
            "real workbook",
            "correct workbook",
            "right workbook",
            "should use",
            "use this workbook",
            "use this workbok",
            "use this file",
            "use the file",
            "use the newest",
            "use the latest",
            "make this the current",
            "make this current",
            "make current",
            "make it current",
            "set this as current",
            "set it as current",
            "active workbook",
            "current workbook",
            "current work book",
            "replace the old",
            "replace old",
            "replace the previous",
            "replace previous",
            "replace the test",
            "replace test",
            "supersede the old",
            "supersede old",
        ),
    )
    if has_workbook_or_file and _has_any_phrase(compact, ("real", "actual", "correct", "right")):
        has_real_or_current_intent = True
    has_retire_other_intent = _has_any_phrase(
        compact,
        (
            "delete the other",
            "delete other",
            "remove the other",
            "remove other",
            "retire the other",
            "retire other",
            "retire the old",
            "retire old",
            "get rid of the other",
            "get rid of other",
            "remove it from openclaw",
            "remove it from open claw",
            "delete it from openclaw",
            "delete it from open claw",
            "from openclaw",
            "from open claw",
        ),
    )
    marks_previous_as_test = _has_any_phrase(compact, ("last", "old", "previous", "prior", "other")) and "test" in compact

    if has_workbook_or_file and has_recent_or_selected_ref and has_real_or_current_intent:
        return True
    if has_workbook_or_file and marks_previous_as_test and has_real_or_current_intent:
        return True
    if has_workbook_or_file and has_real_or_current_intent and has_retire_other_intent:
        return True
    if has_recent_or_selected_ref and has_real_or_current_intent and has_retire_other_intent:
        return True
    if has_retire_other_intent and _has_any_phrase(compact, ("other one", "other")) and _has_any_phrase(
        compact, ("openclaw", "open claw")
    ):
        return True
    return False


def is_workbook_active_selection_ambiguous_request(raw_request: Mapping[str, Any]) -> bool:
    compact = _compact_operator_text(raw_request)
    if is_workbook_active_selection_request(raw_request):
        return False
    if not _is_capital_hilton_workbook_scope(raw_request):
        return False
    if _has_workbook_selection_negative(compact):
        return False
    if _has_any_phrase(
        compact,
        (
            "show",
            "status",
            "where are we",
            "what is",
            "what s",
            "whats",
            "blocking",
            "blocked",
            "audit",
        ),
    ):
        return False
    has_workbook_or_file = _has_any_phrase(compact, ("workbook", "workbok", "work book", "spreadsheet", "file"))
    has_mutating_selection_verb = _has_any_phrase(
        compact,
        (
            "use",
            "make",
            "set",
            "replace",
            "switch",
            "remove",
            "delete",
            "retire",
            "supersede",
        ),
    )
    return has_workbook_or_file and has_mutating_selection_verb


def _is_workbook_candidate_replace_choice_request(raw_request: Mapping[str, Any]) -> bool:
    return is_workbook_active_selection_request(raw_request)


def _workbook_candidate_choice_classification(
    request_path: Path,
    classification: RequestClassification,
    *,
    action: str = "keep_candidate",
) -> RequestClassification:
    return RequestClassification(
        classification_id=classification.classification_id,
        source_request_filename=request_path.name,
        request_family=classification.request_family,
        selected_rail="client_invoice_workbook_candidate_choice",
        classification_reason=(
            "Filename matches Mission Control chat request pattern and operator text deterministically resolves workbook replacement."
        ),
        future_supported=False,
        next_safe_move=(
            "Record the candidate-only choice and publish a scoped Mac response."
            if action == "keep_candidate"
            else "Record the new workbook as current and publish a scoped Mac response."
        ),
    )


def _process_workbook_candidate_choice_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
) -> OpenClawResponseForMac:
    choice_classification = _workbook_candidate_choice_classification(request_path, classification, action="keep_candidate")
    registry_payload = client_invoice_workbook_registry.keep_candidate_and_cancel_replacement(
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
    )
    registry_json, registry_operator = client_invoice_workbook_registry.write_exports(registry_payload, export_root)
    readback = registry_payload["registration_readback"]
    active_record = registry_payload.get("active_record") or {}
    candidate_record = registry_payload.get("candidate_record") or {}
    headline = str(readback["operator_headline"])
    message = str(readback["operator_message"])
    operator_message = "Replacement canceled. Candidate remains staged."
    one_line_answer = "Current workbook kept; test workbook remains candidate-only."
    next_action = str(readback["next_action"])
    next_safe_move = "Wait for field mapping or a real workbook file."
    response_files = (registry_json.as_posix(), registry_operator.as_posix())
    detail = {
        "client_invoice_workbook_registry": {
            "registry_readback_ref": registry_json.as_posix(),
            "operator_readback_ref": registry_operator.as_posix(),
            "registration_readback": readback,
            "active_record": active_record,
            "candidate_record": candidate_record,
            "operator_choice_request": registry_payload.get("operator_choice_request"),
            "duplicate_result": registry_payload.get("duplicate_result"),
            "existing_workbook_preserved": bool(active_record),
            "candidate_preserved": bool(candidate_record),
            "approved_for_metadata_read": bool(candidate_record.get("approved_for_metadata_read")),
            "approved_for_cell_read": bool(candidate_record.get("approved_for_cell_read")),
            "workbook_replacement_performed": False,
            "candidate_promoted_to_authoritative": False,
            "workbook_body_read_performed": False,
            "spreadsheet_parse_performed": False,
            "spreadsheet_cell_read_performed": False,
            "folder_scan_performed": False,
            "external_action_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "CLIENT_INVOICE_WORKBOOK_CANDIDATE_CHOICE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": one_line_answer,
            "eliwinship": message,
            "primary_status": "Workbook candidate kept",
            "primary_blocker": "None",
            "next_action": next_action,
            "missing_items_short": (),
            "detail_summary": str(readback.get("workbook_summary") or ""),
            "proof_refs": (f"generated/read_models/{client_invoice_workbook_registry.JSON_EXPORT_NAME}",),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "persistent_registry_write": False,
        "generated_registry_readmodel_write": True,
        "request_classification": asdict(choice_classification),
    }
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or "unknown_request"),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "capital_hilton_invoice_workflow"),
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline=headline,
        operator_message=operator_message,
        what_happened=(
            "PC consumed the operator choice request from the approved inbox.",
            "PC kept the existing Capital Hilton workbook reference unchanged.",
            "PC left the test workbook staged as a candidate only.",
            "No workbook body, cells, sheet audit, or external action occurred.",
        ),
        why_it_happened="The operator explicitly chose to leave the test workbook as a candidate and cancel replacement.",
        how_to_fix="No fix is needed. Provide field mapping later, or add the real workbook file when ready.",
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    "Current Capital Hilton workbook kept.",
                    "Test workbook remains candidate-only.",
                    "Workbook body and cells were not read.",
                    next_action,
                ),
                "status_tone": "ready",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(registry_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure=detail,
        readback_files=response_files,
        next_safe_move=next_safe_move,
    )


def _process_workbook_candidate_replace_choice_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
) -> OpenClawResponseForMac:
    choice_classification = _workbook_candidate_choice_classification(request_path, classification, action="replace_candidate")
    registry_payload = client_invoice_workbook_registry.replace_current_with_candidate(
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
    )
    registry_json, registry_operator = client_invoice_workbook_registry.write_exports(registry_payload, export_root)
    readback = registry_payload["registration_readback"]
    active_record = registry_payload.get("active_record") or {}
    headline = str(readback["operator_headline"])
    message = str(readback["operator_message"])
    next_action = str(readback["next_action"])
    response_files = (registry_json.as_posix(), registry_operator.as_posix())
    machine_proof = registry_payload.get("machine_proof", {})
    replacement_performed = bool(machine_proof.get("workbook_replacement_performed"))
    current_workbook_confirmed = bool(machine_proof.get("current_workbook_confirmation_performed"))
    workbook_confirmed_for_source = replacement_performed or current_workbook_confirmed
    source_workbook_payload: dict[str, Any] | None = None
    if workbook_confirmed_for_source and active_record:
        source_workbook_payload = invoice_review_action_request_handler.process_source_workbook_selection_result_request(
            {
                "request_id": str(raw_request.get("request_id") or "workbook_candidate_replace_choice"),
                "request_type": "OPERATOR_CORRECTION_TO_PENDING_REQUEST",
                "type": "OPERATOR_CORRECTION_TO_PENDING_REQUEST",
                "kind": "OPERATOR_CORRECTION_TO_PENDING_REQUEST",
                "intended_use": "confirm_source_workbook_reference",
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_workflow",
                "related_source_request_id": raw_request.get("related_source_request_id"),
                "operator_text": _operator_text(raw_request),
                "correction_kind": "confirm_current_source_workbook",
                "operator_provided": True,
                "operator_confirmed": True,
                "artifact_ref": active_record.get("workbook_ref"),
                "workbook_display_name": active_record.get("workbook_display_name"),
                "workbook_extension": active_record.get("workbook_extension"),
                "file_size_bytes": active_record.get("file_size_bytes"),
                "no_workbook_body_read": True,
                "no_cell_read": True,
                "no_external_action": True,
                "physical_deletion_allowed": False,
            },
            generated_at=generated_at,
            db_path=(
                invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_DB_PATH
                if export_root.resolve() == invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_EXPORT_ROOT.resolve()
                else export_root.parent / "invoice_review_state.sqlite"
            ),
            export_root=export_root,
            bridge_export_root=(
                invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT
                if export_root.resolve() == invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_EXPORT_ROOT.resolve()
                else None
            ),
            event_db_path=(
                invoice_review_action_request_handler.operator_action_event_journal.DEFAULT_DB_PATH
                if export_root.resolve() == invoice_review_action_request_handler.invoice_review_state_machine.DEFAULT_EXPORT_ROOT.resolve()
                else export_root.parent / "operator_action_events.sqlite"
            ),
            event_export_root=export_root,
        )
    detail = {
        "client_invoice_workbook_registry": {
            "registry_readback_ref": registry_json.as_posix(),
            "operator_readback_ref": registry_operator.as_posix(),
            "registration_readback": readback,
            "active_record": active_record,
            "operator_choice_request": registry_payload.get("operator_choice_request"),
            "duplicate_result": registry_payload.get("duplicate_result"),
            "workbook_replacement_performed": replacement_performed,
            "current_workbook_confirmation_performed": current_workbook_confirmed,
            "candidate_promoted_to_current_workbook": bool(
                registry_payload.get("machine_proof", {}).get("candidate_promoted_to_current_workbook")
            ),
            "candidate_promoted_to_authoritative": False,
            "approved_for_metadata_read": bool(active_record.get("approved_for_metadata_read")),
            "approved_for_cell_read": bool(active_record.get("approved_for_cell_read")),
            "workbook_body_read_performed": False,
            "spreadsheet_parse_performed": False,
            "spreadsheet_cell_read_performed": False,
            "folder_scan_performed": False,
            "external_action_performed": False,
            "invoice_sent_or_submitted": False,
            "ledger_posted": False,
        },
        "source_workbook_selection_result": source_workbook_payload,
        "layered_response_fields": {
            "response_kind": "CLIENT_INVOICE_WORKBOOK_CANDIDATE_CHOICE",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": (
                "Capital Hilton source workbook confirmed. Nothing was deleted from disk and workbook cells were not read. Next: select the invoice page/period again from this workbook."
                if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED"
                else message
            ),
            "eliwinship": (
                "Capital Hilton source workbook confirmed. Nothing was deleted from disk and workbook cells were not read. Next: select the invoice page/period again from this workbook."
                if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED"
                else message
            ),
            "primary_status": "Workbook updated" if workbook_confirmed_for_source else "Workbook update blocked",
            "primary_blocker": "None" if workbook_confirmed_for_source else "No staged workbook candidate",
            "next_action": (
                "Next: select the invoice page/period again from the confirmed workbook."
                if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED"
                else next_action
            ),
            "missing_items_short": tuple(readback.get("missing_items") or ()),
            "detail_summary": str(readback.get("workbook_summary") or ""),
            "proof_refs": tuple(
                ref
                for ref in (
                    f"generated/read_models/{client_invoice_workbook_registry.JSON_EXPORT_NAME}",
                    (source_workbook_payload or {}).get("action_start_receipt", {}).get("receipt_id")
                    if source_workbook_payload
                    else None,
                )
                if ref
            ),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "persistent_registry_write": False,
        "generated_registry_readmodel_write": True,
        "request_classification": asdict(choice_classification),
    }
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or "unknown_request"),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "capital_hilton_invoice_workflow"),
        request_type="CHAT",
        internal_status="RESPONSE_READY" if workbook_confirmed_for_source else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=(
            "Capital Hilton source workbook confirmed. Nothing was deleted from disk and workbook cells were not read. Next: select the invoice page/period again from this workbook."
            if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED"
            else "I have the workbook candidate. To make it the Capital Hilton source workbook, confirm it as the source workbook. I will not read workbook cells or delete anything."
            if replacement_performed
            else "Workbook update blocked."
        ),
        what_happened=(
            "PC consumed the operator workbook choice request from the approved inbox.",
            "PC confirmed the staged workbook candidate as the Capital Hilton source workbook."
            if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED" and replacement_performed
            else "PC confirmed the existing Capital Hilton workbook as the source workbook."
            if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED"
            else "PC made the staged workbook candidate the current running workbook reference."
            if replacement_performed
            else "PC could not find a staged workbook candidate to make current.",
            "No workbook body, cells, sheet audit, PDF, email, Coupa, ledger posting, or external action occurred.",
        ),
        why_it_happened=(
            "The operator said the previous workbook was a test and the new workbook is the real Capital Hilton running workbook."
            if replacement_performed
            else "The operator clarified that the already captured Capital Hilton workbook is the current source workbook."
            if current_workbook_confirmed
            else "There was no staged candidate in the workbook registry read-model."
        ),
        how_to_fix=(
            "Next: select the invoice page/period again from the confirmed workbook."
            if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED"
            else next_action
        ),
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    message,
                    "Workbook body and cells were not read.",
                    "Nothing was sent, submitted, posted, exported, or marked paid.",
                    next_action,
                ),
                "status_tone": "ready" if workbook_confirmed_for_source else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(registry_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if workbook_confirmed_for_source else "No staged workbook candidate.",
        detail_disclosure=detail,
        readback_files=response_files,
        next_safe_move=(
            "Next: select the invoice page/period again from the confirmed workbook."
            if source_workbook_payload and source_workbook_payload.get("status") == "GUIDED_RESULT_RECORDED"
            else next_action
        ),
    )


def _process_workbook_active_selection_ambiguity_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    classification: RequestClassification,
) -> OpenClawResponseForMac:
    request_id = str(raw_request.get("request_id") or "unknown_workbook_selection_request")
    workflow_ref = str(raw_request.get("workflow_ref") or "capital_hilton_invoice_workflow")
    headline = "Which workbook should I use?"
    message = (
        "I found Capital Hilton workbook context, but I need to know whether to use the newest workbook you just added "
        "or keep the current active one. Nothing was deleted from disk."
    )
    next_action = "Next: choose the newest workbook or keep the current active workbook."
    detail = {
        "workbook_selection_intent": {
            "status": "AMBIGUOUS_WORKBOOK_SELECTION",
            "client_ref": str(raw_request.get("client_ref") or ""),
            "workflow_ref": workflow_ref,
            "world_ref": str(raw_request.get("world_ref") or ""),
            "physical_file_delete_performed": False,
            "registry_reference_retired": False,
            "workbook_body_read_performed": False,
            "spreadsheet_parse_performed": False,
            "spreadsheet_cell_read_performed": False,
            "sheet_audit_performed": False,
            "external_action_performed": False,
            "invoice_sent_or_submitted": False,
            "ledger_posted": False,
        },
        "layered_response_fields": {
            "response_kind": "CLIENT_INVOICE_WORKBOOK_SELECTION_CLARIFICATION",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": "Workbook choice needed",
            "primary_blocker": "Ambiguous workbook selection",
            "next_action": next_action,
            "missing_items_short": ("which workbook should be current",),
            "detail_summary": "OpenClaw needs one workbook-selection confirmation before changing active references.",
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "request_classification": asdict(classification),
    }
    return OpenClawResponseForMac(
        source_request_id=request_id,
        source_request_filename=request_path.name,
        workflow_ref=workflow_ref,
        request_type="CHAT",
        internal_status="CLARIFICATION_REQUIRED",
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC recognized a workbook-selection request in the Capital Hilton workflow.",
            "PC did not change the active workbook reference because the target workbook was ambiguous.",
            "No file was deleted from disk.",
            "No workbook body, cells, sheet audit, PDF, email, Coupa, ledger posting, or external action occurred.",
        ),
        why_it_happened="The operator asked to change workbook state, but the exact workbook choice was not deterministic enough.",
        how_to_fix=next_action,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    "No workbook reference changed.",
                    "Nothing was deleted from disk.",
                    "Workbook body and cells were not read.",
                    next_action,
                ),
                "status_tone": "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason="Ambiguous workbook selection.",
        detail_disclosure=detail,
        readback_files=(),
        next_safe_move=next_action,
    )


def _workbook_registration_request_classification(classification: RequestClassification) -> RequestClassification:
    return RequestClassification(
        classification_id=f"request_classification_{_short_hash(classification.source_request_filename, 'workbook_registration')}",
        source_request_filename=classification.source_request_filename,
        request_family="WORKBOOK_REGISTRATION_REQUEST",
        selected_rail="client_invoice_workbook_registry",
        classification_reason=(
            "Request envelope is a Mission Control WORKBOOK_REGISTRATION_REQUEST_V0 workbook chooser action."
        ),
        future_supported=False,
        next_safe_move="Record the workbook reference as metadata only and return a Mac readback.",
    )


def _process_workbook_registration_request(
    request_path: Path,
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str | None,
    classification: RequestClassification,
    route_decision: Mapping[str, Any] | None = None,
) -> OpenClawResponseForMac:
    registry_payload = client_invoice_workbook_registry.register_workbook_request(
        raw_request,
        export_root=export_root,
        generated_at=generated_at,
        source_file_metadata_ref=f"mission_control_request:{request_path.name}",
    )
    registry_json, registry_operator = client_invoice_workbook_registry.write_exports(registry_payload, export_root)
    workbook_readback = registry_payload["registration_readback"]
    active_record = registry_payload.get("active_record") or {}
    candidate_record = registry_payload.get("candidate_record") or {}
    status = str(workbook_readback["status"])
    terminal_ready = status == "WORKBOOK_REFERENCE_CAPTURED"
    headline = str(workbook_readback["operator_headline"])
    message = str(workbook_readback["operator_message"])
    next_action = str(workbook_readback["next_action"])
    missing_items = tuple(str(item) for item in workbook_readback.get("missing_items") or ())
    primary_blocker = "None" if terminal_ready else (missing_items[0] if missing_items else status)
    response_classification = _workbook_registration_request_classification(classification)
    detail = {
        "client_invoice_workbook_registry": {
            "registry_readback_ref": registry_json.as_posix(),
            "operator_readback_ref": registry_operator.as_posix(),
            "registration_request": registry_payload["registration_request"],
            "registration_readback": workbook_readback,
            "active_record": active_record,
            "candidate_record": candidate_record,
            "duplicate_result": registry_payload["duplicate_result"],
            "selected_local_path_received": bool(raw_request.get("selected_local_path")),
            "selected_local_path_stored_as_ref_only": True,
            "approved_for_metadata_read": bool((active_record or candidate_record).get("approved_for_metadata_read")),
            "approved_for_cell_read": bool((active_record or candidate_record).get("approved_for_cell_read")),
            "workbook_body_read_performed": False,
            "spreadsheet_parse_performed": False,
            "spreadsheet_cell_read_performed": False,
            "folder_scan_performed": False,
            "external_action_performed": False,
        },
        "layered_response_fields": {
            "response_kind": "CLIENT_INVOICE_WORKBOOK_REGISTRATION",
            "audience_mode": "ELIWINSHIP",
            "display_mode": "COMPACT_CHAT",
            "headline": headline,
            "one_line_answer": message,
            "eliwinship": message,
            "primary_status": status.replace("_", " ").title(),
            "primary_blocker": primary_blocker,
            "next_action": next_action,
            "missing_items_short": missing_items,
            "detail_summary": str(workbook_readback.get("workbook_summary") or ""),
            "proof_refs": (f"generated/read_models/{client_invoice_workbook_registry.JSON_EXPORT_NAME}",),
            "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
        },
        "persistent_registry_write": False,
        "generated_registry_readmodel_write": True,
        "request_classification": asdict(response_classification),
        "request_router_decision": dict(route_decision or {}),
        "external_actions_locked": True,
        "model_or_worker_response_adapter_called": False,
    }
    return OpenClawResponseForMac(
        source_request_id=str(raw_request.get("request_id") or workbook_readback["hidden_refs"]["source_request_id"]),
        source_request_filename=request_path.name,
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
        request_type=response_classification.request_family,
        internal_status="RESPONSE_READY" if terminal_ready else "BLOCKED_WITH_REASON",
        operator_headline=headline,
        operator_message=message,
        what_happened=(
            "PC recognized a Mission Control workbook registration request.",
            "PC wrote a generated workbook registry read-model from request metadata only.",
            "PC did not open the workbook, read workbook cells, parse spreadsheets, scan folders, mutate workbooks, export PDFs, send email, open Coupa, post ledger entries, or perform external action.",
        ),
        why_it_happened=(
            "The workbook chooser provided client, workflow, and selected path metadata for registration."
            if terminal_ready
            else "The workbook registration request needs safer context before binding or could not be registered."
        ),
        how_to_fix=(
            "No fix is needed. Audit the invoice sheet later when you explicitly request that governed lane."
            if terminal_ready
            else next_action
        ),
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    str(workbook_readback.get("client_summary") or ""),
                    str(workbook_readback.get("workbook_summary") or ""),
                    "Workbook body and cells were not read.",
                    next_action,
                ),
                "status_tone": "ready" if terminal_ready else "blocked",
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(registry_json.as_posix(),),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None if terminal_ready else primary_blocker,
        detail_disclosure=detail,
        readback_files=(registry_json.as_posix(), registry_operator.as_posix()),
        next_safe_move=next_action,
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
    if client_invoice_workbook_registry.is_workbook_registration_request(raw_request):
        registry_payload = client_invoice_workbook_registry.register_workbook_request(
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            source_file_metadata_ref=file_json.as_posix(),
        )
        registry_json, registry_operator = client_invoice_workbook_registry.write_exports(registry_payload, export_root)
        workbook_readback = registry_payload["registration_readback"]
        active_record = registry_payload.get("active_record") or {}
        candidate_record = registry_payload.get("candidate_record") or {}
        status = str(workbook_readback["status"])
        terminal_ready = status == "WORKBOOK_REFERENCE_CAPTURED"
        response_files = (
            file_json.as_posix(),
            file_operator.as_posix(),
            registry_json.as_posix(),
            registry_operator.as_posix(),
        )
        headline = str(workbook_readback["operator_headline"])
        message = str(workbook_readback["operator_message"])
        next_action = str(workbook_readback["next_action"])
        missing_items = tuple(str(item) for item in workbook_readback.get("missing_items") or ())
        primary_blocker = "None" if terminal_ready else (missing_items[0] if missing_items else status)
        detail = {
            "file_readback_ref": file_json.as_posix(),
            "source_ref_id": source_ref["source_ref_id"] if isinstance(source_ref, Mapping) else None,
            "client_invoice_workbook_registry": {
                "registry_readback_ref": registry_json.as_posix(),
                "operator_readback_ref": registry_operator.as_posix(),
                "registration_request": registry_payload["registration_request"],
                "registration_readback": workbook_readback,
                "active_record": active_record,
                "candidate_record": candidate_record,
                "duplicate_result": registry_payload["duplicate_result"],
                "approved_for_metadata_read": bool((active_record or candidate_record).get("approved_for_metadata_read")),
                "approved_for_cell_read": bool((active_record or candidate_record).get("approved_for_cell_read")),
                "workbook_body_read_performed": False,
                "spreadsheet_parse_performed": False,
                "spreadsheet_cell_read_performed": False,
                "folder_scan_performed": False,
                "external_action_performed": False,
            },
            "layered_response_fields": {
                "response_kind": "CLIENT_INVOICE_WORKBOOK_REGISTRATION",
                "audience_mode": "ELIWINSHIP",
                "display_mode": "COMPACT_CHAT",
                "headline": headline,
                "one_line_answer": message,
                "eliwinship": message,
                "primary_status": status.replace("_", " ").title(),
                "primary_blocker": primary_blocker,
                "next_action": next_action,
                "missing_items_short": missing_items,
                "detail_summary": str(workbook_readback.get("workbook_summary") or ""),
                "proof_refs": (f"generated/read_models/{client_invoice_workbook_registry.JSON_EXPORT_NAME}",),
                "mac_render_hint": "COMPACT_WITH_DISCLOSURE",
            },
            "persistent_registry_write": False,
            "generated_registry_readmodel_write": True,
            "request_classification": asdict(classification),
        }
        return OpenClawResponseForMac(
            source_request_id=request_id,
            source_request_filename=request_path.name,
            workflow_ref=workflow_ref,
            request_type="FILE_METADATA",
            internal_status="RESPONSE_READY" if terminal_ready else "BLOCKED_WITH_REASON",
            operator_headline=headline,
            operator_message=message,
            what_happened=(
                "PC validated the file metadata request.",
                "PC recognized a client invoice workbook registration intended use.",
                "PC wrote a generated workbook registry read-model without reading workbook cells.",
                "No spreadsheet parsing, PDF generation, email, Coupa, browser, workflow, agent, or external action occurred.",
            ),
            why_it_happened=(
                "The Mac request explicitly set intended_use to client_invoice_workbook_registration."
                if terminal_ready
                else "The workbook registration request needs safer context before binding or could not be registered."
            ),
            how_to_fix=(
                "No fix is needed. Audit the invoice sheet later when you explicitly request that governed lane."
                if terminal_ready
                else next_action
            ),
            visible_cards=(
                {
                    "title": headline,
                    "bullets": (
                        str(workbook_readback.get("client_summary") or ""),
                        str(workbook_readback.get("workbook_summary") or ""),
                        "Workbook body and cells were not read.",
                        next_action,
                    ),
                    "status_tone": "ready" if terminal_ready else "blocked",
                },
            ),
            cards_available=True,
            card_mirror_refs=(),
            file_readback_refs=(file_json.as_posix(), registry_json.as_posix()),
            worker_route_refs=(),
            context_package_refs=(),
            blocked_reason=None if terminal_ready else primary_blocker,
            detail_disclosure=detail,
            readback_files=response_files,
            next_safe_move=next_action,
        )
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


def _process_request_path_core(
    request_path: Path,
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    duplicate_check: bool = True,
    read_model_reader: ReadModelReader | None = None,
    _capsule: Any | None = None,
) -> OpenClawResponseForMac:
    classification = classify_request_filename(request_path.name)
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
    if classification.request_family == "EVIDENCE_INTAKE_REQUEST" or is_evidence_intake_request(raw_request):
        raw_request = evidence_intake.normalize_evidence_request(raw_request)
    if classification.request_family == "OPERATOR_CONTROLLER_EVENT_REQUEST" or is_operator_controller_event_request(raw_request):
        raw_request = operator_controller_event_router.normalize_controller_event_request(
            raw_request,
            read_model_root=export_root,
        )
    if classification.request_family == "UNKNOWN_FAIL_CLOSED":
        if is_evidence_intake_request(raw_request):
            classification = RequestClassification(
                classification_id=f"request_classification_{_short_hash(request_path.name, 'EVIDENCE_INTAKE_REQUEST')}",
                source_request_filename=request_path.name,
                request_family="EVIDENCE_INTAKE_REQUEST",
                selected_rail="verified_operator_evidence_intake",
                classification_reason="Request JSON declares EVIDENCE_INTAKE_REQUEST_V0.",
                future_supported=False,
                next_safe_move="Validate the operator envelope and record candidate evidence locally.",
            )
        elif is_operator_controller_event_request(raw_request):
            classification = RequestClassification(
                classification_id=f"request_classification_{_short_hash(request_path.name, 'OPERATOR_CONTROLLER_EVENT_REQUEST')}",
                source_request_filename=request_path.name,
                request_family="OPERATOR_CONTROLLER_EVENT_REQUEST",
                selected_rail="operator_controller_event_router",
                classification_reason="Request JSON declares OPERATOR_CONTROLLER_EVENT_REQUEST_V0.",
                future_supported=False,
                next_safe_move="Validate the operator envelope and route the controller event safely.",
            )
        else:
            return _failed_response(
                request_path=request_path,
                classification=classification,
                reason="Unsupported request filename.",
                how_to_fix=(
                    "Use a supported Mission Control request filename, an EVIDENCE_INTAKE_REQUEST_V0 envelope, "
                    "or an OPERATOR_CONTROLLER_EVENT_REQUEST_V0 envelope."
                ),
            )
    _route_envelope, route_decision_dataclass = openclaw_request_router.route_request(
        raw_request,
        source_request_filename=request_path.name,
        filename_request_family=classification.request_family,
    )
    route_decision = asdict(route_decision_dataclass)
    effective_classification = (
        _classification_from_router_decision(classification, request_path=request_path, decision=route_decision)
        if str(route_decision.get("request_kind") or "") in REQUEST_FAMILIES
        else classification
    )
    ok, blockers, fixes = preflight_request(raw_request, effective_classification.request_family)
    if not ok:
        return OpenClawResponseForMac(
            source_request_id=str(raw_request.get("request_id") or "unknown_request"),
            source_request_filename=request_path.name,
            workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
            request_type=effective_classification.request_family,
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
            detail_disclosure={
                "preflight_blockers": blockers,
                "fixes": fixes,
                "request_classification": asdict(effective_classification),
                "request_router_decision": route_decision,
            },
            readback_files=(),
            next_safe_move="Fix the request and rerun the bounded processor.",
        )
    if classification.request_family == "CHAT" and _is_workbook_candidate_replace_choice_request(raw_request):
        return _process_workbook_candidate_replace_choice_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=classification,
        )
    if classification.request_family == "CHAT" and is_workbook_active_selection_ambiguous_request(raw_request):
        return _process_workbook_active_selection_ambiguity_request(
            request_path,
            raw_request,
            classification=classification,
        )
    if effective_classification.request_family == "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST":
        return _process_st_annes_work_log_review_action_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
        )
    if effective_classification.request_family == "WORKROOM_REVIEW_DECISION_REQUEST":
        return _process_workroom_review_decision_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
        )
    if classification.request_family == "WORKBOOK_REGISTRATION_REQUEST":
        return _process_workbook_registration_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=classification,
            route_decision=route_decision,
        )
    if effective_classification.request_family == "EVIDENCE_INTAKE_REQUEST":
        return _process_evidence_intake_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if effective_classification.request_family == "OPERATOR_CONTROLLER_EVENT_REQUEST":
        return _process_operator_controller_event_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    maestro_frontdoor_response = _process_maestro_frontdoor_operator_instruction(
        request_path,
        raw_request,
        classification=effective_classification,
        route_decision=route_decision,
        _capsule=_capsule,
    )
    if maestro_frontdoor_response is not None:
        return maestro_frontdoor_response
    lm1_shared_seam = _build_lm1_shared_request_seam(
        raw_request,
        generated_at=generated_at,
        _capsule=_capsule,
    )
    # ── Interpreter LM routing augmentation (flag-gated, ADVISORY, DEFAULT-OFF) ──
    # When OPENCLAW_INTERPRETER_LM="1" AND the deterministic gate would send this
    # message to the workflow consumer, consult the interpreter LM.  If it returns
    # route=BRAIN with high confidence → divert to answer_frontdoor_chat (the brain).
    # When off or interpreter returns UNCERTAIN/low-confidence → deterministic path,
    # byte-identical.  The interpreter has NO authority effect and cannot authorize
    # sends, actions, or DENY→ALLOW flips.
    interpreter_divert = _try_interpreter_brain_divert(
        request_path,
        raw_request,
        classification=effective_classification,
        route_decision=route_decision,
        _capsule=_capsule,
        lm1_shared_seam=lm1_shared_seam,
    )
    if interpreter_divert is not None:
        return interpreter_divert
    # ── Interpreter LM ACTION / BLOCKED advisory (flag-gated, ADVISORY, DEFAULT-OFF) ──
    # When OPENCLAW_INTERPRETER_LM="1" AND the BRAIN divert also returned None,
    # check for ACTION or BLOCKED routes.  ACTION → consults authority_gate (gate
    # decides); BLOCKED → surfaces approval requirement.  NO execution in either case.
    # Off or uncertain/low-confidence → deterministic path, byte-identical.
    interpreter_action_blocked_divert = _try_interpreter_action_blocked_divert(
        request_path,
        raw_request,
        classification=effective_classification,
        route_decision=route_decision,
        _capsule=_capsule,
        lm1_shared_seam=lm1_shared_seam,
    )
    if interpreter_action_blocked_divert is not None:
        return interpreter_action_blocked_divert
    # ─────────────────────────────────────────────────────────────────────────────
    if effective_classification.request_family == "WORKFLOW_PACKAGE_REQUEST":
        return _process_workflow_package_request(
            request_path,
            raw_request,
            generated_at=generated_at,
            classification=effective_classification,
            lm1_shared_seam=lm1_shared_seam,
        )
    if classification.request_family == "CHAT" and _is_workbook_candidate_keep_choice_request(raw_request):
        return _process_workbook_candidate_choice_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=classification,
        )
    if _is_artifact_reference_approval_route(route_decision):
        return _process_artifact_reference_approval_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if _is_source_workbook_selection_result_route(route_decision, raw_request):
        return _process_source_workbook_selection_result_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if _is_invoice_record_selection_result_route(route_decision, raw_request):
        return _process_invoice_record_selection_result_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if _is_selected_invoice_pdf_export_completed_candidate_result_route(route_decision, raw_request):
        return _process_selected_invoice_pdf_export_completed_result_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if _is_invoice_review_action_route(route_decision, raw_request):
        return _process_invoice_review_action_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if _is_artifact_intake_route(route_decision):
        return _process_artifact_intake_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if effective_classification.request_family == "ARTIFACT_REFERENCE_APPROVAL":
        return _process_parked_router_request(
            request_path,
            raw_request,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if effective_classification.request_family == "ARTIFACT_INTAKE_REQUEST":
        return _process_parked_router_request(
            request_path,
            raw_request,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if effective_classification.request_family == "LOCAL_SURFACE_RESULT":
        if route_decision.get("route_status") != "ROUTE_MATCHED":
            return _process_parked_router_request(
                request_path,
                raw_request,
                classification=effective_classification,
                route_decision=route_decision,
            )
        return _process_local_surface_result_request(
            request_path,
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            classification=effective_classification,
            route_decision=route_decision,
        )
    if duplicate_check:
        duplicate = _existing_duplicate_response(raw_request, export_root, classification)
        if duplicate is not None:
            return duplicate
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


def _enrich_operator_surface(
    response: OpenClawResponseForMac,
    request_path: Path,
    export_root: Path,
) -> OpenClawResponseForMac:
    """THE single author-aware operator-surface pipeline. Applies the live reply engines (jargon
    teaching + scoped comedy-as-diagnostic + surface-guard + claim detection) to the FINAL
    operator_message of EVERY reply, regardless of which agent/lane produced it — so all six agent
    voices (Maestro, Cassandra, Chief, Guardian, Niles, Hermes) get the engines from one place.

    Additive + TRUTH-FIRST: jargon inserts only VERIFIED catalog wording, comedy uses grounded
    slots scoped to the answer's situation, the detector is read-only/shadow-default and queues
    only supervised heals. Comedy is HARD-LOCKED on any non-CHAT or blocked surface (money, legal,
    intake, approval, deny). Never raises — returns the response unchanged on any issue.
    """
    try:
        if not isinstance(response, OpenClawResponseForMac):
            return response
        message = response.operator_message
        if not isinstance(message, str) or not message.strip():
            return response
        # Responding agent — the same deterministic routing used for voice authorship.
        try:
            layered = _layered_response_fields(response, created_at=utc_now())
            voice_fields = _voice_authorship_fields(response, layered)
            author = str(voice_fields.get("response_author") or "OPENCLAW_SYSTEM")
            humor_health_gate = _humor_health_gate(response, layered, author)
        except Exception:
            author = "OPENCLAW_SYSTEM"
            humor_health_gate = {"health_allows_humor": False}
        agent_id = author.strip().lower() or "openclaw_system"
        # The operator's question — for comedy relevance scoping + claim-detection context.
        question = ""
        try:
            question = _operator_text(_load_json_request(request_path))
        except Exception:
            question = ""
        # Decoration (jargon + comedy) is allowed ONLY on a normal, non-blocked CHAT answer that is
        # NOT a safety/denial surface. Everything else (blocked, deny, intake, approval, file,
        # evidence, money, legal, AND any refusal/SEND_HOLD text) is high_risk -> NO text mutation
        # (only the read-only guard + detector run). This keeps crisp safety denials verbatim — a
        # jargon insert must never split a phrase like "SEND_HOLD remains in force".
        _ml = message.lower()
        safety_surface = any(
            marker in _ml for marker in (
                "send_hold", "cannot route", "cannot send", "will not send", "won't send",
                "no external send", "not authorized to send", "ledger remains untouched",
                "denied", "blocked outputs", "no money", "no payment",
            )
        )
        decorate_ok = (
            str(response.request_type or "").upper() == "CHAT"
            and not str(getattr(response, "blocked_reason", "") or "").strip()
            and not safety_surface
            and humor_health_gate.get("health_allows_humor") is True
        )
        from reply_pipeline import apply_reply_pipeline

        enriched = apply_reply_pipeline(
            message,
            question,
            agent_id,
            packet_id=str(response.source_request_id or ""),
            read_model_root=str(export_root),
            high_risk=not decorate_ok,
        )
        if isinstance(enriched, str) and enriched.strip() and enriched != message:
            response = replace(response, operator_message=enriched)
        # ── RESPONSE VALIDATION Stage 1 — operator_surface_guard (task 144) ───
        # Task 144 (CLASS #5): this used to be gated behind _continuity_enabled(), an
        # unrelated conversation-memory flag that defaults OFF -- meaning the one real
        # substitute-on-leak block in the whole fleet was dormant by default. Now its own
        # flag, default ON. When explicitly disabled: byte-identical to pre-task-144
        # behavior (print-only, response returned unchanged).
        if _operator_surface_guard_enabled():
            try:
                from operator_surface_guard import guard_operator_reply
                _surface_text = response.operator_message
                if isinstance(_surface_text, str) and _surface_text.strip():
                    _guarded_text = guard_operator_reply(_surface_text, agent_role=agent_id)
                    if _guarded_text != _surface_text:
                        return replace(response, operator_message=_guarded_text)
            except Exception:
                pass  # fail-safe: never block a response due to guard error
        return response
    except Exception:
        return response


def process_request_path(
    request_path: Path,
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    duplicate_check: bool = True,
    read_model_reader: ReadModelReader | None = None,
) -> OpenClawResponseForMac:
    """Universal request entrypoint. Runs the real processor, then applies the single author-aware
    operator-surface pipeline so every agent voice gets the live reply engines (see
    _enrich_operator_surface). The enrichment is additive + non-blocking; a failure returns the
    un-enriched response unchanged."""
    # ── CONTINUITY CAPSULE load@turn-start (flag-gated, ADDITIVE) ────────────
    # When ON: load the capsule (or cold-start) from the conversation_id in the
    # request; pass it into the core processor so it flows to
    # build_maestro_context_packet (Edit 2 capsule-aware packet).
    # When OFF: _capsule stays None, _process_request_path_core call is
    # byte-identical to pre-edit behavior.
    _capsule = None
    _continuity_store_state: dict[str, Any] = {}
    if _continuity_enabled():
        try:
            import conversation_capsule as _cc
            _DEFAULT_CAPSULE_STORE_DIR = "/home/openclaw/state/conversation_capsules"
            _raw_req = _load_json_request(request_path)
            _conv_id = str(_raw_req.get("conversation_id") or "")
            _channel_id = str(_raw_req.get("source_channel") or "maestro_listener")
            _operator_id = str(_raw_req.get("actor") or _raw_req.get("speaker") or "operator")
            _generated_at_str = generated_at or utc_now()
            if _conv_id:
                _store = _cc.ConversationCapsuleStore(_DEFAULT_CAPSULE_STORE_DIR)
                _loaded = _store.load(_operator_id, "maestro", _conv_id, _channel_id)
                if _loaded is None:
                    _loaded = _cc.Capsule.cold_start(
                        agent_id="maestro",
                        operator_id=_operator_id,
                        conversation_id=_conv_id,
                        channel_id=_channel_id,
                    )
                _capsule = _loaded
                _continuity_store_state = {
                    "store": _store,
                    "operator_id": _operator_id,
                    "conv_id": _conv_id,
                    "channel_id": _channel_id,
                    "generated_at": _generated_at_str,
                }
        except Exception:
            _capsule = None  # never block the live path
    response = _process_request_path_core(
        request_path,
        export_root=export_root,
        generated_at=generated_at,
        duplicate_check=duplicate_check,
        read_model_reader=read_model_reader,
        _capsule=_capsule,
    )
    response = _enrich_operator_surface(response, request_path, export_root)
    # ── CONTINUITY CAPSULE write-back@turn-end + receipt (flag-gated) ────────
    # When ON: append the turn to recent_messages, set last_interaction_at, and
    # write the capsule back; add conversation_id to detail_disclosure as the
    # proof-of-correlation receipt field.
    # When OFF: no write, response returned unchanged.
    if _continuity_enabled() and _capsule is not None and _continuity_store_state:
        try:
            import conversation_capsule as _cc2
            _ts = _continuity_store_state.get("generated_at") or utc_now()
            _turn_summary = str(response.operator_message or "")[:200]
            _turn_ref = "sha256:" + __import__("hashlib").sha256(_turn_summary.encode()).hexdigest()[:16]
            _new_messages = list(_capsule.recent_messages)
            _new_messages.append({"role": "agent", "ref": _turn_ref, "summary": _turn_summary, "ts": _ts})
            from dataclasses import replace as _dc_replace
            _updated_capsule = _dc_replace(
                _capsule,
                recent_messages=_new_messages,
                last_interaction_at=_ts,
            )
            _st = _continuity_store_state
            _st["store"].write(
                _st["operator_id"], "maestro", _st["conv_id"], _st["channel_id"],
                _updated_capsule,
            )
            # Stamp conversation_id into detail_disclosure as receipt correlation
            _conv_id_for_receipt = _st["conv_id"]
            _detail = dict(response.detail_disclosure) if isinstance(response.detail_disclosure, dict) else {}
            _detail["conversation_id"] = _conv_id_for_receipt
            response = replace(response, detail_disclosure=_detail)
        except Exception:
            pass  # never block response delivery

    # ── Continuity-identity stamp for brain/CHAT responses (ADDITIVE, flag-INDEPENDENT) ──
    # Always attach conversation_id/turn_id/operator_id/agent_id/thread_id to a CHAT
    # response (and mirror conversation_id+turn_id into the brain card's machine_proof)
    # so brain answers are never continuity-starved — even when the continuity flag is
    # off or no conversation_id was minted (safe fallback id). setdefault preserves any
    # conversation_id the write-back above already stamped. Non-CHAT responses unchanged.
    try:
        _raw_req_for_ids = _load_json_request(request_path)
        response = _stamp_continuity_identity(response, _raw_req_for_ids)
    except Exception:
        pass  # never block response delivery
    return response


def process(
    operator_text: str,
    *,
    read_model_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OpenClawResponseForMac:
    """Process one NL prompt through the real request-file processor path."""

    created_at = generated_at or utc_now()
    request_id = f"pc4_nl_stress_{_short_hash(operator_text, created_at)}"
    authority_boundary = {
        "email_send_allowed": False,
        "gmail_read_allowed": False,
        "browser_allowed": False,
        "coupa_allowed": False,
        "submit_allowed": False,
        "ledger_mutation_allowed": False,
        "payment_allowed": False,
        "merge_allowed": False,
        "push_allowed": False,
        "worker_execution_allowed": False,
    }
    payload = {
        "schema_version": "operator_instruction_package_request_v0",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "request_id": request_id,
        "active_surface_ref": "operator_maestro_chat",
        "created_at": created_at,
        "idempotency_key": f"pc4_nl_stress:{request_id}",
        "mac_wrote_request_only": True,
        "operator_text": operator_text,
        "operator_message": operator_text,
        "origin_surface": "pc4_nl_stress_replay",
        "current_world_ref": "pc4_self_heal",
        "current_thread_ref": "nl_stress_replay",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "source_channel": "pc4_nl_stress_replay",
        "source_request_id": request_id,
        "source_surface": "pc4_self_heal",
        "source_text": operator_text,
        "thread_title": "NL Stress Replay",
        "world": "pc4_self_heal",
        "world_ref": "pc4_self_heal",
        "authority_boundary": authority_boundary,
    }
    payload["payload_hash"] = _content_hash(payload)
    with tempfile.TemporaryDirectory(prefix="pc4-openclaw-process-") as tmp:
        request_path = Path(tmp) / f"mission_control_operator_instruction_request_general_operator_instruction_{request_id}.json"
        request_path.write_text(stable_json(payload), encoding="utf-8")
        return process_request_path(
            request_path,
            export_root=read_model_root,
            generated_at=generated_at,
            duplicate_check=False,
        )


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


def _int_counter(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _lm1_shared_seam_detail_from_response(response: OpenClawResponseForMac) -> dict[str, Any] | None:
    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    seam_detail = detail.get("lm1_shared_request_seam")
    if isinstance(seam_detail, Mapping):
        return dict(seam_detail)
    proof = response.proof_to_response if isinstance(response.proof_to_response, Mapping) else {}
    if "lm1_shared_seam_used" not in proof:
        return None
    packet_id = str(proof.get("lm1_shared_packet_id") or "")
    return {
        "status": "READY" if proof.get("lm1_shared_seam_used") and packet_id else "NOT_READY",
        "interpretation": {},
        "workflow_packet_id": "",
        "rich_packet_id": packet_id,
        "packet_error": "",
    }


def _lm1_shared_seam_receipt(
    response: OpenClawResponseForMac,
    *,
    generated_at: str,
) -> dict[str, Any] | None:
    seam_detail = _lm1_shared_seam_detail_from_response(response)
    if seam_detail is None:
        return None
    interpretation = seam_detail.get("interpretation")
    interpretation = interpretation if isinstance(interpretation, Mapping) else {}
    status = str(seam_detail.get("status") or "")
    workflow_packet_id = str(seam_detail.get("workflow_packet_id") or "")
    rich_packet_id = str(seam_detail.get("rich_packet_id") or "")
    used = status == "READY" and bool(workflow_packet_id or rich_packet_id)
    return {
        "schema_version": "lm1_shared_seam_receipt_v0",
        "receipt_type": "lm1_shared_seam_used" if used else "lm1_shared_seam_not_ready",
        "generated_at": generated_at,
        "source_request_id": response.source_request_id,
        "request_type": response.request_type,
        "feature_flag": "OPENCLAW_LM1_SHARED_SEAM",
        "status": status,
        "used": used,
        "workflow_packet_id": workflow_packet_id,
        "rich_packet_id": rich_packet_id,
        "interpretation_source": str(interpretation.get("source") or ""),
        "interpretation_route": str(interpretation.get("route") or ""),
        "interpretation_confidence": interpretation.get("confidence"),
        "packet_error": str(seam_detail.get("packet_error") or ""),
    }


def _lm1_shared_seam_counter(
    receipt: Mapping[str, Any] | None,
    previous_status: Mapping[str, Any] | None,
    *,
    generated_at: str,
) -> dict[str, Any] | None:
    previous_counter = None
    if isinstance(previous_status, Mapping):
        raw_counter = previous_status.get("lm1_shared_seam_counter")
        previous_counter = raw_counter if isinstance(raw_counter, Mapping) else None
    if receipt is None and previous_counter is None:
        return None
    observation_count = _int_counter((previous_counter or {}).get("observation_count"))
    used_count = _int_counter((previous_counter or {}).get("used_count"))
    not_ready_count = _int_counter((previous_counter or {}).get("not_ready_count"))
    if receipt is not None:
        observation_count += 1
        if bool(receipt.get("used")):
            used_count += 1
        else:
            not_ready_count += 1
    return {
        "schema_version": "lm1_shared_seam_counter_v0",
        "read_model_id": "lm1_shared_seam_counter",
        "generated_at": generated_at,
        "feature_flag": "OPENCLAW_LM1_SHARED_SEAM",
        "observation_count": observation_count,
        "used_count": used_count,
        "not_ready_count": not_ready_count,
        "zero_live_fire_receipts": used_count == 0,
        "latest_receipt": dict(receipt) if isinstance(receipt, Mapping) else (previous_counter or {}).get("latest_receipt"),
    }


def _machine_proof(
    response: OpenClawResponseForMac,
    status: OpenClawRequestProcessorStatus,
) -> dict[str, Any]:
    quality_errors = _terminal_quality_errors(response)
    brain_receipt = _brain_receipt_for_response(response)
    brain_model_call_performed = _brain_receipt_model_performed(brain_receipt)
    brain_local_model_invoked = brain_model_call_performed and _brain_receipt_local_invoked(brain_receipt)
    brain_external_model_invoked = brain_model_call_performed and _brain_receipt_external_invoked(brain_receipt)
    brain_route = _brain_receipt_route(brain_receipt)
    brain_model_id = _brain_receipt_model_id(brain_receipt)
    detail = response.detail_disclosure if isinstance(response.detail_disclosure, Mapping) else {}
    interpreter_detail = detail.get("deterministic_intent_interpreter") if isinstance(detail.get("deterministic_intent_interpreter"), Mapping) else {}
    workbook_detail = detail.get("client_invoice_workbook_registry") if isinstance(detail.get("client_invoice_workbook_registry"), Mapping) else {}
    audit_handoff_detail = detail.get("client_invoice_audit_handoff") if isinstance(detail.get("client_invoice_audit_handoff"), Mapping) else {}
    sheet_audit_detail = detail.get("client_invoice_sheet_audit") if isinstance(detail.get("client_invoice_sheet_audit"), Mapping) else {}
    local_artifact_detail = detail.get("local_artifact_reference") if isinstance(detail.get("local_artifact_reference"), Mapping) else {}
    invoice_action_detail = detail.get("invoice_review_action_request") if isinstance(detail.get("invoice_review_action_request"), Mapping) else {}
    router_decision = detail.get("request_router_decision") if isinstance(detail.get("request_router_decision"), Mapping) else {}
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
        "request_router_used": bool(router_decision),
        "request_router_matched": router_decision.get("route_status") == "ROUTE_MATCHED",
        "request_router_selected_handler_id": str(router_decision.get("selected_handler_id") or ""),
        "supported_chat_pattern_present": CHAT_PATTERN in SUPPORTED_REQUEST_PATTERNS,
        "supported_file_pattern_present": FILE_METADATA_PATTERN in SUPPORTED_REQUEST_PATTERNS,
        "supported_workbook_registration_pattern_present": all(
            pattern in SUPPORTED_REQUEST_PATTERNS for pattern in WORKBOOK_REGISTRATION_REQUEST_PATTERNS
        ),
        "supported_local_surface_result_pattern_present": all(pattern in SUPPORTED_REQUEST_PATTERNS for pattern in LOCAL_SURFACE_RESULT_PATTERNS),
        "supported_artifact_reference_approval_pattern_present": all(pattern in SUPPORTED_REQUEST_PATTERNS for pattern in ARTIFACT_REFERENCE_APPROVAL_PATTERNS),
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
        "deterministic_intent_interpreter_used": bool(interpreter_detail),
        "session_resolver_used": bool(interpreter_detail.get("session_resolver_used")),
        "capability_query_used": bool(interpreter_detail.get("capability_query_used")),
        "validator_used": bool(interpreter_detail.get("validator_used")),
        "client_invoice_workbook_registry_used": bool(workbook_detail),
        "approved_readable_artifact_reference_used": bool(local_artifact_detail),
        "approved_readable_artifact_ready": bool(local_artifact_detail.get("artifact_ready")),
        "invoice_review_action_request_used": bool(invoice_action_detail),
        "invoice_review_action_completion_receipt_written": bool(invoice_action_detail.get("completion_receipt_written")),
        "invoice_review_action_underlying_blocker_completed": bool(invoice_action_detail.get("underlying_blocker_completed")),
        "client_invoice_audit_handoff_used": bool(audit_handoff_detail),
        "client_invoice_audit_handoff_live_ready": bool(audit_handoff_detail.get("live_audit_ready")),
        "local_surface_result_consumed": bool((audit_handoff_detail.get("local_surface_result_receipt") or {}).get("receipt_id")),
        "operator_provided_schema_guidance": bool(audit_handoff_detail.get("operator_provided_schema_guidance")),
        "verified_sheet_data": False,
        "client_invoice_sheet_audit_used": bool(sheet_audit_detail),
        "live_lm_interpreter_called": False,
        "workflow_execution_performed": False,
        "file_mutation_performed": False,
        "model_call_performed": brain_model_call_performed,
        "local_model_invoked": brain_local_model_invoked,
        "external_llm_invoked": brain_external_model_invoked,
        "protected_generate_route": brain_route,
        "protected_generate_model_selected": brain_model_id,
        "deterministic_fallback_used": bool(brain_receipt.get("deterministic_fallback_used") is True) if brain_receipt else False,
        "tool_execution_performed": False,
        "agent_dispatch_performed": False,
        "worker_dispatch_performed": False,
        "workbook_body_read_performed": False,
        "spreadsheet_parse_performed": False,
        "spreadsheet_cell_read_performed": False,
        "audit_handoff_schema_inference_performed": False,
        "audit_handoff_mac_path_translation_guessed": False,
        "audit_handoff_formula_evaluation_performed": False,
        "whitelisted_sheet_cells_read_performed": bool(sheet_audit_detail.get("whitelisted_cells_read")),
        "sheet_audit_schema_explicit": bool(sheet_audit_detail.get("schema_explicit")),
        "sheet_audit_pc_path_readable": bool(sheet_audit_detail.get("path_pc_readable")),
        "sheet_audit_inferred_schema_performed": False,
        "sheet_audit_full_sheet_dump_performed": False,
        "sheet_audit_formula_evaluation_performed": False,
        "pdf_generation_performed": False,
        "email_draft_or_send_performed": False,
        "email_send_performed": False,
        "gmail_send_performed": False,
        "coupa_access_or_submit_performed": False,
        "browser_access_performed": False,
        "invoice_generation_performed": False,
        "attachment_performed": False,
        "approval_request_performed": False,
        "send_submit_performed": False,
        "approval_execution_performed": False,
        "candidate_promotion_performed": False,
        "registry_mutation_performed": False,
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
    previous_status: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = generated_at or utc_now()
    status = _processor_status_from_response(response, blockers=blockers)
    layered_fields = _enforce_layered_response_taste(_layered_response_fields(response, created_at=generated_at))
    voice_fields = _voice_authorship_fields(response, layered_fields)
    spoken_packet = _enforce_spoken_packet_taste(_spoken_response_packet(response, layered_fields, voice_fields))
    visual_package = _visual_event_package(response, layered_fields, voice_fields)
    humor_health_gate = _humor_health_gate(
        response,
        layered_fields,
        str(voice_fields.get("response_author") or "OPENCLAW_SYSTEM"),
    )
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
        "visual_event_package": visual_package,
        "humor_health_gate": humor_health_gate,
        "terminal": _terminal_for_status(response.internal_status),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    local_surface_request = local_surface_request_contract.infer_surface_request(response_payload)
    response_payload["local_surface_request"] = local_surface_request
    guardian_gate_payload = guardian_output_gate.validate_response_payload(response_payload)
    guardian_gate_result = guardian_gate_payload["validation_result"]
    response_payload["guardian_output_gate"] = {
        "schema_version": guardian_gate_payload["schema_version"],
        "contract_status": guardian_gate_payload["contract_status"],
        "role_execution_package": guardian_gate_payload["role_execution_package"],
        "validation_result": guardian_gate_result,
    }
    response_payload["guardian_verdict"] = guardian_gate_result["verdict"]
    taste_guardrails = _response_taste_guardrails(response_payload)
    response_payload["taste_guardrails"] = taste_guardrails
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
            "agent_model_backend_separation_present": True,
            "codex_agent_profile_created": False,
            "model_selection_grants_authority": False,
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
            "visual_event_package_present": visual_package is not None,
            "visual_package_truth_bound": True,
            "visual_false_success_claim_blocked": (
                visual_package is None or visual_package.get("visual_event_type") not in VISUAL_SUCCESS_EVENT_TYPES
            )
            or _completion_receipts_present(response),
            "video_generation_performed": False,
            "image_generation_performed": False,
            "cloud_model_call_performed": bool(status_payload["machine_proof"].get("external_llm_invoked")),
            "local_model_call_performed": bool(status_payload["machine_proof"].get("local_model_invoked")),
            "visual_playback_performed": False,
            "visual_provider_call_performed": False,
            "response_taste_guardrails_present": True,
            "response_taste_passed": taste_guardrails["taste_passed"],
            "response_field_limits_passed": taste_guardrails["field_limits_passed"],
            "compact_fields_machine_sludge_free": taste_guardrails["machine_sludge_filtered"],
            "bad_phrase_blockers_passed": taste_guardrails["bad_phrase_blockers_passed"],
            "agent_voice_taste_rules_passed": taste_guardrails["agent_voice_rules_passed"],
            "duplicate_sentence_reduction_passed": taste_guardrails["duplicate_sentence_reduction_passed"],
            "humor_health_gate_present": True,
            "humor_health_allows_humor": humor_health_gate["health_allows_humor"],
            "humor_plain_register_required": humor_health_gate["plain_register_required"],
            "humor_health_model_ok": humor_health_gate["model_ok"],
            "humor_health_grounding_intact": humor_health_gate["grounding_intact"],
            "humor_health_subsystem_functioning": humor_health_gate["subsystem_functioning"],
            "humor_health_auto_heal_landed": humor_health_gate["auto_heal_landed"],
            "humor_agent_humor_rank": humor_health_gate["agent_humor_rank"],
            "humor_per_agent_calibration_reused": humor_health_gate["machine_proof"]["per_agent_calibration_reused"],
            "guardian_output_gate_present": True,
            "guardian_output_gate_used": guardian_gate_payload["machine_proof"]["guardian_output_gate_used"],
            "role_output_validator_used": guardian_gate_payload["machine_proof"]["role_output_validator_used"],
            "guardian_output_gate_verdict": guardian_gate_result["verdict"],
            "guardian_output_gate_passed": guardian_gate_result["output_publish_allowed"],
            "role_output_blocked": not guardian_gate_result["output_publish_allowed"],
            "guardian_output_external_action_allowed": guardian_gate_result["external_action_allowed"],
            "local_surface_request_present": True,
            "local_surface_request_type": local_surface_request.get("surface_type"),
            "local_surface_request_raw_body_allowed": local_surface_request.get("raw_body_allowed"),
            "local_surface_request_external_model_share_allowed": local_surface_request.get("external_model_share_allowed"),
            "local_surface_request_local_only": local_surface_request.get("local_only"),
            "local_surface_request_path_translation_guess_allowed": local_surface_request.get("path_translation_guess_allowed"),
            "local_surface_request_external_action_allowed": local_surface_request.get("external_action_allowed"),
        }
    )
    lm1_seam_receipt = _lm1_shared_seam_receipt(response, generated_at=generated_at)
    lm1_seam_counter = _lm1_shared_seam_counter(
        lm1_seam_receipt,
        previous_status,
        generated_at=generated_at,
    )
    if lm1_seam_receipt is not None:
        response_payload.setdefault("request_receipts", {})["lm1_shared_seam"] = lm1_seam_receipt
    if lm1_seam_counter is not None:
        status_payload["lm1_shared_seam_counter"] = lm1_seam_counter
        status_payload["machine_proof"].update(
            {
                "lm1_shared_seam_receipt_emitted": lm1_seam_receipt is not None,
                "lm1_shared_seam_used": bool(lm1_seam_receipt and lm1_seam_receipt.get("used")),
                "lm1_shared_seam_observation_count": lm1_seam_counter["observation_count"],
                "lm1_shared_seam_used_count": lm1_seam_counter["used_count"],
                "lm1_shared_seam_zero_live_fire_receipts": lm1_seam_counter["zero_live_fire_receipts"],
            }
        )
    else:
        status_payload["machine_proof"]["lm1_shared_seam_receipt_emitted"] = False
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
    publication = status_payload["processor_status"].get("mac_response_publication", {})
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
        "selected_model_backend": response_payload["selected_model_backend"],
        "selected_worker_type": response_payload["selected_worker_type"],
        "voice_profile_ref": response_payload["voice_profile_ref"],
        "vibe_profile_ref": response_payload["vibe_profile_ref"],
        "model_selection_reason": response_payload["model_selection_reason"],
        "voice_selection_reason": response_payload["voice_selection_reason"],
        "high_risk_override_applied": response_payload["high_risk_override_applied"],
        "terminal_quality_passed": status_payload["machine_proof"]["terminal_quality_passed"],
        "all_live_authority_flags_false": status_payload["machine_proof"]["all_live_authority_flags_false"],
        "future_lm_targets_not_called": status_payload["machine_proof"]["future_lm_targets_not_called"],
        "external_action_performed": status_payload["machine_proof"]["external_action_performed"],
        "mac_response_published": publication.get("published", False),
        "mac_scoped_response_file": publication.get("response_file"),
        "mac_latest_response_file": publication.get("latest_response_file"),
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
    response_dir: Path | None = None,
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
    previous_status = _read_existing_processor_status(export_root)
    response_payload, status_payload = build_payloads(
        response,
        generated_at=generated_at,
        blockers=quality_errors,
        previous_status=previous_status,
    )
    publication = publish_response_for_mac_outbox(
        response_payload,
        response_dir=response_dir,
        published_at=generated_at,
    )
    status_payload["processor_status"]["mac_response_publication"] = publication
    status_payload["machine_proof"]["mac_response_scoped_publication_performed"] = bool(publication.get("published"))
    status_payload["machine_proof"]["mac_latest_response_updated"] = bool(publication.get("published"))
    status_payload["machine_proof"]["content_hash"] = _content_hash(status_payload)
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
    parser.add_argument("--no-response-publish", action="store_true", help="Do not write scoped Mac response files.")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    request_file = Path(args.request_file) if args.request_file else None
    inbox = Path(args.inbox)
    response_dir = None
    if not args.no_response_publish:
        response_dir = default_response_publication_dir(inbox=inbox, request_file=request_file)
    response_payload, status_payload, paths, quality_errors = run_and_write(
        inbox=inbox,
        request_file=request_file,
        request_id=args.request_id,
        export_root=export_root,
        generated_at=args.generated_at,
        watch_seconds=args.watch_seconds,
        response_dir=response_dir,
    )
    output = response_payload if args.format == "json" else build_summary(response_payload, status_payload, paths)
    print(stable_json(output), end="")
    return 1 if quality_errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
