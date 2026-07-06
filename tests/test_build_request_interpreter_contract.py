from __future__ import annotations

import dataclasses

import interpreter_lm


def test_build_request_fast_path_extracts_what_and_requesting_agent_without_lm() -> None:
    def _tripwire(*args, **kwargs):
        raise AssertionError("common build request wording must not call the LM")

    result = interpreter_lm.interpret_operator_message(
        "hey niles can you build me a scene recall helper for the X32",
        protected_generate_fn=_tripwire,
    )

    assert result.route == interpreter_lm.ROUTE_ACTION
    assert result.intent == interpreter_lm.BUILD_REQUEST_INTENT
    assert result.requesting_agent == "niles"
    assert "scene recall helper" in result.what
    assert result.confidence >= interpreter_lm.HIGH_CONFIDENCE_THRESHOLD


def test_interpreter_build_request_fields_do_not_add_authority() -> None:
    field_names = {field.name for field in dataclasses.fields(interpreter_lm.InterpretResult)}

    assert {"what", "requesting_agent"} <= field_names
    assert "authority" not in field_names
    assert "allow" not in field_names
    assert "send" not in field_names
