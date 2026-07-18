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
from zoneinfo import ZoneInfo

import ar_counterparty_contact_operations as ar_ops
import authority_secret_custody as custody
from approval_gate_convergence import convergence_for_surface
from authority_gate import ensure_send_hold_sentinel
from email_send_executor import DEFAULT_SEND_HOLD_PATH
from final_output_boundary import OutputBoundaryContext, render_final_output
import invoice_send_transaction
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
EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_SCHEMA = "EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_V0"
OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA = "OPERATOR_ACTION_APPROVAL_REQUEST_V0"
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
EXACT_SEND_TEST_LOOPBACK_RECIPIENT = "winshiplive@gmail.com"
EXACT_SEND_TEST_LOOPBACK_MODE = "test_loopback_only"
EXACT_SEND_LIVE_DB_POLICY_FIXTURE_ONLY = "fixture_only"
EXACT_SEND_LIVE_DB_POLICY_FRESH_EXACT_APPROVAL_ONLY = "fresh_exact_approval_only"
OBSOLETE_EXACT_SEND_REQUEST_IDS = frozenset({
    "exact_send_authority_request:b20f03418d9b24a2",
})

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
STATUS_INVOICE_ENVELOPE_PREPARED = "invoice_envelope_prepared"

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

EXACT_SEND_AUTHORITY_DENIED_ACTIONS = (
    "send_without_exact_guardian_approval",
    "send_after_expiry",
    "send_different_recipient",
    "send_different_subject",
    "send_different_body",
    "send_different_payload_hash",
    "attachments",
    "create_email_draft",
    "compose_email",
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

EXACT_SEND_CREDENTIAL_DENIED_USE = (
    "send_without_exact_guardian_approval",
    "send_after_expiry",
    "send_different_payload",
    "send_different_recipient",
    "send_different_subject",
    "attachments",
    "compose_email",
    "create_email_draft",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "modify_email_labels",
    "contacts_read",
    "calendar_access",
    "mutate_contacts",
    "promote_contact_memory",
    "mark_paid",
    "mutate_ledger",
    "coupa_submit",
)

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
    context = dict(lane_context or {})
    attachment_paths = [str(item) for item in context.get("attachments") or []]
    attachment_sha256 = [str(item) for item in context.get("attachment_sha256") or []]

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
            attachments=attachment_paths,
            attachment_sha256=attachment_sha256,
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
    context = dict(lane_context or {})
    invoice_packet = context.get("deterministic_invoice_packet")
    copy_contract = context.get("immutable_copy_contract")
    artifact_receipt = context.get("artifact_receipt")
    if all(isinstance(item, Mapping) for item in (invoice_packet, copy_contract, artifact_receipt)):
        prepared = invoice_send_transaction.prepare_invoice_send(
            raw_operator_ask=text,
            deterministic_packet_aid=invoice_packet,
            immutable_copy_contract=copy_contract,
            artifact_receipt=artifact_receipt,
            db_path=_rooted(sqlite_path),
            generated_at=generated_at,
        )
        transaction = prepared["transaction"]
        objective_id = "cassandra_invoice_prepare:" + str(transaction["transaction_id"]).rsplit(":", 1)[-1]
        operator_reply = (
            "I prepared the immutable invoice envelope and stopped at review. "
            "Nothing was drafted or sent. Next, review the exact facts and attachment hash."
        )
        boundary = render_final_output(
            operator_reply,
            context=OutputBoundaryContext.from_source_request(text),
            speaker_ref="cassandra",
        )
        objective = {
            "schema_version": CASSANDRA_OPERATOR_OBJECTIVE_SCHEMA,
            "objective_id": objective_id,
            "actor": "Cassandra",
            "requested_by_operator": "operator:winship",
            "source_channel": source_channel,
            "source_message_ref": source_message_ref,
            "original_user_text": _strip_cassandra_prefix(text),
            "lane_context": {
                "target_world_ref": context.get("target_world_ref"),
                "target_thread_ref": context.get("target_thread_ref"),
                "invoice_packet_sha256": prepared["copy_result"]["immutable_input_hashes"]["deterministic_packet_aid"],
            },
            "client_or_counterparty": prepared["envelope"]["client_display_name"],
            "objective_summary": "Prepare an immutable no-send invoice envelope for operator review.",
            "intended_outcome": "Persist PREPARED transaction facts without provider or send activity.",
            "current_step": "invoice_envelope_review",
            "objective_status": STATUS_INVOICE_ENVELOPE_PREPARED,
            "safe_next_step": "Review the exact envelope facts and attachment hash.",
            "steps": [
                _step(
                    "invoice_envelope_prepare",
                    "complete",
                    capability_ids=["invoice_send_class_waist"],
                    transaction_id=transaction["transaction_id"],
                    envelope_hash=transaction["envelope_hash"],
                ),
                _step("provider_draft", "blocked", required_authority="W2 provider draft gate"),
                _step("email_send", "blocked", required_authority="W3 exact send gate and SEND_HOLD lift"),
            ],
            "authority_refs": [],
            "credential_lease_refs": [],
            "receipts": [transaction["envelope_hash"]],
            "proof_refs": [transaction["envelope_hash"]],
            "denied_actions": list(DENIED_ACTIONS),
            "created_at": generated_at,
            "updated_at": generated_at,
        }
        _persist_objective(
            objective,
            sqlite_path,
            generated_at=generated_at,
            decision="immutable_invoice_envelope_prepared_no_send",
        )
        machine_proof = {
            **dict(AUTHORITY_BOUNDARY),
            **prepared["machine_proof"],
            "immutable_envelope_persisted": True,
            "invoice_transaction_state": invoice_send_transaction.PREPARED,
        }
        return {
            "schema_version": "CASSANDRA_INVOICE_PREPARE_ROUTE_V1",
            "recognized": True,
            "response_status": "CASSANDRA_INVOICE_ENVELOPE_PREPARED",
            "operator_reply": boundary.visible_text,
            "next_safe_step": objective["safe_next_step"],
            "objective": objective,
            "invoice_prepare": prepared,
            "voice_boundary_receipt": boundary.receipt.to_dict(),
            "machine_proof": machine_proof,
        }
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_exact_send_test_loopback_binding(
    payload: Mapping[str, Any],
    *,
    verify_file: bool = True,
) -> dict[str, Any]:
    if payload.get("test_loopback_only") is not True:
        return {}
    recipient = str(payload.get("recipient") or "").strip().lower()
    recipient_lock = str(payload.get("test_recipient_lock") or "").strip().lower()
    attachments = [str(item) for item in payload.get("attachments") or []]
    attachment_sha256 = [str(item).strip().lower() for item in payload.get("attachment_sha256") or []]
    if recipient != EXACT_SEND_TEST_LOOPBACK_RECIPIENT:
        raise ValueError("test loopback recipient must be winshiplive@gmail.com")
    if recipient_lock != EXACT_SEND_TEST_LOOPBACK_RECIPIENT:
        raise ValueError("test recipient lock must be winshiplive@gmail.com")
    if len(attachments) != 1 or len(attachment_sha256) != 1:
        raise ValueError("test loopback requires exactly one attachment and one SHA-256")
    digest = attachment_sha256[0]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("test loopback attachment SHA-256 is invalid")
    attachment = Path(attachments[0]).expanduser()
    if not attachment.is_absolute() or attachment.suffix.lower() != ".pdf":
        raise ValueError("test loopback attachment must be an absolute PDF path")
    if attachment.is_symlink():
        raise ValueError("test loopback attachment cannot be a symlink")
    if verify_file:
        if not attachment.is_file():
            raise ValueError("test loopback attachment is missing")
        if _sha256_file(attachment) != digest:
            raise ValueError("test loopback attachment SHA-256 mismatch")
    canonical = {
        "request_id": str(payload.get("request_id") or ""),
        "payload_hash": str(payload.get("payload_hash") or ""),
        "recipient": recipient,
        "test_recipient_lock": recipient_lock,
        "test_loopback_only": True,
        "attachments": [str(attachment)],
        "attachment_sha256": [digest],
    }
    binding_hash = "sha256:" + hashlib.sha256(stable_json(canonical).encode("utf-8")).hexdigest()
    supplied_binding_hash = str(payload.get("test_loopback_binding_hash") or "")
    if supplied_binding_hash and supplied_binding_hash != binding_hash:
        raise ValueError("test loopback binding hash mismatch")
    return {**canonical, "test_loopback_binding_hash": binding_hash}


def _validated_exact_send_attachment_binding(
    payload: Mapping[str, Any],
    *,
    verify_file: bool = True,
) -> dict[str, Any]:
    attachments = [str(item) for item in payload.get("attachments") or []]
    attachment_sha256 = [str(item).strip().lower() for item in payload.get("attachment_sha256") or []]
    if not attachments and not attachment_sha256:
        return {}
    if len(attachments) != 1 or len(attachment_sha256) != 1:
        raise ValueError("exact send requires exactly one attachment and one SHA-256")
    digest = attachment_sha256[0]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("exact send attachment SHA-256 is invalid")
    attachment = Path(attachments[0]).expanduser()
    if not attachment.is_absolute() or attachment.suffix.lower() != ".pdf":
        raise ValueError("exact send attachment must be an absolute PDF path")
    if attachment.is_symlink():
        raise ValueError("exact send attachment cannot be a symlink")
    if verify_file:
        if not attachment.is_file():
            raise ValueError("exact send attachment is missing")
        if _sha256_file(attachment) != digest:
            raise ValueError("exact send attachment SHA-256 mismatch")
    canonical = {
        "request_id": str(payload.get("request_id") or ""),
        "payload_hash": str(payload.get("payload_hash") or ""),
        "recipient": str(payload.get("recipient") or "").strip().lower(),
        "attachments": [str(attachment)],
        "attachment_sha256": [digest],
    }
    binding_hash = "sha256:" + hashlib.sha256(stable_json(canonical).encode("utf-8")).hexdigest()
    supplied_binding_hash = str(payload.get("attachment_binding_hash") or "")
    if supplied_binding_hash and supplied_binding_hash != binding_hash:
        raise ValueError("exact send attachment binding hash mismatch")
    return {**canonical, "attachment_binding_hash": binding_hash}


def bind_exact_send_test_loopback_attachment(
    authority_request: Mapping[str, Any],
    *,
    attachment_path: str | Path,
    attachment_sha256: str,
) -> dict[str, Any]:
    """Bind one reviewed PDF to the existing exact-send action in TEST loopback mode."""
    updated = dict(authority_request)
    if str(updated.get("recipient") or "").strip().lower() != EXACT_SEND_TEST_LOOPBACK_RECIPIENT:
        raise ValueError("test loopback recipient must be winshiplive@gmail.com")
    updated.update(
        {
            "test_loopback_only": True,
            "test_recipient_lock": EXACT_SEND_TEST_LOOPBACK_RECIPIENT,
            "attachments": [str(Path(attachment_path))],
            "attachment_sha256": [str(attachment_sha256).strip().lower()],
        }
    )
    binding = _validated_exact_send_test_loopback_binding(updated)
    updated.update(binding)
    updated["denied_actions"] = [
        action
        for action in updated.get("denied_actions") or []
        if action != "attachments"
    ]
    return updated


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
    attachments: Sequence[str] = (),
    attachment_sha256: Sequence[str] = (),
    expires_at: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    expires_at = expires_at or _default_exact_send_expires_at(generated_at)
    unattended = build_unattended_requirement(objective_id=objective_id, operator_text=operator_text, generated_at=generated_at)
    request = {
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
    if attachments or attachment_sha256:
        request.update(
            {
                "attachments": list(attachments),
                "attachment_sha256": list(attachment_sha256),
            }
        )
        request.update(_validated_exact_send_attachment_binding(request))
        request["denied_actions"] = [
            action for action in request["denied_actions"] if action != "attachments"
        ]
    return request


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
    if authority_request.get("test_loopback_only") is True:
        packet.update(_validated_exact_send_test_loopback_binding(authority_request))
    attachment_binding = _validated_exact_send_attachment_binding(authority_request)
    if attachment_binding:
        packet.update(attachment_binding)
    return packet


def _format_timestamp_utc(value: str) -> str:
    parsed = _parse_timestamp(value) or datetime.now(timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_timestamp_local(value: str, timezone_name: str = "America/New_York") -> str:
    parsed = _parse_timestamp(value) or datetime.now(timezone.utc)
    return parsed.astimezone(ZoneInfo(timezone_name)).isoformat(timespec="seconds")


def create_exact_send_scoped_authority(
    authority_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Create metadata-only authority and lease records for one exact Gmail send.

    This does not approve or execute the send. It only creates scoped refs that
    a later Guardian approval and exact-send gate can bind to.
    """
    generated_at = generated_at or utc_now()
    request_id = str(authority_request.get("request_id") or "")
    objective_id = str(authority_request.get("objective_id") or "")
    payload_hash = str(authority_request.get("payload_hash") or "")
    expires_at = str(expires_at or authority_request.get("expires_at") or _default_exact_send_expires_at(generated_at))
    recipient = str(authority_request.get("recipient") or "")
    subject = str(authority_request.get("subject") or "")
    test_binding = (
        _validated_exact_send_test_loopback_binding(authority_request)
        if authority_request.get("test_loopback_only") is True
        else {}
    )
    attachment_binding = _validated_exact_send_attachment_binding(authority_request)
    max_scope = {
        "exact_send_request_id": request_id,
        "objective_id": objective_id,
        "recipient": recipient,
        "subject": subject,
        "payload_hash": payload_hash,
        "one_time_only": True,
        "attachments_allowed": False,
    }
    if attachment_binding:
        max_scope.update(
            {
                "attachments_allowed": True,
                "attachments": list(attachment_binding["attachments"]),
                "attachment_sha256": list(attachment_binding["attachment_sha256"]),
                "attachment_binding_hash": attachment_binding["attachment_binding_hash"],
            }
        )
    if test_binding:
        max_scope.update(
            {
                "test_loopback_only": True,
                "test_recipient_lock": test_binding["test_recipient_lock"],
                "test_loopback_binding_hash": test_binding["test_loopback_binding_hash"],
            }
        )
    denied_actions = tuple(
        action
        for action in EXACT_SEND_AUTHORITY_DENIED_ACTIONS
        if not (attachment_binding and action == "attachments")
    )
    denied_credential_use = tuple(
        action
        for action in EXACT_SEND_CREDENTIAL_DENIED_USE
        if not (attachment_binding and action == "attachments")
    )
    allowed_use = [
        "gmail_send_exact_single_message_after_guardian_approval",
        f"exact_send_request_id:{request_id}",
        f"payload_hash:{payload_hash}",
        f"recipient:{recipient}",
    ]
    if attachment_binding:
        allowed_use.extend(
            [
                f"attachment_sha256:{attachment_binding['attachment_sha256'][0]}",
                f"attachment_binding_hash:{attachment_binding['attachment_binding_hash']}",
            ]
        )
    if test_binding:
        allowed_use.extend(
            [
                f"test_recipient_lock:{test_binding['test_recipient_lock']}",
                f"test_loopback_binding_hash:{test_binding['test_loopback_binding_hash']}",
            ]
        )
    envelope = custody.create_authority_envelope(
        operator_id="operator:winship",
        device_id="device:guardian_operator_surface",
        confirmation_method="guardian_exact_send_approval_pending",
        confirmation_receipt_ref="pending_guardian_exact_send_approval:" + _short_hash(request_id, payload_hash, generated_at),
        requested_objective=f"Authorize one exact Gmail send for {request_id}.",
        capability_ids=[GMAIL_SEND_MAIL],
        allowed_actions=[
            "send_exact_single_gmail_message_after_guardian_approval",
            "write_exact_send_terminal_receipt",
        ],
        denied_actions=denied_actions,
        credential_handles_allowed=[GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID],
        live_data_access_allowed=False,
        production_action_allowed=True,
        external_service_access_allowed=True,
        unattended_allowed=False,
        one_time_or_reusable="one_time",
        max_scope=max_scope,
        expires_at=expires_at,
        receipt_requirements=[
            "exact_send_guardian_approval_receipt",
            "exact_payload_hash_verifier",
            "exact_send_terminal_receipt",
        ],
        status="pending_guardian_approval",
        generated_at=generated_at,
    )
    handle = custody.google_workspace_broker_credential_handle(generated_at=generated_at)
    lease = custody.create_credential_lease(
        credential_handle=handle,
        authority_envelope=envelope,
        capability_id=GMAIL_SEND_MAIL,
        allowed_use=allowed_use,
        denied_use=denied_credential_use,
        adapter_ref="adapter:google_workspace_broker.exact_send_gate",
        expires_at=expires_at,
        receipt_requirements=[
            "exact_send_guardian_approval_receipt",
            "authority_envelope_ref",
            "exact_send_terminal_receipt",
        ],
        generated_at=generated_at,
    )
    if lease.get("lease_created") is True:
        lease.update(
            {
                "objective_scope": dict(max_scope),
                "task_scope": dict(max_scope),
                "allowed_scope": "one exact Gmail send only after Guardian approval",
                "lease_verifier_ref": "google_workspace_broker_exact_send_lease_verifier",
                "guardian_approval_required": True,
                "live_execution_authorized": False,
                "no_execution_performed": True,
            }
        )
    return {
        "schema_version": "EXACT_SEND_SCOPED_AUTHORITY_BUNDLE_V0",
        "authority_envelope": envelope,
        "credential_handle": handle,
        "credential_lease": lease,
        "request_id": request_id,
        "objective_id": objective_id,
        "payload_hash": payload_hash,
        "expires_at": expires_at,
        "created_at": generated_at,
        "execution_performed": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def verify_exact_send_authority_scope(
    authority_envelope: Mapping[str, Any],
    credential_lease: Mapping[str, Any],
    authority_request: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    request_id = str(authority_request.get("request_id") or "")
    payload_hash = str(authority_request.get("payload_hash") or "")
    test_binding: dict[str, Any] = {}
    attachment_binding: dict[str, Any] = {}
    try:
        attachment_binding = _validated_exact_send_attachment_binding(authority_request)
    except ValueError:
        errors.append("attachment_binding_invalid")
    if authority_request.get("test_loopback_only") is True:
        try:
            test_binding = _validated_exact_send_test_loopback_binding(authority_request)
        except ValueError:
            errors.append("test_loopback_binding_invalid")
    if str(authority_request.get("capability_id") or GMAIL_SEND_MAIL) != GMAIL_SEND_MAIL:
        errors.append("request_capability_must_be_gmail_send")
    if not authority_envelope or authority_envelope.get("schema_version") != custody.AUTHORITY_ENVELOPE_SCHEMA:
        errors.append("authority_envelope_required")
    else:
        capability_ids = set(authority_envelope.get("capability_ids") or [])
        if GMAIL_SEND_MAIL not in capability_ids:
            errors.append("authority_envelope_not_scoped_for_gmail_send")
        if GMAIL_BODY_READ in capability_ids:
            errors.append("body_read_authority_cannot_authorize_send")
        if GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID not in set(authority_envelope.get("credential_handles_allowed") or []):
            errors.append("broker_credential_handle_not_allowed_by_envelope")
        max_scope = authority_envelope.get("max_scope") if isinstance(authority_envelope.get("max_scope"), Mapping) else {}
        if request_id and str(max_scope.get("exact_send_request_id") or "") != request_id:
            errors.append("authority_envelope_request_id_mismatch")
        if payload_hash and str(max_scope.get("payload_hash") or "") != payload_hash:
            errors.append("authority_envelope_payload_hash_mismatch")
        if attachment_binding:
            if max_scope.get("attachments_allowed") is not True:
                errors.append("authority_envelope_attachment_not_allowed")
            for field in ("attachments", "attachment_sha256", "attachment_binding_hash"):
                if max_scope.get(field) != attachment_binding.get(field):
                    errors.append(f"authority_envelope_{field}_mismatch")
        if test_binding:
            for field in (
                "test_loopback_only",
                "test_recipient_lock",
                "test_loopback_binding_hash",
            ):
                if max_scope.get(field) != test_binding.get(field):
                    errors.append(f"authority_envelope_{field}_mismatch")
        if authority_envelope.get("production_action_allowed") is not True:
            errors.append("authority_envelope_send_action_not_marked_production_scoped")
        if authority_envelope.get("external_service_access_allowed") is not True:
            errors.append("authority_envelope_external_service_not_scoped")
    if not credential_lease or credential_lease.get("schema_version") != custody.CREDENTIAL_LEASE_SCHEMA or credential_lease.get("lease_created") is not True:
        errors.append("valid_credential_lease_required")
    else:
        if credential_lease.get("capability_id") != GMAIL_SEND_MAIL:
            errors.append("credential_lease_not_scoped_for_gmail_send")
        if credential_lease.get("capability_id") == GMAIL_BODY_READ:
            errors.append("body_read_credential_lease_cannot_authorize_send")
        if authority_envelope and credential_lease.get("authority_envelope_id") != authority_envelope.get("envelope_id"):
            errors.append("credential_lease_authority_envelope_mismatch")
        allowed_use = set(credential_lease.get("allowed_use") or [])
        if request_id and f"exact_send_request_id:{request_id}" not in allowed_use:
            errors.append("credential_lease_request_id_scope_missing")
        if payload_hash and f"payload_hash:{payload_hash}" not in allowed_use:
            errors.append("credential_lease_payload_hash_scope_missing")
        if attachment_binding:
            required_attachment_uses = {
                f"attachment_sha256:{attachment_binding['attachment_sha256'][0]}",
                f"attachment_binding_hash:{attachment_binding['attachment_binding_hash']}",
            }
            if not required_attachment_uses.issubset(allowed_use):
                errors.append("credential_lease_attachment_scope_missing")
        if test_binding:
            required_test_uses = {
                f"test_recipient_lock:{test_binding['test_recipient_lock']}",
                f"test_loopback_binding_hash:{test_binding['test_loopback_binding_hash']}",
            }
            if not required_test_uses.issubset(allowed_use):
                errors.append("credential_lease_test_loopback_scope_missing")
    return {
        "schema_version": "EXACT_SEND_AUTHORITY_SCOPE_VERDICT_V0",
        "valid": not errors,
        "validation_errors": errors,
        "request_id": request_id,
        "payload_hash": payload_hash,
        "attachment_binding_hash": str(attachment_binding.get("attachment_binding_hash") or ""),
        "test_loopback_only": bool(test_binding),
        "test_loopback_binding_hash": str(test_binding.get("test_loopback_binding_hash") or ""),
        "authority_envelope_id": str(authority_envelope.get("envelope_id") or "") if authority_envelope else "",
        "credential_lease_id": str(credential_lease.get("lease_id") or "") if credential_lease else "",
        "authority_envelope_valid_for_send": not any(error.startswith("authority_envelope") or error == "body_read_authority_cannot_authorize_send" for error in errors),
        "credential_lease_valid_for_send": not any(error.startswith("credential_lease") or error in {"valid_credential_lease_required", "body_read_credential_lease_cannot_authorize_send"} for error in errors),
        "execution_performed": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def attach_exact_send_authority_refs(
    objective: Mapping[str, Any],
    *,
    authority_envelope: Mapping[str, Any],
    credential_lease: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = dict(objective)
    request = dict(updated.get("send_authority_request") or {})
    verdict = verify_exact_send_authority_scope(authority_envelope, credential_lease, request)
    if not verdict["valid"]:
        return updated, verdict
    authority_ref = str(authority_envelope.get("envelope_id") or "")
    lease_ref = str(credential_lease.get("lease_id") or "")
    updated["authority_refs"] = [authority_ref]
    updated["credential_lease_refs"] = [lease_ref]
    request.update(
        {
            "authority_envelope_ref": authority_ref,
            "credential_lease_ref": lease_ref,
            "authority_refs": [authority_ref],
            "credential_lease_refs": [lease_ref],
            "send_authority_scope_verdict": verdict,
            "fresh_exact_approval_required": True,
            "guardian_approval_required": True,
            "execution_performed": False,
        }
    )
    updated["send_authority_request"] = request
    return updated, verdict


def persist_exact_send_authority_bundle(
    objective: Mapping[str, Any],
    *,
    authority_envelope: Mapping[str, Any],
    credential_lease: Mapping[str, Any],
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    authority_provenance: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    updated, verdict = attach_exact_send_authority_refs(
        objective,
        authority_envelope=authority_envelope,
        credential_lease=credential_lease,
    )
    if not verdict["valid"]:
        return {"persisted": False, "objective": updated, "scope_verdict": verdict}
    updated["updated_at"] = generated_at
    updated["authority_provenance"] = str(authority_provenance or "")
    authority_ref = str(authority_envelope.get("envelope_id") or "")
    lease_ref = str(credential_lease.get("lease_id") or "")
    with _connect(sqlite_path) as conn:
        _store_objective(conn, updated)
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_authority_refs
              (objective_id, authority_ref, authority_kind, status, ref_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                updated["objective_id"],
                authority_ref,
                "exact_gmail_send",
                "scoped_pending_operator_decision",
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
                updated["objective_id"],
                lease_ref,
                str(credential_lease.get("credential_handle_id") or ""),
                str(credential_lease.get("capability_id") or ""),
                "scoped_pending_operator_decision",
                stable_json(credential_lease),
            ),
        )
        event = _store_event(
            conn,
            objective_id=updated["objective_id"],
            channel="authority_system",
            message_ref=str(authority_provenance or ""),
            decision="exact_send_authority_and_lease_persisted",
            status_transition=str(updated.get("objective_status") or STATUS_WAITING_SEND_AUTHORITY),
            receipt_ref=authority_ref,
            generated_at=generated_at,
        )
        conn.commit()
    return {
        "persisted": True,
        "objective": updated,
        "scope_verdict": verdict,
        "authority_ref": authority_ref,
        "credential_lease_ref": lease_ref,
        "event": event,
    }


def build_exact_send_guardian_approval_request(
    review_packet: Mapping[str, Any],
    *,
    authority_envelope: Mapping[str, Any],
    credential_lease: Mapping[str, Any],
    generated_at: str | None = None,
    local_timezone: str = "America/New_York",
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request_id = str(review_packet.get("request_id") or "")
    payload_hash = str(review_packet.get("payload_hash") or "")
    expires_at = str(review_packet.get("expires_at") or "")
    authority_request = {
        "request_id": request_id,
        "objective_id": str(review_packet.get("objective_id") or ""),
        "recipient": str(review_packet.get("recipient") or ""),
        "subject": str(review_packet.get("subject") or ""),
        "payload_hash": payload_hash,
        "capability_id": GMAIL_SEND_MAIL,
    }
    try:
        attachment_binding = _validated_exact_send_attachment_binding(review_packet)
    except ValueError as exc:
        return {
            "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
            "operator_action_created": False,
            "response_status": "OPERATOR_ACTION_APPROVAL_REQUEST_REFUSED",
            "refusal_reason": (
                "invalid_test_loopback_attachment_binding"
                if review_packet.get("test_loopback_only") is True
                else "invalid_attachment_binding"
            ),
            "validation_error": str(exc),
            "request_id": request_id,
            "objective_id": objective_id,
            "payload_hash": payload_hash,
            "execution_performed": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
        }
    if attachment_binding:
        authority_request.update(attachment_binding)
    test_binding: dict[str, Any] = {}
    if review_packet.get("test_loopback_only") is True:
        try:
            test_binding = _validated_exact_send_test_loopback_binding(review_packet)
        except ValueError as exc:
            return {
                "schema_version": EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_SCHEMA,
                "request_created": False,
                "response_status": "EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_REFUSED",
                "refusal_reason": "invalid_test_loopback_attachment_binding",
                "validation_error": str(exc),
                "exact_send_request_id": request_id,
                "objective_id": str(review_packet.get("objective_id") or ""),
                "payload_hash": payload_hash,
                "guardian_delivered": False,
                "execution_performed": False,
                "gmail_draft_created": False,
                "email_send_performed": False,
            }
        authority_request.update(test_binding)
    if _timestamp_expired(expires_at, generated_at=generated_at):
        return {
            "schema_version": EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_SCHEMA,
            "request_created": False,
            "response_status": "EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_REFUSED",
            "refusal_reason": "expired_request",
            "exact_send_request_id": request_id,
            "objective_id": str(review_packet.get("objective_id") or ""),
            "payload_hash": payload_hash,
            "expires_at_utc": _format_timestamp_utc(expires_at),
            "expires_at_local": _format_timestamp_local(expires_at, local_timezone),
            "guardian_delivered": False,
            "execution_performed": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    scope_verdict = verify_exact_send_authority_scope(authority_envelope, credential_lease, authority_request)
    if not scope_verdict["valid"]:
        return {
            "schema_version": EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_SCHEMA,
            "request_created": False,
            "response_status": "EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_REFUSED",
            "refusal_reason": "invalid_send_authority_scope",
            "scope_verdict": scope_verdict,
            "exact_send_request_id": request_id,
            "objective_id": str(review_packet.get("objective_id") or ""),
            "payload_hash": payload_hash,
            "expires_at_utc": _format_timestamp_utc(expires_at),
            "expires_at_local": _format_timestamp_local(expires_at, local_timezone),
            "guardian_delivered": False,
            "execution_performed": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    approval_phrase = str(review_packet.get("approval_phrase") or f"Approve exact send request {request_id}")
    expires_utc = _format_timestamp_utc(expires_at)
    expires_local = _format_timestamp_local(expires_at, local_timezone)
    recipient = str(review_packet.get("recipient") or "")
    subject = str(review_packet.get("subject") or "")
    body = str(review_packet.get("body") or "")
    guardian_request_id = "exact_send_guardian_approval_request:" + _short_hash(request_id, payload_hash, expires_at)
    message_text = (
        "EXACT SEND APPROVAL REQUIRED\n\n"
        "Warning: approval sends exactly one email if granted.\n\n"
        f"Guardian approval request id: {guardian_request_id}\n"
        f"Exact send request id: {request_id}\n"
        f"Objective id: {review_packet.get('objective_id')}\n"
        f"Recipient: {recipient}\n"
        f"Subject: {subject}\n"
        f"Payload hash: {payload_hash}\n"
        f"Expires UTC: {expires_utc}\n"
        f"Expires {local_timezone}: {expires_local}\n"
        f"Authority envelope: {authority_envelope.get('envelope_id')}\n"
        f"Credential lease: {credential_lease.get('lease_id')}\n\n"
        "Exact body:\n"
        f"{body}\n\n"
        "Approve with exact phrase:\n"
        f"{approval_phrase}\n\n"
        "Deny by replying: Deny exact send request "
        f"{request_id}"
    )
    return {
        "schema_version": EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_SCHEMA,
        "request_created": True,
        "response_status": "EXACT_SEND_GUARDIAN_APPROVAL_REQUEST_CREATED",
        "guardian_approval_request_id": guardian_request_id,
        "exact_send_request_id": request_id,
        "objective_id": str(review_packet.get("objective_id") or ""),
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "payload_hash": payload_hash,
        "expires_at_utc": expires_utc,
        "expires_at_local": expires_local,
        "local_timezone": local_timezone,
        "authority_envelope_id": str(authority_envelope.get("envelope_id") or ""),
        "credential_lease_id": str(credential_lease.get("lease_id") or ""),
        "approval_phrase": approval_phrase,
        "deny_phrase": f"Deny exact send request {request_id}",
        "button_labels": ["Approve", "Deny", "Why now?"],
        "warning": "This approval sends exactly one email if granted.",
        "message_text": message_text,
        "scope_verdict": scope_verdict,
        "guardian_delivery_authorized": False,
        "guardian_delivered": False,
        "execution_performed": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "calendar_api_called": False,
        "contacts_api_called": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _ttl_seconds_until(expires_at: str, *, generated_at: str | None = None) -> int:
    expiry = _parse_timestamp(expires_at)
    observed = _parse_timestamp(generated_at) or datetime.now(timezone.utc)
    if not expiry:
        return 0
    return max(0, int((expiry - observed).total_seconds()))


def register_exact_send_operator_action_approval(
    review_packet: Mapping[str, Any],
    *,
    authority_envelope: Mapping[str, Any],
    credential_lease: Mapping[str, Any],
    approval_provenance: str = "",
    send_hold_graduation_ref: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Register an exact Gmail send as a real HITL/Guardian operator action.

    The existing HITL queue receives only metadata needed for approval routing.
    Raw body text remains in the exact-send review packet/artifact, not the
    broad pending-action queue.
    """
    generated_at = generated_at or utc_now()
    request_id = str(review_packet.get("request_id") or "")
    objective_id = str(review_packet.get("objective_id") or "")
    payload_hash = str(review_packet.get("payload_hash") or "")
    expires_at = str(review_packet.get("expires_at") or "")
    authority_request = {
        "request_id": request_id,
        "objective_id": objective_id,
        "recipient": str(review_packet.get("recipient") or ""),
        "subject": str(review_packet.get("subject") or ""),
        "payload_hash": payload_hash,
        "capability_id": GMAIL_SEND_MAIL,
    }
    try:
        attachment_binding = _validated_exact_send_attachment_binding(review_packet)
    except ValueError as exc:
        return {
            "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
            "operator_action_created": False,
            "response_status": "OPERATOR_ACTION_APPROVAL_REQUEST_REFUSED",
            "refusal_reason": (
                "invalid_test_loopback_attachment_binding"
                if review_packet.get("test_loopback_only") is True
                else "invalid_attachment_binding"
            ),
            "validation_error": str(exc),
            "request_id": request_id,
            "objective_id": objective_id,
            "payload_hash": payload_hash,
            "execution_performed": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
        }
    if attachment_binding:
        authority_request.update(attachment_binding)
    test_binding: dict[str, Any] = {}
    if review_packet.get("test_loopback_only") is True:
        try:
            test_binding = _validated_exact_send_test_loopback_binding(review_packet)
        except ValueError as exc:
            return {
                "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
                "operator_action_created": False,
                "response_status": "OPERATOR_ACTION_APPROVAL_REQUEST_REFUSED",
                "refusal_reason": "invalid_test_loopback_attachment_binding",
                "validation_error": str(exc),
                "request_id": request_id,
                "objective_id": objective_id,
                "payload_hash": payload_hash,
                "execution_performed": False,
                "gmail_draft_created": False,
                "email_send_performed": False,
            }
        authority_request.update(test_binding)
    if _timestamp_expired(expires_at, generated_at=generated_at):
        return {
            "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
            "operator_action_created": False,
            "response_status": "OPERATOR_ACTION_APPROVAL_REQUEST_REFUSED",
            "refusal_reason": "expired_request",
            "request_id": request_id,
            "objective_id": objective_id,
            "payload_hash": payload_hash,
            "execution_performed": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
        }
    scope_verdict = verify_exact_send_authority_scope(authority_envelope, credential_lease, authority_request)
    if not scope_verdict["valid"]:
        return {
            "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
            "operator_action_created": False,
            "response_status": "OPERATOR_ACTION_APPROVAL_REQUEST_REFUSED",
            "refusal_reason": "invalid_send_authority_scope",
            "scope_verdict": scope_verdict,
            "request_id": request_id,
            "objective_id": objective_id,
            "payload_hash": payload_hash,
            "execution_performed": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
        }
    import hitl_action_service

    exact_payload = {
        "recipient": str(review_packet.get("recipient") or ""),
        "subject": str(review_packet.get("subject") or ""),
        "payload_hash": payload_hash,
        "request_id": request_id,
        "objective_id": objective_id,
        "expires_at": expires_at,
        "authority_envelope_ref": str(authority_envelope.get("envelope_id") or ""),
        "credential_lease_ref": str(credential_lease.get("lease_id") or ""),
        "approved_draft_artifact_ref": str(review_packet.get("approved_draft_artifact_ref") or ""),
        "review_packet_ref": str(review_packet.get("packet_id") or ""),
        "body_stored_in_hitl_queue": False,
        "body_sha256": "sha256:" + hashlib.sha256(str(review_packet.get("body") or "").encode("utf-8")).hexdigest(),
        "approval_provenance": str(approval_provenance or ""),
        "send_hold_graduation_ref": str(send_hold_graduation_ref or ""),
    }
    if attachment_binding:
        exact_payload.update(attachment_binding)
    if test_binding:
        exact_payload.update(test_binding)
    ttl_seconds = _ttl_seconds_until(expires_at, generated_at=generated_at)
    created = hitl_action_service.create_operator_action_approval_request(
        action_type=hitl_action_service.ACTION_TYPE_EXACT_GMAIL_SEND,
        owner_agent="cassandra",
        owner_objective_id=objective_id,
        request_id=request_id,
        summary=(
            f"TEST loopback Gmail send to {exact_payload['recipient']} with one hash-bound PDF."
            if test_binding
            else f"Exact Gmail send to {exact_payload['recipient']} with reviewed subject."
        ),
        payload=exact_payload,
        risk_warning=(
            "This approval executes one TEST-loopback email to winshiplive@gmail.com with the hash-bound PDF."
            if test_binding
            else "This approval sends exactly one email if the Cassandra exact-send gate executes it."
        ),
        expires_at=expires_at,
        route_back={
            "type": "cassandra_exact_send_executor",
            "objective_id": objective_id,
            "request_id": request_id,
            "executor_must_use_reviewed_gate": True,
            "guardian_calls_gmail_or_broker_directly": False,
            "test_loopback_only": bool(test_binding),
            "test_recipient_lock": str(test_binding.get("test_recipient_lock") or ""),
            "test_loopback_binding_hash": str(test_binding.get("test_loopback_binding_hash") or ""),
        },
        ttl_seconds=ttl_seconds,
    )
    return {
        **created,
        "operator_action_created": True,
        "response_status": "OPERATOR_ACTION_APPROVAL_REQUEST_CREATED",
        "exact_send_request_id": request_id,
        "objective_id": objective_id,
        "recipient": exact_payload["recipient"],
        "subject": exact_payload["subject"],
        "payload_hash": payload_hash,
        "expires_at": expires_at,
        "authority_envelope_ref": exact_payload["authority_envelope_ref"],
        "credential_lease_ref": exact_payload["credential_lease_ref"],
        "guardian_delivered": False,
        "execution_performed": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_exact_send_approval_decision_from_operator_action(
    action: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Convert an approved HITL operator action into an exact-send decision."""
    generated_at = generated_at or utc_now()
    payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
    exact_payload = payload.get("payload") if isinstance(payload.get("payload"), Mapping) else {}
    request_id = str(payload.get("request_id") or exact_payload.get("request_id") or action.get("idempotency_key") or "")
    objective_id = str(payload.get("owner_objective_id") or exact_payload.get("objective_id") or "")
    payload_hash = str(exact_payload.get("payload_hash") or "")
    expires_at = str(exact_payload.get("expires_at") or payload.get("expires_at") or "")
    approved = bool(action.get("status") == "APPROVED" and request_id and payload_hash)
    reason = "approved_via_operator_action" if approved else "operator_action_not_approved_or_incomplete"
    attachment_binding: dict[str, Any] = {}
    try:
        attachment_binding = _validated_exact_send_attachment_binding(exact_payload)
    except ValueError:
        approved = False
        reason = "invalid_attachment_binding"
    test_binding: dict[str, Any] = {}
    if exact_payload.get("test_loopback_only") is True:
        try:
            test_binding = _validated_exact_send_test_loopback_binding(exact_payload)
        except ValueError:
            approved = False
            reason = "invalid_test_loopback_attachment_binding"
    if approved and _timestamp_expired(expires_at, generated_at=generated_at):
        approved = False
        reason = "expired_request"
    return {
        "schema_version": EXACT_SEND_APPROVAL_DECISION_SCHEMA,
        "approved": approved,
        "reason": reason,
        "request_id": request_id,
        "expected_request_id": request_id,
        "objective_id": objective_id,
        "payload_hash": payload_hash,
        "supplied_payload_hash": payload_hash,
        **attachment_binding,
        **test_binding,
        "expires_at": expires_at,
        "approval_parser": "operator_action_approval_request",
        "parser_provenance": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
        "operator_action_id": str(action.get("action_id") or ""),
        "approval_source": str(exact_payload.get("approval_provenance") or "guardian_hitl_action_queue"),
        "approved_by": str(action.get("approved_by") or ""),
        "approved_at": str(action.get("approved_at") or ""),
        "execution_performed": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "calendar_api_called": False,
        "contacts_api_called": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def run_exact_send_operator_action_routeback(
    action: Mapping[str, Any],
    *,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    receipt_dir: Path | str | None = None,
    transport: Any = None,
    live_transport_enabled: bool = True,
    live_db_execution_policy: str = EXACT_SEND_LIVE_DB_POLICY_FRESH_EXACT_APPROVAL_ONLY,
    send_hold_path: Path | str = DEFAULT_SEND_HOLD_PATH,
    send_hold_alert_sink: Any = None,
    send_hold_missing_is_tamper: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Route an approved HITL exact-send action into Cassandra's exact-send gate."""
    generated_at = generated_at or utc_now()
    action_id = str(action.get("action_id") or "")
    action_type = str(action.get("action_type") or "")
    payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
    route_back = payload.get("route_back") if isinstance(payload.get("route_back"), Mapping) else {}
    exact_payload = payload.get("payload") if isinstance(payload.get("payload"), Mapping) else {}
    request_id = str(payload.get("request_id") or action.get("idempotency_key") or "")
    objective_id = str(payload.get("owner_objective_id") or route_back.get("objective_id") or "")
    if receipt_dir is None:
        safe_request = re.sub(r"[^A-Za-z0-9_.:-]+", "_", request_id or action_id or "unknown")
        receipt_dir = Path("/tmp/openclaw-mission-control/exact_send_hitl_routeback_v0") / safe_request

    def refused(reason: str) -> dict[str, Any]:
        send_hold_active = reason == "send_hold_active"
        gate_convergence = convergence_for_surface(
            "exact_gmail_send",
            send_hold_active=send_hold_active,
            approval_status=str(action.get("status") or ""),
            approval_receipt_ref=(
                f"hitl_pending_store:{action_id}#decision_receipt"
                if action_id and isinstance(action.get("decision_receipt"), Mapping)
                else None
            ),
        )
        receipt = _exact_send_refusal_receipt(
            schema_version=EXACT_SEND_LIVE_TRANSPORT_REFUSAL_RECEIPT_SCHEMA,
            response_status="EXACT_SEND_LIVE_TRANSPORT_REFUSED",
            reason=reason,
            request_id=request_id,
            objective_id=objective_id,
            generated_at=generated_at,
            transport_mode="operator_action_routeback",
            broker_agent=GOOGLE_BROKER_AGENT_CASSANDRA,
            broker_capability=GOOGLE_GMAIL_SEND_BROKER_CAPABILITY,
            broker_called=False,
            fake_broker_called=False,
        )
        if send_hold_active:
            receipt.update(
                {
                    "send_hold_active": True,
                    "send_hold_ref": str(send_hold_path),
                    "gate_convergence": gate_convergence,
                }
            )
        receipt_path = _write_exact_send_receipt(receipt_dir, "exact_send_hitl_routeback_refusal_receipt", receipt)
        result = {
            "schema_version": "EXACT_SEND_HITL_ROUTEBACK_RESULT_V0",
            "response_status": "EXACT_SEND_HITL_ROUTEBACK_REFUSED",
            "refusal_reason": reason,
            "operator_action_id": action_id,
            "request_id": request_id,
            "objective_id": objective_id,
            "receipt": receipt,
            "refusal_receipt_path": receipt_path.as_posix(),
            "execution_performed": False,
            "gmail_api_called": False,
            "email_send_performed": False,
        }
        if send_hold_active:
            result.update(
                {
                    "send_hold_active": True,
                    "send_hold_ref": str(send_hold_path),
                    "gate_convergence": gate_convergence,
                }
            )
        return result

    if action_type != "exact_gmail_send":
        return refused("wrong_action_type")
    if str(action.get("status") or "") != "APPROVED":
        return refused("operator_action_not_approved")
    if not request_id or str(action.get("idempotency_key") or request_id) != request_id:
        return refused("request_id_idempotency_mismatch")
    if route_back.get("type") != "cassandra_exact_send_executor":
        return refused("route_back_not_cassandra_exact_send_executor")
    send_hold_state = ensure_send_hold_sentinel(
        send_hold_path,
        alert_sink=send_hold_alert_sink,
        missing_is_tamper=send_hold_missing_is_tamper,
    )
    send_hold_graduation: dict[str, Any] | None = None
    if send_hold_state.send_hold_active:
        graduation_ref = str(exact_payload.get("send_hold_graduation_ref") or "")
        if not graduation_ref:
            return refused("send_hold_active")
        try:
            from send_hold_scoped_graduation import verify_send_hold_scoped_graduation

            send_hold_graduation = verify_send_hold_scoped_graduation(
                graduation_path=graduation_ref,
                send_hold_path=send_hold_path,
                request_id=request_id,
                payload_hash=str(exact_payload.get("payload_hash") or ""),
                recipient=str(exact_payload.get("recipient") or ""),
                body_sha256=str(exact_payload.get("body_sha256") or ""),
                attachment_paths=[str(item) for item in exact_payload.get("attachments") or []],
                attachment_sha256=[str(item) for item in exact_payload.get("attachment_sha256") or []],
                observed_at=generated_at,
                consume=False,
            )
        except Exception:
            return refused("send_hold_scoped_graduation_invalid")

    approval_decision = build_exact_send_approval_decision_from_operator_action(
        action,
        generated_at=generated_at,
    )
    if transport is None:
        transport = GovernedGmailBrokerSendTransport(
            live_transport_enabled=live_transport_enabled,
            send_hold_graduation_ref=str(exact_payload.get("send_hold_graduation_ref") or ""),
        )
    result = run_exact_send_live_transport_gate(
        sqlite_path=sqlite_path,
        objective_id=objective_id,
        approval_decision=approval_decision,
        receipt_dir=receipt_dir,
        transport=transport,
        live_transport_enabled=live_transport_enabled,
        live_db_execution_policy=live_db_execution_policy,
        generated_at=generated_at,
    )
    return {
        "schema_version": "EXACT_SEND_HITL_ROUTEBACK_RESULT_V0",
        "response_status": str(result.get("response_status") or ""),
        "operator_action_id": action_id,
        "request_id": request_id,
        "objective_id": objective_id,
        "approval_decision": approval_decision,
        **result,
        "send_hold_graduation": send_hold_graduation,
        "guardian_calls_gmail_or_broker_directly": False,
    }


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
        "approval_parser": "parse_exact_send_approval",
        "parser_provenance": "parse_exact_send_approval",
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
    request_recipient = str(request.get("recipient") or "")
    request_subject = str(request.get("subject") or "")
    if not recipient or not subject or not body:
        return None, {
            "reason": "stored_draft_body_missing",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": recipient or str(request.get("recipient") or ""),
            "subject": subject or str(request.get("subject") or ""),
            "expected_payload_hash": str(request.get("payload_hash") or ""),
        }
    if request_recipient and request_recipient.casefold() != recipient.casefold():
        return None, {
            "reason": "request_recipient_artifact_recipient_mismatch",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": request_recipient,
            "subject": request_subject or subject,
            "expected_payload_hash": str(request.get("payload_hash") or ""),
        }
    if request_subject and request_subject != subject:
        return None, {
            "reason": "request_subject_artifact_subject_mismatch",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": request_recipient or recipient,
            "subject": request_subject,
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
    attachment_binding: dict[str, Any] = {}
    try:
        attachment_binding = _validated_exact_send_attachment_binding(request)
    except ValueError:
        return None, {
            "reason": "invalid_attachment_binding",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": recipient,
            "subject": subject,
            "expected_payload_hash": expected_hash,
        }
    for field in ("attachments", "attachment_sha256", "attachment_binding_hash"):
        if approval_decision.get(field) != attachment_binding.get(field):
            return None, {
                "reason": "attachment_approval_binding_mismatch",
                "request_id": request_id,
                "objective_id": objective_id,
                "recipient": recipient,
                "subject": subject,
                "expected_payload_hash": expected_hash,
            }
    test_binding: dict[str, Any] = {}
    if request.get("test_loopback_only") is True:
        try:
            test_binding = _validated_exact_send_test_loopback_binding(request)
        except ValueError:
            return None, {
                "reason": "invalid_test_loopback_attachment_binding",
                "request_id": request_id,
                "objective_id": objective_id,
                "recipient": recipient,
                "subject": subject,
                "expected_payload_hash": expected_hash,
            }
        for field in (
            "test_loopback_only",
            "test_recipient_lock",
            "attachments",
            "attachment_sha256",
            "test_loopback_binding_hash",
        ):
            if approval_decision.get(field) != test_binding.get(field):
                return None, {
                    "reason": "test_loopback_approval_binding_mismatch",
                    "request_id": request_id,
                    "objective_id": objective_id,
                    "recipient": recipient,
                    "subject": subject,
                    "expected_payload_hash": expected_hash,
                }
    elif approval_decision.get("test_loopback_only") is True:
        return None, {
            "reason": "unexpected_test_loopback_approval_binding",
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": recipient,
            "subject": subject,
            "expected_payload_hash": expected_hash,
        }
    state = {
        "objective": objective,
        "request": dict(request),
        "draft_artifact": artifact,
        "request_id": request_id,
        "objective_id": objective_id,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "payload_hash": expected_hash,
        "observed_payload_hash": observed_hash,
        "expires_at": expires_at,
        "authority_refs": list(objective.get("authority_refs") or []),
        "credential_lease_refs": list(objective.get("credential_lease_refs") or []),
        **attachment_binding,
        **test_binding,
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exact_send_execution_attempts (
          request_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          status TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          terminal_receipt_ref TEXT NOT NULL DEFAULT '',
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
        try:
            attachment_binding = _validated_exact_send_attachment_binding(payload)
            test_binding = _validated_exact_send_test_loopback_binding(payload)
        except ValueError as exc:
            return {
                "ok": False,
                "reason": f"invalid_test_loopback_attachment_binding: {exc}",
                "broker_called": False,
                "fake_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": bool(self.live_transport_enabled),
            }
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

    def __init__(
        self,
        *,
        live_transport_enabled: bool = False,
        broker_call: Any = None,
        send_hold_graduation_ref: str = "",
    ) -> None:
        super().__init__(live_transport_enabled=live_transport_enabled)
        self._broker_call = broker_call
        self.send_hold_graduation_ref = str(send_hold_graduation_ref or "")

    def send_exact_payload(
        self,
        payload: Mapping[str, Any],
        *,
        authority_refs: Sequence[str] = (),
        credential_lease_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        try:
            attachment_binding = _validated_exact_send_attachment_binding(payload)
            test_binding = _validated_exact_send_test_loopback_binding(payload)
        except ValueError as exc:
            return {
                "ok": False,
                "reason": f"invalid_test_loopback_attachment_binding: {exc}",
                "broker_called": False,
                "fake_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": bool(self.live_transport_enabled),
            }
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
            "idempotency_key": str(payload.get("request_id") or ""),
            "exact_send_request_id": str(payload.get("request_id") or ""),
            "send_hold_graduation_ref": self.send_hold_graduation_ref,
            "approval_context": {
                "request_id": str(payload.get("request_id") or ""),
                "objective_id": str(payload.get("objective_id") or ""),
                "payload_hash": str(payload.get("payload_hash") or ""),
                "idempotency_key": str(payload.get("request_id") or ""),
                "authority_refs": list(authority_refs),
                "credential_lease_refs": list(credential_lease_refs),
                "exact_send_gate": True,
                "send_hold_graduation_ref": self.send_hold_graduation_ref,
            },
        }
        if attachment_binding:
            broker_params.update(
                {
                    "attachments": list(attachment_binding["attachments"]),
                    "attachment_sha256": list(attachment_binding["attachment_sha256"]),
                }
            )
        if test_binding:
            broker_params["approval_context"].update(
                {
                    "test_loopback_only": True,
                    "test_recipient_lock": test_binding["test_recipient_lock"],
                    "test_loopback_binding_hash": test_binding["test_loopback_binding_hash"],
                }
            )
        broker_call = self._broker_call
        if broker_call is None:
            broker_module = __import__("google_access_broker")
            broker_call = getattr(broker_module, "call")
        self.broker_called = True
        result = broker_call(self.broker_agent, self.broker_capability, broker_params)
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
            "live_broker_called": True,
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

    def __init__(self, *, mode: str = "success", before_result: Any = None) -> None:
        super().__init__(live_transport_enabled=True, broker_call=None)
        self.calls: list[dict[str, Any]] = []
        self.mode = mode
        self.before_result = before_result

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
                "idempotency_key": str(payload.get("request_id") or ""),
                "exact_send_request_id": str(payload.get("request_id") or ""),
                "approval_context": {
                    "request_id": str(payload.get("request_id") or ""),
                    "objective_id": str(payload.get("objective_id") or ""),
                    "idempotency_key": str(payload.get("request_id") or ""),
                },
            },
        }
        self.calls.append(call)
        self.broker_called = True
        if callable(self.before_result):
            self.before_result(dict(payload), self)
        if self.mode == "exception":
            raise RuntimeError("fixture broker exception before definitive send result")
        if self.mode == "timeout":
            return {
                "ok": False,
                "reason": "broker_timeout",
                "timeout": True,
                "broker_agent": self.broker_agent,
                "broker_capability": self.broker_capability,
                "credential_handle_id": self.credential_handle_id,
                "authority_refs": list(authority_refs),
                "credential_lease_refs": list(credential_lease_refs),
                "broker_called": True,
                "fake_broker_called": True,
                "live_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": True,
                "payload_hash": str(payload.get("payload_hash") or ""),
                "idempotency_key": str(payload.get("request_id") or ""),
                "fixture_only": True,
            }
        if self.mode == "ambiguous":
            return {
                "ok": None,
                "reason": "broker_result_ambiguous",
                "ambiguous": True,
                "broker_agent": self.broker_agent,
                "broker_capability": self.broker_capability,
                "credential_handle_id": self.credential_handle_id,
                "authority_refs": list(authority_refs),
                "credential_lease_refs": list(credential_lease_refs),
                "broker_called": True,
                "fake_broker_called": True,
                "live_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": True,
                "payload_hash": str(payload.get("payload_hash") or ""),
                "idempotency_key": str(payload.get("request_id") or ""),
                "fixture_only": True,
            }
        if self.mode == "failure":
            return {
                "ok": False,
                "reason": "fake_broker_failure",
                "broker_agent": self.broker_agent,
                "broker_capability": self.broker_capability,
                "credential_handle_id": self.credential_handle_id,
                "authority_refs": list(authority_refs),
                "credential_lease_refs": list(credential_lease_refs),
                "broker_called": True,
                "fake_broker_called": True,
                "live_broker_called": False,
                "gmail_api_called": False,
                "email_send_performed": False,
                "live_transport_enabled": True,
                "payload_hash": str(payload.get("payload_hash") or ""),
                "idempotency_key": str(payload.get("request_id") or ""),
                "fixture_only": True,
            }
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
            "broker_called": True,
            "fake_broker_called": True,
            "live_broker_called": False,
            "gmail_api_called": False,
            "email_send_performed": True,
            "live_transport_enabled": True,
            "payload_hash": str(payload.get("payload_hash") or ""),
            "idempotency_key": str(payload.get("request_id") or ""),
            "message_id": message_id,
            "thread_id": "",
            "fixture_only": True,
        }


def _is_allowlisted_exact_send_transport(transport: Any) -> bool:
    return type(transport) in {GovernedGmailBrokerSendTransport, FakeBrokerGmailSendTransport}


def _exact_send_terminal_outcome(transport_result: Mapping[str, Any]) -> str:
    if str(transport_result.get("exception_type") or ""):
        return "exception"
    reason = str(transport_result.get("reason") or "").lower()
    if transport_result.get("ok") is True:
        return "success"
    if transport_result.get("timeout") is True or "timeout" in reason:
        return "timeout"
    if transport_result.get("ambiguous") is True or transport_result.get("ok") not in {True, False}:
        return "ambiguous"
    return "failure"


def _exact_send_terminal_response_status(outcome: str) -> str:
    return {
        "success": "EXACT_SEND_LIVE_TRANSPORT_SUCCESS_RECEIPT_WRITTEN",
        "failure": "EXACT_SEND_LIVE_TRANSPORT_FAILURE_RECEIPT_WRITTEN",
        "exception": "EXACT_SEND_LIVE_TRANSPORT_EXCEPTION_RECEIPT_WRITTEN",
        "timeout": "EXACT_SEND_LIVE_TRANSPORT_TIMEOUT_RECEIPT_WRITTEN",
        "ambiguous": "EXACT_SEND_LIVE_TRANSPORT_AMBIGUOUS_RECEIPT_WRITTEN",
    }.get(outcome, "EXACT_SEND_LIVE_TRANSPORT_FAILURE_RECEIPT_WRITTEN")


def _exact_send_prior_attempt_refusal_reason(status: str) -> str:
    if status == "success":
        return "replay_detected"
    if status == "in_flight":
        return "execution_in_flight_requires_reconciliation"
    return "terminal_attempt_requires_reconciliation"


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
    terminal_outcome = _exact_send_terminal_outcome(transport_result)
    transport_ok = terminal_outcome == "success"
    response_status = _exact_send_terminal_response_status(terminal_outcome)
    idempotency_key = str(transport_result.get("idempotency_key") or request_id)
    return {
        "schema_version": EXACT_SEND_LIVE_TRANSPORT_TERMINAL_RECEIPT_SCHEMA,
        "receipt_id": "exact_send_live_transport_terminal_receipt:" + _short_hash(
            request_id,
            state.get("payload_hash"),
            terminal_outcome,
            transport_result.get("message_id"),
            generated_at,
        ),
        "response_status": response_status,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "objective_id": objective_id,
        "recipient": str(state.get("recipient") or ""),
        "subject": str(state.get("subject") or ""),
        "payload_hash": str(state.get("payload_hash") or ""),
        "observed_payload_hash": str(state.get("observed_payload_hash") or ""),
        "test_loopback_only": bool(state.get("test_loopback_only")),
        "test_recipient_lock": str(state.get("test_recipient_lock") or ""),
        "attachments": list(state.get("attachments") or []),
        "attachment_sha256": list(state.get("attachment_sha256") or []),
        "test_loopback_binding_hash": str(state.get("test_loopback_binding_hash") or ""),
        "expires_at": str(state.get("expires_at") or ""),
        "authority_refs": list(state.get("authority_refs") or []),
        "credential_lease_refs": list(state.get("credential_lease_refs") or []),
        "broker_agent": str(transport_result.get("broker_agent") or GOOGLE_BROKER_AGENT_CASSANDRA),
        "broker_capability": str(transport_result.get("broker_capability") or GOOGLE_GMAIL_SEND_BROKER_CAPABILITY),
        "credential_handle_id": str(transport_result.get("credential_handle_id") or GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID),
        "message_id": str(transport_result.get("message_id") or ""),
        "thread_id": str(transport_result.get("thread_id") or ""),
        "terminal_outcome": terminal_outcome,
        "attempt_status": terminal_outcome,
        "transport_ok": transport_ok,
        "transport_reason": str(transport_result.get("reason") or ""),
        "exception_type": str(transport_result.get("exception_type") or ""),
        "exception_message": str(transport_result.get("exception_message") or ""),
        "requires_reconciliation": terminal_outcome in {"failure", "exception", "timeout", "ambiguous"},
        "fixture_only_transport": fixture_only_transport,
        "broker_called": bool(transport_result.get("broker_called")),
        "fake_broker_called": bool(transport_result.get("fake_broker_called")),
        "live_broker_called": bool(
            transport_result.get(
                "live_broker_called",
                bool(transport_result.get("broker_called")) and not bool(transport_result.get("fake_broker_called")),
            )
        ),
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
    live_db_execution_policy: str = EXACT_SEND_LIVE_DB_POLICY_FIXTURE_ONLY,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    execution_observed_at = utc_now()
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

    parser_pair = (
        str(approval_decision.get("approval_parser") or ""),
        str(approval_decision.get("parser_provenance") or ""),
    )
    allowed_parser_pairs = {
        ("parse_exact_send_approval", "parse_exact_send_approval"),
        ("operator_action_approval_request", OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA),
    }
    if (
        str(approval_decision.get("schema_version") or "") != EXACT_SEND_APPROVAL_DECISION_SCHEMA
        or parser_pair not in allowed_parser_pairs
    ):
        return refuse("approval_parser_provenance_required")
    if str(approval_decision.get("expected_request_id") or "") != str(approval_decision.get("request_id") or ""):
        return refuse("approval_request_id_binding_required")
    if not approval_decision.get("approved"):
        return refuse(str(approval_decision.get("reason") or "approval_not_valid"))

    live_db = _is_live_objective_db(sqlite_path)
    if live_db and live_db_execution_policy != EXACT_SEND_LIVE_DB_POLICY_FRESH_EXACT_APPROVAL_ONLY:
        return refuse("live_objective_db_refused")
    if live_db and request_id in OBSOLETE_EXACT_SEND_REQUEST_IDS:
        return refuse("obsolete_live_request_refused")

    with _connect(sqlite_path) as conn:
        _ensure_exact_send_fixture_tables(conn)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        try:
            state, error = _load_exact_send_execution_state(
                conn,
                objective_id=objective_id,
                approval_decision=approval_decision,
                generated_at=execution_observed_at,
            )
            if error:
                conn.rollback()
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
                conn.rollback()
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
            prior_attempt = conn.execute(
                "SELECT status FROM exact_send_execution_attempts WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if prior_attempt:
                conn.rollback()
                return refuse(
                    _exact_send_prior_attempt_refusal_reason(str(prior_attempt["status"] or "")),
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
                conn.rollback()
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
                conn.rollback()
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
                conn.rollback()
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
            in_flight_receipt = {
                "schema_version": "EXACT_SEND_EXECUTION_ATTEMPT_IN_FLIGHT_V0",
                "request_id": request_id,
                "idempotency_key": request_id,
                "objective_id": objective_id,
                "status": "in_flight",
                "payload_hash": str(state.get("payload_hash") or ""),
                "created_at": generated_at,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
            conn.execute(
                """
                INSERT INTO exact_send_execution_attempts
                  (request_id, objective_id, status, idempotency_key, created_at, updated_at, terminal_receipt_ref, receipt_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, objective_id, "in_flight", request_id, generated_at, generated_at, "", stable_json(in_flight_receipt)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        broker_payload = {
            "request_id": request_id,
            "objective_id": objective_id,
            "recipient": str(state.get("recipient") or ""),
            "subject": str(state.get("subject") or ""),
            "body": str(state.get("body") or ""),
            "payload_hash": str(state.get("payload_hash") or ""),
            "expires_at": str(state.get("expires_at") or ""),
        }
        if state.get("attachments"):
            broker_payload.update(
                {
                    "attachments": list(state.get("attachments") or []),
                    "attachment_sha256": list(state.get("attachment_sha256") or []),
                    "attachment_binding_hash": str(state.get("attachment_binding_hash") or ""),
                }
            )
        if state.get("test_loopback_only") is True:
            broker_payload.update(
                {
                    "test_loopback_only": True,
                    "test_recipient_lock": str(state.get("test_recipient_lock") or ""),
                    "test_loopback_binding_hash": str(state.get("test_loopback_binding_hash") or ""),
                }
            )
        try:
            transport_result = transport.send_exact_payload(
                broker_payload,
                authority_refs=authority_refs,
                credential_lease_refs=credential_lease_refs,
            )
        except Exception as exc:
            transport_result = {
                "ok": False,
                "reason": "transport_exception",
                "exception_type": type(exc).__name__,
                "exception_message": _excerpt(str(exc), limit=160),
                "broker_agent": GOOGLE_BROKER_AGENT_CASSANDRA,
                "broker_capability": GOOGLE_GMAIL_SEND_BROKER_CAPABILITY,
                "credential_handle_id": GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID,
                "authority_refs": authority_refs,
                "credential_lease_refs": credential_lease_refs,
                "broker_called": bool(getattr(transport, "broker_called", False)),
                "fake_broker_called": bool(getattr(transport, "calls", [])),
                "live_broker_called": bool(getattr(transport, "broker_called", False)) and not bool(getattr(transport, "calls", [])),
                "gmail_api_called": False,
                "email_send_performed": False,
                "payload_hash": str(state.get("payload_hash") or ""),
                "idempotency_key": request_id,
            }
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
            else f"exact_send_live_transport_{terminal_receipt['terminal_outcome']}_receipt"
        )
        terminal_receipt_path = _write_exact_send_receipt(receipt_dir, receipt_prefix, terminal_receipt)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE exact_send_execution_attempts
            SET status = ?, updated_at = ?, terminal_receipt_ref = ?, receipt_json = ?
            WHERE request_id = ?
            """,
            (
                str(terminal_receipt.get("attempt_status") or terminal_receipt.get("terminal_outcome") or "failure"),
                generated_at,
                str(terminal_receipt.get("receipt_id") or ""),
                stable_json(terminal_receipt),
                request_id,
            ),
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
                f"{terminal_receipt['terminal_outcome']}_recorded",
                stable_json(terminal_receipt),
            ),
        )
        conn.commit()
        return {
            "schema_version": "EXACT_SEND_LIVE_TRANSPORT_GATE_RESULT_V0",
            "response_status": str(terminal_receipt["response_status"]),
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
