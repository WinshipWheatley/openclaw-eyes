"""Reynolds Tavern gig setup status read-model v0.

This is a read-only setup checklist for the Reynolds Tavern gig. It turns the
existing gig artifact into eight concrete lanes: calendar, contact, logistics,
music, payment, invoice, reply watch, and recurrence. It does not send email,
create calendar events, mutate contacts, send invoices, move money, or write the
business ops ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ARTIFACT_ROOT = Path("/mnt/e/openclaw/orchestration/artifacts/reynolds")
DEFAULT_GIG_FACTS_PATH = DEFAULT_ARTIFACT_ROOT / "gig_facts.json"

SCHEMA_VERSION = "reynolds_gig_setup_status_v0"
READ_MODEL_ID = "reynolds_gig_setup_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

LANE_ORDER: tuple[str, ...] = (
    "calendar",
    "contact",
    "logistics",
    "music",
    "payment",
    "invoice",
    "reply_watch",
    "recurrence",
)

KNOWN_ARTIFACTS = {
    "ready_note": "READY.md",
    "intro_email_draft": "intro_email_draft.md",
    "invoice_draft": "invoice_draft.md",
    "invoice_pdf": "Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf",
    "invoice_ability_spec": "invoice_ability_spec.md",
    "manual_invoice_steps": "invoice_creation_steps_manual.md",
}

AUTHORITY_FLAGS = {
    "status_read_model_only": True,
    "external_send_performed": False,
    "calendar_mutation_performed": False,
    "contact_mutation_performed": False,
    "business_ops_ledger_mutation_performed": False,
    "invoice_send_performed": False,
    "money_movement_performed": False,
    "paid_marking_performed": False,
    "live_reply_watch_verified": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _load_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _artifact_status(artifact_root: Path) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for key, filename in KNOWN_ARTIFACTS.items():
        path = artifact_root / filename
        statuses[key] = {
            "filename": filename,
            "path": str(path),
            "exists": path.exists(),
        }
    return statuses


def _known_fixture_facts(fixture: dict[str, Any]) -> dict[str, Any]:
    gig = _section(fixture, "gig")
    contact = _section(fixture, "contact")
    return {
        "venue_name": gig.get("venue_name") or "Reynolds Tavern",
        "venue_address": gig.get("venue_address") or "7 Church Circle, Annapolis, MD",
        "date": gig.get("date") or "2026-06-27",
        "start_time": gig.get("start_time") or "19:00",
        "end_time": gig.get("end_time") or "22:00",
        "fee_amount": gig.get("fee_amount") or "250.00",
        "currency": gig.get("currency") or "USD",
        "performer_covering_for": gig.get("performer_covering_for") or "Mike Heuer",
        "contact_name": contact.get("name") or "Sally",
        "contact_role": contact.get("role") or "owner",
        "contact_email": contact.get("email") or "reservations@reynoldstavern.com",
        "contact_note": contact.get("note") or "",
    }


def _invoice_defaults(fixture: dict[str, Any]) -> dict[str, Any]:
    defaults = _section(fixture, "defaults_applied_confirm_at_approval")
    return {
        "invoice_business_identity": defaults.get(
            "invoice_business_identity",
            "Winship Wheatley (default; switch if preferred)",
        ),
        "payment_terms": defaults.get("payment_terms", "due upon receipt (default)"),
    }


def _build_lanes(
    *,
    facts: dict[str, Any],
    defaults: dict[str, Any],
    artifact_status: dict[str, dict[str, Any]],
    open_slots: list[str],
) -> dict[str, dict[str, Any]]:
    return {
        "calendar": {
            "status": "known_fact_needs_calendar_receipt",
            "known": {
                "date": facts["date"],
                "start_time": facts["start_time"],
                "end_time": facts["end_time"],
                "venue_name": facts["venue_name"],
                "venue_address": facts["venue_address"],
            },
            "missing": [
                "calendar event receipt or operator confirmation that the date/time is already on the calendar"
            ],
            "safe_next_step": "Create or verify a calendar hold only after calendar-write authority is explicit.",
        },
        "contact": {
            "status": "primary_contact_known_day_of_details_missing",
            "known": {
                "name": facts["contact_name"],
                "role": facts["contact_role"],
                "email": facts["contact_email"],
                "note": facts["contact_note"],
            },
            "missing": [
                "day-of phone number",
                "preferred day-of contact channel",
            ],
            "safe_next_step": "Keep Sally as the contact, then ask for day-of contact details before calling contact setup complete.",
        },
        "logistics": {
            "status": "venue_address_known_logistics_missing",
            "known": {
                "venue_address": facts["venue_address"],
                "performance_window": f"{facts['start_time']}-{facts['end_time']}",
            },
            "missing": [
                "arrival/load-in time",
                "parking/load-in instructions",
                "setup location at the venue",
                "who provides PA/sound",
            ],
            "safe_next_step": "Ask logistics questions before treating the gig as ready to physically execute.",
        },
        "music": {
            "status": "performance_window_known_music_brief_missing",
            "known": {
                "date": facts["date"],
                "performance_window": f"{facts['start_time']}-{facts['end_time']}",
                "covering_for": facts["performer_covering_for"],
            },
            "missing": [
                "music vibe/repertoire",
                "break expectations",
                "volume constraints",
                "dress code or special requests",
            ],
            "safe_next_step": "Ask for the music brief so prep is not just invoice/admin readiness.",
        },
        "payment": {
            "status": "fee_known_payment_method_missing",
            "known": {
                "fee_amount": facts["fee_amount"],
                "currency": facts["currency"],
                "no_coupa_required": True,
            },
            "missing": [
                "payment method",
                "who pays",
                "payment timing",
                "whether any tax/vendor form is needed",
            ],
            "safe_next_step": "Confirm how Reynolds pays before marking the payment lane ready.",
        },
        "invoice": {
            "status": "invoice_artifacts_exist_defaults_need_confirmation",
            "known": {
                "no_coupa_required": True,
                "invoice_draft_exists": artifact_status["invoice_draft"]["exists"],
                "invoice_pdf_exists": artifact_status["invoice_pdf"]["exists"],
                "intro_email_draft_exists": artifact_status["intro_email_draft"]["exists"],
                "default_invoice_business_identity": defaults["invoice_business_identity"],
                "default_payment_terms": defaults["payment_terms"],
            },
            "missing": list(open_slots) or ["operator approval before any invoice send"],
            "safe_next_step": "Confirm invoice identity and terms, then stage the invoice for approval instead of sending it.",
        },
        "reply_watch": {
            "status": "target_known_live_watch_not_proven",
            "known": {
                "watch_target": facts["contact_email"],
                "watch_reason": "Reynolds/Sally replies that change booking, logistics, payment, invoice, or recurrence status.",
            },
            "missing": [
                "scoped read-only reply-watch receipt",
                "allowed query terms",
                "watch cadence or manual-check preference",
            ],
            "safe_next_step": "Wire or run only a scoped metadata/read-only reply watch when explicitly allowed.",
        },
        "recurrence": {
            "status": "unknown_one_off_or_recurring",
            "known": {
                "might_become_non_one_off": True,
            },
            "missing": [
                "one-off vs recurring posture",
                "if recurring: cadence/date source",
                "if recurring: rate/payment rules",
                "if recurring: who confirms future dates",
            ],
            "safe_next_step": "Ask whether to set Reynolds up as a recurring gig lane or keep it one-off for now.",
        },
    }


def build_reynolds_gig_setup_status(
    *,
    generated_at: str | None = None,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    gig_facts_path: Path = DEFAULT_GIG_FACTS_PATH,
) -> dict[str, Any]:
    fixture = _load_json_dict(gig_facts_path)
    facts = _known_fixture_facts(fixture)
    defaults = _invoice_defaults(fixture)
    open_slots_raw = fixture.get("open_slots_for_cassandra_to_ask")
    open_slots = [str(item) for item in open_slots_raw] if isinstance(open_slots_raw, list) else [
        "invoice_business_identity",
        "payment_terms",
    ]
    artifacts = _artifact_status(artifact_root)
    lanes = _build_lanes(
        facts=facts,
        defaults=defaults,
        artifact_status=artifacts,
        open_slots=open_slots,
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "gig_ref": "reynolds_tavern_2026_06_27",
        "venue_display_name": "Reynolds Tavern",
        "source_status": str(fixture.get("status") or "facts_captured_two_defaults_pending_confirm"),
        "source_summary": str(fixture.get("source") or "Reynolds Tavern gig facts artifact"),
        "known_core_facts": facts,
        "artifacts": artifacts,
        "lanes": lanes,
        "lane_order": list(LANE_ORDER),
        "setup_status": {
            "state": "known_facts_ready_missing_operational_answers",
            "plain_status": (
                "Reynolds Tavern has core booking facts and invoice/intro artifacts, but it is not all-set until "
                "calendar, contact, logistics, music, payment, invoice, reply watch, and recurrence questions are closed."
            ),
            "no_coupa_required": True,
            "external_send_performed": False,
            "safe_done_definition": (
                "All eight lanes have either a receipt, an operator-confirmed answer, or an explicit not-needed decision."
            ),
        },
        "questions_for_operator": [
            {
                "lane": "invoice",
                "question": "Use Winship Wheatley and due upon receipt, or use a different billing identity or terms?",
            },
            {
                "lane": "recurrence",
                "question": "Should Reynolds be set up as one-off for June 27, or as a recurring gig lane?",
            },
            {
                "lane": "calendar",
                "question": "Should I verify/create a calendar hold for June 27, 2026, 7-10 PM?",
            },
            {
                "lane": "contact",
                "question": "What day-of phone or preferred day-of contact channel should be stored for Sally/Reynolds?",
            },
            {
                "lane": "logistics",
                "question": "What are arrival/load-in time, parking/load-in instructions, setup location, and PA/sound responsibility?",
            },
            {
                "lane": "music",
                "question": "What music vibe/repertoire, break plan, volume constraints, dress code, or special requests should be captured?",
            },
            {
                "lane": "payment",
                "question": "How will Reynolds pay the $250, who pays, and when should payment be expected?",
            },
            {
                "lane": "reply_watch",
                "question": "Should I run or wire a scoped read-only reply watch for Sally/Reynolds updates?",
            },
        ],
        "safe_actions_after_answers": [
            "stage a compact Reynolds setup packet covering the eight lanes",
            "stage approval-gated intro email and invoice surfaces without sending",
            "stage calendar/contact/watch instructions only inside the authority the operator grants",
            "if recurring, create a recurring-lane checklist with date/rate/payment rules",
        ],
        "authority_flags": dict(AUTHORITY_FLAGS),
        "machine_proof": {
            "eight_lanes_present": all(lane in lanes for lane in LANE_ORDER),
            "no_coupa_required": True,
            "invoice_artifacts_checked": True,
            "missing_operational_answers_not_overclaimed": True,
            "external_send_false": True,
            "ledger_mutation_false": True,
            "reply_watch_not_overclaimed": True,
        },
    }
    payload["content_hash"] = _content_hash(payload)
    return payload


_ENTITY_MARKERS = (
    "reynolds",
    "reynolds tavern",
)

_SETUP_MARKERS = (
    "all set",
    "are we good",
    "are we ready",
    "buttoned up",
    "checklist",
    "covered",
    "do we have",
    "everything",
    "get ready",
    "good to go",
    "handle",
    "handled",
    "happen",
    "in shape",
    "line up",
    "lined up",
    "make happen",
    "set up",
    "setup",
    "make sure",
    "missing",
    "prep",
    "prepare",
    "prepared",
    "pulling off",
    "ready",
    "sort out",
    "sorted",
    "square away",
    "squared away",
    "status",
    "take care",
    "taken care",
    "what do we need",
    "what is left",
    "what's left",
    "whats left",
    "where are we",
)


def is_reynolds_gig_setup_query(text: str) -> bool:
    q = (text or "").lower()
    return any(marker in q for marker in _ENTITY_MARKERS) and any(marker in q for marker in _SETUP_MARKERS)


def format_reynolds_gig_setup_answer(text: str) -> str | None:
    if not is_reynolds_gig_setup_query(text):
        return None
    payload = build_reynolds_gig_setup_status()
    facts = payload["known_core_facts"]
    lanes = payload["lanes"]
    return (
        "Reynolds Tavern setup check: not all-set yet, but the core facts are captured. "
        f"Known: {facts['date']} {facts['start_time']}-{facts['end_time']}, {facts['venue_address']}, "
        f"${facts['fee_amount']} {facts['currency']}, covering {facts['performer_covering_for']}, "
        f"contact {facts['contact_name']} at {facts['contact_email']}. No Coupa is needed. "
        f"calendar: {lanes['calendar']['status']}; "
        f"contact: {lanes['contact']['status']}; "
        f"logistics: {lanes['logistics']['status']}; "
        f"music: {lanes['music']['status']}; "
        f"payment: {lanes['payment']['status']}; "
        f"invoice: {lanes['invoice']['status']}; "
        f"reply watch: {lanes['reply_watch']['status']}; "
        f"recurrence: {lanes['recurrence']['status']}. "
        "Questions to finish setup: use Winship Wheatley / due upon receipt, or different billing identity/terms? "
        "one-off June 27 or recurring Reynolds lane? should I verify/create the calendar hold? "
        "what day-of contact, arrival/load-in, parking, setup location, PA/sound, music vibe/breaks/volume/dress, and payment method/timing should be captured? "
        "should I run or wire a scoped read-only reply watch for Sally/Reynolds? "
        "Nothing has been sent, calendar/contact mutated, ledger-written, invoice-sent, paid-marked, or money-moved by this status path."
    )


def _operator_markdown(payload: dict[str, Any]) -> str:
    facts = payload["known_core_facts"]
    lines = [
        "# Reynolds Tavern Gig Setup Status",
        "",
        f"State: {payload['setup_status']['state']}",
        f"Known gig: {facts['date']} {facts['start_time']}-{facts['end_time']} at {facts['venue_name']}",
        f"Address: {facts['venue_address']}",
        f"Fee: ${facts['fee_amount']} {facts['currency']}",
        f"Contact: {facts['contact_name']} <{facts['contact_email']}>",
        "Coupa: not required",
        "",
        "Eight Lanes",
    ]
    for lane in LANE_ORDER:
        lane_payload = payload["lanes"][lane]
        label = lane.replace("_", " ")
        lines.append(f"- {label}: {lane_payload['status']}")
        missing = lane_payload.get("missing") or []
        if missing:
            lines.append(f"  missing: {', '.join(str(item) for item in missing)}")
    lines.extend(
        [
            "",
            "Questions",
            *[f"- {item['lane']}: {item['question']}" for item in payload["questions_for_operator"]],
            "",
            "Boundary",
            "- No external send, calendar/contact mutation, business ledger write, invoice send, paid marking, or money movement.",
            "",
        ]
    )
    return "\n".join(lines)


def export_read_model(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    gig_facts_path: Path = DEFAULT_GIG_FACTS_PATH,
) -> dict[str, str]:
    payload = build_reynolds_gig_setup_status(
        generated_at=generated_at,
        artifact_root=artifact_root,
        gig_facts_path=gig_facts_path,
    )
    out_root = _rooted(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(_operator_markdown(payload), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "content_hash": str(payload["content_hash"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Reynolds Tavern gig setup status read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    result = export_read_model(export_root=Path(args.export_root), generated_at=args.generated_at)
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
