import json
from pathlib import Path

import capital_hilton_protected_proof_intake as intake
from scripts.export_capital_hilton_protected_proof_intake import main as export_main


FIXED_NOW = "2026-05-23T05:00:00+00:00"


def _build() -> dict:
    return intake.build_capital_hilton_protected_proof_intake(generated_at=FIXED_NOW)


def _items(payload: dict) -> dict:
    return {item["proof_item_id"]: item for item in payload["proof_intake_items"]}


def test_contract_is_deterministic_and_metadata_only():
    first = _build()
    second = _build()

    assert intake.stable_json(first) == intake.stable_json(second)
    assert first["schema_version"] == intake.SCHEMA_VERSION
    assert first["read_model_id"] == "capital_hilton_protected_proof_intake"
    assert first["contract_status"] == "deterministic_protected_proof_intake_metadata_only"
    assert first["core_doctrine"]["operator_answers_are_not_proof"] is True
    assert first["core_doctrine"]["protected_files_are_not_ingested"] is True
    assert first["core_doctrine"]["raw_finance_bodies_are_not_stored"] is True
    assert first["machine_proof"]["raw_private_body_included"] is False
    assert first["machine_proof"]["credential_or_secret_included"] is False
    assert first["machine_proof"]["network_git_sync_mac_app_mutation_authority_added"] is False


def test_current_capital_hilton_facts_are_candidate_not_proven():
    payload = _build()
    facts = payload["capital_hilton_current_facts"]

    assert facts["target_world"] == "Finance"
    assert facts["current_phase"] == "HELM_THRESHOLD_LANE"
    assert facts["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert facts["missing_proof_count"] == 10
    assert facts["protected_proof_required"] is True
    assert facts["candidate_completed_dates"] == ["2026-05-08", "2026-05-15"]
    assert facts["candidate_rate"] == "$400 per gig"
    assert facts["candidate_subtotal"] == "$800"
    assert facts["candidate_one_invoice_posture"] is True
    assert facts["candidate_facts_proven"] is False
    assert facts["action_authority_granted"] is False


def test_exactly_ten_required_proof_intake_items_exist():
    payload = _build()
    items = _items(payload)

    assert len(items) == 10
    assert set(items) == {
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
    assert items["performance_date_2026_05_08_proof"]["eliwinship_question"] == (
        "Can we point to protected proof that the May 8, 2026 Capital Hilton performance happened?"
    )
    assert items["performance_date_2026_05_15_proof"]["candidate_value"] == "2026-05-15"
    assert items["rate_400_per_gig_proof"]["candidate_value"] == "$400 per gig"
    assert items["subtotal_800_proof"]["candidate_value"] == "$800"
    assert items["one_invoice_posture_proof"]["candidate_value"] == "candidate one-invoice posture"
    assert items["future_invoice_generation_receipt_requirement"]["receipt_required"] is True
    assert items["future_invoice_generation_receipt_requirement"]["protected_proof_required"] is False


def test_each_intake_item_has_required_fields_and_blocks_actions():
    payload = _build()
    required_fields = {
        "proof_item_id",
        "display_name",
        "eliwinship_question",
        "why_it_matters",
        "proof_class",
        "candidate_value",
        "proof_status",
        "protected_proof_required",
        "allowed_answer_modalities",
        "operator_answer_becomes",
        "protected_evidence_reference_required",
        "guardian_gate_required",
        "operator_confirmation_required",
        "source_card_required",
        "receipt_required",
        "what_would_satisfy_this",
        "what_would_not_satisfy_this",
        "quiet_condition",
        "blocked_actions",
        "next_safe_move",
    }

    for item in payload["proof_intake_items"]:
        assert required_fields <= set(item)
        assert item["proof_status"] in intake.PROOF_STATUSES
        assert set(item["allowed_answer_modalities"]) == set(intake.ALLOWED_ANSWER_MODALITIES)
        assert item["operator_answer_becomes"] == "memory_candidate_receipt_unless_linked_to_proof_metadata"
        assert item["operator_confirmation_required"] is True
        assert "invoice generation" in item["blocked_actions"]
        assert "send/submit/approval" in item["blocked_actions"]
        assert item["next_safe_move"] == intake.SHARED_FIX_PATH_ID


def test_operator_answer_candidates_are_memory_candidates_not_proof():
    payload = _build()
    answers = payload["operator_answer_candidates"]

    assert len(answers) == 10
    for answer in answers:
        assert answer["answer_status"] in intake.ANSWER_STATUSES
        assert answer["answer_status"] == "UNANSWERED"
        assert answer["memory_candidate_required"] is True
        assert answer["proof_metadata_required"] is True
        assert answer["operator_review_required"] is True
        assert answer["can_quiet_question"] is False
        assert answer["can_satisfy_proof"] is False
    policy = payload["operator_answer_capture_policy"]
    assert policy["text_answers_can_clarify"] is True
    assert policy["text_answers_can_prove"] is False
    assert policy["operator_answers_become"] == "Memory Candidate Receipts"
    assert policy["answers_can_trigger_invoice_generation"] is False
    assert policy["answers_can_trigger_send_submit_approval"] is False
    assert policy["answers_can_trigger_browser_or_account_access"] is False


def test_protected_evidence_requirements_are_metadata_only_and_guardian_gated():
    payload = _build()
    requirements = payload["protected_evidence_requirements"]

    assert {item["protected_surface"] for item in requirements} == set(intake.PROTECTED_SURFACES)
    for requirement in requirements:
        assert requirement["raw_body_allowed"] is False
        assert requirement["metadata_only"] is True
        assert requirement["redaction_required"] is True
        assert requirement["hash_or_receipt_required"] is True
        assert requirement["guardian_gate_required"] is True
        assert requirement["operator_final_authority_required"] is True
        assert "raw Excel body" in requirement["blocked_material"]
        assert "raw email body" in requirement["blocked_material"]
        assert "Coupa login/session data" in requirement["blocked_material"]
        assert "credentials" in requirement["blocked_material"]
    assert payload["machine_proof"]["protected_references_metadata_only"] is True


def test_guardian_gates_exist_for_sensitive_finance_references():
    payload = _build()
    gates = {gate["gate_id"]: gate for gate in payload["guardian_gate_requirements"]}

    assert set(gates) == {
        "protected_finance_metadata_gate",
        "coupa_reference_metadata_gate",
        "ap_route_or_email_metadata_gate",
        "tax_vendor_payment_handling_gate",
        "future_invoice_generation_gate",
    }
    for gate in gates.values():
        assert gate["redaction_required"] is True
        assert gate["operator_review_required"] is True
        assert "receipt refs" in gate["allowed_output"]
    assert "invoice generation" in gates["future_invoice_generation_gate"]["blocked_output"]
    assert payload["machine_proof"]["guardian_gate_count"] == 5


def test_authority_boundary_blocks_finance_and_runtime_actions():
    payload = _build()
    boundary = payload["authority_boundary"]

    for key, value in intake.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is False
        assert boundary[key] is False
    assert boundary["all_authority_flags_false"] is True
    assert payload["machine_proof"]["coupa_browser_email_account_credentials_blocked"] is True
    assert payload["machine_proof"]["invoice_generation_blocked"] is True
    assert payload["machine_proof"]["send_submit_approval_blocked"] is True
    blocked = set(boundary["blocked_actions"])
    assert "Coupa access" in blocked
    assert "browser/OAuth/account access" in blocked
    assert "Gmail/calendar/email account access" in blocked
    assert "raw Excel body ingestion" in blocked
    assert "invoice generation" in blocked
    assert "ledger write" in blocked
    assert "send/submit/approval" in blocked
    assert "tool execution" in blocked


def test_quieting_rules_require_proof_or_valid_rejection():
    payload = _build()
    rules = payload["proof_quieting_rules"]

    assert len(rules) == 10
    for rule in rules:
        assert rule["current_attention_state"] == "NEEDS_PROOF"
        assert rule["if_answered_without_proof"].startswith("Convert to proof-needed")
        assert "quiet-with-proof candidate" in rule["if_proof_metadata_linked"]
        assert "reason, source ref, and rejection/obsolete receipt" in rule["if_rejected_or_obsolete"]
        assert rule["promotion_destination"] == intake.SHARED_FIX_PATH_ID
    quieting = payload["quieting_policy"]
    assert quieting["answered_without_proof_quiets_item"] is False
    assert quieting["protected_proof_metadata_linked_can_quiet"] is True
    assert quieting["valid_rejected_or_obsolete_receipt_can_quiet"] is True
    assert quieting["future_invoice_action_remains_blocked"] is True


def test_shared_fix_path_and_stable_map_posture_are_explicit():
    payload = _build()
    path = payload["shared_fix_path"]
    stable = payload["stable_map_integration"]

    assert path["fix_path_id"] == "protected_finance_proof_metadata_intake"
    assert path["execution_allowed"] is False
    assert path["requires_receipts_and_gates_before_any_future_promotion"] is True
    assert "Capital Hilton" in path["linked_lanes"]
    assert "Finance World" in path["linked_lanes"]
    assert payload["machine_proof"]["shared_fix_path_exists"] is True
    assert stable["summary_included_in_stable_map_now"] is False
    assert stable["safe_summary_for_next_refresh"]["proof_item_count"] == 10
    assert stable["safe_summary_for_next_refresh"]["action_authority_granted"] is False


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    result = export_main([
        "--repo-root",
        tmp_path.as_posix(),
        "--export-root",
        "generated/read_models",
        "--format",
        "summary",
    ])

    assert result == 0
    exported_json = tmp_path / "generated" / "read_models" / intake.JSON_EXPORT_NAME
    exported_md = tmp_path / "generated" / "read_models" / intake.OPERATOR_EXPORT_NAME
    payload = json.loads(exported_json.read_text(encoding="utf-8"))
    operator = exported_md.read_text(encoding="utf-8")
    assert payload["schema_version"] == intake.SCHEMA_VERSION
    assert payload["machine_proof"]["proof_intake_item_count"] == 10
    assert "ELIWINSHIP Summary" in operator
    assert "Answers Versus Proof" in operator
    assert "Still Blocked" in operator


def test_source_has_no_c_drive_defaults_or_disallowed_runtime_behavior():
    text = Path("capital_hilton_protected_proof_intake.py").read_text(encoding="utf-8").lower()
    c_drive_mount = "/" + "mnt" + "/" + "c" + "/" + "openclaw"
    c_drive_windows = "c:" + "\\" + "openclaw"
    for token in [
        c_drive_mount,
        c_drive_windows,
        "subprocess",
        "shell=true",
        "os.system",
        "docker run",
        "ollama run",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
    ]:
        assert token not in text
