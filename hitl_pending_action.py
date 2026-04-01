"""
hitl_pending_action.py

Core Human-in-the-Loop pending action pipeline.

Cassandra (or any agent) can propose actions that remain pending until
explicit approve/deny via Telegram or other authorized channel.

Public API
----------
is_hitl_enabled()                           — check if HITL gating is active
create_pending_action(...)                  — queue an action for approval
get_pending_action(action_id)               — retrieve one action by ID
list_pending_actions(status=None)           — list actions, optionally filtered
update_action_status(action_id, ...)        — transition status with audit
expire_stale_actions()                      — mark expired actions

Status constants
----------------
WAITING_FOR_APPROVAL, APPROVED, DENIED, EXPIRED, FAILED
"""

import fcntl
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chief_file_io import load_json, save_json

# ── Status constants ──────────────────────────────────────────────────────────

WAITING_FOR_APPROVAL = "waiting_for_approval"
APPROVED = "approved"
DENIED = "denied"
EXPIRED = "expired"
FAILED = "failed"

_VALID_STATUSES = {WAITING_FOR_APPROVAL, APPROVED, DENIED, EXPIRED, FAILED}
_TERMINAL_STATUSES = {APPROVED, DENIED, EXPIRED, FAILED}

# ── Allowed transitions ──────────────────────────────────────────────────────

_TRANSITIONS = {
    WAITING_FOR_APPROVAL: {APPROVED, DENIED, EXPIRED, FAILED},
    APPROVED: {FAILED},
    DENIED: set(),
    EXPIRED: set(),
    FAILED: set(),
}

# ── Paths ─────────────────────────────────────────────────────────────────────

_STORE_FILE = Path("/mnt/c/OpenClaw/logs/hitl_pending_actions.json")
_AUDIT_FILE = Path("/mnt/c/OpenClaw/logs/hitl_audit.jsonl")
_LOCK_FILE = Path.home() / ".hitl_pending.lock"
_DEFAULT_EXPIRY_HOURS = 24

# ── HITL toggle ───────────────────────────────────────────────────────────────


def is_hitl_enabled() -> bool:
    """Check if HITL gating is active. Defaults to disabled for backwards compat."""
    return os.environ.get("HITL_ENABLED", "").lower() in ("1", "true", "yes")


# ── Internal helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_action_id() -> str:
    return uuid.uuid4().hex[:12].upper()


def _load_store() -> list[dict]:
    return load_json(_STORE_FILE, [])


def _save_store(actions: list[dict]) -> None:
    save_json(_STORE_FILE, actions)


def _append_audit(entry: dict) -> None:
    """Append one audit record to the JSONL audit trail."""
    _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _audit_transition(
    action_id: str,
    old_status: str,
    new_status: str,
    *,
    approved_by: str | None = None,
    denied_reason: str | None = None,
) -> None:
    _append_audit({
        "action_id": action_id,
        "old_status": old_status,
        "new_status": new_status,
        "approved_by": approved_by,
        "denied_reason": denied_reason,
        "transitioned_at": _now_iso(),
    })


def _with_lock(fn):
    """Decorator: hold advisory flock for atomic store operations."""
    def wrapper(*args, **kwargs):
        _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LOCK_FILE.touch(exist_ok=True)
        with _LOCK_FILE.open("r") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                return fn(*args, **kwargs)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    return wrapper


# ── Public API ────────────────────────────────────────────────────────────────


@_with_lock
def create_pending_action(
    source_agent: str,
    action_type: str,
    payload: dict,
    expires_in_hours: float = _DEFAULT_EXPIRY_HOURS,
) -> str:
    """Create a pending action and return its action_id.

    The action starts in WAITING_FOR_APPROVAL status. No external execution
    happens until the status is explicitly transitioned to APPROVED.
    """
    now = _now_iso()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    ).isoformat()

    action_id = _generate_action_id()
    record = {
        "action_id": action_id,
        "source_agent": source_agent,
        "action_type": action_type,
        "payload": payload,
        "status": WAITING_FOR_APPROVAL,
        "requested_at": now,
        "expires_at": expires_at,
        "approved_by": None,
        "approved_at": None,
        "denied_reason": None,
    }

    actions = _load_store()
    actions.append(record)
    _save_store(actions)

    _append_audit({
        "action_id": action_id,
        "old_status": None,
        "new_status": WAITING_FOR_APPROVAL,
        "source_agent": source_agent,
        "action_type": action_type,
        "transitioned_at": now,
    })

    print(f"[hitl] Created pending action {action_id}: "
          f"{action_type} from {source_agent}", flush=True)
    return action_id


def get_pending_action(action_id: str) -> dict | None:
    """Retrieve a single action by ID, or None if not found."""
    for action in _load_store():
        if action["action_id"] == action_id:
            return action
    return None


def list_pending_actions(status: str | None = None) -> list[dict]:
    """List all actions, optionally filtered by status."""
    actions = _load_store()
    if status is not None:
        actions = [a for a in actions if a["status"] == status]
    return actions


@_with_lock
def update_action_status(
    action_id: str,
    new_status: str,
    *,
    approved_by: str | None = None,
    denied_reason: str | None = None,
) -> bool:
    """Transition an action to a new status. Returns True if successful.

    Enforces valid transitions and audits every change.
    """
    if new_status not in _VALID_STATUSES:
        print(f"[hitl] ERROR: invalid status {new_status!r}", flush=True)
        return False

    actions = _load_store()
    for action in actions:
        if action["action_id"] != action_id:
            continue

        old_status = action["status"]
        allowed = _TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            print(f"[hitl] ERROR: transition {old_status} -> {new_status} "
                  f"not allowed for {action_id}", flush=True)
            return False

        action["status"] = new_status
        if new_status == APPROVED:
            action["approved_by"] = approved_by
            action["approved_at"] = _now_iso()
        if new_status == DENIED:
            action["denied_reason"] = denied_reason

        _save_store(actions)
        _audit_transition(
            action_id, old_status, new_status,
            approved_by=approved_by, denied_reason=denied_reason,
        )
        print(f"[hitl] {action_id}: {old_status} -> {new_status}", flush=True)
        return True

    print(f"[hitl] ERROR: action {action_id} not found", flush=True)
    return False


@_with_lock
def expire_stale_actions() -> list[str]:
    """Mark any WAITING_FOR_APPROVAL actions past their expires_at as EXPIRED.

    Returns list of expired action_ids.
    """
    now = datetime.now(timezone.utc)
    actions = _load_store()
    expired_ids = []

    for action in actions:
        if action["status"] != WAITING_FOR_APPROVAL:
            continue
        try:
            exp = datetime.fromisoformat(action["expires_at"])
        except (KeyError, ValueError):
            continue
        if now >= exp:
            old = action["status"]
            action["status"] = EXPIRED
            expired_ids.append(action["action_id"])
            _audit_transition(action["action_id"], old, EXPIRED)
            print(f"[hitl] {action['action_id']}: auto-expired", flush=True)

    if expired_ids:
        _save_store(actions)
    return expired_ids
