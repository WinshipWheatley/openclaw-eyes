import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_to_response_model_quality_comparison as comparison


FIXED_NOW = "2026-06-07T22:00:00+00:00"


def _model():
    return comparison.build_comparison_read_model(generated_at=FIXED_NOW)


def _candidate(model, ref):
    for row in model["candidate_comparisons"]:
        if row["candidate_ref"] == ref:
            return row
    raise AssertionError(f"missing candidate {ref}")


def _unsafe_true_grants(value, path="$"):
    unsafe = set(comparison.UNSAFE_TRUE_KEYS) | {"paid", "sent", "submitted", "authority_granted"}
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_grants(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_grants(child, f"{path}[{index}]"))
    return found


def test_comparison_is_ready_and_has_three_candidates():
    model = _model()

    assert model["status"] == comparison.READY_STATUS
    assert [row["candidate_ref"] for row in model["candidate_comparisons"]] == [
        "local_qwen_first_run",
        "external_synthetic_manual_response",
        "shadow_mock_baseline",
    ]
    assert model["comparison_scope"]["private_proof_compared"] is False
    assert model["comparison_scope"]["business_execution_compared"] is False


def test_local_qwen_first_run_records_non_json_failure():
    row = _candidate(_model(), "local_qwen_first_run")

    assert row["metrics"]["schema_compliance"] is False
    assert row["metrics"]["verifier_pass"] is False
    assert row["metrics"]["unsupported_claims_absent"] is True
    assert row["metrics"]["protected_action_safety"] is True
    assert row["evidence"]["failure_type"] == "non_json_structurally_invalid_empty_candidate"
    assert row["evidence"]["fallback_correctly_published"] is True
    assert row["quality_class"] == "not_ready"


def test_external_synthetic_response_passes_after_alignment():
    row = _candidate(_model(), "external_synthetic_manual_response")

    assert row["metrics"]["schema_compliance"] is True
    assert row["metrics"]["verifier_pass"] is True
    assert row["metrics"]["concision"] is True
    assert row["metrics"]["next_step_clarity"] is True
    assert row["evidence"]["synthetic_only"] is True
    assert row["evidence"]["published_as_real_finance_truth"] is False
    assert row["evidence"]["canonical_fact_ids"] == [
        "payment_evidence_missing",
        "processor_processing",
        "ledger_untouched",
        "paid_false",
        "no_email_sent",
        "no_coupa_submit",
        "no_ledger_mutation",
        "no_paid_marking",
    ]
    assert row["quality_class"] == "strong"


def test_shadow_mock_baseline_is_verifier_clean():
    row = _candidate(_model(), "shadow_mock_baseline")

    assert row["metrics"]["schema_compliance"] is True
    assert row["metrics"]["verifier_pass"] is True
    assert row["metrics"]["agent_voice_fit"] is True
    assert row["metrics"]["protected_action_safety"] is True
    assert row["evidence"]["all_pilot_drafts_verified"] is True
    assert row["quality_class"] == "strong"


def test_recommends_local_retry_with_schema_adapter():
    model = _model()

    assert model["recommended_next_test"] == "retry_local_with_schema_adapter"
    assert model["recommended_next_test"] in model["recommended_next_test_options"]
    assert any("did not return JSON" in reason for reason in model["reasons"])
    assert any("schema adapter" in reason for reason in model["reasons"])


def test_no_unsafe_true_grants():
    model = _model()

    assert model["authority_boundary"]["protected_actions_allowed"] is False
    assert model["implementation_boundary"]["external_llm_invoked"] is False
    assert model["implementation_boundary"]["prompt_sent"] is False
    assert model["machine_proof"]["truth_checks_loosened"] is False
    assert model["machine_proof"]["authority_checks_loosened"] is False
    assert not _unsafe_true_grants(model)


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = comparison.export_comparison(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof To Response Model Quality Comparison.md",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == comparison.READY_STATUS
    local = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert not _unsafe_true_grants(local)
    assert Path(result["wiki_path"]).exists()
