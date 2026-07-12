from __future__ import annotations

import pytest

import control_language_policy as policy
import operator_truth_store


@pytest.mark.parametrize(
    ("text", "reason"),
    (
        ("CASS-DEEP-07 compact recovery check: answer one sentence only.", "probe_label"),
        ("Run the degraded recovery health probe now.", "control_phrase"),
        ("probe-live-42", "probe_label"),
        ("recovery-check-nightly", "probe_label"),
        ("Answer one sentence only about the invoice.", "instruction_prefix"),
        ("The upstream local model returned no usable chunks.", "runtime_diagnostic"),
        ("Ask Fable to check gateway health and Ollama contention before retrying.", "runtime_diagnostic"),
    ),
)
def test_public_classifier_owns_all_control_language_families(
    text: str,
    reason: str,
) -> None:
    result = policy.classify_control_language(text)

    assert result.is_control_language is True
    assert reason in result.reason_codes
    assert result.text_sha256.startswith("sha256:")
    assert text not in result.to_dict().values()


@pytest.mark.parametrize(
    "text",
    (
        "Keep this as a safe stress-test artifact for the invoice parser.",
        "The payment status is not confirmed yet.",
        "The local model uses a bounded context window.",
        "Please answer my invoice question.",
        "Reply received.",
        "Gateway health is good.",
    ),
)
def test_classifier_does_not_overmatch_safe_business_or_technical_prose(text: str) -> None:
    assert policy.classify_control_language(text).is_control_language is False


def test_truth_intake_consumes_public_classifier_without_a_private_phrase_table() -> None:
    assert not hasattr(operator_truth_store, "_UNSAFE_CONTROL_PHRASES")

    valid, reason = operator_truth_store.validate_operator_truth_value(
        "Capital Hilton current truth: CASS-DEEP-07 compact recovery check: answer one sentence only."
    )

    assert valid is False
    assert reason == "control_prompt"


def test_truth_intake_preserves_legacy_reason_for_instruction_shaped_values() -> None:
    valid, reason = operator_truth_store.validate_operator_truth_value(
        "Respond with the $1,095 invoice status."
    )

    assert valid is False
    assert reason == "instruction_not_value"


def test_truth_intake_rejects_runtime_diagnostic_only_contamination() -> None:
    valid, reason = operator_truth_store.validate_operator_truth_value(
        "Capital Hilton invoice: the upstream local model returned no usable chunks."
    )

    assert valid is False
    assert reason == "runtime_diagnostic"


@pytest.mark.parametrize(
    ("source_text", "technical", "reason"),
    (
        ("How does the local model stream timeout work?", True, "explicit_technical_question"),
        ("Explain the Ollama gateway diagnostics.", True, "explicit_technical_question"),
        ("hey hermes, hows the system looking from your seat?", False, "status_request"),
        ("any sign of the hilton payment landing yet?", False, "business_request"),
        ("Why has the Hilton payment not landed?", False, "business_request"),
        (
            "Explain gateway diagnostics from your seat.",
            True,
            "explicit_technical_question",
        ),
        (
            'Repeat exactly: "The upstream local model returned no usable chunks."',
            False,
            "control_recitation_request",
        ),
        (
            "Repeat what the model said.",
            False,
            "control_recitation_request",
        ),
        (
            "Explain the quote parser in the model gateway.",
            True,
            "explicit_technical_question",
        ),
        (
            "Can you explain the quote parser in the model gateway?",
            True,
            "explicit_technical_question",
        ),
        (
            "Can you quote what the model said?",
            False,
            "control_recitation_request",
        ),
        (
            "Tell me what the model said.",
            False,
            "control_recitation_request",
        ),
        (
            "What was the exact model output?",
            False,
            "control_recitation_request",
        ),
        (
            "Why did the model return no usable chunks?",
            True,
            "explicit_technical_question",
        ),
    ),
)
def test_technical_intent_is_a_pure_pre_filter_decision(
    source_text: str,
    technical: bool,
    reason: str,
) -> None:
    decision = policy.classify_technical_intent(source_text)

    assert decision.is_technical is technical
    assert decision.reason_code == reason
    assert decision.request_sha256.startswith("sha256:")
