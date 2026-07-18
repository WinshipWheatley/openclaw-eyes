from __future__ import annotations

import pytest

import agent_voice_profiles as voice_profiles
from agent_voice_response_layer import build_voice_profiles
from clara_invoice_email_draft_package import build_general_client_invoice_body
from client_comms_thread_rail import build_clara_first_contact_draft
from client_followup_watch import ClientFollowupWatchStore


def test_every_canonical_speaker_has_an_enforced_conformance_contract() -> None:
    profiles = {profile["speaker_ref"]: profile for profile in voice_profiles.build_profiles()}

    assert set(profiles) == set(voice_profiles.SPEAKER_REFS)
    for speaker_ref, profile in profiles.items():
        contract = profile["voice_conformance"]
        assert contract["enforcement"] == "fail_closed"
        assert contract["style_traits"]
        assert contract["forbidden_phrases"]

        example = profile["examples"][0]["operator_text"]
        result = voice_profiles.validate_voice_conformance(speaker_ref, example)
        assert result["passed"] is True
        assert result["voice_profile_ref"] == profile["voice_profile_ref"]


def test_every_canonical_speaker_rejects_known_canned_copy() -> None:
    for speaker_ref in voice_profiles.SPEAKER_REFS:
        result = voice_profiles.validate_voice_conformance(speaker_ref, "As an AI, I can help with that.")
        assert result["passed"] is False
        assert "canned_phrase" in {item["code"] for item in result["violations"]}


def test_response_layer_voice_profiles_derive_from_canonical_registry() -> None:
    canonical = {profile["speaker_ref"]: profile for profile in voice_profiles.build_profiles()}
    role_to_speaker = {
        "MAESTRO": "maestro",
        "CHIEF": "chief",
        "CASSANDRA": "cassandra",
        "GUARDIAN": "guardian",
        "NILES": "niles",
        "HERMES": "hermes",
        "CLARA": "clara",
        "OPENCLAW_SYSTEM": "openclaw",
    }

    for profile in build_voice_profiles():
        if profile.agent_role == "UNKNOWN":
            continue
        source = canonical[role_to_speaker[profile.agent_role]]
        assert profile.voice_profile_ref == source["voice_profile_ref"]
        assert profile.voice_purpose == source["role"]
        assert profile.tone_traits == tuple(source["voice_conformance"]["style_traits"])


def test_clara_conformance_rejects_the_reviewed_off_voice_copy() -> None:
    text = (
        "Hi Draper,\n\n"
        "I'm Clara Reid, helping Winship keep the St. Anne's invoice package organized. "
        "Whenever you're happy with the invoice, just let us know once you've forwarded it to Glenn.\n\n"
        "Best,\nClara Reid"
    )

    result = voice_profiles.validate_voice_conformance("clara", text)

    assert result["passed"] is False
    assert {item["code"] for item in result["violations"]} >= {
        "canned_phrase",
        "over_narrowed_identity",
    }
    with pytest.raises(voice_profiles.VoiceConformanceError):
        voice_profiles.require_voice_conformance("clara", text)


def test_clara_invoice_body_uses_canonical_general_identity_and_direct_ask() -> None:
    body = build_general_client_invoice_body(
        {
            "client_name": "St. Anne's",
            "attachment_filename": "St_Annes.pdf",
            "line_items": ({"description": "Wedding", "date": "2026-06-27", "amount": 250.0},),
        },
        {"name": "Draper Carter", "role": "intermediary", "forward_to": "Glenn"},
        first_contact_intro_required=True,
        client_ref="st_annes",
        workflow_ref="st_annes_invoice_forward_tracking",
    )

    assert "I'm Clara Reid, Winship's assistant." in body
    closure = voice_profiles.loop_closing_ask_for_workflow(
        "st_annes_invoice_forward_tracking",
        client_ref="st_annes",
    )
    assert closure["ask_text"] in body
    assert closure["why_text"] in body
    assert "helping Winship keep the St. Anne's invoice package" not in body
    assert "I hope this note finds you well" not in body
    assert "I'm happy to help" not in body
    conformance = voice_profiles.require_clara_copy_conformance(
        body,
        workflow_ref="st_annes_invoice_forward_tracking",
        client_ref="st_annes",
    )
    assert conformance["passed"] is True
    assert conformance["quiet_luxury_critic"]["passed"] is True


def test_due_followup_draft_is_canonical_clara_and_carries_gate_receipt(tmp_path) -> None:
    store = ClientFollowupWatchStore(str(tmp_path / "followups.sqlite3"))
    store.add_watch(
        client_ref="st_annes",
        client_name="St. Anne's",
        recipient="draper.carter@gmail.com",
        subject="Invoice ST-ANNES-REAL-2026-06",
        sent_at_utc_iso="2026-07-01T10:00:00+00:00",
        invoice_ref="ST-ANNES-REAL-2026-06",
        days_without_reply=3,
    )

    proposal = store.due_followup_proposals("2026-07-05T10:00:00+00:00")[0]

    assert proposal["voice_profile_ref"] == "agent_voice_profile:clara"
    assert proposal["voice_conformance"]["passed"] is True
    assert "I wanted to follow up" not in proposal["draft"]["body"]
    closure = voice_profiles.loop_closing_ask_for_workflow(
        f"client_followup_watch:{proposal['watch_id']}",
        client_ref="st_annes",
    )
    assert closure["ask_text"] in proposal["draft"]["body"]
    assert closure["why_text"] in proposal["draft"]["body"]
    assert "I'm happy to help" not in proposal["draft"]["body"]
    assert proposal["quiet_luxury_critic"]["passed"] is True
    assert proposal["approval_request"]["payload"]["voice_conformance"]["passed"] is True
    assert proposal["loop_closing_ask_conformance"]["milestone_ref"] == "glenn_acknowledged"


def test_client_comms_thread_rail_consumes_canonical_clara_profile() -> None:
    result = build_clara_first_contact_draft(
        client_ref="live_arts_md",
        workflow_ref="invoice:live_arts_md:2026-07",
        recipient_ref="contact:dane",
        recipient_name="Dane",
        subject="July invoice",
        work_kind="invoice",
    )

    draft = result["draft_candidate"]
    assert "I'm Clara Reid, Winship's assistant." in draft["body"]
    assert "helping Winship keep" not in draft["body"]
    assert draft["voice_profile_ref"] == "agent_voice_profile:clara"
    assert draft["voice_conformance"]["passed"] is True
    assert draft["loop_closing_ask_conformance"]["milestone_ref"] == "accountant_acknowledged"
