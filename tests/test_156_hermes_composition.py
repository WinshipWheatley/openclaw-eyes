from __future__ import annotations

import asyncio
from collections import OrderedDict
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import MethodType
from types import SimpleNamespace

import pytest

import agent_contract_renderers
import money_truth
import openclaw_hermes_gateway_policy as policy


def _write_money_fixture(root: Path) -> Path:
    target = root / "receivables_month_bounded.json"
    target.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-10T01:23:45+00:00",
                "rows": [
                    {
                        "client_ref": "capital_hilton",
                        "client_display_name": "Capital Hilton",
                        "month": "2026-07",
                        "currency_iso": "USD",
                        "amount_known": False,
                        "open_minor_units": None,
                        "payment_status": "check_unverified",
                        "needs_reconcile": True,
                        "settled_past_no_compound": False,
                    },
                    {
                        "client_ref": "live_arts_md",
                        "client_display_name": "Live Arts MD",
                        "month": "2026-07",
                        "currency_iso": "USD",
                        "amount_known": True,
                        "open_minor_units": 109500,
                        "payment_status": "open",
                        "needs_reconcile": False,
                        "settled_past_no_compound": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return target


def _write_presence_fixture(root: Path) -> Path:
    target = root / "agent_presence.json"
    target.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-10T01:24:00+00:00",
                "agents": [
                    {
                        "agent_id": "hermes",
                        "actual_state": "online",
                        "observed_at": "2026-07-10T01:23:59+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "openclaw_hermes_sidecar.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-10T01:24:00+00:00",
                "current_posture": {"status": "review_ready"},
            }
        ),
        encoding="utf-8",
    )
    return target


@pytest.fixture
def deterministic_read_models(tmp_path, monkeypatch):
    money_path = _write_money_fixture(tmp_path)
    _write_presence_fixture(tmp_path)
    monkeypatch.setattr(money_truth, "DEFAULT_READ_MODEL_PATH", money_path, raising=True)
    original_status = agent_contract_renderers.render_hermes_status
    monkeypatch.setattr(
        agent_contract_renderers,
        "render_hermes_status",
        lambda: original_status(read_model_root=tmp_path),
    )
    monkeypatch.setenv("OPENCLAW_REFUSAL_RECEIPT_PATH", str(tmp_path / "refusals.jsonl"))
    return tmp_path


def _patched_reply(text: str, worker_calls: list[str]) -> str:
    class GatewayRunner:
        def _is_user_authorized(self, source):
            return True

        async def _handle_message(self, event):
            worker_calls.append(event.text)
            return "SIDE-CAR-WORKER-RAN"

    module = SimpleNamespace(GatewayRunner=GatewayRunner)
    event = SimpleNamespace(
        text=text,
        internal=False,
        source=SimpleNamespace(user_id="operator", platform="test"),
        get_command=lambda: None,
    )
    policy.install_gateway_policy_patch(gateway_run_module=module, base_adapter_cls=None)
    return asyncio.run(GatewayRunner()._handle_message(event))


@pytest.mark.parametrize(
    "text",
    (
        "who owes me money right now?",
        "Could you give me the current receivables picture?",
        "Send me a breakdown of who owes me money.",
        "Can you message me the receivables balance?",
    ),
)
def test_money_read_questions_use_one_truth_and_never_run_worker(
    text, deterministic_read_models
) -> None:
    worker_calls: list[str] = []
    reply = _patched_reply(text, worker_calls)

    assert "Live Arts MD" in reply
    assert "$1,095" in reply
    assert "as of 2026-07-10" in reply
    assert "cannot send messages" not in reply.lower()
    assert worker_calls == []


@pytest.mark.parametrize(
    "text",
    (
        "did the Capital Hilton check arrive?",
        "Do you know whether the check from the Capital Hilton has come in yet?",
    ),
)
def test_payment_arrival_questions_answer_bounded_ledger_and_never_run_worker(
    text, deterministic_read_models
) -> None:
    worker_calls: list[str] = []
    reply = _patched_reply(text, worker_calls)

    assert "Receivables (receivables_month_bounded, as of 2026-07-10)" in reply
    assert "Capital Hilton" in reply
    assert "amount not yet confirmed" in reply
    assert "cannot send messages" not in reply.lower()
    assert worker_calls == []


@pytest.mark.parametrize(
    "text",
    (
        "Did you send anything today?",
        "What messages have you sent recently?",
        "Did you pay that vendor already?",
        "Did we send the payment reminder?",
        "Did you send $500 already?",
        "Has the invoice been sent yet?",
        "Did anything go out today?",
        "Was that vendor payment made?",
        "Which emails went out yesterday?",
        "Do you know whether the invoice went out?",
        "Could you tell me if that payment was sent?",
        "Send me the payment history.",
    ),
)
def test_send_history_questions_get_honest_read_only_answer_not_refusal_or_worker(
    text, deterministic_read_models
) -> None:
    worker_calls: list[str] = []
    reply = _patched_reply(text, worker_calls)

    assert "send-history" in reply.lower()
    assert "not claiming" in reply.lower()
    assert "nothing was sent or paid by this read" in reply.lower()
    assert "denied for live action" not in reply.lower()
    assert worker_calls == []


@pytest.mark.parametrize(
    "text",
    (
        "how do I send money safely?",
        "Explain how ACH payments work.",
        "Should I pay this invoice by ACH?",
        "Should I go ahead with the payment?",
    ),
)
def test_advisory_send_safety_question_is_information_not_action(
    text, deterministic_read_models
) -> None:
    worker_calls: list[str] = []
    reply = _patched_reply(text, worker_calls)

    assert "guardian" in reply.lower()
    assert "explicit operator approval" in reply.lower()
    assert "send_hold" in reply.lower()
    assert "nothing was sent or moved" in reply.lower()
    assert "denied for live action" not in reply.lower()
    assert worker_calls == []


@pytest.mark.parametrize(
    "text",
    (
        "Can you send $500 to the vendor?",
        "Would you pay this invoice now?",
        "Could you wire the funds today?",
        "Please move $500 to the vendor.",
        "I want you to move $500 to the vendor.",
        "Initiate the ACH transfer.",
        "Execute the wire today.",
        "Make a payment to the vendor.",
        "Have the invoice paid today.",
        "Could this payment be made today?",
        "I need this invoice paid today.",
        "Go ahead with the payment.",
        "Put the payment through.",
        "I authorize Hermes to transfer $500.",
        "Hermes must pay the vendor now.",
        "Who owes me money right now, and send them a reminder.",
        "Tell me what was sent, then pay the vendor now.",
        "Send me the payment history, then pay the vendor.",
    ),
)
def test_requested_action_including_compound_is_refused_before_information(
    text, deterministic_read_models
) -> None:
    worker_calls: list[str] = []
    reply = _patched_reply(text, worker_calls)

    assert "cannot send messages" in reply.lower()
    assert "move money" in reply.lower()
    assert "send_hold" in reply.lower()
    assert "send-history" not in reply.lower()
    assert "Live Arts MD" not in reply
    assert worker_calls == []


@pytest.mark.parametrize(
    "text",
    (
        "Did you send $500 already, and delete the old logs?",
        "Did you send $500 already, and approve everything?",
    ),
)
def test_historical_money_clause_cannot_hide_another_refusal_class(
    text, deterministic_read_models
) -> None:
    worker_calls: list[str] = []
    reply = _patched_reply(text, worker_calls)

    assert "send-history" not in reply.lower()
    assert "send_hold" in reply.lower()
    if "delete" in text:
        assert "deletion gate" in reply.lower()
        assert "no deletion" in reply.lower()
    else:
        assert "approval gate" in reply.lower()
        assert "no approval" in reply.lower()
    assert worker_calls == []


@pytest.mark.parametrize(
    "text",
    (
        "status?",
        "How are things on your end right now?",
    ),
)
def test_task151_hermes_status_adapter_uses_presence_and_bypasses_worker(
    text, deterministic_read_models
) -> None:
    worker_calls: list[str] = []
    reply = _patched_reply(text, worker_calls)

    assert "Hermes runtime: online" in reply
    assert "observed 2026-07-10T01:23:59+00:00" in reply
    assert "Advisory snapshot: review ready" in reply
    assert "no model or action ran" in reply
    assert worker_calls == []


def _load_installed_sidecar_gateway():
    configured = os.environ.get("HERMES_COMPOSITION_SIDECAR_ROOT", "").strip()
    if not configured:
        pytest.skip("set HERMES_COMPOSITION_SIDECAR_ROOT for installed-composition acceptance")
    root = Path(configured).resolve()
    run_path = (root / "gateway" / "run.py").resolve()
    previous_gateway_modules = {
        name: module
        for name, module in tuple(sys.modules.items())
        if name == "gateway" or name.startswith("gateway.")
    }
    sys.path.insert(0, str(root))
    try:
        for name in tuple(sys.modules):
            if name == "gateway" or name.startswith("gateway."):
                sys.modules.pop(name, None)
        module = importlib.import_module("gateway.run")
    finally:
        if sys.path[0] == str(root):
            sys.path.pop(0)
    assert Path(module.__file__).resolve() == run_path
    return module, previous_gateway_modules


def _restore_gateway_modules(previous_gateway_modules) -> None:
    for name in tuple(sys.modules):
        if name == "gateway" or name.startswith("gateway."):
            sys.modules.pop(name, None)
    sys.modules.update(previous_gateway_modules)


def test_installed_wrapper_plus_actual_sidecar_intercepts_contracts_before_worker(
    deterministic_read_models,
) -> None:
    gateway_run, previous_gateway_modules = _load_installed_sidecar_gateway()
    try:
        policy.install_gateway_policy_patch(gateway_run_module=gateway_run, base_adapter_cls=None)
        runner = object.__new__(gateway_run.GatewayRunner)
        runner._is_user_authorized = lambda source: True

        def composed_reply(text: str) -> str:
            event = SimpleNamespace(
                text=text,
                internal=False,
                source=SimpleNamespace(user_id="operator", platform="composition-test"),
                get_command=lambda: None,
            )
            return asyncio.run(runner._handle_message(event))

        money_reply = composed_reply("who owes me money right now?")
        status_reply = composed_reply("status?")
        action_reply = composed_reply("Would you pay this invoice now?")

        assert "$1,095" in money_reply
        assert "Live Arts MD" in money_reply
        assert "cannot send messages" not in money_reply.lower()
        assert "Hermes runtime: online" in status_reply
        assert "no model or action ran" in status_reply
        assert "cannot send messages" in action_reply.lower()
        assert "send_hold" in action_reply.lower()
    finally:
        _restore_gateway_modules(previous_gateway_modules)


@pytest.mark.asyncio
async def test_installed_wrapper_cancels_actual_sidecar_and_retains_session_lease(
    monkeypatch,
    tmp_path,
) -> None:
    gateway_run, previous_gateway_modules = _load_installed_sidecar_gateway()
    try:
        from gateway.config import GatewayConfig, Platform, PlatformConfig, StreamingConfig
        from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult
        from gateway.session import SessionSource
        import run_agent

        class CaptureAdapter(BasePlatformAdapter):
            def __init__(self):
                super().__init__(
                    PlatformConfig(enabled=True, token="***"),
                    Platform.DISCORD,
                )

            async def connect(self):
                return True

            async def disconnect(self):
                return None

            async def send(self, chat_id, content, reply_to=None, metadata=None):
                return SendResult(success=True, message_id="m-1")

            async def get_chat_info(self, chat_id):
                return {"id": chat_id}

        class BlockingAgent:
            started = threading.Event()
            release = threading.Event()
            interrupted = threading.Event()
            starts = 0
            instances = 0

            def __init__(self, **kwargs):
                type(self).instances += 1
                self.tools = []
                self.model = kwargs.get("model", "test-model")
                self.session_id = kwargs.get("session_id", "session-1")
                self.was_interrupted = False

            def get_activity_summary(self):
                return {
                    "seconds_since_activity": 0.0,
                    "last_activity_desc": "blocked provider",
                    "current_tool": None,
                    "api_call_count": 1,
                    "max_iterations": 2,
                }

            def interrupt(self, _reason):
                self.was_interrupted = True
                type(self).interrupted.set()

            def run_conversation(self, *_args, **_kwargs):
                type(self).starts += 1
                if self.was_interrupted:
                    return {
                        "final_response": "reused interrupted agent",
                        "messages": [],
                        "api_calls": 0,
                    }
                type(self).started.set()
                type(self).release.wait(timeout=10)
                return {
                    "final_response": "late result",
                    "messages": [],
                    "api_calls": 1,
                }

        BlockingAgent.started.clear()
        BlockingAgent.release.clear()
        BlockingAgent.interrupted.clear()
        BlockingAgent.starts = 0
        BlockingAgent.instances = 0

        monkeypatch.setattr(run_agent, "AIAgent", BlockingAgent)
        monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
        monkeypatch.setattr(
            gateway_run,
            "_load_gateway_config",
            lambda: {
                "display": {
                    "tool_progress": "off",
                    "interim_assistant_messages": False,
                }
            },
        )
        monkeypatch.setattr(
            gateway_run,
            "_resolve_runtime_agent_kwargs",
            lambda: {"api_key": "fake"},
        )
        monkeypatch.setenv("HERMES_OPENCLAW_GATEWAY_REPLY_TIMEOUT_SECONDS", "0.2")
        monkeypatch.setenv("HERMES_AGENT_TIMEOUT", "0")
        monkeypatch.setenv("HERMES_AGENT_TIMEOUT_WARNING", "0")
        monkeypatch.setenv("HERMES_AGENT_NOTIFY_INTERVAL", "0")

        adapter = CaptureAdapter()
        runner = object.__new__(gateway_run.GatewayRunner)
        runner.config = GatewayConfig(
            platforms={
                Platform.DISCORD: PlatformConfig(enabled=True, token="***"),
            },
            streaming=StreamingConfig(enabled=False),
        )
        runner.adapters = {Platform.DISCORD: adapter}
        runner._voice_mode = {}
        runner._prefill_messages = []
        runner._ephemeral_system_prompt = ""
        runner._reasoning_config = None
        runner._service_tier = None
        runner._provider_routing = {}
        runner._fallback_model = None
        runner._session_db = None
        runner._running_agents = {}
        runner._running_agents_ts = {}
        runner._running_agent_generations = {}
        runner._executor_draining_generations = {}
        runner._executor_drain_tasks = set()
        runner._session_run_generation = {}
        runner._pending_messages = {}
        runner._pending_approvals = {}
        runner._pending_clarifies = {}
        runner._update_prompt_pending = {}
        runner._busy_ack_ts = {}
        runner._draining = False
        runner._agent_cache = OrderedDict()
        runner._agent_cache_lock = threading.Lock()
        runner.hooks = SimpleNamespace(loaded_hooks=False)
        runner._is_user_authorized = lambda source: True

        async def run_actual_worker(self, event, source, session_key, run_generation):
            result = await self._run_agent(
                message=event.text,
                context_prompt="",
                history=[],
                source=source,
                session_id="session-1",
                session_key=session_key,
                run_generation=run_generation,
            )
            return result["final_response"]

        runner._handle_message_with_agent = MethodType(run_actual_worker, runner)
        policy.install_gateway_policy_patch(
            gateway_run_module=gateway_run,
            base_adapter_cls=None,
        )

        source = SessionSource(
            platform=Platform.DISCORD,
            chat_id="same-chat",
            chat_type="dm",
            user_id="operator",
        )

        def event(text: str) -> MessageEvent:
            return MessageEvent(
                text=text,
                message_type=MessageType.TEXT,
                source=source,
            )

        started = time.monotonic()
        timeout_reply = await runner._handle_message(
            event("Explain the difference between TCP and UDP in one paragraph.")
        )
        elapsed = time.monotonic() - started
        session_key = runner._session_key_for_source(source)

        assert "Hermes could not produce a fresh answer" in timeout_reply
        assert elapsed < 1.25
        assert BlockingAgent.started.is_set()
        assert BlockingAgent.interrupted.is_set()
        assert BlockingAgent.starts == 1
        assert runner._is_executor_draining(session_key)

        busy_reply = await runner._handle_message(
            event("Explain the difference between HTTP and HTTPS in one paragraph.")
        )
        assert "still stopping" in busy_reply.lower()
        assert BlockingAgent.starts == 1

        BlockingAgent.release.set()
        for _ in range(100):
            if not runner._is_executor_draining(session_key):
                break
            await asyncio.sleep(0.01)
        assert not runner._is_executor_draining(session_key)

        retry_reply = await runner._handle_message(
            event("Explain the difference between RAM and disk storage in one paragraph.")
        )
        assert retry_reply == "late result"
        assert BlockingAgent.starts == 2
        assert BlockingAgent.instances == 2
    finally:
        _restore_gateway_modules(previous_gateway_modules)
