"""
chief_guardian_sender.py

Sends approval requests via the dedicated Guardian bot channel.

Bot priority fallback chain:
  1. GUARDIAN_BOT_TOKEN   — dedicated approval bot (ideal; create via BotFather)
  2. TELEGRAM_BOT_TOKEN   — Chief bot (current behavior, preserved as fallback)

Cassandra bot is intentionally excluded from the fallback chain.
Cassandra is an executive assistant layer, not an approval authority.
Role separation: Chief = operator, Cassandra = assistant, Guardian = approval gate.

If GUARDIAN_BOT_TOKEN is not set, this module falls back to the Chief bot —
meaning approval messages continue to travel via the Chief channel until a
dedicated Guardian bot is configured. Behavior is identical to pre-upgrade
in that case.

Usage:
    from chief_guardian_sender import send_approval
    send_approval("🔒 APPROVAL REQUIRED ...")

CLI:
    python3 chief_guardian_sender.py "message"
"""

import os
import requests


def _load_env_file() -> None:
    env_path = "/home/openclaw/.chief.env"
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def _token() -> str:
    """Return the bot token to use for approval delivery."""
    _load_env_file()
    return (
        os.environ.get("GUARDIAN_BOT_TOKEN")
        or os.environ["TELEGRAM_BOT_TOKEN"]
    )


def _chat_id() -> str:
    """Return the chat ID to send approval requests to."""
    _load_env_file()
    return (
        os.environ.get("TELEGRAM_CHAT_ID")
        or os.environ["TELEGRAM_AUTHORIZED_USER_ID"]
    )


def using_dedicated_bot() -> bool:
    """True if a dedicated GUARDIAN_BOT_TOKEN is configured (not falling back)."""
    return bool(os.environ.get("GUARDIAN_BOT_TOKEN"))


def send_approval(message: str, reply_markup: dict | None = None) -> None:
    """Send an approval request via the Guardian bot channel.

    reply_markup: optional Telegram InlineKeyboardMarkup dict. When provided,
    the message is sent with inline tap buttons. Pass None (default) to send
    plain text (e.g. collision/timeout notifications that need no buttons).
    """
    token = _token()
    chat_id = _chat_id()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict = {"chat_id": chat_id, "text": message}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    response = requests.post(url, json=payload, timeout=15)
    response.raise_for_status()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print('Usage: python3 chief_guardian_sender.py "message"')
        sys.exit(1)
    send_approval(" ".join(sys.argv[1:]))
    dedicated = using_dedicated_bot()
    print(f"Approval message sent ({'Guardian bot' if dedicated else 'Chief bot fallback'}).")
