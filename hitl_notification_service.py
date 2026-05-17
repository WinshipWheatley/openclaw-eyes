"""
hitl_notification_service.py

Notification layer for the HITL pending-action pipeline.

Responsibilities:
  - Format action summaries (action type, risk level, source agent, payload preview)
  - Generate HMAC-signed short-lived approve/deny tokens
  - Send notifications via Telegram (Guardian bot channel)
  - Validate approval callbacks and update action state
  - Audit notification send results and callback decisions

Token format:
    <action_id>.<decision>.<exp_unix>.<hmac12>
    where hmac12 = HMAC-SHA256(<action_id>:<decision>:<exp_unix>, HITL_NOTIFY_SECRET)[:12]

Decision values in token: "Y" (approve) or "N" (deny)

Telegram commands injected into the notification:
    /hitl_approve <token>
    /hitl_deny    <token>

Public API
----------
send_pending_notification(action_id) -> bool
    Send a Telegram notification for a WAITING_FOR_APPROVAL action.

handle_callback(raw_token, *, approved_by="operator") -> dict
    Validate the token, infer decision, update action state.
    Returns {"ok": bool, "action_id": str|None, "decision": str|None, "error": str|None}

format_notification(action) -> str
    Return the formatted message string for a pending action.

generate_token(action_id, decision) -> str
    Generate a signed short-lived token. decision: "Y" or "N".

validate_token(raw_token) -> dict
    Validate and decode a token. Returns {ok, action_id, decision, error}.
"""

import hashlib
import hmac as _hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import hitl_action_service as _svc
from hitl_pending_store import WAITING_FOR_APPROVAL

# ── Config ────────────────────────────────────────────────────────────────────

_TOKEN_TTL_SECONDS = 86400  # 24 hours
_LOGS_DIR = Path("/mnt/c/OpenClaw/logs")
_NOTIFY_LOG = _LOGS_DIR / "hitl_notifications.jsonl"

# Risk classification by action type
_HIGH_RISK_TYPES: frozenset[str] = frozenset({
    "financial_transfer", "payment", "bill_pay", "wire_transfer",
    "invoice_send", "refund", "charge",
})
_MEDIUM_RISK_TYPES: frozenset[str] = frozenset({
    "email_send", "sms", "social_post", "calendar_write",
})


def _notify_secret() -> bytes:
    """Return HMAC secret for notification tokens.

    Uses HITL_NOTIFY_SECRET if set. Falls back to TELEGRAM_BOT_TOKEN so the
    system stays functional before a dedicated secret is configured, but that
    fallback is intentionally weak — set HITL_NOTIFY_SECRET in .chief.env for
    production use.
    """
    import chief_env

    chief_env.load_env()
    secret = os.environ.get("HITL_NOTIFY_SECRET", "")
    if not secret:
        secret = os.environ.get("TELEGRAM_BOT_TOKEN", "hitl-default-secret")
    return secret.encode()


# ── Risk classification ───────────────────────────────────────────────────────

def _risk_level(action_type: str) -> str:
    if action_type in _HIGH_RISK_TYPES:
        return "HIGH"
    if action_type in _MEDIUM_RISK_TYPES:
        return "MEDIUM"
    return "LOW"


# ── Token helpers ─────────────────────────────────────────────────────────────

def _sign(action_id: str, decision: str, exp_unix: int) -> str:
    """Return first 12 hex chars of HMAC-SHA256 over action_id:decision:exp."""
    msg = f"{action_id}:{decision}:{exp_unix}".encode()
    return _hmac.new(_notify_secret(), msg, hashlib.sha256).hexdigest()[:12]


def generate_token(action_id: str, decision: str) -> str:
    """Generate a signed short-lived token for a decision.

    decision: "Y" (approve) or "N" (deny)
    Format:   <action_id>.<decision>.<exp_unix>.<hmac12>
    """
    if decision not in ("Y", "N"):
        raise ValueError(f"decision must be 'Y' or 'N', got {decision!r}")
    exp_unix = int(time.time()) + _TOKEN_TTL_SECONDS
    sig = _sign(action_id, decision, exp_unix)
    return f"{action_id}.{decision}.{exp_unix}.{sig}"


def validate_token(raw_token: str) -> dict:
    """Validate a token.

    Returns dict with keys:
        ok        : bool
        action_id : str | None
        decision  : str | None   ("Y" / "N")
        error     : str | None
    """
    parts = raw_token.strip().split(".")
    if len(parts) != 4:
        return {"ok": False, "action_id": None, "decision": None,
                "error": "malformed_token"}

    action_id, decision, exp_str, provided_sig = parts

    if decision not in ("Y", "N"):
        return {"ok": False, "action_id": action_id, "decision": None,
                "error": "invalid_decision"}

    try:
        exp_unix = int(exp_str)
    except ValueError:
        return {"ok": False, "action_id": action_id, "decision": None,
                "error": "invalid_expiry"}

    if int(time.time()) > exp_unix:
        return {"ok": False, "action_id": action_id, "decision": decision,
                "error": "token_expired"}

    expected_sig = _sign(action_id, decision, exp_unix)
    if not _hmac.compare_digest(provided_sig, expected_sig):
        return {"ok": False, "action_id": action_id, "decision": decision,
                "error": "invalid_signature"}

    return {"ok": True, "action_id": action_id, "decision": decision, "error": None}


# ── Inline keyboard ───────────────────────────────────────────────────────────

def _build_keyboard(action_id: str) -> dict:
    """Return a Telegram InlineKeyboardMarkup dict with signed Approve/Deny buttons.

    Callback data format: HITL:{token}
    where token = generate_token(action_id, 'Y' | 'N')
    """
    approve_token = generate_token(action_id, "Y")
    deny_token    = generate_token(action_id, "N")
    return {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": f"HITL:{approve_token}"},
                {"text": "Deny",    "callback_data": f"HITL:{deny_token}"},
            ]
        ]
    }


# ── Notification formatting ───────────────────────────────────────────────────

def _payload_preview(payload: dict, max_chars: int = 200) -> str:
    """Return a truncated JSON preview of the payload."""
    try:
        preview = json.dumps(payload, separators=(",", ":"))
    except Exception:
        preview = str(payload)
    if len(preview) > max_chars:
        preview = preview[:max_chars] + "..."
    return preview


def format_notification(action: dict) -> str:
    """Format a human-readable Telegram notification for a pending action."""
    action_id = action["action_id"]
    source = action.get("source_agent", "unknown")
    a_type = action.get("action_type", "unknown")
    payload = action.get("payload", {})
    risk = _risk_level(a_type)
    expires_at = action.get("expires_at", "unknown")
    review_state = action.get("review_state", "NORMAL")
    review_reasons = action.get("review_reason_codes") or []
    normalized_amount = action.get("normalized_amount")
    super_flag_limit = action.get("super_flag_limit")
    hard_limit = action.get("hard_limit")

    approve_token = generate_token(action_id, "Y")
    deny_token = generate_token(action_id, "N")

    lines = [
        "🔔 HITL ACTION PENDING",
        f"ID: {action_id}",
        f"Agent: {source}",
        f"Type: {a_type}",
        f"Risk: {risk}",
        f"Review: {review_state}",
        f"Expires: {expires_at}",
        f"Payload: {_payload_preview(payload)}",
    ]
    if normalized_amount is not None:
        lines.append(f"Amount: ${normalized_amount:,.2f}")
    if super_flag_limit is not None and hard_limit is not None:
        lines.append(
            f"Limits: super-flag >= ${super_flag_limit:,.2f}, hard > ${hard_limit:,.2f}"
        )
    if review_reasons:
        lines.append(f"Review reasons: {', '.join(review_reasons)}")
    lines.extend([
        "",
        "To approve:",
        f"/hitl_approve {approve_token}",
        "",
        "To deny:",
        f"/hitl_deny {deny_token}",
    ])
    return "\n".join(lines)


# ── Audit log ─────────────────────────────────────────────────────────────────

def _audit_notify(action_id: str, event: str, detail: dict | None = None) -> None:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "action_id": action_id,
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        **(detail or {}),
    }
    with _NOTIFY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _maybe_send_no_pending_confirmation() -> None:
    """
    If no HITL approvals remain, send the same green-check confirmation the
    legacy approval gate uses.
    """
    try:
        pending = _svc.list_pending_actions(status=WAITING_FOR_APPROVAL)
        if pending:
            return
        from chief_guardian_sender import send_approval

        send_approval("✅ No pending approval requests.")
        _audit_notify("none", "all_clear_confirmation_sent", {"pending_count": 0})
    except Exception as exc:
        _audit_notify("none", "all_clear_confirmation_failed", {"error": str(exc)})


# ── Public API ────────────────────────────────────────────────────────────────

def send_pending_notification(action_id: str) -> bool:
    """Send a Telegram notification for a WAITING_FOR_APPROVAL action.

    Returns True if the message was delivered, False on error or skip.
    """
    from chief_guardian_sender import send_approval  # lazy import: avoid import-time token load

    action = _svc.get_pending_action(action_id)
    if action is None:
        print(f"[hitl_notify] action {action_id} not found", flush=True)
        _audit_notify(action_id, "send_failed", {"error": "action_not_found"})
        return False

    if action["status"] != WAITING_FOR_APPROVAL:
        print(f"[hitl_notify] action {action_id} not in WAITING state "
              f"(status={action['status']})", flush=True)
        _audit_notify(action_id, "send_skipped",
                      {"reason": f"status={action['status']}"})
        return False

    message  = format_notification(action)
    keyboard = _build_keyboard(action_id)
    try:
        send_approval(message, reply_markup=keyboard)
        print(f"[hitl_notify] notification sent for {action_id}", flush=True)
        _audit_notify(action_id, "notification_sent", {"channel": "telegram_guardian"})
        return True
    except Exception as exc:
        print(f"[hitl_notify] send failed for {action_id}: {exc}", flush=True)
        _audit_notify(action_id, "send_failed", {"error": str(exc)})
        return False


def process_callback(callback_data: str, *, approved_by: str = "operator") -> str:
    """Process a HITL inline button callback from Telegram.

    Expected callback_data: HITL:{token}
    where token is the full signed token from generate_token().

    Validates the token, applies the decision, and returns a short operator-
    visible status string suitable for editing the original Telegram message.
    """
    if not callback_data.startswith("HITL:"):
        return "[Error] Not a HITL callback."

    raw_token = callback_data[len("HITL:"):]
    result = handle_callback(raw_token, approved_by=approved_by)

    if result["ok"]:
        decision_label = "Approved" if result["decision"] == "Y" else "Denied"
        return f"[{decision_label}] {result['action_id']}"

    error = result.get("error", "unknown")
    action_id = result.get("action_id") or "?"
    return f"[Error] {action_id}: {error}"


def handle_callback(raw_token: str, *, approved_by: str = "operator") -> dict:
    """Process an approve/deny callback from a signed token.

    Validates the HMAC token, checks expiry, then applies the decision.

    Returns:
        {"ok": bool, "action_id": str|None, "decision": str|None, "error": str|None}
    """
    result = validate_token(raw_token)
    if not result["ok"]:
        _audit_notify(
            result.get("action_id") or "unknown",
            "callback_rejected",
            {"error": result["error"], "token_preview": raw_token[:20]},
        )
        return result

    action_id = result["action_id"]
    decision = result["decision"]

    if decision == "Y":
        ok = _svc.approve_action(action_id, approved_by=approved_by)
        detail: dict = {"decision": "approve", "approved_by": approved_by}
    else:
        ok = _svc.deny_action(action_id)
        detail = {"decision": "deny"}

    if ok:
        _audit_notify(action_id, "callback_applied", detail)
        print(f"[hitl_notify] callback applied: {action_id} decision={decision}",
              flush=True)
        _maybe_send_no_pending_confirmation()
        return {"ok": True, "action_id": action_id, "decision": decision, "error": None}
    else:
        error = "action_not_found_or_terminal"
        _audit_notify(action_id, "callback_failed", {"error": error, **detail})
        print(f"[hitl_notify] callback failed: {action_id} {error}", flush=True)
        return {"ok": False, "action_id": action_id, "decision": decision,
                "error": error}
