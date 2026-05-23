import json
import re
from pathlib import Path

import workflow_session_channel_projection_approval_bus_contract as contract
from scripts.export_workflow_session_channel_projection_approval_bus_contract import main as export_main


FIXED_NOW = "2026-05-23T17:00:00+00:00"


def _build() -> dict:
    return contract.build_workflow_session_channel_projection_approval_bus_contract(generated_at=FIXED_NOW)


def _sessions(payload: dict) -> dict:
    return payload["workflow_sessions_by_id"]


def _projections(payload: dict) -> dict:
    return payload["channel_projections_by_id"]


def _approval_buses(payload: dict) -> dict:
    return payload["approval_buses_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_implement_live_telegram"] is True
    assert first["hard_rule"]["does_not_implement_live_approval_buttons"] is True
    assert first["hard_rule"]["does_not_implement_email_send"] is True
    assert first["hard_rule"]["does_not_implement_invoice_generation"] is True
    assert first["hard_rule"]["does_not_write_workflow_state"] is True
    assert first["hard_rule"]["does_not_refresh_stable_map"] is True
    assert first["hard_rule"]["may_submit_approval_now"] is False
    assert first["hard_rule"]["may_send_message_now"] is False
    assert first["hard_rule"]["may_execute_action_now"] is False


def test_workflow_session_channel_projection_and_approval_models_exist():
    payload = _build()

    assert payload["machine_proof"]["workflow_session_model_present"] is True
    assert payload["machine_proof"]["channel_projection_model_present"] is True
    assert payload["machine_proof"]["approval_bus_model_present"] is True
    assert payload["operator_workflow_session_schema"]["required_fields"] == list(
        contract.REQUIRED_WORKFLOW_SESSION_FIELDS
    )
    assert payload["workflow_channel_projection_schema"]["required_fields"] == list(
        contract.REQUIRED_CHANNEL_PROJECTION_FIELDS
    )
    assert payload["workflow_approval_bus_schema"]["required_fields"] == list(
        contract.REQUIRED_APPROVAL_BUS_FIELDS
    )
    assert set(payload["workflow_states"]) == set(contract.WORKFLOW_STATES)
    assert set(payload["channel_types"]) == set(contract.CHANNEL_TYPES)
    assert set(payload["approval_statuses"]) == set(contract.APPROVAL_STATUSES)
    assert set(payload["approval_types"]) == set(contract.APPROVAL_TYPES)


def test_stale_approval_and_session_staleness_policies_exist():
    payload = _build()
    stale = payload["stale_approval_prevention_policy"]
    staleness = payload["workflow_session_staleness_policy"]

    assert payload["machine_proof"]["stale_approval_policy_present"] is True
    assert payload["machine_proof"]["session_staleness_policy_present"] is True
    assert set(contract.REQUIRED_STALE_APPROVAL_POLICY_FIELDS) <= set(stale)
    assert set(contract.REQUIRED_SESSION_STALENESS_POLICY_FIELDS) <= set(staleness)
    assert stale["single_source_of_truth"] == "SQLite/receipt-backed workflow session"
    assert stale["atomic_invalidation_required"] is True
    assert stale["duplicate_approval_blocked"] is True
    assert stale["channel_local_state_blocked"] is True
    assert stale["approval_expiry_required"] is True
    assert stale["receipt_required"] is True
    assert staleness["reopen_allowed"] is True
    assert staleness["reopen_requires_receipt"] is True
    assert "stale" in staleness["approval_state_effect"]


def test_default_capital_hilton_session_exists_and_is_not_approval_requested():
    payload = _build()
    sessions = _sessions(payload)
    approvals = _approval_buses(payload)

    assert "capital_hilton_invoice_workflow_session" in sessions
    session = sessions["capital_hilton_invoice_workflow_session"]
    assert set(contract.REQUIRED_WORKFLOW_SESSION_FIELDS) <= set(session)
    assert session["world"] == "Finance"
    assert session["lane"] == "Capital Hilton"
    assert session["current_state"] == "DECISION_NODE_ACTIVE"
    assert session["active_solve_path_ref"] == "capital_hilton_invoice_solve_path"
    assert session["active_decision_node_ref"] == "confirm_performance_dates"
    assert "MISSION_CONTROL_FINANCE_WORLD" in session["entry_channels"]
    assert "TELEGRAM" in session["entry_channels"]
    assert "CASSANDRA_CLARA" in session["entry_channels"]
    assert "GUARDIAN" in session["entry_channels"]
    assert "CHIEF" in session["entry_channels"]
    assert session["approval_bus_ref"] == "capital_hilton_invoice_approval_bus"
    approval = approvals["capital_hilton_invoice_approval_bus"]
    assert approval["approval_status"] == "NOT_REQUESTED"
    assert approval["approval_type"] == "INVOICE_ARTIFACT_APPROVAL"
    assert approval["can_execute_without_approval"] is False
    assert payload["machine_proof"]["capital_hilton_session_present"] is True


def test_default_app_wide_sessions_exist():
    sessions = _sessions(_build())

    expected = {
        "capital_hilton_invoice_workflow_session",
        "chief_terrain_reconciliation_session",
        "check_engine_diagnostic_session",
        "cassandra_clara_draft_review_session",
        "automation_trial_session",
    }
    assert set(sessions) == expected
    assert sessions["chief_terrain_reconciliation_session"]["current_state"] == "WORK_MODE_ACTIVE"
    assert sessions["check_engine_diagnostic_session"]["current_state"] == "WORK_MODE_ACTIVE"
    assert sessions["cassandra_clara_draft_review_session"]["current_state"] == "DRAFT_PREVIEW_PENDING"
    assert sessions["automation_trial_session"]["current_state"] == "BLOCKED"
    for session in sessions.values():
        assert session["blocked_actions"]
        assert session["stale_state_policy_ref"] == "default_workflow_session_staleness_policy"
        assert session["reopen_policy_ref"] == "receipt_required_reopen_policy"


def test_channel_projections_exist_and_finance_world_and_telegram_share_session():
    payload = _build()
    projections = _projections(payload)

    for projection_id in [
        "finance_world_projection",
        "telegram_projection",
        "cassandra_clara_projection",
        "guardian_projection",
        "chief_projection",
        "helm_summary_projection",
    ]:
        assert projection_id in projections
        assert set(contract.REQUIRED_CHANNEL_PROJECTION_FIELDS) <= set(projections[projection_id])

    finance = projections["finance_world_projection"]
    telegram = projections["telegram_projection"]
    assert finance["workflow_session_ref"] == "capital_hilton_invoice_workflow_session"
    assert telegram["workflow_session_ref"] == "capital_hilton_invoice_workflow_session"
    assert finance["workflow_session_ref"] == telegram["workflow_session_ref"]
    assert finance["can_start_session"] is True
    assert telegram["can_start_session"] is True
    assert finance["local_state_allowed"] is False
    assert telegram["local_state_allowed"] is False
    assert finance["canonical_state_required"] is True
    assert telegram["canonical_state_required"] is True
    assert finance["duplicate_session_allowed"] is False
    assert telegram["duplicate_session_allowed"] is False
    assert finance["current_authority_granted"] is False
    assert telegram["current_authority_granted"] is False
    assert payload["machine_proof"]["finance_world_and_telegram_attach_same_session"] is True


def test_channel_local_state_and_duplicate_sessions_are_blocked():
    payload = _build()
    projections = _projections(payload)
    session_policy = payload["session_integrity_policy"]

    assert session_policy["one_canonical_session_per_active_workflow_intent"] is True
    assert session_policy["channel_owns_independent_workflow_state"] is False
    assert session_policy["duplicate_workflow_sessions_for_same_intent_allowed"] is False
    assert session_policy["explicit_fork_requires_receipt"] is True
    for projection in projections.values():
        assert projection["local_state_allowed"] is False
        assert projection["canonical_state_required"] is True
        assert projection["duplicate_session_allowed"] is False
        assert projection["current_authority_granted"] is False
    assert payload["machine_proof"]["duplicate_sessions_blocked"] is True
    assert payload["machine_proof"]["channel_local_state_blocked"] is True
    assert payload["machine_proof"]["duplicate_projection_sessions_blocked"] is True


def test_approval_bus_invariants_block_duplicates_and_stale_mirrors():
    payload = _build()
    approvals = _approval_buses(payload)
    invariants = payload["approval_invariants"]

    assert invariants["single_approval_object_per_event"] is True
    assert invariants["approving_one_channel_invalidates_all_visible_mirrors"] is True
    assert invariants["approval_cannot_be_submitted_twice"] is True
    assert invariants["approval_cannot_exist_without_session_ref"] is True
    assert invariants["approval_cannot_execute_action_without_future_authority_and_gates"] is True
    assert invariants["approval_receipt_must_close_stale_projections"] is True
    assert invariants["stale_approvals_expire_or_invalidate"] is True
    for approval_id, approval in approvals.items():
        assert set(contract.REQUIRED_APPROVAL_BUS_FIELDS) <= set(approval), approval_id
        assert approval["workflow_session_ref"]
        assert approval["single_signature_required"] is True
        assert approval["can_approve_from_any_channel"] is True
        assert approval["can_approve_more_than_once"] is False
        assert approval["can_execute_without_approval"] is False
        assert approval["operator_final_authority_required"] is True
        assert approval["blocked_actions"]
    assert payload["machine_proof"]["single_approval_object_invariant"] is True
    assert payload["machine_proof"]["approval_more_than_once_blocked"] is True
    assert payload["machine_proof"]["approval_execute_without_approval_blocked"] is True
    assert payload["machine_proof"]["stale_approval_invalidation_required"] is True


def test_prior_lane_refs_are_represented_if_available():
    payload = _build()
    relationships = {item["lane_id"]: item for item in payload["relationship_to_prior_lanes"]}

    expected = {
        "operator_work_mode_schema_bandwidth_policy",
        "operator_solve_path_decision_node_contract",
        "guided_capture_protected_evidence_path_contract",
        "capital_hilton_proof_resolution_batch",
        "capital_hilton_coupa_po_retrieval_automation_candidate",
        "operator_attention_promotion_contract",
        "chief_test_harness_cross_off_receipt_contract",
        "security_pass_contract",
    }
    assert set(relationships) == expected
    assert relationships["operator_work_mode_schema_bandwidth_policy"]["observation_status"] == "OBSERVED"
    assert relationships["operator_solve_path_decision_node_contract"]["observation_status"] == "OBSERVED"
    assert relationships["guided_capture_protected_evidence_path_contract"]["observation_status"] == "OBSERVED"
    for relationship in relationships.values():
        assert relationship["read_model_ref"]
        assert "without duplicating" in relationship["relationship"]
    assert payload["machine_proof"]["prior_lane_ref_count"] == len(expected)


def test_all_authority_flags_false_and_no_raw_private_bodies_or_secrets():
    payload = _build()
    text = contract.stable_json(payload)

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["authority_boundary"]["session_state_write_allowed"] is False
    assert payload["authority_boundary"]["channel_message_send_allowed"] is False
    assert payload["authority_boundary"]["telegram_send_allowed"] is False
    assert payload["authority_boundary"]["approval_submission_allowed"] is False
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["invoice_generation_allowed"] is False
    assert payload["authority_boundary"]["ledger_write_allowed"] is False
    assert payload["authority_boundary"]["artifact_generation_allowed"] is False
    assert payload["authority_boundary"]["browser_automation_allowed"] is False
    assert payload["authority_boundary"]["credential_handling_allowed"] is False
    assert payload["authority_boundary"]["model_call_allowed"] is False
    assert payload["authority_boundary"]["agent_activation_allowed"] is False
    assert payload["authority_boundary"]["tool_execution_allowed"] is False
    assert payload["authority_boundary"]["queue_execution_allowed"] is False
    assert payload["authority_boundary"]["runtime_dispatch_allowed"] is False
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
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


def test_exporter_writes_json_and_eliwinship_operator_markdown(tmp_path):
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
    json_path = tmp_path / "generated" / "read_models" / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / contract.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["machine_proof"]["workflow_session_count"] == 5
    assert payload["machine_proof"]["finance_world_and_telegram_attach_same_session"] is True
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert "ELIWINSHIP Summary" in operator
    assert "A workflow session is the one canonical state" in operator
    assert "Prompt 5 should add" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("workflow_session_channel_projection_approval_bus_contract.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "urllib",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
