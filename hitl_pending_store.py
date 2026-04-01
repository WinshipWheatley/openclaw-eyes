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

# Default TTL: 1 hour
_DEFAULT_TTL_SECONDS = 3600


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


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_expired(record: dict) -> bool:
    try:
        expires_at = datetime.fromisoformat(record["expires_at"])
        return datetime.now() >= expires_at
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def create_pending_action(
    source_agent: str,
    action_type: str,
    payload: dict,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    *,
    idempotency_key: str | None = None,
) -> dict:
    """
    Create a new pending action in WAITING_FOR_APPROVAL state.

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
        "status":         WAITING_FOR_APPROVAL,
        "requested_at":   requested_at,
        "expires_at":     expires_at,
        "approved_by":    None,
        "approved_at":    None,
        "denied_reason":  None,
    }

    state[action_id] = record
    _save_state(state)
    _audit({**record, "event": "created"})
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

    return record


def list_pending_actions(status: str | None = None) -> list[dict]:
    """
    Return all actions, optionally filtered by status.

    WAITING_FOR_APPROVAL records whose TTL has elapsed are auto-transitioned
    to EXPIRED before the filter is applied.
    """
    state   = _load_state()
    changed = False

    for action_id, record in state.items():
        if record["status"] == WAITING_FOR_APPROVAL and _is_expired(record):
            record["status"] = EXPIRED
            state[action_id] = record
            changed = True
            _audit({**record, "event": "auto_expired"})

    if changed:
        _save_state(state)

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
    return True


def expire_stale_actions() -> int:
    """
    Scan all WAITING_FOR_APPROVAL records and expire those past their TTL.
    Returns the number of records expired.
    """
    state   = _load_state()
    expired = 0
    for action_id, record in state.items():
        if record["status"] == WAITING_FOR_APPROVAL and _is_expired(record):
            record["status"] = EXPIRED
            state[action_id] = record
            expired += 1
            _audit({**record, "event": "auto_expired"})

    if expired:
        _save_state(state)

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

    If HITL is disabled:
        Returns (True, None) — action may proceed immediately.

    If HITL is enabled:
        Creates a pending record in WAITING_FOR_APPROVAL (or returns an
        existing one for the same idempotency_key if still active).
        Returns (False, action_id) — action must not execute until approved.

    Callers check the bool; if False, they surface a message like
    "I've queued this for your approval." and include the action_id for
    status lookup.
    """
    if not is_hitl_enabled():
        return True, None

    record = create_pending_action(
        source_agent, action_type, payload, ttl_seconds,
        idempotency_key=idempotency_key,
    )
    return False, record["action_id"]
