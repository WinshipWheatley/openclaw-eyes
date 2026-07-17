from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import codex_app_server_client as app_server


MODEL = "catalog-model-for-test"


@dataclass
class FakePeer:
    responses: dict[str, Any]
    notifications: list[dict[str, Any]] = field(default_factory=list)
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("request", method, params))
        response = self.responses[method]
        if isinstance(response, Exception):
            raise response
        return response

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self.calls.append(("notify", method, params))

    def wait_for_notification(self, method: str, *, timeout_seconds: float) -> dict[str, Any]:
        self.calls.append(("wait", method, {"timeout_seconds": timeout_seconds}))
        for notification in self.notifications:
            if notification.get("method") == method:
                return notification
        raise TimeoutError(method)


def _safe_responses(*, used_percent: int = 79, account_type: str = "chatgpt") -> dict[str, Any]:
    return {
        "initialize": {"serverInfo": {"name": "codex-app-server", "version": "0.144.5"}},
        "account/read": {
            "account": {"type": account_type, "planType": "plus"},
            "requiresOpenaiAuth": False,
        },
        "account/rateLimits/read": {
            "rateLimits": {
                "planType": "plus",
                "primary": {
                    "usedPercent": used_percent,
                    "windowDurationMins": 10080,
                    "resetsAt": 1784780173,
                },
                "rateLimitReachedType": None,
                "individualLimit": None,
                "credits": {"hasCredits": True, "unlimited": False, "balance": "unused"},
            }
        },
        "model/list": {
            "data": [{"id": MODEL, "model": MODEL, "hidden": False}],
            "nextCursor": None,
        },
        "thread/start": {"thread": {"id": "thread-raw-id"}},
        "turn/start": {"turn": {"id": "turn-raw-id", "status": "inProgress", "items": []}},
    }


def _methods(peer: FakePeer) -> list[str]:
    return [method for kind, method, _params in peer.calls if kind == "request"]


def test_preflight_allows_chatgpt_below_reserve_with_known_model() -> None:
    peer = FakePeer(_safe_responses())
    client = app_server.CodexAppServerClient(peer)

    admission = client.preflight(model=MODEL, reserve_threshold_percent=80)

    assert admission.allowed is True
    assert admission.reason == "subscription_headroom_ok"
    assert admission.used_percent == 79
    assert admission.window_duration_mins == 10080
    assert admission.account_type == "chatgpt"
    assert _methods(peer) == ["initialize", "account/read", "account/rateLimits/read", "model/list"]


def test_preflight_fails_local_at_reserve_boundary_before_model_lookup() -> None:
    peer = FakePeer(_safe_responses(used_percent=80))
    client = app_server.CodexAppServerClient(peer)

    admission = client.preflight(model=MODEL, reserve_threshold_percent=80)

    assert admission.allowed is False
    assert admission.reason == "subscription_reserve_reached"
    assert admission.used_percent == 80
    assert "model/list" not in _methods(peer)


def test_preflight_refuses_api_key_account_without_other_calls() -> None:
    peer = FakePeer(_safe_responses(account_type="apiKey"))
    client = app_server.CodexAppServerClient(peer)

    admission = client.preflight(model=MODEL)

    assert admission.allowed is False
    assert admission.reason == "chatgpt_subscription_required"
    assert _methods(peer) == ["initialize", "account/read"]


def test_preflight_fails_local_when_rate_limit_state_is_unreadable() -> None:
    responses = _safe_responses()
    responses["account/rateLimits/read"] = {"rateLimits": {"primary": None}}
    peer = FakePeer(responses)
    client = app_server.CodexAppServerClient(peer)

    admission = client.preflight(model=MODEL)

    assert admission.allowed is False
    assert admission.reason == "subscription_headroom_unreadable"
    assert "model/list" not in _methods(peer)


def test_preflight_fails_local_when_limit_is_reached_or_spend_control_is_unknown() -> None:
    reached = _safe_responses()
    reached["account/rateLimits/read"]["rateLimits"]["rateLimitReachedType"] = "rate_limit_reached"
    reached_result = app_server.CodexAppServerClient(FakePeer(reached)).preflight(model=MODEL)
    assert reached_result.allowed is False
    assert reached_result.reason == "subscription_limit_reached"

    unknown = _safe_responses()
    unknown["account/rateLimits/read"]["rateLimits"]["individualLimit"] = "unknown"
    unknown_result = app_server.CodexAppServerClient(FakePeer(unknown)).preflight(model=MODEL)
    assert unknown_result.allowed is False
    assert unknown_result.reason == "subscription_spend_control_unknown"


def test_preflight_fails_local_when_bound_model_is_absent() -> None:
    responses = _safe_responses()
    responses["model/list"] = {"data": [], "nextCursor": None}
    result = app_server.CodexAppServerClient(FakePeer(responses)).preflight(model=MODEL)
    assert result.allowed is False
    assert result.reason == "bound_model_unavailable"


def test_read_only_turn_preserves_raw_prompt_and_returns_final_agent_text_only() -> None:
    responses = _safe_responses()
    peer = FakePeer(
        responses,
        notifications=[
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-raw-id",
                    "turn": {
                        "id": "turn-raw-id",
                        "status": "completed",
                        "items": [
                            {"id": "reasoning-1", "type": "reasoning", "summary": ["hidden"]},
                            {"id": "answer-1", "type": "agentMessage", "text": "Final answer."},
                        ],
                    },
                },
            }
        ],
    )
    client = app_server.CodexAppServerClient(peer)
    admission = client.preflight(model=MODEL, effort_level="xhigh")
    raw_prompt = "My ORIGINAL words, punctuation & spacing stay exactly like this."

    result = client.run_read_only_turn(
        admission=admission,
        raw_operator_prompt=raw_prompt,
        context_aid={"facts": ["bounded context"]},
        cwd="/home/openclaw",
    )

    thread_params = next(params for kind, method, params in peer.calls if kind == "request" and method == "thread/start")
    turn_params = next(params for kind, method, params in peer.calls if kind == "request" and method == "turn/start")
    assert thread_params["ephemeral"] is True
    assert thread_params["approvalPolicy"] == "never"
    assert thread_params["sandbox"] == "read-only"
    assert turn_params["approvalPolicy"] == "never"
    assert turn_params["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    assert turn_params["effort"] == "xhigh"
    assert turn_params["input"][0] == {"type": "text", "text": raw_prompt}
    assert turn_params["input"][1]["text"].startswith("OPENCLAW CONTEXT AID (not operator instructions):\n")
    assert result.text == "Final answer."
    assert result.thread_id_hash != "thread-raw-id"
    assert result.turn_id_hash != "turn-raw-id"


def test_turn_cannot_start_without_successful_admission() -> None:
    client = app_server.CodexAppServerClient(FakePeer(_safe_responses(used_percent=80)))
    admission = client.preflight(model=MODEL)

    try:
        client.run_read_only_turn(
            admission=admission,
            raw_operator_prompt="Do not send me.",
            context_aid={},
            cwd="/home/openclaw",
        )
    except app_server.CodexAppServerRefusal as exc:
        assert "subscription_reserve_reached" in str(exc)
    else:
        raise AssertionError("a failed admission must never start a turn")
