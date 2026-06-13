import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_gemini_form_adapter as adapter
import openclaw_lm_consult_spine as spine


FIXED_NOW = "2026-06-12T12:00:00+00:00"
TEST_MODEL = "gemini-3.5-flash"


@pytest.fixture(autouse=True)
def _clear_gemini_env(monkeypatch):
    for name in (
        "OPENCLAW_ENABLE_LIVE_GEMINI_FORM",
        "OPENCLAW_GEMINI_MODEL",
        "OPENCLAW_GEMINI_FORM_MODEL",
        *adapter.GEMINI_CREDENTIAL_ENVS,
    ):
        monkeypatch.delenv(name, raising=False)


def _enable_gemini(monkeypatch, *, generic_model: str = TEST_MODEL, form_model: str | None = None) -> None:
    monkeypatch.setenv("OPENCLAW_ENABLE_LIVE_GEMINI_FORM", "1")
    monkeypatch.setenv("OPENCLAW_GEMINI_MODEL", generic_model)
    if form_model is not None:
        monkeypatch.setenv("OPENCLAW_GEMINI_FORM_MODEL", form_model)
    monkeypatch.setenv("GEMINI_API_KEY", "test-redacted")


def _package() -> dict:
    return {
        "schema_version": "DATA_ROOM_FORM_FILL_PACKAGE_V0",
        "package_id": "data_room_form_fill_package:test",
        "created_at_utc": FIXED_NOW,
        "review_session_id": "data_room_review:test",
        "current_question_id": "review_question:payment",
        "current_question_index": 3,
        "total_questions": 23,
        "form_title": "OpenClaw Data Room setup form",
        "form_questions": [
            {
                "question_id": "review_question:payment",
                "category": "payment privacy",
                "question_text": "What payment details are safe by default?",
                "context_summary": "Payment defaults need review.",
                "source_record_ids": ["privacy:payment_policy"],
                "proposed_options": ["manual approval", "defer"],
                "risk_if_wrong": "Could expose private payment instructions.",
                "recommended_action": "defer",
                "answer_status": "unanswered",
            }
        ],
        "answered_questions": [],
        "skipped_questions": [],
        "deferred_questions": [],
        "unresolved_questions": [
            {
                "question_id": "review_question:payment",
                "source_record_ids": ["privacy:payment_policy"],
            }
        ],
        "current_question": {
            "question_id": "review_question:payment",
            "category": "payment privacy",
            "question_text": "What payment details are safe by default?",
            "source_record_ids": ["privacy:payment_policy"],
        },
        "prior_chat_log_summary": "2 answered, 0 skipped, 0 deferred, 21 remaining.",
        "recent_turns": [],
        "coach_pack_summary": {
            "question_id": "review_question:payment",
            "recommended_default": "Keep private details manual-only.",
            "professional_review_flags": [],
        },
        "safety_boundaries": {
            "chatgpt_mutates_openclaw": False,
            "confirmed_reference_data_created": False,
            "runtime_policy_changed": False,
            "external_action_performed": False,
        },
        "expected_output_schema": {},
        "done_criteria": {"done": False},
    }


def _safe_result(request: dict, *, intent: str = "explain", reply: str = "I have the form and can help.") -> dict:
    return {
        "schema_version": adapter.TURN_RESULT_SCHEMA_VERSION,
        "request_id": request["request_id"],
        "form_session_id": request["form_session_id"],
        "review_session_id": request["review_session_id"],
        "question_id": request["current_question_id"],
        "assistant_reply": reply,
        "operator_intent": intent,
        "proposed_answer": {
            "plain_english": "",
            "normalized_decision": "",
            "confidence": "low",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "requires_winship_confirmation": False,
        "confirmed_by_winship": False,
        "should_record_now": False,
        "next_question_id": "",
        "chat_log_summary_update": "Ready to help with the current question.",
        "done_criteria_met": False,
        "facts_used": ["review_question:payment", "privacy:payment_policy"],
        "codex_finalization_recommended": False,
        "safety_flags": dict(adapter.SAFE_TURN_SAFETY_FLAGS),
    }


def _provider_with_result(result_factory, capture: dict | None = None):
    def fake_provider(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
        if capture is not None:
            capture["request_payload"] = request_payload
            capture["request_body"] = request_body
            capture["model_label"] = model_label
            capture["timeout_seconds"] = timeout_seconds
        result = result_factory(request_payload)
        output_text = result if isinstance(result, str) else json.dumps(result)
        return {"candidates": [{"content": {"parts": [{"text": output_text}]}}]}

    return fake_provider


def test_adapter_disabled_blocks_before_provider(monkeypatch):
    monkeypatch.delenv("OPENCLAW_ENABLE_LIVE_GEMINI_FORM", raising=False)
    monkeypatch.setenv("OPENCLAW_GEMINI_MODEL", TEST_MODEL)
    monkeypatch.setenv("GEMINI_API_KEY", "test-redacted")
    called = False

    def provider(**kwargs):
        nonlocal called
        called = True
        return {}

    availability = adapter.is_live_gemini_form_available()
    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(_package(), "hello", "", provider=provider, created_at_utc=FIXED_NOW)

    assert availability["available"] is False
    assert availability["provider_enabled"] is False
    assert exc.value.reason == "blocked_provider_disabled"
    assert called is False


def test_missing_credential_blocks_without_printing_secret(monkeypatch, capsys):
    monkeypatch.setenv("OPENCLAW_ENABLE_LIVE_GEMINI_FORM", "1")
    monkeypatch.setenv("OPENCLAW_GEMINI_MODEL", TEST_MODEL)
    for name in adapter.GEMINI_CREDENTIAL_ENVS:
        monkeypatch.delenv(name, raising=False)

    availability = adapter.is_live_gemini_form_available()
    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            "hello",
            "",
            provider=_provider_with_result(_safe_result),
            created_at_utc=FIXED_NOW,
        )

    captured = capsys.readouterr()
    assert availability["credential_present"] is False
    assert exc.value.reason == "blocked_operator_config_required"
    assert captured.out == ""
    assert captured.err == ""


def test_fake_provider_valid_schema_returns_structured_result_and_no_tools(monkeypatch):
    _enable_gemini(monkeypatch)
    capture: dict = {}

    result = adapter.call_gemini_data_room_form_turn(
        _package(),
        adapter.READINESS_PROMPT,
        "",
        provider=_provider_with_result(_safe_result, capture),
        created_at_utc=FIXED_NOW,
    )

    assert result["assistant_reply"] == "I have the form and can help."
    assert result["confirmed_by_winship"] is False
    assert result["should_record_now"] is False
    assert "tools" not in capture["request_body"]
    assert "toolConfig" not in capture["request_body"]
    assert capture["request_body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert capture["request_body"]["generationConfig"]["responseSchema"]["type"] == "object"
    assert capture["model_label"] == TEST_MODEL


def test_schema_error_fallback_valid_json_is_accepted_after_validation(monkeypatch):
    _enable_gemini(monkeypatch)
    calls: list[dict] = []

    def provider(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
        calls.append(
            {
                "request_payload": request_payload,
                "request_body": request_body,
                "model_label": model_label,
                "timeout_seconds": timeout_seconds,
            }
        )
        if len(calls) == 1:
            raise spine.LMConsultError(
                "blocked_structured_output_schema",
                validation={
                    "provider_status_code": 400,
                    "provider_error_code": "INVALID_ARGUMENT",
                    "provider_error_message_redacted": "Unknown name responseSchema at generationConfig.",
                    "provider_error_category": "structured_output_schema",
                    "structured_output_enabled": True,
                    "request_body_logged": False,
                    "credential_value_logged": False,
                },
            )
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(_safe_result(request_payload))}]}}]}

    result = adapter.call_gemini_data_room_form_turn(
        _package(),
        adapter.READINESS_PROMPT,
        "",
        provider=provider,
        created_at_utc=FIXED_NOW,
    )

    assert result["assistant_reply"] == "I have the form and can help."
    assert result["_structured_output_mode"] == "json_prompt_fallback"
    assert len(calls) == 2
    assert "responseSchema" in calls[0]["request_body"]["generationConfig"]
    assert "responseSchema" not in calls[1]["request_body"]["generationConfig"]
    assert "tools" not in calls[1]["request_body"]


def test_schema_error_fallback_invalid_json_is_rejected(monkeypatch):
    _enable_gemini(monkeypatch)
    calls: list[dict] = []

    def provider(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
        calls.append(
            {
                "request_payload": request_payload,
                "request_body": request_body,
                "model_label": model_label,
                "timeout_seconds": timeout_seconds,
            }
        )
        if len(calls) == 1:
            raise spine.LMConsultError(
                "blocked_structured_output_schema",
                validation={
                    "provider_status_code": 400,
                    "provider_error_category": "structured_output_schema",
                    "structured_output_enabled": True,
                    "request_body_logged": False,
                    "credential_value_logged": False,
                },
            )
        bad = _safe_result(request_payload)
        bad["schema_version"] = "WRONG_SCHEMA"
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(bad)}]}}]}

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            adapter.READINESS_PROMPT,
            "",
            provider=provider,
            created_at_utc=FIXED_NOW,
        )

    assert exc.value.reason == "adapter_validation_failed"
    assert "invalid_schema_version" in exc.value.validation["errors"]
    assert len(calls) == 2


def test_form_model_missing_falls_back_to_generic_model(monkeypatch):
    _enable_gemini(monkeypatch)
    availability = adapter.is_live_gemini_form_available()

    assert availability["available"] is True
    assert availability["effective_model_label"] == TEST_MODEL
    assert availability["generic_model_label_present"] is True
    assert availability["form_model_label_present"] is False
    assert availability["model_label_source"] == "OPENCLAW_GEMINI_MODEL"


def test_matching_form_model_override_is_allowed(monkeypatch):
    _enable_gemini(monkeypatch, form_model=TEST_MODEL)
    availability = adapter.is_live_gemini_form_available()

    assert availability["available"] is True
    assert availability["effective_model_label"] == TEST_MODEL
    assert availability["form_model_label_present"] is True
    assert availability["model_label_mismatch"] is False


def test_mismatched_form_model_blocks_before_provider(monkeypatch):
    _enable_gemini(monkeypatch, form_model="gemini-2.5-flash")
    called = False

    def provider(**kwargs):
        nonlocal called
        called = True
        return {}

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            adapter.READINESS_PROMPT,
            "",
            provider=provider,
            created_at_utc=FIXED_NOW,
        )

    assert exc.value.reason == "blocked_model_label_mismatch"
    assert exc.value.availability["model_label_mismatch"] is True
    assert called is False


def test_rate_limited_provider_failure_is_preserved(monkeypatch):
    _enable_gemini(monkeypatch)

    def provider(**kwargs):
        raise spine.LMConsultError(
            "blocked_provider_rate_limited",
            validation={
                "provider_status_code": 429,
                "provider_error_category": "rate_limited",
                "retry_after_seconds": 45,
                "request_body_logged": False,
                "credential_value_logged": False,
            },
        )

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            adapter.READINESS_PROMPT,
            "",
            provider=provider,
            created_at_utc=FIXED_NOW,
        )

    assert exc.value.reason == "blocked_provider_rate_limited"
    assert exc.value.validation["validation"]["provider_status_code"] == 429
    assert exc.value.validation["validation"]["provider_error_category"] == "rate_limited"
    assert exc.value.validation["validation"]["retry_after_seconds"] == 45


def test_invalid_model_provider_failure_is_preserved(monkeypatch):
    _enable_gemini(monkeypatch)

    def provider(**kwargs):
        raise spine.LMConsultError(
            "blocked_model_label",
            validation={
                "provider_status_code": 404,
                "provider_error_category": "model_label",
                "request_body_logged": False,
                "credential_value_logged": False,
            },
        )

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            adapter.READINESS_PROMPT,
            "",
            provider=provider,
            created_at_utc=FIXED_NOW,
        )

    assert exc.value.reason == "blocked_model_label"
    assert exc.value.validation["validation"]["provider_status_code"] == 404
    assert exc.value.validation["validation"]["provider_error_category"] == "model_label"


def test_invalid_json_fails_closed(monkeypatch):
    _enable_gemini(monkeypatch)

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            "hello",
            "",
            provider=_provider_with_result(lambda request: "{not json"),
            created_at_utc=FIXED_NOW,
        )

    assert exc.value.reason == "adapter_invalid_json"


def test_unsafe_safety_flag_fails_closed(monkeypatch):
    _enable_gemini(monkeypatch)

    def unsafe(request):
        result = _safe_result(request)
        result["safety_flags"]["external_action_performed"] = True
        return result

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            "hello",
            "",
            provider=_provider_with_result(unsafe),
            created_at_utc=FIXED_NOW,
    )

    assert exc.value.reason == "adapter_validation_failed"
    assert "safety_flag_true:external_action_performed" in exc.value.validation["errors"]


@pytest.mark.parametrize(
    "reply",
    [
        "You should deduct this as a tax expense.",
        "This is legal advice: use that clause.",
        "I diagnose this as a medical issue.",
    ],
)
def test_tax_legal_medical_advice_is_rejected(monkeypatch, reply):
    _enable_gemini(monkeypatch)

    def unsafe(request):
        return _safe_result(request, reply=reply)

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            "hello",
            "",
            provider=_provider_with_result(unsafe),
            created_at_utc=FIXED_NOW,
        )

    assert "professional_advice_detected" in exc.value.validation["errors"]


def test_model_result_cannot_record_directly(monkeypatch):
    _enable_gemini(monkeypatch)

    def unsafe(request):
        result = _safe_result(request, intent="answer_candidate")
        result["confirmed_by_winship"] = True
        result["should_record_now"] = True
        result["proposed_answer"]["plain_english"] = "Use manual approval."
        return result

    with pytest.raises(adapter.GeminiFormAdapterError) as exc:
        adapter.call_gemini_data_room_form_turn(
            _package(),
            "record it",
            "",
            provider=_provider_with_result(unsafe),
            created_at_utc=FIXED_NOW,
        )

    assert "model_attempted_confirmation" in exc.value.validation["errors"]
    assert "model_attempted_record" in exc.value.validation["errors"]
