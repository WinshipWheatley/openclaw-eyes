"""
chief_notify.py

Thin wrapper for sending a Telegram message to the authorized user
from background threads and scheduled tasks that can't use the bot
instance directly.
"""

import json
import os
import urllib.request


def send(text: str, reply_markup: dict | None = None) -> None:
    """Send a Telegram message to the authorized user. Silent on failure."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    user_id = os.environ.get("TELEGRAM_AUTHORIZED_USER_ID", "")
    if not token or not user_id:
        return
    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict = {
        "chat_id":    int(user_id),
        "text":       text,
        "parse_mode": "Markdown",
    }
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
