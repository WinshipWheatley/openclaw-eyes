import json
from pathlib import Path

import capital_hilton_protected_reference_placeholder as placeholder
from scripts.export_capital_hilton_protected_reference_placeholder import main as export_main


FIXED_NOW = "2026-05-23T14:30:00+00:00"


def _build() -> dict:
    return placeholder.build_capital_hilton_protected_reference_placeholder(
        generated_at=FIXED_NOW,
        guardian_packet_present=True,
    )


def test_placeholder_contract_is_deterministic_and_metadata_only():
    payload = _build()

    assert placeholder.stable_json(payload) == placeholder.stable_json(_build())
    assert payload["schema_version"] == placeholder.SCHEMA_VERSION
    assert payload["read_model_id"] == placeholder.READ_MODEL_ID
    assert payload["contract_status"] == "deterministic_protected_reference_placeholder_metadata_only"
    assert payload["placeholder_rules"]["metadata_only"] is True
    assert payload["placeholder_rules"]["raw_body_allowed"] is False
    assert payload["placeholder_rules"]["can_satisfy_proof_by_default"] is False
    assert payload["placeholder_rules"]["can_quiet_item_by_default"] is False


def test_reference_types_and_statuses_exist():
    payload = _build()

    assert set(payload["reference_types"]) == {
        "EXCEL_WORKBOOK_REFERENCE",
        "PDF_INVOICE_REFERENCE",
        "COUPA_REFERENCE_METADATA",
        "AP_EMAIL_ROUTE_METADATA",
        "CONTRACT_OR_RATE_SOURCE_REFERENCE",
        "PAYMENT_OR_PO_REFERENCE_METADATA",
        "PERFORMANCE_PROOF_REFERENCE",
        "TAX_VENDOR_PAYMENT_REFERENCE",
        "FUTURE_INVOICE_RECEIPT_REFERENCE",
        "UNKNOWN_FAIL_CLOSED",
    }
    assert set(payload["reference_statuses"]) == {
        "PLACEHOLDER_ONLY",
        "OPERATOR_REPORTED",
        "SOURCE_CARD_LINKED",
        "RECEIPT_LINKED",
        "HASH_LINKED",
        "PROTECTED_METADATA_READY_FOR_GUARDIAN",
        "GUARDIAN_REVIEW_REQUIRED",
        "GUARDIAN_APPROVED_METADATA",
        "REJECTED_OR_OBSOLETE",
        "UNKNOWN_FAIL_CLOSED",
    }
    assert payload["machine_proof"]["all_reference_types_exist"] is True
    assert payload["machine_proof"]["all_reference_statuses_exist"] is True


def test_safe_metadata_fields_and_raw_material_blocks_are_defined_by_reference_type():
    payload = _build()
    fields = payload["safe_metadata_fields_by_reference_type"]

    assert "file label" in fields["EXCEL_WORKBOOK_REFERENCE"]["allowed"]
    assert "raw workbook contents" in fields["EXCEL_WORKBOOK_REFERENCE"]["blocked"]
    assert "raw PDF contents" in fields["PDF_INVOICE_REFERENCE"]["blocked"]
    assert "Coupa login" in fields["COUPA_REFERENCE_METADATA"]["blocked"]
    assert "browser automation" in fields["COUPA_REFERENCE_METADATA"]["blocked"]
    assert "raw email bodies" in fields["AP_EMAIL_ROUTE_METADATA"]["blocked"]
    assert "source label" in fields["CONTRACT_OR_RATE_SOURCE_REFERENCE"]["allowed"]
    assert "PO/payment reference placeholder" in fields["PAYMENT_OR_PO_REFERENCE_METADATA"]["allowed"]
    assert "performance proof label" in fields["PERFORMANCE_PROOF_REFERENCE"]["allowed"]
    assert "tax form body" in fields["TAX_VENDOR_PAYMENT_REFERENCE"]["blocked"]
    assert "invoice generation" in fields["FUTURE_INVOICE_RECEIPT_REFERENCE"]["blocked"]
    assert "all raw material" in fields["UNKNOWN_FAIL_CLOSED"]["blocked"]


def test_default_placeholders_exist_and_cover_expected_proof_items():
    payload = _build()
    records = {record["placeholder_id"]: record for record in payload["protected_reference_placeholders"]}

    assert set(records) == {
        "excel_workbook_invoice_source_placeholder",
        "coupa_po_payment_reference_placeholder",
        "ap_route_metadata_placeholder",
        "rate_source_placeholder",
        "performance_proof_reference_placeholder",
        "tax_vendor_payment_handling_placeholder",
        "future_invoice_generation_receipt_placeholder",
    }
    assert payload["machine_proof"]["default_placeholder_count"] == 7
    assert set(records["excel_workbook_invoice_source_placeholder"]["proof_item_ids"]) == {
        "excel_workbook_or_invoice_source_reference",
        "subtotal_800_proof",
        "future_invoice_generation_receipt_requirement",
    }
    assert records["coupa_po_payment_reference_placeholder"]["proof_item_ids"] == (
        "coupa_po_payment_reference_metadata",
    )
    assert set(records["performance_proof_reference_placeholder"]["proof_item_ids"]) == {
        "performance_date_2026_05_08_proof",
        "performance_date_2026_05_15_proof",
    }


def test_all_default_placeholders_are_non_proof_non_quiet_and_guardian_gated():
    payload = _build()

    for record in payload["protected_reference_placeholders"]:
        assert record["reference_status"] == "PLACEHOLDER_ONLY"
        assert record["metadata_only"] is True
        assert record["raw_body_allowed"] is False
        assert record["guardian_gate_required"] is True
        assert record["operator_final_authority_required"] is True
        assert record["can_satisfy_proof"] is False
        assert record["can_quiet_item"] is False
        assert "placeholder alone is not proof and cannot quiet the item" in record["promotion_requirements"]
    assert payload["machine_proof"]["metadata_only_true_for_all"] is True
    assert payload["machine_proof"]["raw_body_allowed_false_for_all"] is True
    assert payload["machine_proof"]["can_satisfy_proof_false_by_default"] is True
    assert payload["machine_proof"]["can_quiet_item_false_by_default"] is True
    assert payload["machine_proof"]["guardian_review_required_for_protected_placeholders"] is True


def test_authority_boundary_blocks_file_body_account_finance_and_runtime_authority():
    payload = _build()
    boundary = payload["authority_boundary"]

    for key, value in placeholder.NO_AUTHORITY_FLAGS.items():
        assert value is False
        assert boundary[key] is False, key
    assert boundary["all_authority_flags_false"] is True
    assert payload["machine_proof"]["file_read_copy_upload_false"] is True
    assert payload["machine_proof"]["raw_excel_pdf_email_body_ingestion_false"] is True
    assert payload["machine_proof"]["coupa_browser_email_account_credential_authority_false"] is True
    assert payload["machine_proof"]["invoice_ledger_send_authority_false"] is True
    assert payload["machine_proof"]["model_tool_agent_runtime_queue_authority_false"] is True


def test_answer_candidate_and_guardian_packet_linkage_are_represented():
    payload = _build()
    answer = payload["relationship_to_answer_candidates"]
    guardian = payload["relationship_to_guardian_review_packet"]

    assert answer["read_model_ref"] == "generated/read_models/capital_hilton_answer_candidate_receipt.json"
    assert answer["operator_ref"] == "generated/read_models/capital_hilton_answer_candidate_receipt_OPERATOR.md"
    assert answer["answer_candidate_may_point_to_placeholder"] is True
    assert answer["placeholder_remains_non_proof_until_validated"] is True
    assert answer["file_access_occurs_here"] is False
    assert guardian["read_model_ref"] == "generated/read_models/capital_hilton_guardian_review_packet.json"
    assert guardian["status"] == "OBSERVED"
    assert guardian["guardian_reviews_metadata_posture_only"] is True
    assert guardian["guardian_cannot_approve_invoice_action_or_account_access"] is True
    assert payload["machine_proof"]["answer_candidate_linkage_represented"] is True
    assert payload["machine_proof"]["guardian_packet_linkage_represented"] is True


def test_unknown_references_fail_closed_and_include_no_sensitive_bodies_or_secrets():
    payload = _build()
    text = placeholder.stable_json(payload)

    assert payload["placeholder_rules"]["unknown_references_fail_closed"] is True
    assert payload["machine_proof"]["unknown_references_fail_closed"] is True
    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert "/" + "mnt" + "/" + "c" not in text
    assert "c:" + "\\" not in text.lower()
    assert "sk-" not in text
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
    json_path = tmp_path / "generated" / "read_models" / placeholder.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / placeholder.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == placeholder.READ_MODEL_ID
    assert payload["machine_proof"]["default_placeholder_count"] == 7
    assert "ELIWINSHIP Summary" in operator
    assert "Default Placeholders" in operator


def test_source_has_no_file_access_mutation_network_or_runtime_calls():
    text = Path("capital_hilton_protected_reference_placeholder.py").read_text(encoding="utf-8").lower()
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
