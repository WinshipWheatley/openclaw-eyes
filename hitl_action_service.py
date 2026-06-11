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
from typing import Any, Callable, Sequence

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
ACTION_TYPE_TEST_DISPATCH = "test_operator_action_dispatch"

_APPROVAL_BUTTON_LABELS = ["Approve", "Deny", "Why now?"]
_ACTION_DISPATCHERS: dict[str, Callable[[dict], Mapping[str, Any] | None]] = {}
_KNOWN_ACTION_RISK_TIERS: dict[str, str] = {
    ACTION_TYPE_EXACT_GMAIL_SEND: "high",
    "financial_transfer": "high",
    "payment": "high",
    "bill_pay": "high",
    "wire_transfer": "high",
    "invoice_send": "high",
    "refund": "high",
    "charge": "high",
    "calendar_write": "high",
    "gmail_body_read": "high",
    "file_open": "medium",
    "email_send": "medium",
    "sms": "medium",
    "social_post": "medium",
}


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


def risk_tier_for_action_type(action_type: str) -> str:
    """Fail-safe risk tier: unknown action types are high risk."""
    return _KNOWN_ACTION_RISK_TIERS.get(str(action_type or ""), "high")


def _normalize_refs(values: Sequence[str] | None = None, *fallbacks: Any) -> list[str]:
    refs: list[str] = []
    if values:
        refs.extend(str(value) for value in values if str(value or ""))
    for fallback in fallbacks:
        if isinstance(fallback, (list, tuple, set)):
            refs.extend(str(value) for value in fallback if str(value or ""))
        elif str(fallback or ""):
            refs.append(str(fallback))
    deduped: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref not in seen:
            deduped.append(ref)
            seen.add(ref)
    return deduped


def _default_execution_result(status: str, *, owner_agent: str, terminal: bool = False) -> dict[str, Any]:
    return {
        "status": status,
        "receipt_ref": "",
        "executed_at": "",
        "owner_agent": owner_agent,
        "terminal": terminal,
    }


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
    authority_refs: Sequence[str] | None = None,
    credential_lease_refs: Sequence[str] | None = None,
    risk_tier: str | None = None,
    typed_fallback_reply_code: str = "",
    decision_receipt: Mapping[str, Any] | None = None,
    execution_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the generic Guardian/HITL operator-action envelope."""
    idempotency_key = request_id
    payload_dict = dict(payload)
    promoted_authority_refs = _normalize_refs(
        authority_refs,
        payload_dict.get("authority_refs"),
        payload_dict.get("authority_envelope_ref"),
        payload_dict.get("authority_envelope_id"),
    )
    promoted_credential_refs = _normalize_refs(
        credential_lease_refs,
        payload_dict.get("credential_lease_refs"),
        payload_dict.get("credential_lease_ref"),
        payload_dict.get("credential_lease_id"),
    )
    normalized_risk_tier = str(risk_tier or payload_dict.get("risk_tier") or risk_tier_for_action_type(action_type)).lower()
    return {
        "schema_version": OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA,
        "action_type": action_type,
        "owner_agent": owner_agent,
        "owner_objective_id": owner_objective_id,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "summary": summary,
        "payload": payload_dict,
        "authority_refs": promoted_authority_refs,
        "credential_lease_refs": promoted_credential_refs,
        "risk_tier": normalized_risk_tier,
        "risk_warning": risk_warning,
        "expires_at": expires_at,
        "approval_buttons": list(_APPROVAL_BUTTON_LABELS),
        "typed_fallback_reply_code": typed_fallback_reply_code,
        "route_back": dict(route_back),
        "decision_receipt": dict(decision_receipt or {"status": "pending"}),
        "execution_result": dict(
            execution_result
            or _default_execution_result("pending_approval", owner_agent=owner_agent)
        ),
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
    authority_refs: Sequence[str] | None = None,
    credential_lease_refs: Sequence[str] | None = None,
    risk_tier: str | None = None,
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
        authority_refs=authority_refs,
        credential_lease_refs=credential_lease_refs,
        risk_tier=risk_tier,
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
    stored_payload.setdefault("authority_refs", list(envelope.get("authority_refs") or []))
    stored_payload.setdefault("credential_lease_refs", list(envelope.get("credential_lease_refs") or []))
    stored_payload.setdefault("risk_tier", str(envelope.get("risk_tier") or risk_tier_for_action_type(action_type)).lower())
    stored_payload.setdefault("execution_result", dict(envelope.get("execution_result") or {}))
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
        "authority_refs": list(stored_payload.get("authority_refs") or []),
        "credential_lease_refs": list(stored_payload.get("credential_lease_refs") or []),
        "risk_tier": str(stored_payload.get("risk_tier") or ""),
        "execution_result": dict(stored_payload.get("execution_result") or {}),
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


def register_builtin_action_dispatchers() -> tuple[str, ...]:
    """Register durable startup dispatchers for known action types."""
    _ACTION_DISPATCHERS.setdefault(ACTION_TYPE_EXACT_GMAIL_SEND, _dispatch_exact_gmail_send_to_cassandra)
    return tuple(sorted(_ACTION_DISPATCHERS))


def get_action_dispatcher(action_type: str) -> Callable[[dict], Mapping[str, Any] | None] | None:
    register_builtin_action_dispatchers()
    return _ACTION_DISPATCHERS.get(str(action_type or ""))


def registered_action_dispatchers() -> tuple[str, ...]:
    register_builtin_action_dispatchers()
    return tuple(sorted(_ACTION_DISPATCHERS))


def clear_action_dispatchers_for_tests() -> None:
    """Clear injected dispatchers. Intended for tests."""
    _ACTION_DISPATCHERS.clear()


# ── Execution hook ────────────────────────────────────────────────────────────

def _on_action_approved(action: dict) -> None:
    """Called after an action transitions to APPROVED.

    Dispatches approved operator actions by action_type. Guardian/HITL records
    the human decision; action-specific code owns execution.
    """
    dispatch_approved_action(str(action.get("action_id") or ""))


def _default_dispatcher(action_type: str) -> Callable[[dict], Mapping[str, Any] | None] | None:
    return get_action_dispatcher(action_type)


def _dispatch_exact_gmail_send_to_cassandra(action: dict) -> Mapping[str, Any]:
    """Route exact-send approval into Cassandra's reviewed exact-send gate."""
    import cassandra_operator_objective_loop as objective_loop

    return objective_loop.run_exact_send_operator_action_routeback(action)


def _action_expired(action: Mapping[str, Any]) -> bool:
    raw = str(action.get("expires_at") or "")
    if not raw:
        return False
    try:
        expires_at = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        observed = datetime.now()
    else:
        observed = datetime.now(timezone.utc).astimezone(expires_at.tzinfo)
    return observed >= expires_at


def _receipt_ref_from_dispatch_result(dispatch_result: Mapping[str, Any]) -> str:
    execution_result = dispatch_result.get("execution_result")
    if isinstance(execution_result, Mapping) and execution_result.get("receipt_ref"):
        return str(execution_result.get("receipt_ref") or "")
    receipt = dispatch_result.get("receipt")
    if isinstance(receipt, Mapping) and receipt.get("receipt_id"):
        return str(receipt.get("receipt_id") or "")
    for key in ("receipt_ref", "terminal_receipt_ref", "terminal_receipt_path", "refusal_receipt_path", "dry_run_receipt_path"):
        if dispatch_result.get(key):
            return str(dispatch_result.get(key) or "")
    return ""


def _execution_result_from_dispatch(
    action: Mapping[str, Any],
    *,
    dispatch_status: str,
    dispatch_result: Mapping[str, Any] | None = None,
    error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
    dispatch_result = dict(dispatch_result or {})
    explicit = dispatch_result.get("execution_result") if isinstance(dispatch_result.get("execution_result"), Mapping) else {}
    receipt = dispatch_result.get("receipt") if isinstance(dispatch_result.get("receipt"), Mapping) else {}
    terminal_outcome = str(receipt.get("terminal_outcome") or dispatch_result.get("terminal_outcome") or "")
    if explicit:
        status = str(explicit.get("status") or "unknown")
        terminal = bool(explicit.get("terminal", True))
    elif dispatch_status == "no_dispatcher_registered":
        status = "blocked"
        terminal = True
    elif dispatch_status == "dispatch_exception":
        status = "failed"
        terminal = True
    elif dispatch_status == "not_dispatched_expired":
        status = "expired"
        terminal = True
    elif bool(dispatch_result.get("execution_performed")) or terminal_outcome == "success":
        status = "success"
        terminal = True
    elif bool(receipt.get("requires_reconciliation")):
        status = "reconciliation_required"
        terminal = True
    elif dispatch_result.get("response_status") == "EXACT_SEND_LIVE_TRANSPORT_REFUSED":
        status = "blocked"
        terminal = True
    else:
        status = str(dispatch_result.get("status") or "failed")
        terminal = True

    result = {
        "status": status,
        "receipt_ref": _receipt_ref_from_dispatch_result(dispatch_result) or str(explicit.get("receipt_ref") or ""),
        "executed_at": _utc_now(),
        "owner_agent": str(payload.get("owner_agent") or action.get("source_agent") or ""),
        "terminal": terminal,
        "dispatch_status": dispatch_status,
    }
    if error:
        result["error"] = dict(error)
    return result


def dispatch_approved_action(action_id: str) -> dict[str, Any]:
    """Dispatch one approved operator action through its registered executor."""
    register_builtin_action_dispatchers()
    action = _store.get_action(action_id)
    if action is None:
        return {"action_id": action_id, "dispatch_status": "action_not_found", "processed": False}
    if action.get("status") != APPROVED:
        return {"action_id": action_id, "dispatch_status": "not_approved", "processed": False}
    existing_result = action.get("execution_result") if isinstance(action.get("execution_result"), Mapping) else {}
    if existing_result.get("terminal") is True:
        return {
            "action_id": action_id,
            "dispatch_status": "already_terminal",
            "execution_result": dict(existing_result),
            "processed": False,
        }
    if _action_expired(action):
        execution_result = _execution_result_from_dispatch(
            action,
            dispatch_status="not_dispatched_expired",
            dispatch_result={"status": "expired"},
        )
        _store.record_action_execution_result(action_id, execution_result)
        latest = _store.get_action(action_id) or action
        receipt = _build_decision_receipt(
            latest,
            decision="approved",
            dispatch_status="not_dispatched_expired",
            execution_result=execution_result,
        )
        _store.record_action_decision_receipt(action_id, receipt)
        return {"action_id": action_id, "dispatch_status": "not_dispatched_expired", "execution_result": execution_result, "processed": True}

    if not _store.mark_action_dispatch_in_progress(action_id):
        latest = _store.get_action(action_id) or action
        result = latest.get("execution_result") if isinstance(latest.get("execution_result"), Mapping) else {}
        return {
            "action_id": action_id,
            "dispatch_status": "dispatch_not_available",
            "execution_result": dict(result),
            "processed": False,
        }

    action = _store.get_action(action_id) or action
    action_type = str(action.get("action_type") or "")
    decision_receipt = _build_decision_receipt(
        action,
        decision="approved",
        dispatch_status="not_dispatched",
    )
    dispatcher = _ACTION_DISPATCHERS.get(action_type)
    if dispatcher is None:
        execution_result = _execution_result_from_dispatch(
            action,
            dispatch_status="no_dispatcher_registered",
            dispatch_result={"status": "blocked"},
        )
        _store.record_action_execution_result(action_id, execution_result)
        decision_receipt["dispatch_status"] = "no_dispatcher_registered"
        decision_receipt["execution_result"] = execution_result
        _store.record_action_decision_receipt(action_id, decision_receipt)
        print(
            f"[hitl_service] APPROVED: {action_id} type={action_type} "
            "dispatch=no_dispatcher_registered",
            flush=True,
        )
        return {"action_id": action_id, "dispatch_status": "no_dispatcher_registered", "execution_result": execution_result, "processed": True}

    try:
        dispatch_result = dispatcher(action)
        dispatch_result_dict = dict(dispatch_result or {})
        execution_result = _execution_result_from_dispatch(
            action,
            dispatch_status="dispatched",
            dispatch_result=dispatch_result_dict,
        )
        _store.record_action_execution_result(action_id, execution_result)
        decision_receipt["dispatch_status"] = "dispatched"
        decision_receipt["dispatch_result"] = dispatch_result_dict
        decision_receipt["execution_result"] = execution_result
    except Exception as exc:
        dispatch_error = {
            "type": type(exc).__name__,
            "message": str(exc)[:200],
        }
        execution_result = _execution_result_from_dispatch(
            action,
            dispatch_status="dispatch_exception",
            error=dispatch_error,
        )
        _store.record_action_execution_result(action_id, execution_result)
        decision_receipt["dispatch_status"] = "dispatch_exception"
        decision_receipt["dispatch_error"] = dispatch_error
        decision_receipt["execution_result"] = execution_result

    _store.record_action_decision_receipt(action_id, decision_receipt)
    print(
        f"[hitl_service] APPROVED: {action_id} "
        f"type={action_type} approved_by={action.get('approved_by')} "
        f"dispatch={decision_receipt.get('dispatch_status')}",
        flush=True,
    )
    return {
        "action_id": action_id,
        "dispatch_status": str(decision_receipt.get("dispatch_status") or ""),
        "execution_result": execution_result,
        "processed": True,
    }


def redrive_pending_dispatches(*, limit: int | None = None) -> dict[str, Any]:
    """Process approved actions whose dispatch job survived a restart."""
    register_builtin_action_dispatchers()
    ready = _store.list_actions_ready_for_dispatch()
    if limit is not None:
        ready = ready[: max(0, int(limit))]
    results = [dispatch_approved_action(str(action.get("action_id") or "")) for action in ready]
    return {
        "schema_version": "OPERATOR_ACTION_APPROVED_DISPATCH_REDRIVE_RESULT_V0",
        "processed": sum(1 for result in results if result.get("processed")),
        "seen": len(ready),
        "results": results,
        "created_at": _utc_now(),
    }


def _build_decision_receipt(
    action: Mapping[str, Any],
    *,
    decision: str,
    dispatch_status: str,
    execution_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
    request_id = str(payload.get("request_id") or action.get("idempotency_key") or "")
    if execution_result is None and isinstance(action.get("execution_result"), Mapping):
        execution_result = action.get("execution_result")
    execution_result = dict(execution_result or {})
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
        "execution_result": execution_result,
        "execution_performed": execution_result.get("status") == "success",
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


def approve_action(action_id: str, *, approved_by: str = "operator", dispatch_now: bool = True) -> bool:
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
            _store.record_action_decision_receipt(
                action_id,
                _build_decision_receipt(
                    record,
                    decision="approved",
                    dispatch_status="pending_dispatch",
                ),
            )
            if dispatch_now:
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
                    execution_result=dict(record.get("execution_result") or {}),
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


register_builtin_action_dispatchers()
