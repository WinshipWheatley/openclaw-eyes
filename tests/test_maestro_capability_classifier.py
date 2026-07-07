from __future__ import annotations

import json
from pathlib import Path

import pytest

from contacts_registry import ContactsRegistry
from maestro_cassandra_responder import (
    answer_frontdoor_chat,
    build_truthful_status_capability_answer,
    classify_frontdoor_intent,
    external_llm_invoked_for_result,
)


def _write_read_models(root: Path) -> dict[str, str]:
    root = root / "read_models"
    root.mkdir()
    (root / "openclaw_capability_index.json").write_text(
        json.dumps(
            {
                "generic_capabilities": [
                    {
                        "capability_id": "request_processing",
                        "capability_name": "Bounded request processor",
                        "capability_status": "LIVE_IMPLEMENTED",
                    },
                    {
                        "capability_id": "operator_readback",
                        "capability_name": "Operator status readback",
                        "capability_status": "READ_MODEL_ONLY",
                    },
                    {
                        "capability_id": "browser_control",
                        "capability_name": "Browser control",
                        "capability_status": "FUTURE_GATED",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "agent_presence.json").write_text(
        json.dumps(
            {
                "online_count": 2,
                "next_safe_move": "Review the staged Maestro lane packet before any runtime action.",
                "agents": [
                    {
                        "agent_id": "cassandra",
                        "display_name": "Cassandra",
                        "actual_state": "online",
                        "lane_id": "operator_comms",
                        "role": "operator conversation and guarded readback",
                        "next_safe_move": "No recovery needed.",
                    },
                    {
                        "agent_id": "chief",
                        "display_name": "Chief",
                        "actual_state": "online",
                        "lane_id": "system_orchestration",
                        "role": "coordination and planning visibility",
                        "next_safe_move": "No recovery needed.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "chief_status_rail.json").write_text(
        json.dumps(
            {
                "chief_current_status": "safe_status_read_model_only",
                "chief_current_proven_role": {
                    "role_summary": "Chief is proven for request-only coordination/status visibility.",
                    "runtime_or_send_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return {"read_model_root": str(root)}


@pytest.mark.parametrize(
    ("prompt", "expected_text"),
    [
        ("who are the agents and what does each do?", "Cassandra"),
        ("what is the system-wide next safe move?", "Review the staged Maestro lane packet"),
        ("give me a status readback", "2 agents are online"),
    ],
)
def test_natural_status_capability_phrasings_route_to_truthful_readback(
    tmp_path: Path,
    prompt: str,
    expected_text: str,
) -> None:
    session = _write_read_models(tmp_path)

    result = answer_frontdoor_chat(prompt, session=session)

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "status_capability_readback"
    assert result.allowed_to_call_handle is False
    assert external_llm_invoked_for_result(result) is False
    assert result.machine_proof["status_capability_readback_performed"] is True
    assert result.machine_proof["agent_presence_used"] is True
    assert expected_text in result.plain_summary


def test_conversational_capability_prompt_uses_brain_with_capability_facts(tmp_path: Path) -> None:
    session = _write_read_models(tmp_path)
    captured: dict[str, object] = {}

    def _protected_generate(text: str, *, context_packet: dict[str, object]) -> dict[str, object]:
        captured["text"] = text
        captured["context_packet"] = context_packet
        return {
            "text": "I can help with bounded request processing and operator status readbacks from the live capability index.",
            "receipt": {
                "receipt_id": "receipt_capability_1",
                "audit_ref": "audit_capability_1",
                "decision": "ALLOW_TOKENIZED_MODEL_REASONING",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "route": "local_ollama_frontdoor",
                "model_selected": "qwen3:8b-q4_K_M",
                "deterministic_fallback_used": False,
            },
        }

    result = answer_frontdoor_chat(
        "what can you help me with?",
        session=session,
        protected_generate_fn=_protected_generate,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "status_capability_readback"
    assert result.allowed_to_call_handle is False
    assert result.machine_proof["protected_generate_called"] is True
    assert result.machine_proof["status_capability_facts_injected"] is True
    assert result.machine_proof["model_call_performed"] is True
    assert result.machine_proof["protected_generate_route"] == "local_ollama_frontdoor"
    assert result.machine_proof["protected_generate_model_selected"] == "qwen3:8b-q4_K_M"
    packet = captured["context_packet"]
    assert isinstance(packet, dict)
    packet_text = json.dumps(packet)
    assert "Bounded request processor" in packet_text
    assert "Operator status readback" in packet_text
    assert "Browser control" in packet_text
    assert "live capability index" in result.plain_summary


def test_roster_prompt_lists_live_agents_from_agent_presence(tmp_path: Path) -> None:
    session = _write_read_models(tmp_path)

    result = answer_frontdoor_chat("who are the agents and what does each do?", session=session)

    assert result.status == "ANSWER_READY"
    assert "Agent roster:" in result.plain_summary
    assert "Cassandra (online; operator_comms" in result.plain_summary
    assert "Chief (online; system_orchestration" in result.plain_summary
    assert result.machine_proof["agent_roster_summarized"] is True


def test_people_reference_query_reads_contacts_registry_before_operator_truth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)
    monkeypatch.setenv("OPENCLAW_CONTACTS_DB_PATH", str(contacts_db))

    def _operator_truth_must_not_run(_text: str):
        raise AssertionError("operator truth should not be consulted before registry contacts")

    monkeypatch.setattr("operator_truth_store.find_operator_truth_for_text", _operator_truth_must_not_run)

    result = answer_frontdoor_chat(
        "who do I talk to at St Anne's?",
        session={"operator_truth_store_path": str(tmp_path / "operator_truth_store.json")},
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "people_reference_query"
    assert "Draper Carter" in result.plain_summary
    assert "Glenn Mortoro" in result.plain_summary
    assert "Nancy Pollack" in result.plain_summary
    assert "st-annes" in result.plain_summary
    assert result.machine_proof["contacts_registry_read"] is True
    assert result.machine_proof["contacts_registry_record_found"] is True
    assert result.machine_proof["operator_truth_store_read"] is False
    assert external_llm_invoked_for_result(result) is False


@pytest.mark.parametrize(
    "prompt",
    [
        "reply to that email and send it",
        "give me my morning briefing",
        "send a Gmail to Alex",
        "run the workflow",
    ],
)
def test_send_calendar_briefing_and_action_phrasings_still_route_to_staging(
    tmp_path: Path,
    prompt: str,
) -> None:
    session = _write_read_models(tmp_path)

    result = answer_frontdoor_chat(prompt, session=session)

    assert result.status == "ROUTE_TO_STAGING"
    assert result.allowed_to_call_handle is False
    assert external_llm_invoked_for_result(result) is False
    assert result.machine_proof["email_send_performed"] is False
    assert result.machine_proof["runtime_execution_triggered"] is False


def test_guardian_advisory_payment_question_routes_to_brain_not_staging() -> None:
    intent_class, allowed_to_call_handle, gate_reason = classify_frontdoor_intent(
        "Before I send a payment to a brand-new vendor, what should I check first?"
    )

    assert intent_class == "maestro_brain_freeform"
    assert allowed_to_call_handle is True
    assert gate_reason == ""


def test_real_payment_send_command_still_routes_to_staging() -> None:
    intent_class, allowed_to_call_handle, gate_reason = classify_frontdoor_intent(
        "send a $500 payment to X now"
    )

    assert intent_class in {"send_reply_email_action", "workflow_or_business_action"}
    assert allowed_to_call_handle is False
    assert gate_reason


def test_payment_status_question_with_action_word_routes_to_brain_not_staging() -> None:
    """Task 133: 'did St Anne's pay us?' contains the action-term 'pay' but is a QUESTION
    about status, not an instruction to pay -- must not get hijacked into staging (same bug
    class as 129, in the sibling classify_frontdoor_intent gate)."""
    intent_class, allowed_to_call_handle, gate_reason = classify_frontdoor_intent(
        "did St Anne's pay us?"
    )

    assert intent_class == "maestro_brain_freeform"
    assert allowed_to_call_handle is True
    assert gate_reason == ""


def test_pay_the_invoice_instruction_still_routes_to_staging() -> None:
    """The question-shape exemption must not swallow real instructions that happen to start
    with an interrogative-looking word or otherwise aren't question-shaped."""
    intent_class, allowed_to_call_handle, gate_reason = classify_frontdoor_intent(
        "pay the St Anne's invoice now"
    )

    assert intent_class == "workflow_or_business_action"
    assert allowed_to_call_handle is False
    assert gate_reason == "workflow_or_business_action_routes_to_staging"


def test_calendar_prompt_stays_deterministic_without_brain_or_send(tmp_path: Path) -> None:
    session = _write_read_models(tmp_path)

    result = answer_frontdoor_chat("what's on my calendar today?", session=session)

    assert result.status in {"ANSWER_READY", "ROUTE_TO_STAGING"}
    assert result.allowed_to_call_handle is False
    assert external_llm_invoked_for_result(result) is False
    assert result.machine_proof.get("protected_generate_called") is not True
    assert result.machine_proof["email_send_performed"] is False
    assert result.machine_proof["runtime_execution_triggered"] is False


@pytest.mark.parametrize(
    ("focus", "expected_text"),
    [
        ("status", "2 agents are online"),
        ("capability", "Bounded request processor"),
        ("agent_roster", "Cassandra"),
    ],
)
def test_truthful_status_capability_answer_is_useful_for_each_readback_class(
    tmp_path: Path,
    focus: str,
    expected_text: str,
) -> None:
    session = _write_read_models(tmp_path)

    answer = build_truthful_status_capability_answer(session=session, focus=focus)

    assert expected_text in answer["plain_summary"]
    assert answer["machine_proof"]["readback_focus"] == focus
