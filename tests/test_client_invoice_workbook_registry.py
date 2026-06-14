import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_workbook_registry as registry
from scripts.export_client_invoice_workbook_registry import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"


def _request(**updates) -> dict:
    request = registry.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    request.update(updates)
    return request


def test_required_models_exist_with_required_fields():
    assert tuple(field.name for field in fields(registry.ClientInvoiceWorkbookRegistry)) == (
        "registry_id",
        "doctrine",
        "client_records",
        "workbook_policy",
        "invoice_sheet_policy",
        "registration_policy",
        "authority_boundary",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(registry.ClientInvoiceWorkbookRecord)) == (
        "client_ref",
        "client_display_name",
        "tenant_scope",
        "workflow_ref",
        "workbook_ref",
        "workbook_display_name",
        "workbook_path_ref",
        "workbook_extension",
        "workbook_exists_status",
        "workbook_status",
        "intended_use",
        "approved_for_metadata_read",
        "approved_for_cell_read",
        "source_request_id",
        "source_file_metadata_ref",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(registry.WorkbookRegistrationRequest)) == (
        "request_id",
        "source_request_id",
        "intended_use",
        "file_display_name",
        "file_extension",
        "file_type",
        "local_path_ref",
        "client_ref",
        "workflow_ref",
        "world_ref",
        "authority_boundary",
        "validation_status",
        "missing_context",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(registry.WorkbookRegistrationReadback)) == (
        "readback_id",
        "status",
        "operator_headline",
        "operator_message",
        "client_summary",
        "workbook_summary",
        "missing_items",
        "next_action",
        "hidden_refs",
        "authority_boundary",
        "next_safe_move",
    )


def test_capital_hilton_workbook_registration_creates_metadata_only_record(tmp_path):
    payload = registry.register_workbook_request(
        _request(),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
        source_file_metadata_ref="generated/read_models/operator_file_metadata_readback.json",
    )
    record = payload["active_record"]

    assert payload["registration_request"]["validation_status"] == "WORKBOOK_REFERENCE_CAPTURED"
    assert payload["registration_readback"]["status"] == "WORKBOOK_REFERENCE_CAPTURED"
    assert payload["registration_readback"]["operator_headline"] == "Capital Hilton workbook captured"
    assert record["client_ref"] == "capital_hilton"
    assert record["client_display_name"] == "Capital Hilton"
    assert record["tenant_scope"] == "tenant_scope:fixture_business_ops"
    assert record["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert record["approved_for_metadata_read"] is True
    assert record["approved_for_cell_read"] is False
    assert record["source_file_metadata_ref"].endswith("operator_file_metadata_readback.json")
    assert payload["registry"]["client_records"] == (record,)
    assert payload["machine_proof"]["workbook_body_read_performed"] is False
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False
    assert payload["machine_proof"]["folder_scan_performed"] is False


def test_missing_context_asks_clarification_without_binding_client(tmp_path):
    payload = registry.register_workbook_request(
        _request(client_ref="unknown", workflow_ref="unknown"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["registration_request"]["validation_status"] == "WORKBOOK_CONTEXT_MISSING"
    assert payload["registration_readback"]["status"] == "WORKBOOK_CONTEXT_MISSING"
    assert payload["registration_readback"]["operator_headline"] == "Which client is this for?"
    assert payload["registry"]["client_records"] == ()
    assert payload["active_record"] is None
    assert payload["registration_readback"]["missing_items"] == ("client_ref", "workflow_ref")


def test_non_spreadsheet_registration_is_blocked_without_record(tmp_path):
    payload = registry.register_workbook_request(
        _request(file_display_name="Capital Hilton invoice.pdf", file_extension=".pdf", file_kind_hint="invoice pdf"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["registration_request"]["validation_status"] == "WORKBOOK_NOT_SPREADSHEET"
    assert payload["registration_readback"]["status"] == "WORKBOOK_NOT_SPREADSHEET"
    assert payload["registry"]["client_records"] == ()
    assert payload["machine_proof"]["spreadsheet_parse_performed"] is False


def test_duplicate_same_workbook_is_idempotent(tmp_path):
    first = registry.register_workbook_request(_request(), export_root=tmp_path, generated_at=FIXED_NOW)
    registry.write_exports(first, tmp_path)
    second = registry.register_workbook_request(_request(), export_root=tmp_path, generated_at=FIXED_NOW)

    assert second["duplicate_result"] == "DUPLICATE_SAME_WORKBOOK_NOOP"
    assert second["registration_readback"]["status"] == "WORKBOOK_REFERENCE_CAPTURED"
    assert len(second["registry"]["client_records"]) == 1
    assert second["active_record"]["workbook_ref"] == first["active_record"]["workbook_ref"]


def test_different_workbook_for_same_client_is_candidate_not_overwrite(tmp_path):
    first = registry.register_workbook_request(_request(), export_root=tmp_path, generated_at=FIXED_NOW)
    registry.write_exports(first, tmp_path)
    replacement = _request(
        request_id="mission_control_file_intake_request_capital_hilton_replacement_workbook",
        file_display_name="Capital Hilton replacement workbook.xlsx",
        mac_visible_path_ref="fixture_path_ref:capital_hilton_replacement_workbook",
    )
    second = registry.register_workbook_request(replacement, export_root=tmp_path, generated_at=FIXED_NOW)

    assert second["duplicate_result"] == "DIFFERENT_WORKBOOK_CANDIDATE_REQUIRES_CONFIRMATION"
    assert second["registration_readback"]["status"] == "WORKBOOK_REGISTRATION_BLOCKED"
    assert second["registration_readback"]["next_action"] == "Next: Confirm whether to replace the current workbook."
    assert len(second["registry"]["client_records"]) == 1
    assert second["registry"]["client_records"][0]["workbook_ref"] == first["active_record"]["workbook_ref"]
    assert second["candidate_record"]["workbook_status"] == "WORKBOOK_CANDIDATE"
    assert second["candidate_record"]["approved_for_cell_read"] is False


def test_operator_choice_keeps_candidate_and_cancels_replacement(tmp_path):
    first = registry.register_workbook_request(_request(), export_root=tmp_path, generated_at=FIXED_NOW)
    registry.write_exports(first, tmp_path)
    replacement = _request(
        request_id="mission_control_file_intake_request_capital_hilton_replacement_workbook",
        file_display_name="Capital Hilton replacement workbook.xlsx",
        mac_visible_path_ref="fixture_path_ref:capital_hilton_replacement_workbook",
    )
    candidate_payload = registry.register_workbook_request(replacement, export_root=tmp_path, generated_at=FIXED_NOW)
    registry.write_exports(candidate_payload, tmp_path)

    choice = registry.keep_candidate_and_cancel_replacement(
        {
            "request_id": "capital_hilton_invoice_workflow_candidate_cancel",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "world_ref": "finance",
            "operator_message": "Leave the test workbook as a candidate and cancel workbook replacement for now.",
        },
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert choice["registration_readback"]["status"] == "WORKBOOK_CANDIDATE_KEPT"
    assert choice["registration_readback"]["operator_headline"] == "Workbook candidate kept"
    assert choice["registration_readback"]["next_action"] == (
        "Next: provide the invoice field mapping when you are ready, or add the real workbook file."
    )
    assert choice["registry"]["client_records"][0]["workbook_ref"] == first["active_record"]["workbook_ref"]
    assert choice["candidate_record"]["workbook_status"] == "WORKBOOK_CANDIDATE"
    assert choice["candidate_record"]["approved_for_cell_read"] is False
    assert choice["machine_proof"]["current_workbook_preserved"] is True
    assert choice["machine_proof"]["candidate_preserved"] is True
    assert choice["machine_proof"]["workbook_replacement_performed"] is False
    assert choice["machine_proof"]["spreadsheet_cell_read_performed"] is False


def test_operator_choice_makes_candidate_current_without_reading_cells(tmp_path):
    first = registry.register_workbook_request(_request(), export_root=tmp_path, generated_at=FIXED_NOW)
    registry.write_exports(first, tmp_path)
    replacement = _request(
        request_id="mission_control_file_intake_request_capital_hilton_real_workbook",
        file_display_name="Capital Hilton real running workbook.xlsx",
        mac_visible_path_ref="fixture_path_ref:capital_hilton_real_running_workbook",
    )
    candidate_payload = registry.register_workbook_request(replacement, export_root=tmp_path, generated_at=FIXED_NOW)
    registry.write_exports(candidate_payload, tmp_path)

    choice = registry.replace_current_with_candidate(
        {
            "request_id": "capital_hilton_invoice_workflow_candidate_replace",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "world_ref": "finance",
            "operator_message": "That last workbok was just a test. This new workbook is the real Capital Hilton workbook.",
        },
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert choice["registration_readback"]["status"] == "WORKBOOK_REPLACEMENT_CONFIRMED"
    assert choice["registration_readback"]["operator_headline"] == "Capital Hilton workbook updated"
    assert "Nothing was deleted from disk" in choice["registration_readback"]["operator_message"]
    assert choice["registry"]["client_records"][0]["workbook_ref"] == candidate_payload["candidate_record"]["workbook_ref"]
    assert choice["registry"]["client_records"][0]["workbook_status"] == "WORKBOOK_CONFIRMED"
    assert choice["registry"]["client_records"][0]["approved_for_cell_read"] is False
    assert choice["operator_choice_request"]["invoice_sent_or_submitted"] is False
    assert choice["operator_choice_request"]["ledger_posted"] is False
    assert choice["machine_proof"]["candidate_promoted_to_current_workbook"] is True
    assert choice["machine_proof"]["candidate_promoted_to_authoritative"] is False
    assert choice["machine_proof"]["workbook_body_read_performed"] is False
    assert choice["machine_proof"]["spreadsheet_cell_read_performed"] is False


def test_export_writes_parseable_readmodel_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / registry.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / registry.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == registry.READ_MODEL_ID
    assert summary["status"] == "WORKBOOK_REFERENCE_CAPTURED"
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert "No workbook body" in operator


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = registry.register_workbook_request(_request(), export_root=tmp_path, generated_at=FIXED_NOW)
    registry.write_exports(payload, tmp_path)
    combined = (tmp_path / registry.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / registry.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert payload["machine_proof"]["credential_handling_performed"] is False
    assert payload["machine_proof"]["raw_body_ingestion_performed"] is False
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined)
    for forbidden in ("actual secret", "credential value", "password value", "raw private body value", "cell value", "formula value"):
        assert forbidden not in lowered
    assert all(value is False for value in payload["authority_boundary"].values())
