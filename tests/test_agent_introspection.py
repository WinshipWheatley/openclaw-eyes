from __future__ import annotations

import pytest

from agent_introspection import (
    classify_agent_introspection,
    inject_turn_self_facts,
    normalize_turn_self_facts,
)


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
