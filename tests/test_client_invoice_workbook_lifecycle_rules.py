import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_workbook_lifecycle_rules as lifecycle
from scripts.export_client_invoice_workbook_lifecycle_rules import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"


def _payload() -> dict:
    return lifecycle.build_payload(generated_at=FIXED_NOW)


def _records(payload: dict) -> dict:
    return {record["client_ref"]: record for record in payload["client_workbook_policy"]["client_records"]}


def test_required_models_exist_with_required_fields():
    assert tuple(field.name for field in fields(lifecycle.ClientWorkbookPolicy)) == (
        "policy_id",
        "one_workbook_per_client",
        "client_records",
        "cross_client_workbook_sharing_allowed",
        "capital_hilton_workbook_client_lock",
        "st_annes_workbook_requirement",
        "live_arts_md_workbook_requirement",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(lifecycle.ClientInvoiceTemplatePolicy)) == (
        "policy_id",
        "generic_template_allowed",
        "template_scope",
        "fresh_empty_invoice_page_required",
        "template_may_be_copied_into_client_workbook_only_by_future_writer",
        "template_must_not_be_used_as_client_source_of_record",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(lifecycle.FutureExcelWriterRequirement)) == (
        "requirement_id",
        "requirement_type",
        "condition",
        "required_before_excel_write",
        "fail_closed",
        "next_safe_move",
    )


def test_capital_hilton_locked_to_its_own_workbook():
    payload = _payload()
    records = _records(payload)

    assert payload["client_workbook_policy"]["one_workbook_per_client"] is True
    assert payload["client_workbook_policy"]["cross_client_workbook_sharing_allowed"] is False
    assert payload["client_workbook_policy"]["capital_hilton_workbook_client_lock"] == (
        "Capital Hilton workbook is only for Capital Hilton invoices."
    )
    assert records["capital_hilton"]["workbook_scope"] == "Capital Hilton invoices only"
    assert records["capital_hilton"]["may_share_capital_hilton_workbook"] is True
    assert payload["machine_proof"]["capital_hilton_locked_to_own_workbook"] is True


def test_st_annes_and_live_arts_md_require_separate_workbooks():
    payload = _payload()
    records = _records(payload)

    assert records["st_annes"]["separate_workbook_required"] is True
    assert records["st_annes"]["may_share_capital_hilton_workbook"] is False
    assert records["live_arts_md"]["separate_workbook_required"] is True
    assert records["live_arts_md"]["may_share_capital_hilton_workbook"] is False
    assert payload["machine_proof"]["st_annes_separate_workbook_required"] is True
    assert payload["machine_proof"]["live_arts_md_separate_workbook_required"] is True


def test_new_invoice_per_tab_and_template_start_point_are_represented():
    payload = _payload()

    assert payload["new_invoice_tab_policy"]["new_invoice_per_tab"] is True
    assert "Every new invoice" in payload["new_invoice_tab_policy"]["tab_scope"]
    assert payload["new_invoice_tab_policy"]["new_tab_creation_status"] == "FUTURE_GATED_EXCEL_WRITER_REQUIRED"
    assert payload["new_invoice_tab_policy"]["existing_tab_overwrite_allowed"] is False
    assert payload["template_policy"]["generic_template_allowed"] is True
    assert payload["template_policy"]["fresh_empty_invoice_page_required"] is True
    assert payload["template_policy"]["template_must_not_be_used_as_client_source_of_record"] is True
    assert payload["machine_proof"]["new_invoice_per_tab_represented"] is True


def test_payment_acknowledgment_requires_last_payment_amount_and_source():
    payload = _payload()
    policy = payload["payment_acknowledgment_policy"]

    assert policy["acknowledgment_phrase_template"] == "Thank you for your last payment of $X,"
    assert policy["last_payment_amount_required"] is True
    assert policy["last_payment_source_required"] is True
    assert "last_payment_amount" in policy["missing_facts"]
    assert "last_payment_source_ref" in policy["missing_facts"]
    assert policy["generation_without_last_payment_allowed"] is False
    assert payload["machine_proof"]["payment_acknowledgment_requires_last_payment_fact"] is True


def test_stale_workbook_values_are_not_accepted_without_audit_or_confirmation():
    payload = _payload()
    stale = payload["stale_workbook_policy"]
    records = _records(payload)

    assert records["capital_hilton"]["current_workbook_status"] == "CURRENT_WORKBOOK_IN_USE_MAY_CONTAIN_STALE_DATA"
    assert stale["capital_hilton_workbook_already_in_use"] is True
    assert stale["may_contain_stale_data"] is True
    assert stale["existing_values_current_truth_without_audit"] is False
    assert "whitelisted sheet audit" in stale["required_before_accepting_existing_values"]
    assert payload["machine_proof"]["stale_workbook_values_not_accepted_without_audit"] is True


def test_future_excel_writer_requirements_are_fail_closed():
    payload = _payload()
    requirements = payload["future_excel_writer_requirements"]

    assert requirements
    assert all(requirement["required_before_excel_write"] is True for requirement in requirements)
    assert all(requirement["fail_closed"] is True for requirement in requirements)
    assert {requirement["requirement_type"] for requirement in requirements} >= {
        "CLIENT_WORKBOOK_IDENTITY",
        "NEW_INVOICE_TAB",
        "LAST_PAYMENT_SOURCE",
        "STALE_VALUE_GUARD",
        "AUTHORITY_BOUNDARY",
    }
    assert payload["machine_proof"]["excel_writer_future_gated"] is True


def test_no_excel_read_write_send_or_submit_authority_is_introduced():
    payload = _payload()
    proof = payload["machine_proof"]

    assert all(value is False for value in payload["authority_boundary"].values())
    for key in (
        "excel_write_performed",
        "spreadsheet_created",
        "workbook_duplicated",
        "workbook_body_read_performed",
        "spreadsheet_cell_read_performed",
        "pdf_generation_performed",
        "email_send_performed",
        "gmail_send_performed",
        "coupa_access_or_submit_performed",
        "browser_access_performed",
        "workflow_execution_performed",
        "agent_dispatch_performed",
        "model_call_performed",
        "external_action_performed",
    ):
        assert proof[key] is False
    assert proof["all_live_authority_false"] is True


def test_export_writes_parseable_readmodel_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / lifecycle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / lifecycle.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == lifecycle.READ_MODEL_ID
    assert summary["new_invoice_per_tab"] is True
    assert summary["excel_writer_future_gated"] is True
    assert payload["lifecycle_readback"]["status"] == "LIFECYCLE_RULES_RECORDED_EXCEL_WRITER_FUTURE_GATED"
    assert "Lifecycle rules only" in operator


def test_generated_outputs_have_no_credentials_private_bodies_or_workbook_values(tmp_path):
    payload = _payload()
    lifecycle.write_exports(payload, tmp_path)
    combined = (tmp_path / lifecycle.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / lifecycle.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined)
    for forbidden in (
        "actual secret",
        "credential value",
        "password value",
        "raw private body value",
        "cell value",
        "workbook body value",
        "spreadsheet row",
    ):
        assert forbidden not in lowered
