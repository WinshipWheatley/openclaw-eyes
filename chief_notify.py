"""
chief_notify.py

Thin wrapper for sending a Telegram message to the authorized user
from background threads and scheduled tasks that can't use the bot
instance directly.
"""

import json
import os
import urllib.request


def send(text: str) -> None:
    """Send a Telegram message to the authorized user. Silent on failure."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    user_id = os.environ.get("TELEGRAM_AUTHORIZED_USER_ID", "")
    if not token or not user_id:
        return
    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id":    int(user_id),
        "text":       text,
        "parse_mode": "Markdown",
    }).encode()
    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass
