from __future__ import annotations

import json
import hashlib

import pytest


AMBIGUOUS = "Could you unpack that broader situation?"
EXPECTED_MODEL_TIMEOUT_CLARIFICATION = (
    "The language model timed out before it could classify that request. "
    "The GPU may be busy. I left your request untouched; please try again in a moment."
)
EXPECTED_MODEL_FAILURE_CLARIFICATION = (
    "The language model didn't return a usable routing decision. I left your "
    "request untouched; please try again in a moment."
)


def _force_vote_failure(monkeypatch: pytest.MonkeyPatch, status: str = "error:TimeoutError"):
    import typed_contract_decision as typed

    calls: list[str] = []

    def fail_vote(text, *_args, **_kwargs):
        calls.append(str(text))
        return None, status

    monkeypatch.setenv(typed.SEMANTIC_VOTE_ENV, "maestro")
    monkeypatch.setattr(typed, "_call_semantic_vote", fail_vote)
    return calls


def _forbidden_downstream(*_args, **_kwargs):
    raise AssertionError("a prohibited downstream model/brain path ran")


def test_non_string_vote_status_cannot_impersonate_recoverable_timeout() -> None:
    from vote_timeout_clarification import (
        VoteFailureKind,
        classify_vote_failure_kind,
        is_recoverable_outside_session_conversational_failure,
    )

    class TimeoutStringSpoof:
        def __str__(self) -> str:
            return "deadline_exceeded"

    receipt = {
        "source": "semantic_vote",
        "label": "unresolved",
        "action": "pass_through",
        "reason": "uncertain_outside_session_fail_open",
        "semantic_vote_status": TimeoutStringSpoof(),
    }

    assert classify_vote_failure_kind(receipt) is VoteFailureKind.MODEL_FAILURE
    assert is_recoverable_outside_session_conversational_failure(receipt) is False


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        ("empty", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("invalid", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("timeout_or_invalid", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("error:TimeoutError", EXPECTED_MODEL_TIMEOUT_CLARIFICATION),
        ("error:RuntimeError", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("future_unrecognized_status", EXPECTED_MODEL_FAILURE_CLARIFICATION),
    ),
)
def test_maestro_vote_failure_returns_exact_cautious_line_and_no_second_model(
    status: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro

    calls = _force_vote_failure(monkeypatch, status)
    result = maestro.answer_frontdoor_chat(
        AMBIGUOUS,
        handle_fn=_forbidden_downstream,
        protected_generate_fn=_forbidden_downstream,
    )

    receipt = result.machine_proof["typed_contract_decision"]
    assert calls == [AMBIGUOUS]
    assert result.plain_summary == expected
    assert result.one_line_answer == expected
    if expected == EXPECTED_MODEL_FAILURE_CLARIFICATION:
        assert "timeout" not in result.plain_summary.lower()
    assert receipt["source"] == "semantic_vote"
    assert receipt["label"] == "unresolved"
    assert receipt["action"] == "pass_through"
    assert receipt["reason"] == "uncertain_outside_session_fail_open"
    assert receipt["semantic_vote_status"] == status
    assert result.machine_proof["semantic_vote_model_called"] is True
    assert result.machine_proof["model_call_performed"] is True
    assert result.machine_proof["downstream_model_call_performed"] is False
    assert result.machine_proof["protected_generate_called"] is False
    assert result.machine_proof["cassandra_handle_called"] is False
    assert result.machine_proof["workflow_package_staged"] is False
    assert result.machine_proof["vote_timeout_post_launder_assertion"] is True


@pytest.mark.parametrize("status", ("deadline_exceeded",))
def test_maestro_vote_timeout_recovers_with_downstream_text_answer(
    status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet

    calls = _force_vote_failure(monkeypatch, status)
    downstream_calls: list[str] = []
    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "0")
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "timeout-recovery-packet",
            "facts": [],
            "source_refs": [],
            "packet_text": "",
        },
    )

    def recovered_answer(text: str, **_kwargs):
        downstream_calls.append(text)
        return {
            "text": "I still answered after the classifier timed out.",
            "receipt": {
                "status": "ANSWER_READY",
                "decision": "LOCAL_MODEL_RESPONSE",
                "external_llm_invoked": False,
                "local_model_invoked": True,
                "model_call_performed": True,
            },
        }

    result = maestro.answer_frontdoor_chat(
        AMBIGUOUS,
        handle_fn=_forbidden_downstream,
        protected_generate_fn=recovered_answer,
    )

    receipt = result.machine_proof["typed_contract_decision"]
    assert calls == [AMBIGUOUS]
    assert downstream_calls == [AMBIGUOUS]
    assert result.plain_summary == "I still answered after the classifier timed out."
    assert receipt["action"] == "pass_through"
    assert receipt["semantic_vote_status"] == status
    assert result.machine_proof["protected_generate_called"] is True
    assert result.machine_proof["downstream_model_call_performed"] is True
    assert result.machine_proof["second_model_call_performed"] is True
    assert result.machine_proof["vote_timeout_recovery_applied"] is True


def test_maestro_below_threshold_continues_with_verbatim_bound_two_pass_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet

    calls = _force_vote_failure(monkeypatch, "below_threshold")
    downstream_calls: list[str] = []
    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "0")
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "below-threshold-recovery-packet",
            "facts": [],
            "source_refs": [],
            "packet_text": "",
        },
    )

    def recovered_answer(text: str, **_kwargs):
        downstream_calls.append(text)
        return {
            "text": "Here is the grounded answer, without replaying your prompt.",
            "receipt": {
                "receipt_id": "protected-generate:below-threshold",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "model_selected": "qwen3:8b-q4_K_M",
            },
        }

    result = maestro.answer_frontdoor_chat(
        AMBIGUOUS,
        session={"source_message_id": "telegram:below-threshold"},
        handle_fn=_forbidden_downstream,
        protected_generate_fn=recovered_answer,
    )

    proof = result.machine_proof
    passes = proof["internal_model_pass_receipts"]
    assert calls == [AMBIGUOUS]
    assert downstream_calls == [AMBIGUOUS]
    assert result.plain_summary == "Here is the grounded answer, without replaying your prompt."
    assert AMBIGUOUS not in result.plain_summary
    assert proof["semantic_vote_model_called"] is True
    assert proof["downstream_model_call_performed"] is True
    assert proof["second_model_call_performed"] is True
    assert proof["conversational_vote_failure_recovery_applied"] is True
    assert proof["same_model_for_both_passes"] is True
    assert proof["local_model_binding"]["model"] == "qwen3:8b-q4_K_M"
    assert passes["interpretation"]["original_operator_message"] == AMBIGUOUS
    assert passes["answer"]["original_operator_message"] == AMBIGUOUS
    assert passes["interpretation"]["binding_id"] == passes["answer"]["binding_id"]
    assert passes["interpretation"]["model"] == passes["answer"]["model"]
    assert passes["interpretation"]["input_sha256"] == hashlib.sha256(
        AMBIGUOUS.encode("utf-8")
    ).hexdigest()
    assert passes["answer"]["input_sha256"] == passes["interpretation"]["input_sha256"]


def test_maestro_weather_answer_pass_receives_weather_fact_and_read_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet
    import weather_read_capability

    text = "What's the weather in Annapolis, MD today?"
    _force_vote_failure(monkeypatch, "below_threshold")
    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "0")
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "weather-answer-packet",
            "facts": [],
            "source_refs": [],
            "packet_text": "",
        },
    )
    monkeypatch.setattr(
        weather_read_capability,
        "read_weather",
        lambda _text: weather_read_capability.WeatherReadResult(
            status="READY",
            location="Annapolis, Maryland, United States",
            summary="Annapolis is 84°F and mostly clear.",
            receipt={
                "receipt_id": "weather-read:test",
                "network_method": "GET",
                "credential_use": False,
                "external_action_performed": False,
            },
        ),
    )
    seen_packets: list[dict] = []

    def answer_with_packet(_text: str, *, context_packet):
        seen_packets.append(dict(context_packet))
        return {
            "text": "It is 84°F and mostly clear in Annapolis.",
            "receipt": {
                "receipt_id": "protected-generate:weather",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "model_selected": "qwen3:8b-q4_K_M",
            },
        }

    result = maestro.answer_frontdoor_chat(
        text,
        session={"source_message_id": "telegram:weather"},
        protected_generate_fn=answer_with_packet,
    )

    assert result.plain_summary == "It is 84°F and mostly clear in Annapolis."
    assert seen_packets[0]["weather_read"]["status"] == "READY"
    assert seen_packets[0]["weather_read"]["summary"] == "Annapolis is 84°F and mostly clear."
    assert any(fact["topic"] == "weather_current" for fact in seen_packets[0]["facts"])
    assert result.machine_proof["weather_read_receipt"]["network_method"] == "GET"
    assert result.machine_proof["weather_read_receipt"]["external_action_performed"] is False


def test_two_pass_receipt_does_not_claim_same_model_when_answer_reports_a_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet

    _force_vote_failure(monkeypatch, "below_threshold")
    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "0")
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "model-mismatch-packet",
            "facts": [],
            "source_refs": [],
            "packet_text": "",
        },
    )

    result = maestro.answer_frontdoor_chat(
        "Tell me something useful.",
        session={"source_message_id": "telegram:model-mismatch"},
        protected_generate_fn=lambda *_args, **_kwargs: {
            "text": "Useful answer.",
            "receipt": {
                "receipt_id": "protected-generate:model-mismatch",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "model_selected": "qwen3:4b",
            },
        },
    )

    answer_receipt = result.machine_proof["internal_model_pass_receipts"]["answer"]
    assert answer_receipt["model"] == "qwen3:4b"
    assert result.machine_proof["same_model_for_both_passes"] is False


@pytest.mark.parametrize(
    "text",
    (
        "I like the daily digest",
        "I like the rundown",
        "I like a quick overview",
    ),
)
def test_maestro_timeout_does_not_turn_digest_mentions_into_requests(
    text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet

    calls = _force_vote_failure(monkeypatch, "deadline_exceeded")
    downstream_calls: list[str] = []
    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "0")
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "digest-mention-timeout-recovery",
            "facts": [],
            "source_refs": [],
            "packet_text": "",
        },
    )

    def recovered_answer(question: str, **_kwargs):
        downstream_calls.append(question)
        return {
            "text": "That was a mention, not a request for the global digest.",
            "receipt": {
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
            },
        }

    result = maestro.answer_frontdoor_chat(
        text,
        handle_fn=_forbidden_downstream,
        protected_generate_fn=recovered_answer,
    )

    assert calls == [text]
    assert downstream_calls == [text]
    assert result.plain_summary == "That was a mention, not a request for the global digest."
    assert result.machine_proof["vote_timeout_deterministic_digest"] is False
    assert result.machine_proof["downstream_model_call_performed"] is True
    assert result.machine_proof["vote_timeout_recovery_applied"] is True


def test_maestro_explicit_digest_uses_grounded_renderer_without_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    text = "give me the full digest"
    calls = _force_vote_failure(monkeypatch, "deadline_exceeded")
    packet = {
        "packet_id": "task-167-deterministic",
        "source_refs": ("fixture:task-167",),
        "facts": (
            {
                "fact_id": "task-167:plate",
                "topic": "plate_overview",
                "label": "Current plate",
                "value": "Grounded plate total is $1,095.",
                "provenance": "derived_answer_topic",
                "answer_topic": True,
                "current_truth": True,
            },
        ),
    }
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: packet,
    )

    result = maestro.answer_frontdoor_chat(
        text,
        handle_fn=_forbidden_downstream,
        protected_generate_fn=_forbidden_downstream,
    )

    assert calls == [text]
    assert result.plain_summary == "Grounded plate total is $1,095."
    assert result.plain_summary != WARM_TIMEOUT_CLARIFICATION
    assert result.machine_proof["vote_timeout_deterministic_digest"] is True
    assert result.machine_proof["maestro_context_packet_used"] is True
    assert result.machine_proof["semantic_vote_model_called"] is True
    assert result.machine_proof["model_call_performed"] is True
    assert result.machine_proof["downstream_model_call_performed"] is False
    assert result.machine_proof["protected_generate_called"] is False


def test_addressed_non_maestro_cannot_borrow_maestro_digest_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    text = "give me the full digest"
    _force_vote_failure(monkeypatch)
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        _forbidden_downstream,
    )

    result = maestro.answer_frontdoor_chat(
        text,
        agent="hermes",
        handle_fn=_forbidden_downstream,
        protected_generate_fn=_forbidden_downstream,
    )

    assert result.plain_summary == WARM_TIMEOUT_CLARIFICATION
    assert result.machine_proof.get("vote_timeout_deterministic_digest", False) is False
    assert result.machine_proof["protected_generate_called"] is False


def test_explicit_timeout_digest_stays_capped_after_anti_launder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import maestro_context_packet

    text = "can you catch me up?"
    _force_vote_failure(monkeypatch, "deadline_exceeded")
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "task-167-bounded-digest",
            "source_refs": ("fixture:task-167",),
            "facts": tuple(
                {
                    "fact_id": f"task-167:item-{index}",
                    "topic": "plate_overview",
                    "label": f"Item {index}",
                    "value": f"Item {index} needs ${index}00.",
                    "provenance": "derived_answer_topic",
                    "answer_topic": True,
                    "current_truth": True,
                }
                for index in range(1, 7)
            ),
        },
    )

    result = maestro.answer_frontdoor_chat(
        text,
        handle_fn=_forbidden_downstream,
        protected_generate_fn=_forbidden_downstream,
    )

    assert "$100" in result.plain_summary
    assert "$200" in result.plain_summary
    assert "$300" in result.plain_summary
    assert "$400" not in result.plain_summary
    assert "$500" not in result.plain_summary
    assert "$600" not in result.plain_summary
    assert result.machine_proof["vote_timeout_deterministic_digest"] is True


def test_strict_plate_renderer_outranks_legacy_today_schedule_collision() -> None:
    from protected_generate import render_explicit_deterministic_digest

    rendered = render_explicit_deterministic_digest(
        "what needs my attention today?",
        context_packet={
            "facts": (
                {
                    "topic": "calendar_day",
                    "label": "Calendar",
                    "value": "Rehearsal is at 7 PM.",
                    "current_truth": True,
                },
                {
                    "topic": "plate_overview",
                    "label": "Current plate",
                    "value": "Review the bounded invoice artifact.",
                    "current_truth": True,
                },
            )
        },
    )

    assert rendered == "Current plate: Review the bounded invoice artifact."
    assert "Rehearsal" not in rendered


def test_public_finalizer_reasserts_after_an_inflated_answer_topic() -> None:
    import maestro_cassandra_responder as maestro
    import typed_contract_decision as typed
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    decision = typed.decide_contract(
        AMBIGUOUS,
        context=typed.ContractContext(
            agent="maestro",
            surface="operator_maestro_chat",
        ),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            TimeoutError("vote timeout")
        ),
    )
    inflated = maestro._enforce_answer_topic_presentation(
        "Short answer.",
        {
            "facts": (
                {
                    "value": "Unrelated receivables total is $1,095.",
                    "provenance": "derived_answer_topic",
                },
            )
        },
    )
    assert "$1,095" in inflated
    result = maestro.MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="maestro_brain_freeform",
        allowed_to_call_handle=False,
        one_line_answer=inflated,
        plain_summary=inflated,
        machine_proof={"protected_generate_called": False},
    )
    finalized = maestro._finalize_typed_contract_result(
        result,
        {
            "typed_contract_decision": decision.receipt.to_dict(),
            "typed_contract_matches": ["unresolved"],
        },
        source_text=AMBIGUOUS,
    )

    assert finalized.plain_summary == WARM_TIMEOUT_CLARIFICATION
    assert finalized.one_line_answer == WARM_TIMEOUT_CLARIFICATION
    assert finalized.machine_proof["vote_timeout_post_launder_assertion"] is True


def test_error_timeout_finalizer_reasserts_floor_without_erasing_downstream_evidence() -> None:
    import maestro_cassandra_responder as maestro
    import typed_contract_decision as typed

    decision = typed.decide_contract(
        AMBIGUOUS,
        context=typed.ContractContext(
            agent="maestro",
            surface="operator_maestro_chat",
        ),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            TimeoutError("vote timeout")
        ),
    )
    result = maestro.MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="bad_future_fallthrough",
        allowed_to_call_handle=False,
        one_line_answer="Contaminated answer.",
        plain_summary="Contaminated answer.",
        machine_proof={
            "protected_generate_called": True,
            "downstream_model_call_performed": True,
            "second_model_call_performed": True,
        },
    )

    finalized = maestro._finalize_typed_contract_result(
        result,
        {
            "typed_contract_decision": decision.receipt.to_dict(),
            "typed_contract_matches": ["unresolved"],
        },
        source_text=AMBIGUOUS,
    )

    assert finalized.machine_proof["protected_generate_called"] is True
    assert finalized.machine_proof["downstream_model_call_performed"] is True
    assert finalized.machine_proof["second_model_call_performed"] is True
    assert finalized.machine_proof.get("vote_timeout_recovery_applied", False) is False
    assert finalized.plain_summary == EXPECTED_MODEL_TIMEOUT_CLARIFICATION


def test_final_processor_preserves_timeout_recovery_after_reply_pipeline(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_listener
    import maestro_context_packet
    import openclaw_request_processor as processor
    import protected_generate
    import reply_pipeline
    calls = _force_vote_failure(monkeypatch, "deadline_exceeded")
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
    monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "0")
    monkeypatch.setenv("OPENCLAW_PACKET_ENGINE", "0")
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "processor-timeout-recovery",
            "facts": [],
            "source_refs": [],
            "packet_text": "",
        },
    )
    monkeypatch.setattr(
        protected_generate,
        "protected_generate_with_receipt",
        lambda *_args, **_kwargs: {
            "text": "Recovered operator answer.",
            "receipt": {
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
            },
        },
    )
    monkeypatch.setattr(
        reply_pipeline,
        "apply_reply_pipeline",
        lambda message, *_args, **_kwargs: (
            f"{message} Unrelated receivables total is $1,095."
        ),
    )
    request = maestro_listener.build_operator_maestro_chat_request(
        AMBIGUOUS,
        message_id="task-167-final-boundary",
        chat_id=42,
        created_at="2026-07-12T04:00:00+00:00",
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_task_167.json"
    request_path.write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at="2026-07-12T04:00:00+00:00",
        duplicate_check=False,
    )

    assert calls == [AMBIGUOUS]
    assert "Recovered operator answer." in response.operator_message
    assert "Unrelated receivables total is $1,095." in response.operator_message
    assert response.operator_headline == "Recovered operator answer."
    assert response.visible_cards[0]["title"] == response.operator_headline
    assert response.visible_cards[0]["summary"] == response.operator_headline
    assert response.detail_disclosure["dynamic_card_response"]["title"] == response.operator_headline
    assert response.detail_disclosure["dynamic_card_response"]["summary"] == response.operator_headline
    responder = response.detail_disclosure["maestro_cassandra_responder"]
    assert "Recovered operator answer." in responder["one_line_answer"]
    assert "Recovered operator answer." in responder["plain_summary"]
    receipt = response.typed_contract_trace["typed_contract_decision"]
    assert receipt == response.proof_to_response["typed_contract_decision"]
    assert receipt == response.detail_disclosure["typed_contract_decision"]
    assert receipt["action"] == "pass_through"
    assert receipt["reason"] == "uncertain_outside_session_fail_open"
    assert receipt["semantic_vote_status"] == "deadline_exceeded"
    assert response.proof_to_response["vote_timeout_recovery_applied"] is True
    assert response.proof_to_response["downstream_model_call_performed"] is True
    assert response.proof_to_response["second_model_call_performed"] is True
    assert response.detail_disclosure["external_llm_invoked"] is False
    assert response.detail_disclosure["local_model_runtime_connected"] is True
    assert response.detail_disclosure["output_boundary_receipt"][
        "visible_text_sha256"
    ] == "sha256:" + hashlib.sha256(
        response.operator_message.encode("utf-8")
    ).hexdigest()
    published_response = json.dumps(
        {
            "detail_disclosure": response.detail_disclosure,
            "proof_to_response": response.proof_to_response,
        },
        sort_keys=True,
    )
    assert "internal_model_pass_receipts" not in published_response
    assert "original_operator_message" not in published_response
    assert AMBIGUOUS not in published_response

    payload, _status = processor.build_payloads(
        response,
        generated_at="2026-07-12T04:00:00+00:00",
    )
    assert payload["operator_message"] == response.operator_message
    assert payload["proof_to_response"]["typed_contract_decision"] == receipt
    assert payload["detail_disclosure"]["typed_contract_decision"] == receipt
    assert payload["machine_proof"]["external_llm_invoked"] is False
    assert payload["machine_proof"]["local_model_invoked"] is True
    assert payload["selected_model_backend"] == "LOCAL_OLLAMA"
    published_payload = json.dumps(payload, sort_keys=True)
    assert "internal_model_pass_receipts" not in published_payload
    assert "original_operator_message" not in published_payload
    assert AMBIGUOUS not in published_payload


@pytest.mark.parametrize("pipeline_mode", ("inject", "raise"))
def test_final_processor_restores_canonical_explicit_digest_after_pipeline(
    pipeline_mode: str,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maestro_context_packet
    import maestro_listener
    import openclaw_request_processor as processor
    import protected_generate
    import reply_pipeline

    text = "give me the full digest"
    calls = _force_vote_failure(monkeypatch, "deadline_exceeded")
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
    monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "0")
    monkeypatch.setattr(
        protected_generate,
        "protected_generate_with_receipt",
        _forbidden_downstream,
    )
    monkeypatch.setattr(
        maestro_context_packet,
        "build_maestro_context_packet",
        lambda **_kwargs: {
            "packet_id": "task-167-explicit-final",
            "source_refs": ("fixture:task-167",),
            "facts": (
                {
                    "fact_id": "task-167:explicit-final",
                    "topic": "plate_overview",
                    "label": "Current plate",
                    "value": "Grounded plate total is $1,095.",
                    "provenance": "derived_answer_topic",
                    "answer_topic": True,
                    "current_truth": True,
                },
            ),
        },
    )
    if pipeline_mode == "inject":
        monkeypatch.setattr(
            reply_pipeline,
            "apply_reply_pipeline",
            lambda message, *_args, **_kwargs: f"{message} Injected unrelated fact.",
        )
    else:
        monkeypatch.setattr(
            reply_pipeline,
            "apply_reply_pipeline",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("pipeline unavailable")
            ),
        )
    request = maestro_listener.build_operator_maestro_chat_request(
        text,
        message_id="task-167-explicit-final",
        chat_id=42,
        created_at="2026-07-12T04:00:00+00:00",
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_task_167_digest.json"
    request_path.write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at="2026-07-12T04:00:00+00:00",
        duplicate_check=False,
    )

    expected = "Grounded plate total is $1,095."
    assert calls == [text]
    assert response.operator_message == expected
    assert response.operator_headline == expected
    assert response.visible_cards[0]["summary"] == expected
    assert response.proof_to_response["vote_timeout_deterministic_digest"] is True
    assert response.proof_to_response["downstream_model_call_performed"] is False
    assert response.proof_to_response["protected_generate_called"] is False
    assert response.detail_disclosure["output_boundary_receipt"][
        "visible_text_sha256"
    ] == "sha256:" + hashlib.sha256(expected.encode("utf-8")).hexdigest()


def test_processor_timeout_finalizer_never_overrides_guardian_denial() -> None:
    import openclaw_request_processor as processor

    receipt = {
        "decision_id": "contract:task-167",
        "source": "semantic_vote",
        "label": "unresolved",
        "action": "pass_through",
        "reason": "uncertain_outside_session_fail_open",
        "semantic_vote_status": "deadline_exceeded",
    }
    response = processor.OpenClawResponseForMac(
        source_request_id="task-167",
        source_request_filename=None,
        workflow_ref="task-167",
        request_type="CHAT",
        internal_status="DENIED",
        operator_headline="Guardian denied publication",
        operator_message="Guardian denied publication. Nothing was sent.",
        what_happened=(),
        why_it_happened="Guardian denied it.",
        how_to_fix="Review the denial.",
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason="guardian_denied",
        detail_disclosure={
            "guardian_publication_enforcement": {
                "original_output_publish_allowed": False,
            }
        },
        readback_files=(),
        next_safe_move="Review the denial.",
        typed_contract_trace={"typed_contract_decision": receipt},
    )

    assert processor._reassert_vote_timeout_operator_message(
        response,
        question=AMBIGUOUS,
    ) is response
