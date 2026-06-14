import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import model_router_policy as policy


def test_model_router_selects_fast_cheap_class_for_low_risk_lm1_intent():
    decision = policy.select_model_class(
        {
            "request_id": "test_lm1",
            "chain_lane": "LM1_INTENT_PROPOSAL",
            "task_type": "intent_proposal",
            "role": "OPENCLAW_SYSTEM",
            "risk_level": "low",
            "sensitivity_level": "tokenized_client_finance_metadata",
            "context_size": "small",
            "requires_structured_output": True,
            "tokenization_applied": True,
            "raw_values_included": False,
            "external_lm_allowed": True,
            "package_minimized": True,
        }
    )

    assert decision["selected_model_class"] == policy.FAST_EXTERNAL_INTENT_MODEL
    assert decision["authority_boundary"]["authority_grant_allowed"] is False
    assert decision["confidence"] == "HIGH"
    assert policy.STRONG_EXTERNAL_ROLE_MODEL in decision["rejected_model_classes"]
    assert decision["selected_provider_ref"] == "provider_class:external_privacy_safe_fast_intent"
    assert decision["selected_provider_policy_id"]


def test_model_router_selects_stronger_class_for_lm2_role_package():
    decision = policy.select_model_class(
        {
            "request_id": "test_lm2",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "task_type": "role_response",
            "role": "CASSANDRA",
            "risk_level": "medium",
            "sensitivity_level": "tokenized_client_finance_metadata",
            "context_size": "medium",
            "requires_structured_output": True,
            "tokenization_applied": True,
            "raw_values_included": False,
            "external_lm_allowed": True,
            "package_minimized": True,
        }
    )

    assert decision["selected_model_class"] == policy.STRONG_EXTERNAL_ROLE_MODEL
    assert decision["structured_output_required"] is True
    assert "malformed structured output" in decision["expected_failure_modes"]
    assert decision["selected_provider_ref"] == "provider_class:external_privacy_safe_role_reasoner"
    assert decision["rejected_provider_candidates"]


def test_model_router_selects_external_role_model_for_tokenized_personal_finance():
    decision = policy.select_model_class(
        {
            "request_id": "test_personal_finance_router",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "task_type": "role_response",
            "role": "CASSANDRA",
            "risk_level": "medium",
            "sensitivity_level": "personal_finance_metadata",
            "context_size": "medium",
            "requires_structured_output": True,
            "tokenization_applied": True,
            "raw_values_included": False,
            "external_lm_allowed": True,
            "package_minimized": True,
        }
    )

    assert decision["selected_model_class"] == policy.STRONG_EXTERNAL_ROLE_MODEL
    assert decision["selected_provider_ref"] == "provider_class:external_privacy_safe_role_reasoner"


def test_model_router_selects_local_fallback_when_external_policy_blocked():
    decision = policy.select_model_class(
        {
            "request_id": "test_local_fallback",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "task_type": "role_response",
            "role": "CASSANDRA",
            "risk_level": "medium",
            "sensitivity_level": "client_finance_file_metadata",
            "context_size": "medium",
            "requires_structured_output": True,
            "tokenization_applied": False,
            "raw_values_included": False,
            "local_lm_required": True,
        }
    )

    assert decision["selected_model_class"] == policy.LOCAL_FALLBACK_MODEL
    assert decision["selected_provider_ref"] == "provider_class:local_or_private_fallback_model"


def test_model_router_blocks_weak_local_downgrade_testing_before_external_baseline():
    decision = policy.select_model_class(
        {
            "request_id": "test_downgrade_block",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "task_type": "role_response",
            "role": "CASSANDRA",
            "risk_level": "medium",
            "sensitivity_level": "tokenized_client_finance_metadata",
            "context_size": "medium",
            "requires_structured_output": True,
            "tokenization_applied": True,
            "raw_values_included": False,
            "external_lm_allowed": True,
            "package_minimized": True,
            "downgrade_testing_requested": True,
            "baseline_external_passed": False,
        }
    )

    assert decision["selected_model_class"] == policy.STRONG_EXTERNAL_ROLE_MODEL
    assert "LOCAL_DOWNGRADE_TESTING_BLOCKED_UNTIL_EXTERNAL_BASELINE_PASSES" in decision["risk_notes"]


def test_model_router_blocks_sensitive_raw_values_with_no_safe_model():
    decision = policy.select_model_class(
        {
            "request_id": "test_sensitive",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "task_type": "protected_boundary_response",
            "role": "GUARDIAN",
            "risk_level": "high",
            "sensitivity_level": "protected",
            "context_size": "medium",
            "requires_structured_output": True,
            "raw_values_included": True,
        }
    )

    assert decision["selected_model_class"] == policy.NO_SAFE_MODEL
    assert "RAW_SENSITIVE_VALUES_REQUIRE_TOKENIZATION" in decision["blocked_reasons"]
    assert "SENSITIVE_CONTEXT" in decision["risk_notes"]
    assert policy.FAST_EXTERNAL_INTENT_MODEL in decision["rejected_model_classes"]
    assert decision["selected_provider_ref"] == ""


def test_exported_readmodel_parses(tmp_path):
    payload = policy.build_payload()
    json_path, operator_path = policy.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == policy.READ_MODEL_ID
    assert parsed["machine_proof"]["lm1_example_selects_fast_class"] is True
    assert parsed["machine_proof"]["lm2_example_selects_stronger_class"] is True
    assert parsed["machine_proof"]["provider_policy_consulted"] is True
    assert "does not call models" in operator_path.read_text(encoding="utf-8")
