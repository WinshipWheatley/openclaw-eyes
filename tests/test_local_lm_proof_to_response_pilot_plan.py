import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_to_response_pilot_plan as plan
import proof_bundle_redaction_policy as redaction_policy


FIXED_NOW = "2026-06-07T04:05:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "local_lm_proof_to_response_readiness_gate.json", {"status": "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"})
    _write_json(root / "local_lm_harness_inventory_receipts.json", {"status": "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY"})
    _write_json(root / "proof_bundle_redaction_policy.json", {"status": "PROOF_BUNDLE_REDACTION_HARDENING_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(root / "agent_response_voice_modes.json", {"status": "AGENT_RESPONSE_VOICE_MODES_READY"})
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
    return root


def _candidate(read_model: dict, harness_ref: str) -> dict:
    return {row["harness_ref"]: row for row in read_model["candidate_source_options"]}[harness_ref]


def test_plan_chooses_low_risk_first_pilot_lane(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    lane = read_model["first_pilot_lane"]

    assert lane["world_ref"] == "finance"
    assert lane["thread_ref"] == "capital_hilton"
    assert lane["objective_ref"] == "capital_hilton_payment_watch"
    assert lane["risk_class"] == "low_action_risk"
    assert "low action risk" in lane["reason"]
    assert "Payment evidence is missing" in lane["expected_response"]


def test_plan_does_not_mark_live_invocation_ready_without_explicit_approval(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    status = read_model["pilot_status"]

    assert status["ready_for_operator_approval"] is True
    assert status["ready_for_live_invocation"] is False
    assert status["required_operator_approval_ref"] == "operator_approval_receipt:local_lm_proof_response_pilot:v0"
    assert "operator_approval_receipt" in status["missing_live_receipts"]


def test_external_llm_blocked_by_default(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    external = _candidate(read_model, "external_llm_blocked_by_default")

    assert external["allowed_now"] is False
    assert external["reason"] == "external_provider_blocked_by_default"
    assert external["privacy_risk"] == "unacceptable_for_default_local_private_proof"


def test_hermes_sidecar_blocked_unless_registered_receipted(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    hermes = _candidate(read_model, "hermes_sidecar_candidate")

    assert hermes["allowed_now"] is False
    assert hermes["reason"] == "blocked_until_explicit_registration_and_receipts"
    assert "explicit_hermes_proof_to_response_registration" in hermes["missing_receipts"]


def test_proof_bundle_allowed_fields_match_redaction_policy(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["allowed_lm_input_fields"] == list(redaction_policy.ALLOWED_FIELD_REASONS)


def test_forbidden_fields_excluded(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    forbidden = set(read_model["forbidden_lm_input"])

    assert "raw_finance_details" in forbidden
    assert "bank_account_numbers" in forbidden
    assert "credentials_tokens" in forbidden
    assert "operator_device_session_verification_secrets" in forbidden
    assert "raw_artifact_ocr_text" in forbidden
    assert "authority_granted_fields" in forbidden


def test_verifier_is_mandatory(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["pilot_runtime_flow"][3]["step_ref"] == "run_deterministic_verifier"
    assert all(row["verifier_requirement"] == "proof_to_response_verifier_mandatory" for row in read_model["candidate_source_options"])
    assert "verifier_pass_fail_receipt" in read_model["required_receipts_before_live_invocation"]


def test_stop_conditions_include_unsafe_claims_and_protected_actions(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    stop_conditions = set(read_model["stop_conditions"])

    assert "model_claims_paid_sent_submitted" in stop_conditions
    assert "model_proposes_protected_action" in stop_conditions
    assert "verifier_fails" in stop_conditions
    assert "external_provider_path_appears" in stop_conditions


def test_no_unsafe_true_grants(tmp_path):
    read_model = plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == plan.READY_STATUS
    assert plan.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = plan.export_local_lm_proof_to_response_pilot_plan(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof To Response Pilot Plan.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == plan.READY_STATUS
    assert local == bridge
    assert plan.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Proof To Response Pilot Plan")
