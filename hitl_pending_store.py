"""
hitl_pending_store.py

Human-in-the-Loop (HITL) pending action pipeline for Cassandra.

Cassandra proposes actions here instead of executing them directly.
Each action stays WAITING_FOR_APPROVAL until explicitly approved or denied,
or until its TTL expires.

Status constants
----------------
  WAITING_FOR_APPROVAL  — created, pending human decision
  APPROVED              — explicitly approved by operator
  DENIED                — explicitly denied by operator
  EXPIRED               — TTL elapsed without decision
  FAILED                — approved but execution failed

Schema (one record per action)
-------------------------------
  action_id       : str  — uuid4 short (8 hex chars), unique
  source_agent    : str  — which agent proposed (e.g. "cassandra")
  action_type     : str  — category (e.g. "email_send", "sms", "calendar_write")
  payload         : dict — action-specific data (recipient, body, etc.)
  status          : str  — one of the status constants above
  review_state    : str  — NORMAL | SUPER_FLAG | AUTO_DENIED
  review_reason_codes : list[str] — policy / threshold reason codes
  normalized_amount : float | None — parsed transaction amount used for limits
  requested_at    : str  — ISO datetime string
  expires_at      : str  — ISO datetime string (requested_at + ttl_seconds)
  approved_by     : str | None — identifier of who approved, or None
  approved_at     : str | None — ISO datetime of approval, or None
  denied_reason   : str | None — free-text reason for denial, or None

HITL Toggle
-----------
Set env var HITL_ENABLED=1 or create flag file at HITL_FLAG_PATH to enable.
When disabled, propose_action() returns (True, None) immediately — existing
behavior is preserved with no gate applied.

Audit
-----
Every state transition is appended to HITL_AUDIT_LOG (JSONL, one record per line).
"""

import json
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ── Status constants ───────────────────────────────────────────────────────────

WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
APPROVED             = "APPROVED"
DENIED               = "DENIED"
EXPIRED              = "EXPIRED"
FAILED               = "FAILED"

_TERMINAL_STATUSES = {APPROVED, DENIED, EXPIRED, FAILED}

# ── Paths ─────────────────────────────────────────────────────────────────────

_LOGS_DIR        = Path("/mnt/c/OpenClaw/logs")
HITL_STATE_PATH  = _LOGS_DIR / "hitl_pending_state.json"
HITL_AUDIT_LOG   = _LOGS_DIR / "hitl_audit.jsonl"
HITL_FLAG_PATH   = _LOGS_DIR / "hitl_enabled.flag"

# Default TTL: 24 hours
_DEFAULT_TTL_SECONDS = 86400

# ── Transaction-limit policy ──────────────────────────────────────────────────

_LIMIT_GATED_ACTION_TYPES = frozenset({
    "financial_transfer",
    "payment",
    "bill_pay",
    "wire_transfer",
    "refund",
    "charge",
})
_POLICY_SENSITIVE_ACTION_TYPES = frozenset({
    "wire_transfer",
    "refund",
    "charge",
})

REVIEW_NORMAL = "NORMAL"
REVIEW_SUPER_FLAG = "SUPER_FLAG"
REVIEW_AUTO_DENIED = "AUTO_DENIED"

_DEFAULT_SUPER_FLAG_LIMIT = 1000.0
_DEFAULT_HARD_LIMIT = 2500.0

REASON_HARD_LIMIT_EXCEEDED = "transaction_limit_exceeded"
REASON_SUPER_FLAG_THRESHOLD = "transaction_super_flag_threshold"
REASON_POLICY_SENSITIVE = "transaction_policy_sensitive"
REASON_MISSING_AMOUNT = "transaction_amount_missing"


# ── Toggle ────────────────────────────────────────────────────────────────────

def is_hitl_enabled() -> bool:
    """
    Return True if the HITL pipeline is active.

    Enabled when either:
      - HITL_ENABLED env var is set to '1' or 'true'
      - HITL_FLAG_PATH flag file exists on disk
    """
    if os.environ.get("HITL_ENABLED", "").lower() in ("1", "true", "yes"):
        return True
    return HITL_FLAG_PATH.exists()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load state dict (action_id → record). Returns {} on missing/corrupt."""
    if HITL_STATE_PATH.exists():
        try:
            return json.loads(HITL_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    """Write state dict to disk, creating parent dirs if needed."""
    HITL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    HITL_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _audit(record: dict) -> None:
    """Append a transition record to the audit JSONL log."""
    HITL_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(record)
    entry["audit_ts"] = datetime.now().isoformat(timespec="seconds")
    with HITL_AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _shadow_cassandra_hitl_proposal(record: dict, ttl_seconds: int) -> None:
    """Fail-open observational SQLite shadow for Cassandra HITL proposals."""
    try:
        from guardian_hitl_cassandra_proposal_shadow import (
            mirror_cassandra_hitl_proposal_fail_open,
        )

        mirror_cassandra_hitl_proposal_fail_open(record, ttl_seconds=ttl_seconds)
    except Exception:
        pass


def _shadow_cassandra_hitl_decision(record: dict, decision_status: str) -> None:
    """Fail-open observational SQLite receipt for Cassandra HITL decisions."""
    try:
        from guardian_hitl_cassandra_proposal_shadow import (
            mirror_cassandra_hitl_decision_fail_open,
        )

        mirror_cassandra_hitl_decision_fail_open(record, decision_status)
    except Exception:
        pass


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_expired(record: dict) -> bool:
    try:
        expires_at = datetime.fromisoformat(record["expires_at"])
        return datetime.now() >= expires_at
    except Exception:
        return False


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _limit_thresholds() -> tuple[float, float]:
    super_flag_limit = _env_float(
        "HITL_TRANSACTION_SUPER_FLAG_LIMIT",
        _DEFAULT_SUPER_FLAG_LIMIT,
    )
    hard_limit = _env_float(
        "HITL_TRANSACTION_HARD_LIMIT",
        _DEFAULT_HARD_LIMIT,
    )
    if hard_limit < super_flag_limit:
        hard_limit = super_flag_limit
    return super_flag_limit, hard_limit


def _parse_amount(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return abs(float(value))
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-]", "", value)
        if not cleaned or cleaned in {"-", ".", "-."}:
            return None
        try:
            return abs(float(cleaned))
        except ValueError:
            return None
    return None


def _extract_transaction_amount(payload: dict) -> float | None:
    for key in (
        "amount",
        "payment_amount",
        "amount_total",
        "amount_due",
        "total_amount",
        "value",
    ):
        parsed = _parse_amount(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _is_truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _evaluate_transaction_guard(action_type: str, payload: dict) -> dict:
    """Return limit metadata for money-moving actions."""
    metadata = {
        "review_state": REVIEW_NORMAL,
        "review_reason_codes": [],
        "normalized_amount": None,
        "super_flag_limit": None,
        "hard_limit": None,
    }
    if action_type not in _LIMIT_GATED_ACTION_TYPES:
        return metadata

    super_flag_limit, hard_limit = _limit_thresholds()
    metadata["super_flag_limit"] = super_flag_limit
    metadata["hard_limit"] = hard_limit

    amount = _extract_transaction_amount(payload)
    metadata["normalized_amount"] = amount
    reasons: list[str] = []

    payload_sensitive = any(
        _is_truthy(payload.get(key))
        for key in (
            "policy_sensitive",
            "requires_manual_review",
            "super_flag",
        )
    )

    if action_type in _POLICY_SENSITIVE_ACTION_TYPES or payload_sensitive:
        reasons.append(REASON_POLICY_SENSITIVE)

    if amount is None:
        reasons.append(REASON_MISSING_AMOUNT)
    elif amount > hard_limit:
        metadata["review_state"] = REVIEW_AUTO_DENIED
        metadata["review_reason_codes"] = [REASON_HARD_LIMIT_EXCEEDED]
        return metadata
    elif amount >= super_flag_limit:
        reasons.append(REASON_SUPER_FLAG_THRESHOLD)

    if reasons:
        metadata["review_state"] = REVIEW_SUPER_FLAG
        metadata["review_reason_codes"] = sorted(set(reasons))

    return metadata


# ── Public API ────────────────────────────────────────────────────────────────

def create_pending_action(
    source_agent: str,
    action_type: str,
    payload: dict,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    *,
    idempotency_key: str | None = None,
    initial_status: str = WAITING_FOR_APPROVAL,
    denied_reason: str | None = None,
    review_state: str = REVIEW_NORMAL,
    review_reason_codes: list[str] | None = None,
    normalized_amount: float | None = None,
    super_flag_limit: float | None = None,
    hard_limit: float | None = None,
) -> dict:
    """
    Create a new action record, defaulting to WAITING_FOR_APPROVAL.

    If idempotency_key is provided and an active (WAITING_FOR_APPROVAL) record
    with the same key already exists, returns that record without creating a new one.

    Returns the full record dict (includes action_id).
    Audits the creation event (skipped for idempotency hits).
    """
    state = _load_state()

    if idempotency_key is not None:
        for record in state.values():
            if (
                record.get("idempotency_key") == idempotency_key
                and record["status"] == WAITING_FOR_APPROVAL
                and not _is_expired(record)
            ):
                return record

    action_id   = str(uuid.uuid4())[:8].upper()
    requested_at = _iso_now()
    expires_at  = (
        datetime.now() + timedelta(seconds=ttl_seconds)
    ).isoformat(timespec="seconds")

    record = {
        "action_id":      action_id,
        "source_agent":   source_agent,
        "action_type":    action_type,
        "payload":        payload,
        "idempotency_key": idempotency_key,
        "status":         initial_status,
        "review_state":   review_state,
        "review_reason_codes": list(review_reason_codes or []),
        "normalized_amount": normalized_amount,
        "super_flag_limit": super_flag_limit,
        "hard_limit": hard_limit,
        "requested_at":   requested_at,
        "expires_at":     expires_at,
        "approved_by":    None,
        "approved_at":    None,
        "denied_reason":  denied_reason,
    }

    state[action_id] = record
    _save_state(state)
    _audit({**record, "event": "created"})
    _shadow_cassandra_hitl_proposal(record, ttl_seconds)
    return record


def get_action(action_id: str) -> dict | None:
    """
    Return the record for action_id, or None if not found.

    If the action is still WAITING_FOR_APPROVAL but its TTL has elapsed,
    this call auto-transitions it to EXPIRED.
    """
    state = _load_state()
    record = state.get(action_id)
    if record is None:
        return None

    if record["status"] == WAITING_FOR_APPROVAL and _is_expired(record):
        record["status"] = EXPIRED
        state[action_id] = record
        _save_state(state)
        _audit({**record, "event": "auto_expired"})
        _shadow_cassandra_hitl_decision(record, EXPIRED)

    return record


def list_pending_actions(status: str | None = None) -> list[dict]:
    """
    Return all actions, optionally filtered by status.

    WAITING_FOR_APPROVAL records whose TTL has elapsed are auto-transitioned
    to EXPIRED before the filter is applied.
    """
    state   = _load_state()
    changed = False

    expired_records: list[dict] = []
    for action_id, record in state.items():
        if record["status"] == WAITING_FOR_APPROVAL and _is_expired(record):
            record["status"] = EXPIRED
            state[action_id] = record
            changed = True
            _audit({**record, "event": "auto_expired"})
            expired_records.append(record)

    if changed:
        _save_state(state)
        for record in expired_records:
            _shadow_cassandra_hitl_decision(record, EXPIRED)

    records = list(state.values())
    if status is not None:
        records = [r for r in records if r["status"] == status]
    return records


def update_action_status(
    action_id: str,
    new_status: str,
    *,
    approved_by: str | None = None,
    denied_reason: str | None = None,
) -> bool:
    """
    Transition action_id to new_status.

    Returns True on success, False if action not found or already in a
    terminal status.

    approved_by   — populated on APPROVED transitions
    denied_reason — populated on DENIED transitions
    """
    valid_statuses = {WAITING_FOR_APPROVAL, APPROVED, DENIED, EXPIRED, FAILED}
    if new_status not in valid_statuses:
        raise ValueError(f"Unknown status: {new_status!r}")

    state = _load_state()
    record = state.get(action_id)
    if record is None:
        return False

    if record["status"] in _TERMINAL_STATUSES:
        # Already resolved — no further transitions allowed.
        return False

    prev_status = record["status"]
    record["status"] = new_status

    if new_status == APPROVED:
        record["approved_by"] = approved_by or "operator"
        record["approved_at"] = _iso_now()
    elif new_status == DENIED:
        record["denied_reason"] = denied_reason or ""
    elif new_status == EXPIRED:
        pass  # timestamps already set at creation
    elif new_status == FAILED:
        pass

    state[action_id] = record
    _save_state(state)
    _audit({**record, "event": f"transition:{prev_status}->{new_status}"})
    if new_status in {APPROVED, DENIED, EXPIRED}:
        _shadow_cassandra_hitl_decision(record, new_status)
    return True


def update_action_payload(action_id: str, payload: dict) -> bool:
    """
    Replace the payload for an existing action without changing its status.

    Used by higher-level approval wrappers that need the store-generated
    action_id before they can finish a human-facing envelope, for example a
    short typed fallback reply code. This does not approve, deny, or execute.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    state = _load_state()
    record = state.get(action_id)
    if record is None:
        return False

    record["payload"] = payload
    state[action_id] = record
    _save_state(state)
    _audit({**record, "event": "payload_updated"})
    return True


def record_action_decision_receipt(action_id: str, decision_receipt: dict) -> bool:
    """
    Attach a decision receipt to an action record without changing status.

    Receipts are metadata about the Guardian/operator decision and route-back
    outcome. They are not execution authority by themselves.
    """
    if not isinstance(decision_receipt, dict):
        raise ValueError("decision_receipt must be a dict")

    state = _load_state()
    record = state.get(action_id)
    if record is None:
        return False

    record["decision_receipt"] = decision_receipt
    payload = record.get("payload")
    if isinstance(payload, dict):
        payload = dict(payload)
        payload["decision_receipt"] = decision_receipt
        record["payload"] = payload
    state[action_id] = record
    _save_state(state)
    _audit(
        {
            **record,
            "event": "decision_receipt_recorded",
            "decision_receipt_status": decision_receipt.get("status"),
        }
    )
    return True


def expire_stale_actions() -> int:
    """
    Scan all WAITING_FOR_APPROVAL records and expire those past their TTL.
    Returns the number of records expired.
    """
    state   = _load_state()
    expired = 0
    expired_records: list[dict] = []
    for action_id, record in state.items():
        if record["status"] == WAITING_FOR_APPROVAL and _is_expired(record):
            record["status"] = EXPIRED
            state[action_id] = record
            expired += 1
            _audit({**record, "event": "auto_expired"})
            expired_records.append(record)

    if expired:
        _save_state(state)
        for record in expired_records:
            _shadow_cassandra_hitl_decision(record, EXPIRED)

    return expired


def propose_action(
    source_agent: str,
    action_type: str,
    payload: dict,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    *,
    idempotency_key: str | None = None,
) -> tuple[bool, str | None]:
    """
    Main entry point for Cassandra to propose an external action.

    Money-moving payment actions are always checked against configurable
    thresholds, even when HITL is otherwise disabled. This provides a hard
    stop for over-limit actions and a mandatory escalation path for near-limit
    or policy-sensitive requests.

    If HITL is disabled and the action is not limit-gated:
        Returns (True, None) — action may proceed immediately.

    If HITL is enabled:
        Creates a pending record in WAITING_FOR_APPROVAL (or returns an
        existing one for the same idempotency_key if still active).
        Returns (False, action_id) — action must not execute until approved.

    Callers check the bool; if False, they surface a message like
    "I've queued this for your approval." and include the action_id for
    status lookup.
    """
    guard = _evaluate_transaction_guard(action_type, payload)
    needs_manual_review = guard["review_state"] == REVIEW_SUPER_FLAG
    auto_denied = guard["review_state"] == REVIEW_AUTO_DENIED

    if not is_hitl_enabled() and not needs_manual_review and not auto_denied:
        return True, None

    initial_status = WAITING_FOR_APPROVAL
    denied_reason = None
    if auto_denied:
        initial_status = DENIED
        denied_reason = REASON_HARD_LIMIT_EXCEEDED

    record = create_pending_action(
        source_agent, action_type, payload, ttl_seconds,
        idempotency_key=idempotency_key,
        initial_status=initial_status,
        denied_reason=denied_reason,
        review_state=guard["review_state"],
        review_reason_codes=guard["review_reason_codes"],
        normalized_amount=guard["normalized_amount"],
        super_flag_limit=guard["super_flag_limit"],
        hard_limit=guard["hard_limit"],
    )
    return False, record["action_id"]
