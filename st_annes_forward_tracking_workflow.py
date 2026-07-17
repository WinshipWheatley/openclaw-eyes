"""St. Anne's Draper -> Glenn receivable tracking workflow.

This module advances a read model from observed evidence only. It does not
read Gmail directly, send email, post ledger entries, mark payment, or mutate
finance records.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from agent_voice_profiles import (
    loop_closing_ask_for_workflow,
    render_loop_closing_ask,
    require_clara_copy_conformance,
    voice_copy_rules_for_speaker,
)
from client_followup_watch import AUTHORITY_BOUNDARY_PROPOSAL
from contacts_registry import DEFAULT_CONTACTS_DB_PATH, ContactsRegistry


SCHEMA_VERSION = "st_annes_forward_tracking_workflow_v0"
READ_MODEL_ID = "st_annes_receivable_state"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CLIENT_REF = "st-annes"
CLIENT_DISPLAY_NAME = "St. Anne's"
WORKFLOW_REF = "st_annes_invoice_forward_tracking"
FOLLOWUP_SCHEMA_VERSION = "st_annes_forward_tracking_followup_v0"
FOLLOWUP_CADENCE_DAYS = 3
FOLLOWUP_DUE_AFTER_DAYS = 4

WINSHIP_CC_EMAILS = frozenset({"winshiplive@gmail.com"})

AUTHORITY_BOUNDARY = {
    "email_send_performed": False,
    "gmail_send_performed": False,
    "openclaw_send_performed": False,
    "ledger_mutation_performed": False,
    "ledger_post_performed": False,
    "paid_marking_performed": False,
    "payment_movement_performed": False,
    "draft_only": True,
    "send_hold_required": True,
    "guardian_required": True,
}

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_DRAPER_FORWARDED_RE = re.compile(r"\bforward(?:ed|ing)?\b", re.IGNORECASE)
_GLENN_RE = re.compile(r"\bglenn?\b|\btreasurer\b", re.IGNORECASE)


@dataclass(frozen=True)
class ExportResult:
    schema_version: str
    read_model_path: str
    status: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_aware_iso(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(value: object) -> str:
    return _parse_aware_iso(value).isoformat(timespec="seconds")


def _email_addresses(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {email.lower() for email in _EMAIL_RE.findall(value)}
    if isinstance(value, Mapping):
        return _email_addresses(value.get("email") or value.get("address") or "")
    if isinstance(value, Iterable):
        emails: set[str] = set()
        for item in value:
            emails.update(_email_addresses(item))
        return emails
    return {email.lower() for email in _EMAIL_RE.findall(str(value))}


def _body_text(message: Mapping[str, Any]) -> str:
    for key in ("body", "text", "plain_text", "snippet"):
        value = message.get(key)
        if value:
            return str(value)
    return ""


def _message_id(message: Mapping[str, Any]) -> str:
    return str(
        message.get("message_id")
        or message.get("id")
        or message.get("gmail_message_id")
        or ""
    )


def _thread_id(message: Mapping[str, Any]) -> str:
    return str(message.get("thread_id") or message.get("gmail_thread_id") or "")


def _message_time(message: Mapping[str, Any]) -> str:
    for key in (
        "received_at_utc_iso",
        "received_at",
        "date_utc_iso",
        "date",
        "internal_date_utc_iso",
    ):
        value = message.get(key)
        if value:
            return _iso(value)
    return "1970-01-01T00:00:00+00:00"


def _field_addresses(message: Mapping[str, Any], field: str) -> set[str]:
    return _email_addresses(message.get(field))


def _recipient_addresses(message: Mapping[str, Any]) -> set[str]:
    recipients: set[str] = set()
    for field in ("to", "cc", "bcc"):
        recipients.update(_field_addresses(message, field))
    return recipients


def _contact_emails(contact: Mapping[str, Any]) -> set[str]:
    emails = set(_email_addresses(contact.get("email")))
    emails.update(_email_addresses(contact.get("emails")))
    return emails


def _contact_info(contacts_db_path: str | None) -> dict[str, Any]:
    registry = ContactsRegistry(contacts_db_path or DEFAULT_CONTACTS_DB_PATH, seed=True)
    contacts = registry.get_contacts_for_client(CLIENT_REF)
    draper_emails: set[str] = set()
    glenn_emails: set[str] = set()
    draper_contact: dict[str, Any] | None = None
    glenn_contact: dict[str, Any] | None = None

    for contact in contacts:
        contact_id = str(contact.get("id") or "").lower()
        name = str(contact.get("name") or "").lower()
        role = str(contact.get("role") or "").lower()
        emails = _contact_emails(contact)
        if "draper" in contact_id or "draper" in name or "intermediary" in role:
            draper_emails.update(emails)
            draper_contact = dict(contact)
        if (
            "glenn" in contact_id
            or "glenn" in name
            or "treasurer" in role
            or "forward-to" in role
        ):
            glenn_emails.update(emails)
            glenn_contact = dict(contact)

    return {
        "contacts_source": contacts_db_path or DEFAULT_CONTACTS_DB_PATH,
        "draper_contact": draper_contact,
        "glenn_contact": glenn_contact,
        "draper_emails": draper_emails,
        "glenn_emails": glenn_emails,
        "winship_emails": set(WINSHIP_CC_EMAILS),
    }


def _sorted_messages(messages: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(messages, key=lambda message: (_message_time(message), _message_id(message)))


def _is_from(message: Mapping[str, Any], emails: set[str]) -> bool:
    return bool(_field_addresses(message, "from") & emails)


def _proof(
    *,
    signal: str,
    message: Mapping[str, Any],
    body_excerpt: str | None = None,
) -> dict[str, Any]:
    payload = {
        "signal": signal,
        "message_id": _message_id(message),
        "thread_id": _thread_id(message),
        "received_at_utc_iso": _message_time(message),
        "from": str(message.get("from") or ""),
        "to": sorted(_field_addresses(message, "to")),
        "cc": sorted(_field_addresses(message, "cc")),
    }
    if body_excerpt is not None:
        payload["body_excerpt"] = body_excerpt[:240]
    return payload


def _detect_forward(
    messages: Iterable[Mapping[str, Any]],
    contacts: Mapping[str, Any],
) -> dict[str, Any] | None:
    draper_emails = set(contacts["draper_emails"])
    glenn_emails = set(contacts["glenn_emails"])
    winship_emails = set(contacts["winship_emails"])

    secondary: dict[str, Any] | None = None
    for message in _sorted_messages(messages):
        if not _is_from(message, draper_emails):
            continue

        recipients = _recipient_addresses(message)
        cc = _field_addresses(message, "cc")
        if recipients & glenn_emails and cc & winship_emails:
            return _proof(
                signal="primary_cc_forward_to_glenn",
                message=message,
                body_excerpt=_body_text(message),
            )

        body = _body_text(message)
        if _DRAPER_FORWARDED_RE.search(body) and _GLENN_RE.search(body):
            secondary = _proof(
                signal="secondary_draper_forwarded_reply",
                message=message,
                body_excerpt=body,
            )

    return secondary


def _detect_ack(
    messages: Iterable[Mapping[str, Any]],
    contacts: Mapping[str, Any],
    forward_proof: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, str]:
    glenn_emails = set(contacts["glenn_emails"])
    forward_thread = str((forward_proof or {}).get("thread_id") or "")
    candidates = [
        message for message in _sorted_messages(messages) if _is_from(message, glenn_emails)
    ]
    if forward_thread:
        threaded = [message for message in candidates if _thread_id(message) == forward_thread]
        if threaded:
            candidates = threaded

    if not candidates:
        return None, ""

    message = candidates[0]
    body = _body_text(message)
    return (
        _proof(signal="glenn_acknowledgement", message=message, body_excerpt=body),
        body,
    )


def _followup_draft(step: str, invoice_ref: str) -> dict[str, str]:
    signoff = str(voice_copy_rules_for_speaker("clara")["signoff"])
    closure = loop_closing_ask_for_workflow(WORKFLOW_REF, client_ref=CLIENT_REF)
    if step == "forward_to_glenn":
        return {
            "to": "draper.carter@gmail.com",
            "subject": f"Following up: {invoice_ref}",
            "body": (
                "Hi Draper,\n\n"
                "I'm checking in on the St. Anne's invoice. If there are any issues, "
                "I'm happy to help.\n\n"
                + render_loop_closing_ask(closure)
                + "\n\n"
                + signoff
            ),
        }
    return {
        "to": "draper.carter@gmail.com",
        "subject": f"Following up with Glenn: {invoice_ref}",
        "body": (
            "Hi Draper,\n\n"
            "I'm checking in on the St. Anne's invoice. If Glenn has any issues or questions, "
            "I'm happy to help.\n\n"
            + render_loop_closing_ask(closure)
            + "\n\n"
            + signoff
        ),
    }


def _follow_up(
    *,
    step: str | None,
    baseline_at_utc_iso: str | None,
    now_utc_iso: str,
    invoice_ref: str,
) -> dict[str, Any]:
    if not step or not baseline_at_utc_iso:
        return {
            "schema_version": FOLLOWUP_SCHEMA_VERSION,
            "status": "NOT_REQUIRED",
            "cadence_days": FOLLOWUP_CADENCE_DAYS,
            "proposal": None,
        }

    baseline = _parse_aware_iso(baseline_at_utc_iso)
    due_at = baseline + timedelta(days=FOLLOWUP_DUE_AFTER_DAYS)
    now = _parse_aware_iso(now_utc_iso)
    status = "FOLLOW_UP_DUE" if now >= due_at else "NOT_DUE"
    payload: dict[str, Any] = {
        "schema_version": FOLLOWUP_SCHEMA_VERSION,
        "status": status,
        "step": step,
        "cadence_days": FOLLOWUP_CADENCE_DAYS,
        "due_at_utc_iso": due_at.isoformat(timespec="seconds"),
        "proposal": None,
    }
    if status == "FOLLOW_UP_DUE":
        draft = _followup_draft(step, invoice_ref)
        clara_conformance = require_clara_copy_conformance(
            draft["body"],
            workflow_ref=WORKFLOW_REF,
            client_ref=CLIENT_REF,
        )
        voice_conformance = clara_conformance["voice_conformance"]
        payload["proposal"] = {
            "schema_version": "st_annes_followup_proposal_v0",
            "status": "FOLLOW_UP_PROPOSAL_READY",
            "step": step,
            "invoice_ref": invoice_ref,
            "draft": draft,
            "voice_profile_ref": voice_conformance["voice_profile_ref"],
            "voice_conformance": voice_conformance,
            "loop_closing_ask_conformance": clara_conformance["loop_closing_ask"],
            "gated": True,
            "send_performed": False,
            "authority_boundary": {
                **dict(AUTHORITY_BOUNDARY_PROPOSAL),
                "guardian_required": True,
                "send_hold_required": True,
            },
        }
    return payload


def advance_st_annes_receivable_state(
    *,
    sent_receipt: Mapping[str, Any],
    messages: Iterable[Mapping[str, Any]],
    contacts_db_path: str | None = None,
    generated_at_utc_iso: str | None = None,
    previous_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance the St. Anne's read model from observed send and email evidence."""

    generated_at = _iso(generated_at_utc_iso or _utc_now_iso())
    message_list = list(messages)
    contacts = _contact_info(contacts_db_path)
    sent = bool(sent_receipt.get("ok"))
    invoice_ref = str(sent_receipt.get("invoice_ref") or "st_annes_invoice").strip()
    sent_at = _iso(sent_receipt.get("sent_at_utc_iso")) if sent else None
    invoice_status = str(
        sent_receipt.get("invoice_status") or ("SENT" if sent else "NOT_SENT")
    )
    recipient = str(
        sent_receipt.get("recipient") or "draper.carter@gmail.com"
    ).strip()
    cc = [str(item) for item in sent_receipt.get("cc") or []]
    subject = str(
        sent_receipt.get("subject") or f"Invoice {invoice_ref}"
    ).strip()
    provenance = str(sent_receipt.get("provenance") or "").strip()
    send_proof = {
        "signal": "send_receipt_ok" if sent else "send_receipt_missing",
        "proof_ref": str(sent_receipt.get("proof_ref") or ""),
        "sent_at_utc_iso": sent_at,
        "provenance": provenance,
        "operator_authorized": sent_receipt.get("operator_authorized") is True,
        "gmail_message_id": str(sent_receipt.get("gmail_message_id") or ""),
        "recipient": recipient,
        "cc": cc,
    }

    forward_proof = _detect_forward(message_list, contacts) if sent else None
    ack_proof, glenn_note = (
        _detect_ack(message_list, contacts, forward_proof)
        if sent
        else (None, "")
    )
    if ack_proof and not forward_proof:
        forward_proof = {
            **ack_proof,
            "signal": "forward_proven_by_glenn_acknowledgement",
        }
    forwarded_at = str((forward_proof or {}).get("received_at_utc_iso") or "") or None
    acknowledged_at = str((ack_proof or {}).get("received_at_utc_iso") or "") or None

    if not sent:
        workflow_stage = "awaiting_send"
        followup_step = None
        followup_baseline = None
    elif not forward_proof:
        workflow_stage = "awaiting_forward_to_glenn"
        followup_step = "forward_to_glenn"
        followup_baseline = sent_at
    elif not ack_proof:
        workflow_stage = "awaiting_glenn_ack"
        followup_step = "glenn_ack"
        followup_baseline = forwarded_at
    else:
        workflow_stage = "awaiting_payment"
        followup_step = None
        followup_baseline = None

    follow_up = _follow_up(
        step=followup_step,
        baseline_at_utc_iso=followup_baseline,
        now_utc_iso=generated_at,
        invoice_ref=invoice_ref,
    )
    due_at = str(follow_up.get("due_at_utc_iso") or "")
    surface_flags = {
        "awaiting_send": "AWAITING_ST_ANNES_SEND",
        "awaiting_forward_to_glenn": "AWAITING_DRAPER_FORWARD_TO_GLENN",
        "awaiting_glenn_ack": "AWAITING_GLENN_ACKNOWLEDGMENT",
        "awaiting_payment": "AWAITING_PAYMENT_PROOF",
    }
    unknown_pending = {"status": "UNKNOWN", "state": "pending"}
    milestones = {
        "sent_to_draper": (
            {"status": "PROVEN", "state": "recorded", "proof_ref": send_proof["proof_ref"]}
            if sent
            else dict(unknown_pending)
        ),
        "draper_forwarded_to_glenn": (
            {
                "status": "PROVEN",
                "state": "observed",
                "proof_ref": str((forward_proof or {}).get("message_id") or ""),
            }
            if forward_proof
            else dict(unknown_pending)
        ),
        "glenn_acknowledged": (
            {
                "status": "PROVEN",
                "state": "observed",
                "proof_ref": str((ack_proof or {}).get("message_id") or ""),
            }
            if ack_proof
            else dict(unknown_pending)
        ),
        "check_received": dict(unknown_pending),
        "invoice_paid": dict(unknown_pending),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at_utc_iso": generated_at,
        "client_ref": CLIENT_REF,
        "client_display_name": CLIENT_DISPLAY_NAME,
        "workflow_ref": WORKFLOW_REF,
        "invoice_ref": invoice_ref,
        "invoice_status": invoice_status,
        "recipient": recipient,
        "cc": cc,
        "subject": subject,
        "send_provenance": provenance,
        "operator_authorized": sent_receipt.get("operator_authorized") is True,
        "ar_expected_receivable_ref": f"expected_receivable:{invoice_ref}",
        "sent": sent,
        "sent_at_utc_iso": sent_at,
        "forwarded_to_glenn": forward_proof is not None,
        "forwarded_at_utc_iso": forwarded_at,
        "glenn_acknowledged": ack_proof is not None,
        "acknowledged_at_utc_iso": acknowledged_at,
        "glenn_note": glenn_note,
        "workflow_stage": workflow_stage,
        "operator_surface_flag": surface_flags[workflow_stage],
        "payment_status": "NOT_MARKED_PAID",
        "paid": False,
        "check_received": False,
        "milestones": milestones,
        "monitoring": {
            "status": "ARMED" if followup_step else "NOT_ARMED",
            "step": followup_step or "",
            "due_at_utc_iso": due_at,
            "local_observed_messages_only": True,
            "auto_send": False,
        },
        "payment_check_cadence": {
            "status": "NOT_ARMED_AWAITING_GLENN_ACK",
            "normal_mail_check_window": "15th-20th",
            "defer_when_glenn_ack_after_day": 10,
            "money_state_mutated": False,
        },
        "send_proof": send_proof,
        "forward_proof": forward_proof,
        "ack_proof": ack_proof,
        "follow_up": follow_up,
        "observed_message_count": len(message_list),
        "contacts_source": contacts["contacts_source"],
        "draper_contact_id": (contacts.get("draper_contact") or {}).get("id"),
        "glenn_contact_id": (contacts.get("glenn_contact") or {}).get("id"),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "previous_state_ref": str((previous_state or {}).get("read_model_id") or ""),
    }


def export_st_annes_receivable_state(
    state: Mapping[str, Any],
    *,
    export_root: str | Path = Path("generated/read_models"),
) -> ExportResult:
    export_dir = Path(export_root)
    export_dir.mkdir(parents=True, exist_ok=True)
    read_model_path = export_dir / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(dict(state)), encoding="utf-8")
    return ExportResult(
        schema_version=SCHEMA_VERSION,
        read_model_path=str(read_model_path),
        status="EXPORTED",
    )


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CLIENT_REF",
    "ExportResult",
    "JSON_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "advance_st_annes_receivable_state",
    "export_st_annes_receivable_state",
    "stable_json",
]
