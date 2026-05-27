import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_lm_activation_requirements as activation


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_activation_requirements_make_live_blockers_explicit():
    payload = activation.build_payload(generated_at=FIXED_NOW)
    receipts = {item["receipt_type"]: item for item in payload["activation_receipt_requirements"]}

    assert payload["live_lm1_activation_status"] == "NOT_READY"
    assert payload["live_lm2_activation_status"] == "NOT_READY"
    assert payload["provider_activation_status"] == "RECEIPTS_REQUIRED_NOT_PRESENT"
    assert "production_token_vault_ready_receipt" in receipts
    assert "provider_policy_receipt" in receipts
    assert "model_selection_policy_receipt" in receipts
    assert "live_model_enablement_receipt" in receipts
    assert "privacy_policy_receipt" in receipts
    assert "rollback_disable_receipt" in receipts
    assert "device_trust_live_activation_receipt" in receipts
    assert "real_lm_production_policy_receipt" in receipts
    assert receipts["provider_policy_receipt"]["blocks_provider_activation"] is True
    assert receipts["device_trust_live_activation_receipt"]["present"] is False
    assert receipts["real_lm_production_policy_receipt"]["present"] is False
    assert receipts["shadow_comparison_live_run_receipt"]["present"] is True
    assert payload["shadow_test_receipts"]["provider_policy_receipt"]["present"] is True
    assert payload["shadow_test_receipts"]["provider_policy_receipt"]["satisfies_production_activation"] is False
    assert payload["shadow_test_receipts"]["model_selection_policy_receipt"]["present"] is True
    assert payload["shadow_test_receipts"]["model_selection_policy_receipt"]["satisfies_production_activation"] is False
    assert all(
        item["present"] is False
        for item in payload["activation_receipt_requirements"]
        if item["receipt_type"] != "shadow_comparison_live_run_receipt"
    )


def test_activation_requirements_name_the_seven_production_beams():
    payload = activation.build_payload(generated_at=FIXED_NOW)
    beams = {item["beam_id"]: item for item in payload["production_activation_beams"]}
    proof = payload["machine_proof"]

    assert set(beams) == {
        "production_token_vault",
        "provider_model_receipts",
        "live_enablement_receipt",
        "privacy_receipt",
        "rollback_disable_receipt",
        "device_trust_live_activation",
        "real_lm_production_policy",
    }
    assert beams["provider_model_receipts"]["receipt_types"] == (
        "provider_policy_receipt",
        "model_selection_policy_receipt",
    )
    assert proof["production_activation_beam_count"] == 7
    assert proof["production_activation_beams_explicit"] is True
    assert proof["device_trust_live_activation_receipt_present"] is False
    assert proof["real_lm_production_policy_receipt_present"] is False
    assert "device_trust_live_activation_receipt_missing" in payload["hard_blockers"]
    assert "real_lm_production_policy_receipt_missing" in payload["hard_blockers"]


def test_activation_requirements_do_not_enable_models_or_actions():
    payload = activation.build_payload(generated_at=FIXED_NOW)
    proof = payload["machine_proof"]

    assert proof["live_lm_status"] == "NOT_ACTIVE"
    assert proof["provider_activation_receipts_present"] is False
    assert proof["privacy_policy_receipt_present"] is False
    assert proof["rollback_disable_receipt_present"] is False
    assert proof["device_trust_live_activation_receipt_present"] is False
    assert proof["real_lm_production_policy_receipt_present"] is False
    assert proof["live_shadow_comparison_receipt_present"] is True
    assert proof["live_shadow_model_call_recorded"] is True
    assert proof["shadow_provider_policy_receipt_present"] is True
    assert proof["shadow_model_selection_receipt_present"] is True
    assert proof["shadow_receipts_satisfy_production_activation"] is False
    assert proof["live_model_call_performed"] is False
    assert proof["model_api_call_performed"] is False
    assert proof["network_performed"] is False
    assert proof["tool_execution_performed"] is False
    assert proof["external_action_performed"] is False
    assert proof["all_live_authority_false"] is True


def test_activation_requirements_export_parses(tmp_path):
    payload = activation.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = activation.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == activation.READ_MODEL_ID
    assert parsed["machine_proof"]["missing_receipt_count"] >= 5
    assert "No production model, provider, tool, or action is enabled" in operator_path.read_text(encoding="utf-8")
