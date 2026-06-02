import json
from pathlib import Path

import agent_voice_profiles as profiles


REQUIRED_PROFILE_FIELDS = {
    "speaker_ref",
    "voice_profile_ref",
    "role",
    "speaks_when",
    "must_not_speak_when",
    "authority_boundary",
    "default_voice_modes",
    "tts_profile",
    "copy_rules",
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
    assert {"Cassandra", "Chief", "Hermes", "Guardian", "Niles"}.issubset(set(clara["vocabulary"]["avoid"]))


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


def test_read_model_machine_proof_and_tts_rules():
    read_model = _read_model()

    assert read_model["status"] == profiles.CONTRACT_STATUS
    assert read_model["source_material"]["agy_audit_status_from_operator"] == "AGENT_VOICE_TTS_AUDIT_READY"
    assert read_model["tts_rules"]["all_tts_text_plain_text"] is True
    assert read_model["tts_rules"]["markdown_policy"] == "strip_before_tts"
    assert read_model["machine_proof"]["tts_rules_captured"] is True
    assert read_model["machine_proof"]["all_authority_boundaries_forbid_send_ledger_portal"] is True
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
