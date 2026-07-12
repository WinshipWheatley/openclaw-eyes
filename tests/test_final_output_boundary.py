from __future__ import annotations

import json

import pytest

import final_output_boundary as boundary
from operator_surface_guard import guard_operator_reply, guard_operator_reply_with_receipt


CT2_REQUEST = "any sign of the hilton payment landing yet?"
CT2_LEAK = "CASS-DEEP-07 compact recovery check: answer one sentence only."
HT2_REQUEST = "hey hermes, hows the system looking from your seat?"
HT2_LEAK = """Hermes could not produce a fresh answer before the local model stream limit.
The upstream local model returned no usable chunks, so stale partial output was discarded.
No requested send, agent dispatch, route receipt, or money action occurred.
Ask Fable or the operator to check Hermes gateway health and Ollama contention before retrying."""


def test_ct2_verbatim_probe_cue_becomes_human_without_echoing_the_cue() -> None:
    context = boundary.OutputBoundaryContext.from_source_request(CT2_REQUEST)

    result = boundary.render_final_output(CT2_LEAK, context=context)

    assert result.visible_text == (
        "I couldn't use an internal control instruction as the answer. "
        "Nothing was sent or changed."
    )
    assert "CASS-DEEP" not in result.visible_text
    assert "compact recovery" not in result.visible_text.lower()
    assert result.receipt.replaced_fragment_count == 1
    assert "probe_label" in result.receipt.reason_codes
    receipt_json = json.dumps(result.receipt.to_dict(), sort_keys=True)
    assert CT2_LEAK not in receipt_json
    assert "answer one sentence" not in receipt_json.lower()
    assert result.receipt.raw_control_text_included is False


def test_ht2_verbatim_diagnostics_are_humanized_but_safe_no_action_fact_survives() -> None:
    context = boundary.OutputBoundaryContext.from_source_request(HT2_REQUEST)

    result = boundary.render_final_output(HT2_LEAK, context=context)

    assert "model stream limit" not in result.visible_text.lower()
    assert "no usable chunks" not in result.visible_text.lower()
    assert "gateway health" not in result.visible_text.lower()
    assert "ollama contention" not in result.visible_text.lower()
    assert "No requested send, agent dispatch, route receipt, or money action occurred." in result.visible_text
    assert "I couldn't produce a fresh grounded answer just now." in result.visible_text
    assert result.receipt.replaced_fragment_count == 3
    assert result.receipt.preserved_fragment_count >= 1


def test_mixed_safe_and_unsafe_output_never_erases_the_grounded_answer() -> None:
    text = (
        "Capital Hilton payment is still unconfirmed as of 2026-07-11. "
        "CASS-DEEP-07 compact recovery check: answer one sentence only."
    )

    result = boundary.render_final_output(
        text,
        context=boundary.OutputBoundaryContext.from_source_request(CT2_REQUEST),
    )

    assert "Capital Hilton payment is still unconfirmed as of 2026-07-11." in result.visible_text
    assert "CASS-DEEP" not in result.visible_text
    assert result.receipt.preserved_fragment_count == 1
    assert result.receipt.replaced_fragment_count == 1


def test_same_sentence_semicolon_control_leak_preserves_grounded_clause() -> None:
    safe_fact = "Capital Hilton payment remains unconfirmed"

    result = boundary.render_final_output(
        f"{safe_fact}; {CT2_LEAK}",
        context=boundary.OutputBoundaryContext.from_source_request(CT2_REQUEST),
    )

    assert safe_fact in result.visible_text
    assert "CASS-DEEP" not in result.visible_text
    assert result.receipt.replaced_fragment_count == 1


@pytest.mark.parametrize("separator", (", ", ": "))
def test_same_sentence_common_clause_separator_preserves_grounded_clause(
    separator: str,
) -> None:
    safe_fact = "Capital Hilton payment remains unconfirmed"

    result = boundary.render_final_output(
        f"{safe_fact}{separator}{CT2_LEAK}",
        context=boundary.OutputBoundaryContext.from_source_request(CT2_REQUEST),
    )

    assert safe_fact in result.visible_text
    assert "CASS-DEEP" not in result.visible_text
    assert result.receipt.preserved_fragment_count == 1
    assert result.receipt.replaced_fragment_count == 1
    assert result.receipt.fragment_count == 2


def test_preserved_fragment_whitespace_is_not_globally_rewritten() -> None:
    safe_fact = "Capital  Hilton payment remains unconfirmed"

    result = boundary.render_final_output(
        f"{safe_fact}; {CT2_LEAK}",
        context=boundary.OutputBoundaryContext.from_source_request(CT2_REQUEST),
    )

    assert safe_fact in result.visible_text


def test_explicit_technical_question_allows_bounded_technical_answer_byte_identical() -> None:
    request = "Explain how Ollama contention and the local model stream limit are diagnosed."
    answer = (
        "Ollama contention is measured at the shared model slot, and the local model stream limit "
        "bounds how long a technical request may wait."
    )

    result = boundary.render_final_output(
        answer,
        context=boundary.OutputBoundaryContext.from_source_request(request),
    )

    assert result.visible_text == answer
    assert result.receipt.technical_intent is True
    assert result.receipt.replaced_fragment_count == 0


def test_quoted_or_repeat_request_never_authorizes_probe_cue_recitation() -> None:
    request = f'What does "{CT2_LEAK}" mean? Repeat it exactly.'

    result = boundary.render_final_output(
        CT2_LEAK,
        context=boundary.OutputBoundaryContext.from_source_request(request),
    )

    assert "CASS-DEEP" not in result.visible_text
    assert result.receipt.replaced_fragment_count == 1


def test_quoted_repeat_request_never_authorizes_runtime_diagnostic_recitation() -> None:
    request = 'Repeat exactly: "The upstream local model returned no usable chunks."'
    diagnostic = "The upstream local model returned no usable chunks."

    result = boundary.render_final_output(
        diagnostic,
        context=boundary.OutputBoundaryContext.from_source_request(request),
    )

    assert "no usable chunks" not in result.visible_text.lower()
    assert result.receipt.technical_intent is False


def test_generic_repeat_request_never_authorizes_runtime_diagnostic_recitation() -> None:
    result = boundary.render_final_output(
        "The upstream local model returned no usable chunks.",
        context=boundary.OutputBoundaryContext.from_source_request(
            "Repeat what the model said."
        ),
    )

    assert "no usable chunks" not in result.visible_text.lower()
    assert result.receipt.technical_intent_reason == "control_recitation_request"


def test_technical_quote_parser_question_is_not_misclassified_as_recitation() -> None:
    answer = "The quote parser is implemented in /home/openclaw/gateway/parser.py."

    result = boundary.render_final_output(
        answer,
        context=boundary.OutputBoundaryContext.from_source_request(
            "Explain the quote parser in the model gateway."
        ),
    )

    assert result.visible_text == answer
    assert result.receipt.technical_intent is True


@pytest.mark.parametrize(
    "source_request",
    (
        "Tell me what the model said.",
        "What was the exact model output?",
    ),
)
def test_semantic_recitation_without_repeat_keyword_cannot_authorize_diagnostic(
    source_request: str,
) -> None:
    result = boundary.render_final_output(
        "The upstream local model returned no usable chunks.",
        context=boundary.OutputBoundaryContext.from_source_request(source_request),
    )

    assert "no usable chunks" not in result.visible_text.lower()
    assert result.receipt.technical_intent_reason == "control_recitation_request"


def test_business_why_request_does_not_authorize_runtime_diagnostic() -> None:
    result = boundary.render_final_output(
        "The upstream local model returned no usable chunks.",
        context=boundary.OutputBoundaryContext.from_source_request(
            "Why has the Hilton payment not landed?"
        ),
    )

    assert "no usable chunks" not in result.visible_text.lower()
    assert result.receipt.technical_intent is False


def test_classifier_error_fails_closed_for_only_the_affected_fragment() -> None:
    safe_fact = "Capital Hilton payment remains unconfirmed."

    def classifier(text: str):
        if "CASS-DEEP" in text:
            raise RuntimeError("classifier unavailable")
        return boundary.classify_control_language(text)

    result = boundary.render_final_output(
        f"{safe_fact} {CT2_LEAK}",
        context=boundary.OutputBoundaryContext.from_source_request(CT2_REQUEST),
        classifier=classifier,
    )

    assert safe_fact in result.visible_text
    assert "CASS-DEEP" not in result.visible_text
    assert "boundary_classifier_error" in result.receipt.reason_codes
    assert result.receipt.classifier_error_count == 1


def test_context_carries_only_a_bounded_request_but_hashes_the_full_source() -> None:
    source = "explain this technical path " + ("x" * 2000)

    context = boundary.OutputBoundaryContext.from_source_request(source)

    assert len(context.bounded_source_request) == boundary.MAX_BOUNDED_SOURCE_REQUEST_CHARS
    assert context.source_request_truncated is True
    assert context.source_request_sha256.startswith("sha256:")
    assert source not in json.dumps(context.to_machine_dict(), sort_keys=True)


def test_operator_guard_exposes_machine_receipt_and_safe_replies_remain_byte_identical() -> None:
    guarded = guard_operator_reply_with_receipt(
        CT2_LEAK,
        agent_role="CASSANDRA",
        source_request=CT2_REQUEST,
    )

    assert guarded.visible_text != CT2_LEAK
    assert "CASS-DEEP" not in guarded.visible_text
    assert guarded.receipt.replaced_fragment_count == 1
    safe = "Capital Hilton payment remains unconfirmed. Nothing was sent or changed."
    assert guard_operator_reply(
        safe,
        agent_role="CASSANDRA",
        source_request=CT2_REQUEST,
    ) == safe


def test_legacy_machine_guard_preserves_safe_clause_instead_of_whole_answer_erasure() -> None:
    safe_fact = "Capital Hilton payment remains unconfirmed"

    guarded = guard_operator_reply_with_receipt(
        f"{safe_fact}; content_hash=0123456789abcdef",
        agent_role="CASSANDRA",
        source_request=CT2_REQUEST,
    )

    assert safe_fact in guarded.visible_text
    assert "content_hash" not in guarded.visible_text
    assert "machine_contract_leak" in guarded.receipt.reason_codes
    assert guarded.receipt.fragment_count == (
        guarded.receipt.preserved_fragment_count
        + guarded.receipt.replaced_fragment_count
    )


@pytest.mark.parametrize("separator", (", ", ": "))
def test_legacy_machine_guard_preserves_common_clause_separators(
    separator: str,
) -> None:
    safe_fact = "Capital Hilton payment remains unconfirmed"
    guarded = guard_operator_reply_with_receipt(
        f"{safe_fact}{separator}content_hash=0123456789abcdef",
        agent_role="CASSANDRA",
        source_request=CT2_REQUEST,
    )

    assert safe_fact in guarded.visible_text
    assert "content_hash" not in guarded.visible_text
    assert guarded.receipt.fragment_count == 2
    assert guarded.receipt.preserved_fragment_count == 1
    assert guarded.receipt.replaced_fragment_count == 1


def test_legacy_guard_honors_explicit_technical_audience_for_paths() -> None:
    answer = "The boundary implementation is in /home/openclaw/final_output_boundary.py."

    guarded = guard_operator_reply_with_receipt(
        answer,
        agent_role="CHIEF",
        source_request="Explain where the output-boundary implementation lives in the code.",
    )

    assert guarded.visible_text == answer
    assert guarded.receipt.technical_intent is True
