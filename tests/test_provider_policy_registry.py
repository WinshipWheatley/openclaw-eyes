import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import provider_policy_registry as registry


def test_provider_policy_registry_lists_candidate_model_classes_without_live_calls():
    payload = registry.build_payload()

    records = payload["provider_policy_records"]
    classes = {record["model_class_ref"] for record in records}
    assert registry.FAST_EXTERNAL_INTENT_MODEL in classes
    assert registry.STRONG_EXTERNAL_ROLE_MODEL in classes
    assert registry.LOCAL_FALLBACK_MODEL in classes
    assert registry.LOCAL_ONLY_MODEL in classes
    assert registry.FAST_STRUCTURED_INTENT_SMALL in classes
    assert registry.STRONG_STRUCTURED_ROLE_REASONER in classes
    assert registry.CONSERVATIVE_SENSITIVE_STRUCTURED in classes
    assert payload["machine_proof"]["live_model_call_performed"] is False
    assert payload["machine_proof"]["network_performed"] is False


def test_lm1_provider_policy_selects_fast_structured_candidate():
    decision = registry.select_provider_candidate(
        {
            "request_id": "test_provider_lm1",
            "chain_lane": "LM1_INTENT_PROPOSAL",
            "desired_model_class": registry.FAST_EXTERNAL_INTENT_MODEL,
            "privacy_level": "TOKENIZED_CLIENT_FINANCE_METADATA",
            "context_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA", "MACHINE_INTENT_PROPOSAL_SCHEMA"),
            "tokenization_applied": True,
            "raw_values_included": False,
            "local_only_required": False,
            "requires_structured_output": True,
        }
    )

    assert decision["selected_model_class"] == registry.FAST_EXTERNAL_INTENT_MODEL
    assert decision["selected_provider_ref"] == "provider_class:external_privacy_safe_fast_intent"
    assert decision["no_safe_model"] is False


def test_lm2_provider_policy_selects_stronger_structured_candidate():
    decision = registry.select_provider_candidate(
        {
            "request_id": "test_provider_lm2",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "desired_model_class": registry.STRONG_EXTERNAL_ROLE_MODEL,
            "privacy_level": "TOKENIZED_CLIENT_FINANCE_METADATA",
            "context_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA", "MINIMIZED_ROLE_PACKAGE"),
            "tokenization_applied": True,
            "raw_values_included": False,
            "local_only_required": False,
            "requires_structured_output": True,
        }
    )

    assert decision["selected_model_class"] == registry.STRONG_EXTERNAL_ROLE_MODEL
    assert decision["selected_provider_ref"] == "provider_class:external_privacy_safe_role_reasoner"
    assert decision["fallback_policy_id"]


def test_local_fallback_provider_selected_when_external_policy_blocked():
    decision = registry.select_provider_candidate(
        {
            "request_id": "test_provider_local_fallback",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "desired_model_class": registry.LOCAL_FALLBACK_MODEL,
            "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
            "context_classes": ("CLIENT_FINANCE_FILE_METADATA",),
            "tokenization_applied": False,
            "raw_values_included": False,
            "local_only_required": True,
            "requires_structured_output": True,
        }
    )

    assert decision["selected_model_class"] == registry.LOCAL_FALLBACK_MODEL
    assert decision["selected_provider_ref"] == "provider_class:local_or_private_fallback_model"


def test_provider_policy_returns_no_safe_model_when_privacy_blocks_all_candidates():
    decision = registry.select_provider_candidate(
        {
            "request_id": "test_provider_blocked",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "desired_model_class": registry.STRONG_EXTERNAL_ROLE_MODEL,
            "privacy_level": "RAW_PRIVATE_BODY",
            "context_classes": ("RAW_PRIVATE_BODY",),
            "tokenization_applied": False,
            "raw_values_included": True,
            "requires_structured_output": True,
        }
    )

    assert decision["selected_model_class"] == registry.NO_SAFE_MODEL
    assert decision["no_safe_model"] is True
    assert all("RAW_VALUES_NOT_ALLOWED" in item["reject_reasons"] for item in decision["rejected_candidates"])


def test_rejected_candidates_include_reasons_and_expected_weaknesses():
    decision = registry.select_provider_candidate(
        {
            "request_id": "test_provider_rejections",
            "chain_lane": "LM1_INTENT_PROPOSAL",
            "desired_model_class": registry.FAST_EXTERNAL_INTENT_MODEL,
            "privacy_level": "TOKENIZED_CLIENT_FINANCE_METADATA",
            "context_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA", "MACHINE_INTENT_PROPOSAL_SCHEMA"),
            "tokenization_applied": True,
            "raw_values_included": False,
            "local_only_required": False,
            "requires_structured_output": True,
        }
    )

    rejected = decision["rejected_candidates"]
    assert rejected
    assert all(item["reject_reasons"] for item in rejected)
    assert all(item["weaknesses"] for item in rejected)


def test_exported_readmodel_parses(tmp_path):
    payload = registry.build_payload()
    json_path, operator_path = registry.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == registry.READ_MODEL_ID
    assert parsed["machine_proof"]["lm1_policy_selects_fast_candidate"] is True
    assert "No model call" in operator_path.read_text(encoding="utf-8")
