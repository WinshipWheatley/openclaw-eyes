import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_response_voice_modes as modes


FIXED_NOW = "2026-06-07T01:45:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "proof_to_response_tdd_spec.json", {"status": "PROOF_TO_RESPONSE_TDD_SPEC_READY"})
    _write_json(root / "proof_to_response_lm_shadow_status.json", {"status": "PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"})
    _write_json(
        root / "proof_to_response_runtime_status.json",
        {
            "status": "PROOF_TO_RESPONSE_RUNTIME_READY",
            "active_candidate_source": "shadow_pilot_candidate",
            "source_request_id": "fixture_request",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
        },
    )
    _write_json(
        root / "proof_to_response_latest.json",
        {
            "status": "PROOF_TO_RESPONSE_RUNTIME_READY",
            "candidate_source": "shadow_pilot_candidate",
            "source_request_id": "fixture_request",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
        },
    )
    _write_json(root / "goldilocks_gate_calibration.json", {"status": "GOLDILOCKS_GATE_CALIBRATION_READY"})
    _write_json(root / "self_heal_repair_doctrine.json", {"status": "SELF_HEAL_REPAIR_DOCTRINE_READY"})
    return root


def _read_model(tmp_path: Path) -> dict:
    return modes.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _profile(read_model: dict, speaker_ref: str) -> dict:
    return {row["speaker_ref"]: row for row in read_model["voice_modes"]}[speaker_ref]


def _scenario(read_model: dict, scenario_id: str) -> dict:
    return {row["scenario_id"]: row for row in read_model["required_scenarios"]}[scenario_id]


def test_chief_response_is_concise_and_diagnostic(tmp_path):
    read_model = _read_model(tmp_path)
    chief = _profile(read_model, "chief")
    scenario = _scenario(read_model, "self_heal_blocker")

    assert chief["style"] == ["concise", "direct", "calm", "practical"]
    assert "name_blocker" in chief["allowed"]
    assert "unsupported_fixed_claims" in chief["forbidden"]
    assert scenario["speaker_ref"] == "chief"
    assert "blocker" in scenario["human_response"]["body"].lower()
    assert len(scenario["human_response"]["body"].split()) <= modes.MAX_BODY_WORDS


def test_guardian_response_blocks_protected_action_without_alarmism(tmp_path):
    read_model = _read_model(tmp_path)
    guardian = _profile(read_model, "guardian")
    scenario = _scenario(read_model, "protected_coupa_ledger_email_request")

    assert guardian["style"] == ["firm", "plain", "non_alarmist"]
    assert "granting_authority" in guardian["forbidden"]
    assert scenario["speaker_ref"] == "guardian"
    assert "blocked" in scenario["human_response"]["headline"].lower()
    assert "panic" not in modes.primary_response_text(scenario).lower()
    assert "approval equals execution" not in modes.primary_response_text(scenario).lower()


def test_cassandra_response_is_warmer_client_aware_and_proof_bound(tmp_path):
    read_model = _read_model(tmp_path)
    cassandra = _profile(read_model, "cassandra")
    scenario = _scenario(read_model, "business_development_capital_hilton_followup")

    assert "client_aware" in cassandra["style"]
    assert "draft_reframe_followups" in cassandra["allowed"]
    assert scenario["speaker_ref"] == "cassandra"
    text = modes.primary_response_text(scenario).lower()
    assert "warm" in text
    assert "stage" in text
    assert "will not send" in text
    assert modes.unsafe_completion_claims(scenario) == []


def test_niles_response_is_creative_taste_forward_without_inventing_truth(tmp_path):
    read_model = _read_model(tmp_path)
    niles = _profile(read_model, "niles")
    scenario = _scenario(read_model, "music_niles_controller_mapping")

    assert "texture_forward" in niles["style"]
    assert "generate_options" in niles["allowed"]
    assert scenario["speaker_ref"] == "niles"
    text = modes.primary_response_text(scenario).lower()
    assert "feel" in text or "vibe" in text
    assert "target software" in text
    assert "receipt exists" not in text
    assert modes.unsafe_completion_claims(scenario) == []


def test_hermes_response_is_strategic_but_not_executor_like(tmp_path):
    read_model = _read_model(tmp_path)
    hermes = _profile(read_model, "hermes")
    scenario = _scenario(read_model, "architecture_controller_question")

    assert "horizon_aware" in hermes["style"]
    assert "recommend_system_shape" in hermes["allowed"]
    assert scenario["speaker_ref"] == "hermes"
    assert "sequence" in modes.primary_response_text(scenario).lower()
    assert "I will execute" not in modes.primary_response_text(scenario)
    assert "acting_like_executor" in hermes["forbidden"]


def test_no_response_claims_paid_sent_submitted_or_executed_without_proof(tmp_path):
    read_model = _read_model(tmp_path)

    for scenario in read_model["required_scenarios"]:
        assert modes.unsafe_completion_claims(scenario) == []


def test_no_response_grants_authority(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["authority_boundary"]["authority_grant_allowed"] is False
    for scenario in read_model["required_scenarios"]:
        assert scenario["authority_boundary"]["protected_actions_allowed"] is False
        assert scenario["authority_boundary"]["authority_grant_allowed"] is False


def test_no_machine_contract_jargon_in_primary_response(tmp_path):
    read_model = _read_model(tmp_path)

    for scenario in read_model["required_scenarios"]:
        assert modes.machine_contract_jargon_in_primary_response(scenario) == []


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == modes.READY_STATUS
    assert modes.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = modes.export_agent_response_voice_modes(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Agent Response Voice Modes.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == modes.READY_STATUS
    assert local == bridge
    assert modes.unsafe_true_grants(local) == []
    assert wiki.startswith("# Agent Response Voice Modes")
