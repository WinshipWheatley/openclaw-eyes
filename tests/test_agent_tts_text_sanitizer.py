import json
from pathlib import Path

import agent_tts_text_sanitizer as sanitizer


FIXED_NOW = "2026-06-02T12:00:00+00:00"


def test_strips_markdown_links_bullets_backticks_asterisks_and_raw_json():
    raw_json = '{"' + "email_send_allowed" + '": true, "' + "paid" + '": true}'
    text = """
    # Status
    - **Captured** `work log` [Proof](proof.json)
    ```json
    RAW_JSON_PLACEHOLDER
    ```
    Natural cadence, preserved.
    """.replace("RAW_JSON_PLACEHOLDER", raw_json)

    result = sanitizer.sanitize_text(text, speaker_ref="cassandra")

    assert "Captured work log Proof" in result
    assert "Natural cadence, preserved." in result
    assert "`" not in result
    assert "*" not in result
    assert "#" not in result
    assert "[" not in result and "]" not in result
    assert "{" not in result and "}" not in result
    assert "email_send_" + "allowed" not in result


def test_cassandra_preserves_commas_and_ellipses():
    result = sanitizer.sanitize_text(
        "Captured... review this, then confirm it.",
        speaker_ref="cassandra",
    )

    assert "..." in result
    assert "," in result


def test_chief_uses_periods_and_colons_without_ellipses_or_commas():
    result = sanitizer.sanitize_text(
        "Provider gate... blocked, submit gate missing.",
        speaker_ref="chief",
    )

    assert "..." not in result
    assert "," not in result
    assert ":" in result or "." in result
    assert result.endswith(".")


def test_hermes_allows_measured_commas_and_em_dashes_without_ellipses():
    result = sanitizer.sanitize_text(
        "The stronger pattern -- shared rails, then review...",
        speaker_ref="hermes",
    )

    assert "\u2014" in result
    assert "," in result
    assert "..." not in result


def test_guardian_is_terse_and_removes_ellipses():
    result = sanitizer.sanitize_text(
        "Blocked... send authority missing, ledger authority missing!",
        speaker_ref="guardian",
    )

    assert "..." not in result
    assert "," not in result
    assert "!" not in result
    assert "Blocked." in result


def test_niles_keeps_relaxed_pauses_without_parody_terms():
    result = sanitizer.sanitize_text(
        "The session breathes... mate, keep the vocal texture relaxed, crikey.",
        speaker_ref="niles",
    )

    assert "..." in result
    assert "," in result
    assert "mate" not in result.lower()
    assert "crikey" not in result.lower()


def test_clara_uses_professional_punctuation_only():
    result = sanitizer.sanitize_text(
        "Proposal draft... ready -- please review!",
        speaker_ref="clara",
    )

    assert "..." not in result
    assert "\u2014" not in result
    assert "!" not in result
    assert result.endswith(".")


def test_clara_removes_internal_agent_system_words_for_client_facing_output():
    result = sanitizer.sanitize_text(
        "Internal agent system note: proof drawer says workflow_ref is ready... client may review!",
        speaker_ref="clara",
    )

    lowered = result.lower()
    assert "internal" not in lowered
    assert "agent" not in lowered
    assert "system" not in lowered
    assert "proof drawer" not in lowered
    assert "workflow_ref" not in lowered
    assert "client may review" in lowered
    assert "..." not in result
    assert "!" not in result


def test_unknown_speaker_falls_back_to_openclaw_status_text():
    result = sanitizer.sanitize_operator_display(
        {
            "speaker_ref": "unknown",
            "voice_mode": "operator_calm",
            "audience": "internal_operator",
            "headline": "# System status",
            "plain_summary": "Ready... [Proof](proof.json)",
            "next_safe_action": "Review locally.",
        }
    )

    assert result["speaker_ref"] == "openclaw"
    assert result["voice_profile_ref"] == "agent_voice_profile:openclaw"
    assert "..." not in result["tts_text"]
    assert "Proof" in result["tts_text"]
    assert result["machine_proof"]["plain_text_only"] is True


def test_operator_display_sanitizes_selected_fields_and_preserves_profile_ref():
    result = sanitizer.sanitize_operator_display(
        {
            "speaker_ref": "cassandra",
            "voice_profile_ref": "agent_voice_profile:cassandra",
            "voice_mode": "operator_intake",
            "audience": "internal_operator",
            "headline": "St. Anne's work log captured",
            "plain_summary": "I saved this as a `draft` event...",
            "next_safe_action": "Review and confirm the event.",
        }
    )

    assert result["speaker_ref"] == "cassandra"
    assert result["voice_profile_ref"] == "agent_voice_profile:cassandra"
    assert result["voice_mode"] == "operator_intake"
    assert result["audience"] == "internal_operator"
    assert result["sanitized_fields"]["plain_summary"] == "I saved this as a draft event..."
    assert "`" not in result["tts_text"]
    assert result["machine_proof"]["tts_live_connection_performed"] is False
    assert result["machine_proof"]["message_send_performed"] is False


def test_contract_read_model_captures_all_profile_rules_and_false_authority():
    read_model = sanitizer.build_contract_read_model(generated_at=FIXED_NOW)

    assert read_model["status"] == sanitizer.CONTRACT_STATUS
    assert set(read_model["profile_rules"]) == set(sanitizer.PROFILE_RULES)
    assert read_model["profile_rules"]["cassandra"]["allow_ellipses"] is True
    assert read_model["profile_rules"]["chief"]["allow_ellipses"] is False
    assert read_model["profile_rules"]["hermes"]["allow_em_dash"] is True
    assert read_model["profile_rules"]["guardian"]["allow_commas"] is False
    assert all(value is False for value in read_model["authority_boundary"].values())
    assert read_model["machine_proof"]["tts_live_connection_performed"] is False
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_writes_json_and_wiki(tmp_path):
    result = sanitizer.export_agent_tts_text_sanitizer(
        export_root=tmp_path / "read_models",
        wiki_path=tmp_path / "wiki" / "Agent TTS Text Sanitizer.md",
        generated_at=FIXED_NOW,
    )

    payload = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    wiki_text = Path(result["wiki_path"]).read_text(encoding="utf-8")
    assert payload["status"] == sanitizer.CONTRACT_STATUS
    assert payload["read_model_id"] == sanitizer.READ_MODEL_ID
    assert "Agent TTS Text Sanitizer" in wiki_text
