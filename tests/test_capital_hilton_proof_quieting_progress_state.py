import json
from pathlib import Path

import capital_hilton_proof_quieting_progress_state as progress
from scripts.export_capital_hilton_proof_quieting_progress_state import main as export_main


FIXED_NOW = "2026-05-23T15:30:00+00:00"

EXPECTED_PROOF_ITEM_IDS = {
    "performance_date_2026_05_08_proof",
    "performance_date_2026_05_15_proof",
    "rate_400_per_gig_proof",
    "subtotal_800_proof",
    "one_invoice_posture_proof",
    "coupa_po_payment_reference_metadata",
    "excel_workbook_or_invoice_source_reference",
    "ap_recipient_route_metadata",
    "tax_vendor_handling_metadata",
    "future_invoice_generation_receipt_requirement",
}


def _build(tmp_path: Path | None = None) -> dict:
    return progress.build_capital_hilton_proof_quieting_progress_state(
        repo_root=tmp_path or Path("."),
        generated_at=FIXED_NOW,
    )


def _records(payload: dict) -> dict:
    return {record["proof_item_id"]: record for record in payload["proof_progress_records"]}


def _transitions(payload: dict) -> dict:
    return {transition["transition_id"]: transition for transition in payload["transition_rules"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert progress.stable_json(first) == progress.stable_json(second)
    assert first["schema_version"] == progress.SCHEMA_VERSION
    assert first["read_model_id"] == progress.READ_MODEL_ID
    assert first["contract_status"] == "deterministic_proof_quieting_progress_state_metadata_only"
    assert first["quieting_policy"]["automatic_quieting_allowed"] is False
    assert first["quieting_policy"]["automatic_progression_allowed"] is False
    assert first["machine_proof"]["automatic_quieting_progression_false"] is True


def test_ten_default_progress_records_start_missing(tmp_path):
    payload = _build(tmp_path)
    records = _records(payload)

    assert len(records) == 10
    assert set(records) == EXPECTED_PROOF_ITEM_IDS
    assert payload["machine_proof"]["default_progress_record_count"] == 10
    for record in records.values():
        assert record["current_state"] == "MISSING_PROOF"
        assert record["can_quiet_now"] is False
        assert record["can_progress_now"] is True
        assert record["requires_operator_input"] is True
        assert record["answer_candidate_ref"].startswith(progress.ANSWER_CANDIDATE_READ_MODEL_REF)
        assert record["protected_placeholder_ref"].startswith("NOT_OBSERVED_OR_PENDING:")
        assert record["guardian_packet_ref"].startswith(progress.GUARDIAN_PACKET_READ_MODEL_REF)
        assert "invoice generation" in record["blocked_actions"]
        assert "send/submit/approval" in record["blocked_actions"]


def test_progress_summary_default_counts_are_all_missing(tmp_path):
    payload = _build(tmp_path)
    summary = payload["progress_summary"]

    assert summary["target_world"] == "Finance"
    assert summary["lane_id"] == "capital_hilton"
    assert summary["current_phase"] == "HELM_THRESHOLD_LANE"
    assert summary["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert summary["proof_items_total"] == 10
    assert summary["missing_proof_count"] == 10
    assert summary["answered_memory_candidate_count"] == 0
    assert summary["protected_placeholder_linked_count"] == 0
    assert summary["guardian_review_required_count"] == 0
    assert summary["proof_metadata_linked_count"] == 0
    assert summary["quiet_with_proof_count"] == 0
    assert summary["parked_count"] == 0
    assert summary["quarantined_count"] == 0
    assert summary["candidate_facts_proven"] is False
    assert summary["action_authority_granted"] is False
    assert payload["machine_proof"]["default_missing_proof_count"] == 10


def test_progress_states_and_attention_classes_exist(tmp_path):
    payload = _build(tmp_path)

    assert set(payload["progress_states"]) == set(progress.PROGRESS_STATES)
    assert set(payload["attention_classes"]) == set(progress.ATTENTION_CLASSES)
    assert "MISSING_PROOF" in payload["progress_states"]
    assert "QUIET_WITH_PROOF_CANDIDATE" in payload["progress_states"]
    assert "UNKNOWN_FAIL_CLOSED" in payload["progress_states"]
    assert "NEEDS_OPERATOR_INPUT" in payload["attention_classes"]
    assert "READY_TO_QUIET_WITH_PROOF" in payload["attention_classes"]
    assert payload["machine_proof"]["all_progress_states_exist"] is True
    assert payload["machine_proof"]["all_attention_classes_exist"] is True


def test_transition_rules_cover_required_safe_state_changes(tmp_path):
    payload = _build(tmp_path)
    transitions = _transitions(payload)

    assert transitions["missing_plus_operator_text_answer"]["from_state"] == "MISSING_PROOF"
    assert transitions["missing_plus_operator_text_answer"]["event"] == "OPERATOR_TEXT_ANSWER"
    assert transitions["missing_plus_operator_text_answer"]["to_state"] == "ANSWERED_MEMORY_CANDIDATE_ONLY"
    assert transitions["missing_plus_operator_text_answer"]["authority_granted"] is False
    assert transitions["missing_plus_source_card"]["to_state"] == "ANSWER_POINTS_TO_SOURCE_CARD"
    assert transitions["missing_plus_protected_placeholder"]["to_state"] == "PROTECTED_PLACEHOLDER_LINKED"
    assert transitions["placeholder_plus_guardian_requested"]["to_state"] == "GUARDIAN_REVIEW_REQUIRED"
    assert transitions["guardian_required_plus_metadata_allowed"]["to_state"] == "GUARDIAN_METADATA_ALLOWED"
    assert transitions["guardian_allowed_plus_proof_metadata"]["to_state"] == "PROOF_METADATA_LINKED"
    assert transitions["proof_metadata_plus_receipt"]["to_state"] == "QUIET_WITH_PROOF_CANDIDATE"
    assert transitions["missing_plus_rejection_with_reason"]["to_state"] == "QUIET_WITH_VALID_REJECTION"
    assert payload["machine_proof"]["transition_rules_exist"] is True


def test_text_answer_source_protected_and_guardian_rules_do_not_execute_or_auto_quiet(tmp_path):
    payload = _build(tmp_path)
    transitions = _transitions(payload)

    assert transitions["missing_plus_operator_text_answer"]["authority_granted"] is False
    assert "cannot prove or quiet" in transitions["missing_plus_operator_text_answer"]["notes"]
    assert transitions["missing_plus_source_card"]["authority_granted"] is False
    assert "do not auto-quiet" in transitions["missing_plus_source_card"]["notes"]
    assert transitions["missing_plus_protected_placeholder"]["authority_granted"] is False
    assert "not proof by themselves" in transitions["missing_plus_protected_placeholder"]["notes"]
    assert transitions["guardian_required_plus_metadata_allowed"]["authority_granted"] is False
    assert "cannot execute" in transitions["guardian_required_plus_metadata_allowed"]["notes"]
    assert payload["machine_proof"]["text_answer_transition_does_not_prove"] is True
    assert payload["machine_proof"]["source_protected_refs_do_not_auto_quiet"] is True
    assert payload["machine_proof"]["guardian_metadata_allowed_does_not_execute"] is True


def test_proof_metadata_plus_receipt_can_create_quiet_candidate_not_auto_quiet(tmp_path):
    payload = _build(tmp_path)
    transition = _transitions(payload)["proof_metadata_plus_receipt"]

    assert transition["from_state"] == "PROOF_METADATA_LINKED"
    assert transition["event"] == "RECEIPT_LINKED"
    assert transition["to_state"] == "QUIET_WITH_PROOF_CANDIDATE"
    assert list(transition["required_refs"]) == ["proof_metadata_ref", "receipt_ref", "quiet_receipt_ref"]
    assert transition["authority_granted"] is False
    assert "not automatic quieting" in transition["notes"]
    assert payload["quieting_policy"]["proof_metadata_plus_receipt_can_create_candidate"] is True
    assert payload["machine_proof"]["proof_metadata_plus_receipt_can_create_quiet_with_proof_candidate"] is True


def test_unknown_event_fails_closed_and_quarantine_available_from_any_state(tmp_path):
    payload = _build(tmp_path)
    transitions = _transitions(payload)

    for state in progress.PROGRESS_STATES:
        unknown = transitions[f"{state.lower()}_plus_unknown_event"]
        quarantine = transitions[f"{state.lower()}_plus_quarantine"]
        assert unknown["from_state"] == state
        assert unknown["event"] == "UNKNOWN_EVENT"
        assert unknown["to_state"] == "UNKNOWN_FAIL_CLOSED"
        assert unknown["authority_granted"] is False
        assert quarantine["from_state"] == state
        assert quarantine["event"] == "QUARANTINE_TRIGGERED"
        assert quarantine["to_state"] == "QUARANTINED"
        assert quarantine["authority_granted"] is False
    assert payload["machine_proof"]["unknown_event_fails_closed"] is True


def test_all_authority_flags_are_false(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]

    for key, value in progress.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is False
        assert boundary[key] is False
    assert boundary["all_authority_flags_false"] is True
    assert boundary["invoice_generation_allowed"] is False
    assert boundary["coupa_access_allowed"] is False
    assert boundary["browser_oauth_allowed"] is False
    assert boundary["gmail_calendar_email_access_allowed"] is False
    assert boundary["send_submit_approval_allowed"] is False
    assert boundary["model_call_allowed"] is False
    assert boundary["agent_activation_allowed"] is False
    assert boundary["tool_execution_allowed"] is False
    assert boundary["queue_execution_allowed"] is False
    assert boundary["runtime_dispatch_allowed"] is False
    assert boundary["automatic_quieting_allowed"] is False
    assert boundary["automatic_progression_allowed"] is False
    assert payload["machine_proof"]["authority_flags_false"] is True


def test_prior_lane_refs_are_represented(tmp_path):
    payload = _build(tmp_path)
    refs = payload["relationship_to_prior_lanes"]

    assert refs["capital_hilton_answer_candidate_receipt"]["read_model_ref"] == (
        progress.ANSWER_CANDIDATE_READ_MODEL_REF
    )
    assert refs["capital_hilton_protected_reference_placeholder"]["read_model_ref"] == (
        progress.PROTECTED_PLACEHOLDER_READ_MODEL_REF
    )
    assert refs["capital_hilton_protected_reference_placeholder"]["status"] == "NOT_OBSERVED_OR_PENDING"
    assert refs["capital_hilton_guardian_review_packet"]["read_model_ref"] == (
        progress.GUARDIAN_PACKET_READ_MODEL_REF
    )
    assert refs["capital_hilton_protected_proof_intake"]["read_model_ref"] == (
        progress.PROOF_INTAKE_READ_MODEL_REF
    )
    assert payload["machine_proof"]["prior_lane_refs_represented"] is True


def test_no_credentials_or_raw_private_bodies_are_included(tmp_path):
    payload = _build(tmp_path)
    text = progress.stable_json(payload)

    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert "sk-" not in text
    assert "AKIA" not in text
    assert "BEGIN " + "PRIVATE KEY" not in text


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
    json_path = tmp_path / "generated" / "read_models" / progress.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / progress.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == progress.SCHEMA_VERSION
    assert payload["machine_proof"]["default_progress_record_count"] == 10
    assert "ELIWINSHIP Summary" in operator
    assert "What Moves An Item Forward" in operator
    assert "Final Batch Prompt" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("capital_hilton_proof_quieting_progress_state.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
