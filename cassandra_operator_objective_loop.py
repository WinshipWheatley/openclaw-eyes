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

import authority_secret_custody as custody
import mac_local_action_bridge


ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/cassandra_operator_objective_loop.sqlite")

CASSANDRA_OPERATOR_OBJECTIVE_SCHEMA = "CASSANDRA_OPERATOR_OBJECTIVE_V0"
LOOKUP_AUTHORITY_REQUEST_SCHEMA = "CASSANDRA_LOOKUP_AUTHORITY_REQUEST_V0"
TEXT_FOLLOWUP_DRAFT_SCHEMA = "TEXT_FOLLOWUP_DRAFT_V0"
EXACT_SEND_AUTHORITY_REQUEST_SCHEMA = "EXACT_SEND_AUTHORITY_REQUEST_V0"
UNATTENDED_REQUIREMENT_SCHEMA = "CASSANDRA_UNATTENDED_SEND_REQUIREMENT_V0"

READ_ONLY_EMAIL_LOOKUP = custody.READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID
GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID = custody.GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID

GMAIL_METADATA_READ = "openclaw.gmail_metadata_read"
GMAIL_BODY_READ = "openclaw.gmail_body_read"
GMAIL_DRAFT_GENERATOR = "openclaw.gmail_draft_generator"
GMAIL_SEND_MAIL = "openclaw.gmail_send_mail"

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

def route_cassandra_objective_message(
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
    if not detects_make_it_so_email_objective(text):
        return {
            "schema_version": "CASSANDRA_OPERATOR_OBJECTIVE_ROUTE_V0",
            "recognized": False,
            "response_status": "NOT_CASSANDRA_OPERATOR_OBJECTIVE",
            "machine_proof": dict(AUTHORITY_BOUNDARY),
        }
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


def _load_draft(conn: sqlite3.Connection, objective_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    objective = _load_objective(conn, objective_id)
    draft = objective.get("text_followup_draft") if isinstance(objective.get("text_followup_draft"), Mapping) else {}
    if not draft:
        raise ValueError("text follow-up draft is required before send review")
    return objective, dict(draft)


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
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
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
        request = build_exact_send_authority_request(
            objective_id=objective_id,
            draft=draft,
            operator_text=operator_text,
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
