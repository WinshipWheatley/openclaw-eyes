from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from agent_introspection import (
    AgentIntrospectionAnswer,
    answer_agent_introspection,
    classify_agent_introspection,
    inject_turn_self_facts,
    normalize_turn_self_facts,
)
from codex_app_server_client import CodexTurnResult, SubscriptionAdmission
import external_brain_runtime
from packet_engine import build_agent_packet


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (
            "What language model are you running right now, and on what hardware?",
            "model_brain",
        ),
        ("Which brain answered that last turn?", "model_brain"),
        ("What model did you use for your last response?", "model_brain"),
        ("What did you just do?", "recent_action"),
        ("What was your last action receipt?", "recent_action"),
        (
            "In one sentence, how do you decide whether a task is yours or belongs to another agent?",
            "routing_rule",
        ),
        ("What's your handoff rule?", "routing_rule"),
        ("What do you think the next step is?", "advisory"),
        ("Would you like to review that next?", "advisory"),
        ("What's your own service status?", "status_health"),
        ("What do you have in your packet about St Anne's?", "knowledge_packet"),
        ("What can you do?", "capability"),
    ],
)
def test_classifies_introspection_paraphrases(text: str, kind: str) -> None:
    match = classify_agent_introspection(text, addressed_agent="maestro")

    assert match is not None
    assert match.kind == kind
    assert match.evidence


@pytest.mark.parametrize(
    "text",
    [
        "what can you do with invoices?",
        "can you send this invoice?",
        "what is the invoice status?",
        "route this to Cassandra",
        "what model should we use to price an invoice?",
        "tell Chief to post the receivable",
        "Hey Chief, what's your status right now?",
        "what's your status?",
    ],
)
def test_precision_bias_leaves_business_questions_alone(text: str) -> None:
    assert classify_agent_introspection(text, addressed_agent="maestro") is None


def test_normalizes_external_turn_without_claiming_local_gpu() -> None:
    facts = normalize_turn_self_facts(
        agent="maestro",
        source_request_id="maestro_telegram_1901_69c3190870b8",
        route_receipt={
            "turn_id_hash": "sha256:8b1e704009fa4078",
            "binding_model_id": "gpt-5.6-sol",
            "effective_lane_id": "hard_lane",
            "response_source": "external_brain",
            "external_turn_performed": True,
            "effort_reason": "graduated_binding_default",
        },
    )

    assert facts["schema_version"] == "turn_self_facts_v1"
    assert facts["agent"] == "maestro"
    assert facts["source_request_id"] == "maestro_telegram_1901_69c3190870b8"
    assert facts["turn_receipt_id"] == "sha256:8b1e704009fa4078"
    assert facts["model_id"] == "gpt-5.6-sol"
    assert facts["lane_id"] == "hard_lane"
    assert facts["backend_class"] == "external_brain"
    assert facts["hardware_class"] == "provider_managed_external"
    assert facts["selection_reason"] == "graduated_binding_default"
    assert "last_action_receipt_ptr" in facts["unknown_fields"]
    assert "hardware_class" in facts["known_fields"]


def test_route_receipt_outranks_configured_session_default() -> None:
    facts = normalize_turn_self_facts(
        agent="maestro",
        session={
            "source_request_id": "session-default",
            "local_model_binding": {
                "model": "qwen3:8b",
                "lane": "local_safe_lane",
                "binding_reason": "configured_default",
            },
        },
        route_receipt={
            "request_hash": "sha256:current-request",
            "turn_id_hash": "sha256:current-turn",
            "binding_model_id": "gpt-5.6-sol",
            "effective_lane_id": "hard_lane",
            "external_turn_performed": True,
        },
    )

    assert facts["source_request_id"] == "sha256:current-request"
    assert facts["turn_receipt_id"] == "sha256:current-turn"
    assert facts["model_id"] == "gpt-5.6-sol"
    assert facts["lane_id"] == "hard_lane"


def test_current_turn_receipt_is_distinct_from_last_action_history() -> None:
    facts = normalize_turn_self_facts(
        agent="cassandra",
        route_receipt={
            "receipt_id": "protected:current-turn",
            "model_id": "qwen3:8b",
            "lane_id": "local_safe_lane",
            "local_model_invoked": True,
        },
        last_action_receipt={"receipt_pointer": "cassandra:ar:2026-1004"},
    )

    assert facts["turn_receipt_id"] == "protected:current-turn"
    assert facts["last_action_receipt_ptr"] == "cassandra:ar:2026-1004"
    assert facts["turn_receipt_id"] != facts["last_action_receipt_ptr"]


def test_missing_machine_truth_stays_explicitly_unknown() -> None:
    facts = normalize_turn_self_facts(agent="guardian")

    assert facts["agent"] == "guardian"
    assert facts["model_id"] == ""
    assert facts["lane_id"] == ""
    assert facts["backend_class"] == "unknown"
    assert facts["hardware_class"] == "unknown"
    assert "model_id" in facts["unknown_fields"]
    assert "lane_id" in facts["unknown_fields"]
    assert "hardware_class" in facts["unknown_fields"]


def test_inject_turn_self_facts_adds_closed_packet_section() -> None:
    facts = normalize_turn_self_facts(
        agent="chief",
        source_request_id="chief-test-1",
        route_receipt={
            "receipt_id": "protected:chief-test-1",
            "model_id": "qwen3:8b",
            "lane_id": "local_safe_lane",
            "local_model_invoked": True,
            "selection_reason": "interactive_binding",
        },
    )

    result = inject_turn_self_facts(
        {
            "status": "READY",
            "facts": [],
            "source_refs": ("source:base",),
            "packet_text": "BASE PACKET",
        },
        facts,
    )

    assert result["turn_self_facts"] == facts
    assert result["facts"][-1]["topic"] == "agent_introspection"
    assert result["facts"][-1]["source_ref"] == "machine_proof:turn_self_facts_v1"
    assert "TURN SELF FACTS" in result["packet_text"]
    assert "qwen3:8b" in result["packet_text"]
    assert "machine_proof:turn_self_facts_v1" in result["source_refs"]


def test_packet_engine_delivers_turn_self_facts() -> None:
    facts = normalize_turn_self_facts(
        agent="chief",
        source_request_id="chief-test-1",
        route_receipt={
            "receipt_id": "protected:chief-test-1",
            "model_id": "qwen3:8b",
            "lane_id": "local_safe_lane",
            "local_model_invoked": True,
            "selection_reason": "interactive_binding",
        },
    )

    packet = build_agent_packet(
        agent="chief",
        question="How do you decide whether a task is yours?",
        question_class="agent_introspection",
        turn_self_facts=facts,
        legacy_builder=lambda **_: {
            "status": "READY",
            "facts": [],
            "source_refs": [],
            "packet_text": "base",
        },
    )

    assert packet["turn_self_facts"]["model_id"] == "qwen3:8b"
    assert "turn_self_facts" in packet["packet_engine_receipt"]["sections"]
    assert packet["machine_proof"]["turn_self_facts_delivered"] is True
    assert "TURN SELF FACTS" in packet["packet_text"]


@dataclass
class _ExternalClient:
    admission: SubscriptionAdmission
    turns: list[dict[str, Any]] = field(default_factory=list)

    def preflight(self, **_kwargs: Any) -> SubscriptionAdmission:
        return self.admission

    def run_read_only_turn(self, **kwargs: Any) -> CodexTurnResult:
        self.turns.append(kwargs)
        return CodexTurnResult(
            text="I am running through gpt-5.6-sol on the external hard lane.",
            thread_id_hash="sha256:thread",
            turn_id_hash="sha256:turn",
            packet_critique={
                "summary": "Self facts were present.",
                "quality_score": 100,
                "missing": [],
                "noise": [],
                "mis_scoped": [],
                "improvement_items": [],
                "grounded_in_turn": ["turn self facts"],
            },
        )


def _public_metadata() -> dict[str, Any]:
    return {
        "classification": "public",
        "original_pii_tier": "PUBLIC",
        "cloud_allowed": True,
        "local_required": False,
        "tokenization_applied": False,
        "package_minimized": True,
        "raw_values_included": False,
        "secrets_present": False,
    }


def test_external_preflight_identity_is_injected_before_prompt_submission() -> None:
    client = _ExternalClient(
        SubscriptionAdmission(
            True,
            "subscription_headroom_ok",
            "gpt-5.6-sol",
            effort_level="high",
            account_type="chatgpt",
            used_percent=20,
        )
    )

    result = external_brain_runtime.run_external_brain_request(
        raw_operator_prompt="What model are you running right now?",
        context_aid={"facts": ["bounded"]},
        privacy_metadata=_public_metadata(),
        task_type="architecture policy synthesis",
        role="maestro",
        client=client,
        local_fallback=lambda: "local fallback",
        cwd="/home/openclaw",
        activation_enabled=True,
        packet_quality_db_path=None,
    )

    prompt_facts = client.turns[0]["context_aid"]["turn_self_facts"]
    assert prompt_facts["agent"] == "maestro"
    assert prompt_facts["model_id"] == "gpt-5.6-sol"
    assert prompt_facts["lane_id"] == "hard_lane"
    assert prompt_facts["backend_class"] == "external_brain"
    assert prompt_facts["hardware_class"] == "provider_managed_external"
    assert prompt_facts["turn_receipt_id"] == result.receipt["request_hash"]
    assert result.receipt["turn_self_facts"] == prompt_facts
    assert result.receipt["turn_self_facts_in_prompt"] is True
    assert result.receipt["turn_id_hash"] == "sha256:turn"
    assert client.turns[0]["context_aid"]["facts"] == ["bounded"]


def test_external_preflight_model_mismatch_fails_closed_before_turn() -> None:
    client = _ExternalClient(
        SubscriptionAdmission(
            True,
            "subscription_headroom_ok",
            "unexpected-model",
            effort_level="high",
            account_type="chatgpt",
            used_percent=20,
        )
    )

    result = external_brain_runtime.run_external_brain_request(
        raw_operator_prompt="What model are you running right now?",
        context_aid={},
        privacy_metadata=_public_metadata(),
        task_type="architecture policy synthesis",
        role="maestro",
        client=client,
        local_fallback=lambda: "local fallback",
        cwd="/home/openclaw",
        activation_enabled=True,
        packet_quality_db_path=None,
    )

    assert result.source == "local_fallback"
    assert result.receipt["fallback_reason"] == "external_preflight_model_mismatch"
    assert client.turns == []


def _ready_packet(**_kwargs: Any) -> dict[str, Any]:
    return {
        "status": "READY",
        "packet_id": "packet:introspection-test",
        "facts": [],
        "source_refs": (),
        "packet_text": "Chief persona and bounded context.",
        "machine_proof": {},
    }


def test_shared_brain_uses_original_question_and_self_facts_without_action() -> None:
    captured: dict[str, Any] = {}

    def fake_generate(
        text: str,
        *,
        context_packet: dict[str, Any],
        agent: str,
        model_selected: str,
    ) -> dict[str, Any]:
        captured.update(
            text=text,
            packet=context_packet,
            agent=agent,
            model=model_selected,
        )
        return {
            "text": (
                "I’m Chief; I keep work when it matches my orchestration lane and "
                "hand it off when another agent has the canonical owner."
            ),
            "receipt": {
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "original_message_present_in_submitted_prompt": True,
                "original_message_sha256": "sha256:test",
                "receipt_id": "protected:test",
                "model_selected": "qwen3:8b-q4_K_M",
                "lane_id": "local_safe_lane",
            },
        }

    answer = answer_agent_introspection(
        "How do you decide whether a task is yours?",
        agent="chief",
        source_surface="chief_router",
        source_request_id="chief-test-1",
        session={
            "local_model_binding": {
                "schema_version": "local_model_binding_v2",
                "binding_id": "binding:test",
                "model": "qwen3:8b-q4_K_M",
                "keep_alive": "30m",
                "num_ctx": 2048,
                "num_gpu": 999,
                "num_batch": 128,
            }
        },
        protected_generate_fn=fake_generate,
        packet_builder=_ready_packet,
    )

    assert isinstance(answer, AgentIntrospectionAnswer)
    assert answer.match.kind == "routing_rule"
    assert captured["text"] == "How do you decide whether a task is yours?"
    assert captured["packet"]["turn_self_facts"]["model_id"] == "qwen3:8b-q4_K_M"
    assert answer.machine_proof["intent_class"] == "agent_introspection"
    assert answer.machine_proof["model_call_performed"] is True
    assert answer.machine_proof["original_message_present_in_submitted_prompt"] is True
    assert answer.machine_proof["workflow_package_staged"] is False
    assert answer.machine_proof["send_performed"] is False
    assert answer.machine_proof["ledger_touched"] is False
    assert answer.machine_proof["external_action_performed"] is False


def test_shared_brain_packet_failure_does_not_call_model() -> None:
    model_calls: list[str] = []

    answer = answer_agent_introspection(
        "What model are you running?",
        agent="maestro",
        source_surface="operator_maestro_chat",
        protected_generate_fn=lambda *args, **kwargs: model_calls.append("called"),
        packet_builder=lambda **_kwargs: {
            "status": "PACKET_ENGINE_BUILD_FAILED",
            "packet_id": "packet:failed",
            "facts": [],
            "source_refs": (),
            "packet_text": "",
            "machine_proof": {"packet_engine_failure": True},
        },
    )

    assert model_calls == []
    assert answer.machine_proof["model_call_performed"] is False
    assert answer.machine_proof["turn_self_facts_delivered"] is False
    assert "won't guess" in answer.text


def test_model_answer_that_disagrees_with_receipt_is_rejected() -> None:
    def mismatched_generate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "text": "I’m running qwen3:8b on the local GPU.",
            "receipt": {
                "receipt_id": "protected:mismatch",
                "model_call_performed": True,
                "external_llm_invoked": True,
                "local_model_invoked": False,
                "original_message_present_in_submitted_prompt": True,
                "external_brain_route_receipt": {
                    "turn_id_hash": "sha256:external-turn",
                    "binding_model_id": "gpt-5.6-sol",
                    "effective_lane_id": "hard_lane",
                    "response_source": "external_brain",
                    "external_turn_performed": True,
                },
            },
        }

    answer = answer_agent_introspection(
        "What model are you running right now, and on what hardware?",
        agent="maestro",
        source_surface="operator_maestro_chat",
        protected_generate_fn=mismatched_generate,
        packet_builder=_ready_packet,
    )

    assert answer.machine_proof["answer_grounded_in_turn_self_facts"] is False
    assert answer.machine_proof["answer_grounding_missing_fields"] == (
        "model_id",
        "lane_id",
        "backend_class",
    )
    assert "qwen3:8b" not in answer.text
    assert "did not match this turn's machine proof" in answer.text


def test_genuinely_unknown_self_facts_preserve_honest_unknown() -> None:
    def honest_unknown_generate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "text": (
                "I don’t have a verified model identifier, lane, or hardware fact "
                "for this turn, so I won’t guess."
            ),
            "receipt": {
                "receipt_id": "protected:unknown",
                "model_call_performed": True,
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "original_message_present_in_submitted_prompt": True,
            },
        }

    answer = answer_agent_introspection(
        "What model are you running right now, and on what hardware?",
        agent="guardian",
        source_surface="guardian_listener",
        protected_generate_fn=honest_unknown_generate,
        packet_builder=_ready_packet,
    )

    assert answer.machine_proof["answer_grounded_in_turn_self_facts"] is True
    assert answer.machine_proof["answer_grounding_missing_fields"] == ()
    assert "won’t guess" in answer.text
