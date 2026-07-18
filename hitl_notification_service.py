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

Signed tokens are carried only in Telegram callback_data. Visible copy uses
real buttons plus a short numeric fallback code.

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
from guardian_approval_ui import (
    APPROVE_BUTTON_TEXT,
    DENY_BUTTON_TEXT,
    fallback_lines,
    human_reply_code,
    parse_human_reply,
    terminal_outcome,
)
from hitl_pending_store import WAITING_FOR_APPROVAL

# ── Config ────────────────────────────────────────────────────────────────────

_TOKEN_TTL_SECONDS = 86400  # 24 hours
_LOGS_DIR = Path("/mnt/c/OpenClaw/logs")
_NOTIFY_LOG = _LOGS_DIR / "hitl_notifications.jsonl"
_NOTIFY_SECRET_WARNING_EMITTED = False


class HitlNotificationConfigurationError(RuntimeError):
    """Raised when signed Guardian callbacks cannot be configured safely."""

# Risk classification by action type
_HIGH_RISK_TYPES: frozenset[str] = frozenset({
    "financial_transfer", "payment", "bill_pay", "wire_transfer",
    "invoice_send", "refund", "charge",
})
_MEDIUM_RISK_TYPES: frozenset[str] = frozenset({
    "email_send", "exact_gmail_send", "sms", "social_post", "calendar_write",
})


def _notify_secret() -> bytes:
    """Return HMAC secret for notification tokens.

    The signing key is its own authority boundary.  Bot tokens and public
    constants are never acceptable fallbacks because either would couple
    callback authorization to an unrelated transport identity.
    """
    global _NOTIFY_SECRET_WARNING_EMITTED

    import chief_env

    chief_env.load_env()
    secret = os.environ.get("HITL_NOTIFY_SECRET", "").strip()
    if not secret:
        if not _NOTIFY_SECRET_WARNING_EMITTED:
            print(
                "[hitl_notify] LOUD CONFIGURATION ERROR: HITL_NOTIFY_SECRET is required; "
                "refusing to generate or validate approval tokens.",
                flush=True,
            )
            _NOTIFY_SECRET_WARNING_EMITTED = True
        raise HitlNotificationConfigurationError("HITL_NOTIFY_SECRET is required for signed HITL callbacks.")
    transport_tokens = tuple(
        value.strip()
        for name in (
            "MAESTRO_BOT_TOKEN",
            "CHIEF_BOT_TOKEN",
            "TELEGRAM_BOT_TOKEN",
            "CASSANDRA_BOT_TOKEN",
            "GUARDIAN_BOT_TOKEN",
            "NILES_BOT_TOKEN",
            "PRODUCER_BOT_TOKEN",
            "HERMES_BOT_TOKEN",
        )
        if (value := os.environ.get(name, "")) and value.strip()
    )
    if any(_hmac.compare_digest(secret, token) for token in transport_tokens):
        if not _NOTIFY_SECRET_WARNING_EMITTED:
            print(
                "[hitl_notify] LOUD CONFIGURATION ERROR: HITL_NOTIFY_SECRET must be distinct "
                "from every Telegram transport token; refusing signed callbacks.",
                flush=True,
            )
            _NOTIFY_SECRET_WARNING_EMITTED = True
        raise HitlNotificationConfigurationError("HITL_NOTIFY_SECRET must be distinct from bot tokens.")
    return secret.encode()


# ── Risk classification ───────────────────────────────────────────────────────

def _risk_level(action_type: str) -> str:
    return _svc.risk_tier_for_action_type(str(action_type or "")).upper()


def _legacy_risk_level(action_type: str) -> str:
    if action_type in _HIGH_RISK_TYPES:
        return "HIGH"
    if action_type in _MEDIUM_RISK_TYPES:
        return "MEDIUM"
    return "HIGH"


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

    try:
        expected_sig = _sign(action_id, decision, exp_unix)
    except HitlNotificationConfigurationError:
        return {"ok": False, "action_id": action_id, "decision": decision,
                "error": "hitl_notify_secret_unavailable"}
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
                {"text": APPROVE_BUTTON_TEXT, "callback_data": f"HITL:{approve_token}"},
                {"text": DENY_BUTTON_TEXT, "callback_data": f"HITL:{deny_token}"},
            ],
            [
                {"text": "Why now?", "callback_data": f"HITL_WHY:{action_id}"},
            ],
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


def _reply_code(action_id: str) -> str:
    return human_reply_code(action_id)


def _operator_action_payload(action: dict) -> dict | None:
    payload = action.get("payload")
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") == _svc.OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA:
        return payload
    return None


def _format_operator_action_notification(action: dict, payload: dict) -> str:
    action_id = action["action_id"]
    a_type = action.get("action_type", payload.get("action_type", "unknown"))
    exact_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    fallback = fallback_lines(action_id)
    operator_eli5 = " ".join(str(exact_payload.get("operator_eli5") or "").split())
    if operator_eli5:
        return "\n".join(
            [
                operator_eli5,
                "",
                "Use the buttons below,",
                *fallback,
            ]
        )
    risk = str(payload.get("risk_tier") or _svc.risk_tier_for_action_type(str(a_type))).upper()
    authority_refs = payload.get("authority_refs") if isinstance(payload.get("authority_refs"), list) else []
    credential_lease_refs = payload.get("credential_lease_refs") if isinstance(payload.get("credential_lease_refs"), list) else []
    lines = [
        "HITL ACTION PENDING",
        f"Action ID: {action_id}",
        f"Action type: {a_type}",
        f"Owner: {payload.get('owner_agent', action.get('source_agent', 'unknown'))}",
        f"Objective: {payload.get('owner_objective_id', '')}",
        f"Request: {payload.get('request_id', action.get('idempotency_key', ''))}",
        f"Summary: {payload.get('summary', '')}",
        f"Risk: {risk}",
        f"Warning: {payload.get('risk_warning', '')}",
        f"Expires: {payload.get('expires_at', action.get('expires_at', 'unknown'))}",
        f"Authority refs: {len(authority_refs)}",
        f"Credential lease refs: {len(credential_lease_refs)}",
    ]
    if a_type == _svc.ACTION_TYPE_EXACT_GMAIL_SEND:
        lines.extend(
            [
                f"Recipient: {exact_payload.get('recipient', '')}",
                f"Subject: {exact_payload.get('subject', '')}",
                f"Payload hash: {exact_payload.get('payload_hash', '')}",
                f"Authority envelope: {exact_payload.get('authority_envelope_ref', '')}",
                f"Credential lease: {exact_payload.get('credential_lease_ref', '')}",
                f"Body stored in HITL queue: {str(exact_payload.get('body_stored_in_hitl_queue', False)).lower()}",
            ]
        )
        if exact_payload.get("test_loopback_only") is True:
            attachment_hashes = exact_payload.get("attachment_sha256") or []
            lines.extend(
                [
                    "TEST loopback only: true",
                    f"Test recipient lock: {exact_payload.get('test_recipient_lock', '')}",
                    f"Attachment SHA-256: {attachment_hashes[0] if attachment_hashes else ''}",
                    f"Binding hash: {exact_payload.get('test_loopback_binding_hash', '')}",
                ]
            )
        body_preview = str(exact_payload.get("body_preview") or "")
        if body_preview:
            lines.extend(["Body preview:", body_preview])
    else:
        lines.append(f"Payload: {_payload_preview(exact_payload or payload)}")
    lines.extend(
        [
            "",
            "Use the buttons below,",
            *fallback,
        ]
    )
    return "\n".join(lines)


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

    operator_payload = _operator_action_payload(action)
    if operator_payload is not None:
        return _format_operator_action_notification(action, operator_payload)

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
    lines.extend(["", "Use the buttons below,", *fallback_lines(action_id)])
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

    try:
        message = format_notification(action)
        keyboard = _build_keyboard(action_id)
    except HitlNotificationConfigurationError:
        print(
            f"[hitl_notify] notification refused for {action_id}: dedicated signing secret unavailable",
            flush=True,
        )
        _audit_notify(action_id, "send_failed", {"error": "hitl_notify_secret_unavailable"})
        return False
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
    if callback_data.startswith("HITL_WHY:"):
        return explain_pending_action(callback_data[len("HITL_WHY:"):])
    if not callback_data.startswith("HITL:"):
        return "[Error] Not a HITL callback."

    raw_token = callback_data[len("HITL:"):]
    result = handle_callback(raw_token, approved_by=approved_by)

    if result["ok"]:
        return terminal_outcome("approved" if result["decision"] == "Y" else "denied")

    error = result.get("error", "unknown")
    if error in {"token_expired", "action_not_found_or_terminal"}:
        return terminal_outcome("expired")
    return terminal_outcome("unavailable")


def explain_pending_action(action_id: str) -> str:
    """Return a compact 'Why now?' explanation for a pending HITL action."""
    action = _svc.get_pending_action(action_id)
    if not action or action.get("status") != WAITING_FOR_APPROVAL:
        return "[Expired] No matching pending HITL approval."
    payload = _operator_action_payload(action) or {}
    summary = str(payload.get("summary") or action.get("action_type") or "Pending action")
    warning = str(payload.get("risk_warning") or "This action requires explicit operator approval.")
    route_back = payload.get("route_back") if isinstance(payload.get("route_back"), dict) else {}
    return "\n".join(
        [
            "Why now?",
            f"Action ID: {action_id}",
            f"Summary: {summary}",
            f"Warning: {warning}",
            f"Route back: {route_back.get('type', route_back.get('handler', 'action dispatcher'))}",
            "Approving records your decision and hands the action back to its owning executor.",
        ]
    )


def _parse_typed_decision(text: str, action: dict) -> tuple[str | None, str | None]:
    return parse_human_reply(text, str(action.get("action_id") or ""))


def handle_typed_reply(text: str, *, approved_by: str = "operator") -> dict:
    """Apply a typed CODE DECISION reply against pending HITL action records."""
    pending = _svc.list_pending_actions(status=WAITING_FOR_APPROVAL)
    if not pending:
        return {"handled": False, "ok": False, "error": "no_pending_hitl_approval", "reply": ""}

    matches: list[tuple[dict, str]] = []
    errors: list[str] = []
    for action in pending:
        decision, error = _parse_typed_decision(text, action)
        if decision is not None:
            matches.append((action, decision))
        elif error:
            errors.append(error)

    if len(matches) > 1:
        return {
            "handled": True,
            "ok": False,
            "error": "ambiguous_reply_code_collision",
            "reply": "That short code matches more than one pending approval. Use the buttons; nothing was approved or denied.",
        }
    if not matches:
        codes = [_reply_code(action.get("action_id", "")) for action in pending[:5]]
        return {
            "handled": True,
            "ok": False,
            "error": "wrong_reply_code" if "wrong_reply_code" in errors else "reply_code_required",
            "reply": "Pending HITL approval. Use APPROVE or DENY with one of these codes: " + ", ".join(codes),
        }

    action, decision = matches[0]
    try:
        signed_token = generate_token(action["action_id"], decision)
    except HitlNotificationConfigurationError:
        return {
            "handled": True,
            "ok": False,
            "action_id": action["action_id"],
            "decision": decision,
            "error": "hitl_notify_secret_unavailable",
            "reply": terminal_outcome("unavailable"),
        }
    signed_result = handle_callback(signed_token, approved_by=approved_by)
    ok = bool(signed_result.get("ok"))
    if ok:
        _audit_notify(
            action["action_id"],
            "typed_reply_applied",
            {"decision": decision, "approved_by": approved_by},
        )
        return {
            "handled": True,
            "ok": True,
            "action_id": action["action_id"],
            "decision": decision,
            "reply": terminal_outcome("approved" if decision == "Y" else "denied"),
        }
    return {
        "handled": True,
        "ok": False,
        "action_id": action["action_id"],
        "decision": decision,
        "error": "action_not_found_or_terminal",
        "reply": terminal_outcome("expired"),
    }


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
            {
                "error": result["error"],
                "token_fingerprint": hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:12],
            },
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
