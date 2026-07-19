from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakePeer:
    def __init__(self, *, thread: dict, steer_response: dict | None = None):
        self.thread = thread
        self.steer_response = steer_response or {"turnId": "turn-active"}
        self.requests: list[tuple[str, dict]] = []
        self.notifications: list[tuple[str, dict]] = []

    def request(self, method: str, params: dict) -> dict:
        self.requests.append((method, params))
        if method == "initialize":
            return {"serverInfo": {"version": "0.144.5"}}
        if method == "thread/read":
            return {"thread": self.thread}
        if method == "turn/steer":
            return self.steer_response
        raise AssertionError(f"unexpected method: {method}")

    def notify(self, method: str, params: dict) -> None:
        self.notifications.append((method, params))


def _thread(*, thread_id: str = "thread-exact", status: str = "active", turns=None) -> dict:
    return {
        "id": thread_id,
        "status": {"type": status, "activeFlags": []} if status == "active" else {"type": status},
        "turns": list(turns if turns is not None else [{"id": "turn-active", "status": "inProgress"}]),
    }


def test_steers_only_the_exact_active_turn() -> None:
    from codex_app_server_control import steer_exact_active_turn

    peer = FakePeer(thread=_thread())

    outcome = steer_exact_active_turn(
        peer,
        thread_id="thread-exact",
        message="urgent marker",
        client_user_message_id="wake-event-1",
    )

    assert outcome.status == "delivered"
    assert outcome.thread_id == "thread-exact"
    assert outcome.turn_id == "turn-active"
    assert peer.notifications == [("initialized", {})]
    assert [method for method, _ in peer.requests] == [
        "initialize",
        "thread/read",
        "turn/steer",
    ]
    assert peer.requests[1][1] == {
        "threadId": "thread-exact",
        "includeTurns": True,
    }
    assert peer.requests[2][1] == {
        "threadId": "thread-exact",
        "expectedTurnId": "turn-active",
        "input": [{"type": "text", "text": "urgent marker"}],
        "clientUserMessageId": "wake-event-1",
    }


def test_idle_thread_is_reported_without_steering() -> None:
    from codex_app_server_control import steer_exact_active_turn

    peer = FakePeer(thread=_thread(status="idle", turns=[]))

    outcome = steer_exact_active_turn(peer, thread_id="thread-exact", message="urgent")

    assert outcome.status == "idle"
    assert [method for method, _ in peer.requests] == ["initialize", "thread/read"]


def test_thread_id_mismatch_fails_closed() -> None:
    from codex_app_server_control import steer_exact_active_turn

    peer = FakePeer(thread=_thread(thread_id="wrong-thread"))

    outcome = steer_exact_active_turn(peer, thread_id="thread-exact", message="urgent")

    assert outcome.status == "thread_mismatch"
    assert all(method != "turn/steer" for method, _ in peer.requests)


def test_zero_or_multiple_in_progress_turns_fail_closed() -> None:
    from codex_app_server_control import steer_exact_active_turn

    no_active = FakePeer(thread=_thread(turns=[{"id": "old", "status": "completed"}]))
    ambiguous = FakePeer(
        thread=_thread(
            turns=[
                {"id": "turn-one", "status": "inProgress"},
                {"id": "turn-two", "status": "inProgress"},
            ]
        )
    )

    assert steer_exact_active_turn(no_active, thread_id="thread-exact", message="urgent").status == "no_active_turn"
    assert steer_exact_active_turn(ambiguous, thread_id="thread-exact", message="urgent").status == "ambiguous_active_turn"
    assert all(method != "turn/steer" for method, _ in no_active.requests + ambiguous.requests)


def test_version_and_protocol_failures_are_typed_undelivered_outcomes() -> None:
    from codex_app_server_control import steer_exact_active_turn

    class WrongVersionPeer(FakePeer):
        def request(self, method: str, params: dict) -> dict:
            if method == "initialize":
                self.requests.append((method, params))
                return {"serverInfo": {"version": "99.0.0"}}
            return super().request(method, params)

    class FailedSteerPeer(FakePeer):
        def request(self, method: str, params: dict) -> dict:
            if method == "turn/steer":
                self.requests.append((method, params))
                raise RuntimeError("activeTurnNotSteerable")
            return super().request(method, params)

    wrong = steer_exact_active_turn(
        WrongVersionPeer(thread=_thread()),
        thread_id="thread-exact",
        message="urgent",
    )
    failed = steer_exact_active_turn(
        FailedSteerPeer(thread=_thread()),
        thread_id="thread-exact",
        message="urgent",
    )

    assert wrong.status == "version_mismatch"
    assert failed.status == "steer_failed"
    assert "activeTurnNotSteerable" in failed.detail


def test_blank_target_or_message_is_rejected_before_protocol_use() -> None:
    import pytest

    from codex_app_server_control import steer_exact_active_turn

    peer = FakePeer(thread=_thread())
    with pytest.raises(ValueError, match="thread_id"):
        steer_exact_active_turn(peer, thread_id="", message="urgent")
    with pytest.raises(ValueError, match="message"):
        steer_exact_active_turn(peer, thread_id="thread-exact", message="")
    assert peer.requests == []


def test_production_client_has_no_turn_abort_request() -> None:
    source = (ROOT / "codex_app_server_control.py").read_text(encoding="utf-8")

    assert "turn/" + "interrupt" not in source
    assert "kill(" not in source
    assert "terminate(" not in source
