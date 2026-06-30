from __future__ import annotations

from protected_generate import protected_generate_with_receipt


def test_maestro_system_prompt_includes_perspective_without_new_authority(tmp_path):
    captured: dict[str, str] = {}

    def generator(system_prompt: str, **_kwargs) -> str:
        captured["system_prompt"] = system_prompt
        return "Winship is the human operator."

    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet={
            "facts": [
                {
                    "topic": "identity",
                    "label": "operator",
                    "value": "Winship is the human operator.",
                }
            ]
        },
        generator_fn=generator,
        audit_log_path=tmp_path / "protected_generate_audit.jsonl",
        allow_live_model=False,
    )

    system_prompt = captured["system_prompt"]
    assert outcome.status == "ANSWER_READY"
    assert outcome.receipt["route"] == "injected_generator"
    assert 'First-person words ("I", "me", "my", "mine", "myself") refer only to Maestro.' in system_prompt
    assert 'The human operator is Winship. Address him as "you" or refer to him as "Winship".' in system_prompt
    assert "Maestro must never use first-person words to mean Winship" in system_prompt
    assert "Never claim send/spend/mutation authority." in system_prompt
    assert "DETERMINISTIC PACKET:" in system_prompt


def test_protected_generate_receipt_includes_agent_default_and_override(tmp_path):
    def generator(_system_prompt: str, **_kwargs) -> str:
        return "Grounded answer."

    default_outcome = protected_generate_with_receipt(
        "Say something grounded.",
        context_packet={"facts": [{"topic": "status", "label": "Grounded", "value": "Grounded answer."}]},
        generator_fn=generator,
        audit_log_path=tmp_path / "default.jsonl",
        allow_live_model=False,
    )
    guardian_outcome = protected_generate_with_receipt(
        "Say something grounded.",
        context_packet={"facts": [{"topic": "status", "label": "Grounded", "value": "Grounded answer."}]},
        generator_fn=generator,
        audit_log_path=tmp_path / "guardian.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="guardian",
    )

    assert default_outcome.receipt["agent"] == "maestro"
    assert guardian_outcome.receipt["agent"] == "guardian"
