import json
from pathlib import Path

import agent_voice_profiles as profiles


REQUIRED_PROFILE_FIELDS = {
    "speaker_ref",
    "voice_profile_ref",
    "self_identity",
    "first_person_policy",
    "operator_reference_policy",
    "forbidden_identity_blur",
    "role",
    "speaks_when",
    "must_not_speak_when",
    "authority_boundary",
    "default_voice_modes",
    "tts_profile",
    "copy_rules",
    "revoice_style_guidance",
    "revoice_style_marker_contract",
    "persona_fidelity",
    "autonomy_ladder",
    "vocabulary",
    "examples",
    "guardrails",
}


def _read_model():
    return profiles.build_read_model(generated_at="2026-06-02T03:45:00+00:00")


def test_every_speaker_ref_has_complete_profile():
    read_model = _read_model()
    profile_map = {profile["speaker_ref"]: profile for profile in read_model["profiles"]}

    assert set(profile_map) == set(profiles.SPEAKER_REFS)
    for speaker_ref, profile in profile_map.items():
        assert REQUIRED_PROFILE_FIELDS.issubset(profile)
        assert profile["voice_profile_ref"] == f"agent_voice_profile:{speaker_ref}"
        assert profile["role"]
        assert profile["speaks_when"]
        assert profile["must_not_speak_when"]
        assert profile["examples"]
        assert profile["guardrails"]


def test_voice_profile_ref_source_map_falls_back_to_openclaw():
    assert profiles.voice_profile_ref_for_speaker("cassandra") == "agent_voice_profile:cassandra"
    assert profiles.voice_profile_ref_for_speaker("chief") == "agent_voice_profile:chief"
    assert profiles.voice_profile_ref_for_speaker("unknown") == "agent_voice_profile:openclaw"


def test_read_model_exposes_voice_profile_ref_map():
    read_model = _read_model()

    assert read_model["voice_profile_ref_map"]["cassandra"] == "agent_voice_profile:cassandra"
    assert read_model["voice_profile_ref_map"]["chief"] == "agent_voice_profile:chief"
    assert read_model["voice_profile_ref_map"]["guardian"] == "agent_voice_profile:guardian"


def test_every_profile_has_tts_profile_and_plain_text_policy():
    read_model = _read_model()

    for profile in read_model["profiles"]:
        tts = profile["tts_profile"]
        assert tts["enabled"] is True
        assert tts["voice_target"]
        assert tts["cadence_description"]
        assert tts["sentence_shape"]
        assert tts["punctuation_rules"]
        assert tts["markdown_policy"] == "strip_before_tts"
        assert "raw JSON" in tts["do_not_use_markers"]
        for example in profile["examples"]:
            spoken = example["spoken_tts_text"]
            assert "`" not in spoken
            assert "*" not in spoken
            assert not spoken.strip().startswith("#")
            assert "{" not in spoken and "}" not in spoken


def test_authority_boundaries_forbid_action_by_default():
    read_model = _read_model()

    for profile in read_model["profiles"]:
        boundary = profile["authority_boundary"]
        assert boundary["can_execute"] is False
        assert boundary["can_send"] is False
        assert boundary["can_mutate_ledger"] is False
        assert boundary["can_submit_portal"] is False
        assert boundary["can_mutate_workbooks"] is False
        assert boundary["can_export_pdf"] is False
        assert boundary["can_mark_paid"] is False


def test_clara_is_only_external_client_facing_profile_and_cassandra_internal_only():
    read_model = _read_model()
    visibility = {
        profile["speaker_ref"]: profile["copy_rules"]["client_visibility"]
        for profile in read_model["profiles"]
    }

    assert visibility["clara"] == "external_allowed"
    assert visibility["cassandra"] == "internal_only"
    assert {
        speaker
        for speaker, client_visibility in visibility.items()
        if client_visibility != "internal_only"
    } == {"clara"}
    clara = next(profile for profile in read_model["profiles"] if profile["speaker_ref"] == "clara")
    assert {"Cassandra", "Chief", "Hermes", "Guardian", "Niles", "Maestro"}.issubset(set(clara["vocabulary"]["avoid"]))


def test_agent_perspective_policy_pins_first_person_to_speaker_not_operator():
    read_model = _read_model()

    assert read_model["machine_proof"]["required_agent_self_identities_present"] is True
    assert read_model["machine_proof"]["all_profiles_have_perspective_policy"] is True
    assert read_model["machine_proof"]["operator_first_person_blur_allowed"] is False
    profile_map = {profile["speaker_ref"]: profile for profile in read_model["profiles"]}
    for speaker in ("cassandra", "chief", "guardian", "hermes", "niles", "maestro"):
        profile = profile_map[speaker]
        assert profile["self_identity"]["display_name"].lower() == speaker
        assert "Winship" in profile["operator_reference_policy"]
        assert "first-person" in profile["forbidden_identity_blur"]


def test_guardian_and_niles_guardrails_avoid_bad_characterization():
    read_model = _read_model()
    guardian = next(profile for profile in read_model["profiles"] if profile["speaker_ref"] == "guardian")
    niles = next(profile for profile in read_model["profiles"] if profile["speaker_ref"] == "niles")

    guardian_text = json.dumps(guardian["examples"], sort_keys=True).lower()
    assert "maybe" not in guardian_text
    assert "panic" not in guardian_text
    assert "watchman" in guardian["vocabulary"]["avoid"]
    assert "warrior" in guardian["vocabulary"]["avoid"]
    assert "tribal" in guardian["vocabulary"]["avoid"]

    niles_text = json.dumps(niles["examples"], sort_keys=True).lower()
    assert "mate" not in niles_text
    assert "crikey" not in niles_text
    assert "ripper" not in niles_text
    assert "mate" in niles["vocabulary"]["avoid"]
    assert "crikey" in niles["vocabulary"]["avoid"]
    assert "ripper" in niles["vocabulary"]["avoid"]


def test_immutable_persona_cores_derive_from_one_canonical_fleet_source():
    cores = {
        speaker: profiles.immutable_persona_core_for_speaker(speaker)
        for speaker in ("cassandra", "chief", "hermes", "guardian", "niles", "maestro")
    }

    assert len({core["core_sha256"] for core in cores.values()}) == len(cores)
    for speaker, core in cores.items():
        profile = profiles.voice_profile_for_speaker(speaker)
        assert core["agent"] == speaker
        assert core["voice_profile_ref"] == profile["voice_profile_ref"]
        assert core["prompt_descriptor"] == profile["prompt_descriptor"]
        assert core["revoice_style_guidance"] == profile["revoice_style_guidance"]
        assert core["revoice_style_marker_contract"] == profile["revoice_style_marker_contract"]
        assert core["style_traits"] == profile["voice_conformance"]["style_traits"]
        assert core["role"] == profile["role"]
        assert core["operator_change_gate"] == "first_class_operator_approval_receipt_required"
        assert "translate_operator_frustration_into_positive_communication" in core["culture_traits"]
        assert core["backstory_policy"]["write_mode"] == "append_only_grounded_experience"


def test_every_speaker_has_distinct_canonical_revoice_guidance():
    guidance = {
        speaker: profiles.revoice_prompt_guidance_for_speaker(speaker)
        for speaker in profiles.SPEAKER_REFS
    }

    assert len(set(guidance.values())) == len(profiles.SPEAKER_REFS)
    assert "right-hand" in guidance["maestro"]
    assert "executive-assistant" in guidance["cassandra"]
    assert "foreman" in guidance["chief"]
    assert "Australian" in guidance["niles"]
    assert "gatekeeper" in guidance["guardian"]
    assert "systems-advisor" in guidance["hermes"]


def test_every_speaker_has_register_relative_persona_fidelity_notes():
    notes = {
        speaker: profiles.persona_fidelity_note_for_speaker(speaker)
        for speaker in profiles.SPEAKER_REFS
    }

    assert len({note["register_target"] for note in notes.values()}) == len(profiles.SPEAKER_REFS)
    assert all(note["warmth_definition"] for note in notes.values())
    assert all(note["anti_patterns"] for note in notes.values())
    assert "quietly confident" in notes["clara"]["register_target"]
    assert "closing ask" in notes["clara"]["warmth_definition"]


def test_clara_persona_fidelity_rejects_solicitous_pleasantry_padding():
    result = profiles.validate_voice_conformance(
        "clara",
        "Thanks for your attention, and I hope your week is going well.",
    )

    assert result["passed"] is False
    assert {item["code"] for item in result["violations"]} == {"persona_fidelity_anti_pattern"}


def test_clara_profile_carries_quiet_luxury_flow_without_forced_polished_markers():
    profile = profiles.voice_profile_for_speaker("clara")
    core = profiles.immutable_persona_core_for_speaker("clara")
    marker_contract = profile["revoice_style_marker_contract"]
    copy_blob = json.dumps(profile["copy_rules"], sort_keys=True).casefold()

    assert marker_contract["flow_steps"] == ["Recognize", "Clarify", "Guide", "Confirm"]
    assert "required_any" not in marker_contract
    assert profile["quiet_luxury"]["doctrine_ref"] == "quiet_luxury:clara_cassandra:v1"
    assert core["quiet_luxury"]["flow"] == ["Recognize", "Clarify", "Guide", "Confirm"]
    assert "i'm happy to help" not in copy_blob
    assert "let me know if you have any questions or need anything else" not in copy_blob
    assert profile["copy_rules"]["signoff"] == "Warmly,\nClara Reid"


def test_read_model_machine_proof_and_tts_rules():
    read_model = _read_model()

    assert read_model["status"] == profiles.CONTRACT_STATUS
    assert read_model["source_material"]["agy_audit_status_from_operator"] == "AGENT_VOICE_TTS_AUDIT_READY"
    assert read_model["tts_rules"]["all_tts_text_plain_text"] is True
    assert read_model["tts_rules"]["markdown_policy"] == "strip_before_tts"
    assert read_model["machine_proof"]["tts_rules_captured"] is True
    assert read_model["machine_proof"]["all_authority_boundaries_forbid_send_ledger_portal"] is True
    assert read_model["machine_proof"]["all_operator_approved_initial_autonomy_rungs_present"] is True
    assert read_model["machine_proof"]["autonomy_rungs_confer_no_new_authority"] is True
    assert read_model["machine_proof"]["clara_only_external_client_facing_profile"] is True
    assert read_model["machine_proof"]["cassandra_internal_only"] is True


def test_export_writes_local_bridge_and_wiki(tmp_path):
    result = profiles.export_agent_voice_profiles(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Agent Voice Profiles.md",
        generated_at="2026-06-02T03:45:00+00:00",
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert Path(result["wiki_path"]).exists()
    assert local["status"] == profiles.CONTRACT_STATUS
    assert len(local["profiles"]) == len(profiles.SPEAKER_REFS)


def test_operator_approved_initial_autonomy_rungs_are_profile_wide_and_non_granting() -> None:
    by_speaker = {row["speaker_ref"]: row for row in profiles.build_profiles()}

    assert {
        speaker: row["autonomy_ladder"]["rung"] for speaker, row in by_speaker.items()
    } == profiles.AUTONOMY_RUNG_ASSIGNMENTS
    for row in by_speaker.values():
        assignment = row["autonomy_ladder"]
        assert assignment["assignment_status"] == "operator_approved_initial_rung"
        assert assignment["classification_only"] is True
        assert assignment["new_authority_conferred"] is False
        assert assignment["send_authority_implied"] is False
        assert assignment["money_authority_implied"] is False
        assert assignment["delete_authority_implied"] is False
        assert assignment["secret_authority_implied"] is False
        assert row["authority_boundary"]["can_send"] is False
        assert row["authority_boundary"]["can_mutate_ledger"] is False


def test_live_voice_conformance_projects_the_approved_autonomy_rung() -> None:
    result = profiles.validate_voice_conformance(
        "cassandra",
        "The review packet remains unchanged and is prepared for your review.",
    )

    assert result["passed"] is True
    assert result["autonomy_ladder"]["rung"] == "PREPARE_ONLY"
    assert result["autonomy_ladder"]["new_authority_conferred"] is False
