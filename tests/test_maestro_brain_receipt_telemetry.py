from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import openclaw_request_processor as processor
from openclaw_request_processor import OpenClawResponseForMac
from maestro_cassandra_responder import _protected_generate_receipt_machine_proof, answer_frontdoor_chat


def _write_minimal_read_models(root: Path) -> dict[str, str]:
    read_models = root / "read_models"
    read_models.mkdir()
    (read_models / "openclaw_capability_index.json").write_text(
        json.dumps(
            {
                "generic_capabilities": [
                    {
                        "capability_id": "request_processing",
                        "capability_name": "Bounded request processor",
                        "capability_status": "LIVE_IMPLEMENTED",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (read_models / "agent_presence.json").write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "agent_id": "maestro",
                        "display_name": "Maestro",
                        "actual_state": "online",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (read_models / "chief_status_rail.json").write_text(
        json.dumps({"chief_current_status": "safe_status_read_model_only"}),
        encoding="utf-8",
    )
    return {"read_model_root": str(read_models)}


def _chat_response_with_proof(proof: dict[str, Any]) -> OpenClawResponseForMac:
    card = {
        "schema_version": "maestro_frontdoor_answer_card_v0",
        "proof": {"proof_refs": [], "machine_proof": dict(proof)},
    }
    return OpenClawResponseForMac(
        source_request_id="req_brain_1",
        source_request_filename="mission_control_req_brain_1.json",
        workflow_ref="general/operator_maestro_chat",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline="Brain answered.",
        operator_message="Brain answered.",
        what_happened=("The protected Maestro generation path answered.",),
        why_it_happened="The Maestro intent gate allowed the prompt.",
        how_to_fix="No fix is needed.",
        visible_cards=(card,),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={"dynamic_card_response": card},
        readback_files=(),
        next_safe_move="Ask a follow-up.",
        proof_to_response=dict(proof),
    )


def test_protected_generate_receipt_fields_survive_responder_machine_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    import maestro_context_packet

    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_: {
            "packet_id": "packet_receipt_truth",
            "source_refs": ("generated/read_models/openclaw_capability_index.json",),
            "facts": [
                {
                    "topic": "capability",
                    "label": "Truthful capability posture",
                    "value": "Bounded request processor is live.",
                    "source_ref": "generated/read_models/openclaw_capability_index.json",
                    "pii_tier": "PUBLIC",
                }
            ],
        },
    )

    def _protected_generate(text: str, *, context_packet: dict[str, object]) -> dict[str, object]:
        return {
            "text": "The local brain answered.",
            "receipt": {
                "receipt_id": "receipt_truth_1",
                "audit_ref": "audit_truth_1",
                "decision": "ALLOW_TOKENIZED_MODEL_REASONING",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "route": "local_ollama_frontdoor",
                "model_selected": "qwen3:8b-q4_K_M",
                "model_output_delivered": True,
                "deterministic_fallback_used": False,
            },
        }

    result = answer_frontdoor_chat(
        "tell me about the current system",
        protected_generate_fn=_protected_generate,
    )

    assert result.machine_proof["model_call_performed"] is True
    assert result.machine_proof["local_model_invoked"] is True
    assert result.machine_proof["protected_generate_route"] == "local_ollama_frontdoor"
    assert result.machine_proof["protected_generate_model_selected"] == "qwen3:8b-q4_K_M"
    assert result.machine_proof["deterministic_fallback_used"] is False


def test_missing_protected_generate_model_call_key_defaults_false() -> None:
    proof = _protected_generate_receipt_machine_proof({"route": "local_ollama_frontdoor"})

    assert proof["model_call_performed"] is False


def test_status_capability_brain_path_passes_real_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    import maestro_context_packet
    import protected_generate

    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_: {
            "packet_id": "packet_cassandra_capability",
            "source_refs": ("generated/read_models/openclaw_capability_index.json",),
            "facts": [],
        },
    )
    captured: dict[str, str] = {}

    def fake_protected_generate(text: str, *, context_packet: dict[str, object], agent: str) -> dict[str, object]:
        captured["agent"] = agent
        return {
            "text": f"{agent} can answer from current capability facts.",
            "receipt": {
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "route": "local_ollama_frontdoor",
                "model_selected": "qwen3.5:4b",
                "model_output_delivered": True,
            },
        }

    monkeypatch.setattr(protected_generate, "protected_generate_with_receipt", fake_protected_generate)

    result = answer_frontdoor_chat(
        "what can you help me with?",
        agent="cassandra",
        source_surface="operator_cassandra_chat",
    )

    assert captured["agent"] == "cassandra"
    assert "cassandra can answer" in result.plain_summary.lower()
    assert result.machine_proof["protected_generate_called"] is True


def test_non_maestro_status_capability_fallback_does_not_say_maestro_packet() -> None:
    def fake_fallback(text: str, *, context_packet: dict[str, object]) -> dict[str, object]:
        return {
            "text": "I don't have that in the current Maestro packet.",
            "receipt": {
                "model_call_performed": False,
                "local_model_invoked": False,
                "external_llm_invoked": False,
                "route": "deterministic_fallback",
                "deterministic_fallback_used": True,
            },
        }

    result = answer_frontdoor_chat(
        "what can you help me with?",
        protected_generate_fn=fake_fallback,
        agent="cassandra",
        source_surface="operator_cassandra_chat",
    )

    assert "Maestro packet" not in result.plain_summary
    assert "Cassandra" in result.plain_summary
    assert result.machine_proof["model_call_performed"] is False


def test_processor_model_fields_mirror_brain_receipt_not_voice_map() -> None:
    proof = {
        "protected_generate_called": True,
        "model_call_performed": True,
        "local_model_invoked": True,
        "external_llm_invoked": False,
        "protected_generate_route": "local_ollama_frontdoor",
        "protected_generate_model_selected": "qwen3:8b-q4_K_M",
        "protected_generate_decision": "ALLOW_TOKENIZED_MODEL_REASONING",
        "deterministic_fallback_used": False,
    }
    response = _chat_response_with_proof(proof)

    payload, status = processor.build_payloads(response, generated_at="2026-06-29T12:00:00+00:00")

    assert payload["selected_model_backend"] == "LOCAL_OLLAMA"
    assert payload["selected_model_id"] == "qwen3:8b-q4_K_M"
    assert payload["selected_worker_type"] == "local_ollama_frontdoor"
    assert "brain answered" in payload["model_selection_reason"].lower()
    assert payload["machine_proof"]["model_call_performed"] is True
    assert payload["machine_proof"]["local_model_call_performed"] is True
    assert payload["machine_proof"]["protected_generate_route"] == "local_ollama_frontdoor"
    assert status["machine_proof"]["model_call_performed"] is True


def test_processor_keeps_deterministic_label_when_receipt_says_no_model_call() -> None:
    proof = {
        "protected_generate_called": True,
        "model_call_performed": False,
        "local_model_invoked": False,
        "external_llm_invoked": False,
        "protected_generate_route": "deterministic_fallback_unreachable",
        "protected_generate_model_selected": "qwen3:8b-q4_K_M",
        "deterministic_fallback_used": True,
    }
    response = _chat_response_with_proof(proof)

    payload, status = processor.build_payloads(response, generated_at="2026-06-29T12:00:00+00:00")

    assert payload["selected_model_backend"] == "NONE_DETERMINISTIC"
    assert payload["selected_model_id"] == "qwen3:8b-q4_K_M"
    assert payload["selected_worker_type"] == "deterministic_fallback_unreachable"
    assert "deterministic fallback" in payload["model_selection_reason"].lower()
    assert payload["machine_proof"]["model_call_performed"] is False
    assert status["machine_proof"]["model_call_performed"] is False


def test_controller_lm2_reused_proof_keeps_reuse_telemetry() -> None:
    proof = {
        "candidate_source": "lm2_room_backed_worker_structured_output_retry",
        "selected_model_backend": "LOCAL_OLLAMA",
        "model_call_performed": False,
        "headline": "Reused verified proof",
        "body": "Existing room-backed worker proof was reused.",
    }
    response = _chat_response_with_proof(proof)
    response = replace(response, request_type="OPERATOR_CONTROLLER_EVENT_REQUEST")

    payload, status = processor.build_payloads(response, generated_at="2026-06-29T12:00:00+00:00")

    assert payload["selected_model_backend"] == "LOCAL_OLLAMA"
    assert payload["selected_worker_type"] == "LOCAL_OLLAMA_REUSED_PROOF_RESPONSE"
    assert "reused" in payload["model_selection_reason"].lower()
    assert payload["machine_proof"]["model_call_performed"] is False
    assert status["machine_proof"]["model_call_performed"] is False
