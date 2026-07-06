from __future__ import annotations

import dataclasses

import interpreter_lm


def test_paid_up_fast_path_recognizes_common_phrasings_without_lm(monkeypatch) -> None:
    def _tripwire(*args, **kwargs):
        raise AssertionError("common paid-up phrasing must not call the LM")

    result = interpreter_lm.interpret_operator_message(
        "St Anne's is all paid up through 2026-06-15",
        protected_generate_fn=_tripwire,
    )

    assert result.route == interpreter_lm.ROUTE_ACTION
    assert result.intent == interpreter_lm.MARK_PAID_UP_INTENT
    assert result.client == "st-annes"
    assert result.as_of == "2026-06-15"
    assert result.scope == "client"
    assert result.partial is False
    assert result.needs_clarification is False


def test_paid_up_everything_scopes_to_all_active_clients() -> None:
    result = interpreter_lm.interpret_operator_message("we are all square on everything as of 2026-06-30")

    assert result.intent == interpreter_lm.MARK_PAID_UP_INTENT
    assert result.scope == "all"
    assert result.client == ""
    assert result.as_of == "2026-06-30"


def test_paid_half_is_partial_not_full_paid_up() -> None:
    result = interpreter_lm.interpret_operator_message("St Anne's paid half on 2026-06-15")

    assert result.intent == interpreter_lm.PARTIAL_PAYMENT_INTENT
    assert result.client == "st-annes"
    assert result.partial is True


def test_ambiguous_paid_up_requires_clarification_not_paid_forever() -> None:
    result = interpreter_lm.interpret_operator_message("all paid up")

    assert result.intent == interpreter_lm.MARK_PAID_UP_INTENT
    assert result.scope == "ambiguous"
    assert result.needs_clarification is True
    assert result.reason == "paid_up_scope_ambiguous"


def test_interpreter_contract_adds_paid_up_fields_without_authority() -> None:
    field_names = {field.name for field in dataclasses.fields(interpreter_lm.InterpretResult)}

    assert {"as_of", "scope", "partial", "needs_clarification"} <= field_names
    assert "authority" not in field_names
    assert "allow" not in field_names
