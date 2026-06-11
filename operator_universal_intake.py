"""Universal Operator Intake v0.

This module turns low-risk operator text into local receipts, a generated read
model, and Watch Desk items. It does not approve, execute, send, call live
services, mutate external systems, or mark invoices paid.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
OPERATOR_INTAKE_SCHEMA_VERSION = "OPERATOR_INTAKE_EVENT_V0"
READ_MODEL_VERSION = "operator_intake_events_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_RECEIPT_ROOT = Path("/tmp/openclaw-mission-control/openclaw_universal_operator_intake_v0/receipts")
JSON_EXPORT_NAME = "operator_intake_events.json"

SUPPORTED_SURFACES = (
    "telegram",
    "mac_composer",
    "voice_stt",
    "watch_desk",
    "app_card",
    "local_cli",
)
SUPPORTED_ACTION_TYPES = (
    "income_payment_log",
    "expense_log",
    "gig_event_log",
    "identity_signature_preference",
)

SURFACE_WIRING_STATUS = {
    "local_api": True,
    "telegram_cassandra_route_hook": True,
    "telegram_live_listener_restart_required": True,
    "mac_composer_callable_contract": True,
    "mac_composer_live_bridge": False,
}

AUTHORITY_BOUNDARY = {
    "external_calls_performed": False,
    "approval_request_created": False,
    "email_sent": False,
    "gmail_draft_created": False,
    "gmail_or_broker_called": False,
    "calendar_contacts_called": False,
    "coupa_bank_external_ledger_mutated": False,
    "workbook_pdf_browser_apple_mail_called": False,
    "daw_or_media_session_mutated": False,
    "invoice_marked_paid": False,
    "tax_or_legal_advice_given": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return ROOT / path_obj


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:20]}"


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _canonical_received_at(value: str | None) -> str:
    return _parse_datetime(value).isoformat()


def _normalized_text(text: str) -> str:
    return " ".join(text.replace("\u2019", "'").replace("\u2018", "'").strip().split())


def _lower_text(text: str) -> str:
    return _normalized_text(text).lower()


def _mentions_st_annes(text: str) -> bool:
    lower = _lower_text(text)
    return "st. anne" in lower or "st anne" in lower or "anne's" in lower or "annes" in lower


def _amount_value(value: str) -> int | float:
    amount = float(value.replace(",", ""))
    if amount.is_integer():
        return int(amount)
    return amount


def _amount_display(value: int | float) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return f"${int(value)}"
    return f"${value:.2f}"


def _clean_phrase(value: str) -> str:
    return value.strip().strip(" .!?;:")


def _today_date(received_at_utc: str | None) -> str:
    return _parse_datetime(received_at_utc).date().isoformat()


def _date_fields(text: str, received_at_utc: str | None) -> dict[str, str]:
    lower = _lower_text(text)
    explicit = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", lower)
    if explicit:
        return {"event_date": explicit.group(0), "date_basis": "explicit_iso_date"}
    if "tonight" in lower:
        return {"event_date": _today_date(received_at_utc), "date_basis": "implied_tonight"}
    if "today" in lower:
        return {"event_date": _today_date(received_at_utc), "date_basis": "implied_today"}
    return {"event_date": _today_date(received_at_utc), "date_basis": "default_received_date"}


def _recent_gig_match(payer: str, session_context: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not session_context or not _mentions_st_annes(payer):
        return None
    recent = session_context.get("recent_gigs")
    if not isinstance(recent, list):
        return None
    for candidate in reversed(recent):
        if not isinstance(candidate, Mapping):
            continue
        parsed = candidate.get("parsed") if isinstance(candidate.get("parsed"), Mapping) else {}
        fields = parsed.get("fields") if isinstance(parsed.get("fields"), Mapping) else {}
        venue = str(fields.get("venue") or candidate.get("venue") or "")
        if _mentions_st_annes(venue):
            return {
                "associated_gig_intake_id": str(candidate.get("intake_id") or ""),
                "associated_gig_date": str(fields.get("event_date") or candidate.get("event_date") or ""),
            }
    return None


def _base_parse_result() -> dict[str, Any]:
    return {
        "parsed": {
            "action_type": "unknown",
            "lane": "operator_intake",
            "fields": {},
            "confidence": 0.2,
        },
        "risk_tier": "low",
        "normalized_summary": "Needs clarification before OpenClaw can classify this intake.",
        "needs_clarification": ["action_type"],
        "referent_refs": [],
        "proposed_actions": [],
        "stop_condition": "clarification_required",
    }


def parse_operator_intake_text(
    raw_text: str,
    *,
    received_at_utc: str | None = None,
    session_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse supported low-risk operator text without side effects."""

    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text is required")

    text = _normalized_text(raw_text)
    lower = text.lower()

    sign_match = re.search(r"\bsign\s+(this|that|it)\s+as\s+(.+?)\.?$", text, flags=re.IGNORECASE)
    if sign_match:
        requested_identity = _clean_phrase(sign_match.group(2))
        referent = sign_match.group(1).lower()
        return {
            "parsed": {
                "action_type": "identity_signature_preference",
                "lane": "chief_identity",
                "fields": {
                    "requested_identity": requested_identity,
                    "scope": "local_signature_preference_pending_referent",
                    "outbound_identity_change_allowed": False,
                    "referent_required": True,
                },
                "confidence": 0.82,
            },
            "risk_tier": "low",
            "normalized_summary": f"Need the target item before staging signature preference as {requested_identity}.",
            "needs_clarification": [f"referent:{referent}"],
            "referent_refs": [],
            "proposed_actions": ["clarify_referent"],
            "stop_condition": "clarification_required",
        }

    start_using = re.search(r"\bstart\s+using\s+(.+?)\.?$", text, flags=re.IGNORECASE)
    if start_using:
        requested_identity = _clean_phrase(start_using.group(1))
        return {
            "parsed": {
                "action_type": "identity_signature_preference",
                "lane": "chief_identity",
                "fields": {
                    "requested_identity": requested_identity,
                    "scope": "local_display_or_stage_preference_only",
                    "outbound_email_from_name_change_allowed": False,
                    "public_or_legal_identity_change_allowed": False,
                    "clarification_required_before_external_identity_change": True,
                },
                "confidence": 0.86,
            },
            "risk_tier": "low",
            "normalized_summary": f"Staged local identity preference: use {requested_identity} for local display/stage context.",
            "needs_clarification": [],
            "referent_refs": [],
            "proposed_actions": ["record_local_identity_preference_stage"],
            "stop_condition": "local_receipt_written",
        }

    income_match = re.search(r"\b(?:got\s+)?paid\s+\$?([\d,]+(?:\.\d+)?)\s+from\s+(.+)$", text, flags=re.IGNORECASE)
    if income_match:
        amount = _amount_value(income_match.group(1))
        payer = _clean_phrase(income_match.group(2))
        if _mentions_st_annes(payer):
            payer = "St. Anne's"
        association = _recent_gig_match(payer, session_context)
        fields: dict[str, Any] = {
            "amount": amount,
            "currency": "USD",
            "payer": payer,
            "local_receipt_only": True,
            "invoice_marked_paid": False,
            "external_ledger_mutated": False,
            "missing": ["invoice/project link", "payment method"],
        }
        if association:
            fields.update(association)
        return {
            "parsed": {
                "action_type": "income_payment_log",
                "lane": "cassandra_finance",
                "fields": fields,
                "confidence": 0.9,
            },
            "risk_tier": "low",
            "normalized_summary": f"Logged income: {_amount_display(amount)} from {payer}.",
            "needs_clarification": ["invoice/project link", "payment method"],
            "referent_refs": [association["associated_gig_intake_id"]] if association and association.get("associated_gig_intake_id") else [],
            "proposed_actions": ["record_local_income_payment_receipt"],
            "stop_condition": "local_receipt_written",
        }

    expense_match = re.search(r"\bspent\s+\$?([\d,]+(?:\.\d+)?)\s+on\s+(.+?)(?:[.!?]|$)", text, flags=re.IGNORECASE)
    if expense_match:
        amount = _amount_value(expense_match.group(1))
        purchase = _clean_phrase(expense_match.group(2))
        vendor = purchase
        product = purchase
        category = "expense"
        if "claude code" in purchase.lower():
            vendor = "Claude Code"
            product = "Fable 5" if "fable 5" in purchase.lower() else purchase
            category = "AI tools/software"
        return {
            "parsed": {
                "action_type": "expense_log",
                "lane": "cassandra_finance",
                "fields": {
                    "amount": amount,
                    "currency": "USD",
                    "vendor": vendor,
                    "product_or_service": product,
                    "purchase_label": purchase,
                    "category_label": category,
                    "local_receipt_only": True,
                    "tax_advice_given": False,
                },
                "confidence": 0.89,
            },
            "risk_tier": "low",
            "normalized_summary": f"Logged expense: {_amount_display(amount)} {purchase} as {category}.",
            "needs_clarification": [],
            "referent_refs": [],
            "proposed_actions": ["record_local_expense_receipt"],
            "stop_condition": "local_receipt_written",
        }

    if ("gig" in lower or "show" in lower or "played" in lower or "did a" in lower) and _mentions_st_annes(text):
        date_info = _date_fields(text, received_at_utc)
        return {
            "parsed": {
                "action_type": "gig_event_log",
                "lane": "cassandra_business/niles_context",
                "fields": {
                    "venue": "St. Anne's",
                    "event_date": date_info["event_date"],
                    "date_basis": date_info["date_basis"],
                    "local_receipt_only": True,
                    "external_calendar_or_invoice_mutated": False,
                    "missing": ["payment amount"],
                },
                "confidence": 0.88,
            },
            "risk_tier": "low",
            "normalized_summary": f"Logged gig: St. Anne's on {date_info['event_date']}.",
            "needs_clarification": ["payment amount"],
            "referent_refs": [],
            "proposed_actions": ["record_local_gig_event_receipt"],
            "stop_condition": "local_receipt_written",
        }

    return _base_parse_result()


def _excluded_route_text(raw_text: str) -> bool:
    lowered = _lower_text(raw_text)
    exact_send_or_guardian_terms = (
        "approve exact send request",
        "approve the exact send request",
        "exact send request",
        "exact_send_authority_request",
        "send authority request",
        "prepare the send authority",
        "draft is approved",
        "draft approved",
        "approved with this exact text",
        "operator_action_approval_request",
        "guardian approval",
        "guardian decision",
    )
    if any(term in lowered for term in exact_send_or_guardian_terms):
        return True

    reminder_terms = (
        "remind me",
        "remind us",
        "set a reminder",
        "send a reminder",
        "check back",
        "check again",
        "follow up tomorrow",
        "follow-up tomorrow",
    )
    return any(term in lowered for term in reminder_terms)


def is_universal_operator_intake_candidate(raw_text: str) -> bool:
    """Return True only for clear low-risk local intake phrases."""

    if not raw_text or not raw_text.strip() or _excluded_route_text(raw_text):
        return False
    parsed = parse_operator_intake_text(raw_text)
    action_type = str(parsed["parsed"]["action_type"])
    confidence = float(parsed["parsed"].get("confidence") or 0)
    return action_type in SUPPORTED_ACTION_TYPES and confidence >= 0.8


def _safe_action_for(action_type: str) -> str:
    return {
        "income_payment_log": "record_local_income_payment_receipt",
        "expense_log": "record_local_expense_receipt",
        "gig_event_log": "record_local_gig_event_receipt",
        "identity_signature_preference": "record_local_identity_preference_stage",
    }.get(action_type, "")


def format_operator_intake_reply(event: Mapping[str, Any]) -> str:
    if event.get("watch_desk_items"):
        item = event["watch_desk_items"][0]
        if isinstance(item, Mapping) and item.get("plain_line"):
            return str(item["plain_line"])
    action_type = str(event.get("parsed", {}).get("action_type") or "")
    if action_type == "identity_signature_preference" and event.get("needs_clarification"):
        return f"{event['normalized_summary']} No external action taken."
    return str(event.get("normalized_summary") or "I need one more detail before I can log that.")


def _watch_plain_line(event: Mapping[str, Any]) -> str:
    parsed = event["parsed"]
    fields = parsed["fields"]
    action_type = parsed["action_type"]
    if action_type == "income_payment_log":
        return (
            f"Logged income: {_amount_display(fields['amount'])} from {fields['payer']}. "
            "Missing: invoice/project link, payment method."
        )
    if action_type == "expense_log":
        return (
            f"Logged expense: {_amount_display(fields['amount'])} "
            f"{fields.get('purchase_label') or fields['product_or_service']} as {fields['category_label']}."
        )
    if action_type == "gig_event_log":
        return f"Logged gig: {fields['venue']} on {fields['event_date']}. Missing: payment amount?"
    if action_type == "identity_signature_preference":
        return f"Staged identity preference: use {fields['requested_identity']} locally."
    return "Operator intake needs clarification."


def _watch_lane(lane: str) -> str:
    if lane == "cassandra_finance":
        return "cassandra_ar"
    if lane == "cassandra_business/niles_context":
        return "niles_creative"
    if lane == "chief_identity":
        return "chief_runtime"
    return "chief_runtime"


def _build_watch_item(event: Mapping[str, Any], receipt_ref: str) -> dict[str, Any]:
    parsed = event["parsed"]
    action_type = str(parsed["action_type"])
    lane = str(parsed["lane"])
    return {
        "item_id": f"operator_intake:{event['intake_id']}",
        "intake_id": event["intake_id"],
        "action_type": action_type,
        "lane": _watch_lane(lane),
        "urgency": "watch",
        "plain_line": _watch_plain_line(event),
        "source_receipt_ref": receipt_ref,
        "one_next_safe_action": "Review the local receipt; keep external mutation behind the existing approval spine.",
        "push_class": "on_demand",
    }


def _receipt_payload(event: Mapping[str, Any], created_at_utc: str) -> dict[str, Any]:
    parsed = event["parsed"]
    return {
        "schema_version": "operator_intake_receipt_v0",
        "intake_id": event["intake_id"],
        "action_type": parsed["action_type"],
        "lane": parsed["lane"],
        "normalized_summary": event["normalized_summary"],
        "parsed_fields": parsed["fields"],
        "safe_actions_taken": event["safe_actions_taken"],
        "approval_required": False,
        "external_calls_performed": False,
        "mutation_scope": "local_read_model_or_receipt_only",
        "created_at_utc": created_at_utc,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _write_receipt(event: Mapping[str, Any], *, receipt_root: str | Path, created_at_utc: str) -> dict[str, str]:
    root = _rooted(receipt_root)
    root.mkdir(parents=True, exist_ok=True)
    action_type = str(event["parsed"]["action_type"])
    filename = f"{_safe_filename(str(event['intake_id']))}_{_safe_filename(action_type)}_receipt.json"
    path = root / filename
    path.write_text(stable_json(_receipt_payload(event, created_at_utc)), encoding="utf-8")
    return {
        "receipt_id": f"operator_intake_receipt:{_sha256_text(path.as_posix())[:16]}",
        "path": path.as_posix(),
    }


def _read_model_path(read_model_root: str | Path) -> Path:
    return _rooted(read_model_root) / JSON_EXPORT_NAME


def _load_read_model(read_model_root: str | Path) -> dict[str, Any]:
    path = _read_model_path(read_model_root)
    if not path.is_file():
        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "generated_at": None,
            "event_count": 0,
            "receipt_count": 0,
            "events": [],
            "latest_receipts": [],
            "watch_desk_items": [],
            "supported_action_types": list(SUPPORTED_ACTION_TYPES),
            "surface_wiring_status": dict(SURFACE_WIRING_STATUS),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON at {path}")
    return payload


def _write_read_model(event: Mapping[str, Any], *, read_model_root: str | Path, generated_at: str) -> Path:
    path = _read_model_path(read_model_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_read_model(read_model_root)
    events = [item for item in payload.get("events", []) if isinstance(item, Mapping)]
    events = [item for item in events if item.get("intake_id") != event["intake_id"]]
    events.append(dict(event))
    events = sorted(events, key=lambda item: str(item.get("received_at_utc") or ""), reverse=True)[:100]

    receipts: list[dict[str, Any]] = []
    watch_items: list[dict[str, Any]] = []
    for item in events:
        receipts.extend([receipt for receipt in item.get("receipts", []) if isinstance(receipt, Mapping)])
        watch_items.extend([watch for watch in item.get("watch_desk_items", []) if isinstance(watch, Mapping)])

    payload.update(
        {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "generated_at": generated_at,
            "event_count": len(events),
            "receipt_count": len(receipts),
            "events": events,
            "latest_receipts": receipts[:50],
            "watch_desk_items": watch_items[:100],
            "supported_action_types": list(SUPPORTED_ACTION_TYPES),
            "surface_wiring_status": dict(SURFACE_WIRING_STATUS),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    )
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def process_operator_intake(
    *,
    raw_text: str,
    surface: str = "local_cli",
    operator: str = "Winship",
    received_at_utc: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any]:
    """Create an OPERATOR_INTAKE_EVENT_V0 and write local artifacts when safe."""

    if surface not in SUPPORTED_SURFACES:
        raise ValueError(f"unsupported surface: {surface}")
    received = _canonical_received_at(received_at_utc)
    parsed_result = parse_operator_intake_text(
        raw_text,
        received_at_utc=received,
        session_context=session_context,
    )
    text_hash = "sha256:" + _sha256_text(_normalized_text(raw_text))
    intake_id = _row_id("operator_intake", surface, operator, received, text_hash)
    local_text_allowed = surface == "local_cli"
    action_type = str(parsed_result["parsed"]["action_type"])
    safe_action = _safe_action_for(action_type)
    clarifications = set(parsed_result["needs_clarification"])
    blocking_clarification = action_type == "unknown" or bool(
        clarifications.intersection({"referent:this", "referent:that", "referent:it"})
    )
    should_write_local_receipt = action_type in SUPPORTED_ACTION_TYPES and safe_action and not blocking_clarification

    event: dict[str, Any] = {
        "schema_version": OPERATOR_INTAKE_SCHEMA_VERSION,
        "intake_id": intake_id,
        "received_at_utc": received,
        "surface": surface,
        "operator": operator,
        "normalized_summary": parsed_result["normalized_summary"],
        "parsed": parsed_result["parsed"],
        "risk_tier": parsed_result["risk_tier"],
        "needs_clarification": parsed_result["needs_clarification"],
        "referent_refs": parsed_result["referent_refs"],
        "proposed_actions": parsed_result["proposed_actions"],
        "safe_actions_taken": [safe_action] if should_write_local_receipt else [],
        "approval_required": False,
        "receipts": [],
        "watch_desk_items": [],
        "stop_condition": parsed_result["stop_condition"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "raw_text_stored": local_text_allowed,
    }
    if local_text_allowed:
        event["raw_text"] = raw_text
    else:
        event["raw_text_ref"] = text_hash

    if should_write_local_receipt:
        created_at = utc_now()
        receipt = _write_receipt(event, receipt_root=receipt_root, created_at_utc=created_at)
        receipt_ref = f"{receipt['path']}#receipt"
        watch_item = _build_watch_item(event, receipt_ref)
        event["receipts"] = [receipt]
        event["watch_desk_items"] = [watch_item]
        event["stop_condition"] = "local_receipt_written"
        _write_read_model(event, read_model_root=read_model_root, generated_at=created_at)

    return event


def try_process_surface_operator_intake(
    raw_text: str,
    *,
    surface: str,
    operator: str = "Winship",
    received_at_utc: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any] | None:
    if not is_universal_operator_intake_candidate(raw_text):
        return None
    event = process_operator_intake(
        raw_text=raw_text,
        surface=surface,
        operator=operator,
        received_at_utc=received_at_utc,
        session_context=session_context,
        read_model_root=read_model_root,
        receipt_root=receipt_root,
    )
    return {
        "schema_version": "operator_intake_surface_response_v0",
        "handled": True,
        "surface": surface,
        "intake_id": event["intake_id"],
        "action_type": event["parsed"]["action_type"],
        "lane": event["parsed"]["lane"],
        "risk_tier": event["risk_tier"],
        "reply": format_operator_intake_reply(event),
        "event": event,
        "approval_required": False,
        "external_calls_performed": False,
    }


def process_mac_composer_operator_intake(
    raw_text: str,
    *,
    operator: str = "Winship",
    received_at_utc: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any]:
    routed = try_process_surface_operator_intake(
        raw_text,
        surface="mac_composer",
        operator=operator,
        received_at_utc=received_at_utc,
        session_context=session_context,
        read_model_root=read_model_root,
        receipt_root=receipt_root,
    )
    if routed is not None:
        return routed
    parsed = parse_operator_intake_text(raw_text, received_at_utc=received_at_utc, session_context=session_context)
    return {
        "schema_version": "operator_intake_surface_response_v0",
        "handled": False,
        "surface": "mac_composer",
        "action_type": parsed["parsed"]["action_type"],
        "lane": parsed["parsed"]["lane"],
        "risk_tier": parsed["risk_tier"],
        "reply": parsed["normalized_summary"],
        "needs_clarification": parsed["needs_clarification"],
        "approval_required": False,
        "external_calls_performed": False,
    }


def load_operator_intake_read_model(*, read_model_root: str | Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return _load_read_model(read_model_root)
