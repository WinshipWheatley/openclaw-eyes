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
    assert declaration["safe_for_role_package"] is True


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
