"""Fail-closed control-plane delivery into one exact active Codex turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


REQUIRED_APP_SERVER_VERSION = "0.144.5"
_CLIENT_INFO = {
    "name": "openclaw-fleet-wake-v2b",
    "title": "OpenClaw Fleet Wake v2b",
    "version": "2.0",
}


class AppServerControlPeer(Protocol):
    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

    def notify(self, method: str, params: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class MidturnDeliveryOutcome:
    status: str
    thread_id: str
    turn_id: str = ""
    detail: str = ""


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _initialization_version(response: Mapping[str, Any]) -> str:
    server_info = _mapping(response.get("serverInfo"))
    return str((server_info or {}).get("version") or "")


def _outcome(
    status: str,
    thread_id: str,
    *,
    turn_id: str = "",
    detail: str = "",
) -> MidturnDeliveryOutcome:
    return MidturnDeliveryOutcome(
        status=status,
        thread_id=thread_id,
        turn_id=turn_id,
        detail=detail,
    )


def steer_exact_active_turn(
    peer: AppServerControlPeer,
    *,
    thread_id: str,
    message: str,
    client_user_message_id: str = "",
    required_version: str = REQUIRED_APP_SERVER_VERSION,
) -> MidturnDeliveryOutcome:
    """Steer one verified active turn, returning a typed undelivered outcome otherwise."""

    exact_thread_id = str(thread_id or "").strip()
    exact_message = str(message or "").strip()
    if not exact_thread_id:
        raise ValueError("thread_id is required")
    if not exact_message:
        raise ValueError("message is required")

    try:
        initialized = peer.request(
            "initialize",
            {
                "clientInfo": dict(_CLIENT_INFO),
                "capabilities": {"experimentalApi": False},
            },
        )
        version = _initialization_version(initialized)
        if version != required_version:
            return _outcome(
                "version_mismatch",
                exact_thread_id,
                detail=version or "unknown",
            )
        peer.notify("initialized", {})
    except Exception as exc:
        return _outcome("control_unavailable", exact_thread_id, detail=str(exc))

    try:
        response = peer.request(
            "thread/read",
            {"threadId": exact_thread_id, "includeTurns": True},
        )
    except Exception as exc:
        return _outcome("thread_read_failed", exact_thread_id, detail=str(exc))

    thread = _mapping(response.get("thread"))
    if thread is None:
        return _outcome("invalid_thread_response", exact_thread_id)
    if str(thread.get("id") or "") != exact_thread_id:
        return _outcome("thread_mismatch", exact_thread_id)

    thread_status = _mapping(thread.get("status"))
    status_type = str((thread_status or {}).get("type") or "")
    if status_type == "idle":
        return _outcome("idle", exact_thread_id)
    if status_type != "active":
        return _outcome("not_active", exact_thread_id, detail=status_type or "unknown")

    raw_turns = thread.get("turns")
    if not isinstance(raw_turns, list):
        return _outcome("invalid_thread_response", exact_thread_id)
    active_turns = [
        turn
        for turn in raw_turns
        if isinstance(turn, Mapping) and turn.get("status") == "inProgress"
    ]
    if not active_turns:
        return _outcome("no_active_turn", exact_thread_id)
    if len(active_turns) != 1:
        return _outcome("ambiguous_active_turn", exact_thread_id)
    active_turn_id = str(active_turns[0].get("id") or "").strip()
    if not active_turn_id:
        return _outcome("invalid_thread_response", exact_thread_id)

    params: dict[str, Any] = {
        "threadId": exact_thread_id,
        "expectedTurnId": active_turn_id,
        "input": [{"type": "text", "text": exact_message}],
    }
    if client_user_message_id:
        params["clientUserMessageId"] = str(client_user_message_id)
    try:
        steer_response = peer.request("turn/steer", params)
    except Exception as exc:
        return _outcome(
            "steer_failed",
            exact_thread_id,
            turn_id=active_turn_id,
            detail=str(exc),
        )
    response_turn_id = str(steer_response.get("turnId") or "")
    if response_turn_id != active_turn_id:
        return _outcome(
            "steer_response_mismatch",
            exact_thread_id,
            turn_id=active_turn_id,
            detail=response_turn_id or "missing",
        )
    return _outcome("delivered", exact_thread_id, turn_id=active_turn_id)
