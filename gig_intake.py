"""Deterministic Cassandra gig-intake helper.

This module is local-only glue for the compose/gate spine. It extracts booking
facts, stores a session snapshot through chief_session_manager, and emits
approval-gated compose packets. It does not send email, generate invoices,
call external APIs, or execute packet surfaces.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from business_ops_ledger import append_event, append_packet_receipt, init_business_ops_ledger, record_canonical_fact


GIG_INTAKE_VERSION = "gig_intake_v0"
WORKFLOW_NAME = "gig_intake"
REQUIRED_GIG_SLOTS: tuple[str, ...] = (
    "venue_name",
    "venue_address",
    "date",
    "start_time",
    "end_time",
    "fee_amount",
    "currency",
    "contact_name",
    "contact_email",
    "invoice_business_identity",
    "payment_terms",
    "deliverables",
)
RISKY_CONFIRMATION_SLOTS: tuple[str, ...] = ("fee_amount", "contact_email")
DEFAULTS_REQUIRING_CONFIRMATION: dict[str, str] = {
    "invoice_business_identity": "Winship Wheatley",
    "payment_terms": "due upon receipt",
}
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class GigIntakeState:
    status: str
    fields: dict[str, Any]
    missing_slots: tuple[str, ...]
    slots_to_ask: tuple[str, ...]
    confirmation_slots: tuple[str, ...]
    follow_up_question: str
    deliverables: tuple[dict[str, Any], ...]
    source_summary: str
    no_send_performed: bool = True
    no_invoice_sent: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": GIG_INTAKE_VERSION,
            "status": self.status,
            "fields": dict(self.fields),
            "missing_slots": list(self.missing_slots),
            "slots_to_ask": list(self.slots_to_ask),
            "confirmation_slots": list(self.confirmation_slots),
            "follow_up_question": self.follow_up_question,
            "deliverables": [dict(item) for item in self.deliverables],
            "source_summary": self.source_summary,
            "no_send_performed": self.no_send_performed,
            "no_invoice_sent": self.no_invoice_sent,
        }


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _stable_id(prefix: str, payload: Any) -> str:
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _fixture_section(fixture: dict[str, Any] | None, section: str) -> dict[str, Any]:
    if isinstance(fixture, dict) and isinstance(fixture.get(section), dict):
        return dict(fixture[section])
    return {}


def booking_text_from_fixture(fixture: dict[str, Any]) -> str:
    gig = _fixture_section(fixture, "gig")
    contact = _fixture_section(fixture, "contact")
    return (
        f"You're all set at {gig.get('venue_name')} on {gig.get('date')} "
        f"{gig.get('start_time')}-{gig.get('end_time')} for ${gig.get('fee_amount')} "
        f"covering {gig.get('performer_covering_for')}. Contact {contact.get('name')} "
        f"at {contact.get('email')}. Address: {gig.get('venue_address')}."
    )


def _parse_date(text: str) -> str | None:
    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if iso:
        return iso.group(0)
    month_match = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(20\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if not month_match:
        return None
    month = MONTHS[month_match.group(1).lower().rstrip(".")]
    day = int(month_match.group(2))
    year = int(month_match.group(3))
    return datetime(year, month, day).strftime("%Y-%m-%d")


def _to_24_hour(hour_text: str, minute_text: str | None, ampm: str | None) -> str:
    hour = int(hour_text)
    minute = int(minute_text or "0")
    suffix = (ampm or "").lower()
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _parse_time_range(text: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"\b(?P<start>\d{1,2})(?::(?P<start_min>\d{2}))?\s*(?P<start_ampm>am|pm)?\s*(?:-|–|to)\s*(?P<end>\d{1,2})(?::(?P<end_min>\d{2}))?\s*(?P<end_ampm>am|pm)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"\b(?P<start>\d{1,2})(?::(?P<start_min>\d{2}))?\s*(?P<start_ampm>am|pm)\s*(?:-|–|to)\s*(?P<end>\d{1,2})(?::(?P<end_min>\d{2}))?\s*(?P<end_ampm>am|pm)?\b",
            text,
            re.IGNORECASE,
        )
    if not match:
        return None, None
    start_ampm = match.group("start_ampm") or match.group("end_ampm")
    end_ampm = match.group("end_ampm") or match.group("start_ampm")
    return (
        _to_24_hour(match.group("start"), match.group("start_min"), start_ampm),
        _to_24_hour(match.group("end"), match.group("end_min"), end_ampm),
    )


def _parse_amount(text: str) -> str | None:
    match = re.search(r"\$\s*(\d{1,6})(?:\.(\d{1,2}))?", text)
    if not match:
        match = re.search(r"\b(\d{2,6})(?:\.(\d{1,2}))?\s*(?:usd|dollars?)\b", text, re.IGNORECASE)
    if not match:
        return None
    dollars = int(match.group(1))
    cents = int((match.group(2) or "00").ljust(2, "0")[:2])
    return f"{dollars}.{cents:02d}"


def _extract_contact_email(text: str) -> str | None:
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)
    return match.group(0) if match else None


def _extract_contact_name(text: str) -> str | None:
    match = re.search(r"\bcontact\s+([A-Z][a-z]+)\b", text)
    if match:
        return match.group(1)
    match = re.search(r"\b([A-Z][a-z]+)\s+(?:at|owns|owner)\b", text)
    return match.group(1) if match else None


def _extract_covering_for(text: str) -> str | None:
    match = re.search(r"\bcovering(?:\s+for)?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text)
    return match.group(1) if match else None


def _extract_venue_name(text: str) -> str | None:
    if re.search(r"\breynolds(?:\s+tavern)?\b", text, re.IGNORECASE):
        return "Reynolds Tavern"
    match = re.search(r"\bat\s+([A-Z][A-Za-z0-9&' ]+?)(?:\s+on\s+|\s+\d{1,2}[/-]|\s+for\s+\$|,)", text)
    return _clean_text(match.group(1)) if match else None


def _extract_address(text: str) -> str | None:
    match = re.search(r"\b\d{1,6}\s+[A-Z][A-Za-z0-9' .-]+,\s*[A-Z][A-Za-z .-]+,\s*[A-Z]{2}\b", text)
    if match:
        return match.group(0)
    if re.search(r"\breynolds(?:\s+tavern)?\b", text, re.IGNORECASE):
        return "7 Church Circle, Annapolis, MD"
    return None


def _value_from_fixture(fixture: dict[str, Any] | None, key: str) -> Any:
    gig = _fixture_section(fixture, "gig")
    contact = _fixture_section(fixture, "contact")
    mapping = {
        "venue_name": gig.get("venue_name"),
        "venue_address": gig.get("venue_address"),
        "date": gig.get("date"),
        "start_time": gig.get("start_time"),
        "end_time": gig.get("end_time"),
        "fee_amount": gig.get("fee_amount"),
        "currency": gig.get("currency"),
        "contact_name": contact.get("name"),
        "contact_email": contact.get("email"),
        "covering_for": gig.get("performer_covering_for"),
    }
    return mapping.get(key)


def _build_deliverables(fields: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    contact_name = fields.get("contact_name") or "the venue contact"
    contact_email = fields.get("contact_email")
    venue = fields.get("venue_name") or "the venue"
    start = fields.get("start_time")
    end = fields.get("end_time")
    date = fields.get("date")
    return (
        {
            "type": "intro_email",
            "to": f"{contact_name} ({contact_email})" if contact_email else contact_name,
            "purpose": f"introduce Winship as the cover for {fields.get('covering_for') or 'the gig'} on {date} {start}-{end}",
            "approval_required": True,
            "execution_allowed": False,
        },
        {
            "type": "invoice_send",
            "to": venue,
            "amount": fields.get("fee_amount"),
            "currency": fields.get("currency") or "USD",
            "for": f"live music performance, {date} {start}-{end}",
            "approval_required": True,
            "execution_allowed": False,
        },
    )


def _human_time_range(fields: dict[str, Any]) -> str:
    start = fields.get("start_time")
    end = fields.get("end_time")
    if not start or not end:
        return "the booked time"
    start_hour, start_minute = [int(part) for part in start.split(":")]
    end_hour, end_minute = [int(part) for part in end.split(":")]
    suffix = "PM" if end_hour >= 12 else "AM"
    display_start = start_hour - 12 if start_hour > 12 else start_hour
    display_end = end_hour - 12 if end_hour > 12 else end_hour
    return f"{display_start}:{start_minute:02d}-{display_end}:{end_minute:02d} {suffix}"


def _human_date(fields: dict[str, Any]) -> str:
    date = fields.get("date")
    if not date:
        return "the booked date"
    try:
        return datetime.strptime(date, "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return date


def _follow_up_question(fields: dict[str, Any], slots_to_ask: tuple[str, ...]) -> str:
    summary = (
        f"I have {fields.get('venue_name') or 'the venue'} on {_human_date(fields)}, "
        f"{_human_time_range(fields)} for ${fields.get('fee_amount') or 'the fee'}, "
        f"with {fields.get('contact_name') or 'the contact'} at {fields.get('contact_email') or 'the contact email'}."
    )
    if fields.get("covering_for"):
        summary += f" You are covering {fields['covering_for']}."
    if set(slots_to_ask) == {"invoice_business_identity", "payment_terms"}:
        return summary + " What name should go on the invoice, and is due upon receipt okay?"
    labels = {
        "invoice_business_identity": "the name that should go on the invoice",
        "payment_terms": "the payment terms",
        "venue_address": "the venue address",
        "contact_email": "the contact email",
        "fee_amount": "the fee",
    }
    missing = ", ".join(labels.get(slot, slot.replace("_", " ")) for slot in slots_to_ask)
    return summary + f" I still need {missing}."


def extract_gig_slots(text: str, fixture: dict[str, Any] | None = None) -> GigIntakeState:
    source_text = _clean_text(text)
    if not source_text:
        raise ValueError("gig intake text is required")

    start_time, end_time = _parse_time_range(source_text)
    fields: dict[str, Any] = {
        "venue_name": _extract_venue_name(source_text),
        "venue_address": _extract_address(source_text),
        "date": _parse_date(source_text),
        "start_time": start_time,
        "end_time": end_time,
        "fee_amount": _parse_amount(source_text),
        "currency": "USD" if "$" in source_text or re.search(r"\busd|dollars?\b", source_text, re.IGNORECASE) else None,
        "contact_name": _extract_contact_name(source_text),
        "contact_email": _extract_contact_email(source_text),
        "covering_for": _extract_covering_for(source_text),
    }
    for key in list(fields):
        if fields[key] in {"", None}:
            fixture_value = _value_from_fixture(fixture, key)
            if fixture_value not in {"", None}:
                fields[key] = fixture_value
    fields = {key: value for key, value in fields.items() if value not in {"", None}}
    fields["deliverables"] = list(_build_deliverables(fields))

    missing_slots = tuple(slot for slot in REQUIRED_GIG_SLOTS if not fields.get(slot))
    slots_to_ask = tuple(slot for slot in missing_slots if slot not in {"deliverables"})
    confirmation_slots = tuple(slot for slot in RISKY_CONFIRMATION_SLOTS if fields.get(slot))
    follow_up = _follow_up_question(fields, slots_to_ask)
    status = "needs_confirmation" if slots_to_ask or confirmation_slots else "ready_for_packet_handoff"
    return GigIntakeState(
        status=status,
        fields=fields,
        missing_slots=missing_slots,
        slots_to_ask=slots_to_ask,
        confirmation_slots=confirmation_slots,
        follow_up_question=follow_up,
        deliverables=tuple(fields["deliverables"]),
        source_summary=f"gig intake extracted from operator-provided booking text ({len(source_text)} chars)",
    )


def start_gig_intake_session(
    text: str,
    *,
    fixture: dict[str, Any] | None = None,
    persist_session: bool = True,
) -> GigIntakeState:
    state = extract_gig_slots(text, fixture=fixture)
    if persist_session:
        import chief_session_manager

        session = chief_session_manager.set_workflow(WORKFLOW_NAME, mode="slot_fill")
        session["fields"] = dict(state.fields)
        session["workflow_state"] = {
            "schema_version": GIG_INTAKE_VERSION,
            "status": state.status,
            "missing_slots": list(state.missing_slots),
            "slots_to_ask": list(state.slots_to_ask),
            "confirmation_slots": list(state.confirmation_slots),
            "deliverables": [dict(item) for item in state.deliverables],
            "no_send_performed": True,
            "no_invoice_sent": True,
        }
        session["last_question"] = state.follow_up_question
        chief_session_manager.save_session(session)
    return state


def confirm_gig_intake_slots(
    state: GigIntakeState | dict[str, Any],
    *,
    invoice_business_identity: str,
    payment_terms: str,
) -> GigIntakeState:
    payload = state.to_dict() if isinstance(state, GigIntakeState) else dict(state)
    fields = dict(payload["fields"])
    fields["invoice_business_identity"] = invoice_business_identity.strip()
    fields["payment_terms"] = payment_terms.strip()
    if not fields["invoice_business_identity"] or not fields["payment_terms"]:
        raise ValueError("invoice_business_identity and payment_terms are required before packet handoff")
    fields["deliverables"] = list(_build_deliverables(fields))
    missing = tuple(slot for slot in REQUIRED_GIG_SLOTS if not fields.get(slot))
    return GigIntakeState(
        status="ready_for_packet_handoff" if not missing else "needs_confirmation",
        fields=fields,
        missing_slots=missing,
        slots_to_ask=tuple(slot for slot in missing if slot not in {"deliverables"}),
        confirmation_slots=tuple(slot for slot in RISKY_CONFIRMATION_SLOTS if fields.get(slot)),
        follow_up_question="Ready to prepare the intro email and invoice approval cards.",
        deliverables=tuple(fields["deliverables"]),
        source_summary=str(payload.get("source_summary") or "gig intake confirmed by operator"),
    )


def record_gig_in_business_ops_ledger(
    state: GigIntakeState | dict[str, Any],
    *,
    db_path: str | Path | None = None,
    source_file: str | None = None,
    source_commit: str | None = None,
    source_description: str | None = None,
) -> dict[str, Any]:
    payload = state.to_dict() if isinstance(state, GigIntakeState) else dict(state)
    fields = payload["fields"]
    path = str(db_path) if db_path is not None else None
    init_business_ops_ledger(path)
    event_id = _stable_id("gig_intake", {
        "venue_name": fields.get("venue_name"),
        "date": fields.get("date"),
        "start_time": fields.get("start_time"),
        "end_time": fields.get("end_time"),
        "fee_amount": fields.get("fee_amount"),
    })
    summary = (
        f"Recorded candidate gig intake for {fields.get('venue_name')} on {fields.get('date')}; "
        "draft sends remain approval-gated."
    )
    event_ok = append_event(
        event_id=event_id,
        event_type="gig_intake_recorded",
        actor="cassandra",
        prompt_hash=hashlib.sha256(stable_json(fields).encode("utf-8")).hexdigest(),
        operator_visible_summary=summary,
        raw_sensitive_data_stored=False,
        replay_safe=True,
        db_path=path,
    )
    packet_id = f"{event_id}_packet"
    packet_ok = append_packet_receipt(
        {
            "packet_id": packet_id,
            "intent_name": "gig_intake",
            "request_category": "candidate_gig_record",
            "actor_name": "cassandra",
            "execution_authority": False,
            "approval_required": False,
            "approval_tier": None,
            "action_status": "candidate_gig_recorded_no_send",
            "safe_summary": {
                "venue_name": fields.get("venue_name"),
                "date": fields.get("date"),
                "start_time": fields.get("start_time"),
                "end_time": fields.get("end_time"),
                "fee_amount": fields.get("fee_amount"),
                "currency": fields.get("currency"),
                "deliverable_count": len(fields.get("deliverables") or []),
            },
            "email_send_performed": False,
            "invoice_send_performed": False,
        },
        event_id=event_id,
        db_path=path,
    )
    canonical_fact_id = _stable_id(
        "canonical_gig",
        {
            "venue_name": fields.get("venue_name"),
            "date": fields.get("date"),
            "start_time": fields.get("start_time"),
            "end_time": fields.get("end_time"),
        },
    )
    canonical_fact_text = (
        f"{fields.get('venue_name')} gig on {fields.get('date')} from "
        f"{fields.get('start_time')} to {fields.get('end_time')} for "
        f"{fields.get('currency') or 'USD'} {fields.get('fee_amount')}; "
        "candidate booking record from operator-provided source. "
        "Intro email and invoice remain pending approval; no send performed."
    )
    fact_ok = record_canonical_fact(
        fact_id=canonical_fact_id,
        source_file=source_file or "operator_provided_gig_intake",
        section_heading="gig_booking",
        source_commit=source_commit or "operator_provided_unversioned",
        fact_text=canonical_fact_text,
        sensitivity_class="operational_canonical",
        allowed_actors=["cassandra", "chief", "guardian", "winship"],
        doc_category="gig_intake",
        temporal_or_doctrine="event_specific",
        source_description=source_description or payload.get("source_summary") or "operator-provided gig intake",
        truth_source_id=event_id,
        truth_status="operator_reported_candidate",
        verification_required=1,
        verification_evidence_id=packet_id,
        db_path=path,
    )
    return {
        "db_path": path,
        "event_id": event_id,
        "packet_id": packet_id,
        "canonical_fact_id": canonical_fact_id,
        "recorded": bool(event_ok and packet_ok and fact_ok),
        "event_recorded": bool(event_ok),
        "packet_receipt_recorded": bool(packet_ok),
        "canonical_fact_recorded": bool(fact_ok),
    }


def emit_gig_handoff_packets(
    state: GigIntakeState | dict[str, Any],
    *,
    db_path: str | Path | None = None,
    source_channel: str = "gig_intake",
    requested_by: str = "winship",
    source_file: str | None = None,
    source_commit: str | None = None,
    source_description: str | None = None,
) -> dict[str, Any]:
    payload = state.to_dict() if isinstance(state, GigIntakeState) else dict(state)
    if payload.get("status") != "ready_for_packet_handoff":
        raise ValueError("gig intake must be confirmed before packet handoff")
    fields = payload["fields"]
    ledger_record = record_gig_in_business_ops_ledger(
        payload,
        db_path=db_path,
        source_file=source_file,
        source_commit=source_commit,
        source_description=source_description,
    )

    from chief_compose import compose

    intro_text = (
        f"Draft an intro email to {fields['contact_name']} at {fields['contact_email']} "
        f"introducing Winship as the cover for {fields.get('covering_for') or 'the performer'} "
        f"at {fields['venue_name']} on {fields['date']} from {fields['start_time']} to {fields['end_time']}."
    )
    invoice_text = (
        f"Send an invoice to {fields['venue_name']} for {fields['currency']} {fields['fee_amount']} "
        f"for live music performance on {fields['date']} from {fields['start_time']} to {fields['end_time']} "
        f"with payment terms {fields['payment_terms']}."
    )
    results = (
        ("intro_email", compose(intro_text, source_channel=source_channel, requested_by=requested_by, db_path=str(db_path) if db_path is not None else None)),
        ("invoice_send", compose(invoice_text, source_channel=source_channel, requested_by=requested_by, db_path=str(db_path) if db_path is not None else None)),
    )
    packets: list[dict[str, Any]] = []
    for deliverable_type, result in results:
        packets.append(
            {
                "deliverable_type": deliverable_type,
                "intent": result.intent,
                "gate_state": result.gate_state.value,
                "packet_id": result.packet_id,
                "pending_approval": result.pending_approval.to_dict() if result.pending_approval else None,
                "segments": list(result.segments),
                "execution_allowed": False,
                "send_performed": False,
            }
        )
    return {
        "schema_version": GIG_INTAKE_VERSION,
        "status": "packets_pending_approval",
        "ledger_record": ledger_record,
        "deliverable_packets": packets,
        "email_send_performed": False,
        "invoice_send_performed": False,
        "external_send_performed": False,
        "no_executor_registered": True,
    }
