from __future__ import annotations

import json

import pytest


PROMISE = "I'm on it, let me pull that up for you."


@pytest.mark.parametrize(
    "speaker_ref",
    (
        "cassandra",
        "chief",
        "hermes",
        "guardian",
        "niles",
        "maestro",
        "clara",
        "openclaw",
    ),
)
def test_unbound_action_promise_is_replaced_in_each_canonical_voice(speaker_ref: str) -> None:
    import action_promise_integrity as integrity
    import agent_voice_profiles

    result = integrity.enforce_action_promise_integrity(
        PROMISE,
        speaker_ref=speaker_ref,
        action_receipt_refs=(),
    )

    assert result.receipt.promise_detected is True
    assert result.receipt.action_binding_present is False
    assert result.receipt.substituted is True
    assert result.visible_text == agent_voice_profiles.action_promise_fallback_for_speaker(
        speaker_ref
    )
    assert integrity.contains_action_promise(result.visible_text) is False
    assert agent_voice_profiles.require_voice_conformance(
        speaker_ref, result.visible_text
    )["passed"] is True


def test_every_canonical_speaker_has_a_distinct_honest_fallback() -> None:
    import agent_voice_profiles

    fallbacks = {
        speaker: agent_voice_profiles.action_promise_fallback_for_speaker(speaker)
        for speaker in agent_voice_profiles.SPEAKER_REFS
    }

    assert len(set(fallbacks.values())) == len(agent_voice_profiles.SPEAKER_REFS)
    for fallback in fallbacks.values():
        assert not {"proof", "pdf", "file"}.intersection(fallback.casefold().split())


@pytest.mark.parametrize(
    "promise",
    (
        "I'm on it.",
        "Let me get that.",
        "I'll take care of it.",
        "I'm working on that now.",
        "Getting that for you now.",
        "I'll look into it.",
    ),
)
def test_action_promise_detection_covers_the_verb_class(promise: str) -> None:
    import action_promise_integrity as integrity

    assert integrity.contains_action_promise(promise) is True


def test_artifact_readback_renders_through_each_canonical_voice() -> None:
    import action_promise_integrity as integrity
    import agent_voice_profiles

    messages = {
        speaker: agent_voice_profiles.artifact_ready_message_for_speaker(
            speaker,
            label="St. Anne's June 2026 invoice PDF proof",
            path="/Volumes/openclaw_e/artifacts/invoice.pdf",
        )
        for speaker in agent_voice_profiles.SPEAKER_REFS
    }

    assert len(set(messages.values())) == len(agent_voice_profiles.SPEAKER_REFS)
    for speaker, message in messages.items():
        assert agent_voice_profiles.require_voice_conformance(speaker, message)["passed"] is True
        if integrity.contains_action_promise(message):
            bound = integrity.enforce_action_promise_integrity(
                message,
                speaker_ref=speaker,
                action_receipt_refs=("proof_presenter_request:verified",),
            )
            assert bound.visible_text == message
            assert bound.receipt.action_binding_present is True


def test_receipted_action_promise_survives_with_binding_receipt() -> None:
    import action_promise_integrity as integrity

    result = integrity.enforce_action_promise_integrity(
        PROMISE,
        speaker_ref="maestro",
        action_receipt_refs=("bridge_request:req_1690",),
    )

    assert result.visible_text == PROMISE
    assert result.receipt.promise_detected is True
    assert result.receipt.action_binding_present is True
    assert result.receipt.substituted is False
    assert result.receipt.action_receipt_refs == ("bridge_request:req_1690",)
    assert PROMISE not in json.dumps(result.receipt.to_dict(), sort_keys=True)


@pytest.mark.parametrize(
    "speaker_ref",
    (
        "cassandra",
        "chief",
        "hermes",
        "guardian",
        "niles",
        "maestro",
        "clara",
        "openclaw",
    ),
)
def test_fleet_operator_guard_enforces_each_canonical_voice(speaker_ref: str) -> None:
    import agent_voice_profiles
    from operator_surface_guard import guard_operator_reply_with_receipt

    bounded = guard_operator_reply_with_receipt(
        PROMISE,
        agent_role=speaker_ref.upper(),
        source_request="show me the proof",
    )

    assert bounded.visible_text == agent_voice_profiles.action_promise_fallback_for_speaker(
        speaker_ref
    )
    assert "action_promise_unbound_replaced" in bounded.receipt.reason_codes


def test_fleet_operator_guard_preserves_a_receipted_action_promise() -> None:
    from operator_surface_guard import guard_operator_reply_with_receipt

    bounded = guard_operator_reply_with_receipt(
        PROMISE,
        agent_role="MAESTRO",
        source_request="show me the proof",
        action_receipt_refs=("proof_presenter_request:verified",),
    )

    assert bounded.visible_text == PROMISE
    assert "action_promise_bound_to_receipt" in bounded.receipt.reason_codes


def test_shared_final_surface_replaces_unbound_promise_and_rebinds_cards(
    tmp_path,
) -> None:
    import openclaw_request_processor as processor

    request_path = tmp_path / "mission_control_operator_instruction_request_promise.json"
    request_path.write_text(
        json.dumps({"source_text": "show me the proof"}) + "\n",
        encoding="utf-8",
    )
    response = processor.OpenClawResponseForMac(
        source_request_id="req_promise",
        source_request_filename=request_path.name,
        workflow_ref="general/operator_maestro_chat",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline=PROMISE,
        operator_message=PROMISE,
        what_happened=(),
        why_it_happened="",
        how_to_fix="",
        visible_cards=(
            {
                "card_type": "FRONTDOOR_AGENT_ANSWER",
                "title": PROMISE,
                "summary": PROMISE,
            },
        ),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={
            "operator_display": {"speaker_ref": "chief"},
            "dynamic_card_response": {"title": PROMISE, "summary": PROMISE},
            "maestro_cassandra_responder": {
                "one_line_answer": PROMISE,
                "plain_summary": PROMISE,
            },
        },
        readback_files=(),
        next_safe_move="Review the response.",
    )

    bounded = processor._enrich_operator_surface(
        response,
        request_path,
        tmp_path / "read_models",
    )

    assert "No action receipt" in bounded.operator_message
    assert bounded.operator_headline == bounded.operator_message
    assert bounded.visible_cards[0]["title"] == bounded.operator_message
    assert bounded.visible_cards[0]["summary"] == bounded.operator_message
    assert bounded.detail_disclosure["dynamic_card_response"]["title"] == bounded.operator_message
    assert bounded.detail_disclosure["dynamic_card_response"]["summary"] == bounded.operator_message
    responder = bounded.detail_disclosure["maestro_cassandra_responder"]
    assert responder["one_line_answer"] == bounded.operator_message
    assert responder["plain_summary"] == bounded.operator_message
    receipt = bounded.detail_disclosure["action_promise_integrity"]
    assert receipt["speaker_ref"] == "chief"
    assert receipt["substituted"] is True
