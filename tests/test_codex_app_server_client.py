from __future__ import annotations

import json
import subprocess
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import codex_app_server_client as app_server


MODEL = "catalog-model-for-test"


def test_work_turn_output_preserves_nested_structured_answer_as_json() -> None:
    answer, critique = app_server._parse_work_turn_output(
        json.dumps(
            {
                "answer": {
                    "route": "BRAIN",
                    "confidence": 0.98,
                    "answer_draft": "Focused context helps. COPPERKITE",
                },
                "packet_critique": {
                    "summary": "The packet was focused.",
                    "quality_score": 94,
                    "missing": [],
                    "noise": [],
                    "mis_scoped": [],
                    "improvement_items": [],
                    "grounded_in_turn": ["bounded context"],
                },
            }
        )
    )

    assert json.loads(answer)["route"] == "BRAIN"
    assert json.loads(answer)["answer_draft"].endswith("COPPERKITE")
    assert critique["quality_score"] == 94


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
        for index, notification in enumerate(self.notifications):
            if notification.get("method") == method:
                return self.notifications.pop(index)
        raise TimeoutError(method)


@dataclass
class FakeLineTransport:
    inbound: deque[str]
    outbound: list[str] = field(default_factory=list)

    def read_line(self, *, timeout_seconds: float) -> str:
        if not self.inbound:
            raise TimeoutError(timeout_seconds)
        return self.inbound.popleft()

    def write_line(self, line: str) -> None:
        self.outbound.append(line)


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


def test_preflight_requests_guardian_approval_at_reserve_boundary_before_model_lookup() -> None:
    peer = FakePeer(_safe_responses(used_percent=80))
    client = app_server.CodexAppServerClient(peer)

    admission = client.preflight(
        model=MODEL,
        effort_level="high",
        request_hash="sha256:request",
        lane_id="hard_lane",
        reserve_threshold_percent=80,
    )

    assert admission.allowed is False
    assert admission.reason == "guardian_approval_required"
    assert admission.used_percent == 80
    assert admission.guardian_approval_required is True
    assert admission.guardian_approval_request == {
        "schema_version": "external_subscription_guardian_request_v1",
        "action_type": "external_subscription_over_reserve",
        "request_hash": "sha256:request",
        "lane_id": "hard_lane",
        "effort_level": "high",
        "used_percent": 80,
        "reserve_threshold_percent": 80,
        "window_duration_mins": 10080,
        "binding_model_id": MODEL,
    }
    assert "model/list" not in _methods(peer)


def test_verified_guardian_approval_allows_catalog_check_above_reserve() -> None:
    observed: dict = {}

    def verify(action_id: str, scope: dict[str, Any]) -> bool:
        observed.update(scope)
        return action_id == "guardian-action-1"

    peer = FakePeer(_safe_responses(used_percent=84))
    client = app_server.CodexAppServerClient(peer, guardian_approval_verifier=verify)

    admission = client.preflight(
        model=MODEL,
        effort_level="xhigh",
        request_hash="sha256:request",
        lane_id="hard_lane",
        reserve_threshold_percent=80,
        guardian_approval_id="guardian-action-1",
    )

    assert admission.allowed is True
    assert admission.guardian_approved is True
    assert admission.guardian_approval_id == "guardian-action-1"
    assert observed["used_percent"] == 84
    assert observed["effort_level"] == "xhigh"
    assert "model/list" in _methods(peer)


def test_unverified_guardian_approval_stays_local() -> None:
    peer = FakePeer(_safe_responses(used_percent=81))
    client = app_server.CodexAppServerClient(
        peer,
        guardian_approval_verifier=lambda _action_id, _scope: False,
    )

    admission = client.preflight(
        model=MODEL,
        request_hash="sha256:request",
        lane_id="mid_lane",
        guardian_approval_id="stale-or-mismatched",
    )

    assert admission.allowed is False
    assert admission.reason == "guardian_approval_invalid"
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
                            {
                                "id": "answer-1",
                                "type": "agentMessage",
                                "text": json.dumps(
                                    {
                                        "answer": "Final answer.",
                                        "packet_critique": {
                                            "summary": "The packet was focused and sufficient.",
                                            "quality_score": 92,
                                            "missing": [],
                                            "noise": [],
                                            "mis_scoped": [],
                                            "improvement_items": [],
                                            "grounded_in_turn": ["bounded context supported the answer"],
                                        },
                                    }
                                ),
                            },
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
        original_operator_message="ORIGINAL words, punctuation & spacing",
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
    assert result.packet_critique["quality_score"] == 92
    assert result.packet_critique["summary"] == "The packet was focused and sufficient."
    assert result.thread_id_hash != "thread-raw-id"
    assert result.turn_id_hash != "turn-raw-id"
    assert result.original_message_present_in_prompt is True
    assert len(result.original_message_sha256) == 64
    assert len(result.prompt_sha256) == 64
    assert len(result.prompt_composition_sha256) == 64


def test_read_only_turn_receipts_stable_cache_prefix_and_observed_cached_tokens() -> None:
    peer = FakePeer(
        _safe_responses(),
        notifications=[
            {
                "method": "thread/tokenUsage/updated",
                "params": {
                    "threadId": "thread-raw-id",
                    "turnId": "turn-raw-id",
                    "tokenUsage": {
                        "last": {
                            "cachedInputTokens": 320,
                            "inputTokens": 480,
                            "outputTokens": 40,
                            "reasoningOutputTokens": 12,
                            "totalTokens": 532,
                        },
                        "total": {
                            "cachedInputTokens": 320,
                            "inputTokens": 480,
                            "outputTokens": 40,
                            "reasoningOutputTokens": 12,
                            "totalTokens": 532,
                        },
                    },
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-raw-id",
                    "turn": {
                        "id": "turn-raw-id",
                        "status": "completed",
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": json.dumps(
                                    {
                                        "answer": "Cached answer.",
                                        "packet_critique": {
                                            "summary": "The packet was bounded.",
                                            "quality_score": 90,
                                            "missing": [],
                                            "noise": [],
                                            "mis_scoped": [],
                                            "improvement_items": [],
                                            "grounded_in_turn": ["bounded packet"],
                                        },
                                    }
                                ),
                            }
                        ],
                    },
                },
            },
        ],
    )
    client = app_server.CodexAppServerClient(peer)
    admission = client.preflight(model=MODEL)

    result = client.run_read_only_turn(
        admission=admission,
        raw_operator_prompt="Dynamic operator suffix.",
        context_aid={"packet_id": "packet-1"},
        cwd="/home/openclaw",
        cache_prefix="Maestro immutable persona core v1",
    )

    thread_params = next(
        params
        for kind, method, params in peer.calls
        if kind == "request" and method == "thread/start"
    )
    assert "Maestro immutable persona core v1" in thread_params["baseInstructions"]
    assert "The first user input is the complete task prompt." in thread_params["baseInstructions"]
    assert "place that structured output verbatim in answer" in thread_params["baseInstructions"]
    assert result.cache_prefix_sha256.startswith("sha256:")
    assert result.cache_prefix_chars > 0
    assert result.input_tokens == 480
    assert result.cached_input_tokens == 320
    assert result.cache_read_hit is True
    assert result.cache_read_ratio == 0.6667


def test_turn_cannot_start_without_successful_admission() -> None:
    client = app_server.CodexAppServerClient(FakePeer(_safe_responses(used_percent=80)))
    admission = client.preflight(
        model=MODEL,
        request_hash="sha256:request",
        lane_id="mid_lane",
    )

    try:
        client.run_read_only_turn(
            admission=admission,
            raw_operator_prompt="Do not send me.",
            context_aid={},
            cwd="/home/openclaw",
        )
    except app_server.CodexAppServerRefusal as exc:
        assert "guardian_approval_required" in str(exc)
    else:
        raise AssertionError("a failed admission must never start a turn")


def test_read_only_turn_collects_v2_item_completed_agent_message() -> None:
    peer = FakePeer(
        _safe_responses(),
        notifications=[
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thread-raw-id",
                    "turnId": "turn-raw-id",
                    "completedAtMs": 1,
                    "item": {
                        "id": "answer-1",
                        "type": "agentMessage",
                        "text": json.dumps(
                            {
                                "answer": "V2 final answer.",
                                "packet_critique": {
                                    "summary": "Useful but one source was stale.",
                                    "quality_score": 74,
                                    "missing": ["fresh status"],
                                    "noise": [],
                                    "mis_scoped": [],
                                    "improvement_items": ["refresh the status source"],
                                    "grounded_in_turn": ["status timestamp was old"],
                                },
                            }
                        ),
                    },
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-raw-id",
                    "turn": {"id": "turn-raw-id", "status": "completed", "items": []},
                },
            },
        ],
    )
    client = app_server.CodexAppServerClient(peer)
    admission = client.preflight(model=MODEL)

    result = client.run_read_only_turn(
        admission=admission,
        raw_operator_prompt="Synthetic public prompt.",
        context_aid={},
        cwd="/home/openclaw",
    )

    assert result.text == "V2 final answer."
    assert result.packet_critique["improvement_items"] == ["refresh the status source"]


def test_read_only_turn_refuses_output_without_packet_critique() -> None:
    peer = FakePeer(
        _safe_responses(),
        notifications=[
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-raw-id",
                    "turn": {
                        "id": "turn-raw-id",
                        "status": "completed",
                        "items": [
                            {"id": "answer-1", "type": "agentMessage", "text": "answer only"}
                        ],
                    },
                },
            }
        ],
    )
    client = app_server.CodexAppServerClient(peer)
    admission = client.preflight(model=MODEL)

    try:
        client.run_read_only_turn(
            admission=admission,
            raw_operator_prompt="Synthetic public prompt.",
            context_aid={},
            cwd="/home/openclaw",
        )
    except app_server.CodexAppServerRefusal as exc:
        assert "packet_critique" in str(exc)
    else:
        raise AssertionError("a work turn without its packet critique must fail closed")


def test_safe_subscription_receipt_contains_binding_and_no_raw_prompt() -> None:
    admission = app_server.SubscriptionAdmission(
        allowed=False,
        reason="guardian_approval_required",
        model=MODEL,
        effort_level="high",
        account_type="chatgpt",
        used_percent=80,
        window_duration_mins=10080,
        guardian_approval_required=True,
        app_server_version="0.144.5",
        app_server_version_source="verified_pinned_cli",
    )

    receipt = app_server.build_safe_subscription_receipt(
        admission,
        request_hash="sha256:request",
        lane_id="hard_lane",
        fallback_reason="guardian_approval_required",
    )

    assert receipt["binding_model_id"] == MODEL
    assert receipt["selected_effort"] == "high"
    assert receipt["chatgpt_auth_asserted"] is True
    assert receipt["guardian_approval_required"] is True
    assert receipt["app_server_version_source"] == "verified_pinned_cli"
    assert "raw" not in json.dumps(receipt).lower()


def test_json_line_peer_correlates_response_and_buffers_notifications() -> None:
    transport = FakeLineTransport(
        deque(
            [
                json.dumps({"method": "account/updated", "params": {"type": "chatgpt"}}),
                json.dumps({"id": 1, "result": {"account": {"type": "chatgpt"}}}),
            ]
        )
    )
    peer = app_server.JsonLineAppServerPeer(transport)

    result = peer.request("account/read", {"refreshToken": False})
    notification = peer.wait_for_notification("account/updated", timeout_seconds=1)

    assert result == {"account": {"type": "chatgpt"}}
    assert notification["params"]["type"] == "chatgpt"
    assert json.loads(transport.outbound[0]) == {
        "id": 1,
        "method": "account/read",
        "params": {"refreshToken": False},
    }


def test_json_line_peer_refuses_server_initiated_requests() -> None:
    transport = FakeLineTransport(
        deque(
            [
                json.dumps({"id": 900, "method": "item/tool/call", "params": {"tool": "shell"}}),
                json.dumps({"id": 1, "result": {"ok": True}}),
            ]
        )
    )
    peer = app_server.JsonLineAppServerPeer(transport)

    assert peer.request("model/list", {}) == {"ok": True}
    refusal = json.loads(transport.outbound[1])
    assert refusal["id"] == 900
    assert refusal["error"]["code"] == -32000
    assert "refuses server-initiated requests" in refusal["error"]["message"]


def test_json_line_peer_raises_on_protocol_error_response() -> None:
    transport = FakeLineTransport(
        deque([json.dumps({"id": 1, "error": {"code": -32601, "message": "not found"}})])
    )
    peer = app_server.JsonLineAppServerPeer(transport)

    try:
        peer.request("missing/method", {})
    except app_server.CodexAppServerProtocolError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("protocol errors must fail closed")


def test_managed_proxy_command_uses_subscription_daemon_proxy() -> None:
    assert app_server.managed_proxy_command("/opt/codex") == (
        "/opt/codex",
        "app-server",
        "proxy",
    )


def test_catalog_validation_checks_chatgpt_models_without_starting_turn() -> None:
    peer = FakePeer(_safe_responses())
    client = app_server.CodexAppServerClient(peer)
    bindings = {
        "lanes": {
            "easy_lane": {"transport": "codex_app_server", "model": MODEL},
            "local_safe_lane": {"transport": "ollama", "model": "local-model"},
        }
    }

    receipt = client.validate_binding_catalog(bindings)

    assert receipt == {
        "schema_version": "external_brain_catalog_validation_v1",
        "ok": True,
        "reason": "catalog_bindings_available",
        "chatgpt_auth_asserted": True,
        "bound_models": [MODEL],
        "missing_models": [],
    }
    assert _methods(peer) == ["initialize", "account/read", "model/list"]
    assert "thread/start" not in _methods(peer)
    assert "turn/start" not in _methods(peer)


def test_catalog_validation_refuses_non_chatgpt_account() -> None:
    peer = FakePeer(_safe_responses(account_type="apiKey"))
    client = app_server.CodexAppServerClient(peer)

    receipt = client.validate_binding_catalog(
        {"lanes": {"easy_lane": {"transport": "codex_app_server", "model": MODEL}}}
    )

    assert receipt["ok"] is False
    assert receipt["reason"] == "chatgpt_subscription_required"
    assert _methods(peer) == ["initialize", "account/read"]


def test_dedicated_app_server_command_is_pinned_to_wsl_cli_01445() -> None:
    assert app_server.DEFAULT_CODEX_EXECUTABLE == (
        "/home/openclaw/.nvm/versions/node/v24.14.0/bin/codex"
    )
    assert app_server.REQUIRED_APP_SERVER_VERSION == "0.144.5"
    assert app_server.dedicated_app_server_command() == (
        "/home/openclaw/.nvm/versions/node/v24.14.0/bin/codex",
        "app-server",
    )


def test_preflight_refuses_old_app_server_before_account_or_model_calls() -> None:
    responses = _safe_responses()
    responses["initialize"] = {
        "serverInfo": {"name": "codex-app-server", "version": "0.142.5"}
    }
    peer = FakePeer(responses)
    client = app_server.CodexAppServerClient(peer)

    admission = client.preflight(model=MODEL)

    assert admission.allowed is False
    assert admission.reason == "app_server_version_unsupported"
    assert admission.app_server_version == "0.142.5"
    assert _methods(peer) == ["initialize"]


def test_preflight_accepts_real_01445_user_agent_version_format() -> None:
    responses = _safe_responses()
    responses["initialize"] = {
        "codexHome": "/redacted",
        "platformFamily": "unix",
        "userAgent": "Codex Desktop/0.144.5 (Ubuntu; x86_64) dumb (test; 1.0)",
    }
    peer = FakePeer(responses)
    client = app_server.CodexAppServerClient(peer)

    admission = client.preflight(model=MODEL)

    assert admission.allowed is True
    assert admission.app_server_version == "0.144.5"
    assert admission.app_server_version_source == "initialize_response"
    assert _methods(peer) == [
        "initialize",
        "account/read",
        "account/rateLimits/read",
        "model/list",
    ]


def test_preflight_accepts_missing_initialize_version_only_with_verified_pinned_cli() -> None:
    responses = _safe_responses()
    responses["initialize"] = {"codexHome": "/redacted", "platformFamily": "unix"}
    peer = FakePeer(responses)
    client = app_server.CodexAppServerClient(
        peer,
        trusted_app_server_version="0.144.5",
    )

    admission = client.preflight(model=MODEL)

    assert admission.allowed is True
    assert admission.app_server_version == "0.144.5"
    assert admission.app_server_version_source == "verified_pinned_cli"


def test_preflight_refuses_missing_initialize_version_without_verified_pinned_cli() -> None:
    responses = _safe_responses()
    responses["initialize"] = {"codexHome": "/redacted", "platformFamily": "unix"}
    admission = app_server.CodexAppServerClient(FakePeer(responses)).preflight(model=MODEL)

    assert admission.allowed is False
    assert admission.reason == "app_server_version_unsupported"
    assert admission.app_server_version == "unknown"


def test_verified_pinned_codex_cli_version_requires_exact_output(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        app_server.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="codex-cli 0.144.5\n",
            stderr="",
        ),
    )

    assert app_server.verified_pinned_codex_cli_version() == "0.144.5"


def test_verified_pinned_codex_cli_version_rejects_mismatched_output(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        app_server.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="codex-cli 0.144.6\n",
            stderr="",
        ),
    )

    assert app_server.verified_pinned_codex_cli_version() == ""
