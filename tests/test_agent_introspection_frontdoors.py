from __future__ import annotations

from typing import Any

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
    assert result.plain_summary.startswith("I’m Maestro. This turn is gpt-5.6-sol")
    assert "Legacy answer" not in result.plain_summary
    assert captured["text"].startswith("What language model")
    facts = captured["packet"]["turn_self_facts"]
    assert facts["model_id"] == "gpt-5.6-sol"
    assert facts["lane_id"] == "hard_lane"
    proof = dict(result.machine_proof or {})
    assert proof["turn_self_facts"]["model_id"] == "gpt-5.6-sol"
    assert proof["answer_grounded_in_turn_self_facts"] is True
    assert proof["workflow_package_staged"] is False
