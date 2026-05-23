import json
from pathlib import Path

import capital_hilton_answer_candidate_receipt as receipt
from scripts.export_capital_hilton_answer_candidate_receipt import main as export_main


FIXED_NOW = "2026-05-23T13:00:00+00:00"


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


def _build() -> dict:
    return receipt.build_capital_hilton_answer_candidate_receipt(generated_at=FIXED_NOW)


def _default_records(payload: dict) -> dict:
    return {item["proof_item_id"]: item for item in payload["answer_candidate_receipts"]}


def _examples(payload: dict) -> dict:
    return {item["answer_receipt_id"]: item for item in payload["answer_outcome_examples"]}


def test_contract_is_deterministic_and_linked_to_existing_intake():
    first = _build()
    second = _build()

    assert receipt.stable_json(first) == receipt.stable_json(second)
    assert first["schema_version"] == receipt.SCHEMA_VERSION
    assert first["read_model_id"] == receipt.READ_MODEL_ID
    assert first["contract_status"] == "deterministic_answer_candidate_receipt_metadata_only"
    assert first["source_linkage"]["source_read_model_ref"] == receipt.SOURCE_READ_MODEL_REF
    assert first["source_linkage"]["source_operator_ref"] == receipt.SOURCE_OPERATOR_REF
    assert first["source_linkage"]["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert first["machine_proof"]["all_10_proof_item_ids_represented"] is True


def test_exactly_ten_default_answer_candidate_records_exist():
    payload = _build()
    records = _default_records(payload)

    assert len(records) == 10
    assert set(records) == EXPECTED_PROOF_ITEM_IDS
    assert payload["machine_proof"]["default_answer_candidate_count"] == 10
    for proof_item_id, item in records.items():
        assert item["answer_receipt_id"] == f"{proof_item_id}_answer_candidate_receipt"
        assert item["answer_status"] == "UNANSWERED"
        assert item["answer_modality"] == "STRUCTURED_FORM"
        assert item["operator_supplied_summary"] is None
        assert item["memory_candidate_created"] is False
        assert item["can_clarify"] is True
        assert item["can_satisfy_proof"] is False
        assert item["can_quiet_item"] is False
        assert "invoice generation" in item["blocked_actions"]
        assert "send/submit/approval" in item["blocked_actions"]
    assert payload["machine_proof"]["default_records_unanswered"] is True
    assert payload["machine_proof"]["can_quiet_item_false_by_default"] is True


def test_allowed_modalities_and_statuses_exist():
    payload = _build()

    assert set(payload["allowed_answer_modalities"]) == set(receipt.ALLOWED_ANSWER_MODALITIES)
    assert set(payload["allowed_answer_statuses"]) == set(receipt.ALLOWED_ANSWER_STATUSES)
    for modality in [
        "TEXT",
        "YES_NO",
        "STRUCTURED_FORM",
        "SOURCE_CARD_REFERENCE",
        "PROTECTED_EVIDENCE_REFERENCE",
        "RECEIPT_REFERENCE",
        "PARK_THIS",
        "REJECT_OBSOLETE",
        "NEEDS_DISCOVERY",
    ]:
        assert modality in payload["allowed_answer_modalities"]
    for status in [
        "UNANSWERED",
        "ANSWER_CAPTURED_MEMORY_CANDIDATE",
        "ANSWER_POINTS_TO_SOURCE_CARD",
        "ANSWER_POINTS_TO_PROTECTED_REFERENCE",
        "ANSWER_POINTS_TO_RECEIPT",
        "ANSWER_STILL_NEEDS_PROOF",
        "ANSWER_REJECTS_CANDIDATE",
        "ANSWER_PARKS_ITEM",
        "ANSWER_NEEDS_DISCOVERY",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert status in payload["allowed_answer_statuses"]


def test_text_answers_can_clarify_but_cannot_prove_or_quiet():
    payload = _build()
    example = _examples(payload)["text_clarifies_rate_but_not_proof"]

    assert example["answer_modality"] == "TEXT"
    assert example["answer_status"] == "ANSWER_CAPTURED_MEMORY_CANDIDATE"
    assert example["memory_candidate_created"] is True
    assert example["memory_candidate_ref"]
    assert example["can_clarify"] is True
    assert example["can_satisfy_proof"] is False
    assert example["can_quiet_item"] is False
    assert payload["answer_classification_rules"]["text_yes_no_structured_form"]["can_satisfy_proof"] is False
    assert payload["machine_proof"]["text_answers_can_clarify_but_not_prove"] is True


def test_source_protected_and_receipt_refs_do_not_automatically_satisfy_proof():
    payload = _build()
    examples = _examples(payload)

    source = examples["source_card_points_to_rate_proof"]
    protected = examples["protected_excel_reference_for_workbook"]
    assert source["answer_modality"] == "SOURCE_CARD_REFERENCE"
    assert source["answer_status"] == "ANSWER_POINTS_TO_SOURCE_CARD"
    assert source["source_card_ref"]
    assert source["can_satisfy_proof"] is False
    assert protected["answer_modality"] == "PROTECTED_EVIDENCE_REFERENCE"
    assert protected["answer_status"] == "ANSWER_POINTS_TO_PROTECTED_REFERENCE"
    assert protected["protected_reference_ref"]
    assert protected["can_satisfy_proof"] is False
    assert payload["answer_classification_rules"]["source_card_protected_reference_receipt"][
        "can_satisfy_proof_without_validation"
    ] is False
    assert payload["machine_proof"]["source_protected_receipt_refs_do_not_automatically_satisfy_proof"] is True


def test_protected_reference_answers_require_guardian_and_raw_bodies_are_blocked():
    payload = _build()
    records = _default_records(payload)
    protected = _examples(payload)["protected_excel_reference_for_workbook"]

    for proof_item_id in [
        "performance_date_2026_05_08_proof",
        "performance_date_2026_05_15_proof",
        "rate_400_per_gig_proof",
        "one_invoice_posture_proof",
        "coupa_po_payment_reference_metadata",
        "excel_workbook_or_invoice_source_reference",
        "ap_recipient_route_metadata",
        "tax_vendor_handling_metadata",
    ]:
        assert records[proof_item_id]["protected_reference_required"] is True
        assert records[proof_item_id]["guardian_gate_required"] is True
        assert "guardian_gate_not_satisfied" in records[proof_item_id]["quieting_blockers"]

    assert protected["guardian_gate_required"] is True
    assert payload["answer_classification_rules"]["protected_reference"]["raw_body_allowed"] is False
    assert payload["answer_classification_rules"]["protected_reference"]["metadata_only"] is True
    assert payload["machine_proof"]["protected_reference_answers_require_guardian"] is True
    assert payload["machine_proof"]["raw_bodies_blocked"] is True


def test_reject_and_park_examples_do_not_complete_or_prove_items():
    payload = _build()
    examples = _examples(payload)
    rejected = examples["operator_rejects_one_invoice_posture"]
    parked = examples["operator_parks_tax_vendor_handling"]

    assert rejected["answer_modality"] == "REJECT_OBSOLETE"
    assert rejected["answer_status"] == "ANSWER_REJECTS_CANDIDATE"
    assert rejected["rejection_reason"] == "operator_rejects_candidate_invoice_shape"
    assert rejected["can_satisfy_proof"] is False
    assert rejected["can_quiet_item"] is False
    assert payload["answer_classification_rules"]["reject_obsolete"]["requires_rejection_reason_and_receipt_policy"] is True
    assert parked["answer_modality"] == "PARK_THIS"
    assert parked["answer_status"] == "ANSWER_PARKS_ITEM"
    assert parked["park_reason"] == "needs_later_vendor_or_tax_context"
    assert parked["can_satisfy_proof"] is False
    assert payload["answer_classification_rules"]["park_this"]["completion_status"] == "parked_visible_not_completed"


def test_operator_answers_are_memory_candidates_unless_linked_to_proof_refs():
    payload = _build()
    rule = payload["answer_classification_rules"]["text_yes_no_structured_form"]

    assert rule["becomes"] == "memory_candidate_receipt_unless_linked_to_proof_ref"
    assert payload["core_rule"]["operator_answers_do_not_prove"] is True
    assert payload["core_rule"]["answers_must_not_quiet_without_proof_metadata_valid_receipt_or_valid_rejection"] is True
    assert payload["machine_proof"]["operator_answers_are_memory_candidates_unless_linked_to_proof_refs"] is True


def test_authority_boundary_blocks_finance_account_send_and_runtime_actions():
    payload = _build()
    boundary = payload["authority_boundary"]

    for key, value in receipt.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is False
        assert boundary[key] is False
    assert boundary["all_authority_flags_false"] is True
    assert payload["machine_proof"]["authority_flags_false"] is True
    assert boundary["invoice_generation_allowed"] is False
    assert boundary["coupa_access_allowed"] is False
    assert boundary["browser_oauth_allowed"] is False
    assert boundary["account_access_allowed"] is False
    assert boundary["gmail_calendar_email_access_allowed"] is False
    assert boundary["send_submit_approval_allowed"] is False
    assert boundary["model_call_allowed"] is False
    assert boundary["agent_activation_allowed"] is False
    assert boundary["tool_execution_allowed"] is False
    assert boundary["queue_execution_allowed"] is False
    assert boundary["runtime_dispatch_allowed"] is False
    assert boundary["raw_excel_body_ingestion_allowed"] is False
    assert boundary["raw_pdf_body_ingestion_allowed"] is False
    assert boundary["raw_email_body_ingestion_allowed"] is False
    assert boundary["raw_finance_body_ingestion_allowed"] is False


def test_no_credentials_or_raw_private_bodies_are_included():
    payload = _build()
    text = receipt.stable_json(payload)

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
    json_path = tmp_path / "generated" / "read_models" / receipt.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / receipt.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == receipt.SCHEMA_VERSION
    assert payload["machine_proof"]["default_answer_candidate_count"] == 10
    assert "ELIWINSHIP Summary" in operator
    assert "Why Answers Clarify But Do Not Prove" in operator
    assert "Next Backend Batch Lane" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("capital_hilton_answer_candidate_receipt.py").read_text(encoding="utf-8").lower()
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
