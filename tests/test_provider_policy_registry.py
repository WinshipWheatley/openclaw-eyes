import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import provider_policy_registry as registry
import provider_lanes


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
    assert decision["selected_candidate_id"] == "kimi_openrouter"
    assert decision["selected_model_ref"]
    assert decision["selected_lane_id"] == "fast"
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
    assert decision["selected_candidate_id"] == "codex_exec"
    assert decision["selected_lane_id"] == "balanced"
    assert decision["fallback_policy_id"]
    assert decision["rejected_candidates"]


def test_external_provider_policy_accepts_tokenized_personal_finance_and_discovery_classes():
    personal = registry.select_provider_candidate(
        {
            "request_id": "test_provider_personal_finance",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "desired_model_class": registry.STRONG_EXTERNAL_ROLE_MODEL,
            "privacy_level": "TOKENIZED_PERSONAL_FINANCE_METADATA",
            "context_classes": ("TOKENIZED_PERSONAL_FINANCE_METADATA", "MINIMIZED_ROLE_PACKAGE"),
            "tokenization_applied": True,
            "raw_values_included": False,
            "local_only_required": False,
            "requires_structured_output": True,
        }
    )
    discovery = registry.select_provider_candidate(
        {
            "request_id": "test_provider_legal_discovery",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "desired_model_class": registry.STRONG_EXTERNAL_ROLE_MODEL,
            "privacy_level": "TOKENIZED_LEGAL_DISCOVERY_METADATA",
            "context_classes": ("TOKENIZED_LEGAL_DISCOVERY_METADATA", "MINIMIZED_ROLE_PACKAGE"),
            "tokenization_applied": True,
            "raw_values_included": False,
            "local_only_required": False,
            "requires_structured_output": True,
        }
    )

    assert personal["selected_model_class"] == registry.STRONG_EXTERNAL_ROLE_MODEL
    assert personal["selected_provider_ref"] == "provider_class:external_privacy_safe_role_reasoner"
    assert discovery["selected_model_class"] == registry.STRONG_EXTERNAL_ROLE_MODEL
    assert discovery["selected_provider_ref"] == "provider_class:external_privacy_safe_role_reasoner"


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
    assert decision["selected_candidate_id"] == provider_lanes.LOCAL_FLOOR_CANDIDATE
    assert decision["selected_model_ref"] == ""


def test_provider_policy_returns_no_safe_model_when_privacy_blocks_all_candidates():
    decision = registry.select_provider_candidate(
        {
            "request_id": "test_provider_blocked",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "desired_model_class": registry.STRONG_EXTERNAL_ROLE_MODEL,
            "privacy_level": "TOKENIZED_CLIENT_FINANCE_METADATA",
            "context_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA",),
            "tokenization_applied": False,
            "raw_values_included": True,
            "requires_structured_output": True,
        }
    )

    assert decision["selected_model_class"] == registry.NO_SAFE_MODEL
    assert decision["no_safe_model"] is True
    assert decision["selected_provider_ref"] == ""
    assert decision["selected_policy_id"] == ""
    assert decision["rejected_candidates"][0]["reason"] == "TOKENIZATION_REQUIRED_BEFORE_PROVIDER"


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
    assert all(item["reason"] for item in rejected)


def test_strict_private_and_unknown_labels_force_local():
    strict = registry.select_provider_candidate(
        {
            "request_id": "test_provider_strict",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "desired_model_class": registry.STRONG_EXTERNAL_ROLE_MODEL,
            "privacy_level": "STRICT_PRIVATE_CLIENT_METADATA",
            "context_classes": ("STRICT_PRIVATE_CLIENT_METADATA",),
            "tokenization_applied": True,
            "raw_values_included": False,
            "requires_structured_output": True,
        }
    )
    unknown = registry.select_provider_candidate(
        {
            "request_id": "test_provider_unknown",
            "chain_lane": "LM1_INTENT_PROPOSAL",
            "desired_model_class": registry.FAST_EXTERNAL_INTENT_MODEL,
            "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
            "context_classes": ("CLIENT_FINANCE_FILE_METADATA",),
            "tokenization_applied": True,
            "raw_values_included": False,
            "requires_structured_output": True,
        }
    )

    assert strict["selected_provider_ref"] == "provider_class:local_or_private_fallback_model"
    assert strict["selected_candidate_id"] == provider_lanes.LOCAL_FLOOR_CANDIDATE
    assert strict["no_safe_model"] is False
    assert unknown["selected_provider_ref"] == "provider_class:local_or_private_fallback_model"
    assert unknown["selected_candidate_id"] == provider_lanes.LOCAL_FLOOR_CANDIDATE
    assert unknown["selection_reason"] == "FORCED_LOCAL_LABEL_NOT_ALLOWLISTED"


def test_external_lm2_admitted_case_has_non_empty_rejected_candidates():
    decision = registry.select_provider_candidate(
        {
            "request_id": "test_provider_lm2_admitted",
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

    assert decision["selected_provider_ref"] == "provider_class:external_privacy_safe_role_reasoner"
    assert decision["rejected_candidates"]
    assert any(item["reason"] == "DISPATCH_DISABLED_P0" for item in decision["rejected_candidates"])


def test_exported_readmodel_parses(tmp_path):
    payload = registry.build_payload()
    json_path, operator_path = registry.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == registry.READ_MODEL_ID
    assert parsed["machine_proof"]["lm1_policy_selects_fast_candidate"] is True
    assert parsed["machine_proof"]["unknown_label_forces_local"] is True
    assert parsed["lanes_snapshot"]
    assert "No model call" in operator_path.read_text(encoding="utf-8")
