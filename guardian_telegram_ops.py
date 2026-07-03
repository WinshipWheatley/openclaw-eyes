"""Real Telegram send/edit/delete for the Guardian approval board.

Implements the TelegramOps interface the board needs, via the Guardian bot channel
(chief_guardian_sender's token/chat resolution). Fail-soft: every method swallows
errors and returns a safe value so a Telegram hiccup can never break the sweep — the
board simply reconciles again next cycle.
"""

from __future__ import annotations

from typing import Any

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore


def _api(method: str) -> str | None:
    try:
        from chief_guardian_sender import _token, _chat_id  # reuse the resolved token/chat
        token = _token(require_guardian=False)
        return f"https://api.telegram.org/bot{token}/{method}"
    except Exception:
        return None


def _chat() -> str | None:
    try:
        from chief_guardian_sender import _chat_id
        return _chat_id()
    except Exception:
        return None


class GuardianTelegramOps:
    """Live Telegram operations on the Guardian channel."""

    def send(self, text: str, buttons: dict | None = None) -> int:
        url, chat = _api("sendMessage"), _chat()
        if not (url and chat and requests):
            return -1
        payload: dict[str, Any] = {"chat_id": chat, "text": text}
        if buttons is not None:
            payload["reply_markup"] = buttons
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            return int(r.json().get("result", {}).get("message_id", -1))
        except Exception:
            return -1

    def edit(self, message_id: int, text: str, buttons: dict | None = None) -> None:
        url, chat = _api("editMessageText"), _chat()
        if not (url and chat and requests) or not message_id or message_id < 0:
            return
        payload: dict[str, Any] = {"chat_id": chat, "message_id": message_id, "text": text}
        if buttons is not None:
            payload["reply_markup"] = buttons
        try:
            requests.post(url, json=payload, timeout=15)
        except Exception:
            pass

    def delete(self, message_id: int) -> None:
        url, chat = _api("deleteMessage"), _chat()
        if not (url and chat and requests) or not message_id or message_id < 0:
            return
        try:
            requests.post(url, json={"chat_id": chat, "message_id": message_id}, timeout=15)
        except Exception:
            pass


__all__ = ["GuardianTelegramOps"]
