import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_voice_response_layer as layer
from scripts.export_agent_voice_response_layer import main as export_main


FIXED_NOW = "2026-05-25T18:30:00+00:00"


def _payload() -> dict:
    return layer.build_payload(generated_at=FIXED_NOW)


def _by_role(rows: tuple[dict, ...] | list[dict]) -> dict[str, dict]:
    return {row["agent_role"]: row for row in rows}


def _by_id(rows: tuple[dict, ...] | list[dict], key: str) -> dict[str, dict]:
    return {row[key]: row for row in rows}


def test_required_models_and_response_packet_exist():
    payload = _payload()
    schemas = payload["model_schemas"]

    assert tuple(schemas["AgentVoiceResponseLayer"]) == (
        "layer_id",
        "doctrine",
        "truth_preservation_policy",
        "voice_selection_policy",
        "vibe_selection_policy",
        "agent_voice_profiles",
        "agent_vibe_profiles",
        "allowed_tone_policy",
        "forbidden_tone_policy",
        "response_packet_policy",
        "authority_boundary",
        "next_safe_move",
    )
    assert "AgentVoiceProfile" in schemas
    assert "AgentVibeProfile" in schemas
    assert "VoiceBoundResponsePacket" in schemas
    assert "VoiceTransformConstraint" in schemas
    assert "AgentVoiceSelectionPolicy" in schemas
    assert "AgentVoiceExample" in schemas
    assert payload["response_packets"][0]["response_author"] == "CHIEF"
    assert payload["response_packets"][0]["truth_payload_ref"]
    assert "Missing confirmed Coupa PO/reference" == payload["response_packets"][0]["primary_blocker"]


def test_all_required_voice_profiles_exist():
    payload = _payload()
    profiles = _by_role(payload["voice_profiles"])

    assert set(layer.AGENT_ROLES).issubset(set(profiles))
    assert "concise operational commander" in profiles["CHIEF"]["tone_traits"]
    assert "polished executive assistant" in profiles["CASSANDRA"]["tone_traits"]
    assert "proof-first" in profiles["GUARDIAN"]["tone_traits"]
    assert "creative producer" in profiles["NILES"]["tone_traits"]
    assert "validation-first" in profiles["CODEX"]["tone_traits"]
    assert "neutral" in profiles["OPENCLAW_SYSTEM"]["tone_traits"]
    assert "randomly choose persona" in profiles["UNKNOWN"]["forbidden_moves"]


def test_all_required_vibe_profiles_exist():
    payload = _payload()
    vibes = _by_role(payload["vibe_profiles"])

    assert {"NILES", "CASSANDRA", "CHIEF", "GUARDIAN", "CODEX", "OPENCLAW_SYSTEM"}.issubset(set(vibes))
    assert vibes["NILES"]["humor_level"] == "HIGH"
    assert vibes["NILES"]["pressure_level"] == "LOW"
    assert vibes["NILES"]["creative_energy_level"] == "HIGH"
    assert "clownishness" in vibes["NILES"]["forbidden_vibe_moves"]
    assert "X32" in vibes["NILES"]["context_where_this_vibe_applies"]
    assert vibes["CASSANDRA"]["directness_level"] == "HIGH"
    assert vibes["GUARDIAN"]["seriousness_level"] == "HIGH"
    assert "playful tone during safety/proof/approval/secret contexts" in vibes["GUARDIAN"]["forbidden_vibe_moves"]
    assert vibes["CODEX"]["directness_level"] == "HIGH"
    assert vibes["OPENCLAW_SYSTEM"]["encouragement_style"] == "neutral, minimal, status-oriented"


def test_selection_policy_routes_expected_contexts():
    payload = _payload()
    policies = _by_id(payload["selection_policies"], "policy_id")

    assert policies["voice_selection_capital_hilton_status"]["inferred_agent_role"] == "CHIEF"
    assert policies["voice_selection_email_draft"]["inferred_agent_role"] == "CASSANDRA"
    assert policies["voice_selection_guardian_gate"]["inferred_agent_role"] == "GUARDIAN"
    assert policies["voice_selection_niles_creative"]["inferred_agent_role"] == "NILES"
    assert policies["voice_selection_codex_build"]["inferred_agent_role"] == "CODEX"
    assert policies["voice_selection_ambiguous"]["ambiguity_status"] == "AMBIGUOUS_FAIL_CLOSED"
    assert policies["voice_selection_ambiguous"]["inferred_agent_role"] == "OPENCLAW_SYSTEM"


def test_constraints_enforce_truth_and_authority():
    payload = _payload()
    constraints = _by_id(payload["constraints"], "constraint_type")

    for constraint_type in layer.CONSTRAINT_TYPES:
        assert constraint_type in constraints
        assert constraints[constraint_type]["fail_closed"] is True

    assert "source receipts" in constraints["COMPLETION_REQUIRES_RECEIPTS"]["rule"]
    assert "send, submit, dispatch" in constraints["NO_EXTERNAL_AUTHORITY_CLAIM"]["rule"]
    assert "suppress playful" in constraints["HIGH_RISK_SUPPRESSES_PLAYFUL_VIBE"]["rule"]
    assert payload["machine_proof"]["completion_without_receipts_blocked"] is True
    assert payload["machine_proof"]["send_authority_claim_blocked"] is True
    assert payload["machine_proof"]["vibe_cannot_remove_blockers"] is True
    assert payload["machine_proof"]["vibe_cannot_alter_completion_state"] is True


def test_required_examples_and_bad_examples_marked_invalid():
    payload = _payload()
    examples = _by_id(payload["examples"], "example_id")
    validation = payload["example_validation"]

    expected = {
        "chief_capital_hilton_invoice_status",
        "cassandra_email_draft_review",
        "guardian_approval_gate",
        "niles_x32_source_refs_missing",
        "niles_low_risk_creative_flow",
        "codex_build_status",
        "openclaw_system_file_intake",
    }
    assert expected.issubset(set(examples))
    assert "Capital Hilton is not ready to move" in examples["chief_capital_hilton_invoice_status"]["voiced_response"]
    assert examples["cassandra_email_draft_review"]["forbidden_bad_response"] == "I sent it to Annette."
    assert examples["guardian_approval_gate"]["forbidden_bad_response"] == "Approved enough."
    assert "X32" in examples["niles_x32_source_refs_missing"]["voiced_response"]
    assert "fixed the routing" in examples["niles_x32_source_refs_missing"]["forbidden_bad_response"]
    assert "loose and musical" in examples["niles_low_risk_creative_flow"]["voiced_response"]
    assert "updated the show file" in examples["niles_low_risk_creative_flow"]["forbidden_bad_response"]
    assert examples["codex_build_status"]["forbidden_bad_response"] == "Deployed."
    assert examples["openclaw_system_file_intake"]["forbidden_bad_response"] == "I analyzed the file."
    for example_id in expected:
        assert validation[example_id]["bad_response_valid"] is False
        assert validation[example_id]["good_response_preserves_truth"] is True


def test_high_risk_context_suppresses_playful_vibe():
    payload = _payload()
    override = payload["high_risk_override_preview"]

    assert override["requested_agent_role"] == "NILES"
    assert override["truth_risk"] == "HIGH"
    assert override["selected_voice_profile_ref"] == "agent_voice_profile:guardian"
    assert override["selected_vibe_profile_ref"] == "agent_vibe_profile:guardian"
    assert override["playful_vibe_suppressed"] is True
    assert "audio/project file mutation" in override["blocked_actions"]


def test_all_live_authority_false_and_no_private_bodies():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key

    text = layer.stable_json(payload)
    assert "-----BEGIN" not in text
    assert "raw_body_value" not in text
    assert "raw_private_body" not in text
    assert "api_key:" not in text.lower()
    assert not re.search(r"(?i)(password|token|secret)\s*[:=]\s*[A-Za-z0-9+/=_-]{12,}", text)


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(
        [
            "--generated-at",
            FIXED_NOW,
            "--export-root",
            str(tmp_path),
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = tmp_path / layer.JSON_EXPORT_NAME
    operator_path = tmp_path / layer.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["read_model_id"] == layer.READ_MODEL_ID
    assert summary["voice_profile_count"] >= 6
    assert summary["all_live_authority_false"] is True
    assert payload["read_model_id"] == layer.READ_MODEL_ID
    assert operator_path.exists()
    assert "Truth first" in operator_path.read_text(encoding="utf-8")
