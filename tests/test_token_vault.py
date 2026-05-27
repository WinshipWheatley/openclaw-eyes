import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import token_vault


def test_synthetic_values_tokenize_stably_within_scope():
    first = token_vault.tokenize_synthetic_value("synthetic.person@example.invalid", scope="scope:a", token_kind="email")
    second = token_vault.tokenize_synthetic_value("synthetic.person@example.invalid", scope="scope:a", token_kind="email")

    assert first.token_id == second.token_id
    assert first.raw_value_included is False
    assert first.synthetic_fixture_only is True


def test_different_scopes_do_not_imply_same_raw_entity():
    first = token_vault.tokenize_synthetic_value("synthetic.person@example.invalid", scope="scope:a", token_kind="email")
    second = token_vault.tokenize_synthetic_value("synthetic.person@example.invalid", scope="scope:b", token_kind="email")

    assert first.token_id != second.token_id


def test_role_package_can_declare_tokenization_without_raw_values():
    declaration = token_vault.role_package_tokenization_declaration("scope:finance:capital_hilton")

    assert declaration["tokenization_applied"] is True
    assert declaration["raw_values_included"] is False
    assert declaration["tokenization_required"] is True
    assert declaration["model_may_see_raw_values"] is False
    assert declaration["detokenization_allowed"] is False
    assert declaration["safe_for_role_package"] is True


def test_tokenization_policy_raises_privacy_for_finance_client_files():
    policy = token_vault.evaluate_tokenization_policy(
        {
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "artifact_kind": "running_invoice_workbook",
            "file_type": "spreadsheet",
        }
    )

    assert policy["privacy_level"] == "CLIENT_FINANCE_FILE_METADATA"
    assert policy["tokenization_required"] is True
    assert policy["model_may_see_raw_values"] is False
    assert policy["detokenization_allowed"] is False
    assert policy["local_only_required"] is True
    assert "FINANCE_CONTEXT" in policy["reason_codes"]


def test_privacy_readiness_reports_production_token_vault_substrate_ready():
    readiness = token_vault.privacy_readiness_status()

    assert readiness["privacy_readiness_status"] == "PRODUCTION_TOKEN_VAULT_SUBSTRATE_READY_PRIVACY_RECEIPT_PRESENT_NO_LIVE_LM"
    assert readiness["production_token_vault_ready"] is True
    assert readiness["synthetic_tokenization_ready"] is True
    assert readiness["real_sensitive_data_allowed"] is False
    assert readiness["private_mode_requires_tokenization"] is True
    assert readiness["strict_private_requires_local_only"] is True
    assert readiness["cloud_lm_blocked_when_private"] is True


def test_production_token_vault_substrate_exists_without_raw_storage(tmp_path):
    db_path = tmp_path / "token_vault.sqlite"
    substrate = token_vault.ensure_production_token_vault_substrate(db_path)

    assert substrate["exists"] is True
    assert substrate["missing_tables"] == ()
    assert substrate["production_token_vault_ready"] is True
    assert substrate["production_token_vault_ready_receipt_present"] is True
    assert substrate["privacy_policy_receipt_present"] is True
    assert substrate["raw_value_columns_present"] is False
    assert substrate["real_sensitive_data_allowed"] is False


def test_production_activation_receipts_can_be_detected_from_local_substrate(tmp_path):
    db_path = tmp_path / "token_vault.sqlite"
    token_vault.ensure_production_token_vault_substrate(db_path)
    token_receipt = token_vault.production_token_vault_receipt_status(
        {
            "production_token_vault_ready": True,
            "scoped_entity_registry_ready": True,
            "scope_isolation_proven": True,
            "token_revocation_supported": True,
            "audit_log_supported": True,
            "raw_value_export_allowed": False,
            "cloud_tokenization_allowed": False,
            "credential_material_included": False,
        }
    )
    privacy_receipt = token_vault.privacy_policy_receipt_status(
        {
            "production_privacy_policy_ready": True,
            "private_mode_policy_defined": True,
            "strict_private_policy_defined": True,
            "raw_values_to_lm_default_denied": True,
            "detokenization_requires_receipt": True,
            "operator_visible_mode_choice_defined": True,
            "cloud_lm_blocked_when_private": True,
            "policy_rollback_supported": True,
            "raw_values_to_cloud_lm_allowed": False,
        }
    )

    assert token_receipt["present"] is True
    assert token_receipt["satisfies_live_lm_activation"] is True
    assert privacy_receipt["present"] is True
    assert privacy_receipt["satisfies_live_lm_activation"] is True


def test_generated_readmodel_does_not_expose_raw_synthetic_sensitive_values(tmp_path):
    payload = token_vault.build_payload()
    json_path, operator_path = token_vault.write_exports(payload, tmp_path)
    text = json_path.read_text(encoding="utf-8")

    for raw in token_vault.SYNTHETIC_VALUES.values():
        assert raw not in text
    assert "tok_email:" in text
    assert "No real sensitive values" in operator_path.read_text(encoding="utf-8")

    parsed = json.loads(text)
    assert parsed["machine_proof"]["raw_values_exported"] is False
    assert parsed["machine_proof"]["different_scope_token_differs"] is True
    assert parsed["machine_proof"]["finance_policy_tokenization_required"] is True
    assert parsed["machine_proof"]["finance_policy_blocks_raw_model_visibility"] is True
    assert parsed["privacy_readiness"]["production_token_vault_ready"] is True
    assert parsed["production_token_vault_substrate"]["production_token_vault_ready"] is True
    assert parsed["production_activation_receipts"]["production_token_vault_ready_receipt"]["present"] is True
    assert parsed["production_activation_receipts"]["privacy_policy_receipt"]["present"] is True
    assert parsed["machine_proof"]["cloud_lm_blocked_when_private"] is True
