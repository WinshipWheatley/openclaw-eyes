import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_safe_package_compiler as compiler
import external_shadow_provider_config as provider_config
import provider_policy_registry


SECRET_FIXTURE_VALUE = "do-not-store-this-shadow-credential-value"


def _lm1_compile_result(**overrides):
    source = {
        "source_request_id": "external_shadow_provider_test_lm1",
        "user_message": "what's next for the Capital Hilton invoice?",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "file_display_name": "Invoice Capitol Hilton Running.xlsx",
        "artifact_kind": "running_invoice_workbook",
    }
    source.update(overrides)
    return compiler.compile_lm1_safe_package(source)


def _lm2_compile_result(**overrides):
    package = {
        "source_request_id": "external_shadow_provider_test_lm2",
        "package_id": "role_package:external_shadow_provider_test_lm2",
        "role_identity": "CASSANDRA_CLARA",
        "task": "Draft client-safe invoice package wording for Capital Hilton; do not send.",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
        "tokenization_applied": True,
        "raw_values_included": False,
    }
    package.update(overrides)
    return compiler.compile_lm2_safe_package(package)


def test_missing_credentials_returns_provider_not_configured():
    result = provider_config.select_provider_for_safe_package(_lm1_compile_result(), env={})

    assert result["status"] == provider_config.SHADOW_PROVIDER_NOT_CONFIGURED
    assert result["credentials_present"] is False
    assert "MISSING_SHADOW_CREDENTIAL" in result["blocked_reasons"]
    assert result["adapter_provider_config"]["external_shadow_enabled"] is False


def test_credential_presence_is_boolean_only_and_value_is_not_exposed():
    payload = provider_config.build_payload(
        env={"OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE}
    )
    text = provider_config.stable_json(payload)
    lm1_records = [
        record
        for record in payload["provider_configs"]
        if record["model_alias"] == provider_policy_registry.FAST_EXTERNAL_INTENT_MODEL
    ]

    assert lm1_records[0]["credentials_present"] is True
    assert lm1_records[0]["credential_value_exposed"] is False
    assert "redacted" in lm1_records[0]["credential_source_ref"]
    assert SECRET_FIXTURE_VALUE not in text
    assert "OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL" not in text
    assert "API_KEY" not in text


def test_lm1_provider_config_satisfies_fast_external_intent_alias():
    result = provider_config.select_provider_for_safe_package(
        _lm1_compile_result(),
        env={"OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE},
    )

    assert result["status"] == provider_config.SHADOW_CALL_READY
    assert result["shadow_call_ready"] is True
    assert result["model_alias"] == provider_policy_registry.FAST_EXTERNAL_INTENT_MODEL
    assert result["provider_ref"] == "provider_class:external_privacy_safe_fast_intent"


def test_lm2_provider_config_satisfies_strong_external_role_alias():
    result = provider_config.select_provider_for_safe_package(
        _lm2_compile_result(),
        env={"OPENCLAW_EXTERNAL_LM2_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE},
    )

    assert result["status"] == provider_config.SHADOW_CALL_READY
    assert result["shadow_call_ready"] is True
    assert result["model_alias"] == provider_policy_registry.STRONG_EXTERNAL_ROLE_MODEL
    assert result["provider_ref"] == "provider_class:external_privacy_safe_role_reasoner"


def test_production_remains_blocked_even_when_shadow_provider_is_configured():
    payload = provider_config.build_payload(
        env={"OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE}
    )

    assert payload["machine_proof"]["any_shadow_provider_configured"] is True
    assert payload["machine_proof"]["production_allowed"] is False
    assert all(value is False for value in payload["authority_boundary"].values())
    assert all(record["production_allowed"] is False for record in payload["provider_configs"])


def test_raw_private_package_cannot_use_external_provider():
    package = dict(_lm1_compile_result()["safe_package"])
    package["raw_values_included"] = True
    result = provider_config.select_provider_for_safe_package(
        package,
        env={"OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE},
    )

    assert result["status"] == provider_config.SHADOW_PROVIDER_POLICY_BLOCKED
    assert result["shadow_call_ready"] is False
    assert "RAW_VALUES_NOT_ALLOWED" in result["blocked_reasons"]


def test_strict_private_local_only_policy_blocks_external_provider():
    package = dict(_lm1_compile_result()["safe_package"])
    package["privacy_level"] = "STRICT_PRIVATE_CLIENT_METADATA"
    package["local_lm_required"] = True
    package["external_lm_allowed"] = False
    result = provider_config.select_provider_for_safe_package(
        package,
        env={"OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE},
    )

    assert result["status"] == provider_config.SHADOW_PROVIDER_POLICY_BLOCKED
    assert "STRICT_PRIVATE_LOCAL_ONLY" in result["blocked_reasons"]
    assert "LOCAL_ONLY_REQUIRED" in result["blocked_reasons"]


def test_safe_synthetic_package_can_reach_shadow_call_ready_state():
    result = provider_config.select_provider_for_safe_package(
        _lm2_compile_result(),
        env={"OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE},
    )

    assert result["status"] == provider_config.SHADOW_CALL_READY
    assert result["package_policy_passed"] is True
    assert result["production_allowed"] is False
    assert result["adapter_provider_config"]["external_shadow_enabled"] is True


def test_generated_read_model_contains_no_secret_values(tmp_path):
    payload = provider_config.build_payload(
        env={"OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL": SECRET_FIXTURE_VALUE}
    )
    json_path, operator_path = provider_config.write_exports(payload, tmp_path)

    json_text = json_path.read_text()
    operator_text = operator_path.read_text()
    json.loads(json_text)

    assert SECRET_FIXTURE_VALUE not in json_text
    assert SECRET_FIXTURE_VALUE not in operator_text
    assert "OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL" not in json_text
    assert "API_KEY" not in json_text
    assert "Production provider authority: false" in operator_text
