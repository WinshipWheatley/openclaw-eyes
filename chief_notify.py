"""
chief_notify.py

Thin wrapper for sending a Telegram message to the authorized user
from background threads and scheduled tasks that can't use the bot
instance directly.
"""

import json
import os
import urllib.request

from telegram_listener_integrity import resolve_role_bot_token
from operator_surface_guard import guard_operator_reply_with_receipt


def send(
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str | None = "Markdown",
) -> dict:
    """Send a Telegram message to the authorized user. Silent on failure."""
    bounded = guard_operator_reply_with_receipt(
        text,
        agent_role="CHIEF",
        technical_intent=False,
    )
    text = bounded.visible_text
    boundary_receipt = bounded.receipt.to_dict()
    try:
        token = resolve_role_bot_token("chief")
    except RuntimeError:
        return boundary_receipt
    user_id = os.environ.get("TELEGRAM_AUTHORIZED_USER_ID", "")
    if not token or not user_id:
        return boundary_receipt
    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict = {
        "chat_id":    int(user_id),
        "text":       text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    encoded = json.dumps(payload).encode()
    try:
        req = urllib.request.Request(
            url, data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass
    return boundary_receipt
