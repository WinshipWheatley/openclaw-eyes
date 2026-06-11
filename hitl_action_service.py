"""
hitl_action_service.py

Service-layer API for the Human-in-the-Loop action queue.

Sits between callers (Cassandra, future dashboard) and the raw store
(hitl_pending_store.py). Adds:
  - Field validation (type, payload; recipient+amount for financial types)
  - Idempotency key deduplication for repeated proposals
  - approve_action / deny_action convenience methods
  - Action-type route-back dispatch after approval

Public API
----------
create_pending_action(source_agent, action_type, payload, *,
                      idempotency_key=None, ttl_seconds=DEFAULT)
    -> (action_id: str, created: bool)

get_pending_action(action_id) -> dict | None
list_pending_actions(status=None) -> list[dict]

approve_action(action_id, *, approved_by="operator") -> bool
deny_action(action_id, *, reason="") -> bool
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable

import hitl_pending_store as _store
from hitl_pending_store import (
    APPROVED,
    DENIED,
    EXPIRED,
    FAILED,
    WAITING_FOR_APPROVAL,
    is_hitl_enabled,
)

# ── Financial action types ────────────────────────────────────────────────────
# These require `recipient` and `amount` in the payload.

FINANCIAL_ACTION_TYPES: frozenset[str] = frozenset({
    "financial_transfer",
    "payment",
    "bill_pay",
    "wire_transfer",
    "invoice_send",
    "refund",
    "charge",
})

_DEFAULT_TTL_SECONDS = 86400  # 24 hours

OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA = "OPERATOR_ACTION_APPROVAL_REQUEST_V0"
OPERATOR_ACTION_DECISION_RECEIPT_SCHEMA = "OPERATOR_ACTION_APPROVAL_DECISION_RECEIPT_V0"
ACTION_TYPE_EXACT_GMAIL_SEND = "exact_gmail_send"

_APPROVAL_BUTTON_LABELS = ["Approve", "Deny", "Why now?"]
_ACTION_DISPATCHERS: dict[str, Callable[[dict], Mapping[str, Any] | None]] = {}


# ── Validation ────────────────────────────────────────────────────────────────

def _validate(action_type: str, payload: dict) -> None:
    """Raise ValueError if required fields are missing.

    Rules:
      - action_type must be a non-empty string
      - payload must be a dict
      - Financial types additionally require payload['recipient'] and
        payload['amount']
    """
    if not isinstance(action_type, str) or not action_type.strip():
        raise ValueError("action_type must be a non-empty string")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    if action_type in FINANCIAL_ACTION_TYPES:
        missing = [f for f in ("recipient", "amount") if not payload.get(f)]
        if missing:
            raise ValueError(
                f"Financial action '{action_type}' requires payload fields: "
                + ", ".join(missing)
            )


# ── Idempotency helpers ───────────────────────────────────────────────────────

def _derive_idem_key(source_agent: str, action_type: str, payload: dict) -> str:
    """Derive a deterministic idempotency key from the proposal content.

    Used when the caller does not supply an explicit key.  The hash is over
    source_agent + action_type + canonicalized payload JSON so that retried
    identical proposals are deduplicated automatically.
    """
    canonical = json.dumps(
        {"source_agent": source_agent, "action_type": action_type, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "auto:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _typed_reply_code(action_id: str) -> str:
    return str(action_id or "")[:4].upper()


def build_operator_action_approval_payload(
    *,
    action_type: str,
    owner_agent: str,
    owner_objective_id: str,
    request_id: str,
    summary: str,
    payload: Mapping[str, Any],
    risk_warning: str,
    expires_at: str,
    route_back: Mapping[str, Any],
    typed_fallback_reply_code: str = "",
    decision_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the generic Guardian/HITL operator-action envelope."""
    idempotency_key = request_id
    return {
        "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
        "action_type": action_type,
        "owner_agent": owner_agent,
        "owner_objective_id": owner_objective_id,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "summary": summary,
        "payload": dict(payload),
        "risk_warning": risk_warning,
        "expires_at": expires_at,
        "approval_buttons": list(_APPROVAL_BUTTON_LABELS),
        "typed_fallback_reply_code": typed_fallback_reply_code,
        "route_back": dict(route_back),
        "decision_receipt": dict(decision_receipt or {"status": "pending"}),
    }


def create_operator_action_approval_request(
    *,
    action_type: str,
    owner_agent: str,
    owner_objective_id: str,
    request_id: str,
    summary: str,
    payload: Mapping[str, Any],
    risk_warning: str,
    expires_at: str,
    route_back: Mapping[str, Any],
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    """Register an OPERATOR_ACTION_APPROVAL_REQUEST_V0 on the existing queue."""
    envelope = build_operator_action_approval_payload(
        action_type=action_type,
        owner_agent=owner_agent,
        owner_objective_id=owner_objective_id,
        request_id=request_id,
        summary=summary,
        payload=payload,
        risk_warning=risk_warning,
        expires_at=expires_at,
        route_back=route_back,
    )
    action_id, created = create_pending_action(
        owner_agent,
        action_type,
        envelope,
        idempotency_key=request_id,
        ttl_seconds=ttl_seconds,
    )
    record = get_pending_action(action_id) or {}
    stored_payload = dict(record.get("payload") or envelope)
    stored_payload["typed_fallback_reply_code"] = _typed_reply_code(action_id)
    stored_payload["approval_buttons"] = list(_APPROVAL_BUTTON_LABELS)
    if created:
        _store.update_action_payload(action_id, stored_payload)
    else:
        # Keep existing active records authoritative, but make the returned
        # envelope complete even if it was created before reply codes existed.
        if stored_payload != record.get("payload"):
            _store.update_action_payload(action_id, stored_payload)
    return {
        "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
        "action_id": action_id,
        "created": created,
        "status": WAITING_FOR_APPROVAL,
        "action_type": action_type,
        "owner_agent": owner_agent,
        "owner_objective_id": owner_objective_id,
        "request_id": request_id,
        "idempotency_key": request_id,
        "approval_buttons": list(_APPROVAL_BUTTON_LABELS),
        "typed_fallback_reply_code": _typed_reply_code(action_id),
        "payload": stored_payload,
        "execution_performed": False,
        "gmail_api_called": False,
        "email_send_performed": False,
    }


def register_action_dispatcher(
    action_type: str,
    dispatcher: Callable[[dict], Mapping[str, Any] | None],
) -> None:
    """Register a route-back dispatcher for approved operator actions."""
    if not action_type:
        raise ValueError("action_type is required")
    _ACTION_DISPATCHERS[action_type] = dispatcher


def clear_action_dispatchers_for_tests() -> None:
    """Clear injected dispatchers. Intended for tests."""
    _ACTION_DISPATCHERS.clear()


# ── Execution hook ────────────────────────────────────────────────────────────

def _on_action_approved(action: dict) -> None:
    """Called after an action transitions to APPROVED.

    Dispatches approved operator actions by action_type. Guardian/HITL records
    the human decision; action-specific code owns execution.
    """
    action_type = str(action.get("action_type") or "")
    decision_receipt = _build_decision_receipt(
        action,
        decision="approved",
        dispatch_status="not_dispatched",
    )
    try:
        dispatcher = _ACTION_DISPATCHERS.get(action_type) or _default_dispatcher(action_type)
        if dispatcher is None:
            decision_receipt["dispatch_status"] = "no_dispatcher_registered"
        else:
            dispatch_result = dispatcher(action)
            decision_receipt["dispatch_status"] = "dispatched"
            decision_receipt["dispatch_result"] = dict(dispatch_result or {})
    except Exception as exc:
        decision_receipt["dispatch_status"] = "dispatch_exception"
        decision_receipt["dispatch_error"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:200],
        }
    _store.record_action_decision_receipt(str(action["action_id"]), decision_receipt)
    print(
        f"[hitl_service] APPROVED: {action['action_id']} "
        f"type={action['action_type']} approved_by={action.get('approved_by')} "
        f"dispatch={decision_receipt.get('dispatch_status')}",
        flush=True,
    )


def _default_dispatcher(action_type: str) -> Callable[[dict], Mapping[str, Any] | None] | None:
    if action_type == ACTION_TYPE_EXACT_GMAIL_SEND:
        return _dispatch_exact_gmail_send_to_cassandra
    return None


def _dispatch_exact_gmail_send_to_cassandra(action: dict) -> Mapping[str, Any]:
    """Build the Cassandra exact-send decision without touching Gmail/broker."""
    import cassandra_operator_objective_loop as objective_loop

    return objective_loop.build_exact_send_approval_decision_from_operator_action(action)


def _build_decision_receipt(
    action: Mapping[str, Any],
    *,
    decision: str,
    dispatch_status: str,
) -> dict[str, Any]:
    payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
    request_id = str(payload.get("request_id") or action.get("idempotency_key") or "")
    return {
        "schema_version": OPERATOR_ACTION_DECISION_RECEIPT_SCHEMA,
        "decision": decision,
        "status": "recorded",
        "action_id": str(action.get("action_id") or ""),
        "action_type": str(action.get("action_type") or ""),
        "owner_agent": str(payload.get("owner_agent") or action.get("source_agent") or ""),
        "owner_objective_id": str(payload.get("owner_objective_id") or ""),
        "request_id": request_id,
        "idempotency_key": str(action.get("idempotency_key") or request_id),
        "approved_by": str(action.get("approved_by") or ""),
        "approved_at": str(action.get("approved_at") or ""),
        "denied_reason": str(action.get("denied_reason") or ""),
        "route_back": dict(payload.get("route_back") or {}) if isinstance(payload.get("route_back"), Mapping) else {},
        "dispatch_status": dispatch_status,
        "execution_performed": False,
        "gmail_api_called": False,
        "email_send_performed": False,
        "created_at": _utc_now(),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def create_pending_action(
    source_agent: str,
    action_type: str,
    payload: dict,
    *,
    idempotency_key: str | None = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> tuple[str, bool]:
    """Queue an action for approval.

    Validates fields, deduplicates via idempotency key, then delegates to
    the store.

    Returns (action_id, created) where created=False if a duplicate was found.

    Raises ValueError for invalid input.
    """
    _validate(action_type, payload)

    if idempotency_key is None:
        idempotency_key = _derive_idem_key(source_agent, action_type, payload)

    existing = _find_active_by_idem_key(idempotency_key)
    if existing is not None:
        print(
            f"[hitl_service] idempotency hit: returning existing "
            f"{existing['action_id']} for key {idempotency_key!r}",
            flush=True,
        )
        return existing["action_id"], False

    record = _store.create_pending_action(
        source_agent,
        action_type,
        payload,
        ttl_seconds,
        idempotency_key=idempotency_key,
    )
    print(
        f"[hitl_service] created {record['action_id']} "
        f"type={action_type} agent={source_agent}",
        flush=True,
    )
    return record["action_id"], True


def get_pending_action(action_id: str) -> dict | None:
    """Return a single action record by ID, or None if not found."""
    return _store.get_action(action_id)


def list_pending_actions(status: str | None = None) -> list[dict]:
    """Return all action records, optionally filtered by status.

    WAITING_FOR_APPROVAL records past their TTL are auto-expired before
    the filter is applied.
    """
    return _store.list_pending_actions(status=status)


def approve_action(action_id: str, *, approved_by: str = "operator") -> bool:
    """Transition action_id to APPROVED.

    Stamps approved_by and approved_at on the record, then calls the
    execution hook so the approved action can be handed off.

    Returns True on success, False if not found or already terminal.
    """
    ok = _store.update_action_status(
        action_id,
        APPROVED,
        approved_by=approved_by,
    )
    if ok:
        record = _store.get_action(action_id)
        if record:
            _on_action_approved(record)
    return ok


def deny_action(action_id: str, *, reason: str = "") -> bool:
    """Transition action_id to DENIED with an optional reason.

    Returns True on success, False if not found or already terminal.
    """
    ok = _store.update_action_status(
        action_id,
        DENIED,
        denied_reason=reason,
    )
    if ok:
        record = _store.get_action(action_id)
        if record:
            _store.record_action_decision_receipt(
                action_id,
                _build_decision_receipt(
                    record,
                    decision="denied",
                    dispatch_status="not_dispatched_denied",
                ),
            )
        print(
            f"[hitl_service] DENIED: {action_id} reason={reason!r}",
            flush=True,
        )
    return ok


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_active_by_idem_key(idempotency_key: str) -> dict | None:
    """Return first active WAITING_FOR_APPROVAL record with this idem key."""
    for record in _store.list_pending_actions(status=WAITING_FOR_APPROVAL):
        if record.get("idempotency_key") == idempotency_key:
            return record
    return None
