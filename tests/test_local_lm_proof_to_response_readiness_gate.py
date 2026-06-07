import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_to_response_readiness_gate as gate


FIXED_NOW = "2026-06-07T00:15:00+00:00"


def test_external_llm_blocked_by_default():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)
    classes = {row["model_harness_class"]: row for row in read_model["model_harness_classes"]}

    external = classes["external_llm_blocked_by_default"]
    assert external["allowed_for_live_pilot"] is False
    assert external["default_policy"] == "blocked_by_default"
    assert external["authority_boundary"]["external_provider_connect_allowed"] is False


def test_local_lm_allowed_only_in_shadow_response_mode():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)
    classes = {row["model_harness_class"]: row for row in read_model["model_harness_classes"]}

    shadow = classes["local_llm_shadow_mode"]
    future = classes["future_local_open_model"]
    assert shadow["allowed_for_response_drafting"] is True
    assert shadow["allowed_modes"] == ["proof_to_response_shadow_only"]
    assert shadow["business_execution_allowed"] is False
    assert future["allowed_for_live_pilot"] is False
    assert "explicit_operator_approval" in future["required_before_live"]


def test_proof_bundle_excludes_secrets_and_device_verification_material():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)
    excluded = set(read_model["data_boundaries"]["excluded_fields_and_material"])

    assert "operator_envelope" in excluded
    assert "device_verification_material" in excluded
    assert "session_verification_material" in excluded
    assert "credentials_or_tokens" in excluded
    assert "raw_prompt_dumps" in excluded
    assert "source_workbook_bodies" in excluded


def test_financial_sensitive_data_requires_redaction_local_only_policy():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)
    policy = read_model["data_boundaries"]["financial_sensitive_policy"]

    assert policy["raw_bank_details_allowed_to_model"] is False
    assert policy["required_privacy_class"] == "financial_sensitive/local_only"
    assert policy["redaction_required"] is True


def test_failed_verifier_blocks_publication():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)
    verifier = read_model["required_verifier_behavior"]

    assert verifier["all_lm_drafts_pass_proof_to_response_verifier"] is True
    assert verifier["failed_drafts_publish_safe_fallback"] is True
    assert verifier["unsafe_draft_text_published"] is False
    assert "unsupported_paid_sent_submitted_executed_claims" in verifier["blocked_claims"]


def test_no_authority_grant_possible_from_lm_draft():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)

    assert read_model["authority_boundary"]["authority_grant_allowed"] is False
    assert read_model["required_verifier_behavior"]["no_authority_grants"] is True
    assert read_model["implementation_boundary"]["business_action_performed"] is False


def test_first_pilot_scope_limited_to_proof_to_response_only():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)

    assert read_model["allowed_first_pilot_scope"] == [
        "finance_capital_hilton_payment_watch",
        "business_development_capital_hilton_followup",
        "finance_live_arts_md_evidence",
        "build_informational_review",
        "self_heal_repair_explanation",
    ]
    assert read_model["scope_boundary"]["proof_to_response_only"] is True
    assert "business_action_execution" in read_model["explicitly_blocked"]
    assert "memory_promotion_to_truth" in read_model["explicitly_blocked"]


def test_readiness_decision_and_next_safe_action():
    read_model = gate.build_read_model(generated_at=FIXED_NOW)

    assert read_model["status"] == gate.READY_STATUS
    assert read_model["readiness_decision"]["ready_for_live_local_lm_pilot"] is False
    assert "explicit_operator_approval_missing" in read_model["readiness_decision"]["blockers"]
    assert read_model["readiness_decision"]["next_safe_action"] == "Run another verifier-gated shadow/mock pilot or request explicit approval for a local-only model harness."


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = gate.export_local_lm_proof_to_response_readiness_gate(
        read_model_root=ROOT / "generated/read_models",
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof To Response Readiness Gate.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == gate.READY_STATUS
    assert local == bridge
    assert gate.unsafe_true_grants(local) == []
    assert Path(result["wiki_path"]).read_text(encoding="utf-8").startswith("# Local LM Proof To Response Readiness Gate")
