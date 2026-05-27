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
            "sensitivity_level": "low",
            "context_size": "small",
            "requires_structured_output": True,
        }
    )

    assert decision["selected_model_class"] == policy.FAST_STRUCTURED_INTENT_SMALL
    assert decision["authority_boundary"]["authority_grant_allowed"] is False
    assert decision["confidence"] == "HIGH"
    assert policy.STRONG_STRUCTURED_ROLE_REASONER in decision["rejected_model_classes"]


def test_model_router_selects_stronger_class_for_lm2_role_package():
    decision = policy.select_model_class(
        {
            "request_id": "test_lm2",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "task_type": "role_response",
            "role": "CASSANDRA",
            "risk_level": "medium",
            "sensitivity_level": "low",
            "context_size": "medium",
            "requires_structured_output": True,
        }
    )

    assert decision["selected_model_class"] == policy.STRONG_STRUCTURED_ROLE_REASONER
    assert decision["structured_output_required"] is True
    assert "malformed structured output" in decision["expected_failure_modes"]


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
    assert policy.FAST_STRUCTURED_INTENT_SMALL in decision["rejected_model_classes"]


def test_exported_readmodel_parses(tmp_path):
    payload = policy.build_payload()
    json_path, operator_path = policy.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == policy.READ_MODEL_ID
    assert parsed["machine_proof"]["lm1_example_selects_fast_class"] is True
    assert parsed["machine_proof"]["lm2_example_selects_stronger_class"] is True
    assert "does not call models" in operator_path.read_text(encoding="utf-8")
