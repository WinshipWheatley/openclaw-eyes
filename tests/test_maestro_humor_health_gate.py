from __future__ import annotations

from typing import Any

import openclaw_request_processor as processor
import operator_surface_guard
from openclaw_request_processor import OpenClawResponseForMac


def _chat_response(
    *,
    proof: dict[str, Any],
    message: str = "The local brain answered cleanly.",
    speaker_ref: str = "maestro",
    detail_extra: dict[str, Any] | None = None,
) -> OpenClawResponseForMac:
    card = {
        "schema_version": "maestro_frontdoor_answer_card_v0",
        "proof": {"proof_refs": [], "machine_proof": dict(proof)},
    }
    detail: dict[str, Any] = {
        "operator_display": {"speaker_ref": speaker_ref},
        "dynamic_card_response": card,
    }
    if detail_extra:
        detail.update(detail_extra)
    return OpenClawResponseForMac(
        source_request_id="req_humor_health",
        source_request_filename="mission_control_req_humor_health.json",
        workflow_ref="general/operator_maestro_chat",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline="Maestro response",
        operator_message=message,
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
        detail_disclosure=detail,
        readback_files=(),
        next_safe_move="Ask a follow-up.",
        proof_to_response=dict(proof),
    )


def _healthy_proof() -> dict[str, Any]:
    return {
        "protected_generate_called": True,
        "model_call_performed": True,
        "local_model_invoked": True,
        "external_llm_invoked": False,
        "protected_generate_route": "local_ollama_frontdoor",
        "protected_generate_model_selected": "qwen3:8b-q4_K_M",
        "model_fallback_reason": "model_ok",
        "model_output_delivered": True,
        "deterministic_fallback_used": False,
    }


def test_healthy_brain_reply_exposes_humor_health_allowed_from_real_receipt() -> None:
    response = _chat_response(proof=_healthy_proof())

    payload, status = processor.build_payloads(response, generated_at="2026-06-29T12:00:00+00:00")

    gate = payload["humor_health_gate"]
    assert gate["health_allows_humor"] is True
    assert gate["model_ok"] is True
    assert gate["deterministic_fallback_used"] is False
    assert gate["subsystem_functioning"] is True
    assert gate["grounding_intact"] is True
    assert gate["agent_humor_rank"] == operator_surface_guard.FUNNY_RANKING["MAESTRO"]
    assert status["machine_proof"]["humor_health_allows_humor"] is True


def test_deterministic_fallback_suppresses_humor_even_for_maestro() -> None:
    proof = {
        **_healthy_proof(),
        "model_call_performed": False,
        "local_model_invoked": False,
        "protected_generate_route": "deterministic_fallback_unreachable",
        "model_fallback_reason": "unreachable",
        "model_output_delivered": False,
        "deterministic_fallback_used": True,
    }
    response = _chat_response(proof=proof)

    payload, status = processor.build_payloads(response, generated_at="2026-06-29T12:00:00+00:00")

    gate = payload["humor_health_gate"]
    assert gate["health_allows_humor"] is False
    assert gate["plain_register_required"] is True
    assert "deterministic_fallback" in gate["suppression_reasons"]
    assert status["machine_proof"]["humor_health_allows_humor"] is False


def test_calendar_auth_failure_is_plain_even_when_chat_surface() -> None:
    proof = {
        **_healthy_proof(),
        "model_call_performed": False,
        "local_model_invoked": False,
        "protected_generate_route": "deterministic_calendar_readback",
        "model_fallback_reason": "never_invoked",
        "model_output_delivered": False,
        "deterministic_fallback_used": True,
    }
    response = _chat_response(
        proof=proof,
        message="I couldn't reach your calendar. Re-run --auth before I can read today's schedule.",
    )

    payload, _status = processor.build_payloads(response, generated_at="2026-06-29T12:00:00+00:00")

    gate = payload["humor_health_gate"]
    assert gate["health_allows_humor"] is False
    assert gate["subsystem_functioning"] is False
    assert "subsystem_degraded" in gate["suppression_reasons"]
    assert gate["plain_register_required"] is True


def test_auto_healed_event_may_allow_fixed_it_wit_only_when_landed() -> None:
    response = _chat_response(
        proof=_healthy_proof(),
        speaker_ref="niles",
        message="The gateway errored, the self-heal landed, and the reply is healthy now.",
        detail_extra={"self_heal_landed": True},
    )

    payload, _status = processor.build_payloads(response, generated_at="2026-06-29T12:00:00+00:00")

    gate = payload["humor_health_gate"]
    assert gate["auto_heal_landed"] is True
    assert gate["health_allows_humor"] is True
    assert gate["agent_humor_rank"] == operator_surface_guard.FUNNY_RANKING["NILES"]


def test_existing_agent_humor_calibration_order_is_reused() -> None:
    ranking = operator_surface_guard.FUNNY_RANKING

    assert ranking["NILES"] > ranking["MAESTRO"]
    assert ranking["MAESTRO"] > ranking["HERMES"]
    assert ranking["HERMES"] > ranking["CASSANDRA"]
    assert ranking["CASSANDRA"] > ranking["CHIEF"]
    assert ranking["CHIEF"] > ranking["GUARDIAN"]
