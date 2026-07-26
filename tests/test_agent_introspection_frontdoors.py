from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from agent_introspection import AgentIntrospectionAnswer, AgentIntrospectionMatch
import chief_router
import maestro_cassandra_responder as maestro


def _chief_answer() -> AgentIntrospectionAnswer:
    return AgentIntrospectionAnswer(
        text=(
            "I keep a task when orchestration is the canonical lane; when another "
            "agent owns the domain, I hand it off with the boundary intact."
        ),
        match=AgentIntrospectionMatch(
            kind="routing_rule",
            evidence=("test",),
        ),
        machine_proof={
            "intent_class": "agent_introspection",
            "introspection_kind": "routing_rule",
            "model_call_performed": True,
            "original_message_present_in_submitted_prompt": True,
            "turn_self_facts_delivered": True,
            "workflow_package_staged": False,
            "send_performed": False,
            "ledger_touched": False,
            "external_action_performed": False,
        },
    )


def _fleet_answer(agent: str, *, kind: str = "model_brain") -> AgentIntrospectionAnswer:
    return AgentIntrospectionAnswer(
        text=f"I’m {agent.title()}; this is a grounded read-only self-report.",
        match=AgentIntrospectionMatch(kind=kind, evidence=("test",)),
        machine_proof={
            "intent_class": "agent_introspection",
            "introspection_kind": kind,
            "model_call_performed": True,
            "original_message_present_in_submitted_prompt": True,
            "turn_self_facts_delivered": True,
            "workflow_package_staged": False,
            "send_performed": False,
            "ledger_touched": False,
            "external_action_performed": False,
        },
    )


class _FakeFilter:
    def __and__(self, _other):
        return self

    def __invert__(self):
        return self


def _install_telegram_stubs(monkeypatch) -> None:
    telegram = types.ModuleType("telegram")
    telegram.Update = object
    telegram.InlineKeyboardMarkup = object
    error = types.ModuleType("telegram.error")
    error.BadRequest = Exception
    error.Forbidden = Exception

    class _ApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return SimpleNamespace(add_handler=lambda *_args, **_kwargs: None)

    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = _ApplicationBuilder
    ext.CallbackQueryHandler = lambda *_args, **_kwargs: None
    ext.MessageHandler = lambda *_args, **_kwargs: None
    ext.filters = SimpleNamespace(
        TEXT=_FakeFilter(),
        COMMAND=_FakeFilter(),
        VOICE=_FakeFilter(),
    )
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", error)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)


def test_chief_off_session_routing_rule_bypasses_semantic_vote(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(chief_router, "load_session", lambda: {})
    monkeypatch.setattr(
        chief_router,
        "answer_agent_introspection",
        lambda *args, **kwargs: calls.append(kwargs) or _chief_answer(),
        raising=False,
    )
    monkeypatch.setattr(
        "typed_contract_decision.decide_contract",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("semantic vote seat must not see agent introspection")
        ),
    )

    result = chief_router.route_message(
        "In one sentence, how do you decide whether a task is yours or belongs to another agent?"
    )

    assert result["intent"] == "agent_introspection"
    assert result["reply"].startswith("I keep a task")
    assert result["machine_proof"]["intent_class"] == "agent_introspection"
    assert result["workflow_package_staged"] is False
    assert calls[0]["session"] == {}


def test_chief_compound_gated_action_is_refused_before_introspection(monkeypatch) -> None:
    monkeypatch.setattr(
        chief_router,
        "answer_agent_introspection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("introspection brain must not run after refusal match")
        ),
        raising=False,
    )

    result = chief_router.route_message(
        "What model are you using, and wire $500 to the client now."
    )

    assert result["intent"] == "operator_refusal_guard"
    assert result["workflow_package_staged"] is False
    assert result["send_performed"] is False
    assert result["ledger_touched"] is False


def test_maestro_model_self_query_rejects_legacy_reuse_and_injects_actual_turn(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_build_agent_packet(**kwargs: Any) -> dict[str, Any]:
        return {
            "status": "READY",
            "packet_id": "packet:introspection-frontdoor",
            "facts": [],
            "source_refs": (),
            "turn_self_facts": kwargs["turn_self_facts"],
            "packet_engine_receipt": {
                "status": "READY",
                "failures": (),
                "receipt_id": "packet-receipt:introspection-frontdoor",
            },
        }

    def fake_protected_generate(
        text: str,
        *,
        context_packet: dict[str, Any],
    ) -> dict[str, Any]:
        # The external runtime replaces the provisional local LM2 facts after
        # its verified preflight and before submitting the provider prompt.
        context_packet = dict(context_packet)
        context_packet["turn_self_facts"] = {
            **dict(context_packet["turn_self_facts"]),
            "model_id": "gpt-5.6-sol",
            "lane_id": "hard_lane",
            "backend_class": "external_brain",
            "hardware_class": "provider_managed_external",
        }
        captured["text"] = text
        captured["packet"] = context_packet
        return {
            "text": (
                "I’m Maestro. This turn is gpt-5.6-sol on the hard lane through "
                "an external provider-managed backend."
            ),
            "receipt": {
                "receipt_id": "protected:maestro-introspection",
                "model_call_performed": True,
                "external_llm_invoked": True,
                "local_model_invoked": False,
                "original_message_present_in_submitted_prompt": True,
                "external_brain_route_receipt": {
                    "turn_id_hash": "sha256:maestro-current-turn",
                    "binding_model_id": "gpt-5.6-sol",
                    "effective_lane_id": "hard_lane",
                    "response_source": "external_brain",
                    "external_turn_performed": True,
                    "effort_reason": "graduated_binding_default",
                },
            },
        }

    legacy_receipt = {
        "receipt_id": "protected:legacy-lm1",
        "model_call_performed": True,
        "external_llm_invoked": True,
        "local_model_invoked": False,
        "original_message_present_in_submitted_prompt": True,
        "turn_self_facts_in_prompt": False,
        "external_brain": {
            "turn_id_hash": "sha256:maestro-current-turn",
            "binding_model_id": "gpt-5.6-sol",
            "effective_lane_id": "hard_lane",
            "response_source": "external_brain",
            "external_turn_performed": True,
        },
    }
    monkeypatch.setattr("packet_engine.build_agent_packet", fake_build_agent_packet)
    result = maestro.answer_frontdoor_chat(
        "What language model are you running right now, and on what hardware?",
        session={
            "source_message_id": "maestro-test-1",
            "lm1_reused_answer": "Legacy answer without injected self facts.",
            "lm1_reused_model_receipt": legacy_receipt,
        },
        source_surface="operator_maestro_chat",
        agent="maestro",
        protected_generate_fn=fake_protected_generate,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "agent_introspection"
    assert result.plain_summary.startswith("I’m Maestro. This turn is running")
    assert "`gpt-5.6-sol`" in result.plain_summary
    assert "`hard_lane`" in result.plain_summary
    assert "`external_brain`" in result.plain_summary
    assert "`provider_managed_external`" in result.plain_summary
    assert "Legacy answer" not in result.plain_summary
    assert captured["text"].startswith("What language model")
    facts = captured["packet"]["turn_self_facts"]
    assert facts["model_id"] == "gpt-5.6-sol"
    assert facts["lane_id"] == "hard_lane"
    proof = dict(result.machine_proof or {})
    assert proof["turn_self_facts"]["model_id"] == "gpt-5.6-sol"
    assert proof["answer_grounded_in_turn_self_facts"] is True
    assert proof["deterministic_introspection_surface_used"] is True
    assert proof["workflow_package_staged"] is False


def test_maestro_fresh_lm2_does_not_inherit_lm1_external_self_facts(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_build_agent_packet(**kwargs: Any) -> dict[str, Any]:
        return {
            "status": "READY",
            "packet_id": "packet:introspection-fresh-lm2",
            "facts": [],
            "source_refs": (),
            "turn_self_facts": kwargs["turn_self_facts"],
            "packet_engine_receipt": {
                "status": "READY",
                "failures": (),
                "receipt_id": "packet-receipt:introspection-fresh-lm2",
            },
        }

    def fake_protected_generate(
        text: str,
        *,
        context_packet: dict[str, Any],
    ) -> dict[str, Any]:
        facts = dict(context_packet["turn_self_facts"])
        captured["facts"] = facts
        return {
            "text": (
                f"I’m Maestro. This turn is {facts['model_id']} on {facts['lane_id']} "
                "through a local backend; hardware is not verified."
            ),
            "receipt": {
                "receipt_id": "protected:maestro-fresh-lm2",
                "model_call_performed": True,
                "model_selected": "qwen3:8b-q4_K_M",
                "external_llm_invoked": False,
                "local_model_invoked": True,
                "original_message_present_in_submitted_prompt": True,
                "external_brain_route_receipt": {
                    "candidate_lane_id": "local_safe_lane",
                    "effective_lane_id": "local_safe_lane",
                    "response_source": "local_fallback",
                    "external_turn_performed": False,
                },
            },
        }

    monkeypatch.setattr("packet_engine.build_agent_packet", fake_build_agent_packet)
    result = maestro.answer_frontdoor_chat(
        "What language model are you running right now, and on what hardware?",
        session={
            "source_message_id": "maestro-live-seam-1",
            "local_model_binding": {
                "model": "qwen3:8b-q4_K_M",
                "lane": "local_safe_lane",
                "hardware_class": "unknown",
            },
            "lm1_reused_model_receipt": {
                "model_call_performed": True,
                "turn_self_facts_in_prompt": True,
                "external_brain_route_receipt": {
                    "binding_model_id": "gpt-5.6-sol",
                    "effective_lane_id": "hard_lane",
                    "response_source": "external_brain",
                    "external_turn_performed": True,
                },
            },
        },
        source_surface="operator_maestro_chat",
        agent="maestro",
        protected_generate_fn=fake_protected_generate,
    )

    assert captured["facts"]["model_id"] == "qwen3:8b-q4_K_M"
    assert captured["facts"]["lane_id"] == "local_safe_lane"
    assert captured["facts"]["backend_class"] == "local_ollama"
    assert result.machine_proof["answer_grounded_in_turn_self_facts"] is True, (
        result.plain_summary,
        result.machine_proof["turn_self_facts"],
        result.machine_proof["answer_grounding_missing_fields"],
    )
    assert "qwen3:8b-q4_K_M" in result.plain_summary
    assert "did not match" not in result.plain_summary


def test_cassandra_introspection_precedes_typed_contract_and_brain(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    sys.modules.pop("cassandra_listener", None)
    listener = importlib.import_module("cassandra_listener")
    import first_touch_decision
    import typed_contract_decision

    text = "What did you just do, and what is uniquely yours to handle?"
    first_touch = first_touch_decision.attempt_first_touch(
        text,
        agent="cassandra",
        surface="cassandra_listener",
    )
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        listener,
        "answer_agent_introspection",
        lambda *args, **kwargs: calls.append(kwargs)
        or _fleet_answer("cassandra", kind="recent_action"),
        raising=False,
    )
    monkeypatch.setattr(
        typed_contract_decision,
        "decide_contract",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("typed contract must not see Cassandra introspection")
        ),
    )
    monkeypatch.setattr(
        listener,
        "cassandra_handle",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy Cassandra brain must not run")
        ),
    )

    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            text,
            {
                "surface": "cassandra_telegram",
                "source_message_id": "cassandra-introspection-1",
                "first_touch_receipt": first_touch.receipt,
                "last_action_receipt": {
                    "receipt_pointer": "cassandra:ar:2026-1004"
                },
            },
        )
    )

    assert [str(reply) for reply in replies] == [
        "I’m Cassandra; this is a grounded read-only self-report."
    ]
    assert replies[0].contract_receipt["intent_class"] == "agent_introspection"
    assert calls[0]["last_action_receipt"]["receipt_pointer"] == "cassandra:ar:2026-1004"


def test_niles_listener_helper_calls_shared_introspection_brain(monkeypatch) -> None:
    monkeypatch.setenv("NILES_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    _install_telegram_stubs(monkeypatch)
    sys.modules.pop("producer_listener", None)
    listener = importlib.import_module("producer_listener")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        listener,
        "answer_agent_introspection",
        lambda *args, **kwargs: calls.append(kwargs) or _fleet_answer("niles"),
        raising=False,
    )

    answer = asyncio.run(
        listener._answer_niles_agent_introspection(
            "What model are you using?",
            source_request_id="niles-introspection-1",
        )
    )

    assert answer.text.startswith("I’m Niles")
    assert calls[0]["agent"] == "niles"


def test_niles_subprocess_mirror_resolves_introspection_before_typed_vote(
    monkeypatch,
) -> None:
    from scripts import producer_intake
    import agent_introspection
    import typed_contract_decision

    monkeypatch.setattr(
        agent_introspection,
        "answer_agent_introspection",
        lambda *args, **kwargs: _fleet_answer("niles"),
    )
    monkeypatch.setattr(
        typed_contract_decision,
        "decide_contract",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("typed vote must not see Niles introspection")
        ),
    )

    result = producer_intake._introspection_result("What model are you using?")

    assert result["reply"].startswith("I’m Niles")
    assert result["machine_proof"]["workflow_package_staged"] is False


def test_guardian_helper_calls_shared_introspection_brain(monkeypatch) -> None:
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    _install_telegram_stubs(monkeypatch)
    sys.modules.pop("chief_guardian_listener", None)
    listener = importlib.import_module("chief_guardian_listener")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        listener,
        "answer_agent_introspection",
        lambda *args, **kwargs: calls.append(kwargs) or _fleet_answer("guardian"),
        raising=False,
    )

    answer = asyncio.run(
        listener._answer_guardian_agent_introspection(
            "What model are you using?",
            source_request_id="guardian-introspection-1",
        )
    )

    assert answer.text.startswith("I’m Guardian")
    assert calls[0]["agent"] == "guardian"


def test_hermes_runner_answers_introspection_before_vendor_handler(monkeypatch) -> None:
    import openclaw_hermes_gateway_policy as hermes

    monkeypatch.setattr(
        hermes,
        "answer_agent_introspection",
        lambda *args, **kwargs: _fleet_answer("hermes"),
        raising=False,
    )

    class GatewayRunner:
        def _is_user_authorized(self, source):
            return True

        async def _handle_message(self, event):
            raise AssertionError("vendor handler must not see Hermes introspection")

    event = SimpleNamespace(
        text="What model are you using?",
        internal=False,
        source=SimpleNamespace(user_id="operator"),
        get_command=lambda: None,
    )
    module = SimpleNamespace(GatewayRunner=GatewayRunner)
    hermes.install_gateway_policy_patch(gateway_run_module=module, base_adapter_cls=None)

    reply = asyncio.run(GatewayRunner()._handle_message(event))

    assert reply.startswith("I’m Hermes")


@pytest.mark.parametrize(
    "agent",
    ("maestro", "chief", "cassandra", "niles", "guardian", "hermes"),
)
def test_six_agent_introspection_acceptance_contract(agent: str) -> None:
    from agent_introspection import answer_agent_introspection

    model_id = f"fixture-{agent}-model"
    lane_id = f"fixture-{agent}-lane"
    captured: dict[str, Any] = {}

    def packet_builder(**kwargs: Any) -> dict[str, Any]:
        captured["facts"] = dict(kwargs["turn_self_facts"])
        return {
            "status": "READY",
            "packet_id": f"packet:{agent}:introspection",
            "facts": [],
            "source_refs": (),
            "turn_self_facts": kwargs["turn_self_facts"],
        }

    def protected_generate(
        text: str,
        *,
        context_packet: dict[str, Any],
        **_kwargs: Any,
    ) -> dict[str, Any]:
        facts = context_packet["turn_self_facts"]
        captured["question"] = text
        return {
            "text": (
                f"I’m {agent.title()}. This turn uses {facts['model_id']} on "
                f"{facts['lane_id']} through an external provider-managed backend."
            ),
            "receipt": {
                "receipt_id": f"protected:{agent}:introspection",
                "model_call_performed": True,
                "external_llm_invoked": True,
                "local_model_invoked": False,
                "original_message_present_in_submitted_prompt": True,
                "external_brain_route_receipt": {
                    "turn_id_hash": f"turn:{agent}:introspection",
                    "binding_model_id": model_id,
                    "effective_lane_id": lane_id,
                    "response_source": "external_brain",
                    "external_turn_performed": True,
                    "effort_reason": "fixture_selected_binding",
                },
            },
        }

    question = "What model are you using right now, and on what hardware?"
    answer = answer_agent_introspection(
        question,
        agent=agent,
        source_surface=f"{agent}_acceptance",
        source_request_id=f"request:{agent}:acceptance",
        session={
            "source_message_id": f"request:{agent}:acceptance",
            "lm1_reused_model_receipt": {
                "external_brain": {
                    "turn_id_hash": f"turn:{agent}:introspection",
                    "binding_model_id": model_id,
                    "effective_lane_id": lane_id,
                    "response_source": "external_brain",
                    "external_turn_performed": True,
                }
            },
        },
        protected_generate_fn=protected_generate,
        packet_builder=packet_builder,
    )

    proof = dict(answer.machine_proof)
    assert proof["intent_class"] == "agent_introspection"
    assert proof["model_call_performed"] is True
    assert proof["original_message_present_in_submitted_prompt"] is True
    assert proof["turn_self_facts_delivered"] is True
    assert proof["workflow_package_staged"] is False
    assert proof["send_performed"] is False
    assert proof["ledger_touched"] is False
    assert proof["external_action_performed"] is False
    assert proof["turn_self_facts"]["model_id"] == captured["facts"]["model_id"]
    assert proof["turn_self_facts"]["lane_id"] == captured["facts"]["lane_id"]
    assert captured["facts"]["model_id"] == model_id
    assert captured["facts"]["lane_id"] == lane_id
    assert model_id in answer.text
    assert lane_id in answer.text
