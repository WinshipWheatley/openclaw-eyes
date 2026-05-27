import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_eligibility_policy as policy


SUBSTRATE_READY = {
    "production_token_vault_ready": True,
    "privacy_policy_receipt_present": True,
}


def test_sensitive_finance_tokenized_package_is_external_eligible():
    result = policy.evaluate_external_lm_eligibility(
        {
            "recommended_lane": "LM2",
            "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
            "data_classes": ("CLIENT_FINANCE_FILE_METADATA", "MINIMIZED_ROLE_PACKAGE"),
            "tokenization_applied": True,
            "raw_values_included": False,
            "package_minimized": True,
            "context_minimization_applied": True,
            "privacy_policy_allows_external_model": True,
            "model_allowed_for_data_classes": True,
        },
        lane="LM2",
        substrate=SUBSTRATE_READY,
    )

    assert result["external_lm_allowed"] is True
    assert result["local_lm_required"] is False
    assert result["recommended_model_class"] == policy.STRONG_EXTERNAL_ROLE_MODEL
    assert "TOKENIZED_CLIENT_FINANCE_METADATA" in result["safe_data_classes"]
    assert result["live_production_activation_allowed"] is False


def test_sensitive_finance_raw_values_block_external():
    result = policy.evaluate_external_lm_eligibility(
        {
            "recommended_lane": "LM2",
            "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
            "data_classes": ("CLIENT_FINANCE_FILE_METADATA",),
            "tokenization_applied": True,
            "raw_values_included": True,
            "package_minimized": True,
        },
        lane="LM2",
        substrate=SUBSTRATE_READY,
    )

    assert result["external_lm_allowed"] is False
    assert result["local_lm_required"] is True
    assert "RAW_VALUES_INCLUDED_BLOCK_EXTERNAL" in result["reason_codes"]
    assert "RAW_PRIVATE_BODY" in result["blocked_data_classes"]


def test_strict_private_mode_requires_local_only():
    result = policy.evaluate_external_lm_eligibility(
        {
            "recommended_lane": "LM1",
            "privacy_level": "STRICT_PRIVATE_CLIENT_METADATA",
            "data_classes": ("STRICT_PRIVATE_CLIENT_METADATA",),
            "tokenization_applied": True,
            "raw_values_included": False,
            "package_minimized": True,
            "strict_private_mode_active": True,
        },
        lane="LM1",
        substrate=SUBSTRATE_READY,
    )

    assert result["external_lm_allowed"] is False
    assert result["local_lm_required"] is True
    assert result["recommended_model_class"] == policy.LOCAL_ONLY_MODEL


def test_credentials_or_secrets_have_no_safe_model():
    result = policy.evaluate_external_lm_eligibility(
        {
            "recommended_lane": "LM1",
            "privacy_level": "LOW_METADATA",
            "data_classes": ("LOW_METADATA",),
            "tokenization_applied": False,
            "raw_values_included": False,
            "package_minimized": True,
            "credentials_or_secrets_present": True,
        },
        lane="LM1",
        substrate=SUBSTRATE_READY,
    )

    assert result["external_lm_allowed"] is False
    assert result["no_safe_model"] is True
    assert result["recommended_model_class"] == policy.NO_SAFE_MODEL


def test_unminimized_package_blocks_external_but_allows_local_fallback():
    result = policy.evaluate_external_lm_eligibility(
        {
            "recommended_lane": "LM2",
            "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
            "data_classes": ("CLIENT_FINANCE_FILE_METADATA",),
            "tokenization_applied": True,
            "raw_values_included": False,
            "package_minimized": False,
        },
        lane="LM2",
        substrate=SUBSTRATE_READY,
    )

    assert result["external_lm_allowed"] is False
    assert result["recommended_model_class"] == policy.LOCAL_FALLBACK_MODEL
    assert "PACKAGE_NOT_MINIMIZED_BLOCK_EXTERNAL" in result["reason_codes"]


def test_exported_readmodel_parses(tmp_path):
    payload = policy.build_payload()
    json_path, operator_path = policy.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == policy.READ_MODEL_ID
    assert parsed["machine_proof"]["finance_lm1_external_eligible"] is True
    assert parsed["machine_proof"]["finance_lm2_external_eligible"] is True
    assert parsed["machine_proof"]["live_production_activation_allowed"] is False
    assert "Live production models remain off" in operator_path.read_text(encoding="utf-8")
