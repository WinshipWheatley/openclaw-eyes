"""Universal Operator Intake v0.

This module turns low-risk operator text into local receipts, a generated read
model, and Watch Desk items. It does not approve, execute, send, call live
services, mutate external systems, or mark invoices paid.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from operator_skill_registry import (
    LOCAL_LOG_SKILL_ACTION_TYPES,
    get_operator_skill,
    operator_skill_reference_data_needs_manifest,
    operator_skill_rows,
)


ROOT = Path(__file__).resolve().parent
OPERATOR_INTAKE_SCHEMA_VERSION = "OPERATOR_INTAKE_EVENT_V0"
READ_MODEL_VERSION = "operator_intake_events_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_RECEIPT_ROOT = Path("/tmp/openclaw-mission-control/openclaw_universal_operator_intake_v0/receipts")
JSON_EXPORT_NAME = "operator_intake_events.json"
DEFAULT_OPERATOR_TIMEZONE = "America/New_York"

SUPPORTED_SURFACES = (
    "telegram",
    "cassandra_direct",
    "niles_direct",
    "chief_direct",
    "hermes_direct",
    "guardian_direct",
    "watch_desk_direct",
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
    "agent_lane_request",
    "approval_gated_action_request",
    "operator_clarification_event",
)
LOCAL_OPERATOR_SKILL_ACTION_TYPES = set(LOCAL_LOG_SKILL_ACTION_TYPES)

WATCH_DESK_LANES = {
    "cassandra_ar",
    "chief_runtime",
    "niles_creative",
    "mac_sync",
    "guardian_approval",
    "hermes",
}

AGENT_LANE_REGISTRY_V0 = {
    "cassandra": {
        "display_name": "Cassandra",
        "watch_lane": "cassandra_ar",
        "owns": "business ops, AR, client follow-up, income/payment/expense/gig logs, executive continuity",
        "must_not": ("mark invoices paid", "send email without Guardian approval", "mutate external ledgers"),
    },
    "niles": {
        "display_name": "Niles",
        "watch_lane": "niles_creative",
        "owns": "music/creative/audio lane, song/session notes, setlist prep, Struna/Fundo context, creative prep",
        "must_not": ("mutate DAW/session/media files", "export/bounce/publish", "scan private media without scope"),
    },
    "chief": {
        "display_name": "Chief",
        "watch_lane": "chief_runtime",
        "owns": "routing, proof harness, build tasks, system ops, priority decisions",
        "must_not": ("bypass Guardian", "execute external actions without authority"),
    },
    "hermes": {
        "display_name": "Hermes",
        "watch_lane": "hermes",
        "owns": "adapter/protocol/bridge boundary and route-back mechanics",
        "must_not": ("own business logic", "hold raw secrets", "execute live bridges"),
    },
    "guardian": {
        "display_name": "Guardian",
        "watch_lane": "guardian_approval",
        "owns": "approval authority only",
        "must_not": ("execute business logic", "send email", "mutate operator state"),
    },
    "watch desk": {
        "display_name": "Watch Desk",
        "watch_lane": "chief_runtime",
        "owns": "what needs me projection",
        "must_not": ("mutate state", "create approvals", "execute actions"),
    },
}

AGENT_LANE_ALIASES = {
    "cassandra": "cassandra",
    "cass": "cassandra",
    "niles": "niles",
    "producer": "niles",
    "chief": "chief",
    "hermes": "hermes",
    "guardian": "guardian",
    "watch desk": "watch desk",
    "watchdesk": "watch desk",
}

SURFACE_WIRING_STATUS = {
    "local_api": True,
    "telegram_cassandra_route_hook": True,
    "telegram_live_listener_restart_required": True,
    "mac_composer_callable_contract": True,
    "mac_composer_live_bridge": False,
    "direct_niles_surface_live": False,
    "direct_chief_surface_live": False,
    "direct_hermes_surface_live": False,
}

AGENT_EXECUTION_MODE_REGISTRY_V0 = {
    "cassandra": {
        "agent_id": "cassandra",
        "lane": "cassandra_ar",
        "execution_mode": "live_listener",
        "direct_surface_available": True,
        "fallback_route_available": True,
        "spawn_supported": False,
        "route_back_supported": True,
        "approval_required_for_spawn": False,
        "receipt_required": True,
        "current_status": "wired",
        "surface_kind": "telegram_cassandra_route_hook",
        "calls_universal_intake": True,
        "fallback_surface": "telegram",
        "live_direct_endpoint": True,
        "safe_next_step": "Use Cassandra Telegram or local API intake for routed requests.",
    },
    "niles": {
        "agent_id": "niles",
        "lane": "niles_creative",
        "execution_mode": "spawned_worker",
        "direct_surface_available": False,
        "fallback_route_available": True,
        "spawn_supported": True,
        "route_back_supported": True,
        "approval_required_for_spawn": False,
        "receipt_required": True,
        "current_status": "partial",
        "surface_kind": "spawned_worker_packet_only",
        "calls_universal_intake": True,
        "fallback_surface": "cassandra_or_mac_composer",
        "live_direct_endpoint": False,
        "safe_next_step": "Create a scoped Niles work packet through Cassandra or Mac composer; do not touch DAW/session files.",
    },
    "chief": {
        "agent_id": "chief",
        "lane": "chief_runtime",
        "execution_mode": "hardcoded_route",
        "direct_surface_available": False,
        "fallback_route_available": True,
        "spawn_supported": True,
        "route_back_supported": True,
        "approval_required_for_spawn": False,
        "receipt_required": True,
        "current_status": "partial",
        "surface_kind": "status_route_or_work_packet",
        "calls_universal_intake": True,
        "fallback_surface": "cassandra_or_mac_composer",
        "live_direct_endpoint": False,
        "safe_next_step": "Create a Chief status/build work packet or use existing status read models.",
    },
    "hermes": {
        "agent_id": "hermes",
        "lane": "hermes",
        "execution_mode": "sidecar_adapter",
        "direct_surface_available": False,
        "fallback_route_available": True,
        "spawn_supported": False,
        "route_back_supported": True,
        "approval_required_for_spawn": False,
        "receipt_required": True,
        "current_status": "partial",
        "surface_kind": "adapter_protocol_boundary",
        "calls_universal_intake": True,
        "fallback_surface": "cassandra_or_mac_composer",
        "live_direct_endpoint": False,
        "safe_next_step": "Route only adapter health or protocol-boundary checks; do not assign business ownership.",
    },
    "guardian": {
        "agent_id": "guardian",
        "lane": "guardian_approval",
        "execution_mode": "human_approval",
        "direct_surface_available": False,
        "fallback_route_available": True,
        "spawn_supported": False,
        "route_back_supported": True,
        "approval_required_for_spawn": False,
        "receipt_required": True,
        "current_status": "deferred",
        "surface_kind": "human_authority_lane",
        "calls_universal_intake": True,
        "fallback_surface": "cassandra_or_mac_composer",
        "live_direct_endpoint": False,
        "safe_next_step": "Capture approve, deny, or why-now decisions only; Guardian never executes the business action.",
    },
    "watch desk": {
        "agent_id": "watch desk",
        "lane": "chief_runtime",
        "execution_mode": "logical_only",
        "direct_surface_available": False,
        "fallback_route_available": True,
        "spawn_supported": False,
        "route_back_supported": False,
        "approval_required_for_spawn": False,
        "receipt_required": True,
        "current_status": "not_wired",
        "surface_kind": "logical_lane_only",
        "calls_universal_intake": True,
        "fallback_surface": "cassandra_or_mac_composer",
        "live_direct_endpoint": False,
        "safe_next_step": "Record the request and report that the Watch Desk executor is not wired.",
    },
    "mac_composer": {
        "agent_id": "mac_composer",
        "lane": "chief_runtime",
        "execution_mode": "hardcoded_route",
        "direct_surface_available": True,
        "fallback_route_available": True,
        "spawn_supported": False,
        "route_back_supported": True,
        "approval_required_for_spawn": False,
        "receipt_required": True,
        "current_status": "partial",
        "surface_kind": "mac_composer_callable_contract",
        "calls_universal_intake": True,
        "fallback_surface": "mac_composer",
        "live_direct_endpoint": False,
        "safe_next_step": "Use the callable contract locally; the live bridge remains off.",
    },
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


def _stable_compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


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


def _operator_timezone_name(value: str | None) -> str:
    candidate = str(value or "").strip() or DEFAULT_OPERATOR_TIMEZONE
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return DEFAULT_OPERATOR_TIMEZONE
    return candidate


def _operator_local_datetime(received_at_utc: str | None, operator_timezone: str | None = None) -> datetime:
    timezone_name = _operator_timezone_name(operator_timezone)
    return _parse_datetime(received_at_utc).astimezone(ZoneInfo(timezone_name))


def _operator_local_date(received_at_utc: str | None, operator_timezone: str | None = None) -> str:
    return _operator_local_datetime(received_at_utc, operator_timezone).date().isoformat()


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


def _agent_display_name(agent_id: str) -> str:
    if agent_id == "mac_composer":
        return "Mac composer"
    if agent_id == "watch_desk":
        agent_id = "watch desk"
    if agent_id in AGENT_LANE_REGISTRY_V0:
        return str(AGENT_LANE_REGISTRY_V0[agent_id]["display_name"])
    return agent_id.replace("_", " ").title()


def _resolve_agent_id(value: str) -> str:
    normalized = _clean_phrase(value).lower().replace("-", " ").replace("_", " ")
    if normalized in {"mac composer", "mission control composer"}:
        return "mac_composer"
    if normalized in {"watch desk", "watchdesk"}:
        return "watch desk"
    return AGENT_LANE_ALIASES.get(normalized, normalized.replace(" ", "_"))


def agent_execution_mode_status(agent_id: str) -> dict[str, Any]:
    resolved = _resolve_agent_id(agent_id)
    status = dict(AGENT_EXECUTION_MODE_REGISTRY_V0.get(resolved) or {})
    if not status:
        status = {
            "agent_id": resolved,
            "lane": "chief_runtime",
            "execution_mode": "logical_only",
            "direct_surface_available": False,
            "fallback_route_available": False,
            "spawn_supported": False,
            "route_back_supported": False,
            "approval_required_for_spawn": False,
            "receipt_required": True,
            "current_status": "not_wired",
            "surface_kind": "unknown_agent",
            "calls_universal_intake": False,
            "fallback_surface": "cassandra_or_mac_composer",
            "live_direct_endpoint": False,
            "safe_next_step": "Use Cassandra or Mac composer until this agent lane is registered.",
        }
    status["agent_id"] = resolved
    status["display_name"] = _agent_display_name(resolved)
    return status


def _execution_status_for_agent(agent_id: str) -> dict[str, Any]:
    status = agent_execution_mode_status(agent_id)
    required_fields = (
        "agent_id",
        "lane",
        "execution_mode",
        "direct_surface_available",
        "fallback_route_available",
        "spawn_supported",
        "route_back_supported",
        "approval_required_for_spawn",
        "receipt_required",
        "current_status",
    )
    return {key: status[key] for key in required_fields}


def _extract_addressed_agent(raw_text: str) -> dict[str, str]:
    match = re.match(r"^\s*([A-Za-z][A-Za-z ]{1,24})\s*,\s*(.+?)\s*$", raw_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return {"requested_agent": "", "agent_id": "", "request_text": _clean_phrase(_normalized_text(raw_text))}
    requested_agent = _clean_phrase(match.group(1))
    agent_id = AGENT_LANE_ALIASES.get(requested_agent.lower()) or (
        "mac_composer" if requested_agent.lower() in {"mac composer", "mission control composer"} else ""
    )
    return {
        "requested_agent": requested_agent,
        "agent_id": agent_id,
        "request_text": _clean_phrase(_normalized_text(match.group(2))),
    }


def _surface_receiving_agent(surface: str, receiving_agent_id: str | None = None) -> str:
    if receiving_agent_id:
        return _resolve_agent_id(receiving_agent_id)
    return {
        "telegram": "cassandra",
        "cassandra_direct": "cassandra",
        "niles_direct": "niles",
        "chief_direct": "chief",
        "hermes_direct": "hermes",
        "guardian_direct": "guardian",
        "watch_desk_direct": "watch desk",
        "mac_composer": "mac_composer",
    }.get(surface, "")


def _confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _date_fields(
    text: str,
    received_at_utc: str | None,
    *,
    operator_timezone: str | None = None,
) -> dict[str, str]:
    lower = _lower_text(text)
    timezone_name = _operator_timezone_name(operator_timezone)
    local_dt = _operator_local_datetime(received_at_utc, timezone_name)
    local_date = local_dt.date()
    explicit = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", lower)
    if explicit:
        event_date = explicit.group(0)
        return {
            "event_date": event_date,
            "normalized_event_date": event_date,
            "date_basis": "explicit_iso_date",
            "operator_local_timezone": timezone_name,
            "operator_local_date": local_date.isoformat(),
        }
    if "tonight" in lower:
        event_date = local_date
        basis = "implied_tonight"
    elif "yesterday" in lower:
        event_date = local_date - timedelta(days=1)
        basis = "implied_yesterday"
    elif "tomorrow" in lower:
        event_date = local_date + timedelta(days=1)
        basis = "implied_tomorrow"
    if "today" in lower:
        event_date = local_date
        basis = "implied_today"
    elif "tonight" not in lower and "yesterday" not in lower and "tomorrow" not in lower:
        event_date = local_date
        basis = "default_received_local_date"
    event_date_text = event_date.isoformat()
    return {
        "event_date": event_date_text,
        "normalized_event_date": event_date_text,
        "date_basis": basis,
        "operator_local_timezone": timezone_name,
        "operator_local_date": local_date.isoformat(),
    }


def _local_skill_idempotency_date(
    action_type: str,
    fields: Mapping[str, Any],
    received_at_utc: str,
    *,
    operator_timezone: str | None = None,
) -> str:
    if action_type == "gig_event_log" and fields.get("event_date"):
        return str(fields["event_date"])
    if fields.get("associated_gig_date"):
        return str(fields["associated_gig_date"])
    return _operator_local_date(received_at_utc, operator_timezone)


def _operator_skill_for_action(action_type: str) -> dict[str, Any]:
    if action_type == "operator_clarification_event":
        return {
            "schema_version": "OPERATOR_SKILL_V0",
            "skill_id": "operator_skill:operator_clarification_event:v0",
            "action_type": "operator_clarification_event",
            "owner_agent": "chief",
            "owner_lane": "chief_runtime",
            "risk_tier": "low",
            "external": False,
            "required_fields": ["action_type"],
            "optional_fields": ["requested_detail", "surface", "receiving_agent"],
            "safe_local_action": "",
            "approval_action": None,
            "receipt_schema": "operator_clarification_event_receipt_v0",
            "watch_desk_lane": "chief_runtime",
            "push_class": "needs_operator",
            "must_not": [
                "execute vague request",
                "create approval request",
                "call external services",
            ],
            "clarify_when": ["action_type"],
            "reference_data_needed": [],
        }
    return get_operator_skill(action_type)


def _local_skill_intake_id(
    *,
    action_type: str,
    fields: Mapping[str, Any],
    raw_text: str,
    surface: str,
    operator: str,
    received_at_utc: str,
    operator_timezone: str | None = None,
) -> str:
    skill = _operator_skill_for_action(action_type)
    if action_type == "operator_clarification_event":
        return _row_id(
            "operator_intake",
            skill["skill_id"],
            surface,
            operator,
            _operator_local_date(received_at_utc, operator_timezone),
            _normalized_text(raw_text),
        )
    if action_type not in LOCAL_OPERATOR_SKILL_ACTION_TYPES or skill.get("external"):
        text_hash = "sha256:" + _sha256_text(_normalized_text(raw_text))
        return _row_id("operator_intake", surface, operator, received_at_utc, text_hash)
    idempotency_date = _local_skill_idempotency_date(action_type, fields, received_at_utc)
    return _row_id(
        "operator_intake",
        skill["skill_id"],
        surface,
        operator,
        idempotency_date,
        _normalized_text(raw_text),
        _stable_compact_json(fields),
    )


def _existing_event_by_id(read_model_root: str | Path, intake_id: str) -> dict[str, Any] | None:
    payload = _load_read_model(read_model_root)
    for item in payload.get("events", []):
        if isinstance(item, Mapping) and item.get("intake_id") == intake_id:
            return dict(item)
    return None


def _skill_required_missing(skill: Mapping[str, Any], clarifications: set[str]) -> set[str]:
    required = {str(field) for field in skill.get("required_fields", [])}
    return required.intersection(clarifications)


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


def _latest_recent_gig(session_context: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not session_context:
        return None
    recent = session_context.get("recent_gigs")
    if not isinstance(recent, list):
        return None
    for candidate in reversed(recent):
        if isinstance(candidate, Mapping):
            parsed = candidate.get("parsed") if isinstance(candidate.get("parsed"), Mapping) else {}
            if parsed.get("action_type") == "gig_event_log":
                fields = parsed.get("fields") if isinstance(parsed.get("fields"), Mapping) else {}
                return {
                    "associated_gig_intake_id": str(candidate.get("intake_id") or ""),
                    "associated_gig_date": str(fields.get("event_date") or candidate.get("event_date") or ""),
                }
    return None


def _initial_cross_link_refs(parsed_result: Mapping[str, Any]) -> list[str]:
    refs = [str(ref) for ref in parsed_result.get("referent_refs", []) if str(ref)]
    fields = parsed_result.get("parsed", {}).get("fields")
    if isinstance(fields, Mapping):
        associated = str(fields.get("associated_gig_intake_id") or "")
        if associated and associated not in refs:
            refs.append(associated)
    return refs


def _base_parse_result() -> dict[str, Any]:
    return {
        "parsed": {
            "action_type": "operator_clarification_event",
            "lane": "chief_runtime",
            "fields": {
                "requested_detail": "action_type",
                "execution_performed": False,
                "external_action_allowed": False,
            },
            "confidence": 0.35,
        },
        "risk_tier": "low",
        "normalized_summary": "Needs clarification before OpenClaw can classify this intake.",
        "needs_clarification": ["action_type"],
        "referent_refs": [],
        "proposed_actions": [],
        "stop_condition": "clarification_required",
    }


def _recipient_label(request_text: str) -> str:
    match = re.search(r"\b(?:to|with|about)\s+([A-Z][A-Za-z0-9 .'-]+?)(?:\s+about\b|\.?$)", request_text)
    if match:
        return _clean_phrase(match.group(1))
    return ""


def _approval_gated_action_request(raw_text: str) -> dict[str, Any] | None:
    addressed = _extract_addressed_agent(raw_text)
    request_text = addressed["request_text"]
    lower = request_text.lower()
    send_like = bool(re.search(r"\b(send|email|message|reply|draft)\b", lower))
    follow_up_like = bool(re.search(r"\bfollow[- ]?up\b", lower) or re.search(r"\bfollow\s+up\b", lower))
    outbound_target = bool(re.search(r"\b(to|with)\s+[A-Z][A-Za-z0-9 .'-]+", request_text)) or "annette" in lower
    invoice_context = "invoice" in lower or "client" in lower or "ar" in lower
    if not ((send_like and outbound_target) or (follow_up_like and (outbound_target or invoice_context))):
        return None

    recipient = _recipient_label(request_text) or ("Annette" if "annette" in lower else "")
    execution_status = _execution_status_for_agent("cassandra")
    fields: dict[str, Any] = {
        "agent_id": "cassandra",
        "agent_display_name": "Cassandra",
        "request_text": request_text,
        "requested_external_action": "outbound_followup_or_send",
        "recipient_label": recipient,
        "guardian_approval_required": True,
        "approval_request_created": False,
        "approval_packet_created": False,
        "email_sent": False,
        "gmail_draft_created": False,
        "external_action_allowed": False,
        "live_execution_allowed": False,
        "agent_registry_ref": "AGENT_LANE_REGISTRY_V0:cassandra",
        "agent_execution": execution_status,
        "execution_mode": execution_status["execution_mode"],
        "direct_surface_available": execution_status["direct_surface_available"],
        "fallback_route_available": execution_status["fallback_route_available"],
        "spawn_supported": execution_status["spawn_supported"],
        "route_back_supported": execution_status["route_back_supported"],
        "approval_required_for_spawn": execution_status["approval_required_for_spawn"],
        "receipt_required": execution_status["receipt_required"],
        "current_status": execution_status["current_status"],
    }
    if addressed["agent_id"]:
        fields["addressed_agent"] = addressed["agent_id"]
    return {
        "parsed": {
            "action_type": "approval_gated_action_request",
            "lane": "cassandra_ar",
            "fields": fields,
            "confidence": 0.87,
        },
        "risk_tier": "high",
        "normalized_summary": "Cassandra outbound action request staged for Guardian approval. No email sent.",
        "needs_clarification": [],
        "referent_refs": [],
        "proposed_actions": [
            "record_local_approval_gated_request_receipt",
            "guardian_approval_required_before_execution",
        ],
        "stop_condition": "guardian_approval_required",
    }


def _agent_lane_request(raw_text: str) -> dict[str, Any] | None:
    addressed = _extract_addressed_agent(raw_text)
    if not addressed["requested_agent"]:
        return None
    requested_agent = addressed["requested_agent"]
    agent_id = addressed["agent_id"]
    request_text = addressed["request_text"]
    if not agent_id:
        return {
            "parsed": {
                "action_type": "agent_lane_request",
                "lane": "chief_runtime",
                "fields": {
                    "requested_agent": requested_agent,
                    "request_text": request_text,
                    "route_status": "unknown_agent",
                    "external_action_allowed": False,
                },
                "confidence": 0.83,
            },
            "risk_tier": "low",
            "normalized_summary": f"I don't know an active lane named {requested_agent}.",
            "needs_clarification": ["known_agent_lane"],
            "referent_refs": [],
            "proposed_actions": ["clarify_agent_lane"],
            "stop_condition": "clarification_required",
        }

    lane_spec = AGENT_LANE_REGISTRY_V0[agent_id]
    execution_status = _execution_status_for_agent(agent_id)
    fields: dict[str, Any] = {
        "agent_id": agent_id,
        "agent_display_name": lane_spec["display_name"],
        "request_text": request_text,
        "route_status": "staged",
        "external_action_allowed": False,
        "live_execution_allowed": False,
        "agent_registry_ref": f"AGENT_LANE_REGISTRY_V0:{agent_id}",
        "agent_execution": execution_status,
        "execution_mode": execution_status["execution_mode"],
        "direct_surface_available": execution_status["direct_surface_available"],
        "fallback_route_available": execution_status["fallback_route_available"],
        "spawn_supported": execution_status["spawn_supported"],
        "route_back_supported": execution_status["route_back_supported"],
        "approval_required_for_spawn": execution_status["approval_required_for_spawn"],
        "receipt_required": execution_status["receipt_required"],
        "current_status": execution_status["current_status"],
    }
    lower_request = request_text.lower()
    if agent_id == "niles":
        topic = request_text
        prep_match = re.search(r"\bprep\s+(?:my\s+)?(.+)", request_text, flags=re.IGNORECASE)
        if prep_match:
            topic = _clean_phrase(prep_match.group(1))
        fields.update(
            {
                "creative_context_request": topic,
                "daw_action_taken": False,
                "media_or_session_mutated": False,
            }
        )
        summary = f"Niles prep request staged: {topic}. No DAW action taken."
    elif agent_id == "chief":
        intent = "what broke" if "broke" in lower_request else request_text
        fields.update({"chief_request_type": "runtime_or_priority_check", "request_label": intent})
        summary = f"Chief check request staged: {intent}. No external action taken."
    elif agent_id == "hermes":
        bridge_check = "bridge" if "bridge" in lower_request else request_text
        fields.update({"bridge_context": bridge_check, "business_logic_owner": False})
        summary = f"Hermes bridge check staged: {bridge_check}. No external action taken."
    elif agent_id == "cassandra":
        target_match = re.search(r"\b(?:with|for)\s+([A-Za-z0-9 .'-]+)$", request_text, flags=re.IGNORECASE)
        target = _clean_phrase(target_match.group(1)) if target_match else request_text
        fields.update(
            {
                "business_ops_request": request_text,
                "target_label": target,
                "email_action_taken": False,
                "invoice_marked_paid": False,
            }
        )
        summary = f"Cassandra request staged: {request_text}. No email action taken."
    elif agent_id == "guardian":
        fields.update({"approval_created": False, "approval_decision_made": False})
        summary = f"Guardian review request staged: {request_text}. No approval created."
    else:
        fields.update({"projection_request": request_text, "source_state_mutated": False})
        summary = f"Watch Desk request staged: {request_text}. No state mutation taken."

    return {
        "parsed": {
            "action_type": "agent_lane_request",
            "lane": lane_spec["watch_lane"],
            "fields": fields,
            "confidence": 0.88,
        },
        "risk_tier": "low",
        "normalized_summary": summary,
        "needs_clarification": [],
        "referent_refs": [],
        "proposed_actions": ["record_local_agent_lane_request_receipt"],
        "stop_condition": "local_receipt_written",
    }


def _implicit_agent_lane_request(raw_text: str) -> dict[str, Any] | None:
    addressed = _extract_addressed_agent(raw_text)
    if addressed["requested_agent"]:
        return None
    request_text = addressed["request_text"]
    lower = request_text.lower()
    if re.search(r"\b(prep|prepare|plan|organize)\b.*\b(live set|setlist|set notes|song|session|struna|fundo)\b", lower) or re.search(
        r"\b(open|review|find)\b.*\b(fundo|struna|song|session|setlist)\b", lower
    ):
        agent_id = "niles"
        confidence = 0.84
    elif re.search(r"\b(what broke|build|test|harness|system status|runtime|priority|architecture)\b", lower):
        agent_id = "chief"
        confidence = 0.84
    elif re.search(r"\b(bridge|adapter|protocol|connector|route[- ]back|tool wrapper)\b", lower):
        agent_id = "hermes"
        confidence = 0.84
    else:
        return None
    parsed = _agent_lane_request(f"{_agent_display_name(agent_id)}, {request_text}")
    if parsed is None:
        return None
    parsed["parsed"]["confidence"] = confidence
    parsed["parsed"]["fields"]["implicit_owner_inference"] = True
    parsed["parsed"]["fields"]["original_request_text"] = request_text
    return parsed


def parse_operator_intake_text(
    raw_text: str,
    *,
    received_at_utc: str | None = None,
    operator_timezone: str | None = None,
    session_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse supported low-risk operator text without side effects."""

    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text is required")

    text = _normalized_text(raw_text)
    lower = text.lower()

    approval_gated = _approval_gated_action_request(text)
    if approval_gated is not None:
        return approval_gated

    agent_lane = _agent_lane_request(text)
    if agent_lane is not None:
        return agent_lane

    implicit_agent_lane = _implicit_agent_lane_request(text)
    if implicit_agent_lane is not None:
        return implicit_agent_lane

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

    income_missing_amount = re.search(r"\b(?:got\s+)?paid\s+for\s+(.+)$", text, flags=re.IGNORECASE)
    if income_missing_amount:
        context_label = _clean_phrase(income_missing_amount.group(1))
        fields: dict[str, Any] = {
            "context_label": context_label,
            "amount": None,
            "currency": "USD",
            "local_receipt_only": True,
            "invoice_marked_paid": False,
            "external_ledger_mutated": False,
            "missing": ["amount", "payer", "payment method"],
        }
        if _mentions_st_annes(context_label):
            fields["payer"] = "St. Anne's"
        return {
            "parsed": {
                "action_type": "income_payment_log",
                "lane": "cassandra_finance",
                "fields": fields,
                "confidence": 0.82,
            },
            "risk_tier": "low",
            "normalized_summary": "Need payment amount before logging income.",
            "needs_clarification": ["amount"],
            "referent_refs": [],
            "proposed_actions": ["clarify_income_payment_amount"],
            "stop_condition": "clarification_required",
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

    expense_match = re.search(r"\bspent\s+\$?([\d,]+(?:\.\d+)?)\s+on\s+(.+)$", text, flags=re.IGNORECASE)
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
        association = _latest_recent_gig(session_context) if _mentions_st_annes(purchase) else None
        fields: dict[str, Any] = {
            "amount": amount,
            "currency": "USD",
            "vendor": vendor,
            "product_or_service": product,
            "purchase_label": purchase,
            "category_label": category,
            "local_receipt_only": True,
            "tax_advice_given": False,
        }
        if association:
            fields.update(association)
        return {
            "parsed": {
                "action_type": "expense_log",
                "lane": "cassandra_finance",
                "fields": fields,
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
        date_info = _date_fields(text, received_at_utc, operator_timezone=operator_timezone)
        return {
            "parsed": {
                "action_type": "gig_event_log",
                "lane": "cassandra_business/niles_context",
                "fields": {
                    "venue": "St. Anne's",
                    "event_date": date_info["event_date"],
                    "normalized_event_date": date_info["normalized_event_date"],
                    "date_basis": date_info["date_basis"],
                    "operator_local_timezone": date_info["operator_local_timezone"],
                    "operator_local_date": date_info["operator_local_date"],
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


def split_operator_intake_text(raw_text: str) -> list[str]:
    text = _normalized_text(raw_text)
    if not text:
        return []
    marker = re.compile(
        r"\b(?:i\s+did\s+a|did\s+a|i\s+played|played|i\s+got\s+paid|got\s+paid|paid\s+\$|"
        r"i\s+spent|spent\s+\$)\b",
        flags=re.IGNORECASE,
    )
    matches = list(marker.finditer(text))
    if len(matches) < 2:
        return [text]
    parts: list[str] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        part = text[start:end]
        part = re.sub(r"^\s*(?:and|then|,)\s+", "", part, flags=re.IGNORECASE)
        part = re.sub(r"(?:,?\s+and|,?\s+then)\s*$", "", part, flags=re.IGNORECASE)
        part = part.strip(" ,;.")
        if part:
            parts.append(part)
    return parts or [text]


def parse_operator_intake_texts(
    raw_text: str,
    *,
    received_at_utc: str | None = None,
    operator_timezone: str | None = None,
    session_context: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    parts = split_operator_intake_text(raw_text)
    parsed_items: list[dict[str, Any]] = []
    local_context: dict[str, Any] = dict(session_context or {})
    recent_gigs = list(local_context.get("recent_gigs") or [])
    local_context["recent_gigs"] = recent_gigs
    for part in parts:
        parsed = parse_operator_intake_text(
            part,
            received_at_utc=received_at_utc,
            operator_timezone=operator_timezone,
            session_context=local_context,
        )
        parsed_items.append({"raw_text": part, "parsed_result": parsed})
        if parsed["parsed"]["action_type"] == "gig_event_log":
            recent_gigs.append({"parsed": parsed["parsed"], "intake_id": ""})
    return parsed_items


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
    parsed_items = parse_operator_intake_texts(raw_text)
    if not parsed_items:
        return False
    for item in parsed_items:
        parsed = item["parsed_result"]
        action_type = str(parsed["parsed"]["action_type"])
        confidence = float(parsed["parsed"].get("confidence") or 0)
        if action_type == "operator_clarification_event" or action_type not in SUPPORTED_ACTION_TYPES or confidence < 0.8:
            return False
    return True


def is_operator_intake_clarification_candidate(raw_text: str) -> bool:
    """Return True for narrow ambiguous handoff phrases that should get a safe clarification reply."""

    if not raw_text or not raw_text.strip() or _excluded_route_text(raw_text):
        return False
    lowered = _lower_text(raw_text).strip(" .!?")
    return bool(
        re.fullmatch(
            r"(?:can|could|would)\s+you\s+handle\s+(?:that|this)(?:\s+thing)?",
            lowered,
        )
    )


def _safe_action_for(action_type: str) -> str:
    return {
        "income_payment_log": "record_local_income_payment_receipt",
        "expense_log": "record_local_expense_receipt",
        "gig_event_log": "record_local_gig_event_receipt",
        "identity_signature_preference": "record_local_identity_preference_stage",
        "agent_lane_request": "record_local_agent_lane_request_receipt",
        "approval_gated_action_request": "record_local_approval_gated_request_receipt",
    }.get(action_type, "")


def _refresh_watch_desk_feed(
    *,
    read_model_root: str | Path,
    generated_at: str,
) -> dict[str, Any]:
    try:
        from watch_desk_feed import export_watch_desk_feed

        return export_watch_desk_feed(
            read_model_root=read_model_root,
            export_root=read_model_root,
            generated_at=generated_at,
        )
    except Exception as exc:
        return {
            "read_model_path": "",
            "item_count": 0,
            "new_push_candidate_count": 0,
            "live_push_allowed": False,
            "refresh_error": type(exc).__name__,
        }


def format_operator_intake_reply(event: Mapping[str, Any]) -> str:
    if event.get("operator_visible_reply"):
        return str(event["operator_visible_reply"])
    if event.get("watch_desk_items"):
        item = event["watch_desk_items"][0]
        if isinstance(item, Mapping) and item.get("plain_line"):
            return str(item["plain_line"])
    action_type = str(event.get("parsed", {}).get("action_type") or "")
    if action_type == "identity_signature_preference" and event.get("needs_clarification"):
        return f"{event['normalized_summary']} No external action taken."
    if action_type == "identity_signature_preference":
        return _watch_plain_line(event)
    if action_type == "agent_lane_request":
        return str(event.get("normalized_summary") or "Agent lane request staged locally.")
    if action_type == "approval_gated_action_request":
        return str(event.get("normalized_summary") or "Action request logged for Guardian-gated review.")
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
    if action_type == "agent_lane_request":
        return str(event.get("normalized_summary") or "Agent lane request staged locally.")
    if action_type == "approval_gated_action_request":
        return "Guardian approval required before execution: outbound action request logged locally."
    if action_type == "operator_clarification_event":
        return "Needs clarification before routing: what kind of action is it?"
    return "Operator intake needs clarification."


def _watch_lane(lane: str) -> str:
    if lane in WATCH_DESK_LANES:
        return lane
    if lane == "cassandra_finance":
        return "cassandra_ar"
    if lane == "cassandra_business/niles_context":
        return "niles_creative"
    if lane == "chief_identity":
        return "chief_runtime"
    return "chief_runtime"


def _owner_for_parsed(parsed_result: Mapping[str, Any]) -> tuple[str, str]:
    parsed = parsed_result["parsed"]
    action_type = str(parsed["action_type"])
    lane = str(parsed["lane"])
    fields = parsed.get("fields") if isinstance(parsed.get("fields"), Mapping) else {}
    if action_type == "approval_gated_action_request":
        return "cassandra", "cassandra_ar"
    if action_type in {"income_payment_log", "expense_log", "gig_event_log"}:
        return "cassandra", "cassandra_ar"
    if action_type == "identity_signature_preference":
        return "chief", "chief_runtime"
    if action_type == "agent_lane_request":
        if fields.get("route_status") == "unknown_agent":
            return "", "chief_runtime"
        agent_id = str(fields.get("agent_id") or "")
        if agent_id:
            return agent_id, str(_execution_status_for_agent(agent_id)["lane"])
    if action_type == "operator_clarification_event":
        return "", "chief_runtime"
    if lane == "hermes":
        return "hermes", "hermes"
    if lane == "niles_creative":
        return "niles", "niles_creative"
    if lane in {"chief_runtime", "chief_identity"}:
        return "chief", "chief_runtime"
    if lane in {"cassandra_ar", "cassandra_finance", "cassandra_business/niles_context"}:
        return "cassandra", "cassandra_ar"
    if lane == "guardian_approval":
        return "guardian", "guardian_approval"
    return "", _watch_lane(lane)


def _route_decision(
    *,
    raw_text: str,
    parsed_result: Mapping[str, Any],
    surface: str,
    receiving_agent_id: str | None = None,
) -> dict[str, Any]:
    parsed = parsed_result["parsed"]
    addressed = _extract_addressed_agent(raw_text)
    addressed_agent = addressed["agent_id"]
    receiving_agent = _surface_receiving_agent(surface, receiving_agent_id)
    owner_agent, owner_lane = _owner_for_parsed(parsed_result)
    if not owner_agent and addressed_agent:
        owner_agent = addressed_agent
        owner_lane = str(_execution_status_for_agent(owner_agent)["lane"])
    if not owner_agent and receiving_agent and receiving_agent != "mac_composer":
        owner_agent = receiving_agent
        owner_lane = str(_execution_status_for_agent(owner_agent)["lane"])

    score = float(parsed.get("confidence") or 0.0)
    confidence = (
        "low"
        if str(parsed["action_type"]) == "operator_clarification_event" or "known_agent_lane" in parsed_result.get("needs_clarification", [])
        else _confidence_label(score)
    )
    routed_from = receiving_agent or addressed_agent
    routed_to = owner_agent
    execution_status = _execution_status_for_agent(owner_agent) if owner_agent else _execution_status_for_agent("")

    if confidence == "low":
        handoff_reason = "route_confidence_low_clarification_required"
    elif addressed_agent and addressed_agent != owner_agent:
        handoff_reason = (
            f"{_agent_display_name(addressed_agent)} was named, but the request belongs to "
            f"{_agent_display_name(owner_agent)} by content or authority boundary."
        )
    elif routed_from and routed_to and routed_from != routed_to and routed_from != "mac_composer":
        handoff_reason = (
            f"{_agent_display_name(routed_from)} received a {_agent_display_name(routed_to)} intent; "
            f"patched to {_agent_display_name(routed_to)}."
        )
    elif routed_from == "mac_composer" and routed_to:
        handoff_reason = "Mac composer submitted neutral intake; owner inferred by content."
    elif addressed_agent and addressed_agent == owner_agent:
        handoff_reason = "explicit_agent_request_matched_owner_lane"
    elif routed_to:
        handoff_reason = "owner_inferred_by_content"
    else:
        handoff_reason = "owner_not_confident"

    return {
        "received_surface": surface,
        "addressed_agent": addressed_agent,
        "addressed_agent_label": addressed["requested_agent"],
        "inferred_owner_agent": owner_agent,
        "inferred_owner_lane": owner_lane,
        "route_confidence": confidence,
        "route_confidence_score": score,
        "routed_from_agent": routed_from,
        "routed_to_agent": routed_to,
        "handoff_reason": handoff_reason,
        "execution_mode": execution_status["execution_mode"],
        "agent_execution": execution_status,
    }


def _approval_required_for(parsed_result: Mapping[str, Any]) -> bool:
    parsed = parsed_result["parsed"]
    fields = parsed.get("fields") if isinstance(parsed.get("fields"), Mapping) else {}
    return str(parsed["action_type"]) == "approval_gated_action_request" or bool(
        fields.get("guardian_approval_required")
    )


def _operator_visible_reply(event: Mapping[str, Any]) -> str:
    action_type = str(event.get("parsed", {}).get("action_type") or "")
    owner = str(event.get("routed_to_agent") or event.get("inferred_owner_agent") or "")
    routed_from = str(event.get("routed_from_agent") or "")
    confidence = str(event.get("route_confidence") or "")
    execution_mode = str(event.get("execution_mode") or "")
    if event.get("needs_clarification"):
        if "known_agent_lane" in event.get("needs_clarification", []):
            return str(event.get("normalized_summary") or "I need a known agent lane before routing that.")
        if action_type == "identity_signature_preference":
            return format_operator_intake_reply({key: value for key, value in event.items() if key != "operator_visible_reply"})
        fields = event.get("parsed", {}).get("fields") if isinstance(event.get("parsed"), Mapping) else {}
        if action_type == "income_payment_log" and isinstance(fields, Mapping) and fields.get("amount") is None:
            return str(event.get("normalized_summary") or "Need payment amount before logging income.")
        if action_type == "operator_clarification_event":
            return "I need one detail before routing that: what kind of action is it?"
    if confidence == "low":
        if "known_agent_lane" in event.get("needs_clarification", []):
            return str(event.get("normalized_summary") or "I need a known agent lane before routing that.")
        return "I need one detail before routing that: what kind of action is it?"
    if event.get("approval_required"):
        return (
            "That's a Cassandra outbound action. I logged it for Cassandra; "
            "Guardian approval is required before execution."
        )
    if execution_mode == "logical_only":
        return f"{_agent_display_name(owner)} lane recognized; executor is not wired yet. I recorded the request."
    if routed_from == "mac_composer" and action_type == "identity_signature_preference":
        return format_operator_intake_reply({key: value for key, value in event.items() if key != "operator_visible_reply"})
    if routed_from and owner and routed_from != owner:
        if owner == "cassandra":
            if action_type in {"income_payment_log", "expense_log", "gig_event_log"}:
                return "That's a Cassandra finance item. I logged it there."
            return "That's a Cassandra operations item. I staged it for Cassandra."
        if owner == "niles":
            return "That's a Niles creative prep request. I staged it for Niles."
        if owner == "chief":
            return "That's a Chief/system review request. I routed it to Chief."
        if owner == "hermes":
            return "That's a Hermes adapter/protocol check. I staged it for Hermes."
        if owner == "guardian":
            return "That needs Guardian approval before execution."
    if action_type in {"income_payment_log", "expense_log", "gig_event_log", "identity_signature_preference"}:
        return _watch_plain_line(event)
    return format_operator_intake_reply({key: value for key, value in event.items() if key != "operator_visible_reply"})


def _build_watch_item(event: Mapping[str, Any], receipt_ref: str) -> dict[str, Any]:
    parsed = event["parsed"]
    action_type = str(parsed["action_type"])
    lane = str(parsed["lane"])
    skill = event.get("operator_skill") if isinstance(event.get("operator_skill"), Mapping) else _operator_skill_for_action(action_type)
    return {
        "item_id": f"operator_intake:{event['intake_id']}",
        "intake_id": event["intake_id"],
        "action_type": action_type,
        "skill_id": event.get("skill_id", skill.get("skill_id", "")),
        "owner_agent": event.get("owner_agent") or event.get("inferred_owner_agent", ""),
        "owner_lane": event.get("owner_lane") or event.get("inferred_owner_lane", ""),
        "lane": str(skill.get("watch_desk_lane") or _watch_lane(lane)),
        "urgency": "watch",
        "plain_line": _watch_plain_line(event),
        "source_receipt_ref": receipt_ref,
        "missing_fields": list(event.get("needs_clarification", [])),
        "operator_local_timezone": event.get("operator_local_timezone", DEFAULT_OPERATOR_TIMEZONE),
        "operator_local_date": event.get("operator_local_date", ""),
        "normalized_event_date": event.get("normalized_event_date", ""),
        "one_next_safe_action": "Review the local receipt; keep external mutation behind the existing approval spine.",
        "push_class": str(skill.get("push_class") or "on_demand"),
        "received_surface": event.get("received_surface", ""),
        "addressed_agent": event.get("addressed_agent", ""),
        "inferred_owner_agent": event.get("inferred_owner_agent", ""),
        "inferred_owner_lane": event.get("inferred_owner_lane", ""),
        "route_confidence": event.get("route_confidence", ""),
        "routed_from_agent": event.get("routed_from_agent", ""),
        "routed_to_agent": event.get("routed_to_agent", ""),
        "handoff_reason": event.get("handoff_reason", ""),
        "execution_mode": event.get("execution_mode", ""),
        "direct_surface_available": event.get("direct_surface_available", False),
        "fallback_route_available": event.get("fallback_route_available", False),
        "spawn_supported": event.get("spawn_supported", False),
        "route_back_supported": event.get("route_back_supported", False),
        "operator_visible_reply": event.get("operator_visible_reply", ""),
    }


def _receipt_payload(event: Mapping[str, Any], created_at_utc: str) -> dict[str, Any]:
    parsed = event["parsed"]
    action_type = str(parsed["action_type"])
    skill = event.get("operator_skill") if isinstance(event.get("operator_skill"), Mapping) else _operator_skill_for_action(action_type)
    return {
        "schema_version": skill.get("receipt_schema") or "operator_intake_receipt_v0",
        "intake_id": event["intake_id"],
        "skill_id": event.get("skill_id") or skill.get("skill_id", ""),
        "action_type": action_type,
        "owner_agent": event.get("owner_agent") or skill.get("owner_agent", ""),
        "owner_lane": event.get("owner_lane") or skill.get("owner_lane", ""),
        "lane": parsed["lane"],
        "normalized_summary": event["normalized_summary"],
        "parsed_fields": parsed["fields"],
        "required_fields": list(skill.get("required_fields", [])),
        "optional_fields": list(skill.get("optional_fields", [])),
        "must_not": list(skill.get("must_not", [])),
        "reference_data_needed": list(skill.get("reference_data_needed", [])),
        "source_surface": event.get("surface", ""),
        "operator_local_timezone": event.get("operator_local_timezone", DEFAULT_OPERATOR_TIMEZONE),
        "operator_local_date": event.get("operator_local_date", ""),
        "normalized_event_date": event.get("normalized_event_date", ""),
        "received_surface": event.get("received_surface", ""),
        "addressed_agent": event.get("addressed_agent", ""),
        "inferred_owner_agent": event.get("inferred_owner_agent", ""),
        "inferred_owner_lane": event.get("inferred_owner_lane", ""),
        "route_confidence": event.get("route_confidence", ""),
        "routed_from_agent": event.get("routed_from_agent", ""),
        "routed_to_agent": event.get("routed_to_agent", ""),
        "handoff_reason": event.get("handoff_reason", ""),
        "execution_mode": event.get("execution_mode", ""),
        "direct_surface_available": event.get("direct_surface_available", False),
        "fallback_route_available": event.get("fallback_route_available", False),
        "spawn_supported": event.get("spawn_supported", False),
        "route_back_supported": event.get("route_back_supported", False),
        "agent_execution": event.get("agent_execution", {}),
        "operator_visible_reply": event.get("operator_visible_reply", ""),
        "safe_actions_taken": event["safe_actions_taken"],
        "receipt_refs": event.get("receipt_refs", []),
        "approval_required": bool(event.get("approval_required")),
        "external_calls_performed": False,
        "invoice_marked_paid": bool(parsed.get("fields", {}).get("invoice_marked_paid", False)),
        "tax_advice_given": bool(parsed.get("fields", {}).get("tax_advice_given", False)),
        "mutation_scope": "local_receipt_read_model_only",
        "created_at_utc": created_at_utc,
        "cross_link_refs": list(event.get("cross_link_refs", [])),
        "duplicate_detected": bool(event.get("duplicate_detected", False)),
        "duplicate_of_intake_id": event.get("duplicate_of_intake_id", ""),
        "idempotency_key": event.get("idempotency_key", ""),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _write_receipt(event: Mapping[str, Any], *, receipt_root: str | Path, created_at_utc: str) -> dict[str, str]:
    root = _rooted(receipt_root)
    root.mkdir(parents=True, exist_ok=True)
    action_type = str(event["parsed"]["action_type"])
    filename = f"{_safe_filename(str(event['intake_id']))}_{_safe_filename(action_type)}_receipt.json"
    path = root / filename
    receipt_ref = f"{path.as_posix()}#receipt"
    receipt_event = dict(event)
    receipt_event["receipt_refs"] = [receipt_ref]
    path.write_text(stable_json(_receipt_payload(receipt_event, created_at_utc)), encoding="utf-8")
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
            "operator_skill_schema_version": "OPERATOR_SKILL_V0",
            "operator_skill_rows": operator_skill_rows(),
            "operator_skill_reference_data_needs": operator_skill_reference_data_needs_manifest(),
            "surface_wiring_status": dict(SURFACE_WIRING_STATUS),
            "agent_execution_modes": {
                agent_id: agent_execution_mode_status(agent_id)
                for agent_id in AGENT_EXECUTION_MODE_REGISTRY_V0
            },
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
            "operator_skill_schema_version": "OPERATOR_SKILL_V0",
            "operator_skill_rows": operator_skill_rows(),
            "operator_skill_reference_data_needs": operator_skill_reference_data_needs_manifest(),
            "surface_wiring_status": dict(SURFACE_WIRING_STATUS),
            "agent_execution_modes": {
                agent_id: agent_execution_mode_status(agent_id)
                for agent_id in AGENT_EXECUTION_MODE_REGISTRY_V0
            },
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
    operator_timezone: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    receiving_agent_id: str | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any]:
    """Create an OPERATOR_INTAKE_EVENT_V0 and write local artifacts when safe."""

    if surface not in SUPPORTED_SURFACES:
        raise ValueError(f"unsupported surface: {surface}")
    received = _canonical_received_at(received_at_utc)
    timezone_name = _operator_timezone_name(operator_timezone)
    operator_local_date = _operator_local_date(received, timezone_name)
    parsed_result = parse_operator_intake_text(
        raw_text,
        received_at_utc=received,
        operator_timezone=timezone_name,
        session_context=session_context,
    )
    route_decision = _route_decision(
        raw_text=raw_text,
        parsed_result=parsed_result,
        surface=surface,
        receiving_agent_id=receiving_agent_id,
    )
    text_hash = "sha256:" + _sha256_text(_normalized_text(raw_text))
    local_text_allowed = surface == "local_cli"
    action_type = str(parsed_result["parsed"]["action_type"])
    parsed_fields = parsed_result["parsed"].get("fields") if isinstance(parsed_result["parsed"].get("fields"), Mapping) else {}
    skill = _operator_skill_for_action(action_type)
    intake_id = _local_skill_intake_id(
        action_type=action_type,
        fields=parsed_fields,
        raw_text=raw_text,
        surface=surface,
        operator=operator,
        received_at_utc=received,
        operator_timezone=timezone_name,
    )
    idempotency_key = _sha256_text(
        "|".join(
            [
                str(skill.get("skill_id", "")),
                surface,
                operator,
                _local_skill_idempotency_date(
                    action_type,
                    parsed_fields,
                    received,
                    operator_timezone=timezone_name,
                ),
                _normalized_text(raw_text),
                _stable_compact_json(parsed_fields),
            ]
        )
    )
    safe_action = _safe_action_for(action_type)
    approval_required = _approval_required_for(parsed_result)
    clarifications = set(parsed_result["needs_clarification"])
    missing_required = _skill_required_missing(skill, clarifications)
    blocking_clarification = action_type == "operator_clarification_event" or bool(
        clarifications.intersection({"referent:this", "referent:that", "referent:it"})
        or "known_agent_lane" in clarifications
        or missing_required
    )
    should_write_clarification_proof = (
        action_type == "operator_clarification_event"
        and is_operator_intake_clarification_candidate(raw_text)
    )
    should_write_local_receipt = (
        (action_type in SUPPORTED_ACTION_TYPES and safe_action and not blocking_clarification)
        or should_write_clarification_proof
    )

    event: dict[str, Any] = {
        "schema_version": OPERATOR_INTAKE_SCHEMA_VERSION,
        "intake_id": intake_id,
        "received_at_utc": received,
        "surface": surface,
        "received_surface": route_decision["received_surface"],
        "operator": operator,
        "operator_local_timezone": timezone_name,
        "operator_local_date": operator_local_date,
        "normalized_event_date": str(
            parsed_fields.get("normalized_event_date")
            or parsed_fields.get("event_date")
            or parsed_fields.get("associated_gig_date")
            or operator_local_date
        ),
        "normalized_summary": parsed_result["normalized_summary"],
        "parsed": parsed_result["parsed"],
        "risk_tier": parsed_result["risk_tier"],
        "needs_clarification": parsed_result["needs_clarification"],
        "referent_refs": parsed_result["referent_refs"],
        "cross_link_refs": _initial_cross_link_refs(parsed_result),
        "proposed_actions": parsed_result["proposed_actions"],
        "safe_actions_taken": [safe_action] if safe_action and should_write_local_receipt else [],
        "approval_required": approval_required,
        "receipts": [],
        "receipt_refs": [],
        "watch_desk_items": [],
        "stop_condition": parsed_result["stop_condition"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "raw_text_stored": local_text_allowed,
        "addressed_agent": route_decision["addressed_agent"],
        "addressed_agent_label": route_decision["addressed_agent_label"],
        "inferred_owner_agent": route_decision["inferred_owner_agent"],
        "inferred_owner_lane": route_decision["inferred_owner_lane"],
        "route_confidence": route_decision["route_confidence"],
        "route_confidence_score": route_decision["route_confidence_score"],
        "routed_from_agent": route_decision["routed_from_agent"],
        "routed_to_agent": route_decision["routed_to_agent"],
        "handoff_reason": route_decision["handoff_reason"],
        "execution_mode": route_decision["execution_mode"],
        "direct_surface_available": route_decision["agent_execution"]["direct_surface_available"],
        "fallback_route_available": route_decision["agent_execution"]["fallback_route_available"],
        "spawn_supported": route_decision["agent_execution"]["spawn_supported"],
        "route_back_supported": route_decision["agent_execution"]["route_back_supported"],
        "agent_execution": route_decision["agent_execution"],
        "operator_skill": skill,
        "skill_id": skill.get("skill_id", ""),
        "receipt_schema": skill.get("receipt_schema", ""),
        "owner_agent": skill.get("owner_agent", route_decision["inferred_owner_agent"]),
        "owner_lane": skill.get("owner_lane", route_decision["inferred_owner_lane"]),
        "safe_local_action": skill.get("safe_local_action", safe_action),
        "approval_action": skill.get("approval_action"),
        "watch_desk_lane": skill.get("watch_desk_lane", _watch_lane(str(parsed_result["parsed"]["lane"]))),
        "push_class": skill.get("push_class", "on_demand"),
        "idempotency_key": "sha256:" + idempotency_key,
    }
    event["operator_visible_reply"] = _operator_visible_reply(event)
    if local_text_allowed:
        event["raw_text"] = raw_text
    else:
        event["raw_text_ref"] = text_hash

    if should_write_local_receipt:
        existing = _existing_event_by_id(read_model_root, intake_id)
        if existing and existing.get("receipts"):
            event["duplicate_detected"] = True
            event["duplicate_of_intake_id"] = intake_id
            event["receipts"] = [receipt for receipt in existing.get("receipts", []) if isinstance(receipt, Mapping)]
            event["receipt_refs"] = [
                f"{receipt['path']}#receipt"
                for receipt in event["receipts"]
                if isinstance(receipt, Mapping) and receipt.get("path")
            ]
            event["watch_desk_items"] = [
                item for item in existing.get("watch_desk_items", []) if isinstance(item, Mapping)
            ]
            event["safe_actions_taken"] = ["reuse_existing_local_receipt_ref"] if safe_action else []
            event["stop_condition"] = "duplicate_local_receipt_reused"
            event["watch_desk_feed_refresh"] = _refresh_watch_desk_feed(
                read_model_root=read_model_root,
                generated_at=utc_now(),
            )
            return event
        created_at = utc_now()
        receipt = _write_receipt(event, receipt_root=receipt_root, created_at_utc=created_at)
        receipt_ref = f"{receipt['path']}#receipt"
        watch_item = _build_watch_item(event, receipt_ref)
        event["receipts"] = [receipt]
        event["receipt_refs"] = [receipt_ref]
        event["watch_desk_items"] = [watch_item]
        if approval_required:
            event["stop_condition"] = "guardian_approval_required_local_receipt_written"
        elif should_write_clarification_proof:
            event["stop_condition"] = "clarification_proof_written"
        else:
            event["stop_condition"] = "local_receipt_written"
        _write_read_model(event, read_model_root=read_model_root, generated_at=created_at)
        event["watch_desk_feed_refresh"] = _refresh_watch_desk_feed(
            read_model_root=read_model_root,
            generated_at=created_at,
        )

    return event


def process_operator_intake_batch(
    *,
    raw_text: str,
    surface: str = "local_cli",
    operator: str = "Winship",
    received_at_utc: str | None = None,
    operator_timezone: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    receiving_agent_id: str | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> list[dict[str, Any]]:
    if surface not in SUPPORTED_SURFACES:
        raise ValueError(f"unsupported surface: {surface}")
    received = _canonical_received_at(received_at_utc)
    timezone_name = _operator_timezone_name(operator_timezone)
    local_context: dict[str, Any] = dict(session_context or {})
    recent_gigs = list(local_context.get("recent_gigs") or [])
    local_context["recent_gigs"] = recent_gigs
    events: list[dict[str, Any]] = []
    for part in split_operator_intake_text(raw_text):
        event = process_operator_intake(
            raw_text=part,
            surface=surface,
            operator=operator,
            received_at_utc=received,
            operator_timezone=timezone_name,
            session_context=local_context,
            receiving_agent_id=receiving_agent_id,
            read_model_root=read_model_root,
            receipt_root=receipt_root,
        )
        events.append(event)
        if event["parsed"]["action_type"] == "gig_event_log":
            recent_gigs.append(event)
    linked_events = [event for event in events if event.get("receipts")]
    if len(linked_events) > 1:
        group_id = _row_id("operator_intake_group", surface, operator, received, _normalized_text(raw_text))
        for event in linked_events:
            if event.get("duplicate_detected"):
                continue
            link_refs = {
                str(ref)
                for ref in event.get("cross_link_refs", [])
                if str(ref)
            }
            for other in linked_events:
                if other["intake_id"] == event["intake_id"]:
                    continue
                link_refs.add(str(other["intake_id"]))
                for receipt_ref in other.get("receipt_refs", []):
                    if str(receipt_ref):
                        link_refs.add(str(receipt_ref))
            event["batch_group_id"] = group_id
            event["cross_link_refs"] = sorted(link_refs)
            created_at = utc_now()
            receipt = _write_receipt(event, receipt_root=receipt_root, created_at_utc=created_at)
            receipt_ref = f"{receipt['path']}#receipt"
            event["receipts"] = [receipt]
            event["receipt_refs"] = [receipt_ref]
            event["watch_desk_items"] = [_build_watch_item(event, receipt_ref)]
            _write_read_model(event, read_model_root=read_model_root, generated_at=created_at)
            event["watch_desk_feed_refresh"] = _refresh_watch_desk_feed(
                read_model_root=read_model_root,
                generated_at=created_at,
            )
    return events


def _surface_response_from_events(
    *,
    surface: str,
    events: list[Mapping[str, Any]],
) -> dict[str, Any]:
    replies = [format_operator_intake_reply(event) for event in events]
    event_refs = [str(event["intake_id"]) for event in events]
    receipt_refs = [
        f"{receipt['path']}#receipt"
        for event in events
        for receipt in event.get("receipts", [])
        if isinstance(receipt, Mapping) and receipt.get("path")
    ]
    watch_refs = [
        str(item["item_id"])
        for event in events
        for item in event.get("watch_desk_items", [])
        if isinstance(item, Mapping) and item.get("item_id")
    ]
    missing_fields = sorted(
        {
            str(missing)
            for event in events
            for missing in event.get("needs_clarification", [])
            if str(missing)
        }
    )
    action_types = [str(event.get("parsed", {}).get("action_type") or "") for event in events]
    lanes = [str(event.get("parsed", {}).get("lane") or "") for event in events]
    risk_tiers = [str(event.get("risk_tier") or "low") for event in events]
    approval_required = any(bool(event.get("approval_required")) for event in events)
    execution_modes = sorted({str(event.get("execution_mode") or "") for event in events if event.get("execution_mode")})
    owner_agents = sorted(
        {str(event.get("inferred_owner_agent") or "") for event in events if event.get("inferred_owner_agent")}
    )
    primary = events[0]
    reply_text = "\n".join(reply for reply in replies if reply)
    return {
        "schema_version": "operator_intake_surface_response_v0",
        "handled": True,
        "surface": surface,
        "intake_id": primary["intake_id"],
        "intake_event_refs": event_refs,
        "receipt_refs": receipt_refs,
        "watch_desk_refs": watch_refs,
        "action_type": "multi_intent" if len(set(action_types)) > 1 else action_types[0],
        "action_types": action_types,
        "lane": "multi_lane" if len(set(lanes)) > 1 else lanes[0],
        "lanes": lanes,
        "risk_tier": "high" if "high" in risk_tiers else "low",
        "operator_local_timezone": primary.get("operator_local_timezone", DEFAULT_OPERATOR_TIMEZONE),
        "operator_local_date": primary.get("operator_local_date", ""),
        "normalized_event_date": primary.get("normalized_event_date", ""),
        "received_surface": primary.get("received_surface", surface),
        "addressed_agent": primary.get("addressed_agent", ""),
        "inferred_owner_agent": primary.get("inferred_owner_agent", ""),
        "inferred_owner_lane": primary.get("inferred_owner_lane", ""),
        "route_confidence": primary.get("route_confidence", ""),
        "routed_from_agent": primary.get("routed_from_agent", ""),
        "routed_to_agent": primary.get("routed_to_agent", ""),
        "handoff_reason": primary.get("handoff_reason", ""),
        "execution_mode": primary.get("execution_mode", ""),
        "direct_surface_available": primary.get("direct_surface_available", False),
        "fallback_route_available": primary.get("fallback_route_available", False),
        "spawn_supported": primary.get("spawn_supported", False),
        "route_back_supported": primary.get("route_back_supported", False),
        "execution_modes": execution_modes,
        "owner_agents": owner_agents,
        "agent_execution": primary.get("agent_execution", {}),
        "reply": reply_text,
        "reply_text": reply_text,
        "missing_fields": missing_fields,
        "event": dict(primary),
        "events": [dict(event) for event in events],
        "approval_required": approval_required,
        "external_calls_performed": False,
        "safety_flags": dict(AUTHORITY_BOUNDARY),
    }


def try_process_surface_operator_intake(
    raw_text: str,
    *,
    surface: str,
    operator: str = "Winship",
    received_at_utc: str | None = None,
    operator_timezone: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    receiving_agent_id: str | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any] | None:
    candidate = is_universal_operator_intake_candidate(raw_text)
    clarification_candidate = is_operator_intake_clarification_candidate(raw_text)
    if not candidate and not clarification_candidate:
        return None
    events = process_operator_intake_batch(
        raw_text=raw_text,
        surface=surface,
        operator=operator,
        received_at_utc=received_at_utc,
        operator_timezone=operator_timezone,
        session_context=session_context,
        receiving_agent_id=receiving_agent_id,
        read_model_root=read_model_root,
        receipt_root=receipt_root,
    )
    response = _surface_response_from_events(surface=surface, events=events)
    if clarification_candidate and not candidate:
        response["handled"] = False
    return response


def process_mac_composer_operator_intake(
    raw_text: str,
    *,
    operator: str = "Winship",
    received_at_utc: str | None = None,
    operator_timezone: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any]:
    routed = try_process_surface_operator_intake(
        raw_text,
        surface="mac_composer",
        operator=operator,
        received_at_utc=received_at_utc,
        operator_timezone=operator_timezone,
        session_context=session_context,
        receiving_agent_id="mac_composer",
        read_model_root=read_model_root,
        receipt_root=receipt_root,
    )
    if routed is not None:
        return routed
    event = process_operator_intake(
        raw_text=raw_text,
        surface="mac_composer",
        operator=operator,
        received_at_utc=received_at_utc,
        operator_timezone=operator_timezone,
        session_context=session_context,
        receiving_agent_id="mac_composer",
        read_model_root=read_model_root,
        receipt_root=receipt_root,
    )
    return {
        "schema_version": "operator_intake_surface_response_v0",
        "handled": False,
        "surface": "mac_composer",
        "action_type": event["parsed"]["action_type"],
        "lane": event["parsed"]["lane"],
        "risk_tier": event["risk_tier"],
        "operator_local_timezone": event["operator_local_timezone"],
        "operator_local_date": event["operator_local_date"],
        "normalized_event_date": event["normalized_event_date"],
        "received_surface": event["received_surface"],
        "addressed_agent": event["addressed_agent"],
        "inferred_owner_agent": event["inferred_owner_agent"],
        "inferred_owner_lane": event["inferred_owner_lane"],
        "route_confidence": event["route_confidence"],
        "routed_from_agent": event["routed_from_agent"],
        "routed_to_agent": event["routed_to_agent"],
        "handoff_reason": event["handoff_reason"],
        "execution_mode": event["execution_mode"],
        "direct_surface_available": event["direct_surface_available"],
        "fallback_route_available": event["fallback_route_available"],
        "spawn_supported": event["spawn_supported"],
        "route_back_supported": event["route_back_supported"],
        "agent_execution": event["agent_execution"],
        "reply": event["operator_visible_reply"],
        "reply_text": event["operator_visible_reply"],
        "intake_event_refs": [],
        "receipt_refs": [],
        "watch_desk_refs": [],
        "event": event,
        "events": [event],
        "needs_clarification": event["needs_clarification"],
        "missing_fields": event["needs_clarification"],
        "approval_required": event["approval_required"],
        "external_calls_performed": False,
        "safety_flags": dict(AUTHORITY_BOUNDARY),
    }


def infer_agent_lane_target(
    raw_text: str,
    *,
    default_agent_id: str = "",
    operator_timezone: str | None = None,
) -> dict[str, Any]:
    """Infer the intended agent lane without executing or writing anything."""

    text = _normalized_text(raw_text)
    parsed = parse_operator_intake_text(text, operator_timezone=operator_timezone)
    owner_agent, owner_lane = _owner_for_parsed(parsed)
    resolved_default = _resolve_agent_id(default_agent_id) if default_agent_id else ""
    if not owner_agent and resolved_default in AGENT_EXECUTION_MODE_REGISTRY_V0:
        owner_agent = resolved_default
        owner_lane = str(_execution_status_for_agent(resolved_default)["lane"])
    addressed = _extract_addressed_agent(text)
    basis = "explicit_agent_prefix" if addressed["agent_id"] and addressed["agent_id"] == owner_agent else "content_inference"
    if str(parsed["parsed"]["action_type"]) == "operator_clarification_event":
        basis = "unknown"
    confidence = float(parsed["parsed"].get("confidence") or 0.0)
    return {
        "agent_id": owner_agent,
        "lane": owner_lane,
        "basis": basis,
        "confidence": confidence,
        "route_confidence": _confidence_label(confidence),
    }


def direct_agent_surface_status(agent_id: str) -> dict[str, Any]:
    status = agent_execution_mode_status(agent_id)
    if status.get("agent_id") == "mac_composer":
        surface_status = "CALLABLE_CONTRACT_ONLY"
    elif status.get("current_status") == "wired" or status.get("direct_surface_available"):
        surface_status = "WIRED"
    elif status.get("fallback_route_available"):
        surface_status = "FALLBACK_ONLY"
    else:
        surface_status = "NOT_WIRED"
    status["surface_status"] = surface_status
    status["live_direct_endpoint"] = bool(status.get("live_direct_endpoint"))
    return status


def build_agent_surface_parity_report() -> dict[str, Any]:
    agent_ids = ("cassandra", "niles", "chief", "hermes", "guardian", "watch desk", "mac_composer")
    surfaces = {agent_id: direct_agent_surface_status(agent_id) for agent_id in agent_ids}
    return {
        "schema_version": "agent_surface_parity_report_v0",
        "agents": surfaces,
        "surfaces": surfaces,
        "live_surfaces_found": [
            agent_id for agent_id, surface in surfaces.items() if surface["execution_mode"] == "live_listener"
        ],
        "callable_contract_surfaces": [agent_id for agent_id, surface in surfaces.items() if agent_id == "mac_composer"],
        "direct_surfaces_wired": {
            agent_id: bool(surface["direct_surface_available"]) for agent_id, surface in surfaces.items()
        },
        "fallback_routes_available": {
            agent_id: bool(surface["fallback_route_available"]) for agent_id, surface in surfaces.items()
        },
        "spawn_supported": {agent_id: bool(surface["spawn_supported"]) for agent_id, surface in surfaces.items()},
        "execution_modes": {agent_id: surface["execution_mode"] for agent_id, surface in surfaces.items()},
        "logical_only_surfaces": [
            agent_id for agent_id, surface in surfaces.items() if surface["execution_mode"] == "logical_only"
        ],
        "sidecar_adapter_lanes": [
            agent_id for agent_id, surface in surfaces.items() if surface["execution_mode"] == "sidecar_adapter"
        ],
        "human_approval_lanes": [
            agent_id for agent_id, surface in surfaces.items() if surface["execution_mode"] == "human_approval"
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _direct_surface_for_agent(agent_id: str) -> str:
    if agent_id == "cassandra":
        return "telegram"
    if agent_id == "mac_composer":
        return "mac_composer"
    return f"{agent_id.replace(' ', '_')}_direct"


def _direct_response_status(response: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    if response.get("route_confidence") == "low":
        return "CLARIFICATION_REQUIRED"
    routed_from = str(response.get("routed_from_agent") or "")
    routed_to = str(response.get("routed_to_agent") or "")
    if routed_from and routed_to and routed_from != routed_to:
        return "PATCHED_TO_OWNER"
    if not status.get("direct_surface_available") and status.get("fallback_route_available"):
        return "ROUTED_VIA_FALLBACK"
    return "ROUTED"


def _augment_direct_response(
    response: dict[str, Any],
    *,
    resolved: str,
    status: Mapping[str, Any],
    target: Mapping[str, Any],
) -> dict[str, Any]:
    response["schema_version"] = "operator_intake_direct_surface_response_v0"
    response["agent_id"] = resolved
    response["surface_status"] = status["surface_status"]
    response["direct_surface_available"] = bool(status["direct_surface_available"])
    response["fallback_route_available"] = bool(status["fallback_route_available"])
    response["spawn_supported"] = bool(status["spawn_supported"])
    response["route_back_supported"] = bool(status["route_back_supported"])
    response["target_agent_id"] = target["agent_id"]
    response["target_lane"] = target["lane"]
    response["target_basis"] = target["basis"]
    response["routing_status"] = _direct_response_status(response, status)
    response["wrong_agent_recovery"] = bool(
        response.get("routed_from_agent")
        and response.get("routed_to_agent")
        and response.get("routed_from_agent") != response.get("routed_to_agent")
    )
    response["safe_next_step"] = status["safe_next_step"]
    return response


def process_direct_agent_surface_operator_intake(
    raw_text: str,
    *,
    agent_id: str,
    operator: str = "Winship",
    received_at_utc: str | None = None,
    operator_timezone: str | None = None,
    session_context: Mapping[str, Any] | None = None,
    read_model_root: str | Path = DEFAULT_EXPORT_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any]:
    """Classify a direct-agent context without pretending unwired agents are live listeners."""

    resolved = _resolve_agent_id(agent_id)
    status = direct_agent_surface_status(resolved)
    target = infer_agent_lane_target(raw_text, default_agent_id=resolved, operator_timezone=operator_timezone)
    surface = _direct_surface_for_agent(resolved)
    routed = try_process_surface_operator_intake(
        raw_text,
        surface=surface,
        operator=operator,
        received_at_utc=received_at_utc,
        operator_timezone=operator_timezone,
        session_context=session_context,
        receiving_agent_id=resolved,
        read_model_root=read_model_root,
        receipt_root=receipt_root,
    )
    if routed is not None:
        return _augment_direct_response(dict(routed), resolved=resolved, status=status, target=target)

    event = process_operator_intake(
        raw_text=raw_text,
        surface=surface,
        operator=operator,
        received_at_utc=received_at_utc,
        operator_timezone=operator_timezone,
        session_context=session_context,
        receiving_agent_id=resolved,
        read_model_root=read_model_root,
        receipt_root=receipt_root,
    )
    response = {
        "schema_version": "operator_intake_direct_surface_response_v0",
        "handled": False,
        "surface": surface,
        "intake_id": event["intake_id"],
        "intake_event_refs": [],
        "receipt_refs": [],
        "watch_desk_refs": [],
        "action_type": event["parsed"]["action_type"],
        "lane": event["parsed"]["lane"],
        "risk_tier": event["risk_tier"],
        "operator_local_timezone": event["operator_local_timezone"],
        "operator_local_date": event["operator_local_date"],
        "normalized_event_date": event["normalized_event_date"],
        "received_surface": event["received_surface"],
        "addressed_agent": event["addressed_agent"],
        "inferred_owner_agent": event["inferred_owner_agent"],
        "inferred_owner_lane": event["inferred_owner_lane"],
        "route_confidence": event["route_confidence"],
        "routed_from_agent": event["routed_from_agent"],
        "routed_to_agent": event["routed_to_agent"],
        "handoff_reason": event["handoff_reason"],
        "execution_mode": event["execution_mode"],
        "direct_surface_available": event["direct_surface_available"],
        "fallback_route_available": event["fallback_route_available"],
        "spawn_supported": event["spawn_supported"],
        "route_back_supported": event["route_back_supported"],
        "agent_execution": event["agent_execution"],
        "reply": event["operator_visible_reply"],
        "reply_text": event["operator_visible_reply"],
        "missing_fields": event["needs_clarification"],
        "event": event,
        "events": [event],
        "approval_required": event["approval_required"],
        "external_calls_performed": False,
        "safety_flags": dict(AUTHORITY_BOUNDARY),
    }
    return _augment_direct_response(response, resolved=resolved, status=status, target=target)


def load_operator_intake_read_model(*, read_model_root: str | Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return _load_read_model(read_model_root)
