import json
import re
from pathlib import Path

import workflow_block_intent_live_draft_contract as contract
from scripts.export_workflow_block_intent_live_draft_contract import main as export_main


FIXED_NOW = "2026-05-23T16:00:00+00:00"


def _build() -> dict:
    return contract.build_workflow_block_intent_live_draft_contract(generated_at=FIXED_NOW)


def _drafts(payload: dict) -> dict:
    return payload["draft_intents_by_id"]


def _workspaces(payload: dict) -> dict:
    return payload["live_workspaces_by_id"]


def _proposals(payload: dict) -> dict:
    return payload["agent_compiler_proposals_by_id"]


def _validations(payload: dict) -> dict:
    return payload["validation_results_by_id"]


def _boundaries(payload: dict) -> dict:
    return payload["capture_boundaries_by_id"]


def _flows(payload: dict) -> dict:
    return payload["conversational_flows_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["summary"] == "Live draft workspace -> explicit commit boundary -> receipt-backed state."
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_persist_operator_answers"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_execute_workflow"] is True
    assert first["hard_rule"]["does_not_call_agents_or_models"] is True
    assert first["hard_rule"]["may_grant_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["workflow_block_draft_intent_model_present"] is True
    assert payload["machine_proof"]["live_workflow_draft_workspace_model_present"] is True
    assert payload["machine_proof"]["agent_compiler_proposal_model_present"] is True
    assert payload["machine_proof"]["deterministic_validation_result_model_present"] is True
    assert payload["machine_proof"]["capture_boundary_model_present"] is True
    assert payload["machine_proof"]["conversational_workflow_block_flow_model_present"] is True
    assert payload["workflow_block_draft_intent_schema"]["required_fields"] == list(
        contract.REQUIRED_DRAFT_INTENT_FIELDS
    )
    assert payload["live_workflow_draft_workspace_schema"]["required_fields"] == list(
        contract.REQUIRED_WORKSPACE_FIELDS
    )
    assert payload["workflow_block_agent_compiler_proposal_schema"]["required_fields"] == list(
        contract.REQUIRED_AGENT_PROPOSAL_FIELDS
    )
    assert payload["workflow_block_intent_validation_result_schema"]["required_fields"] == list(
        contract.REQUIRED_VALIDATION_RESULT_FIELDS
    )
    assert payload["workflow_block_capture_boundary_schema"]["required_fields"] == list(
        contract.REQUIRED_CAPTURE_BOUNDARY_FIELDS
    )
    assert payload["conversational_workflow_block_flow_schema"]["required_fields"] == list(
        contract.REQUIRED_CONVERSATIONAL_FLOW_FIELDS
    )
    assert set(payload["validation_statuses"]) == set(contract.VALIDATION_STATUSES)
    assert set(payload["review_modes"]) == set(contract.REVIEW_MODES)


def test_capital_hilton_mission_control_draft_example_exists_and_is_preview_only():
    payload = _build()
    drafts = _drafts(payload)

    assert "capital_hilton_mission_control_performance_dates_draft" in drafts
    draft = drafts["capital_hilton_mission_control_performance_dates_draft"]
    assert set(contract.REQUIRED_DRAFT_INTENT_FIELDS) <= set(draft)
    assert draft["origin_surface"] == "MISSION_CONTROL"
    assert draft["block_id"] == "performance_dates"
    assert draft["operation"] == "add_dates"
    assert draft["operator_input_raw"] == "May 22 and May 29"
    assert draft["operator_input_structured"]["date_values"] == ("2026-05-22", "2026-05-29")
    assert draft["proposed_updates"][0]["value"] == "2026-05-22"
    assert draft["proposed_updates"][1]["value"] == "2026-05-29"
    assert draft["resulting_fields"]["performance_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert "invoice subtotal preview becomes stale until recalculated" in draft["downstream_effects"]
    assert "email attachment preview becomes stale" in draft["downstream_effects"]
    assert draft["receipt_target"] == "capital_hilton_performance_dates_operator_correction_or_confirmation_receipt_target"
    assert draft["preview_only"] is True
    assert draft["capture_ready"] is False
    assert payload["machine_proof"]["capital_hilton_mission_control_example_present"] is True


def test_live_workspace_keeps_current_draft_and_future_captured_state_distinct():
    payload = _build()
    workspace = _workspaces(payload)["capital_hilton_invoice_live_draft_workspace"]

    assert set(contract.REQUIRED_WORKSPACE_FIELDS) <= set(workspace)
    assert workspace["current_openclaw_state"]["state_kind"] == "canonical_current"
    assert workspace["active_local_draft_state"]["state_kind"] == "active_draft_not_canonical"
    assert workspace["future_captured_state_preview"]["state_kind"] == "future_captured_preview_not_written"
    assert workspace["current_openclaw_state"]["performance_dates"] == ("2026-05-08", "2026-05-15")
    assert workspace["active_local_draft_state"]["performance_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert workspace["downstream_preview"]["subtotal"] == "stale_until_recalculated"
    assert workspace["reversible_exploration_state"]["can_reset_to_current_openclaw_state"] is True
    assert workspace["reversible_exploration_state"]["draft_history_commits_to_canonical_state"] is False
    assert "explicit capture" in workspace["commit_boundary"]
    assert payload["live_workflow_draft_workspace_schema"]["stepping_through_blocks_commits_state"] is False
    assert payload["live_workflow_draft_workspace_schema"]["editing_updates_downstream_preview"] is True
    assert payload["live_workflow_draft_workspace_schema"]["current_draft_captured_state_distinct"] is True
    assert payload["machine_proof"]["current_vs_draft_vs_captured_state_distinct"] is True
    assert payload["machine_proof"]["draft_input_updates_downstream_preview"] is True


def test_agent_compiler_proposals_translate_but_cannot_commit_truth():
    payload = _build()
    proposals = _proposals(payload)

    assert "cassandra_capital_hilton_invoice_request_compiler_proposal" in proposals
    cassandra = proposals["cassandra_capital_hilton_invoice_request_compiler_proposal"]
    assert set(contract.REQUIRED_AGENT_PROPOSAL_FIELDS) <= set(cassandra)
    assert cassandra["source_surface"] == "TELEGRAM"
    assert "client" in cassandra["blocks_system_can_fill"]
    assert "exact performance dates if not deterministically known" in cassandra["blocks_operator_must_answer"]
    assert cassandra["validation_required"] is True
    assert cassandra["can_skip_operator_review"] is False
    assert payload["workflow_block_agent_compiler_proposal_schema"]["agent_may_translate_human_language"] is True
    assert payload["workflow_block_agent_compiler_proposal_schema"]["agent_may_fill_from_deterministic_evidence"] is True
    assert payload["workflow_block_agent_compiler_proposal_schema"]["agent_may_commit_canonical_state"] is False
    assert payload["workflow_block_agent_compiler_proposal_schema"]["agent_may_approve_send_execute"] is False
    assert payload["machine_proof"]["agent_proposal_cannot_commit_truth"] is True


def test_validator_normalizes_preview_but_cannot_write_or_execute():
    payload = _build()
    validations = _validations(payload)

    assert "capital_hilton_performance_dates_preview_validation" in validations
    validation = validations["capital_hilton_performance_dates_preview_validation"]
    assert set(contract.REQUIRED_VALIDATION_RESULT_FIELDS) <= set(validation)
    assert validation["validation_status"] == "VALID_PREVIEW"
    assert validation["normalized_updates"][0]["value"] == "2026-05-22"
    assert "invoice_subtotal_preview" in validation["downstream_invalidations"]
    assert validation["capture_allowed"] is False
    assert validation["canonical_write_allowed"] is False
    assert validation["execution_allowed"] is False
    for item in validations.values():
        assert item["canonical_write_allowed"] is False
        assert item["execution_allowed"] is False
    assert payload["workflow_block_intent_validation_result_schema"]["normalizes_without_writing_receipts"] is True
    assert payload["machine_proof"]["validator_cannot_execute"] is True


def test_capture_boundary_is_explicit_and_not_execution():
    payload = _build()
    boundaries = _boundaries(payload)

    boundary = boundaries["capital_hilton_performance_dates_capture_boundary"]
    assert set(contract.REQUIRED_CAPTURE_BOUNDARY_FIELDS) <= set(boundary)
    assert boundary["capture_label"] == "Use these dates"
    assert boundary["required_validation_status"] == "VALID_PREVIEW"
    assert boundary["required_operator_action"] == "explicit operator capture action"
    assert boundary["required_state_writer"] == "future receipt-backed workflow state writer"
    assert boundary["current_capture_authority"] is False
    assert boundary["current_write_authority"] is False
    assert boundary["current_execution_authority"] is False
    for item in boundaries.values():
        assert item["current_capture_authority"] is False
        assert item["current_write_authority"] is False
        assert item["current_execution_authority"] is False
    assert payload["workflow_block_capture_boundary_schema"]["capture_is_execution"] is False
    assert payload["workflow_block_capture_boundary_schema"]["capture_requires_future_writer_lane"] is True
    assert payload["machine_proof"]["capture_boundary_is_explicit"] is True


def test_conversational_flows_include_required_examples():
    payload = _build()
    flows = _flows(payload)

    assert "telegram_cassandra_capital_hilton_invoice_request_flow" in flows
    invoice = flows["telegram_cassandra_capital_hilton_invoice_request_flow"]
    assert set(contract.REQUIRED_CONVERSATIONAL_FLOW_FIELDS) <= set(invoice)
    assert invoice["example_request"] == "Send Capital Hilton an invoice for this week's and last week's job."
    assert invoice["originating_agent"] == "Cassandra"
    assert invoice["originating_surface"] == "Telegram"
    assert "client" in invoice["system_filled_blocks"][0]
    assert "Cool, I can prepare the draft." in invoice["conversation_steps"][3]
    assert "send_email_approval_bus" in invoice["approval_boundaries"]
    assert invoice["review_mode"] == "REVIEW_REQUIRED"

    assert "new_monthly_client_recap_workflow_request_flow" in flows
    new_flow = flows["new_monthly_client_recap_workflow_request_flow"]
    assert new_flow["example_request"] == "Set up a monthly client recap workflow for Client X."
    assert "source_materials" in new_flow["inferred_blocks"]
    assert "review and fill it together" in new_flow["conversation_steps"][2]

    assert "chief_check_engine_build_blocker_flow" in flows
    chief = flows["chief_check_engine_build_blocker_flow"]
    assert chief["example_request"] == "What is blocking the build?"
    assert chief["originating_agent"] == "Chief"
    assert "current blocker summary if refs are current" in chief["system_filled_blocks"]
    assert "Captain-facing blocker summary" in chief["final_response_shape"]

    assert payload["machine_proof"]["telegram_cassandra_invoice_request_example_present"] is True
    assert payload["machine_proof"]["new_workflow_request_example_present"] is True
    assert payload["machine_proof"]["chief_check_engine_example_present"] is True


def test_channel_and_agent_neutrality_includes_required_surfaces_and_agents():
    payload = _build()
    required_surfaces = {
        "Mission Control",
        "Telegram",
        "Cassandra/Clara",
        "Chief",
        "Guardian",
        "Hermes",
        "Niles",
        "future workflow agents",
    }
    required_agents = {"Cassandra/Clara", "Chief", "Guardian", "Hermes", "Niles", "future workflow agents"}

    assert required_surfaces <= set(payload["compatible_surfaces_required"])
    assert required_agents <= set(payload["compatible_agents_required"])
    for draft in payload["draft_intents"]:
        assert required_surfaces <= set(draft["compatible_surfaces"])
        assert required_agents <= set(draft["compatible_agents"])
    assert payload["workflow_block_draft_intent_schema"]["mission_control_and_telegram_are_surfaces_not_state_owners"] is True
    assert payload["machine_proof"]["channel_agent_neutrality_present"] is True


def test_starship_operating_model_alignment_exists():
    starship = _build()["starship_operating_model_alignment"]

    assert starship["captain"] == "operator/final authority"
    assert "command and attention surface" in starship["bridge_helm"]
    assert "domain work surfaces" in starship["worlds"]
    assert "workflow sessions" in starship["away_missions"]
    assert "agents that brief" in starship["crew"]
    assert "proof, sync, tests, receipts, read-models" in starship["engineering"]
    assert "receipts and proof" in starship["ship_logs"]
    assert "developer/build noise" in starship["shipyard_mode"]
    assert "Helm routes; worlds do work." in starship["rules"]
    assert "Captain sees decisions, not raw telemetry." in starship["rules"]


def test_no_live_authority_credentials_or_raw_private_bodies():
    payload = _build()
    text = contract.stable_json(payload)

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for draft in payload["draft_intents"]:
        for key, value in draft["authority_state"].items():
            assert value is False, key
        assert draft["preview_only"] is True
        assert draft["capture_ready"] is False
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    for key in [
        "canonical_state_write_allowed",
        "receipt_write_allowed",
        "capture_write_allowed",
        "execution_allowed",
        "invoice_generation_allowed",
        "email_draft_allowed",
        "email_send_allowed",
        "browser_automation_allowed",
        "coupa_access_allowed",
        "credential_handling_allowed",
        "telegram_send_allowed",
        "model_call_allowed",
        "agent_activation_allowed",
        "tool_execution_allowed",
        "queue_execution_allowed",
        "runtime_dispatch_allowed",
        "file_write_allowed",
        "raw_body_ingestion_allowed",
    ]:
        assert payload["authority_boundary"][key] is False
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
    assert payload["machine_proof"]["draft_intent_count"] == 4
    assert payload["machine_proof"]["capture_boundary_is_explicit"] is True
    assert "ELIWINSHIP Summary" in operator
    assert "A live draft workspace is a place to try workflow answers" in operator
    assert "Agents translate. Determinism validates. Receipts commit. Gates execute." in operator
    assert "that was easy" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("workflow_block_intent_live_draft_contract.py").read_text(encoding="utf-8").lower()
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
