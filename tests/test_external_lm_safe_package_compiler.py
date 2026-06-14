import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_eligibility_policy
import external_lm_safe_package_compiler as compiler
import token_vault


def _finance_lm1_source(**overrides):
    source = {
        "source_request_id": "test_lm1_finance_package",
        "user_message": "what's next for the Capital Hilton invoice?",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "file_display_name": "Invoice Capitol Hilton Running.xlsx",
        "file_type": "spreadsheet",
        "artifact_kind": "running_invoice_workbook",
    }
    source.update(overrides)
    return source


def _finance_lm2_package(**overrides):
    package = {
        "source_request_id": "test_lm2_finance_package",
        "package_id": "role_package:test_lm2_finance_package",
        "role_identity": "CASSANDRA_CLARA",
        "task": "Draft client-safe invoice package wording for Capital Hilton; do not send.",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
        "tokenization_applied": True,
        "raw_values_included": False,
        "tool_policy": {"allowed_tools": (), "forbidden_tools": ("gmail", "browser", "ledger_writer")},
        "authority_policy": {
            "tool_authority_granted": False,
            "external_action_authority_granted": False,
            "send_submit_authority_granted": False,
        },
    }
    package.update(overrides)
    return package


def test_privacy_safe_lm1_package_compiles():
    result = compiler.compile_lm1_safe_package(_finance_lm1_source())
    package = result["safe_package"]

    assert result["package_status"] == compiler.PACKAGE_COMPILED
    assert package["lane"] == compiler.LM1
    assert package["model_class_recommended"] == external_lm_eligibility_policy.FAST_EXTERNAL_INTENT_MODEL
    assert package["external_lm_allowed"] is True
    assert package["ready_for_external_shadow"] is True
    assert package["lm_input_payload"]["tools_allowed"] == ()
    assert package["raw_values_included"] is False
    assert package["ready_for_production"] is False


def test_privacy_safe_lm2_package_compiles():
    result = compiler.compile_lm2_safe_package(_finance_lm2_package())
    package = result["safe_package"]

    assert result["package_status"] == compiler.PACKAGE_COMPILED
    assert package["lane"] == compiler.LM2
    assert package["model_class_recommended"] == external_lm_eligibility_policy.STRONG_EXTERNAL_ROLE_MODEL
    assert package["external_lm_allowed"] is True
    assert package["lm_input_payload"]["tools_allowed"] == ()
    assert all(value is False for value in package["authority_boundary"].values())


def test_raw_sensitive_value_causes_compile_block():
    result = compiler.compile_lm1_safe_package(
        _finance_lm1_source(user_message=token_vault.SYNTHETIC_VALUES["email"])
    )

    assert result["package_status"] == compiler.PACKAGE_BLOCKED
    assert "SOURCE_LEAK_SCAN_FAILED" in result["blocked_reasons"]
    assert result["safe_package"] is None


def test_credential_like_value_causes_compile_block():
    result = compiler.compile_lm1_safe_package(
        _finance_lm1_source(user_message="use api_key=sk-testsecret123 for this")
    )

    assert result["package_status"] == compiler.PACKAGE_BLOCKED
    assert "SOURCE_LEAK_SCAN_FAILED" in result["blocked_reasons"]
    assert result["eligibility_result"]["no_safe_model"] is True


def test_missing_eligibility_result_blocks_when_required():
    result = compiler.compile_lm1_safe_package(
        _finance_lm1_source(),
        require_existing_eligibility=True,
    )

    assert result["package_status"] == compiler.PACKAGE_BLOCKED
    assert result["blocked_reasons"] == ("MISSING_EXTERNAL_LM_ELIGIBILITY_RESULT",)


def test_strict_private_mode_blocks_external_package_compile():
    result = compiler.compile_lm1_safe_package(
        {
            "source_request_id": "test_strict_private",
            "user_message": "This is legal/private bank tax material.",
            "strict_private_mode_active": True,
        }
    )

    assert result["package_status"] == compiler.PACKAGE_BLOCKED
    assert result["eligibility_result"]["recommended_model_class"] == external_lm_eligibility_policy.LOCAL_ONLY_MODEL


def test_tokenized_package_has_token_refs_and_no_raw_values():
    result = compiler.compile_lm1_safe_package(_finance_lm1_source())
    package = result["safe_package"]
    text = json.dumps(package, sort_keys=True)

    assert package["token_scope"].startswith("scope:finance:client_")
    assert package["token_vault_ref"] == compiler.TOKEN_VAULT_REF
    assert "Capital Hilton" not in package["lm_input_payload"]["user_message"]
    assert "capital_hilton" not in json.dumps(package["lm_input_payload"], sort_keys=True)
    assert "Capital Hilton" not in json.dumps(package["lm_input_payload"], sort_keys=True)
    for raw in token_vault.SYNTHETIC_VALUES.values():
        assert raw not in text


def test_lm2_package_does_not_include_raw_client_task_values_when_tokenized():
    result = compiler.compile_lm2_safe_package(_finance_lm2_package())
    package = result["safe_package"]
    lm_payload_text = json.dumps(package["lm_input_payload"], sort_keys=True)

    assert "Capital Hilton" not in lm_payload_text
    assert "capital_hilton" not in lm_payload_text
    assert package["lm_input_payload"]["role_execution_package"]["client_ref"].startswith("client_ref_token:")
    assert package["lm_input_payload"]["role_execution_package"]["workflow_ref"].startswith("workflow_ref_token:")


def test_package_leak_scan_catches_raw_fixture_values():
    scan = compiler.scan_package_for_leaks({"message": token_vault.SYNTHETIC_VALUES["email"]})

    assert scan["passed"] is False
    assert scan["forbidden_raw_hits"]


def test_token_estimate_and_omitted_context_summary_are_present():
    result = compiler.compile_lm2_safe_package(_finance_lm2_package())
    package = result["safe_package"]

    assert package["estimated_token_count"] > 0
    assert "raw workbook/body/cell contents" in package["omitted_context_summary"]


def test_weather_low_sensitivity_does_not_require_tokenization_by_default():
    result = compiler.compile_lm1_safe_package(
        {
            "source_request_id": "test_weather",
            "user_message": "What is the weather pattern generally?",
            "world_ref": "general",
        }
    )
    package = result["safe_package"]

    assert result["package_status"] == compiler.PACKAGE_COMPILED
    assert package["sensitivity_class"] == compiler.SENSITIVITY_LOW
    assert package["tokenization_required"] is False
    assert package["tokenization_applied"] is False


def test_calendar_personal_request_is_minimized_and_classified_personal():
    result = compiler.compile_lm1_safe_package(
        {
            "source_request_id": "test_calendar",
            "user_message": "What is on my calendar tomorrow?",
            "world_ref": "personal",
        }
    )
    package = result["safe_package"]

    assert package["sensitivity_class"] == compiler.SENSITIVITY_PERSONAL
    assert package["tokenization_required"] is True
    assert "personal schedule item" in package["lm_input_payload"]["user_message"]


def test_client_finance_invoice_requires_tokenization_before_external_lm():
    result = compiler.compile_lm1_safe_package(_finance_lm1_source())
    package = result["safe_package"]

    assert package["sensitivity_class"] == compiler.SENSITIVITY_CLIENT_FINANCE
    assert package["tokenization_required"] is True
    assert package["tokenization_applied"] is True


def test_personal_finance_request_can_compile_external_safe_package():
    result = compiler.compile_lm1_safe_package(
        {
            "source_request_id": "test_personal_finance",
            "user_message": "Review bank ledger transaction dates, amounts, vendors, categories, and proposed ledger mappings.",
            "client_ref": "personal_finance",
        }
    )
    package = result["safe_package"]

    assert result["package_status"] == compiler.PACKAGE_COMPILED
    assert package["sensitivity_class"] == compiler.SENSITIVITY_PERSONAL_FINANCE
    assert package["external_lm_allowed"] is True
    assert package["raw_values_included"] is False


def test_legal_discovery_request_can_compile_external_safe_package():
    result = compiler.compile_lm2_safe_package(
        {
            "source_request_id": "test_legal_discovery",
            "task": "Summarize discovery matter metadata with privilege and confidentiality markers.",
            "world_ref": "legal",
        }
    )
    package = result["safe_package"]

    assert result["package_status"] == compiler.PACKAGE_COMPILED
    assert package["sensitivity_class"] == compiler.SENSITIVITY_LEGAL_DISCOVERY
    assert package["external_lm_allowed"] is True
    assert "privileged raw document bodies" in package["omitted_context_summary"]


def test_raw_bank_tax_identifier_blocks_external_package_compile():
    result = compiler.compile_lm1_safe_package(
        {
            "source_request_id": "test_raw_bank_identifier",
            "user_message": "Reconcile account number 1234567890 and routing 021000021.",
        }
    )

    assert result["package_status"] == compiler.PACKAGE_BLOCKED
    assert "SOURCE_LEAK_SCAN_FAILED" in result["blocked_reasons"]
    assert result["eligibility_result"]["no_safe_model"] is True


def test_no_lm_needed_is_possible_for_deterministic_simple_cases():
    result = compiler.compile_lm1_safe_package(
        {
            "source_request_id": "test_no_lm",
            "user_message": "ping",
            "deterministic_result_available": True,
        }
    )

    assert result["package_status"] == compiler.NO_LM_NEEDED
    assert result["no_lm_needed"] is True
    assert result["safe_package"] is None


def test_send_post_request_gains_no_authority_from_tokenization():
    result = compiler.compile_lm2_safe_package(_finance_lm2_package(task="Send the invoice now."))
    package = result["safe_package"]

    assert result["package_status"] == compiler.PACKAGE_COMPILED
    assert "block_sent_submitted_paid_posted_claims_without_receipts" in package["guardian_requirements"]
    assert package["lm_input_payload"]["authority_granted"]["send_submit"] is False
    assert package["external_lm_allowed"] is True


def test_exported_readmodel_parses(tmp_path):
    payload = compiler.build_payload()
    json_path, operator_path = compiler.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == compiler.READ_MODEL_ID
    assert parsed["machine_proof"]["lm1_safe_package_compiled"] is True
    assert parsed["machine_proof"]["lm2_safe_package_compiled"] is True
    assert parsed["machine_proof"]["raw_value_leak_blocked"] is True
    assert parsed["machine_proof"]["personal_finance_external_ready"] is True
    assert parsed["machine_proof"]["legal_discovery_external_ready"] is True
    assert "does not call models" in operator_path.read_text(encoding="utf-8")
