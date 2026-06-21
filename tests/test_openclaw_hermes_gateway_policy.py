from __future__ import annotations

import asyncio
from types import SimpleNamespace

import openclaw_hermes_gateway_policy as policy


def test_route_request_denies_without_skill_lookup_or_dispatch() -> None:
    reply = policy.truthful_reply_for_text("route this to Cassandra")

    assert reply is not None
    lowered = reply.lower()
    assert "cannot route this to cassandra" in lowered
    assert "no route receipt was written" in lowered
    assert "no message was sent" in lowered
    assert "skill" not in lowered
    assert "send_hold" in lowered


def test_route_inventory_does_not_advertise_helper_tools_as_routes() -> None:
    reply = policy.truthful_reply_for_text("what can you route to?")

    assert reply is not None
    assert "Real agent bridges available to Hermes here: none proven." in reply
    assert "not dispatch routes" in reply
    assert "helper tools" not in reply.lower()
    assert "enqueue" in reply.lower()


def test_send_and_money_actions_are_denied_for_live_action() -> None:
    reply = policy.truthful_reply_for_text("send the payment confirmation and wire the money")

    assert reply is not None
    lowered = reply.lower()
    assert "cannot send messages" in lowered
    assert "move money" in lowered
    assert "denied for live action" in lowered
    assert "no external send" in lowered
    assert "agent dispatch" in lowered


def test_non_agent_route_target_with_money_falls_to_money_denial() -> None:
    reply = policy.truthful_reply_for_text("forward this to accounting and pay the vendor")

    assert reply is not None
    lowered = reply.lower()
    assert "cannot send messages" in lowered
    assert "move money" in lowered
    assert "denied for live action" in lowered
    assert "cannot route this to accounting" not in lowered
    assert "agent dispatch" in lowered


def test_route_target_resolves_only_canonical_agents() -> None:
    assert policy._route_target("forward this to accounting and pay the vendor") == ""
    assert policy._route_target("route this to Cassandra") == "cassandra"


def test_non_agent_route_target_is_not_treated_as_agent_route() -> None:
    reply = policy.truthful_reply_for_text("route this to accounting")

    assert reply is not None
    lowered = reply.lower()
    assert "cannot route this to accounting" in lowered
    assert "not a canonical openclaw agent route" in lowered
    assert "no route receipt was written" in lowered


def test_sanitizer_removes_runtime_leaks() -> None:
    sanitized = policy.sanitize_gateway_response(
        "Non-canonical advisory output: Interrupting current task (iteration 7/90)\n"
        "Actual answer stays.\n"
        "loop 3/90"
    )

    assert sanitized == "Actual answer stays."


def test_runner_patch_intercepts_authorized_plain_messages_before_original_handler() -> None:
    class GatewayRunner:
        def _is_user_authorized(self, source):
            return True

        async def _handle_message(self, event):
            raise AssertionError("Hermes agent path must not run for route prompts")

    event = SimpleNamespace(
        text="route this to Cassandra",
        internal=False,
        source=SimpleNamespace(user_id="operator"),
        get_command=lambda: None,
    )
    module = SimpleNamespace(GatewayRunner=GatewayRunner)

    assert policy.install_gateway_policy_patch(gateway_run_module=module, base_adapter_cls=None) is True
    reply = asyncio.run(GatewayRunner()._handle_message(event))

    assert "cannot route this to cassandra" in reply.lower()


def test_runner_patch_preserves_unauthorized_flow() -> None:
    class GatewayRunner:
        def _is_user_authorized(self, source):
            return False

        async def _handle_message(self, event):
            return "original unauthorized handling"

    event = SimpleNamespace(
        text="route this to Cassandra",
        internal=False,
        source=SimpleNamespace(user_id="stranger"),
        get_command=lambda: None,
    )
    module = SimpleNamespace(GatewayRunner=GatewayRunner)

    policy.install_gateway_policy_patch(gateway_run_module=module, base_adapter_cls=None)

    assert asyncio.run(GatewayRunner()._handle_message(event)) == "original unauthorized handling"


def test_send_patch_sanitizes_busy_status_before_delivery() -> None:
    class BaseAdapter:
        async def _send_with_retry(self, *args, **kwargs):
            self.sent_args = args
            self.sent_kwargs = kwargs
            return "sent"

    module = SimpleNamespace(GatewayRunner=type("GatewayRunner", (), {"_handle_message": lambda self, event: None}))
    policy.install_gateway_policy_patch(gateway_run_module=module, base_adapter_cls=BaseAdapter)
    adapter = BaseAdapter()

    result = asyncio.run(
        adapter._send_with_retry(
            chat_id="chat",
            content="Still working (iteration 12/90).\nNon-canonical advisory output: OK",
        )
    )

    assert result == "sent"
    assert adapter.sent_kwargs["content"] == "Still working.\nOK"
