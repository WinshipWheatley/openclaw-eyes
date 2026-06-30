from __future__ import annotations

from types import SimpleNamespace

from scripts import frontdoor_live_probe as probe


def _packet() -> dict:
    return {
        "schema_version": "maestro_context_packet_v0",
        "packet_id": "maestro_context_packet:test",
        "source_surface": "operator_maestro_chat",
        "facts": [
            {
                "fact_id": "identity:operator",
                "topic": "identity",
                "label": "operator",
                "value": "Winship is the human operator.",
                "source_ref": "generated/read_models/operator_truth.json",
            }
        ],
    }


def test_frontdoor_live_probe_activates_profile_and_requires_model(monkeypatch):
    captured: dict = {}

    def fake_protected_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            text="Winship is the human operator.",
            receipt={
                "status": "ANSWER_READY",
                "front_door_profile_used": True,
                "delivered_response_source": "model",
                "model_selected": "qwen3.5:4b",
                "model_call_performed": True,
            },
        )

    monkeypatch.setattr(probe, "protected_generate_with_receipt", fake_protected_generate)

    result = probe.run_probe("Who is the operator?", context_packet=_packet(), agent="niles")

    assert captured["kwargs"]["front_door_profile"] is True
    assert captured["kwargs"]["allow_live_model"] is True
    assert captured["kwargs"]["interactive_timeout_s"] == 44.0
    assert captured["kwargs"]["agent"] == "niles"
    assert result["passed"] is True
    assert result["receipt"]["delivered_response_source"] == "model"


def test_frontdoor_live_probe_fails_when_model_lane_not_delivered(monkeypatch):
    def fake_protected_generate(prompt, **kwargs):
        return SimpleNamespace(
            text="Grounded fallback.",
            receipt={
                "status": "ANSWER_READY",
                "front_door_profile_used": True,
                "delivered_response_source": "grounded_fallback",
                "model_selected": None,
                "model_call_performed": False,
            },
        )

    monkeypatch.setattr(probe, "protected_generate_with_receipt", fake_protected_generate)

    result = probe.run_probe("Who is the operator?", context_packet=_packet(), agent="guardian")

    assert result["passed"] is False
    assert result["failure_reason"] == "frontdoor_model_not_delivered"
