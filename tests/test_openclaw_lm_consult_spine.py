from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_lm_consult_spine as spine
import watch_desk_feed


FIXED_NOW = "2026-06-13T05:30:00+00:00"
TEST_MODEL = "gemini-3.5-flash"


def _consult_request(**overrides):
    payload = {
        "created_at_utc": FIXED_NOW,
        "requested_by_agent": "cassandra",
        "owner_agent": "cassandra",
        "source_surface": "telegram",
        "source_context_ref": "guided_review:data_room_review:test",
        "task_type": "data_room_form_fill",
        "consult_kind": "form_fill",
        "preferred_model_class": "external_fast_worker",
        "preferred_provider": "gemini",
        "provider_model_label": TEST_MODEL,
        "reason_for_model_choice": "Fast advisory reasoning over redacted Data Room proof.",
        "context_refs": ["guided_review_session:test", "question:test"],
        "redacted_context_summary": "Current question only. No private proof.",
        "expected_output_schema": {"type": "object"},
    }
    payload.update(overrides)
    return spine.build_lm_consult_request(**payload)


def _safe_payload(request):
    return {
        "assistant_reply": "I can help explain the current question.",
        "proposed_answer": {
            "plain_english": "Use a conservative provisional answer.",
            "normalized_decision": "conservative provisional answer",
            "confidence": "medium",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "confirmed_by_winship": False,
        "should_record_now": False,
        "safety_flags": {
            "authoritative": False,
            "runtime_policy_changed": False,
            "confirmed_reference_data_created": False,
            "external_action_performed": False,
            "execution_attempted": False,
        },
        "facts_used": [request["source_context_ref"]],
    }


def _fake_gemini_transport(calls: list[dict], payload: dict | None = None):
    def transport(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
        calls.append(
            {
                "request_payload": request_payload,
                "request_body": request_body,
                "model_label": model_label,
                "timeout_seconds": timeout_seconds,
            }
        )
        response_payload = dict(payload or _safe_payload(request_payload))
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(response_payload)}]}}]}

    return transport


def test_generic_request_validates_and_keeps_authority_false():
    request = _consult_request()
    validation = spine.validate_lm_consult_request(request)

    assert validation["valid"] is True
    assert request["schema_version"] == spine.LM_CONSULT_REQUEST_SCHEMA_VERSION
    assert request["advisory_only"] is True
    assert request["execution_allowed"] is False
    assert request["runtime_mutation_allowed"] is False
    assert request["external_action_allowed"] is False
    assert request["sensitive_data_excluded"] is True
    assert request["tools_exposed"] is False


def test_gemini_provider_disabled_reports_blocked_config():
    request = _consult_request()
    result = spine.request_lm_consult(request, env={})

    assert result["status"] == "blocked_provider_config_required"
    assert result["provider"] == "gemini"
    assert result["execution_attempted"] is False
    assert result["runtime_mutation_performed"] is False
    assert result["external_action_performed"] is False


def test_fake_gemini_provider_valid_result_is_accepted():
    request = _consult_request()
    calls: list[dict] = []
    adapter = spine.GeminiProviderAdapter(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=_fake_gemini_transport(calls),
    )

    result = spine.request_lm_consult(request, provider_adapter=adapter)

    assert result["status"] == "result_accepted"
    assert result["provider"] == "gemini"
    assert result["authoritative"] is False
    assert calls
    assert "tools" not in calls[0]["request_body"]


def test_fake_unsafe_result_is_rejected():
    request = _consult_request()
    calls: list[dict] = []
    unsafe = _safe_payload(request)
    unsafe["assistant_reply"] = "I will send email and create a Gmail draft."
    adapter = spine.GeminiProviderAdapter(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=_fake_gemini_transport(calls, unsafe),
    )

    result = spine.request_lm_consult(request, provider_adapter=adapter)

    assert result["status"] == "result_rejected"
    assert "forbidden_action_or_tool_text" in result["structured_payload"]["validation"]["errors"]
    assert result["execution_attempted"] is False


def test_openai_chatgpt_adapter_is_contract_interchangeable_stub():
    request = _consult_request(preferred_provider="openai", provider_model_label="chatgpt-class")
    adapter = spine.provider_adapter_for(
        request,
        env={"OPENCLAW_ENABLE_LM_CONSULTS": "1", "OPENCLAW_LM_PROVIDER": "openai"},
    )

    availability = adapter.is_available()
    result = spine.request_lm_consult(request, provider_adapter=adapter)

    assert availability["interchangeable_contract_level"] is True
    assert result["status"] == "adapter_stub_not_live"
    assert result["provider"] == "openai"
    assert result["execution_attempted"] is False


def test_manual_handoff_creates_package_not_live_success():
    request = _consult_request(preferred_provider="manual", preferred_model_class="manual_handoff", provider_model_label="manual")

    result = spine.request_lm_consult(request)

    assert result["status"] == "manual_handoff_package_created"
    assert result["provider"] == "manual"
    assert result["structured_payload"]["live_model_called"] is False
    assert result["execution_attempted"] is False


def test_data_room_request_uses_generic_spine_contract():
    package = {
        "package_id": "data_room_form_fill_package:test",
        "review_session_id": "data_room_review:test",
        "current_question_id": "question:test",
        "current_question_index": 1,
        "total_questions": 23,
        "current_question": {"question_text": "What is the payment privacy default?"},
        "expected_output_schema": {"schema_version": "DATA_ROOM_GEMINI_FORM_TURN_RESULT_V0"},
    }

    request = spine.build_data_room_form_fill_consult_request(package, user_turn="Explain this question.", created_at_utc=FIXED_NOW)

    assert request["schema_version"] == spine.LM_CONSULT_REQUEST_SCHEMA_VERSION
    assert request["consult_kind"] == "form_fill"
    assert request["preferred_provider"] == "gemini"
    assert request["requested_by_agent"] == "cassandra"
    assert "data_room_gemini_form" not in request["schema_version"].lower()
    assert request["execution_allowed"] is False


def test_model_result_cannot_record_directly():
    request = _consult_request()
    result = spine.build_lm_consult_result(
        request,
        provider="gemini",
        model_class="external_fast_worker",
        model_label=TEST_MODEL,
        assistant_reply="Candidate ready.",
        structured_payload={"assistant_reply": "Candidate ready.", "should_record_now": True},
    )

    validation = spine.validate_lm_consult_result(result, request)

    assert validation["valid"] is False
    assert "model_attempted_record" in validation["errors"]


def test_confirmation_records_only_after_winship_confirmation():
    request = _consult_request()
    result = spine.build_lm_consult_result(
        request,
        provider="gemini",
        model_class="external_fast_worker",
        model_label=TEST_MODEL,
        assistant_reply="Use manual approval for payment privacy.",
        structured_payload={
            "proposed_answer": {"plain_english": "Use manual approval for payment privacy."},
            "confirmed_by_winship": False,
            "should_record_now": False,
        },
    )

    candidate = spine.build_review_answer_from_consult_result(result, question_id="question:test", confirmed_by_winship=False)
    confirmed = spine.build_review_answer_from_consult_result(
        result,
        question_id="question:test",
        confirmed_by_winship=True,
        source_refs=["privacy:payment_policy"],
    )

    assert candidate["record_review_answer"] is False
    assert candidate["status"] == "candidate_pending_winship_confirmation"
    assert confirmed["record_review_answer"] is True
    assert confirmed["schema_version"] == "REVIEW_ANSWER_V0"
    assert confirmed["authoritative"] is False
    assert confirmed["confirmed_reference_data_created"] is False


def test_codex_finalizer_package_only_after_done_criteria():
    blocked = spine.maybe_build_codex_finalizer_package(review_session_id="session:test", done_criteria={"done": False})
    ready = spine.maybe_build_codex_finalizer_package(
        review_session_id="session:test",
        done_criteria={"done": True},
        confirmed_answer_refs=["answer:one"],
        created_at_utc=FIXED_NOW,
    )

    assert blocked["status"] == "blocked_until_done_criteria"
    assert blocked["codex_finalizer_package_ref"] == ""
    assert ready["status"] == "waiting_for_codex_dispatch"
    assert ready["codex_finalizer_package_ref"].startswith("codex_work_package:")
    assert ready["automatic_codex_dispatch"] is False
    assert ready["confirmed_reference_data_created"] is False
    assert ready["hydration_performed"] is False


def test_watch_desk_item_for_lm_consult_status(tmp_path):
    status = spine.build_lm_consult_spine_status(env={})
    (tmp_path / "openclaw_lm_consult_spine_status.json").write_text(spine.stable_json(status), encoding="utf-8")
    (tmp_path / "operator_intake_events.json").write_text(
        json.dumps({"generated_at": FIXED_NOW, "events": [], "watch_desk_items": []}),
        encoding="utf-8",
    )

    feed = watch_desk_feed.build_watch_desk_feed(
        read_model_root=tmp_path,
        task_root=tmp_path / "tasks",
        generated_at=FIXED_NOW,
    )
    items = {item["item_id"]: item for item in feed["feed_items"]}

    assert "lm_consult_spine:gemini:blocked" in items
    item = items["lm_consult_spine:gemini:blocked"]
    assert item["urgency"] == "blocked"
    assert item["push_allowed"] is False
    assert item["state"]["execution_allowed"] is False
    assert item["state"]["tools_exposed"] is False


def test_no_tools_no_runtime_no_confirmed_data_or_hydration():
    status = spine.build_lm_consult_spine_status(env={})

    assert status["advisory_only"] is True
    assert status["tools_exposed"] is False
    assert status["execution_allowed"] is False
    assert status["runtime_mutation_allowed"] is False
    assert status["external_action_allowed"] is False
    assert status["confirmed_reference_data_allowed"] is False
    assert status["hydration_allowed"] is False


def test_provider_config_alone_is_not_live_ready_without_readiness_result():
    status = spine.build_lm_consult_spine_status(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        }
    )

    assert status["provider_config_ready"] is True
    assert status["readiness_call_succeeded"] is False
    assert status["live_ready"] is False
    assert status["blocked_reason"] == "readiness_call_required"
    assert spine.cassandra_lm_brain_claim(status) == "The LM consult spine is built, but Gemini readiness has not succeeded yet."


def test_gemini_model_label_status_reports_matching_labels():
    status = spine.gemini_model_label_status(
        {
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "OPENCLAW_GEMINI_FORM_MODEL": TEST_MODEL,
        }
    )

    assert status["effective_model_label"] == TEST_MODEL
    assert status["generic_model_label_present"] is True
    assert status["form_model_label_present"] is True
    assert status["model_label_mismatch"] is False
    assert status["model_label_source"] == "OPENCLAW_GEMINI_FORM_MODEL"


def test_gemini_model_label_mismatch_blocks_provider_config():
    status = spine.build_lm_consult_spine_status(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "OPENCLAW_GEMINI_FORM_MODEL": "gemini-2.5-flash",
            "GEMINI_API_KEY": "test-redacted",
        }
    )

    assert status["provider_config_ready"] is False
    assert status["live_ready"] is False
    assert status["blocked_reason"] == "blocked_model_label_mismatch"
    assert status["model_label_mismatch"] is True
    assert status["effective_model_label"] == ""


def test_rate_limited_result_keeps_live_ready_false():
    request = _consult_request()

    def rate_limited_transport(**kwargs):
        raise spine.LMConsultError(
            "blocked_provider_rate_limited",
            validation={
                "provider_status_code": 429,
                "provider_error_category": "rate_limited",
                "retry_after_seconds": 60,
                "request_body_logged": False,
                "credential_value_logged": False,
            },
        )

    adapter = spine.GeminiProviderAdapter(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=rate_limited_transport,
    )

    result = spine.request_lm_consult(request, provider_adapter=adapter)
    status = spine.build_lm_consult_spine_status(env=adapter.env, latest_request=request, latest_result=result)

    assert result["status"] == "blocked_provider_rate_limited"
    assert status["live_ready"] is False
    assert status["blocked_reason"] == "blocked_provider_rate_limited"
    assert status["provider_status_code"] == 429
    assert status["provider_error_category"] == "rate_limited"
    assert status["retry_after_seconds"] == 60


def test_http_429_classifies_without_request_or_credential_leakage():
    headers = {"Retry-After": "30"}
    exc = HTTPError("https://provider.invalid", 429, "Too Many Requests", headers, BytesIO(b'{"error":"quota"}'))

    reason, validation = spine.provider_http_error_classification(exc)

    assert reason == "blocked_provider_rate_limited"
    assert validation["provider_status_code"] == 429
    assert validation["provider_error_category"] == "rate_limited"
    assert validation["retry_after_seconds"] == 30
    assert validation["request_body_logged"] is False
    assert validation["credential_value_logged"] is False


def test_gemini_generate_content_request_uses_header_auth_not_query_param():
    request = spine._build_gemini_generate_content_request(
        api_key="test-redacted",
        model_label=TEST_MODEL,
        request_body={"contents": []},
    )

    assert "key=" not in request.full_url
    assert request.get_header("X-goog-api-key") == "test-redacted"


def test_minimal_gemini_probe_success_uses_no_schema_or_tools():
    calls: list[dict] = []

    def transport(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
        calls.append(
            {
                "request_payload": request_payload,
                "request_body": request_body,
                "model_label": model_label,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"candidates": [{"content": {"parts": [{"text": "ready"}]}}]}

    result = spine.run_minimal_gemini_probe(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=transport,
    )

    assert result["success"] is True
    assert result["status"] == "probe_succeeded"
    assert result["probe_attempted"] is True
    assert result["provider_reached"] is True
    assert result["structured_output_enabled"] is False
    assert result["raw_data_room_context_included"] is False
    assert result["credential_env_selected"] == "GEMINI_API_KEY"
    assert calls[0]["request_payload"]["schema_version"] == spine.GEMINI_MINIMAL_PROBE_SCHEMA_VERSION
    assert calls[0]["request_payload"]["data_room_context_included"] is False
    assert "responseSchema" not in calls[0]["request_body"]["generationConfig"]
    assert "tools" not in calls[0]["request_body"]


def test_gemini_credential_status_prefers_google_api_key_without_values():
    status = spine.gemini_credential_status(
        {
            "GEMINI_API_KEY": "gemini-test-secret",
            "GOOGLE_API_KEY": "google-test-secret",
        }
    )
    rendered = json.dumps(status, sort_keys=True)

    assert status["credential_present"] is True
    assert status["credential_env_selected"] == "GOOGLE_API_KEY"
    assert status["multiple_credential_vars_present"] is True
    assert "multiple credential vars present" in status["credential_warning"]
    assert "google-test-secret" not in rendered
    assert "gemini-test-secret" not in rendered


def test_minimal_gemini_probe_400_blocks_as_provider_bad_request():
    def transport(**kwargs):
        body = json.dumps(
            {
                "error": {
                    "code": 400,
                    "status": "INVALID_ARGUMENT",
                    "message": "Bad request for minimal probe.",
                }
            }
        ).encode("utf-8")
        raise HTTPError("https://provider.invalid", 400, "Bad Request", {}, BytesIO(body))

    result = spine.run_minimal_gemini_probe(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=transport,
    )
    rendered = json.dumps(result, sort_keys=True)

    assert result["success"] is False
    assert result["status"] == "blocked_provider_bad_request"
    assert result["provider_status_code"] == 400
    assert result["provider_error_category"] == "provider_http_error"
    assert result["request_shape_version"] == spine.GEMINI_MINIMAL_PROBE_REQUEST_SHAPE_VERSION
    assert "current_question" not in rendered
    assert "test-redacted" not in rendered


def test_minimal_gemini_probe_429_returns_rate_limited_category():
    def transport(**kwargs):
        body = json.dumps(
            {
                "error": {
                    "code": 429,
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Prepayment credits are depleted.",
                }
            }
        ).encode("utf-8")
        raise HTTPError("https://provider.invalid", 429, "Too Many Requests", {}, BytesIO(body))

    result = spine.run_minimal_gemini_probe(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=transport,
    )

    assert result["success"] is False
    assert result["status"] == "blocked_provider_rate_limited"
    assert result["provider_status_code"] == 429
    assert result["provider_error_category"] == "rate_limited"
    assert result["provider_error_code"] == "RESOURCE_EXHAUSTED"


def test_minimal_gemini_probe_model_not_found_returns_model_label_category():
    def transport(**kwargs):
        body = json.dumps(
            {
                "error": {
                    "code": 400,
                    "status": "INVALID_ARGUMENT",
                    "message": "models/gemini-3.5-flash is not found for API version v1beta.",
                }
            }
        ).encode("utf-8")
        raise HTTPError("https://provider.invalid", 400, "Bad Request", {}, BytesIO(body))

    result = spine.run_minimal_gemini_probe(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=transport,
    )

    assert result["success"] is False
    assert result["status"] == "blocked_model_label"
    assert result["provider_status_code"] == 400
    assert result["provider_error_category"] == "model_label"
    assert "not found" in result["provider_error_message_redacted"]


def test_http_404_classifies_as_model_label_block():
    exc = HTTPError("https://provider.invalid", 404, "Not Found", {}, BytesIO(b'{"error":"model not found"}'))

    reason, validation = spine.provider_http_error_classification(exc)

    assert reason == "blocked_model_label"
    assert validation["provider_status_code"] == 404
    assert validation["provider_error_category"] == "model_label"


def test_http_400_model_not_found_classifies_as_model_label_block():
    body = json.dumps(
        {
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "models/gemini-3.5-flash is not found for API version v1beta.",
            }
        }
    ).encode("utf-8")
    exc = HTTPError("https://provider.invalid", 400, "Bad Request", {}, BytesIO(body))

    reason, validation = spine.provider_http_error_classification(
        exc,
        request_body={"generationConfig": {"responseSchema": {"type": "object"}}},
        model_label=TEST_MODEL,
    )

    assert reason == "blocked_model_label"
    assert validation["provider_status_code"] == 400
    assert validation["provider_error_category"] == "model_label"
    assert validation["provider_error_code"] == "INVALID_ARGUMENT"
    assert "not found" in validation["provider_error_message_redacted"]
    assert validation["effective_model_label"] == TEST_MODEL
    assert validation["endpoint_family"] == spine.GEMINI_ENDPOINT_FAMILY
    assert validation["structured_output_enabled"] is True
    assert validation["request_shape_version"] == spine.GEMINI_REQUEST_SHAPE_VERSION
    assert validation["request_body_logged"] is False
    assert validation["credential_value_logged"] is False


def test_http_400_schema_error_classifies_as_structured_output_schema():
    body = json.dumps(
        {
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "Unknown name responseSchema at generationConfig: Cannot find field.",
            }
        }
    ).encode("utf-8")
    exc = HTTPError("https://provider.invalid", 400, "Bad Request", {}, BytesIO(body))

    reason, validation = spine.provider_http_error_classification(
        exc,
        request_body={"generationConfig": {"responseSchema": {"type": "object"}}},
        model_label=TEST_MODEL,
    )

    assert reason == "blocked_structured_output_schema"
    assert validation["provider_error_category"] == "structured_output_schema"
    assert validation["structured_output_enabled"] is True
    assert "responseSchema" in validation["provider_error_message_redacted"]
    assert "GEMINI_API_KEY" not in json.dumps(validation)


def test_http_400_generic_bad_request_keeps_redacted_provider_message():
    body = json.dumps(
        {
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "Bad request: debug token AIzaFakeSecretValue should not appear.",
            }
        }
    ).encode("utf-8")
    exc = HTTPError("https://provider.invalid", 400, "Bad Request", {}, BytesIO(body))

    reason, validation = spine.provider_http_error_classification(
        exc,
        request_body={"generationConfig": {"responseMimeType": "application/json"}},
        model_label=TEST_MODEL,
    )
    rendered = json.dumps(validation, sort_keys=True)

    assert reason == "adapter_api_http_400"
    assert validation["provider_error_category"] == "provider_http_error"
    assert "AIzaFakeSecretValue" not in rendered
    assert "generationConfig" not in rendered
    assert "responseMimeType" not in rendered
    assert validation["request_body_logged"] is False
    assert validation["credential_value_logged"] is False


def test_schema_error_falls_back_to_json_prompt_mode():
    request = _consult_request()
    calls: list[dict] = []

    def transport(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
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
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(_safe_payload(request_payload))}]}}]}

    adapter = spine.GeminiProviderAdapter(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=transport,
    )

    result = spine.request_lm_consult(request, provider_adapter=adapter)

    assert result["status"] == "result_accepted"
    assert result["structured_output_mode"] == spine.STRUCTURED_OUTPUT_JSON_PROMPT_FALLBACK
    assert len(calls) == 2
    assert "responseSchema" in calls[0]["request_body"]["generationConfig"]
    assert "responseSchema" not in calls[1]["request_body"]["generationConfig"]
    assert "tools" not in calls[1]["request_body"]


def test_schema_fallback_failure_preserves_native_schema_diagnostic():
    request = _consult_request()
    calls: list[dict] = []

    def transport(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
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
        raise spine.LMConsultError(
            "blocked_provider_rate_limited",
            validation={
                "provider_status_code": 429,
                "provider_error_code": "RESOURCE_EXHAUSTED",
                "provider_error_message_redacted": "Prepayment credits are depleted.",
                "provider_error_category": "rate_limited",
                "structured_output_enabled": False,
                "request_body_logged": False,
                "credential_value_logged": False,
            },
        )

    adapter = spine.GeminiProviderAdapter(
        env={
            "OPENCLAW_ENABLE_LM_CONSULTS": "1",
            "OPENCLAW_LM_PROVIDER": "gemini",
            "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
            "GEMINI_API_KEY": "test-redacted",
        },
        transport=transport,
    )

    result = spine.request_lm_consult(request, provider_adapter=adapter)
    status = spine.build_lm_consult_spine_status(env=adapter.env, latest_request=request, latest_result=result)

    assert result["status"] == "blocked_provider_rate_limited"
    assert status["provider_error_category"] == "rate_limited"
    assert status["structured_output_mode"] == spine.STRUCTURED_OUTPUT_JSON_PROMPT_FALLBACK
    assert status["native_schema_provider_status_code"] == 400
    assert status["native_schema_provider_error_category"] == "structured_output_schema"
    assert "responseSchema" in status["native_schema_provider_error_message_redacted"]
    assert len(calls) == 2


def test_status_payload_does_not_contain_secret_value():
    env = {
        "OPENCLAW_ENABLE_LM_CONSULTS": "1",
        "OPENCLAW_LM_PROVIDER": "gemini",
        "OPENCLAW_GEMINI_MODEL": TEST_MODEL,
        "GEMINI_API_KEY": "test-secret-value-not-for-output",
    }

    status = spine.build_lm_consult_spine_status(env=env)
    rendered = json.dumps(status, sort_keys=True)

    assert "test-secret-value-not-for-output" not in rendered


def test_all_agents_can_construct_consult_request_fixtures():
    for agent in ("cassandra", "chief", "hermes", "guardian", "niles", "watch_desk"):
        request = spine.build_lm_consult_request(
            created_at_utc=FIXED_NOW,
            requested_by_agent=agent,
            owner_agent=agent,
            source_surface=f"{agent}_fixture",
            source_context_ref=f"{agent}:context",
            task_type="synthesis" if agent != "niles" else "creative_planning",
            consult_kind="synthesis" if agent != "niles" else "recommendation",
            preferred_model_class="external_fast_worker",
            preferred_provider="manual",
            provider_model_label="manual",
            redacted_context_summary="fixture only",
        )
        assert spine.validate_lm_consult_request(request)["valid"] is True
        assert request["execution_allowed"] is False
