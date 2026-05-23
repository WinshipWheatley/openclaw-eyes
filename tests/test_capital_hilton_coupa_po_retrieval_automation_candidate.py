import json
from pathlib import Path

import capital_hilton_coupa_po_retrieval_automation_candidate as candidate
from scripts.export_capital_hilton_coupa_po_retrieval_automation_candidate import main as export_main


FIXED_NOW = "2026-05-23T16:00:00+00:00"


def _build() -> dict:
    return candidate.build_capital_hilton_coupa_po_retrieval_automation_candidate(generated_at=FIXED_NOW)


def _default_candidate(payload: dict) -> dict:
    return payload["automation_candidates"][0]


def _trial_stage(payload: dict, stage_id: str) -> dict:
    return next(stage for stage in payload["trial_ladder"] if stage["stage_id"] == stage_id)


def test_contract_is_deterministic_and_models_default_coupa_candidate():
    payload = _build()

    assert candidate.stable_json(payload) == candidate.stable_json(_build())
    assert payload["schema_version"] == candidate.SCHEMA_VERSION
    assert payload["read_model_id"] == candidate.READ_MODEL_ID
    assert payload["contract_status"] == "deterministic_future_automation_candidate_no_current_authority"
    assert payload["machine_proof"]["default_candidate_exists"] is True
    assert payload["machine_proof"]["candidate_count"] == 1

    record = _default_candidate(payload)
    assert record["candidate_id"] == "capital_hilton_coupa_po_reference_retrieval"
    assert record["target_world"] == "Finance"
    assert record["target_lane"] == "Capital Hilton"
    assert record["external_surface"] == "Coupa supplier portal / Hilton AP payment reference surface"
    assert "Retrieve or confirm Coupa / PO / payment reference metadata" in record["business_purpose"]
    assert record["current_authority_granted"] is False


def test_automation_statuses_and_stages_exist():
    payload = _build()

    assert set(payload["automation_statuses"]) == set(candidate.AUTOMATION_STATUSES)
    assert set(payload["automation_stages"]) == set(candidate.AUTOMATION_STAGES)
    for status in [
        "MANUAL_FALLBACK_ONLY_CURRENTLY",
        "ASSISTED_MANUAL_CANDIDATE",
        "SUPERVISED_AUTOMATION_CANDIDATE",
        "READ_ONLY_AUTOMATION_CANDIDATE",
        "PROTECTED_LOGIN_AUTOMATION_CANDIDATE",
        "AUTONOMOUS_RETRIEVAL_CANDIDATE",
        "BLOCKED_PENDING_SECURITY_DELTA",
        "BLOCKED_PENDING_PROTECTED_ACCESS_BROKER",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert status in payload["automation_statuses"]
    for stage in [
        "STAGE_0_MANUAL_INSTRUCTIONS",
        "STAGE_1_GUIDED_MANUAL_SESSION",
        "STAGE_2_SUPERVISED_BROWSER_PREVIEW",
        "STAGE_3_READ_ONLY_PORTAL_LOOKUP_DRY_RUN",
        "STAGE_4_PROTECTED_CREDENTIAL_BROKER_TRIAL",
        "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL",
        "STAGE_6_ACTION_OR_SUBMISSION_BLOCKED",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert stage in payload["automation_stages"]
    assert payload["machine_proof"]["automation_statuses_exist"] is True
    assert payload["machine_proof"]["automation_stages_exist"] is True


def test_manual_fallback_and_future_supervised_autonomous_candidates_are_modeled():
    payload = _build()
    record = _default_candidate(payload)

    assert "manually logs in" in record["current_manual_fallback"]
    assert "governed read-only lookup" in record["automation_goal"]
    assert record["automation_status"] == "BLOCKED_PENDING_PROTECTED_ACCESS_BROKER"
    assert record["automation_stage"] == "STAGE_0_MANUAL_INSTRUCTIONS"
    assert record["protected_access_broker_required"] is True
    assert record["credential_broker_required"] is True
    assert record["browser_automation_required"] is True
    assert record["network_required_future"] is True
    assert payload["machine_proof"]["manual_fallback_modeled"] is True
    assert payload["machine_proof"]["supervised_and_autonomous_candidates_modeled_future_gated"] is True


def test_required_safe_and_blocked_outputs_are_defined():
    payload = _build()
    record = _default_candidate(payload)

    for required_input in [
        "client/vendor identity",
        "invoice lane/session id",
        "expected date range",
        "expected amount",
        "Capital Hilton label",
        "PO/payment reference target",
        "credential broker token later, not now",
        "operator authorization later",
        "Guardian approval later",
    ]:
        assert required_input in record["required_inputs"]
    for safe_output in [
        "PO/reference number if found",
        "no-reference-found receipt",
        "lookup attempted receipt",
        "portal route label",
        "timestamp",
        "source surface label",
        "redacted proof metadata",
        "hash/receipt reference",
    ]:
        assert safe_output in record["safe_outputs"]
    for blocked_output in [
        "credentials",
        "session cookies",
        "raw portal body scrape",
        "invoice submission",
        "payment request mutation",
        "email/send/submit action",
    ]:
        assert blocked_output in record["blocked_outputs"]


def test_readiness_gates_exist_and_are_not_currently_satisfied():
    payload = _build()
    gates = {gate["gate_id"]: gate for gate in payload["readiness_gates"]}

    assert set(gates) == {
        "security_delta_for_external_portal",
        "protected_access_broker_gate",
        "credential_handling_gate",
        "browser_automation_sandbox_gate",
        "read_only_lookup_contract_gate",
        "portal_terms_compliance_gate",
        "guardian_metadata_review_gate",
        "operator_authorization_gate",
        "receipt_and_rollback_gate",
        "no_submission_mutation_gate",
    }
    assert payload["machine_proof"]["readiness_gate_count"] == 10
    assert set(payload["gate_types"]) == set(candidate.GATE_TYPES)
    assert all(gate["current_status"] == "NOT_SATISFIED_CURRENTLY" for gate in gates.values())
    assert "live portal access now" in gates["security_delta_for_external_portal"]["blocked_result"]
    assert "direct credential access by agents" in gates["protected_access_broker_gate"]["blocked_result"]
    assert "invoice submission" in gates["no_submission_mutation_gate"]["blocked_result"]


def test_stop_conditions_exist_and_require_receipts():
    payload = _build()
    conditions = {condition["condition_id"]: condition for condition in payload["stop_conditions"]}

    assert payload["machine_proof"]["stop_condition_count"] == 12
    for condition_id in [
        "login_challenge_mfa_required",
        "credentials_unavailable",
        "portal_layout_changed",
        "unexpected_payment_account_page",
        "mutation_submit_button_encountered",
        "raw_sensitive_data_exposed",
        "unknown_account_session_state",
        "po_reference_ambiguous",
        "duplicate_invoice_reference_risk",
        "compliance_terms_uncertainty",
        "guardian_quarantine_trigger",
        "operator_cancels",
    ]:
        assert condition_id in conditions
        assert conditions[condition_id]["receipt_required"] is True
        assert conditions[condition_id]["operator_visibility"] == "operator_visible_required"
    assert conditions["raw_sensitive_data_exposed"]["severity"] == "QUARANTINE"


def test_trial_ladder_exists_and_submission_stage_is_blocked():
    payload = _build()
    stages = {stage["stage_id"]: stage for stage in payload["trial_ladder"]}

    assert set(stages) == {
        "manual_reference_capture",
        "guided_manual_readback",
        "supervised_browser_navigation_preview",
        "read_only_lookup_dry_run",
        "protected_credential_broker_trial",
        "autonomous_read_only_retrieval",
        "submission_or_invoice_action",
    }
    assert payload["machine_proof"]["trial_stage_count"] == 7
    assert "operator manually records safe PO/reference metadata" in stages["manual_reference_capture"]["allowed_actions"]
    assert "future supervised preview only after gates" in stages["supervised_browser_navigation_preview"]["allowed_actions"]
    assert "future autonomous read-only retrieval after all gates" in stages["autonomous_read_only_retrieval"]["allowed_actions"]
    assert stages["submission_or_invoice_action"]["allowed_actions"] == ()
    assert "Coupa submit" in stages["submission_or_invoice_action"]["blocked_actions"]
    assert stages["submission_or_invoice_action"]["can_advance_to_next_stage"] is False
    assert payload["machine_proof"]["mutation_submission_stage_blocked"] is True


def test_all_current_authority_flags_are_false_and_future_flags_do_not_grant_authority():
    payload = _build()
    boundary = payload["authority_boundary"]

    for key, value in candidate.NO_CURRENT_AUTHORITY_FLAGS.items():
        assert value is False
        assert payload[key] is False, key
        assert boundary[key] is False, key
    assert boundary["all_current_authority_flags_false"] is True
    assert payload["machine_proof"]["all_current_authority_flags_false"] is True
    assert payload["future_candidate_flags_non_authority"]["read_only_portal_lookup_future_candidate"] is True
    assert payload["future_candidate_flags_non_authority"]["autonomous_retrieval_future_candidate"] is True
    assert payload["future_candidate_flags_non_authority"]["future_flags_grant_current_authority"] is False
    assert payload["machine_proof"]["future_candidate_flags_do_not_grant_authority"] is True


def test_no_coupa_browser_network_invoice_send_ledger_or_runtime_authority():
    payload = _build()
    boundary = payload["authority_boundary"]

    for key in [
        "coupa_access_allowed",
        "browser_automation_allowed",
        "network_operation_allowed",
        "credential_handling_allowed",
        "protected_credential_broker_active",
        "portal_login_allowed",
        "portal_read_allowed",
        "portal_write_allowed",
        "invoice_generation_allowed",
        "invoice_submission_allowed",
        "ledger_write_allowed",
        "email_send_allowed",
        "payment_mutation_allowed",
        "model_call_allowed",
        "agent_activation_allowed",
        "tool_execution_allowed",
        "queue_execution_allowed",
        "runtime_dispatch_allowed",
    ]:
        assert boundary[key] is False
    assert payload["machine_proof"]["no_credential_storage"] is True
    assert payload["machine_proof"]["no_coupa_browser_network_authority"] is True
    assert payload["machine_proof"]["no_invoice_send_submit_ledger_authority"] is True


def test_capital_hilton_proof_resolution_linkage_exists():
    payload = _build()
    linkage = payload["relationship_to_capital_hilton_proof_resolution"]

    assert linkage["proof_item_id_supported"] == "coupa_po_payment_reference_metadata"
    assert linkage["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert linkage["capital_hilton_proof_resolution_batch"]["read_model_ref"] == (
        "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json"
    )
    assert linkage["capital_hilton_protected_reference_placeholder"]["read_model_ref"] == (
        "generated/read_models/capital_hilton_protected_reference_placeholder.json"
    )
    assert linkage["capital_hilton_guardian_review_packet"]["guardian_review_required"] is True
    assert linkage["capital_hilton_proof_quieting_progress_state"]["transitioned_now"] is False
    assert linkage["lookup_receipt_may_be_created_later"] is True
    assert linkage["lookup_receipt_created_now"] is False
    assert linkage["proof_satisfied_now"] is False
    assert payload["machine_proof"]["relationship_to_capital_hilton_proof_item_exists"] is True


def test_no_credentials_secrets_or_raw_private_bodies_are_included():
    payload = _build()
    text = candidate.stable_json(payload)

    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert "sk-" not in text
    assert "AKIA" not in text
    assert "BEGIN " + "PRIVATE KEY" not in text
    assert "/" + "mnt" + "/" + "c" not in text
    assert "c:" + "\\" not in text.lower()


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    result = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            "generated/read_models",
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / candidate.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / candidate.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")

    assert payload["read_model_id"] == candidate.READ_MODEL_ID
    assert payload["machine_proof"]["candidate_count"] == 1
    assert payload["machine_proof"]["readiness_gate_count"] == 10
    assert "ELIWINSHIP Summary" in operator
    assert "Manual lookup is the fallback, not the goal" in operator


def test_source_has_no_network_browser_portal_runtime_or_mutation_calls():
    text = Path("capital_hilton_coupa_po_retrieval_automation_candidate.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "urllib.",
        "selenium",
        "playwright",
        "webbrowser",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "shutil.rmtree",
        "openai",
    ]:
        assert token not in text
