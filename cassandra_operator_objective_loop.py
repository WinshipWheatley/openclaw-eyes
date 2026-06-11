"""Cassandra gated operator objective loop V0.

This module records and advances Cassandra-owned operator objectives without
calling Google APIs, opening browsers, creating Gmail drafts, sending mail, or
trusting raw authority text. Google Workspace access remains brokered through
authority envelopes, credential leases, policy gates, and verifier receipts.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import ar_counterparty_contact_operations as ar_ops
import authority_secret_custody as custody
import mac_local_action_bridge


ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/cassandra_operator_objective_loop.sqlite")

CASSANDRA_OPERATOR_OBJECTIVE_SCHEMA = "CASSANDRA_OPERATOR_OBJECTIVE_V0"
LOOKUP_AUTHORITY_REQUEST_SCHEMA = "CASSANDRA_LOOKUP_AUTHORITY_REQUEST_V0"
TEXT_FOLLOWUP_DRAFT_SCHEMA = "TEXT_FOLLOWUP_DRAFT_V0"
APPROVED_SEND_DRAFT_ARTIFACT_SCHEMA = "APPROVED_SEND_DRAFT_ARTIFACT_V0"
EXACT_SEND_AUTHORITY_REQUEST_SCHEMA = "EXACT_SEND_AUTHORITY_REQUEST_V0"
EXACT_SEND_REVIEW_PACKET_SCHEMA = "EXACT_SEND_REVIEW_PACKET_V0"
EXACT_SEND_APPROVAL_DECISION_SCHEMA = "EXACT_SEND_APPROVAL_DECISION_V0"
EXACT_SEND_DRY_RUN_RECEIPT_SCHEMA = "EXACT_SEND_DRY_RUN_RECEIPT_V0"
EXACT_SEND_REFUSAL_RECEIPT_SCHEMA = "EXACT_SEND_REFUSAL_RECEIPT_V0"
EXACT_SEND_LIVE_TRANSPORT_REFUSAL_RECEIPT_SCHEMA = "EXACT_SEND_LIVE_TRANSPORT_REFUSAL_RECEIPT_V0"
EXACT_SEND_LIVE_TRANSPORT_TERMINAL_RECEIPT_SCHEMA = "EXACT_SEND_LIVE_TRANSPORT_TERMINAL_RECEIPT_V0"
EXACT_SEND_FUTURE_LIVE_SUCCESS_RECEIPT_SCHEMA = "EXACT_SEND_FUTURE_LIVE_SUCCESS_RECEIPT_V0"
UNATTENDED_REQUIREMENT_SCHEMA = "CASSANDRA_UNATTENDED_SEND_REQUIREMENT_V0"

READ_ONLY_EMAIL_LOOKUP = custody.READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID
GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID = custody.GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID

GMAIL_METADATA_READ = "openclaw.gmail_metadata_read"
GMAIL_BODY_READ = "openclaw.gmail_body_read"
GMAIL_DRAFT_GENERATOR = "openclaw.gmail_draft_generator"
GMAIL_SEND_MAIL = "openclaw.gmail_send_mail"
GOOGLE_GMAIL_SEND_BROKER_CAPABILITY = "google.gmail.send"
GOOGLE_BROKER_AGENT_CASSANDRA = "cassandra"

STATUS_PLANNING = "planning"
STATUS_WAITING_LOOKUP_AUTHORITY = "waiting_for_lookup_authority"
STATUS_LOOKUP_READY = "lookup_ready"
STATUS_LOOKUP_COMPLETE = "lookup_complete"
STATUS_WAITING_BODY_READ_AUTHORITY = "waiting_for_body_read_authority"
STATUS_DRAFT_READY_FOR_REVIEW = "draft_ready_for_review"
STATUS_WAITING_SEND_AUTHORITY = "waiting_for_send_authority"
STATUS_WAITING_UNATTENDED_RUN_AUTHORITY = "waiting_for_unattended_run_authority"
STATUS_SCHEDULED = "scheduled"
STATUS_SENT = "sent"
STATUS_BLOCKED = "blocked"
STATUS_COMPLETE = "complete"
STATUS_WAITING_MAC_LOCAL_ACTION_RESULT = "waiting_for_mac_local_action_result"
STATUS_MAC_LOCAL_ACTION_COMPLETE = "mac_local_action_complete"

MAC_LOCAL_SHADOW_RESULT_NEXT_SAFE_STEP = (
    "Mac Apple Mail live adapter is not enabled. Next: approve/build selected-message metadata proof harness if needed."
)
MAC_LOCAL_SHADOW_RESULT_OPERATOR_ANSWER = (
    "Cassandra received the Mac shadow result. The Mac bridge is working, but live Apple Mail execution is not enabled. "
    "No email was read, drafted, sent, or mutated. Next: build or approve the selected-message metadata proof harness."
)

DENIED_ACTIONS = (
    "compose_email",
    "send_email",
    "create_email_draft",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "modify_email_labels",
    "contacts_read",
    "calendar_access",
    "calendar_mutation",
    "mutate_contacts",
    "promote_contact_memory",
    "paid_marking",
    "mark_paid",
    "ledger_mutation",
    "mutate_ledger",
    "coupa_submit",
    "open_browser",
    "open_gmail_ui",
    "trust_raw_authority_granted",
    "broad_google_workspace_broker_ambient_use",
)

AUTHORITY_BOUNDARY = {
    "broad_broker_ambient_use": False,
    "gmail_lookup_performed": False,
    "gmail_body_read_performed": False,
    "gmail_draft_created": False,
    "email_send_performed": False,
    "scheduled_send_created": False,
    "calendar_api_called": False,
    "contacts_api_called": False,
    "calendar_mutation_allowed": False,
    "contacts_mutation_allowed": False,
    "paid_marking_allowed": False,
    "ledger_mutation_allowed": False,
    "coupa_access_allowed": False,
    "token_exposed": False,
    "secret_exposed": False,
    "raw_authority_granted_trusted": False,
    "pc_apple_mail_execution_allowed": False,
    "apple_mail_called": False,
    "apple_mail_automation_invoked": False,
    "mailbox_mutation_allowed": False,
    "mail_body_read_allowed": False,
    "mail_draft_create_allowed": False,
    "mail_send_allowed": False,
}

STEP_TYPES = (
    "scoped_email_metadata_lookup",
    "optional_email_body_read",
    "text_followup_draft",
    "operator_draft_review",
    "optional_gmail_draft_create",
    "optional_email_send",
    "optional_unattended_send_window",
    "completion_receipt",
)

INTERRUPT_CONDITIONS = (
    "new_matching_reply",
    "draft_changed",
    "approval_expired",
    "verifier_fails",
    "mfa_or_credential_issue",
    "send_window_expired",
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


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value)
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _message_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(("cassandra-operator-objective-v0:" + str(text or "")).encode("utf-8")).hexdigest()


def _excerpt(text: str, limit: int = 180) -> str:
    clean = " ".join(str(text or "").replace("\x00", " ").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _next_timestamp(value: str) -> str:
    try:
        return (datetime.fromisoformat(value) + timedelta(seconds=1)).isoformat(timespec="seconds")
    except ValueError:
        return value


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _timestamp_expired(expires_at: str | None, *, generated_at: str | None = None) -> bool:
    expiry = _parse_timestamp(expires_at)
    if expiry is None:
        return False
    observed = _parse_timestamp(generated_at) or datetime.now(timezone.utc)
    return observed > expiry


def _default_exact_send_expires_at(generated_at: str) -> str:
    parsed = _parse_timestamp(generated_at) or datetime.now(timezone.utc)
    return (parsed + timedelta(minutes=30)).isoformat(timespec="seconds")


def _is_live_objective_db(sqlite_path: Path | str) -> bool:
    candidate = _rooted(sqlite_path)
    live_path = _rooted(DEFAULT_SQLITE_PATH)
    try:
        if candidate.resolve(strict=False) == live_path.resolve(strict=False):
            return True
        if candidate.exists() and live_path.exists() and candidate.samefile(live_path):
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return False


def _connect(sqlite_path: Path | str = DEFAULT_SQLITE_PATH) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cassandra_operator_objectives (
          objective_id TEXT PRIMARY KEY,
          actor TEXT NOT NULL,
          source_channel TEXT NOT NULL,
          objective_status TEXT NOT NULL,
          current_step TEXT NOT NULL,
          safe_next_step TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          objective_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS objective_steps (
          objective_id TEXT NOT NULL,
          step_id TEXT NOT NULL,
          step_type TEXT NOT NULL,
          status TEXT NOT NULL,
          step_json TEXT NOT NULL,
          PRIMARY KEY (objective_id, step_id)
        );

        CREATE TABLE IF NOT EXISTS objective_channel_messages (
          message_record_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          source_channel TEXT NOT NULL,
          source_message_ref TEXT NOT NULL,
          message_text_hash TEXT NOT NULL,
          message_text_excerpt TEXT NOT NULL,
          message_text_stored INTEGER NOT NULL DEFAULT 0,
          message_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS objective_authority_refs (
          objective_id TEXT NOT NULL,
          authority_ref TEXT NOT NULL,
          authority_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          ref_json TEXT NOT NULL,
          PRIMARY KEY (objective_id, authority_ref)
        );

        CREATE TABLE IF NOT EXISTS objective_credential_leases (
          objective_id TEXT NOT NULL,
          credential_lease_ref TEXT NOT NULL,
          credential_handle_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          status TEXT NOT NULL,
          lease_json TEXT NOT NULL,
          PRIMARY KEY (objective_id, credential_lease_ref)
        );

        CREATE TABLE IF NOT EXISTS objective_receipts (
          objective_id TEXT NOT NULL,
          receipt_ref TEXT NOT NULL,
          receipt_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          receipt_json TEXT NOT NULL,
          PRIMARY KEY (objective_id, receipt_ref)
        );

        CREATE TABLE IF NOT EXISTS objective_events (
          event_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          channel TEXT NOT NULL,
          message_ref TEXT NOT NULL,
          decision TEXT NOT NULL,
          actor TEXT NOT NULL,
          status_transition TEXT NOT NULL,
          receipt_ref TEXT NOT NULL,
          created_at TEXT NOT NULL,
          event_json TEXT NOT NULL
        );
        """
    )


def detects_make_it_so_email_objective(text: str) -> bool:
    lowered = str(text or "").lower()
    email_lookup = any(term in lowered for term in ("email", "emails", "gmail", "reply", "replied", "responded", "response", "responese", "recieved", "received"))
    followup = any(term in lowered for term in ("follow up", "follow-up", "followup", "send a follow", "send it", "send a reply"))
    review_first = any(term in lowered for term in ("show me the draft", "show the draft", "before you send", "before sending", "review", "don't send until", "do not send until"))
    return email_lookup and followup and review_first


def detects_draft_approval_send_authority(text: str) -> bool:
    lowered = str(text or "").lower()
    draft_approval = any(phrase in lowered for phrase in ("draft is approved", "approved with this exact text", "draft approved"))
    send_authority = any(phrase in lowered for phrase in ("prepare the send authority", "send authority request", "do not send until", "exact send request", "don't send until"))
    return draft_approval and send_authority


def detects_ar_counterparty_objective(text: str) -> bool:
    return ar_ops.detects_ar_counterparty_intent(text)


def _strip_cassandra_prefix(text: str) -> str:
    return re.sub(r"^\s*(cassandra|clara)\s*[:,]\s*", "", str(text or ""), flags=re.I).strip()


def _extract_counterparty(text: str) -> str:
    lowered = text.lower()
    if "annette" in lowered:
        return "Annette"
    if "glenn" in lowered:
        return "Glenn"
    match = re.search(r"\bfrom\s+([A-Z][A-Za-z.'-]+)\b", text)
    if match:
        return match.group(1)
    match = re.search(r"\bwith\s+([A-Z][A-Za-z.'-]+)\b", text)
    if match:
        return match.group(1)
    return "specified counterparty"


def _extract_organization(text: str, lane_context: Mapping[str, Any] | None = None) -> str:
    lowered = text.lower()
    if "capital hilton" in lowered or "capital_hilton" in lowered:
        return "Capital Hilton"
    if "live arts" in lowered or "live_arts" in lowered:
        return "Live Arts"
    if "st. anne" in lowered or "st anne" in lowered or "st_annes" in lowered:
        return "St. Anne's"
    match = re.search(r"\bat\s+([A-Z][A-Za-z0-9.'& -]{2,80}?)(?:[?.!,]|$)", text)
    if match:
        return " ".join(match.group(1).split())
    context = lane_context or {}
    thread = str(context.get("target_thread_ref") or context.get("thread_ref") or "").replace("_", " ").strip()
    if thread:
        return thread.title()
    return "specified organization"


def _objective_summary(counterparty: str, organization: str) -> str:
    return (
        f"Check for a reply from {counterparty} at {organization}; if no matching reply exists, "
        "prepare a follow-up draft for operator review before any send."
    )


def _intended_outcome(counterparty: str, organization: str, scheduled: bool) -> str:
    schedule_phrase = " and prepare a scheduled-send authority path" if scheduled else ""
    return (
        f"Find whether {counterparty} at {organization} replied; if not, draft the follow-up, "
        f"show draft before sending, then request exact send authority{schedule_phrase}."
    )


def _step(step_type: str, status: str, **extra: Any) -> dict[str, Any]:
    base = {
        "step_id": step_type,
        "step_type": step_type,
        "status": status,
        "no_execution_performed": True,
    }
    base.update(extra)
    return base


def _build_steps(*, scheduled: bool) -> list[dict[str, Any]]:
    return [
        _step(
            "scoped_email_metadata_lookup",
            "waiting_for_authority",
            capability_ids=[GMAIL_METADATA_READ, READ_ONLY_EMAIL_LOOKUP],
            authority_needed="scoped Gmail metadata lookup authority envelope",
            credential_candidate=GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID,
            required_lease="broker read-only credential lease",
            allowed_actions=["scoped_gmail_search", "scoped_gmail_metadata_read", "receipt_creation", "redacted_summary"],
            denied_actions=list(DENIED_ACTIONS),
        ),
        _step(
            "optional_email_body_read",
            "blocked_until_separate_body_read_authority",
            capability_ids=[GMAIL_BODY_READ],
            authority_needed="separate body-read authority if metadata evidence is insufficient",
            denied_actions=list(DENIED_ACTIONS),
        ),
        _step(
            "text_followup_draft",
            "pending_lookup_result",
            capability_ids=[],
            gmail_draft_created=False,
            email_send_performed=False,
        ),
        _step(
            "operator_draft_review",
            "pending_text_draft",
            requires_operator_review=True,
        ),
        _step(
            "optional_gmail_draft_create",
            "blocked_without_draft_authority",
            capability_ids=[GMAIL_DRAFT_GENERATOR],
            send_denied_separately=True,
        ),
        _step(
            "optional_email_send",
            "blocked_without_exact_send_authority",
            capability_ids=[GMAIL_SEND_MAIL],
            requires_exact_payload_approval=True,
            send_disabled_by_default=True,
        ),
        _step(
            "optional_unattended_send_window",
            "blocked_without_unattended_run_envelope" if scheduled else "not_requested_yet",
            required_schema_version=custody.UNATTENDED_RUN_ENVELOPE_SCHEMA,
            interrupt_conditions=list(INTERRUPT_CONDITIONS),
        ),
        _step(
            "completion_receipt",
            "pending",
            required_receipts=["lookup_receipt", "draft_review_receipt", "send_or_blocker_receipt"],
        ),
    ]


def _authority_request(objective_id: str, counterparty: str, organization: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": LOOKUP_AUTHORITY_REQUEST_SCHEMA,
        "approval_request_id": f"approval_request:cassandra_lookup:{_short_hash(objective_id, generated_at)}",
        "objective_id": objective_id,
        "requested_capability_ids": [GMAIL_METADATA_READ, READ_ONLY_EMAIL_LOOKUP],
        "credential_candidate": GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID,
        "required_authority": "scoped read-only Gmail metadata lookup envelope",
        "required_lease": "broker read-only credential lease",
        "max_scope": {
            "person": counterparty,
            "organization": organization,
            "objective": "payment follow-up",
            "allowed_use": "Gmail metadata search only",
        },
        "denied_actions": list(DENIED_ACTIONS),
        "execution_authorized": False,
        "created_at": generated_at,
        "raw_authority_granted_trusted": False,
    }


def build_cassandra_operator_objective(
    original_user_text: str,
    *,
    source_channel: str,
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    requested_by_operator: str = "operator:winship",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    clean_text = _strip_cassandra_prefix(original_user_text)
    context = dict(lane_context or {})
    counterparty = _extract_counterparty(clean_text)
    organization = _extract_organization(clean_text, context)
    scheduled = "tomorrow" in clean_text.lower() or "later" in clean_text.lower() or "scheduled" in clean_text.lower()
    context.setdefault("organization", organization)
    context.setdefault("counterparty", counterparty)
    context.setdefault("objective_lane", "payment follow-up")
    objective_id = "cassandra_operator_objective:" + _short_hash(clean_text, source_channel, context, requested_by_operator)
    steps = _build_steps(scheduled=scheduled)
    authority_request = _authority_request(objective_id, counterparty, organization, generated_at)
    return {
        "schema_version": CASSANDRA_OPERATOR_OBJECTIVE_SCHEMA,
        "objective_id": objective_id,
        "actor": "Cassandra",
        "requested_by_operator": requested_by_operator,
        "source_channel": source_channel,
        "source_message_ref": source_message_ref,
        "original_user_text": clean_text,
        "lane_context": context,
        "client_or_counterparty": counterparty,
        "objective_summary": _objective_summary(counterparty, organization),
        "intended_outcome": _intended_outcome(counterparty, organization, scheduled),
        "current_step": "scoped_email_metadata_lookup",
        "objective_status": STATUS_WAITING_LOOKUP_AUTHORITY,
        "steps": steps,
        "authority_refs": [],
        "credential_lease_refs": [],
        "receipts": [],
        "proof_refs": [],
        "denied_actions": list(DENIED_ACTIONS),
        "safe_next_step": "Approve the scoped metadata lookup.",
        "lookup_authority_request": authority_request,
        "created_at": generated_at,
        "updated_at": generated_at,
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }


def _store_objective(conn: sqlite3.Connection, objective: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO cassandra_operator_objectives
          (objective_id, actor, source_channel, objective_status, current_step,
           safe_next_step, created_at, updated_at, objective_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            objective["objective_id"],
            objective["actor"],
            objective["source_channel"],
            objective["objective_status"],
            objective["current_step"],
            objective["safe_next_step"],
            objective["created_at"],
            objective["updated_at"],
            stable_json(objective),
        ),
    )
    for step in objective.get("steps") or []:
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_steps
              (objective_id, step_id, step_type, status, step_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                objective["objective_id"],
                step["step_id"],
                step["step_type"],
                step["status"],
                stable_json(step),
            ),
        )


def _store_message(conn: sqlite3.Connection, objective: Mapping[str, Any]) -> None:
    message_ref = str(objective.get("source_message_ref") or "")
    text = str(objective.get("original_user_text") or "")
    record = {
        "objective_id": objective["objective_id"],
        "source_channel": objective["source_channel"],
        "source_message_ref": message_ref,
        "message_text_hash": _message_hash(text),
        "message_text_excerpt": _excerpt(text),
        "message_text_stored": False,
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO objective_channel_messages
          (message_record_id, objective_id, source_channel, source_message_ref,
           message_text_hash, message_text_excerpt, message_text_stored, message_json)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            "objective_message:" + _short_hash(objective["objective_id"], message_ref, text),
            objective["objective_id"],
            objective["source_channel"],
            message_ref,
            record["message_text_hash"],
            record["message_text_excerpt"],
            stable_json(record),
        ),
    )


def _store_event(
    conn: sqlite3.Connection,
    *,
    objective_id: str,
    channel: str,
    message_ref: str,
    decision: str,
    status_transition: str,
    receipt_ref: str = "",
    actor: str = "Cassandra",
    generated_at: str,
) -> dict[str, Any]:
    event = {
        "event_id": "objective_event:" + _short_hash(objective_id, channel, message_ref, decision, status_transition, generated_at),
        "objective_id": objective_id,
        "channel": channel,
        "message_ref": message_ref,
        "decision": decision,
        "actor": actor,
        "status_transition": status_transition,
        "receipt_ref": receipt_ref,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO objective_events
          (event_id, objective_id, channel, message_ref, decision, actor,
           status_transition, receipt_ref, created_at, event_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_id"],
            objective_id,
            channel,
            message_ref,
            decision,
            actor,
            status_transition,
            receipt_ref,
            generated_at,
            stable_json(event),
        ),
    )
    return event


def _load_objective(conn: sqlite3.Connection, objective_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT objective_json FROM cassandra_operator_objectives WHERE objective_id = ?",
        (objective_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"unknown objective_id: {objective_id}")
    return json.loads(row["objective_json"])


def _maybe_load_objective(conn: sqlite3.Connection, objective_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT objective_json FROM cassandra_operator_objectives WHERE objective_id = ?",
        (objective_id,),
    ).fetchone()
    if not row:
        return None
    return json.loads(row["objective_json"])


def _persist_objective(objective: Mapping[str, Any], sqlite_path: Path | str, *, generated_at: str, decision: str) -> None:
    with _connect(sqlite_path) as conn:
        _store_objective(conn, objective)
        _store_message(conn, objective)
        _store_event(
            conn,
            objective_id=str(objective["objective_id"]),
            channel=str(objective.get("source_channel") or ""),
            message_ref=str(objective.get("source_message_ref") or ""),
            decision=decision,
            status_transition=str(objective.get("objective_status") or ""),
            generated_at=generated_at,
        )
        conn.commit()


def _operator_reply() -> str:
    return (
        "I can handle that as a gated Cassandra objective. First I need approval for a scoped "
        "Gmail metadata lookup for Annette / Capital Hilton. If no matching reply is found, "
        "I'll prepare a follow-up draft and stop for your review before anything is sent.\n\n"
        "Next safe step: Approve the scoped metadata lookup."
    )



def _mac_local_operator_reply() -> str:
    return (
        "Cassandra needs the Mac to perform this Apple Mail action. I queued a scoped "
        "Mac-local action request.\n\n"
        "Next safe step: wait for the Mac-local action result. No Apple Mail action has run on PC."
    )


def build_mac_local_action_objective(
    original_user_text: str,
    *,
    source_channel: str,
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    requested_by_operator: str = "operator:winship",
    mac_result_queue: Path | str = mac_local_action_bridge.DEFAULT_RESULT_QUEUE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    clean_text = _strip_cassandra_prefix(original_user_text)
    context = dict(lane_context or {})
    counterparty = _extract_counterparty(clean_text)
    organization = _extract_organization(clean_text, context)
    context.setdefault("organization", organization)
    context.setdefault("counterparty", counterparty)
    context.setdefault("objective_lane", "mac-local Apple Mail action")
    capability = mac_local_action_bridge.capability_for_text(clean_text)
    objective_id = "cassandra_operator_objective:" + _short_hash(clean_text, source_channel, context, requested_by_operator, "mac_local_action")
    input_scope = mac_local_action_bridge.build_input_scope(clean_text, context)
    request = mac_local_action_bridge.build_mac_local_action_request(
        objective_id=objective_id,
        source_channel=source_channel,
        requested_by_actor="Cassandra",
        requested_capability=capability,
        lane_context=context,
        input_scope=input_scope,
        authority_envelope_ref="authority_envelope:pending_mac_local_action_scope",
        local_permission_ref=None,
        result_queue=mac_result_queue,
        generated_at=generated_at,
    )
    steps = [
        _step(
            "mac_local_action_request",
            "queued_for_mac",
            capability_ids=[mac_local_action_bridge.APPLE_MAIL_LOCAL_BROKER, capability],
            required_request_schema=mac_local_action_bridge.MAC_LOCAL_ACTION_REQUEST_SCHEMA,
            required_executor="mac_local",
            request_id=request["request_id"],
            allowed_actions=list(request["allowed_actions"]),
            denied_actions=list(request["denied_actions"]),
        ),
        _step(
            "mac_local_action_result",
            "waiting_for_mac_result",
            required_result_schema=mac_local_action_bridge.MAC_LOCAL_ACTION_RESULT_SCHEMA,
            reply_to_result_path=request["reply_to_result_path"],
        ),
    ]
    return {
        "schema_version": CASSANDRA_OPERATOR_OBJECTIVE_SCHEMA,
        "objective_id": objective_id,
        "actor": "Cassandra",
        "requested_by_operator": requested_by_operator,
        "source_channel": source_channel,
        "source_message_ref": source_message_ref,
        "original_user_text": clean_text,
        "lane_context": context,
        "client_or_counterparty": counterparty,
        "objective_summary": f"Ask the Mac to perform a scoped Apple Mail local action for {counterparty} / {organization}.",
        "intended_outcome": "Queue a Mac-local action request, wait for a receipt-backed result, and avoid PC-side Apple Mail execution.",
        "current_step": "mac_local_action_request",
        "objective_status": STATUS_WAITING_MAC_LOCAL_ACTION_RESULT,
        "steps": steps,
        "authority_refs": [request["authority_envelope_ref"]],
        "credential_lease_refs": [],
        "receipts": [],
        "proof_refs": [request["request_id"]],
        "denied_actions": _dedupe([*DENIED_ACTIONS, *request["denied_actions"]]),
        "safe_next_step": "Wait for the Mac-local action result.",
        "mac_local_action_request": request,
        "package_plan": mac_local_action_bridge.build_package_plan_for_text(
            clean_text,
            source_channel=source_channel,
            objective_id=objective_id,
            lane_context=context,
            generated_at=generated_at,
        ),
        "created_at": generated_at,
        "updated_at": generated_at,
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }


def route_mac_local_action_objective_message(
    text: str,
    *,
    source_channel: str,
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    mac_bridge_sqlite_path: Path | str = mac_local_action_bridge.DEFAULT_SQLITE_PATH,
    mac_request_queue: Path | str = mac_local_action_bridge.DEFAULT_REQUEST_QUEUE,
    mac_result_queue: Path | str = mac_local_action_bridge.DEFAULT_RESULT_QUEUE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    objective = build_mac_local_action_objective(
        text,
        source_channel=source_channel,
        source_message_ref=source_message_ref,
        lane_context=lane_context,
        mac_result_queue=mac_result_queue,
        generated_at=generated_at,
    )
    queued = mac_local_action_bridge.write_mac_local_action_request(
        objective["mac_local_action_request"],
        request_queue=mac_request_queue,
        sqlite_path=mac_bridge_sqlite_path,
        generated_at=generated_at,
    )
    objective["mac_local_action_request"] = queued["request"]
    objective["proof_refs"] = _dedupe([*objective.get("proof_refs", []), queued["request_path"]])
    _persist_objective(objective, sqlite_path, generated_at=generated_at, decision="mac_local_action_request_queued")
    proof = dict(AUTHORITY_BOUNDARY)
    proof.update(
        {
            "mac_local_action_request_created": True,
            "pc_apple_mail_execution_performed": False,
            "mailbox_mutation_performed": False,
            "raw_body_exposed": False,
        }
    )
    return {
        "schema_version": "CASSANDRA_OPERATOR_OBJECTIVE_ROUTE_V0",
        "recognized": True,
        "response_status": "CASSANDRA_OBJECTIVE_WAITING_FOR_MAC_LOCAL_ACTION",
        "operator_reply": _mac_local_operator_reply(),
        "next_safe_step": objective["safe_next_step"],
        "objective": objective,
        "mac_local_action_request": queued["request"],
        "mac_local_action_request_path": queued["request_path"],
        "package_plan": objective["package_plan"],
        "machine_proof": proof,
    }


def _ar_operator_reply(ar_plan: Mapping[str, Any]) -> str:
    contact = ar_plan.get("contact") if isinstance(ar_plan.get("contact"), Mapping) else {}
    account = ar_plan.get("account") if isinstance(ar_plan.get("account"), Mapping) else {}
    return (
        "I can handle this as a gated AR contact objective. "
        f"I resolved {contact.get('display_name', 'the contact')} as the payment contact for "
        f"{account.get('account_label', 'the account')}. "
        f"Next safe step: {ar_plan.get('next_safe_step')}"
    )


def _ar_objective_status(ar_plan: Mapping[str, Any]) -> str:
    intent = str(ar_plan.get("intent") or "")
    required_authority = str(ar_plan.get("required_authority") or "")
    if required_authority == "single_message_body_read_authority":
        return STATUS_WAITING_BODY_READ_AUTHORITY
    if intent == "payment_followup":
        return STATUS_WAITING_LOOKUP_AUTHORITY
    if intent == "invoice_send":
        return STATUS_WAITING_SEND_AUTHORITY
    if intent == "email_watch":
        return STATUS_WAITING_UNATTENDED_RUN_AUTHORITY
    if intent == "email_followup":
        return STATUS_DRAFT_READY_FOR_REVIEW
    return STATUS_PLANNING


def build_ar_counterparty_objective(
    original_user_text: str,
    *,
    ar_plan: Mapping[str, Any],
    source_channel: str,
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    requested_by_operator: str = "operator:winship",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    clean_text = _strip_cassandra_prefix(original_user_text)
    account = ar_plan.get("account") if isinstance(ar_plan.get("account"), Mapping) else {}
    contact = ar_plan.get("contact") if isinstance(ar_plan.get("contact"), Mapping) else {}
    objective_id = "cassandra_operator_objective:" + _short_hash(
        clean_text,
        source_channel,
        account.get("account_id"),
        contact.get("contact_id"),
        requested_by_operator,
        "ar_contact_operations",
    )
    status = _ar_objective_status(ar_plan)
    context = dict(lane_context or {})
    context.setdefault("objective_lane", "accounts receivable contact operations")
    context.setdefault("account_id", account.get("account_id"))
    context.setdefault("contact_id", contact.get("contact_id"))
    steps = [
        _step(
            "ar_contact_profile_resolution",
            "complete",
            capability_ids=["ar_contact_profile_resolution"],
            account_id=account.get("account_id"),
            contact_id=contact.get("contact_id"),
            relationship_status=list(contact.get("relationship_status") or []),
        ),
        _step(
            "ar_policy_next_authority",
            "waiting_for_authority" if "authority" in str(ar_plan.get("required_authority") or "") else "ready_for_review",
            required_authority=ar_plan.get("required_authority"),
            next_safe_step=ar_plan.get("next_safe_step"),
            denied_actions=list(ar_plan.get("denied_actions") or []),
        ),
        _step(
            "ar_receipt",
            "pending",
            required_receipts=["policy_resolution_receipt", "authority_or_blocker_receipt"],
        ),
    ]
    return {
        "schema_version": CASSANDRA_OPERATOR_OBJECTIVE_SCHEMA,
        "objective_id": objective_id,
        "actor": "Cassandra",
        "requested_by_operator": requested_by_operator,
        "source_channel": source_channel,
        "source_message_ref": source_message_ref,
        "original_user_text": clean_text,
        "lane_context": context,
        "client_or_counterparty": contact.get("display_name") or account.get("account_label") or "specified AR counterparty",
        "objective_summary": (
            f"Handle AR contact operations for {account.get('account_label', 'the account')} "
            f"through {contact.get('display_name', 'the resolved contact')}."
        ),
        "intended_outcome": "Resolve the AR contact, identify the one next gated action, and preserve send/body/watch locks.",
        "current_step": "ar_policy_next_authority",
        "objective_status": status,
        "steps": steps,
        "authority_refs": [],
        "credential_lease_refs": [],
        "receipts": [],
        "proof_refs": [str(ar_plan.get("metadata_receipt_path") or "")] if ar_plan.get("metadata_receipt_path") else [],
        "denied_actions": list(ar_plan.get("denied_actions") or DENIED_ACTIONS),
        "safe_next_step": str(ar_plan.get("next_safe_step") or "Review the AR contact objective."),
        "ar_plan": dict(ar_plan),
        "package_plan": dict(ar_plan.get("package_plan") or {}),
        "created_at": generated_at,
        "updated_at": generated_at,
        "machine_proof": dict(ar_plan.get("machine_proof") or AUTHORITY_BOUNDARY),
    }


def route_ar_counterparty_objective_message(
    text: str,
    *,
    source_channel: str,
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    ar_sqlite_path: Path | str = ar_ops.DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    ar_sqlite_path = ar_sqlite_path or ar_ops.DEFAULT_SQLITE_PATH
    ar_plan = ar_ops.plan_ar_counterparty_action(text, sqlite_path=ar_sqlite_path, generated_at=generated_at)
    if not ar_plan.get("recognized"):
        return {
            "schema_version": "CASSANDRA_OPERATOR_OBJECTIVE_ROUTE_V0",
            "recognized": False,
            "response_status": "NOT_CASSANDRA_AR_OBJECTIVE",
            "ar_plan": ar_plan,
            "machine_proof": dict(AUTHORITY_BOUNDARY),
        }
    objective = build_ar_counterparty_objective(
        text,
        ar_plan=ar_plan,
        source_channel=source_channel,
        source_message_ref=source_message_ref,
        lane_context=lane_context,
        generated_at=generated_at,
    )
    _persist_objective(objective, sqlite_path, generated_at=generated_at, decision="ar_contact_objective_planned")
    proof = dict(AUTHORITY_BOUNDARY)
    proof.update(dict(ar_plan.get("machine_proof") or {}))
    return {
        "schema_version": "CASSANDRA_OPERATOR_OBJECTIVE_ROUTE_V0",
        "recognized": True,
        "response_status": "CASSANDRA_AR_OBJECTIVE_PLANNED",
        "operator_reply": _ar_operator_reply(ar_plan),
        "next_safe_step": objective["safe_next_step"],
        "objective": objective,
        "ar_plan": ar_plan,
        "package_plan": ar_plan.get("package_plan"),
        "machine_proof": proof,
    }

def extract_approved_draft_payload(text: str) -> dict[str, Any]:
    recipient_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
    recipient = recipient_match.group(1) if recipient_match else ""

    subject_match = re.search(r"Subject:\s*([^\n]+)", text, re.IGNORECASE)
    subject = subject_match.group(1).strip() if subject_match else ""

    body = ""
    if subject_match:
        parts = text[subject_match.end():].split("Prepare the send", 1)
        if len(parts) == 1:
            parts = text[subject_match.end():].split("do not send", 1)
        if len(parts) == 1:
            parts = text[subject_match.end():].split("Do not send", 1)
        body = parts[0].strip()

    return {
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "payload_hash": _payload_hash(recipient=recipient, subject=subject, body=body),
    }


def route_draft_approval_to_send_authority(
    text: str,
    *,
    objective_id: str | None = None,
    source_channel: str,
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    payload = extract_approved_draft_payload(text)

    with _connect(sqlite_path) as conn:
        objective = None
        if objective_id:
            objective = _maybe_load_objective(conn, objective_id)
        if not objective:
            cursor = conn.execute(
                "SELECT objective_json FROM cassandra_operator_objectives WHERE objective_status = ?",
                (STATUS_DRAFT_READY_FOR_REVIEW,)
            )
            row = cursor.fetchone()
            if row:
                objective = json.loads(row["objective_json"])

        if not objective:
            obj_id = "cassandra_operator_objective:" + _short_hash(text, source_channel, generated_at)
            objective = {
                "schema_version": CASSANDRA_OPERATOR_OBJECTIVE_SCHEMA,
                "objective_id": obj_id,
                "actor": "Cassandra",
                "requested_by_operator": "operator:winship",
                "source_channel": source_channel,
                "source_message_ref": source_message_ref,
                "original_user_text": text,
                "lane_context": dict(lane_context or {}),
                "client_or_counterparty": "specified counterparty",
                "objective_summary": "Prepare exact send authority request.",
                "intended_outcome": "Draft approved, requesting exact send authority.",
                "current_step": "optional_email_send",
                "objective_status": STATUS_WAITING_SEND_AUTHORITY,
                "steps": [],
                "authority_refs": [],
                "credential_lease_refs": [],
                "receipts": [],
                "proof_refs": [],
                "denied_actions": list(DENIED_ACTIONS),
                "safe_next_step": "Review exact send/scheduled-send authority request.",
                "created_at": generated_at,
                "updated_at": generated_at,
                "machine_proof": dict(AUTHORITY_BOUNDARY),
            }
            obj_id = objective["objective_id"]
        else:
            obj_id = objective["objective_id"]
            objective["objective_status"] = STATUS_WAITING_SEND_AUTHORITY
            objective["current_step"] = "optional_email_send"
            objective["safe_next_step"] = "Review exact send/scheduled-send authority request."
            objective["updated_at"] = generated_at

        artifact = store_approved_send_draft_artifact(objective, draft=payload, generated_at=generated_at)
        request = build_exact_send_authority_request(
            objective_id=obj_id,
            draft=payload,
            operator_text=text,
            approved_draft_artifact_ref=str(artifact.get("artifact_id") or ""),
            generated_at=generated_at,
        )
        objective["send_authority_request"] = request

        _store_objective(conn, objective)
        _store_event(
            conn,
            objective_id=obj_id,
            channel=source_channel,
            message_ref=source_message_ref,
            decision="draft_approved_send_authority_prepared",
            status_transition=STATUS_WAITING_SEND_AUTHORITY,
            receipt_ref=str(request.get("request_id") or ""),
            generated_at=generated_at,
        )
        conn.commit()

    proof = dict(AUTHORITY_BOUNDARY)
    proof.update({
        "email_send_performed": False,
        "gmail_draft_created": False,
        "scheduled_send_created": False,
        "calendar_api_called": False,
        "contacts_api_called": False,
        "broad_broker_ambient_use": False,
    })

    return {
        "schema_version": "CASSANDRA_OPERATOR_OBJECTIVE_ROUTE_V0",
        "recognized": True,
        "response_status": "CASSANDRA_OBJECTIVE_DRAFT_APPROVED_PREPARE_SEND_AUTHORITY",
        "operator_reply": f"I prepared the send authority request for {payload['recipient']}. Nothing has been sent. Next: approve the exact send request.",
        "send_authority_request": request,
        "objective": objective,
        "machine_proof": proof,
    }


def route_cassandra_objective_message(
    text: str,
    *,
    source_channel: str,
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    ar_sqlite_path: Path | str = ar_ops.DEFAULT_SQLITE_PATH,
    mac_bridge_sqlite_path: Path | str = mac_local_action_bridge.DEFAULT_SQLITE_PATH,
    mac_request_queue: Path | str = mac_local_action_bridge.DEFAULT_REQUEST_QUEUE,
    mac_result_queue: Path | str = mac_local_action_bridge.DEFAULT_RESULT_QUEUE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if source_channel == "telegram" and mac_local_action_bridge.detects_apple_mail_local_request(text):
        return route_mac_local_action_objective_message(
            text,
            source_channel=source_channel,
            source_message_ref=source_message_ref,
            lane_context=lane_context,
            sqlite_path=sqlite_path,
            mac_bridge_sqlite_path=mac_bridge_sqlite_path,
            mac_request_queue=mac_request_queue,
            mac_result_queue=mac_result_queue,
            generated_at=generated_at,
        )
    if detects_draft_approval_send_authority(text):
        return route_draft_approval_to_send_authority(
            text,
            source_channel=source_channel,
            source_message_ref=source_message_ref,
            lane_context=lane_context,
            sqlite_path=sqlite_path,
            generated_at=generated_at,
        )
    if detects_make_it_so_email_objective(text):
        objective = build_cassandra_operator_objective(
            text,
            source_channel=source_channel,
            source_message_ref=source_message_ref,
            lane_context=lane_context,
            generated_at=generated_at,
        )
        _persist_objective(objective, sqlite_path, generated_at=generated_at, decision="objective_created_waiting_for_lookup_authority")
        return {
            "schema_version": "CASSANDRA_OPERATOR_OBJECTIVE_ROUTE_V0",
            "recognized": True,
            "response_status": "CASSANDRA_OBJECTIVE_WAITING_FOR_LOOKUP_AUTHORITY",
            "operator_reply": _operator_reply(),
            "next_safe_step": objective["safe_next_step"],
            "objective": objective,
            "authority_request": objective["lookup_authority_request"],
            "machine_proof": dict(AUTHORITY_BOUNDARY),
        }
    if detects_ar_counterparty_objective(text):
        return route_ar_counterparty_objective_message(
            text,
            source_channel=source_channel,
            source_message_ref=source_message_ref,
            lane_context=lane_context,
            sqlite_path=sqlite_path,
            ar_sqlite_path=ar_sqlite_path,
            generated_at=generated_at,
        )
    return {
        "schema_version": "CASSANDRA_OPERATOR_OBJECTIVE_ROUTE_V0",
        "recognized": False,
        "response_status": "NOT_CASSANDRA_OPERATOR_OBJECTIVE",
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }


def record_lookup_authority_approval(
    objective_id: str,
    *,
    authority_envelope: Mapping[str, Any],
    credential_lease: Mapping[str, Any],
    credential_handle: Mapping[str, Any],
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    with _connect(sqlite_path) as conn:
        objective = _load_objective(conn, objective_id)
        verdict = custody.verify_google_workspace_broker_readonly_lease(
            credential_lease,
            credential_handle=credential_handle,
            authority_envelope=authority_envelope,
        )
        if verdict["valid"]:
            objective["objective_status"] = STATUS_LOOKUP_READY
            objective["safe_next_step"] = "Run scoped metadata lookup only under the approved broker lease."
            objective["authority_refs"] = _dedupe([*objective.get("authority_refs", []), str(authority_envelope.get("envelope_id") or "")])
            objective["credential_lease_refs"] = _dedupe([*objective.get("credential_lease_refs", []), str(credential_lease.get("lease_id") or "")])
            status_transition = STATUS_LOOKUP_READY
        else:
            objective["objective_status"] = STATUS_BLOCKED
            objective["safe_next_step"] = "Review the scoped metadata lookup lease."
            status_transition = STATUS_BLOCKED
        objective["updated_at"] = generated_at
        _store_objective(conn, objective)
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_authority_refs
              (objective_id, authority_ref, authority_kind, status, ref_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                objective_id,
                str(authority_envelope.get("envelope_id") or ""),
                custody.AUTHORITY_ENVELOPE_SCHEMA,
                str(authority_envelope.get("status") or ""),
                stable_json(authority_envelope),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_credential_leases
              (objective_id, credential_lease_ref, credential_handle_id, capability_id, status, lease_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                objective_id,
                str(credential_lease.get("lease_id") or ""),
                str(credential_lease.get("credential_handle_id") or ""),
                str(credential_lease.get("capability_id") or ""),
                str(credential_lease.get("status") or ""),
                stable_json(credential_lease),
            ),
        )
        _store_event(
            conn,
            objective_id=objective_id,
            channel="authority_system",
            message_ref=str(authority_envelope.get("confirmation_receipt_ref") or ""),
            decision="lookup_authority_and_lease_verified" if verdict["valid"] else "lookup_authority_or_lease_blocked",
            status_transition=status_transition,
            receipt_ref=str(verdict.get("schema_version") or ""),
            generated_at=generated_at,
        )
        conn.commit()
    return {
        "schema_version": "CASSANDRA_LOOKUP_AUTHORITY_CONTINUATION_V0",
        "response_status": "LOOKUP_READY" if verdict["valid"] else "LOOKUP_BLOCKED",
        "objective": objective,
        "lease_verdict": verdict,
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }


def _payload_hash(*, recipient: str, subject: str, body: str) -> str:
    return "sha256:" + hashlib.sha256(stable_json({"body": body, "recipient": recipient, "subject": subject}).encode("utf-8")).hexdigest()


def build_text_followup_draft(
    *,
    objective_id: str,
    counterparty: str,
    organization: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    recipient = f"{counterparty} at {organization}"
    subject = f"Following up on {organization}"
    body = (
        f"Hi {counterparty},\n\n"
        f"I wanted to follow up on the {organization} payment status and see whether there is any update you can share.\n\n"
        "Best,\n"
        "Winship"
    )
    return {
        "schema_version": TEXT_FOLLOWUP_DRAFT_SCHEMA,
        "draft_id": "text_followup_draft:" + _short_hash(objective_id, recipient, subject, body),
        "objective_id": objective_id,
        "draft_medium": "text_only_review",
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "payload_hash": _payload_hash(recipient=recipient, subject=subject, body=body),
        "gmail_draft_created": False,
        "email_send_performed": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def record_lookup_receipt(
    objective_id: str,
    *,
    lookup_receipt: Mapping[str, Any],
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    with _connect(sqlite_path) as conn:
        objective = _load_objective(conn, objective_id)
        count = int(lookup_receipt.get("matching_message_count") or 0)
        no_match = str(lookup_receipt.get("result") or "").lower() == "no_match" or count == 0
        receipt_ref = str(lookup_receipt.get("receipt_id") or f"lookup_receipt:{_short_hash(objective_id, generated_at)}")
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_receipts
              (objective_id, receipt_ref, receipt_kind, status, receipt_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (objective_id, receipt_ref, "gmail_metadata_lookup", str(lookup_receipt.get("result") or ""), stable_json(dict(lookup_receipt))),
        )
        objective["receipts"] = _dedupe([*objective.get("receipts", []), receipt_ref])
        if no_match:
            draft = build_text_followup_draft(
                objective_id=objective_id,
                counterparty=str(objective.get("client_or_counterparty") or "there"),
                organization=str((objective.get("lane_context") or {}).get("organization") or "the account"),
                generated_at=generated_at,
            )
            objective["objective_status"] = STATUS_DRAFT_READY_FOR_REVIEW
            objective["current_step"] = "operator_draft_review"
            objective["safe_next_step"] = "Review the text-only follow-up draft."
            objective["text_followup_draft"] = draft
            response_status = "TEXT_DRAFT_READY_FOR_REVIEW"
            decision = "no_match_receipt_created_text_draft"
        else:
            draft = {}
            objective["objective_status"] = STATUS_LOOKUP_COMPLETE
            objective["current_step"] = "scoped_email_metadata_lookup"
            objective["safe_next_step"] = "Review metadata evidence and decide whether body-read authority is needed."
            response_status = "LOOKUP_METADATA_MATCH_FOUND"
            decision = "matching_metadata_receipt_recorded"
        objective["updated_at"] = generated_at
        _store_objective(conn, objective)
        _store_event(
            conn,
            objective_id=objective_id,
            channel="google_workspace_broker_receipt",
            message_ref=receipt_ref,
            decision=decision,
            status_transition=str(objective["objective_status"]),
            receipt_ref=receipt_ref,
            generated_at=generated_at,
        )
        conn.commit()
    return {
        "schema_version": "CASSANDRA_LOOKUP_RECEIPT_CONTINUATION_V0",
        "response_status": response_status,
        "objective": objective,
        "text_followup_draft": draft,
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }


def record_mac_local_action_result(
    objective_id: str,
    *,
    mac_result: Mapping[str, Any],
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    mac_bridge_sqlite_path: Path | str = mac_local_action_bridge.DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if mac_result.get("schema_version") != mac_local_action_bridge.MAC_LOCAL_ACTION_RESULT_SCHEMA:
        raise ValueError("MAC_LOCAL_ACTION_RESULT_V0 is required")
    with _connect(sqlite_path) as conn:
        objective = _load_objective(conn, objective_id)
        request = objective.get("mac_local_action_request") if isinstance(objective.get("mac_local_action_request"), Mapping) else {}
        bridge_record = mac_local_action_bridge.record_mac_local_action_result(
            mac_result,
            sqlite_path=mac_bridge_sqlite_path,
            request=request,
            generated_at=generated_at,
        )
        receipt_ref = str(mac_result.get("receipt_ref") or f"mac_local_action_receipt:{_short_hash(objective_id, generated_at)}")
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_receipts
              (objective_id, receipt_ref, receipt_kind, status, receipt_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (objective_id, receipt_ref, "mac_local_action_result", str(mac_result.get("status") or ""), stable_json(dict(mac_result))),
        )
        objective["receipts"] = _dedupe([*objective.get("receipts", []), receipt_ref])
        if bridge_record.get("response_status") == "MAC_LOCAL_ACTION_RESULT_RECORDED":
            objective["objective_status"] = STATUS_MAC_LOCAL_ACTION_COMPLETE
            objective["current_step"] = "mac_local_action_result"
            objective["safe_next_step"] = str(mac_result.get("next_safe_step") or "Review the Mac-local action result.")
            decision = "mac_local_action_result_recorded"
        else:
            objective["objective_status"] = STATUS_BLOCKED
            objective["safe_next_step"] = "Review the Mac-local action result verifier errors."
            decision = "mac_local_action_result_rejected"
        objective["mac_local_action_result"] = dict(mac_result)
        objective["updated_at"] = generated_at
        _store_objective(conn, objective)
        _store_event(
            conn,
            objective_id=objective_id,
            channel="mac_local_action_bridge",
            message_ref=str(mac_result.get("request_id") or ""),
            decision=decision,
            status_transition=str(objective["objective_status"]),
            receipt_ref=receipt_ref,
            generated_at=generated_at,
        )
        conn.commit()
    return {
        "schema_version": "CASSANDRA_MAC_LOCAL_ACTION_RESULT_CONTINUATION_V0",
        "response_status": "MAC_LOCAL_ACTION_RESULT_ACCEPTED" if objective["objective_status"] == STATUS_MAC_LOCAL_ACTION_COMPLETE else "MAC_LOCAL_ACTION_RESULT_BLOCKED",
        "objective": objective,
        "bridge_record": bridge_record,
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }


def _mac_local_result_machine_proof() -> dict[str, Any]:
    proof = dict(AUTHORITY_BOUNDARY)
    proof.update(
        {
            "apple_mail_called": False,
            "apple_mail_automation_invoked": False,
            "mailbox_mutation_allowed": False,
            "mailbox_mutation_performed": False,
            "mail_body_read_allowed": False,
            "mail_body_read_performed": False,
            "mail_draft_create_allowed": False,
            "mail_draft_created": False,
            "mail_send_allowed": False,
            "email_send_performed": False,
        }
    )
    return proof


def ingest_mac_local_action_result_file(
    result_path: Path | str,
    *,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    mac_bridge_sqlite_path: Path | str = mac_local_action_bridge.DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    path = Path(result_path)
    if not path.exists():
        bridge_record = mac_local_action_bridge.ingest_mac_local_action_result_file(
            path,
            sqlite_path=mac_bridge_sqlite_path,
            generated_at=generated_at,
        )
        return {
            "schema_version": "CASSANDRA_MAC_LOCAL_ACTION_RESULT_FILE_INGESTION_V0",
            "response_status": "MAC_LOCAL_ACTION_RESULT_FILE_MISSING",
            "result_file_found": False,
            "result_path": path.as_posix(),
            "objective_updated": False,
            "orphan_result": True,
            "bridge_record": bridge_record,
            "operator_reply": "Mac local action result file was not found.",
            "next_safe_step": "Wait for the Mac-local action result.",
            "machine_proof": _mac_local_result_machine_proof(),
        }

    result = mac_local_action_bridge.load_mac_local_action_result_file(path)
    objective_id = str(result.get("objective_id") or "")
    with _connect(sqlite_path) as conn:
        objective = _maybe_load_objective(conn, objective_id) if objective_id else None

    request = objective.get("mac_local_action_request") if isinstance(objective, Mapping) and isinstance(objective.get("mac_local_action_request"), Mapping) else None
    bridge_record = mac_local_action_bridge.ingest_mac_local_action_result_file(
        path,
        sqlite_path=mac_bridge_sqlite_path,
        request=request,
        generated_at=generated_at,
    )
    result_status = str(result.get("status") or "")
    receipt_ref = str(result.get("receipt_ref") or f"mac_local_action_receipt:{_short_hash(objective_id, generated_at)}")
    is_shadow = result_status in mac_local_action_bridge.SAFE_SHADOW_RESULT_STATUSES
    proof = _mac_local_result_machine_proof()

    if not objective:
        response_status = (
            "MAC_LOCAL_ACTION_ORPHAN_SHADOW_RESULT_RECORDED"
            if bridge_record.get("response_status") == "MAC_LOCAL_ACTION_RESULT_RECORDED" and is_shadow
            else str(bridge_record.get("response_status") or "MAC_LOCAL_ACTION_RESULT_BLOCKED")
        )
        return {
            "schema_version": "CASSANDRA_MAC_LOCAL_ACTION_RESULT_FILE_INGESTION_V0",
            "response_status": response_status,
            "result_file_found": True,
            "result_path": path.as_posix(),
            "request_id": str(result.get("request_id") or ""),
            "objective_id": objective_id,
            "result_status": result_status,
            "mutation_performed": bool(result.get("mutation_performed") is True),
            "raw_body_exposed": bool(result.get("raw_body_exposed") is True),
            "denied_actions_confirmed": list(result.get("denied_actions_confirmed") or []),
            "persisted_to_sqlite": bridge_record.get("response_status") == "MAC_LOCAL_ACTION_RESULT_RECORDED",
            "objective_updated": False,
            "orphan_result": True,
            "bridge_record": bridge_record,
            "operator_reply": MAC_LOCAL_SHADOW_RESULT_OPERATOR_ANSWER if is_shadow else "Mac local action result was recorded without an attached objective.",
            "next_safe_step": MAC_LOCAL_SHADOW_RESULT_NEXT_SAFE_STEP if is_shadow else "Attach the Mac-local action result to an objective if needed.",
            "machine_proof": proof,
        }

    with _connect(sqlite_path) as conn:
        current = _load_objective(conn, objective_id)
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_receipts
              (objective_id, receipt_ref, receipt_kind, status, receipt_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (objective_id, receipt_ref, "mac_local_action_result", result_status, stable_json(result)),
        )
        current["receipts"] = _dedupe([*current.get("receipts", []), receipt_ref])
        current["mac_local_action_result"] = result
        current["updated_at"] = generated_at
        if bridge_record.get("response_status") != "MAC_LOCAL_ACTION_RESULT_RECORDED":
            current["objective_status"] = STATUS_BLOCKED
            current["safe_next_step"] = "Review the Mac-local action result verifier errors."
            decision = "mac_local_action_result_rejected"
            response_status = "MAC_LOCAL_ACTION_RESULT_BLOCKED"
        elif is_shadow:
            current["objective_status"] = STATUS_WAITING_MAC_LOCAL_ACTION_RESULT
            current["current_step"] = "mac_local_action_result"
            current["safe_next_step"] = MAC_LOCAL_SHADOW_RESULT_NEXT_SAFE_STEP
            decision = "mac_local_action_shadow_result_recorded"
            response_status = "MAC_LOCAL_ACTION_SHADOW_RESULT_RECORDED"
        else:
            current["objective_status"] = STATUS_MAC_LOCAL_ACTION_COMPLETE
            current["current_step"] = "mac_local_action_result"
            current["safe_next_step"] = str(result.get("next_safe_step") or "Review the Mac-local action result.")
            decision = "mac_local_action_result_recorded"
            response_status = "MAC_LOCAL_ACTION_RESULT_ACCEPTED"
        _store_objective(conn, current)
        _store_event(
            conn,
            objective_id=objective_id,
            channel="mac_local_action_bridge",
            message_ref=str(result.get("request_id") or ""),
            decision=decision,
            status_transition=str(current["objective_status"]),
            receipt_ref=receipt_ref,
            generated_at=_next_timestamp(generated_at),
        )
        conn.commit()

    return {
        "schema_version": "CASSANDRA_MAC_LOCAL_ACTION_RESULT_FILE_INGESTION_V0",
        "response_status": response_status,
        "result_file_found": True,
        "result_path": path.as_posix(),
        "request_id": str(result.get("request_id") or ""),
        "objective_id": objective_id,
        "result_status": result_status,
        "mutation_performed": bool(result.get("mutation_performed") is True),
        "raw_body_exposed": bool(result.get("raw_body_exposed") is True),
        "denied_actions_confirmed": list(result.get("denied_actions_confirmed") or []),
        "persisted_to_sqlite": bridge_record.get("response_status") == "MAC_LOCAL_ACTION_RESULT_RECORDED",
        "objective_updated": response_status != "MAC_LOCAL_ACTION_RESULT_BLOCKED",
        "orphan_result": False,
        "objective": current,
        "bridge_record": bridge_record,
        "operator_reply": MAC_LOCAL_SHADOW_RESULT_OPERATOR_ANSWER if is_shadow else "Cassandra received the Mac local action result.",
        "next_safe_step": str(current.get("safe_next_step") or ""),
        "machine_proof": proof,
    }


def _load_draft(conn: sqlite3.Connection, objective_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    objective = _load_objective(conn, objective_id)
    draft = objective.get("text_followup_draft") if isinstance(objective.get("text_followup_draft"), Mapping) else {}
    if not draft:
        raise ValueError("text follow-up draft is required before send review")
    return objective, dict(draft)


def build_approved_send_draft_artifact(
    *,
    objective_id: str,
    draft: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    recipient = str(draft.get("recipient") or "")
    subject = str(draft.get("subject") or "")
    body = str(draft.get("body") or "")
    payload_hash = _payload_hash(recipient=recipient, subject=subject, body=body)
    return {
        "schema_version": APPROVED_SEND_DRAFT_ARTIFACT_SCHEMA,
        "artifact_id": "approved_send_draft_artifact:" + _short_hash(objective_id, recipient, subject, payload_hash, generated_at),
        "objective_id": objective_id,
        "draft_medium": "approved_text_only",
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "payload_hash": payload_hash,
        "body_hash": payload_hash,
        "created_at": generated_at,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def store_approved_send_draft_artifact(
    objective: dict[str, Any],
    *,
    draft: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    artifact = build_approved_send_draft_artifact(
        objective_id=str(objective.get("objective_id") or ""),
        draft=draft,
        generated_at=generated_at,
    )
    artifacts = objective.get("approved_send_draft_artifacts") if isinstance(objective.get("approved_send_draft_artifacts"), Mapping) else {}
    updated = dict(artifacts)
    updated[str(artifact["artifact_id"])] = artifact
    objective["approved_send_draft_artifacts"] = updated
    objective["approved_send_draft_artifact"] = artifact
    return artifact


def build_unattended_requirement(
    *,
    objective_id: str,
    operator_text: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    lowered = str(operator_text or "").lower()
    required = "tomorrow" in lowered or "later" in lowered or "schedule" in lowered
    send_window = {"relative_request": "tomorrow"} if "tomorrow" in lowered else {"relative_request": "later" if required else ""}
    try:
        base = datetime.fromisoformat(generated_at)
        if "tomorrow" in lowered:
            send_window["not_before_date"] = (base + timedelta(days=1)).date().isoformat()
    except ValueError:
        pass
    return {
        "schema_version": UNATTENDED_REQUIREMENT_SCHEMA,
        "objective_id": objective_id,
        "required": required,
        "required_schema_version": custody.UNATTENDED_RUN_ENVELOPE_SCHEMA,
        "send_window": send_window,
        "interrupt_conditions": list(INTERRUPT_CONDITIONS),
        "scheduled_send_created": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_exact_send_authority_request(
    *,
    objective_id: str,
    draft: Mapping[str, Any],
    operator_text: str,
    approved_draft_artifact_ref: str = "",
    expires_at: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    expires_at = expires_at or _default_exact_send_expires_at(generated_at)
    unattended = build_unattended_requirement(objective_id=objective_id, operator_text=operator_text, generated_at=generated_at)
    return {
        "schema_version": EXACT_SEND_AUTHORITY_REQUEST_SCHEMA,
        "request_id": "exact_send_authority_request:" + _short_hash(objective_id, draft.get("payload_hash"), operator_text, generated_at),
        "objective_id": objective_id,
        "capability_id": GMAIL_SEND_MAIL,
        "recipient": str(draft.get("recipient") or ""),
        "subject": str(draft.get("subject") or ""),
        "body_hash": _payload_hash(
            recipient=str(draft.get("recipient") or ""),
            subject=str(draft.get("subject") or ""),
            body=str(draft.get("body") or ""),
        ),
        "payload_hash": str(draft.get("payload_hash") or ""),
        "approved_draft_artifact_ref": str(approved_draft_artifact_ref or ""),
        "expires_at": expires_at,
        "one_time_only": True,
        "scheduled_send_requested": unattended["required"],
        "unattended_run_envelope_required": unattended["required"],
        "required_unattended_schema": custody.UNATTENDED_RUN_ENVELOPE_SCHEMA if unattended["required"] else "",
        "send_window": unattended["send_window"],
        "denied_actions": [
            "other_recipients",
            "attachments",
            "calendar_access",
            "contacts_read",
            "mark_paid",
            "mutate_ledger",
            "coupa_submit",
        ],
        "created_at": generated_at,
        "raw_authority_granted_trusted": False,
        "execution_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def verify_exact_payload_authority(authority_request: Mapping[str, Any], *, draft: Mapping[str, Any]) -> dict[str, Any]:
    expected = str(authority_request.get("payload_hash") or "")
    observed = _payload_hash(
        recipient=str(draft.get("recipient") or ""),
        subject=str(draft.get("subject") or ""),
        body=str(draft.get("body") or ""),
    )
    errors = []
    if not expected or expected != observed:
        errors.append("payload_hash_mismatch")
    return {
        "schema_version": "EXACT_PAYLOAD_AUTHORITY_VERDICT_V0",
        "valid": not errors,
        "validation_errors": errors,
        "expected_payload_hash": expected,
        "observed_payload_hash": observed,
        "email_send_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_exact_send_review_packet(
    authority_request: Mapping[str, Any],
    *,
    draft: Mapping[str, Any],
    expires_at: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if expires_at is None:
        expires_at = str(authority_request.get("expires_at") or "")
    if not expires_at:
        expires_at = _default_exact_send_expires_at(generated_at)
    observed_hash = _payload_hash(
        recipient=str(draft.get("recipient") or ""),
        subject=str(draft.get("subject") or ""),
        body=str(draft.get("body") or ""),
    )
    packet = {
        "schema_version": EXACT_SEND_REVIEW_PACKET_SCHEMA,
        "packet_id": "exact_send_review_packet:" + _short_hash(authority_request.get("request_id"), observed_hash, expires_at),
        "request_id": str(authority_request.get("request_id") or ""),
        "objective_id": str(authority_request.get("objective_id") or ""),
        "recipient": str(authority_request.get("recipient") or draft.get("recipient") or ""),
        "subject": str(authority_request.get("subject") or draft.get("subject") or ""),
        "body": str(draft.get("body") or ""),
        "payload_hash": str(authority_request.get("payload_hash") or ""),
        "observed_payload_hash": observed_hash,
        "body_hash": str(authority_request.get("body_hash") or ""),
        "approved_draft_artifact_ref": str(authority_request.get("approved_draft_artifact_ref") or ""),
        "expires_at": expires_at,
        "approval_phrase": f"Approve exact send request {authority_request.get('request_id')}",
        "refusal_options": [
            "refuse_wrong_request_id",
            "refuse_payload_hash_mismatch",
            "refuse_supplied_hash_divergence",
            "refuse_expired_request",
            "refuse_ambiguous_approval",
            "refuse_replay_or_double_send",
            "refuse_live_transport",
        ],
        "review_only": True,
        "execution_performed": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return packet


def _extract_request_ids(text: str) -> list[str]:
    ids: list[str] = []
    for match in re.finditer(r"exact_send_authority_request:[A-Za-z0-9_.:-]+", str(text or "")):
        ids.append(match.group(0).rstrip(".,;:!?)]}"))
    return ids


def _extract_supplied_payload_hash(text: str) -> str:
    match = re.search(r"(?:payload[_ -]?hash|hash)\s*[:=]\s*(sha256:[0-9a-fA-F]{64})", str(text or ""))
    return match.group(1).lower() if match else ""


def parse_exact_send_approval(
    text: str,
    review_packet: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    consumed_request_ids: Sequence[str] = (),
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    expected_id = str(review_packet.get("request_id") or "")
    lowered = str(text or "").lower()
    exact_phrase_present = any(
        phrase in lowered
        for phrase in (
            "approve exact send request",
            "approved exact send request",
            "approve exact send",
            "approved exact send",
        )
    )
    request_ids = _extract_request_ids(text)
    supplied_hash = _extract_supplied_payload_hash(text)
    reason = ""
    approved = True

    if not exact_phrase_present or not request_ids:
        approved = False
        reason = "ambiguous_approval"
    elif len(set(request_ids)) != 1:
        approved = False
        reason = "ambiguous_approval"
    elif request_ids[0] != expected_id:
        approved = False
        reason = "wrong_request_id"
    elif _timestamp_expired(str(review_packet.get("expires_at") or ""), generated_at=generated_at):
        approved = False
        reason = "expired_request"
    elif expected_id in {str(item) for item in consumed_request_ids}:
        approved = False
        reason = "replay_detected"

    if approved:
        reason = "approved"

    return {
        "schema_version": EXACT_SEND_APPROVAL_DECISION_SCHEMA,
        "approved": approved,
        "reason": reason,
        "request_id": request_ids[0] if request_ids else "",
        "expected_request_id": expected_id,
        "objective_id": str(review_packet.get("objective_id") or ""),
        "review_packet_id": str(review_packet.get("packet_id") or ""),
        "payload_hash": str(review_packet.get("payload_hash") or ""),
        "supplied_payload_hash": supplied_hash,
        "expires_at": str(review_packet.get("expires_at") or ""),
        "created_at": generated_at,
        "raw_authority_granted_trusted": False,
        "execution_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _stored_approved_send_draft_artifact(objective: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    artifact_ref = str(request.get("approved_draft_artifact_ref") or "")
    artifacts = objective.get("approved_send_draft_artifacts") if isinstance(objective.get("approved_send_draft_artifacts"), Mapping) else {}
    artifact = artifacts.get(artifact_ref) if artifact_ref else None
    if not artifact and isinstance(objective.get("approved_send_draft_artifact"), Mapping):
        latest = objective.get("approved_send_draft_artifact")
        if not artifact_ref or str(latest.get("artifact_id") or "") == artifact_ref:
            artifact = latest
    return dict(artifact or {})


def _load_exact_send_execution_state(
    conn: sqlite3.Connection,
    *,
    objective_id: str,
    approval_decision: Mapping[str, Any],
    generated_at: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    objective = _maybe_load_objective(conn, objective_id)
    request_id = str(approval_decision.get("expected_request_id") or approval_decision.get("request_id") or "")
    if not objective:
        return None, {"reason": "wrong_objective_id", "request_id": request_id, "objective_id": objective_id}
    decision_objective_id = str(approval_decision.get("objective_id") or "")
    if decision_objective_id and decision_objective_id != objective_id:
        return None, {"reason": "wrong_objective_id", "request_id": request_id, "objective_id": objective_id}
    request = objective.get("send_authority_request") if isinstance(objective.get("send_authority_request"), Mapping) else {}
    if str(request.get("objective_id") or "") != objective_id:
        return None, {"reason": "wrong_objective_id", "request_id": request_id, "objective_id": objective_id}
    stored_request_id = str(request.get("request_id") or "")
    if request_id != stored_request_id:
        return None, {
            "reason": "wrong_request_id",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(request.get("recipient") or ""),
            "subject": str(request.get("subject") or ""),
            "expected_payload_hash": str(request.get("payload_hash") or ""),
        }
    expires_at = str(request.get("expires_at") or "")
    if not _parse_timestamp(expires_at):
        return None, {
            "reason": "missing_or_invalid_expiry",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(request.get("recipient") or ""),
            "subject": str(request.get("subject") or ""),
            "expected_payload_hash": str(request.get("payload_hash") or ""),
        }
    if _timestamp_expired(expires_at, generated_at=generated_at):
        return None, {
            "reason": "expired_request",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(request.get("recipient") or ""),
            "subject": str(request.get("subject") or ""),
            "expected_payload_hash": str(request.get("payload_hash") or ""),
        }
    artifact = _stored_approved_send_draft_artifact(objective, request)
    if not artifact:
        return None, {
            "reason": "stored_draft_missing",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(request.get("recipient") or ""),
            "subject": str(request.get("subject") or ""),
            "expected_payload_hash": str(request.get("payload_hash") or ""),
        }
    recipient = str(artifact.get("recipient") or "")
    subject = str(artifact.get("subject") or "")
    body = str(artifact.get("body") or "")
    if not recipient or not subject or not body:
        return None, {
            "reason": "stored_draft_body_missing",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": recipient or str(request.get("recipient") or ""),
            "subject": subject or str(request.get("subject") or ""),
            "expected_payload_hash": str(request.get("payload_hash") or ""),
        }
    observed_hash = _payload_hash(recipient=recipient, subject=subject, body=body)
    expected_hash = str(request.get("payload_hash") or "")
    supplied_hash = str(approval_decision.get("supplied_payload_hash") or "")
    if supplied_hash and supplied_hash != expected_hash:
        return None, {
            "reason": "supplied_hash_mismatch",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(request.get("recipient") or recipient),
            "subject": str(request.get("subject") or subject),
            "expected_payload_hash": expected_hash,
            "observed_payload_hash": observed_hash,
            "supplied_payload_hash": supplied_hash,
        }
    if expected_hash != observed_hash:
        return None, {
            "reason": "payload_hash_mismatch",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(request.get("recipient") or recipient),
            "subject": str(request.get("subject") or subject),
            "expected_payload_hash": expected_hash,
            "observed_payload_hash": observed_hash,
            "supplied_payload_hash": supplied_hash,
        }
    state = {
        "objective": objective,
        "request": dict(request),
        "draft_artifact": artifact,
        "request_id": request_id,
        "objective_id": objective_id,
        "recipient": str(request.get("recipient") or recipient),
        "subject": str(request.get("subject") or subject),
        "body": body,
        "payload_hash": expected_hash,
        "observed_payload_hash": observed_hash,
        "expires_at": expires_at,
        "authority_refs": list(objective.get("authority_refs") or []),
        "credential_lease_refs": list(objective.get("credential_lease_refs") or []),
    }
    return state, None


def _ensure_exact_send_fixture_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exact_send_fixture_executions (
          request_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        )
        """
    )


def _write_exact_send_receipt(receipt_dir: Path | str, prefix: str, receipt: Mapping[str, Any]) -> Path:
    path = Path(receipt_dir)
    path.mkdir(parents=True, exist_ok=True)
    receipt_id = str(receipt.get("receipt_id") or _short_hash(receipt))
    receipt_path = path / f"{prefix}_{receipt_id.replace(':', '_')}.json"
    receipt_path.write_text(stable_json(dict(receipt)), encoding="utf-8")
    return receipt_path


def _exact_send_refusal_receipt(
    *,
    reason: str,
    request_id: str,
    objective_id: str,
    generated_at: str,
    schema_version: str = EXACT_SEND_REFUSAL_RECEIPT_SCHEMA,
    response_status: str = "EXACT_SEND_DRY_RUN_REFUSED",
    recipient: str = "",
    subject: str = "",
    expected_payload_hash: str = "",
    observed_payload_hash: str = "",
    supplied_payload_hash: str = "",
    authority_refs: Sequence[str] = (),
    credential_lease_refs: Sequence[str] = (),
    transport_mode: str = "fixture_dry_run",
    live_transport_constructed: bool = False,
    live_transport_enabled: bool = False,
    broker_agent: str = "",
    broker_capability: str = "",
    broker_called: bool = False,
    fake_broker_called: bool = False,
) -> dict[str, Any]:
    receipt = {
        "schema_version": schema_version,
        "receipt_id": "exact_send_refusal_receipt:" + _short_hash(reason, request_id, generated_at),
        "response_status": response_status,
        "reason": reason,
        "request_id": request_id,
        "objective_id": objective_id,
        "recipient": recipient,
        "subject": subject,
        "expected_payload_hash": expected_payload_hash,
        "observed_payload_hash": observed_payload_hash,
        "supplied_payload_hash": supplied_payload_hash,
        "authority_refs": list(authority_refs),
        "credential_lease_refs": list(credential_lease_refs),
        "transport_mode": transport_mode,
        "broker_agent": broker_agent,
        "broker_capability": broker_capability,
        "broker_called": broker_called,
        "fake_broker_called": fake_broker_called,
        "live_transport_enabled": live_transport_enabled,
        "execution_performed": False,
        "dry_run_transport_called": False,
        "live_transport_constructed": live_transport_constructed,
        "gmail_api_called": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "calendar_api_called": False,
        "contacts_api_called": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return receipt


def run_exact_send_dry_run_executor(
    *,
    sqlite_path: Path | str,
    objective_id: str,
    approval_decision: Mapping[str, Any],
    draft: Mapping[str, Any] | None = None,
    receipt_dir: Path | str,
    transport: Any = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request_id = str(approval_decision.get("expected_request_id") or approval_decision.get("request_id") or "")

    def refuse(
        reason: str,
        *,
        objective_ref: str = "",
        recipient: str = "",
        subject: str = "",
        expected: str = "",
        observed: str = "",
        supplied: str = "",
        authority_refs: Sequence[str] = (),
        credential_lease_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        receipt = _exact_send_refusal_receipt(
            reason=reason,
            request_id=request_id,
            objective_id=objective_ref or objective_id,
            generated_at=generated_at,
            recipient=recipient,
            subject=subject,
            expected_payload_hash=expected,
            observed_payload_hash=observed,
            supplied_payload_hash=supplied,
            authority_refs=authority_refs,
            credential_lease_refs=credential_lease_refs,
        )
        receipt_path = _write_exact_send_receipt(receipt_dir, "exact_send_refusal_receipt", receipt)
        return {
            "schema_version": "EXACT_SEND_DRY_RUN_EXECUTOR_RESULT_V0",
            "response_status": "EXACT_SEND_DRY_RUN_REFUSED",
            "refusal_reason": reason,
            "receipt": receipt,
            "refusal_receipt_path": receipt_path.as_posix(),
            "execution_performed": False,
            "machine_proof": dict(AUTHORITY_BOUNDARY),
        }

    if _is_live_objective_db(sqlite_path):
        return refuse("live_objective_db_refused")
    if not approval_decision.get("approved"):
        return refuse(str(approval_decision.get("reason") or "approval_not_valid"))
    if transport is None:
        return refuse("dry_run_transport_required")
    if getattr(transport, "live_transport", False) is True:
        return refuse("live_transport_refused")
    record_dry_run = getattr(transport, "record_dry_run", None)
    dry_run_send = getattr(transport, "dry_run_send", None)
    if not callable(record_dry_run) and not callable(dry_run_send):
        return refuse("dry_run_transport_required")

    with _connect(sqlite_path) as conn:
        _ensure_exact_send_fixture_tables(conn)
        state, error = _load_exact_send_execution_state(
            conn,
            objective_id=objective_id,
            approval_decision=approval_decision,
            generated_at=generated_at,
        )
        if error:
            return refuse(
                str(error.get("reason") or "stored_request_invalid"),
                objective_ref=str(error.get("objective_id") or objective_id),
                recipient=str(error.get("recipient") or ""),
                subject=str(error.get("subject") or ""),
                expected=str(error.get("expected_payload_hash") or ""),
                observed=str(error.get("observed_payload_hash") or ""),
                supplied=str(error.get("supplied_payload_hash") or ""),
            )
        assert state is not None
        replay = conn.execute(
            "SELECT request_id FROM exact_send_fixture_executions WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if replay:
            return refuse(
                "replay_detected",
                objective_ref=str(state.get("objective_id") or ""),
                recipient=str(state.get("recipient") or ""),
                subject=str(state.get("subject") or ""),
                expected=str(state.get("payload_hash") or ""),
                observed=str(state.get("observed_payload_hash") or ""),
                authority_refs=list(state.get("authority_refs") or []),
                credential_lease_refs=list(state.get("credential_lease_refs") or []),
            )

        dry_run_payload = {
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(state.get("recipient") or ""),
            "subject": str(state.get("subject") or ""),
            "body": str(state.get("body") or ""),
            "payload_hash": str(state.get("payload_hash") or ""),
            "expires_at": str(state.get("expires_at") or ""),
            "caller_draft_ignored": draft is not None,
        }
        if callable(record_dry_run):
            transport_result = record_dry_run(dict(dry_run_payload))
        else:
            transport_result = dry_run_send(dict(dry_run_payload))

        receipt = {
            "schema_version": EXACT_SEND_DRY_RUN_RECEIPT_SCHEMA,
            "receipt_id": "exact_send_dry_run_receipt:" + _short_hash(request_id, state.get("payload_hash"), generated_at),
            "response_status": "EXACT_SEND_DRY_RUN_RECEIPT_WRITTEN",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(state.get("recipient") or ""),
            "subject": str(state.get("subject") or ""),
            "payload_hash": str(state.get("payload_hash") or ""),
            "observed_payload_hash": str(state.get("observed_payload_hash") or ""),
            "expires_at": str(state.get("expires_at") or ""),
            "approved_draft_artifact_ref": str((state.get("draft_artifact") or {}).get("artifact_id") or ""),
            "authority_refs": list(state.get("authority_refs") or []),
            "credential_lease_refs": list(state.get("credential_lease_refs") or []),
            "transport_result": dict(transport_result or {}) if isinstance(transport_result, Mapping) else {},
            "request_consumed_in_fixture": True,
            "stored_body_loaded": True,
            "caller_draft_ignored": draft is not None,
            "live_request_touched": False,
            "execution_performed": False,
            "dry_run_transport_called": True,
            "live_transport_constructed": False,
            "gmail_api_called": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
            "calendar_api_called": False,
            "contacts_api_called": False,
            "created_at": generated_at,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        receipt_path = _write_exact_send_receipt(receipt_dir, "exact_send_dry_run_receipt", receipt)
        conn.execute(
            """
            INSERT INTO exact_send_fixture_executions
              (request_id, objective_id, created_at, receipt_json)
            VALUES (?, ?, ?, ?)
            """,
            (request_id, objective_id, generated_at, stable_json(receipt)),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_receipts
              (objective_id, receipt_ref, receipt_kind, status, receipt_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (objective_id, str(receipt.get("receipt_id") or ""), "exact_send_dry_run", "dry_run_recorded", stable_json(receipt)),
        )
        conn.commit()

    return {
        "schema_version": "EXACT_SEND_DRY_RUN_EXECUTOR_RESULT_V0",
        "response_status": "EXACT_SEND_DRY_RUN_RECEIPT_WRITTEN",
        "receipt": receipt,
        "dry_run_receipt_path": receipt_path.as_posix(),
        "execution_performed": False,
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }


class DisabledExactSendLiveTransport:
    """Structural live transport placeholder; it never calls Gmail."""

    live_transport = True
    enabled = False
    fixture_only = False

    def send_exact_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("exact send live transport is disabled")


class DisabledGmailExactSendTransport:
    """Disabled Gmail adapter using the governed broker route as metadata only."""

    live_transport = True
    live_transport_enabled = False
    fixture_only = False
    allowlisted_exact_send_transport = False
    uses_governed_broker_pattern = True
    broker_agent = GOOGLE_BROKER_AGENT_CASSANDRA
    broker_capability = GOOGLE_GMAIL_SEND_BROKER_CAPABILITY
    credential_handle_id = GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID

    def __init__(self, *, live_transport_enabled: bool = False) -> None:
        self.live_transport_enabled = live_transport_enabled
        self.broker_called = False

    def send_exact_payload(
        self,
        payload: Mapping[str, Any],
        *,
        authority_refs: Sequence[str] = (),
        credential_lease_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        if not authority_refs or not credential_lease_refs:
            reason = "authority_and_credential_lease_refs_required"
        elif not self.live_transport_enabled:
            reason = "gmail_transport_disabled"
        else:
            reason = "gmail_transport_requires_future_reviewed_broker_call"
        return {
            "ok": False,
            "reason": reason,
            "broker_agent": self.broker_agent,
            "broker_capability": self.broker_capability,
            "credential_handle_id": self.credential_handle_id,
            "authority_refs": list(authority_refs),
            "credential_lease_refs": list(credential_lease_refs),
            "broker_called": False,
            "gmail_api_called": False,
            "email_send_performed": False,
            "live_transport_enabled": bool(self.live_transport_enabled),
            "payload_hash": str(payload.get("payload_hash") or ""),
        }


class GovernedGmailBrokerSendTransport(DisabledGmailExactSendTransport):
    """Allowlisted exact-send transport for the governed Google broker."""

    allowlisted_exact_send_transport = True

    def __init__(self, *, live_transport_enabled: bool = False, broker_call: Any = None) -> None:
        super().__init__(live_transport_enabled=live_transport_enabled)
        self._broker_call = broker_call

    def send_exact_payload(
        self,
        payload: Mapping[str, Any],
        *,
        authority_refs: Sequence[str] = (),
        credential_lease_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        if not authority_refs or not credential_lease_refs:
            return {
                "ok": False,
                "reason": "authority_and_credential_lease_refs_required",
                "broker_called": False,
                "fake_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": bool(self.live_transport_enabled),
            }
        if not self.live_transport_enabled:
            return {
                "ok": False,
                "reason": "gmail_transport_disabled",
                "broker_agent": self.broker_agent,
                "broker_capability": self.broker_capability,
                "credential_handle_id": self.credential_handle_id,
                "broker_called": False,
                "fake_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": False,
                "payload_hash": str(payload.get("payload_hash") or ""),
            }
        broker_params = {
            "to": str(payload.get("recipient") or ""),
            "subject": str(payload.get("subject") or ""),
            "body": str(payload.get("body") or ""),
            "approval_context": {
                "request_id": str(payload.get("request_id") or ""),
                "objective_id": str(payload.get("objective_id") or ""),
                "payload_hash": str(payload.get("payload_hash") or ""),
                "authority_refs": list(authority_refs),
                "credential_lease_refs": list(credential_lease_refs),
                "exact_send_gate": True,
            },
        }
        broker_call = self._broker_call
        if broker_call is None:
            broker_module = __import__("google_access_broker")
            broker_call = getattr(broker_module, "call")
        result = broker_call(self.broker_agent, self.broker_capability, broker_params)
        self.broker_called = True
        ok = bool(isinstance(result, Mapping) and result.get("ok") is True)
        return {
            "ok": ok,
            "reason": "broker_send_completed" if ok else str((result or {}).get("error") or (result or {}).get("reason") or "broker_send_failed"),
            "broker_agent": self.broker_agent,
            "broker_capability": self.broker_capability,
            "credential_handle_id": self.credential_handle_id,
            "authority_refs": list(authority_refs),
            "credential_lease_refs": list(credential_lease_refs),
            "broker_called": True,
            "fake_broker_called": False,
            "gmail_api_called": ok,
            "email_send_performed": ok,
            "live_transport_enabled": True,
            "payload_hash": str(payload.get("payload_hash") or ""),
            "message_id": str(((result or {}).get("data") or {}).get("message_id") or "") if isinstance(result, Mapping) else "",
            "thread_id": str(((result or {}).get("data") or {}).get("thread_id") or "") if isinstance(result, Mapping) else "",
            "broker_result": dict(result or {}) if isinstance(result, Mapping) else {},
        }


class FakeBrokerGmailSendTransport(GovernedGmailBrokerSendTransport):
    """Fixture-only fake for exact-send tests; it never calls the real broker."""

    fixture_only = True

    def __init__(self) -> None:
        super().__init__(live_transport_enabled=True, broker_call=None)
        self.calls: list[dict[str, Any]] = []

    def send_exact_payload(
        self,
        payload: Mapping[str, Any],
        *,
        authority_refs: Sequence[str] = (),
        credential_lease_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        if not authority_refs or not credential_lease_refs:
            return {
                "ok": False,
                "reason": "authority_and_credential_lease_refs_required",
                "broker_called": False,
                "fake_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": True,
            }
        call = {
            "broker_agent": self.broker_agent,
            "broker_capability": self.broker_capability,
            "params": {
                "to": str(payload.get("recipient") or ""),
                "subject": str(payload.get("subject") or ""),
                "body_hash_only": str(payload.get("payload_hash") or ""),
                "approval_context": {
                    "request_id": str(payload.get("request_id") or ""),
                    "objective_id": str(payload.get("objective_id") or ""),
                },
            },
        }
        self.calls.append(call)
        message_id = "fake-gmail-message:" + _short_hash(
            payload.get("request_id"),
            payload.get("payload_hash"),
            payload.get("recipient"),
        )
        return {
            "ok": True,
            "reason": "fake_broker_send_recorded",
            "broker_agent": self.broker_agent,
            "broker_capability": self.broker_capability,
            "credential_handle_id": self.credential_handle_id,
            "authority_refs": list(authority_refs),
            "credential_lease_refs": list(credential_lease_refs),
            "broker_called": False,
            "fake_broker_called": True,
            "gmail_api_called": False,
            "email_send_performed": True,
            "live_transport_enabled": True,
            "payload_hash": str(payload.get("payload_hash") or ""),
            "message_id": message_id,
            "thread_id": "",
            "fixture_only": True,
        }


def _is_allowlisted_exact_send_transport(transport: Any) -> bool:
    return type(transport) in {GovernedGmailBrokerSendTransport, FakeBrokerGmailSendTransport}


def build_future_live_send_success_receipt_shape(
    *,
    request_id: str,
    objective_id: str,
    recipient: str,
    subject: str,
    payload_hash: str,
    authority_refs: Sequence[str] = (),
    credential_lease_refs: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": EXACT_SEND_FUTURE_LIVE_SUCCESS_RECEIPT_SCHEMA,
        "schema_only": True,
        "receipt_id": "exact_send_future_live_success_schema:" + _short_hash(request_id, payload_hash, generated_at),
        "response_status": "EXACT_SEND_FUTURE_LIVE_SUCCESS_SCHEMA_ONLY",
        "request_id": request_id,
        "objective_id": objective_id,
        "recipient": recipient,
        "subject": subject,
        "payload_hash": payload_hash,
        "authority_refs": list(authority_refs),
        "credential_lease_refs": list(credential_lease_refs),
        "broker_agent": GOOGLE_BROKER_AGENT_CASSANDRA,
        "broker_capability": GOOGLE_GMAIL_SEND_BROKER_CAPABILITY,
        "credential_handle_id": GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID,
        "broker_called": False,
        "execution_performed": False,
        "gmail_api_called": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "live_transport_constructed": False,
        "created_at": generated_at,
        "requires_future_review": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _exact_send_terminal_receipt(
    *,
    request_id: str,
    objective_id: str,
    state: Mapping[str, Any],
    transport_result: Mapping[str, Any],
    generated_at: str,
    fixture_only_transport: bool,
) -> dict[str, Any]:
    transport_ok = bool(transport_result.get("ok") is True)
    response_status = (
        "EXACT_SEND_LIVE_TRANSPORT_SUCCESS_RECEIPT_WRITTEN"
        if transport_ok
        else "EXACT_SEND_LIVE_TRANSPORT_FAILURE_RECEIPT_WRITTEN"
    )
    return {
        "schema_version": EXACT_SEND_LIVE_TRANSPORT_TERMINAL_RECEIPT_SCHEMA,
        "receipt_id": "exact_send_live_transport_terminal_receipt:" + _short_hash(
            request_id,
            state.get("payload_hash"),
            transport_result.get("message_id"),
            generated_at,
        ),
        "response_status": response_status,
        "request_id": request_id,
        "objective_id": objective_id,
        "recipient": str(state.get("recipient") or ""),
        "subject": str(state.get("subject") or ""),
        "payload_hash": str(state.get("payload_hash") or ""),
        "observed_payload_hash": str(state.get("observed_payload_hash") or ""),
        "expires_at": str(state.get("expires_at") or ""),
        "authority_refs": list(state.get("authority_refs") or []),
        "credential_lease_refs": list(state.get("credential_lease_refs") or []),
        "broker_agent": str(transport_result.get("broker_agent") or GOOGLE_BROKER_AGENT_CASSANDRA),
        "broker_capability": str(transport_result.get("broker_capability") or GOOGLE_GMAIL_SEND_BROKER_CAPABILITY),
        "credential_handle_id": str(transport_result.get("credential_handle_id") or GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID),
        "message_id": str(transport_result.get("message_id") or ""),
        "thread_id": str(transport_result.get("thread_id") or ""),
        "transport_ok": transport_ok,
        "transport_reason": str(transport_result.get("reason") or ""),
        "fixture_only_transport": fixture_only_transport,
        "broker_called": bool(transport_result.get("broker_called")),
        "fake_broker_called": bool(transport_result.get("fake_broker_called")),
        "live_broker_called": bool(transport_result.get("broker_called")),
        "live_transport_enabled": True,
        "live_transport_constructed": True,
        "execution_performed": bool(transport_result.get("email_send_performed")),
        "dry_run_transport_called": False,
        "gmail_api_called": bool(transport_result.get("gmail_api_called")),
        "gmail_draft_created": False,
        "email_send_performed": bool(transport_result.get("email_send_performed")),
        "calendar_api_called": False,
        "contacts_api_called": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def run_exact_send_live_transport_gate(
    *,
    sqlite_path: Path | str,
    objective_id: str,
    approval_decision: Mapping[str, Any],
    receipt_dir: Path | str,
    transport: Any = None,
    live_transport_enabled: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request_id = str(approval_decision.get("expected_request_id") or approval_decision.get("request_id") or "")

    def refuse(
        reason: str,
        *,
        objective_ref: str = "",
        recipient: str = "",
        subject: str = "",
        expected: str = "",
        observed: str = "",
        supplied: str = "",
        authority_refs: Sequence[str] = (),
        credential_lease_refs: Sequence[str] = (),
        live_transport_constructed: bool = False,
        live_transport_enabled_flag: bool = False,
        broker_called: bool = False,
        fake_broker_called: bool = False,
    ) -> dict[str, Any]:
        receipt = _exact_send_refusal_receipt(
            schema_version=EXACT_SEND_LIVE_TRANSPORT_REFUSAL_RECEIPT_SCHEMA,
            response_status="EXACT_SEND_LIVE_TRANSPORT_REFUSED",
            reason=reason,
            request_id=request_id,
            objective_id=objective_ref or objective_id,
            generated_at=generated_at,
            recipient=recipient,
            subject=subject,
            expected_payload_hash=expected,
            observed_payload_hash=observed,
            supplied_payload_hash=supplied,
            authority_refs=authority_refs,
            credential_lease_refs=credential_lease_refs,
            transport_mode="disabled_live_transport",
            live_transport_constructed=live_transport_constructed,
            live_transport_enabled=live_transport_enabled_flag,
            broker_agent=GOOGLE_BROKER_AGENT_CASSANDRA,
            broker_capability=GOOGLE_GMAIL_SEND_BROKER_CAPABILITY,
            broker_called=broker_called,
            fake_broker_called=fake_broker_called,
        )
        receipt_path = _write_exact_send_receipt(receipt_dir, "exact_send_live_transport_refusal_receipt", receipt)
        return {
            "schema_version": "EXACT_SEND_LIVE_TRANSPORT_GATE_RESULT_V0",
            "response_status": "EXACT_SEND_LIVE_TRANSPORT_REFUSED",
            "refusal_reason": reason,
            "receipt": receipt,
            "refusal_receipt_path": receipt_path.as_posix(),
            "execution_performed": False,
            "machine_proof": dict(AUTHORITY_BOUNDARY),
        }

    if _is_live_objective_db(sqlite_path):
        return refuse("live_objective_db_refused")
    if not approval_decision.get("approved"):
        return refuse(str(approval_decision.get("reason") or "approval_not_valid"))

    with _connect(sqlite_path) as conn:
        _ensure_exact_send_fixture_tables(conn)
        state, error = _load_exact_send_execution_state(
            conn,
            objective_id=objective_id,
            approval_decision=approval_decision,
            generated_at=generated_at,
        )
        if error:
            return refuse(
                str(error.get("reason") or "stored_request_invalid"),
                objective_ref=str(error.get("objective_id") or objective_id),
                recipient=str(error.get("recipient") or ""),
                subject=str(error.get("subject") or ""),
                expected=str(error.get("expected_payload_hash") or ""),
                observed=str(error.get("observed_payload_hash") or ""),
                supplied=str(error.get("supplied_payload_hash") or ""),
            )
        assert state is not None
        replay = conn.execute(
            "SELECT request_id FROM exact_send_fixture_executions WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if replay:
            return refuse(
                "replay_detected",
                objective_ref=str(state.get("objective_id") or ""),
                recipient=str(state.get("recipient") or ""),
                subject=str(state.get("subject") or ""),
                expected=str(state.get("payload_hash") or ""),
                observed=str(state.get("observed_payload_hash") or ""),
                authority_refs=list(state.get("authority_refs") or []),
                credential_lease_refs=list(state.get("credential_lease_refs") or []),
            )
        constructed = transport is not None and _is_allowlisted_exact_send_transport(transport)
        if not live_transport_enabled:
            return refuse(
                "live_transport_disabled",
                objective_ref=str(state.get("objective_id") or ""),
                recipient=str(state.get("recipient") or ""),
                subject=str(state.get("subject") or ""),
                expected=str(state.get("payload_hash") or ""),
                observed=str(state.get("observed_payload_hash") or ""),
                authority_refs=list(state.get("authority_refs") or []),
                credential_lease_refs=list(state.get("credential_lease_refs") or []),
                live_transport_constructed=constructed,
            )
        authority_refs = list(state.get("authority_refs") or [])
        credential_lease_refs = list(state.get("credential_lease_refs") or [])
        if transport is None or not _is_allowlisted_exact_send_transport(transport):
            return refuse(
                "allowlisted_gmail_transport_required",
                objective_ref=str(state.get("objective_id") or ""),
                recipient=str(state.get("recipient") or ""),
                subject=str(state.get("subject") or ""),
                expected=str(state.get("payload_hash") or ""),
                observed=str(state.get("observed_payload_hash") or ""),
                authority_refs=authority_refs,
                credential_lease_refs=credential_lease_refs,
                live_transport_constructed=constructed,
                live_transport_enabled_flag=True,
            )
        if not authority_refs or not credential_lease_refs:
            return refuse(
                "authority_and_credential_lease_refs_required",
                objective_ref=str(state.get("objective_id") or ""),
                recipient=str(state.get("recipient") or ""),
                subject=str(state.get("subject") or ""),
                expected=str(state.get("payload_hash") or ""),
                observed=str(state.get("observed_payload_hash") or ""),
                authority_refs=authority_refs,
                credential_lease_refs=credential_lease_refs,
                live_transport_constructed=constructed,
                live_transport_enabled_flag=True,
            )
        broker_payload = {
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(state.get("recipient") or ""),
            "subject": str(state.get("subject") or ""),
            "body": str(state.get("body") or ""),
            "payload_hash": str(state.get("payload_hash") or ""),
            "expires_at": str(state.get("expires_at") or ""),
        }
        transport_result = transport.send_exact_payload(
            broker_payload,
            authority_refs=authority_refs,
            credential_lease_refs=credential_lease_refs,
        )
        terminal_receipt = _exact_send_terminal_receipt(
            request_id=request_id,
            objective_id=objective_id,
            state=state,
            transport_result=dict(transport_result or {}) if isinstance(transport_result, Mapping) else {},
            generated_at=generated_at,
            fixture_only_transport=bool(getattr(transport, "fixture_only", False)),
        )
        receipt_prefix = (
            "exact_send_live_transport_success_receipt"
            if terminal_receipt["transport_ok"]
            else "exact_send_live_transport_failure_receipt"
        )
        terminal_receipt_path = _write_exact_send_receipt(receipt_dir, receipt_prefix, terminal_receipt)
        if terminal_receipt["transport_ok"]:
            conn.execute(
                """
                INSERT INTO exact_send_fixture_executions
                  (request_id, objective_id, created_at, receipt_json)
                VALUES (?, ?, ?, ?)
                """,
                (request_id, objective_id, generated_at, stable_json(terminal_receipt)),
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_receipts
              (objective_id, receipt_ref, receipt_kind, status, receipt_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                objective_id,
                str(terminal_receipt.get("receipt_id") or ""),
                "exact_send_live_transport_terminal",
                "success_recorded" if terminal_receipt["transport_ok"] else "failure_recorded",
                stable_json(terminal_receipt),
            ),
        )
        conn.commit()
        return {
            "schema_version": "EXACT_SEND_LIVE_TRANSPORT_GATE_RESULT_V0",
            "response_status": (
                "EXACT_SEND_LIVE_TRANSPORT_SUCCESS_RECEIPT_WRITTEN"
                if terminal_receipt["transport_ok"]
                else "EXACT_SEND_LIVE_TRANSPORT_FAILURE_RECEIPT_WRITTEN"
            ),
            "receipt": terminal_receipt,
            "terminal_receipt_path": terminal_receipt_path.as_posix(),
            "execution_performed": bool(terminal_receipt["execution_performed"]),
            "machine_proof": dict(AUTHORITY_BOUNDARY),
        }


def handle_draft_review_message(
    objective_id: str,
    operator_text: str,
    *,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    lowered = str(operator_text or "").lower()
    with _connect(sqlite_path) as conn:
        objective, draft = _load_draft(conn, objective_id)
        if "authority_granted" in lowered:
            _store_event(
                conn,
                objective_id=objective_id,
                channel="operator_chat",
                message_ref="draft_review_message",
                decision="raw_authority_text_rejected",
                status_transition=str(objective.get("objective_status") or ""),
                generated_at=generated_at,
            )
            conn.commit()
            return {
                "schema_version": "CASSANDRA_DRAFT_REVIEW_CONTINUATION_V0",
                "response_status": "RAW_AUTHORITY_TEXT_REJECTED",
                "send_authority_request_created": False,
                "objective": objective,
                "machine_proof": dict(AUTHORITY_BOUNDARY),
            }
        artifact = store_approved_send_draft_artifact(objective, draft=draft, generated_at=generated_at)
        request = build_exact_send_authority_request(
            objective_id=objective_id,
            draft=draft,
            operator_text=operator_text,
            approved_draft_artifact_ref=str(artifact.get("artifact_id") or ""),
            generated_at=generated_at,
        )
        objective["objective_status"] = STATUS_WAITING_SEND_AUTHORITY
        objective["current_step"] = "optional_email_send"
        objective["safe_next_step"] = "Review exact send/scheduled-send authority request."
        objective["send_authority_request"] = request
        objective["updated_at"] = generated_at
        _store_objective(conn, objective)
        _store_event(
            conn,
            objective_id=objective_id,
            channel="operator_chat",
            message_ref="draft_review_message",
            decision="send_authority_request_created_no_send",
            status_transition=STATUS_WAITING_SEND_AUTHORITY,
            receipt_ref=str(request.get("request_id") or ""),
            generated_at=generated_at,
        )
        conn.commit()
    return {
        "schema_version": "CASSANDRA_DRAFT_REVIEW_CONTINUATION_V0",
        "response_status": "SEND_AUTHORITY_REQUEST_READY",
        "send_authority_request_created": True,
        "send_authority_request": request,
        "objective": objective,
        "machine_proof": dict(AUTHORITY_BOUNDARY),
    }
