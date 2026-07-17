from __future__ import annotations

import pytest

import agent_voice_profiles as voice_profiles
import frontdoor_prompt
import activation_gate_register
from clara_invoice_email_draft_package import build_general_client_invoice_body
from final_output_boundary import OutputBoundaryContext, render_final_output
from operator_surface_guard import guard_operator_reply_with_receipt


ROLE_BY_SPEAKER = {
    "cassandra": "CASSANDRA",
    "chief": "CHIEF",
    "hermes": "HERMES",
    "guardian": "GUARDIAN",
    "niles": "NILES",
    "maestro": "MAESTRO",
    "clara": "CLARA",
    "openclaw": "OPENCLAW_SYSTEM",
}


def test_frontdoor_personas_are_derived_from_the_canonical_eight_agent_registry() -> None:
    profiles = {profile["speaker_ref"]: profile for profile in voice_profiles.build_profiles()}

    assert set(profiles) == set(voice_profiles.SPEAKER_REFS)
    for speaker_ref, profile in profiles.items():
        assert profile["prompt_descriptor"]
        assert (
            frontdoor_prompt._conversational_persona(speaker_ref)
            == voice_profiles.conversational_prompt_descriptor_for_speaker(speaker_ref)
            == profile["prompt_descriptor"]
        )


def test_every_live_final_boundary_receipts_its_own_voice_profile() -> None:
    for speaker_ref, role in ROLE_BY_SPEAKER.items():
        example = voice_profiles.voice_profile_for_speaker(speaker_ref)["examples"][0][
            "operator_text"
        ]

        rendered = guard_operator_reply_with_receipt(
            example,
            agent_role=role,
            source_request="Give me the current status.",
        )

        receipt = rendered.receipt.to_dict()
        assert rendered.visible_text == example
        assert receipt["speaker_ref"] == speaker_ref
        assert receipt["voice_profile_ref"] == f"agent_voice_profile:{speaker_ref}"
        assert receipt["voice_conformance_outcome"] == "passed"
        assert receipt["voice_replaced_fragment_count"] == 0


def test_off_voice_fragment_fails_closed_per_agent_without_losing_neighboring_truth() -> None:
    outputs: set[str] = set()
    for speaker_ref, role in ROLE_BY_SPEAKER.items():
        rendered = guard_operator_reply_with_receipt(
            "Capital Hilton payment remains unconfirmed. As an AI, I can help with that.",
            agent_role=role,
            source_request="What is the Capital Hilton payment status?",
        )
        receipt = rendered.receipt.to_dict()

        assert "Capital Hilton payment remains unconfirmed." in rendered.visible_text
        assert "as an ai" not in rendered.visible_text.casefold()
        assert voice_profiles.voice_boundary_fallback_for_speaker(speaker_ref) in rendered.visible_text
        assert receipt["voice_conformance_outcome"] == "substituted"
        assert receipt["voice_replaced_fragment_count"] == 1
        assert "voice_conformance:canned_phrase" in receipt["reason_codes"]
        outputs.add(rendered.visible_text)

    assert len(outputs) == len(ROLE_BY_SPEAKER)


def test_fleet_voice_boundary_has_an_explicit_rollback_switch(monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_FLEET_VOICE_BOUNDARY", "0")

    rendered = render_final_output(
        "As an AI, I can help with that.",
        context=OutputBoundaryContext.from_source_request("Say that exact sentence."),
        speaker_ref="chief",
    )

    assert rendered.visible_text == "As an AI, I can help with that."
    assert rendered.receipt.voice_conformance_outcome == "disabled"


def test_activation_register_names_the_live_fleet_voice_boundary() -> None:
    register = activation_gate_register.build_activation_gate_register()
    row = next(
        item
        for item in register["capabilities"]
        if item["capability_id"] == "fleet_voice_boundary"
    )

    assert row["flag_or_config"] == ["OPENCLAW_FLEET_VOICE_BOUNDARY"]
    assert row["default_state"] == "on_fail_closed"
    assert row["gate_stage"] == "operator_approved_live"
    assert "owner-surface canaries" in row["canary_status"]


def test_st_annes_clara_copy_carries_the_registered_human_loop_closing_ask() -> None:
    body = build_general_client_invoice_body(
        {
            "client_name": "St. Anne's",
            "attachment_filename": "St_Annes.pdf",
            "line_items": (
                {"description": "Wedding", "date": "2026-06-27", "amount": 250.0},
            ),
        },
        {"name": "Draper Carter", "role": "intermediary", "forward_to": "Glenn"},
        first_contact_intro_required=True,
        client_ref="st_annes",
        workflow_ref="st_annes_invoice_forward_tracking",
    )

    closure = voice_profiles.loop_closing_ask_for_workflow(
        "st_annes_invoice_forward_tracking",
        client_ref="st_annes",
    )
    conformance = voice_profiles.require_clara_copy_conformance(
        body,
        workflow_ref="st_annes_invoice_forward_tracking",
        client_ref="st_annes",
    )

    assert closure["milestone_ref"] == "glenn_acknowledged"
    assert closure["ask_text"] in body
    assert closure["why_text"] in body
    assert "tracking requirements" not in body.casefold()
    assert conformance["passed"] is True
    assert conformance["loop_closing_ask"]["passed"] is True
    assert conformance["loop_closing_ask"]["workflow_ref"] == "st_annes_invoice_forward_tracking"
    assert conformance["loop_closing_ask"]["milestone_ref"] == "glenn_acknowledged"
    assert "body" not in conformance["loop_closing_ask"]


def test_clara_copy_gate_rejects_a_human_sounding_ask_that_does_not_close_the_milestone() -> None:
    closure = voice_profiles.loop_closing_ask_for_workflow(
        "st_annes_invoice_forward_tracking",
        client_ref="st_annes",
    )
    body = (
        "Hi Draper,\n\n"
        "Winship's invoice is attached. Please forward it to Glenn after your review. "
        f"{closure['why_text']}\n\nWarmly,\nClara Reid"
    )

    with pytest.raises(voice_profiles.VoiceConformanceError) as exc_info:
        voice_profiles.require_clara_copy_conformance(
            body,
            workflow_ref="st_annes_invoice_forward_tracking",
            client_ref="st_annes",
        )

    assert "loop_closing_ask_missing" in {
        item["code"] for item in exc_info.value.result["violations"]
    }
