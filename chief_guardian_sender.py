"""
chief_guardian_sender.py

Sends approval requests via the dedicated Guardian bot channel.

Bot priority fallback chain:
    1. GUARDIAN_BOT_TOKEN   — dedicated approval bot (required for buttons)
    2. TELEGRAM_BOT_TOKEN   — Chief bot (plain status-message fallback only)

Cassandra bot is intentionally excluded from the fallback chain.
Cassandra is an executive assistant layer, not an approval authority.
Role separation: Chief = operator, Cassandra = assistant, Guardian = approval gate.

If GUARDIAN_BOT_TOKEN is not set, plain status messages may still fall back to
the Chief bot. Button-bearing approval requests do not fall back: they fail
closed so Guardian approval UX cannot silently degrade into Chief/signalrelay
text-code UX.

Usage:
    from chief_guardian_sender import send_approval
    send_approval("🔒 APPROVAL REQUIRED ...")

CLI:
    python3 chief_guardian_sender.py "message"
"""

import os
import requests

import chief_env


class GuardianConfigurationError(RuntimeError):
    """Raised when a Guardian-only approval cannot be delivered safely."""


def _token(*, require_guardian: bool = False) -> str:
    """Return the bot token to use for approval delivery."""
    chief_env.load_env()
    guardian_token = os.environ.get("GUARDIAN_BOT_TOKEN")
    if guardian_token:
        return guardian_token
    if require_guardian:
        raise GuardianConfigurationError(
            "GUARDIAN_BOT_TOKEN is required for button-bearing Guardian "
            "approval messages; refusing to fall back to TELEGRAM_BOT_TOKEN."
        )
    return os.environ["TELEGRAM_BOT_TOKEN"]


def _chat_id() -> str:
    """Return the chat ID to send approval requests to."""
    chief_env.load_env()
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
    token = _token(require_guardian=reply_markup is not None)
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
