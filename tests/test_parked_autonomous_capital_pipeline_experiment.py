import json
import re
from pathlib import Path

import parked_autonomous_capital_pipeline_experiment as contract


FIXED_NOW = "2026-05-22T16:00:00+00:00"


def _build() -> dict:
    return contract.build_parked_autonomous_capital_pipeline_experiment(generated_at=FIXED_NOW)


def _phase(payload: dict, phase_id: str) -> dict:
    return {item["phase_id"]: item for item in payload["five_phase_roadmap"]}[phase_id]


def _track(payload: dict, track_id: str) -> dict:
    return {item["track_id"]: item for item in payload["conceptual_architecture"]}[track_id]


def test_experiment_is_deterministic_and_parked_high_risk():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["experiment_name"] == contract.EXPERIMENT_NAME
    assert first["experiment_status"] == "PARKED_HIGH_RISK_R_AND_D_EXPERIMENT"
    assert first["contract_type"] == "parked_r_and_d_thought_experiment"
    assert first["machine_proof"]["experiment_status_is_parked_high_risk"] is True
    assert first["machine_proof"]["phase_count"] == 5
    assert first["machine_proof"]["architecture_track_count"] == 4


def test_all_authority_flags_are_false_and_no_live_action_is_granted():
    payload = _build()

    assert set(payload["no_action_authority_matrix"]) == set(contract.NO_ACTION_AUTHORITY_FLAGS)
    for key, value in payload["no_action_authority_matrix"].items():
        assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["no_spending_authority"] is True
    assert payload["machine_proof"]["no_financial_account_authority"] is True
    assert payload["machine_proof"]["no_account_creation_authority"] is True
    assert payload["machine_proof"]["no_network_authority"] is True
    assert payload["machine_proof"]["no_model_tool_agent_runtime_authority"] is True
    assert payload["machine_proof"]["no_queue_autonomy_authority"] is True
    assert payload["machine_proof"]["no_deployment_acquisition_payout_authority"] is True


def test_architecture_tracks_are_preserved_as_blocked_concepts():
    payload = _build()

    zero = _track(payload, "zero_human_control_experiment")
    hybrid = _track(payload, "hybrid_human_variable_experiment")
    meta = _track(payload, "meta_ceo_differential_layer")
    capstone = _track(payload, "business_3_sovereign_shell_capstone")

    assert zero["current_status"] == "BLOCKED_CONCEPT_ONLY"
    assert "deployment" in zero["blocked_actions"]
    assert "spend" in zero["blocked_actions"]
    assert hybrid["current_status"] == "BLOCKED_CONCEPT_ONLY"
    assert "external action" in hybrid["blocked_actions"]
    assert meta["current_status"] == "CONCEPTUAL_ONLY"
    assert "authority delegation" in meta["blocked_actions"]
    assert capstone["current_status"] == "SPECULATIVE_PARKED"
    assert "implementation" in capstone["blocked_actions"]


def test_five_phase_roadmap_is_future_gated_and_blocks_spend_deployments_accounts_and_payouts():
    payload = _build()

    phase_1 = _phase(payload, "zero_infrastructure_bootstrapping")
    assert phase_1["current_status"] == "BLOCKED_FUTURE_GATED"
    assert "spending" in phase_1["blocked_actions"]
    assert "domain purchase" in phase_1["blocked_actions"]
    assert "checkout creation" in phase_1["blocked_actions"]
    assert "account creation" in phase_1["blocked_actions"]

    phase_2 = _phase(payload, "micro_saas_self_hosted_compute")
    assert "cloud accounts" in phase_2["blocked_actions"]
    assert "API keys" in phase_2["blocked_actions"]
    assert "paid compute" in phase_2["blocked_actions"]

    phase_3 = _phase(payload, "portfolio_diversification_automated_acquisition")
    assert "acquisitions" in phase_3["blocked_actions"]
    assert "payments" in phase_3["blocked_actions"]
    assert "external account access" in phase_3["blocked_actions"]

    phase_4 = _phase(payload, "autonomous_treasury_dividend_routing")
    assert "payouts" in phase_4["blocked_actions"]
    assert "banking" in phase_4["blocked_actions"]
    assert "outbound financial transfers" in phase_4["blocked_actions"]

    phase_5 = _phase(payload, "business_3_sovereign_shell")
    assert phase_5["current_status"] == "SPECULATIVE_NOT_ACTIONABLE"


def test_allowed_tokens_are_future_concepts_only_and_do_not_grant_budget_or_account_authority():
    payload = _build()
    tokens = payload["allowed_tokens"]

    assert tokens["status"] == "FUTURE_CONCEPT_ONLY"
    assert tokens["tokens_exist_now"] is False
    assert tokens["tokens_grant_external_spend"] is False
    assert tokens["tokens_grant_account_access"] is False
    assert tokens["tokens_bypass_guardian_operator_gates"] is False
    assert tokens["tokens_must_be_scoped_receipted_revocable_capped"] is True
    assert [item["token_type"] for item in tokens["token_types"]] == list(contract.TOKEN_TYPES)
    for token in tokens["token_types"]:
        assert token["status"] == "FUTURE_CONCEPT_ONLY"
        assert token["current_authority"] == "NONE"
        assert "tokens_do_not_grant_external_spend" in token["rules"]
        assert "tokens_do_not_grant_account_access" in token["rules"]


def test_future_gates_required_before_any_actuation():
    payload = _build()

    assert set(payload["required_future_gates"]) == set(contract.REQUIRED_FUTURE_GATES)
    assert all(payload["required_future_gates"].values())
    for required_gate in [
        "security_pass_vnext_required",
        "operator_budget_token_required",
        "legal_compliance_review_required",
        "tax_accounting_review_required",
        "external_account_policy_required",
        "payment_processor_policy_required",
        "guardian_gate_required",
        "operator_final_approval_required",
        "chief_test_harness_required",
        "hermes_architecture_review_required",
        "full_trust_clearance_required",
    ]:
        assert payload["required_future_gates"][required_gate] is True
    assert payload["machine_proof"]["required_future_gates_all_true"] is True


def test_operator_questions_create_memory_candidates_not_proof():
    payload = _build()
    questions = payload["experiment_safety_questions"]

    assert questions["operator_answers_become_memory_candidates"] is True
    assert questions["operator_answers_are_proof"] is False
    assert len(questions["questions"]) == 12
    for question in questions["questions"]:
        assert question["answer_status"] == "UNANSWERED"
        assert question["answer_becomes"] == "MEMORY_CANDIDATE_RECEIPT"
        assert question["proof_status"] == "OPERATOR_ANSWER_IS_NOT_PROOF"
    assert payload["machine_proof"]["operator_answers_are_memory_candidates_not_proof"] is True


def test_experiment_is_security_stress_test_artifact_and_relationship_to_security_pass_is_read_only_only():
    payload = _build()
    stress = payload["security_stress_test_classification"]
    relationship = payload["relationship_to_current_security_pass"]
    batch = payload["post_security_governance_batch_relationship"]

    assert stress["is_security_stress_test_artifact"] is True
    assert stress["current_security_relevance"] == "HIGH"
    for area in [
        "budget authority",
        "external account boundaries",
        "payment/payout systems",
        "tool/model/agent execution gates",
        "FULL_TRUST_CLEARANCE",
        "kill-switch posture",
    ]:
        assert area in stress["stress_test_areas"]
    assert stress["authorizes_action"] is False
    assert relationship["read_only_preview_modeling_allowed"] is True
    assert relationship["parked_breadcrumb_allowed"] is True
    assert relationship["action_authority_granted"] is False
    assert relationship["financial_authority_granted"] is False
    assert relationship["spend_authority_granted"] is False
    assert relationship["deployment_authority_granted"] is False
    assert batch["batch_id"] == "post_security_governance_batch_v0"
    assert batch["prompt_index"] == 1
    assert batch["stable_map_refresh_deferred"] is True
    assert batch["commit_deferred_until_prompt_5"] is True
    assert batch["action_authority_granted"] is False


def test_no_credentials_external_urls_or_raw_private_bodies_are_included():
    payload = _build()
    text = contract.stable_json(payload)

    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["external_urls_or_api_calls_required"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    assert "http" + "://" not in text
    assert "https" + "://" not in text
    secret_patterns = [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_-]{20,}",
        r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY",
    ]
    for pattern in secret_patterns:
        assert re.search(pattern, text) is None


def test_export_writes_json_and_operator_markdown(tmp_path):
    result = contract.export_parked_autonomous_capital_pipeline_experiment(
        repo_root=tmp_path,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    json_path = Path(result.json_path)
    operator_path = Path(result.operator_path)

    assert json_path.exists()
    assert operator_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator_text = operator_path.read_text(encoding="utf-8")
    assert payload["experiment_status"] == "PARKED_HIGH_RISK_R_AND_D_EXPERIMENT"
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert "ELIWINSHIP Summary" in operator_text
    assert "Current authority: none." in operator_text
    assert "Tokens grant external spend: `false`." in operator_text
    assert "Post-Security Governance Batch" in operator_text
    assert "Stable-map refresh is deferred until Prompt 5." in operator_text
