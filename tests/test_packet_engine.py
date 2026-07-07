from __future__ import annotations

from typing import Any

import pytest


def _base_packet(packet_id: str = "maestro_context_packet:test") -> dict[str, Any]:
    return {
        "schema_version": "maestro_context_packet_v0",
        "packet_id": packet_id,
        "status": "READY",
        "question": "what should I focus on?",
        "facts": [
            {
                "fact_id": "fact:focus",
                "topic": "focus",
                "label": "Focus",
                "value": "Capital Hilton needs review.",
                "source_ref": "generated/read_models/work_board.json",
                "ledger_provenance": {
                    "source_of_truth": "business_ops_ledger",
                    "ledger_path": "/tmp/ledger.sqlite",
                },
                "pii_tier": "PUBLIC",
            }
        ],
        "source_refs": ("generated/read_models/work_board.json",),
        "packet_text": "MAESTRO_CONTEXT_PACKET\n- Focus: Capital Hilton needs review.",
        "machine_proof": {"packet_compiler": "maestro_context_packet.build_maestro_context_packet"},
    }


def _protected_capture(captured: dict[str, Any]):
    def _protected_generate(text: str, *, context_packet: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["text"] = text
        captured["context_packet"] = context_packet
        captured["kwargs"] = kwargs
        return {
            "text": "Packet-grounded answer.",
            "receipt": {
                "receipt_id": "receipt:test",
                "decision": "INJECTED_PROTECTED_GENERATE",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "model_output_delivered": True,
            },
        }

    return _protected_generate


def test_build_agent_packet_adds_distinct_persona_core_and_receipt() -> None:
    import packet_engine

    calls: list[dict[str, Any]] = []

    def builder(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _base_packet()

    packets = {
        agent: packet_engine.build_agent_packet(
            agent=agent,
            question="what should I focus on?",
            question_class="frontdoor_freeform",
            authority={"send_hold": True},
            legacy_builder=builder,
        )
        for agent in ("maestro", "chief", "niles", "guardian")
    }

    assert calls and calls[0]["question"] == "what should I focus on?"
    assert packets["chief"]["persona_core"] != packets["maestro"]["persona_core"]
    assert packets["niles"]["persona_core"]["agent"] == "niles"
    assert packets["guardian"]["persona_core"]["agent"] == "guardian"
    assert "Niles" in packets["niles"]["packet_text"]
    assert "Guardian" in packets["guardian"]["packet_text"]
    assert packets["chief"]["facts"][0]["topic"] == "persona_core"
    receipt = packets["chief"]["packet_engine_receipt"]
    assert receipt["schema_version"] == "packet_engine_receipt_v1"
    assert receipt["agent"] == "chief"
    assert receipt["question_class"] == "frontdoor_freeform"
    assert "persona_core" in receipt["sections"]
    assert receipt["failures"] == []
    assert receipt["build_ms"] >= 0


def test_build_agent_packet_emits_failure_receipt() -> None:
    import packet_engine

    def failing_builder(**_: Any) -> dict[str, Any]:
        raise RuntimeError("packet block failed")

    packet = packet_engine.build_agent_packet(
        agent="guardian",
        question="is this safe?",
        legacy_builder=failing_builder,
    )

    receipt = packet["packet_engine_receipt"]
    assert packet["status"] == "PACKET_ENGINE_BUILD_FAILED"
    assert receipt["agent"] == "guardian"
    assert receipt["status"] == "PACKET_ENGINE_BUILD_FAILED"
    assert receipt["failures"][0]["type"] == "RuntimeError"
    assert "packet block failed" in receipt["failures"][0]["message"]


def test_answer_frontdoor_packet_engine_flag_off_is_legacy_packet_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_context_packet
    from maestro_cassandra_responder import answer_frontdoor_chat

    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "0")
    base_packet = _base_packet("legacy-packet")
    monkeypatch.setattr(maestro_context_packet, "build_maestro_context_packet", lambda **_: dict(base_packet))
    captured: dict[str, Any] = {}

    result = answer_frontdoor_chat(
        "tell me about the current system",
        protected_generate_fn=_protected_capture(captured),
    )

    assert captured["context_packet"] == base_packet
    assert result.machine_proof.get("packet_engine_used") is not True
    assert result.machine_proof.get("packet_engine_fallback_used") is not True


def test_answer_frontdoor_packet_engine_on_injects_persona_for_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_context_packet
    from maestro_cassandra_responder import answer_frontdoor_chat

    monkeypatch.delenv("OPENCLAW_PACKET_ENGINE", raising=False)
    monkeypatch.setattr(maestro_context_packet, "build_maestro_context_packet", lambda **_: _base_packet())
    captured: dict[str, Any] = {}

    result = answer_frontdoor_chat(
        "tell me about the current system",
        agent="niles",
        protected_generate_fn=_protected_capture(captured),
    )

    packet = captured["context_packet"]
    assert packet["persona_core"]["agent"] == "niles"
    assert packet["facts"][0]["topic"] == "persona_core"
    assert "Niles" in packet["packet_text"]
    assert packet["packet_engine_receipt"]["agent"] == "niles"
    assert result.machine_proof["packet_engine_used"] is True
    assert result.machine_proof["packet_engine_receipt_id"].startswith("packet_engine_receipt:")


def test_answer_frontdoor_packet_engine_failure_falls_back_to_legacy_packet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_context_packet
    import packet_engine
    from maestro_cassandra_responder import answer_frontdoor_chat

    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "1")
    base_packet = _base_packet("fallback-packet")
    monkeypatch.setattr(maestro_context_packet, "build_maestro_context_packet", lambda **_: dict(base_packet))

    def boom(**_: Any) -> dict[str, Any]:
        raise RuntimeError("packet engine unavailable")

    monkeypatch.setattr(packet_engine, "build_agent_packet", boom)
    captured: dict[str, Any] = {}

    result = answer_frontdoor_chat(
        "tell me about the current system",
        agent="guardian",
        protected_generate_fn=_protected_capture(captured),
    )

    assert captured["context_packet"] == base_packet
    assert result.machine_proof["packet_engine_used"] is False
    assert result.machine_proof["packet_engine_fallback_used"] is True
    assert result.machine_proof["packet_engine_failure_type"] == "RuntimeError"
