import json
import re
from pathlib import Path

import meaningful_work_gravity_contract as gravity
from scripts.export_meaningful_work_gravity_contract import main as export_main


FIXED_NOW = "2026-05-24T21:30:00+00:00"


def _build() -> dict:
    return gravity.build_meaningful_work_gravity_contract(generated_at=FIXED_NOW)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert gravity.stable_json(first) == gravity.stable_json(second)
    assert first["schema_version"] == gravity.SCHEMA_VERSION
    assert first["read_model_id"] == gravity.READ_MODEL_ID
    assert first["contract_status"] == gravity.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["live_compute_commons_activation_added"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["meaningful_work_gravity_contract_model_present"] is True
    assert proof["meaningful_work_signal_model_present"] is True
    assert proof["operator_sovereignty_guardrail_model_present"] is True
    assert proof["anti_sludge_detection_policy_model_present"] is True
    assert proof["compounding_opportunity_model_present"] is True
    assert proof["elioperator_nudge_model_present"] is True
    assert proof["compute_efficiency_signal_model_present"] is True
    assert proof["opt_in_compute_commons_concept_model_present"] is True
    assert proof["compute_commons_candidate_model_present"] is True
    assert proof["meaningful_work_builder_blocker_model_present"] is True
    assert schemas["meaningful_work_gravity_contract"]["required_fields"] == list(
        gravity.REQUIRED_CONTRACT_FIELDS
    )
    assert schemas["meaningful_work_signal"]["required_fields"] == list(gravity.REQUIRED_SIGNAL_FIELDS)
    assert schemas["operator_sovereignty_guardrail"]["required_fields"] == list(
        gravity.REQUIRED_SOVEREIGNTY_FIELDS
    )


def test_work_categories_and_sovereignty_guardrails_exist():
    payload = _build()
    guardrail = payload["operator_sovereignty_guardrail"]

    for category in gravity.WORK_CATEGORIES:
        assert category in payload["work_categories"]
    assert payload["machine_proof"]["all_work_categories_present"] is True
    assert guardrail["immediate_task_first"] is True
    assert guardrail["optional_expansion_only"] is True
    assert guardrail["no_moralizing"] is True
    assert guardrail["no_hidden_scope_expansion"] is True
    assert guardrail["no_gamified_score"] is True
    assert guardrail["no_task_hijack"] is True
    assert payload["machine_proof"]["operator_sovereignty_guardrails_present"] is True


def test_anti_sludge_policy_names_required_patterns():
    payload = _build()
    policy = payload["anti_sludge_detection_policy"]

    assert "repeated context rediscovery" in policy["sludge_patterns"]
    assert "looping agent retries" in policy["sludge_patterns"]
    assert "fake readback without state" in policy["sludge_patterns"]
    assert "UI success without backend proof" in policy["sludge_patterns"]
    assert "repeated bespoke shuttle prompts where a registry can help" in policy["sludge_patterns"]
    assert "broad scans instead of bounded read-model use" in policy["sludge_patterns"]
    assert "moralizing audit bloat" in policy["sludge_patterns"]
    assert "compute-saving analysis that itself burns unnecessary compute" in policy["sludge_patterns"]
    assert payload["machine_proof"]["anti_sludge_policy_present"] is True


def test_required_examples_exist():
    payload = _build()

    assert payload["machine_proof"]["capital_hilton_example_present"] is True
    assert payload["machine_proof"]["low_stakes_one_off_example_present"] is True
    assert payload["machine_proof"]["handoff_churn_example_present"] is True
    assert payload["machine_proof"]["privacy_improvement_example_present"] is True
    assert payload["machine_proof"]["compute_commons_candidate_example_present"] is True
    assert payload["machine_proof"]["blocked_compute_workload_example_present"] is True
    assert payload["machine_proof"]["agent_nudge_example_present"] is True
    assert payload["examples"]["capital_hilton"]["handling"] == "COMPLETE_AND_NOTE_BUILD_CUE"
    assert payload["examples"]["low_stakes_one_off"]["handling"] == "COMPLETE_DIRECTLY_ONLY"


def test_capital_hilton_and_privacy_examples_are_compounding_but_bounded():
    payload = _build()
    capital = payload["meaningful_work_signals_by_id"]["signal_capital_hilton_steel_thread"]
    privacy = payload["meaningful_work_signals_by_id"]["signal_privacy_tokenization"]

    assert capital["immediate_operator_value"] == "Move a real invoice closer to payment."
    assert capital["reusable_rail_potential"] == "high"
    assert "external authority gated" in capital["next_safe_move"]
    assert privacy["work_category"] == "safety_privacy_improvement"
    assert "raw sensitive values" in privacy["immediate_operator_value"].lower()
    assert "do not mutate a live vault" in privacy["next_safe_move"].lower()


def test_compute_efficiency_signal_avoids_fake_numeric_energy_claims():
    payload = _build()

    assert payload["machine_proof"]["compute_efficiency_avoids_fake_numeric_claims"] is True
    for signal in payload["compute_efficiency_signals_by_id"].values():
        combined = (
            signal["estimated_context_reduction"]
            + " "
            + signal["meaningful_work_per_watt_note"]
            + " "
            + signal["guardrail"]
        )
        assert "qualitative" in combined
        assert not re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|watt|kwh|tokens?)\b", combined.lower())


def test_opt_in_compute_commons_concept_is_default_off_and_consent_gated():
    payload = _build()
    concept = payload["opt_in_compute_commons_concept"]
    candidates = payload["compute_commons_candidates_by_id"]

    assert concept["opt_in_status"] == "DEFAULT_OFF_CONCEPT_ONLY"
    assert concept["audit_receipts_required"] is True
    assert "crypto mining" in concept["forbidden_uses"]
    assert "spam or fraud" in concept["forbidden_uses"]
    assert "surveillance" in concept["forbidden_uses"]
    assert "malware" in concept["forbidden_uses"]
    assert payload["machine_proof"]["compute_commons_default_off"] is True
    assert payload["machine_proof"]["compute_commons_opt_in_required"] is True
    assert candidates["candidate_public_good_validation_batch"]["eligibility_status"] == (
        "ELIGIBLE_FOR_OPERATOR_REVIEW"
    )
    assert candidates["candidate_unknown_external_gpu_file_access"]["eligibility_status"] == "BLOCKED_PRIVACY_RISK"
    assert candidates["candidate_opt_in_disabled_default"]["eligibility_status"] == "OPT_IN_DISABLED"


def test_builder_blockers_block_score_moralizing_hidden_scope_and_unbounded_commons():
    payload = _build()
    blockers = payload["builder_blockers_by_id"]

    assert blockers["blocker_visible_impact_score"]["blocker_type"] == "VISIBLE_IMPACT_SCORE"
    assert blockers["blocker_moralizing_language"]["blocker_type"] == "MORALIZING_LANGUAGE"
    assert blockers["blocker_hidden_scope_expansion"]["blocker_type"] == "HIDDEN_SCOPE_EXPANSION"
    assert blockers["blocker_unbounded_compute_commons"]["blocker_type"] == "UNBOUNDED_COMPUTE_COMMONS"
    assert blockers["blocker_opt_in_bypass"]["blocker_type"] == "OPT_IN_BYPASS"
    assert blockers["blocker_harmful_workload"]["blocker_type"] == "HARMFUL_WORKLOAD"
    for blocker in blockers.values():
        if blocker["blocker_type"] in {
            "VISIBLE_IMPACT_SCORE",
            "MORALIZING_LANGUAGE",
            "HIDDEN_SCOPE_EXPANSION",
            "UNBOUNDED_COMPUTE_COMMONS",
            "OPT_IN_BYPASS",
            "HARMFUL_WORKLOAD",
        }:
            assert blocker["fail_closed"] is True
            assert "ELIOPERATOR" in blocker["elioperator_warning"]
    assert payload["machine_proof"]["visible_score_gamification_blocked"] is True
    assert payload["machine_proof"]["moralizing_language_blocked"] is True
    assert payload["machine_proof"]["hidden_scope_expansion_blocked"] is True


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for value in payload["authority_boundary"].values():
        assert value is False
    for value in payload["gravity_contract"]["authority_boundary"].values():
        assert value is False


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])

    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")
    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_sensitive_fixture_values_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "PO-" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "meaningful_work_gravity_contract.py",
            "scripts/export_meaningful_work_gravity_contract.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
