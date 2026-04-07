"""
hitl_action_service.py

Service-layer API for the Human-in-the-Loop action queue.

Sits between callers (Cassandra, future dashboard) and the raw store
(hitl_pending_store.py). Adds:
  - Field validation (type, payload; recipient+amount for financial types)
  - Idempotency key deduplication for repeated proposals
  - approve_action / deny_action convenience methods
  - Execution handoff hook called on approval (currently logs; wire to
    executor when ready)

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


# ── Execution hook ────────────────────────────────────────────────────────────

def _on_action_approved(action: dict) -> None:
    """Called after an action transitions to APPROVED.

    Currently a no-op placeholder.  Wire to the real executor here once the
    execution path is defined (e.g. route to cassandra_brain dispatch or
    a dedicated executor module).

    The action dict contains the full record including approved_by, approved_at,
    and payload, so the executor receives everything it needs.
    """
    print(
        f"[hitl_service] APPROVED: {action['action_id']} "
        f"type={action['action_type']} approved_by={action.get('approved_by')}",
        flush=True,
    )


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
