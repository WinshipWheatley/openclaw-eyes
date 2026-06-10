"""PC to Mac local action bridge V0.

This module creates durable PC -> Mac local action request/result contracts for
Mac-only brokers such as Apple Mail. It never calls Apple Mail, opens Mail.app,
reads Gmail, creates drafts, sends mail, mutates mailboxes, opens browsers, or
handles secrets. It only writes scoped request artifacts and SQLite provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/mac_local_action_bridge.sqlite")
DEFAULT_REQUEST_QUEUE = Path("/mnt/e/openclaw/mac_local_action_requests/to_mac")
DEFAULT_RESULT_QUEUE = Path("/mnt/e/openclaw/mac_local_action_results/from_mac")
MAC_VISIBLE_REQUEST_QUEUE = "/Volumes/openclaw_e/mac_local_action_requests/to_mac"
MAC_VISIBLE_RESULT_QUEUE = "/Volumes/openclaw_e/mac_local_action_results/from_mac"

MAC_LOCAL_ACTION_REQUEST_SCHEMA = "MAC_LOCAL_ACTION_REQUEST_V0"
MAC_LOCAL_ACTION_RESULT_SCHEMA = "MAC_LOCAL_ACTION_RESULT_V0"
MAC_LOCAL_ACTION_PACKAGE_PLAN_SCHEMA = "MAC_LOCAL_ACTION_PACKAGE_PLAN_V0"

APPLE_MAIL_LOCAL_BROKER = "openclaw.apple_mail_local_broker"
APPLE_MAIL_SELECTED_MESSAGE_METADATA_READ = "openclaw.apple_mail_selected_message_metadata_read"
APPLE_MAIL_SCOPED_METADATA_SEARCH = "openclaw.apple_mail_scoped_metadata_search"
APPLE_MAIL_SELECTED_MESSAGE_BODY_READ = "openclaw.apple_mail_selected_message_body_read"
APPLE_MAIL_TEXT_DRAFT_PREVIEW = "openclaw.apple_mail_text_draft_preview"
APPLE_MAIL_DRAFT_CREATE = "openclaw.apple_mail_draft_create"
APPLE_MAIL_SEND = "openclaw.apple_mail_send"

APPLE_MAIL_CAPABILITIES = (
    APPLE_MAIL_LOCAL_BROKER,
    APPLE_MAIL_SELECTED_MESSAGE_METADATA_READ,
    APPLE_MAIL_SCOPED_METADATA_SEARCH,
    APPLE_MAIL_SELECTED_MESSAGE_BODY_READ,
    APPLE_MAIL_TEXT_DRAFT_PREVIEW,
    APPLE_MAIL_DRAFT_CREATE,
    APPLE_MAIL_SEND,
)

REQUEST_REQUIRED_FIELDS = (
    "schema_version",
    "request_id",
    "objective_id",
    "source_channel",
    "requested_by_actor",
    "target_mac_id",
    "local_broker",
    "requested_capability",
    "lane_context",
    "input_scope",
    "allowed_actions",
    "denied_actions",
    "authority_envelope_ref",
    "local_permission_ref",
    "expires_at",
    "receipt_requirements",
    "reply_to_result_path",
    "status",
)

RESULT_REQUIRED_FIELDS = (
    "schema_version",
    "request_id",
    "objective_id",
    "local_broker",
    "status",
    "result_summary",
    "redacted_outputs",
    "receipt_ref",
    "denied_actions_confirmed",
    "mutation_performed",
    "raw_body_exposed",
    "error_code",
    "next_safe_step",
    "created_at",
)

DENIED_ACTIONS = (
    "apple_mail_direct_pc_execution",
    "apple_mail_automation_without_mac_local_permission",
    "apple_mail_body_read_without_body_authority",
    "apple_mail_draft_create_without_draft_authority",
    "apple_mail_send_without_exact_payload_authority",
    "mailbox_delete",
    "mailbox_archive",
    "mailbox_mark_read",
    "mailbox_label_or_folder_mutation",
    "background_mailbox_scan_without_unattended_envelope",
    "raw_body_exposure",
    "gmail_access",
    "gmail_compose",
    "gmail_draft_create",
    "gmail_send",
    "calendar_api_call",
    "contacts_api_call",
    "open_browser",
    "open_gmail_ui",
    "open_coupa",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "print_secret",
    "print_token",
    "trust_raw_authority_granted",
)

AUTHORITY_BOUNDARY = {
    "pc_apple_mail_execution_allowed": False,
    "apple_mail_called": False,
    "apple_mail_automation_invoked": False,
    "mailbox_mutation_allowed": False,
    "mail_body_read_allowed": False,
    "mail_draft_create_allowed": False,
    "mail_send_allowed": False,
    "background_mailbox_scan_allowed": False,
    "gmail_access_allowed": False,
    "calendar_api_allowed": False,
    "contacts_api_allowed": False,
    "browser_open_allowed": False,
    "coupa_access_allowed": False,
    "paid_marking_allowed": False,
    "ledger_mutation_allowed": False,
    "secret_print_allowed": False,
    "raw_authority_granted_trusted": False,
}

POLICY_GATES = (
    {
        "gate_id": "policy.apple_mail_local_broker_requires_mac_local_action_bridge",
        "gate_label": "Apple Mail local broker requires Mac-local action bridge",
        "blocked_actions": ["pc_direct_apple_mail_execution", "ambient_mailbox_scan"],
        "unlock_requirements": ["MAC_LOCAL_ACTION_REQUEST_V0", "Mac local runner receipt", "operator authority envelope"],
    },
    {
        "gate_id": "policy.apple_mail_automation_permission_does_not_imply_mailbox_authority",
        "gate_label": "Apple Mail Automation permission does not imply mailbox authority",
        "blocked_actions": ["mailbox_read_without_scope", "mailbox_mutation_without_authority"],
        "unlock_requirements": ["scoped action request", "local permission receipt", "denied action confirmation"],
    },
    {
        "gate_id": "policy.apple_mail_selected_metadata_does_not_imply_body_read",
        "gate_label": "Selected-message metadata does not imply body read",
        "blocked_actions": ["message_body_read"],
        "unlock_requirements": ["separate body-read authority"],
    },
    {
        "gate_id": "policy.apple_mail_body_read_does_not_imply_send",
        "gate_label": "Body read does not imply send",
        "blocked_actions": ["mail_send"],
        "unlock_requirements": ["exact payload send approval"],
    },
    {
        "gate_id": "policy.apple_mail_draft_preview_does_not_imply_mail_draft_create",
        "gate_label": "Draft preview does not imply Mail.app draft creation",
        "blocked_actions": ["mail_app_draft_create"],
        "unlock_requirements": ["separate Mail.app draft-create authority"],
    },
    {
        "gate_id": "policy.apple_mail_draft_create_does_not_imply_send",
        "gate_label": "Mail.app draft creation does not imply send",
        "blocked_actions": ["mail_send"],
        "unlock_requirements": ["exact payload send approval"],
    },
    {
        "gate_id": "policy.apple_mail_send_requires_exact_payload_approval",
        "gate_label": "Send requires exact payload approval",
        "blocked_actions": ["mail_send_without_exact_payload_hash"],
        "unlock_requirements": ["exact payload approval", "send receipt"],
    },
    {
        "gate_id": "policy.apple_mail_background_scan_requires_unattended_envelope",
        "gate_label": "Background mailbox scanning requires unattended envelope",
        "blocked_actions": ["background_mailbox_scan"],
        "unlock_requirements": ["unattended run envelope", "expiry", "interrupt conditions"],
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        value = json.dumps(part, sort_keys=True, ensure_ascii=True) if isinstance(part, (dict, list, tuple)) else str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _safe_ref(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_")[:120] or "request"


def _expires_at(generated_at: str, hours: int = 2) -> str:
    base = datetime.fromisoformat(generated_at)
    return (base + timedelta(hours=hours)).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS mac_local_action_requests (
          request_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          source_channel TEXT NOT NULL,
          local_broker TEXT NOT NULL,
          requested_capability TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          request_path TEXT NOT NULL,
          reply_to_result_path TEXT NOT NULL,
          request_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mac_local_action_results (
          request_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          local_broker TEXT NOT NULL,
          status TEXT NOT NULL,
          receipt_ref TEXT NOT NULL,
          created_at TEXT NOT NULL,
          result_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mac_local_action_events (
          event_id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          objective_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          event_json TEXT NOT NULL
        );
        """
    )


def connect(sqlite_path: Path | str = DEFAULT_SQLITE_PATH) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def detects_apple_mail_local_request(text: str) -> bool:
    lowered = str(text or "").lower()
    mentions_mail = "apple mail" in lowered or "mail.app" in lowered or "local mail" in lowered
    wants_lookup = any(term in lowered for term in ("check", "search", "look", "find", "received", "recieved", "reply", "response", "email"))
    return mentions_mail and wants_lookup


def capability_for_text(text: str) -> str:
    lowered = str(text or "").lower()
    if "send" in lowered:
        return APPLE_MAIL_SEND
    if "create" in lowered and "draft" in lowered:
        return APPLE_MAIL_DRAFT_CREATE
    if "draft" in lowered:
        return APPLE_MAIL_TEXT_DRAFT_PREVIEW
    if "body" in lowered or "content" in lowered:
        return APPLE_MAIL_SELECTED_MESSAGE_BODY_READ
    if "selected" in lowered and "message" in lowered:
        return APPLE_MAIL_SELECTED_MESSAGE_METADATA_READ
    return APPLE_MAIL_SCOPED_METADATA_SEARCH


def allowed_actions_for_capability(capability: str) -> list[str]:
    if capability in {APPLE_MAIL_SCOPED_METADATA_SEARCH, APPLE_MAIL_SELECTED_MESSAGE_METADATA_READ}:
        return ["queue_mac_local_action", "apple_mail_metadata_only", "write_redacted_result_receipt"]
    if capability == APPLE_MAIL_TEXT_DRAFT_PREVIEW:
        return ["queue_mac_local_action", "text_only_draft_preview", "write_draft_preview_receipt"]
    if capability == APPLE_MAIL_SELECTED_MESSAGE_BODY_READ:
        return ["queue_mac_local_action", "body_read_requires_separate_authority", "write_redacted_result_receipt"]
    if capability == APPLE_MAIL_DRAFT_CREATE:
        return ["queue_mac_local_action", "draft_create_requires_separate_authority", "write_draft_create_receipt"]
    if capability == APPLE_MAIL_SEND:
        return ["queue_mac_local_action", "send_requires_exact_payload_authority", "write_send_or_blocker_receipt"]
    return ["queue_mac_local_action", "write_redacted_result_receipt"]


def build_input_scope(text: str, lane_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    lowered = str(text or "").lower()
    scope = dict(lane_context or {})
    if "annette" in lowered:
        scope.setdefault("counterparty", "Annette")
    if "capital hilton" in lowered or "capital_hilton" in lowered:
        scope.setdefault("organization", "Capital Hilton")
    scope.setdefault("query_summary", "Scoped Apple Mail metadata request")
    scope.setdefault("metadata_only", True)
    scope.setdefault("raw_body_read_allowed", False)
    scope.setdefault("mailbox_mutation_allowed", False)
    return scope


def validate_mac_local_action_request(request: Mapping[str, Any]) -> list[str]:
    errors = [f"missing required field: {field}" for field in REQUEST_REQUIRED_FIELDS if field not in request]
    if request.get("schema_version") != MAC_LOCAL_ACTION_REQUEST_SCHEMA:
        errors.append("schema_version must be MAC_LOCAL_ACTION_REQUEST_V0")
    if request.get("local_broker") != APPLE_MAIL_LOCAL_BROKER:
        errors.append("local_broker must be openclaw.apple_mail_local_broker")
    if request.get("requested_capability") not in APPLE_MAIL_CAPABILITIES:
        errors.append("requested_capability must be an Apple Mail local broker capability")
    denied = set(map(str, request.get("denied_actions") or []))
    required_denied = {"apple_mail_send_without_exact_payload_authority", "apple_mail_body_read_without_body_authority", "mailbox_delete", "raw_body_exposure"}
    missing = sorted(required_denied - denied)
    if missing:
        errors.append("denied_actions_missing:" + ",".join(missing))
    if request.get("status") not in {"queued_for_mac_local_action", "pending_mac_local_permission", "blocked"}:
        errors.append("status must be queued_for_mac_local_action, pending_mac_local_permission, or blocked")
    return errors


def build_mac_local_action_request(
    *,
    objective_id: str,
    source_channel: str,
    requested_by_actor: str = "Cassandra",
    target_mac_id: str = "mac:winship-primary",
    requested_capability: str = APPLE_MAIL_SCOPED_METADATA_SEARCH,
    lane_context: Mapping[str, Any] | None = None,
    input_scope: Mapping[str, Any] | None = None,
    authority_envelope_ref: str = "authority_envelope:pending_mac_local_action_scope",
    local_permission_ref: str | None = None,
    result_queue: Path | str = DEFAULT_RESULT_QUEUE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    result_dir = Path(result_queue)
    request_id = "mac_local_action_request:" + _short_hash(objective_id, source_channel, requested_capability, lane_context or {}, input_scope or {}, generated_at)
    safe_id = _safe_ref(request_id)
    request = {
        "schema_version": MAC_LOCAL_ACTION_REQUEST_SCHEMA,
        "request_id": request_id,
        "objective_id": objective_id,
        "source_channel": source_channel,
        "requested_by_actor": requested_by_actor,
        "target_mac_id": target_mac_id,
        "local_broker": APPLE_MAIL_LOCAL_BROKER,
        "requested_capability": requested_capability,
        "lane_context": dict(lane_context or {}),
        "input_scope": dict(input_scope or {}),
        "allowed_actions": allowed_actions_for_capability(requested_capability),
        "denied_actions": list(DENIED_ACTIONS),
        "authority_envelope_ref": authority_envelope_ref,
        "local_permission_ref": local_permission_ref,
        "expires_at": _expires_at(generated_at),
        "receipt_requirements": [
            "mac_local_action_receipt",
            "request_scope_echo",
            "denied_actions_confirmed",
            "mutation_performed_false",
            "raw_body_exposed_false_unless_separate_body_authority",
        ],
        "reply_to_result_path": (result_dir / f"mac_local_action_result_{safe_id}.json").as_posix(),
        "status": "queued_for_mac_local_action",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "request_filename": f"mac_local_action_request_{safe_id}.json",
        "pc_queue_path": "",
        "mac_visible_queue_path": MAC_VISIBLE_REQUEST_QUEUE,
        "mac_visible_result_path": MAC_VISIBLE_RESULT_QUEUE + f"/mac_local_action_result_{safe_id}.json",
    }
    errors = validate_mac_local_action_request(request)
    if errors:
        request["status"] = "blocked"
        request["validation_errors"] = errors
    return request


def write_mac_local_action_request(
    request: Mapping[str, Any],
    *,
    request_queue: Path | str = DEFAULT_REQUEST_QUEUE,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or str(request.get("created_at") or utc_now())
    queue = Path(request_queue)
    queue.mkdir(parents=True, exist_ok=True)
    filename = str(request.get("request_filename") or f"mac_local_action_request_{_safe_ref(str(request.get('request_id') or 'request'))}.json")
    path = queue / filename
    payload = dict(request)
    payload["pc_queue_path"] = path.as_posix()
    path.write_text(stable_json(payload), encoding="utf-8")
    with connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO mac_local_action_requests
              (request_id, objective_id, source_channel, local_broker, requested_capability,
               status, created_at, expires_at, request_path, reply_to_result_path, request_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(payload["request_id"]),
                str(payload["objective_id"]),
                str(payload["source_channel"]),
                str(payload["local_broker"]),
                str(payload["requested_capability"]),
                str(payload["status"]),
                generated_at,
                str(payload["expires_at"]),
                path.as_posix(),
                str(payload["reply_to_result_path"]),
                stable_json(payload),
            ),
        )
        event = {
            "event_id": "mac_local_action_event:" + _short_hash(payload["request_id"], "queued", generated_at),
            "request_id": payload["request_id"],
            "objective_id": payload["objective_id"],
            "event_type": "request_queued",
            "status": payload["status"],
            "created_at": generated_at,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        conn.execute(
            """
            INSERT OR REPLACE INTO mac_local_action_events
              (event_id, request_id, objective_id, event_type, status, created_at, event_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event["event_id"], event["request_id"], event["objective_id"], event["event_type"], event["status"], generated_at, stable_json(event)),
        )
        conn.commit()
    return {"request_path": path.as_posix(), "request": payload, "event": event}


def validate_mac_local_action_result(result: Mapping[str, Any], *, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
    errors = [f"missing required field: {field}" for field in RESULT_REQUIRED_FIELDS if field not in result]
    if result.get("schema_version") != MAC_LOCAL_ACTION_RESULT_SCHEMA:
        errors.append("schema_version must be MAC_LOCAL_ACTION_RESULT_V0")
    if result.get("local_broker") != APPLE_MAIL_LOCAL_BROKER:
        errors.append("local_broker must be openclaw.apple_mail_local_broker")
    if request:
        if result.get("request_id") != request.get("request_id"):
            errors.append("request_id_mismatch")
        if result.get("objective_id") != request.get("objective_id"):
            errors.append("objective_id_mismatch")
    if result.get("mutation_performed") is True:
        errors.append("mutation_performed_must_be_false_for_initial_bridge")
    if result.get("raw_body_exposed") is True:
        errors.append("raw_body_exposed_requires_separate_body_authority")
    denied_confirmed = set(map(str, result.get("denied_actions_confirmed") or []))
    if "apple_mail_send_without_exact_payload_authority" not in denied_confirmed:
        errors.append("send_denial_confirmation_required")
    return {
        "schema_version": "MAC_LOCAL_ACTION_RESULT_VERDICT_V0",
        "valid": not errors,
        "validation_errors": errors,
        "request_id": str(result.get("request_id") or ""),
        "objective_id": str(result.get("objective_id") or ""),
        "mutation_performed": bool(result.get("mutation_performed") is True),
        "raw_body_exposed": bool(result.get("raw_body_exposed") is True),
    }


def record_mac_local_action_result(
    result: Mapping[str, Any],
    *,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    request: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or str(result.get("created_at") or utc_now())
    verdict = validate_mac_local_action_result(result, request=request)
    if not verdict["valid"]:
        return {"response_status": "MAC_LOCAL_ACTION_RESULT_REJECTED", "verdict": verdict, "machine_proof": dict(AUTHORITY_BOUNDARY)}
    with connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO mac_local_action_results
              (request_id, objective_id, local_broker, status, receipt_ref, created_at, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(result["request_id"]),
                str(result["objective_id"]),
                str(result["local_broker"]),
                str(result["status"]),
                str(result["receipt_ref"]),
                generated_at,
                stable_json(dict(result)),
            ),
        )
        event = {
            "event_id": "mac_local_action_event:" + _short_hash(result["request_id"], "result", generated_at),
            "request_id": str(result["request_id"]),
            "objective_id": str(result["objective_id"]),
            "event_type": "result_recorded",
            "status": str(result["status"]),
            "created_at": generated_at,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        conn.execute(
            """
            INSERT OR REPLACE INTO mac_local_action_events
              (event_id, request_id, objective_id, event_type, status, created_at, event_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event["event_id"], event["request_id"], event["objective_id"], event["event_type"], event["status"], generated_at, stable_json(event)),
        )
        conn.commit()
    return {"response_status": "MAC_LOCAL_ACTION_RESULT_RECORDED", "verdict": verdict, "event": event, "machine_proof": dict(AUTHORITY_BOUNDARY)}


def build_package_plan_for_text(
    text: str,
    *,
    source_channel: str,
    objective_id: str = "",
    lane_context: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    capability = capability_for_text(text)
    return {
        "schema_version": MAC_LOCAL_ACTION_PACKAGE_PLAN_SCHEMA,
        "recognized": detects_apple_mail_local_request(text),
        "source_channel": source_channel,
        "objective_id": objective_id,
        "required_executor": "mac_local",
        "package_target": "mac_surface_action",
        "local_broker": APPLE_MAIL_LOCAL_BROKER,
        "requested_capability": capability,
        "required_request_schema": MAC_LOCAL_ACTION_REQUEST_SCHEMA,
        "required_result_schema": MAC_LOCAL_ACTION_RESULT_SCHEMA,
        "queue_paths": {
            "pc_to_mac_request_queue": DEFAULT_REQUEST_QUEUE.as_posix(),
            "mac_to_pc_result_queue": DEFAULT_RESULT_QUEUE.as_posix(),
            "mac_visible_request_queue": MAC_VISIBLE_REQUEST_QUEUE,
            "mac_visible_result_queue": MAC_VISIBLE_RESULT_QUEUE,
        },
        "lane_context": dict(lane_context or {}),
        "allowed_actions": allowed_actions_for_capability(capability),
        "denied_actions": list(DENIED_ACTIONS),
        "policy_gates": list(POLICY_GATES),
        "next_safe_step": "Wait for the Mac-local action result; do not execute Apple Mail on PC.",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
