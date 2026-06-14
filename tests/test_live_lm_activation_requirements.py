import json
import sqlite3
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
    assert "real_lm1_production_policy_receipt" in receipts
    assert "real_lm2_production_policy_receipt" in receipts
    assert receipts["provider_policy_receipt"]["blocks_provider_activation"] is True
    assert receipts["device_trust_live_activation_receipt"]["present"] is False
    assert receipts["real_lm1_production_policy_receipt"]["present"] is False
    assert receipts["real_lm2_production_policy_receipt"]["present"] is False
    assert receipts["shadow_comparison_live_run_receipt"]["present"] is True
    assert payload["shadow_test_receipts"]["provider_policy_receipt"]["present"] is True
    assert payload["shadow_test_receipts"]["provider_policy_receipt"]["satisfies_production_activation"] is False
    assert payload["shadow_test_receipts"]["model_selection_policy_receipt"]["present"] is True
    assert payload["shadow_test_receipts"]["model_selection_policy_receipt"]["satisfies_production_activation"] is False
    assert receipts["production_token_vault_ready_receipt"]["present"] is True
    assert receipts["privacy_policy_receipt"]["present"] is True
    assert all(
        item["present"] is False
        for item in payload["activation_receipt_requirements"]
        if item["receipt_type"]
        not in {"shadow_comparison_live_run_receipt", "production_token_vault_ready_receipt", "privacy_policy_receipt"}
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
    assert beams["real_lm_production_policy"]["receipt_types"] == (
        "real_lm1_production_policy_receipt",
        "real_lm2_production_policy_receipt",
    )
    assert beams["production_token_vault"]["status"] == "PRESENT"
    assert beams["privacy_receipt"]["status"] == "PRESENT"
    assert beams["provider_model_receipts"]["status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
    assert beams["live_enablement_receipt"]["status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
    assert beams["rollback_disable_receipt"]["status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
    assert beams["device_trust_live_activation"]["status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
    assert beams["real_lm_production_policy"]["status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
    assert proof["production_activation_beam_count"] == 7
    assert proof["production_activation_beams_explicit"] is True
    assert proof["production_token_vault_ready_receipt_present"] is True
    assert proof["privacy_policy_receipt_present"] is True
    assert proof["device_trust_live_activation_receipt_present"] is False
    assert proof["real_lm1_production_policy_receipt_present"] is False
    assert proof["real_lm2_production_policy_receipt_present"] is False
    assert "production_token_vault_inactive" not in payload["hard_blockers"]
    assert "production_privacy_policy_receipt_missing" not in payload["hard_blockers"]
    assert "device_trust_live_activation_receipt_missing" in payload["hard_blockers"]
    assert "real_lm1_production_policy_receipt_missing" in payload["hard_blockers"]
    assert "real_lm2_production_policy_receipt_missing" in payload["hard_blockers"]


def test_activation_beams_can_detect_future_production_receipt_presence_without_enabling_live():
    present = {
        "provider_policy_receipt": True,
        "model_selection_policy_receipt": True,
        "live_model_enablement_receipt": True,
        "rollback_disable_receipt": True,
        "device_trust_live_activation_receipt": True,
        "real_lm1_production_policy_receipt": True,
        "real_lm2_production_policy_receipt": True,
    }
    beams = {
        item["beam_id"]: item
        for item in activation.production_activation_beams(
            token_vault_receipt_present=True,
            privacy_policy_receipt_present=True,
            receipt_contracts_ready=True,
            production_receipts_present=present,
        )
    }

    assert all(item["status"] == "PRESENT" for item in beams.values())


def test_activation_receipt_contracts_ready_without_production_approval():
    payload = activation.build_payload(generated_at=FIXED_NOW)
    contracts = {item["receipt_type"]: item for item in payload["activation_receipt_contracts"]}
    fixtures = {item["receipt_type"]: item for item in payload["activation_receipt_fixture_results"]}
    proof = payload["machine_proof"]

    assert set(contracts) == {
        "provider_policy_receipt",
        "model_selection_policy_receipt",
        "live_model_enablement_receipt",
        "rollback_disable_receipt",
        "device_trust_live_activation_receipt",
        "real_lm1_production_policy_receipt",
        "real_lm2_production_policy_receipt",
    }
    assert proof["activation_receipt_contract_count"] == 7
    assert proof["activation_receipt_contracts_ready"] is True
    assert proof["activation_receipt_fixture_count"] == 7
    assert proof["activation_receipt_fixtures_valid"] is True
    assert proof["activation_receipt_fixtures_satisfy_production"] is False
    assert all(contract["can_be_collected_without_live_authority"] is True for contract in contracts.values())
    assert all(contract["production_receipt_required"] is True for contract in contracts.values())
    assert all(contract["operator_approval_required"] is True for contract in contracts.values())
    assert all(fixture["valid_as_test_fixture"] is True for fixture in fixtures.values())
    assert all(fixture["satisfies_production_activation"] is False for fixture in fixtures.values())


def test_activation_receipt_contracts_are_backed_by_local_sqlite_substrate(tmp_path):
    db_path = tmp_path / "activation_receipts.sqlite"
    substrate = activation.ensure_activation_receipt_substrate(db_path, generated_at=FIXED_NOW)

    assert substrate["exists"] is True
    assert substrate["missing_tables"] == ()
    assert substrate["contract_rows_persisted"] == 7
    assert substrate["fixture_validation_rows_persisted"] == 7
    assert substrate["production_receipt_rows_present"] == 0
    assert substrate["valid_production_receipt_rows_present"] == 0
    assert substrate["contracts_backed_by_sqlite"] is True
    assert substrate["fixtures_backed_by_sqlite"] is True
    assert substrate["production_receipt_intake_ready"] is True
    assert substrate["production_receipt_writer_authority_free"] is True
    assert substrate["satisfies_production_activation"] is False

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        production_rows = conn.execute("SELECT COUNT(*) FROM activation_production_receipts").fetchone()[0]
        fixture_prod_rows = conn.execute(
            "SELECT COUNT(*) FROM activation_receipt_fixture_validations WHERE satisfies_production_activation != 0"
        ).fetchone()[0]

    assert production_rows == 0
    assert fixture_prod_rows == 0


def _production_candidate(receipt_type: str) -> dict:
    contract = activation.activation_receipt_contract_by_type(receipt_type)
    return {
        "receipt_type": receipt_type,
        "test_fixture": False,
        "production_receipt": True,
        "operator_approved": True,
        "receipt_source": "governed_production_review",
        **{name: True for name in contract["required_true_controls"]},
        **{name: False for name in contract["required_false_controls"]},
    }


def test_governed_production_receipt_candidate_records_metadata_only(tmp_path):
    db_path = tmp_path / "activation_receipts.sqlite"
    result = activation.record_activation_production_receipt_candidate(
        "provider_policy_receipt",
        _production_candidate("provider_policy_receipt"),
        db_path,
        generated_at=FIXED_NOW,
    )
    substrate = activation.inspect_activation_receipt_substrate(db_path, create_if_missing=False)
    statuses = {
        item["receipt_type"]: item
        for item in activation.activation_production_receipt_statuses(db_path, create_if_missing=False)
    }

    assert result["recorded"] is True
    assert result["intake_status"] == "VALID_PRODUCTION_RECEIPT"
    assert result["payload_hash"].startswith("sha256:")
    assert substrate["production_receipt_rows_present"] == 1
    assert substrate["valid_production_receipt_rows_present"] == 1
    assert substrate["satisfies_production_activation"] is False
    assert statuses["provider_policy_receipt"]["present"] is True
    assert statuses["provider_policy_receipt"]["payload_hash"].startswith("sha256:")
    assert statuses["model_selection_policy_receipt"]["present"] is False

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT receipt_type, receipt_status, operator_approved, governed_review_source FROM activation_production_receipts"
        ).fetchall()

    assert rows == [("provider_policy_receipt", "VALID_PRODUCTION_RECEIPT", 1, 1)]


def test_governed_production_receipt_candidate_rejects_unsafe_or_unapproved_input(tmp_path):
    db_path = tmp_path / "activation_receipts.sqlite"
    unsafe = activation.record_activation_production_receipt_candidate(
        "provider_policy_receipt",
        {**_production_candidate("provider_policy_receipt"), "provider_api_call_enabled": True},
        db_path,
        generated_at=FIXED_NOW,
    )
    unapproved = activation.record_activation_production_receipt_candidate(
        "provider_policy_receipt",
        {**_production_candidate("provider_policy_receipt"), "operator_approved": False},
        db_path,
        generated_at=FIXED_NOW,
    )
    authority = activation.record_activation_production_receipt_candidate(
        "provider_policy_receipt",
        {**_production_candidate("provider_policy_receipt"), "tool_execution_allowed": True},
        db_path,
        generated_at=FIXED_NOW,
    )
    substrate = activation.inspect_activation_receipt_substrate(db_path, create_if_missing=False)

    assert unsafe["recorded"] is False
    assert unapproved["recorded"] is False
    assert authority["recorded"] is False
    assert substrate["production_receipt_rows_present"] == 0


def test_activation_receipt_validator_blocks_missing_or_unsafe_controls():
    provider_contract = activation.activation_receipt_contract_by_type("provider_policy_receipt")
    valid_fixture = {
        "receipt_type": "provider_policy_receipt",
        "test_fixture": True,
        "production_receipt": False,
        "operator_approved": False,
        "receipt_source": "test_fixture",
        **{name: True for name in provider_contract["required_true_controls"]},
        **{name: False for name in provider_contract["required_false_controls"]},
    }
    valid = activation.validate_activation_receipt_candidate("provider_policy_receipt", valid_fixture)
    unsafe = activation.validate_activation_receipt_candidate(
        "provider_policy_receipt",
        {**valid_fixture, "provider_api_call_enabled": True},
    )
    missing = activation.validate_activation_receipt_candidate(
        "provider_policy_receipt",
        {**valid_fixture, "provider_policy_defined": False},
    )

    assert valid["valid_for_contract"] is True
    assert valid["valid_as_test_fixture"] is True
    assert valid["satisfies_production_activation"] is False
    assert unsafe["valid_for_contract"] is False
    assert "provider_api_call_enabled" in unsafe["unsafe_true_controls"]
    assert missing["valid_for_contract"] is False
    assert "provider_policy_defined" in missing["missing_true_controls"]
    authority = activation.validate_activation_receipt_candidate(
        "provider_policy_receipt",
        {**valid_fixture, "tool_execution_allowed": True},
    )
    assert authority["valid_for_contract"] is False
    assert "tool_execution_allowed" in authority["unsafe_authority_controls"]


def test_activation_requirements_do_not_enable_models_or_actions():
    payload = activation.build_payload(generated_at=FIXED_NOW)
    proof = payload["machine_proof"]

    assert proof["live_lm_status"] == "NOT_ACTIVE"
    assert proof["provider_activation_receipts_present"] is False
    assert proof["production_token_vault_ready_receipt_present"] is True
    assert proof["privacy_policy_receipt_present"] is True
    assert proof["rollback_disable_receipt_present"] is False
    assert proof["device_trust_live_activation_receipt_present"] is False
    assert proof["real_lm1_production_policy_receipt_present"] is False
    assert proof["real_lm2_production_policy_receipt_present"] is False
    assert proof["activation_receipt_substrate_exists"] is True
    assert proof["activation_receipt_substrate_contract_rows"] == 7
    assert proof["activation_receipt_substrate_fixture_rows"] == 7
    assert proof["activation_receipt_substrate_production_rows"] == 0
    assert proof["activation_receipt_substrate_valid_production_rows"] == 0
    assert proof["activation_receipt_substrate_contracts_backed"] is True
    assert proof["activation_receipt_substrate_fixtures_backed"] is True
    assert proof["activation_production_receipt_intake_ready"] is True
    assert proof["activation_production_receipt_writer_authority_free"] is True
    assert proof["activation_production_receipt_status_count"] == 7
    assert proof["activation_production_receipts_present_count"] == 0
    assert proof["activation_receipt_substrate_satisfies_production"] is False
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
