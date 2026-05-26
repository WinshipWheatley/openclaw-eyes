import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_audit_handoff as handoff
import client_invoice_workbook_registry as registry
from scripts.export_client_invoice_audit_handoff import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"


def _seed_registry(export_root: Path) -> dict:
    payload = registry.register_workbook_request(
        registry.make_capital_hilton_fixture_request(created_at=FIXED_NOW),
        export_root=export_root,
        generated_at=FIXED_NOW,
        source_file_metadata_ref="generated/read_models/operator_file_metadata_readback.json",
    )
    registry.write_exports(payload, export_root)
    return payload


def _schema(*, complete: bool = True, formula_policy: str | None = None) -> dict:
    cells = [
        ("invoice_number", "B2", "text", True),
        ("performance_dates", "B3", "text", True),
        ("rate", "B4", "currency", True),
        ("subtotal_or_total", "B5", "currency", True),
    ]
    if complete:
        cells.append(("po_reference", "B6", "text", True))
    cells.append(("notes_status", "B7", "text", False))
    payload = {
        "sheet_name": "Invoice",
        "whitelisted_cells": [
            {
                "field_name": field_name,
                "cell_ref": cell_ref,
                "expected_value_type": value_type,
                "required": required,
            }
            for field_name, cell_ref, value_type, required in cells
        ],
        "whitelisted_columns": [],
        "required_fields": tuple(field for field, _cell, _type, required in cells if required),
        "optional_fields": ("notes_status",),
    }
    if formula_policy is not None:
        payload["formula_promotion_policy"] = formula_policy
    return payload


def _request(*, intended_use: str = handoff.INTENDED_USE, path: str = "", path_ref: str = "", schema: dict | None = None, client_ref: str = "capital_hilton", workflow_ref: str = "capital_hilton_invoice_workflow", world_ref: str = "finance") -> dict:
    payload = {
        "request_id": "mission_control_chat_request_capital_hilton_audit_handoff_fixture",
        "workflow_ref": workflow_ref,
        "world_ref": world_ref,
        "client_ref": client_ref,
        "operator_goal": "Prepare Capital Hilton sheet audit handoff.",
        "operator_message": "Here is the approved workbook path and sheet mapping.",
        "sanitized_message_summary": "Prepare audit handoff.",
        "intended_use": intended_use,
        "operator_approval_marker": "operator_selected_pc_path",
        "authority_boundary": dict(handoff.AUTHORITY_BOUNDARY),
        "created_at": FIXED_NOW,
    }
    if path:
        payload["approved_pc_readable_path"] = path
    if path_ref:
        payload["approved_path_ref"] = path_ref
    if schema is not None:
        payload["sheet_schema_mapping"] = schema
    return payload


def _local_surface_result(*, complete: bool = True, client_ref: str = "capital_hilton", workflow_ref: str = "capital_hilton_invoice_workflow", world_ref: str = "finance", unsafe_flag: str | None = None, confirmed: bool = True) -> dict:
    fields = {
        "invoice_number": "B2",
        "performance_dates": "B3",
        "rate": "B4",
        "subtotal_or_total": "B5",
        "po_reference": "B6",
        "notes_status": "B7",
    }
    if not complete:
        fields.pop("po_reference")
    payload = {
        "kind": "LOCAL_SURFACE_RESULT",
        "request_id": "mission_control_local_surface_result_capital_hilton_mapping_fixture",
        "idempotency_key": "local_surface_result_capital_hilton_mapping_fixture",
        "payload_hash": "fixture_local_surface_result_hash",
        "created_at": FIXED_NOW,
        "intended_use": handoff.SCHEMA_MAPPING_INTENDED_USE,
        "client_ref": client_ref,
        "workflow_ref": workflow_ref,
        "world_ref": world_ref,
        "operator_confirmed_mapping": confirmed,
        "operator_provided": True,
        "body_read": False,
        "workbook_body_read": False,
        "spreadsheet_cell_read": False,
        "ocr_performed": False,
        "external_llm_shared": False,
        "external_action": False,
        "path_translation_guessed": False,
        "authority_boundary": dict(handoff.AUTHORITY_BOUNDARY),
        "result": {
            "sheet_tab_name": "Invoice",
            "field_mappings": fields,
            "formula_policy": "operator_confirmation_required",
        },
    }
    if unsafe_flag is not None:
        payload[unsafe_flag] = True
    return payload


def test_required_models_exist_with_required_fields():
    assert tuple(field.name for field in fields(handoff.ClientInvoiceWorkbookPathApprovalRequest)) == (
        "request_id",
        "source_request_id",
        "intended_use",
        "client_ref",
        "workflow_ref",
        "world_ref",
        "workbook_ref",
        "workbook_identity",
        "approved_pc_readable_path",
        "approved_path_ref",
        "operator_approval_marker",
        "authority_boundary",
        "validation_status",
        "missing_context",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(handoff.ApprovedWorkbookPathRef)) == (
        "path_ref_id",
        "client_ref",
        "workflow_ref",
        "world_ref",
        "workbook_ref",
        "approved_pc_readable_path",
        "approved_path_ref",
        "path_kind",
        "path_approval_status",
        "operator_approval_marker",
        "source_request_id",
        "mac_visible_path_rejected",
        "path_translation_guessed",
        "workbook_body_read",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(handoff.FormulaPromotionPolicy)) == (
        "policy_id",
        "selected_policy",
        "allowed_policy_states",
        "operator_confirmation_required",
        "deterministic_recalculation_required",
        "cached_readback_allowed_only_if_explicit",
        "formula_values_not_promoted",
        "formula_evaluation_allowed",
        "next_safe_move",
    )
    assert "live_audit_ready" in tuple(field.name for field in fields(handoff.ClientInvoiceAuditHandoffReadback))


def test_mac_visible_path_rejected_and_not_translated(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_handoff_request(
        _request(path="/Volumes/openclaw_e/Capital Hilton invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["path_approval_request"]["validation_status"] == "APPROVED_PC_PATH_REJECTED_MAC_VISIBLE"
    assert payload["audit_handoff_readback"]["status"] == "APPROVED_PC_PATH_REQUIRED"
    assert payload["approved_workbook_path_ref"] is None
    assert payload["live_audit_ready"] is False
    assert payload["machine_proof"]["mac_path_translation_guessed"] is False
    assert payload["machine_proof"]["workbook_body_read_performed"] is False


def test_approved_pc_readable_path_is_accepted_but_schema_still_required(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_handoff_request(
        _request(intended_use=handoff.PATH_APPROVAL_INTENDED_USE, path="/mnt/e/openclaw/capital_hilton_invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["path_approval_request"]["validation_status"] == "APPROVED_PC_PATH_CAPTURED"
    assert payload["approved_workbook_path_ref"]["path_approval_status"] == "APPROVED_PC_PATH_CAPTURED"
    assert payload["audit_handoff_readback"]["status"] == "APPROVED_PC_PATH_CAPTURED_SCHEMA_REQUIRED"
    assert payload["audit_handoff_readback"]["operator_headline"] == "Capital Hilton workbook path approved"
    assert payload["live_audit_ready"] is False
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False


def test_schema_mapping_is_accepted_but_path_still_required(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_handoff_request(
        _request(intended_use=handoff.SCHEMA_MAPPING_INTENDED_USE, schema=_schema()),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_mapping_request"]["validation_status"] == "SHEET_AUDIT_SCHEMA_CAPTURED"
    assert payload["schema_mapping"]["sheet_name"] == "Invoice"
    assert payload["audit_handoff_readback"]["status"] == "SCHEMA_MAPPING_CAPTURED_PATH_REQUIRED"
    assert payload["audit_handoff_readback"]["operator_headline"] == "Capital Hilton invoice sheet mapping captured"
    assert payload["live_audit_ready"] is False


def test_local_surface_schema_mapping_result_is_operator_guidance_not_sheet_data(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_local_surface_schema_mapping_result(
        _local_surface_result(),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["local_surface_result_receipt"]["receipt_status"] == "LOCAL_SURFACE_RESULT_SCHEMA_GUIDANCE_CAPTURED"
    assert payload["local_surface_result_receipt"]["operator_confirmed_mapping"] is True
    assert payload["local_surface_result_receipt"]["mapping_classification"] == "operator_provided_schema_guidance"
    assert payload["local_surface_result_receipt"]["verified_sheet_data"] is False
    assert payload["schema_mapping_request"]["validation_status"] == "SHEET_AUDIT_SCHEMA_CAPTURED"
    assert payload["schema_mapping"]["sheet_name"] == "Invoice"
    assert payload["schema_mapping"]["whitelisted_cells"][0]["cell_ref"] == "B2"
    assert payload["audit_handoff_readback"]["status"] == "SCHEMA_MAPPING_CAPTURED_PATH_REQUIRED"
    assert payload["live_audit_ready"] is False
    assert payload["machine_proof"]["operator_provided_schema_guidance"] is True
    assert payload["machine_proof"]["verified_sheet_data"] is False
    assert payload["machine_proof"]["workbook_body_read_performed"] is False
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False


def test_local_surface_schema_mapping_result_requires_capital_hilton_binding(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_local_surface_schema_mapping_result(
        _local_surface_result(workflow_ref="unknown"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["local_surface_result_receipt"]["receipt_status"] == "LOCAL_SURFACE_RESULT_BLOCKED"
    assert "workflow_ref=capital_hilton_invoice_workflow" in payload["local_surface_result_receipt"]["validation_errors"]
    assert payload["schema_mapping"] is None
    assert payload["live_audit_ready"] is False


def test_local_surface_schema_mapping_result_blocks_unsafe_flags(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_local_surface_schema_mapping_result(
        _local_surface_result(unsafe_flag="spreadsheet_cell_read"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["local_surface_result_receipt"]["receipt_status"] == "LOCAL_SURFACE_RESULT_UNSAFE_FLAGS"
    assert "spreadsheet_cell_read=false" in payload["local_surface_result_receipt"]["validation_errors"]
    assert payload["schema_mapping"] is None
    assert payload["machine_proof"]["operator_provided_schema_guidance"] is False
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False


def test_local_surface_schema_mapping_result_blocks_unconfirmed_mapping(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_local_surface_schema_mapping_result(
        _local_surface_result(confirmed=False),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["local_surface_result_receipt"]["receipt_status"] == "LOCAL_SURFACE_RESULT_UNCONFIRMED"
    assert "operator_confirmed_mapping=true" in payload["local_surface_result_receipt"]["validation_errors"]
    assert payload["schema_mapping"] is None


def test_local_surface_schema_mapping_result_reports_missing_mapping_fields(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_local_surface_schema_mapping_result(
        _local_surface_result(complete=False),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["local_surface_result_receipt"]["receipt_status"] == "LOCAL_SURFACE_RESULT_SCHEMA_GUIDANCE_INCOMPLETE"
    assert payload["schema_mapping_request"]["validation_status"] == "SHEET_AUDIT_SCHEMA_INCOMPLETE"
    assert payload["local_surface_result_receipt"]["missing_mapping_fields"] == ("po_reference",)
    assert payload["live_audit_ready"] is False


def test_local_surface_schema_mapping_result_can_make_handoff_ready_when_path_exists(tmp_path):
    _seed_registry(tmp_path)
    path_payload = handoff.process_handoff_request(
        _request(intended_use=handoff.PATH_APPROVAL_INTENDED_USE, path="/mnt/e/openclaw/capital_hilton_invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    handoff.write_exports(path_payload, tmp_path)

    payload = handoff.process_local_surface_schema_mapping_result(
        _local_surface_result(),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["local_surface_result_receipt"]["receipt_status"] == "LOCAL_SURFACE_RESULT_SCHEMA_GUIDANCE_CAPTURED"
    assert payload["live_audit_ready"] is True
    assert payload["audit_handoff_readback"]["status"] == "HANDOFF_READY_FOR_SHEET_AUDIT"
    assert payload["sheet_audit_request_template"]["intended_use"] == "client_invoice_sheet_audit"
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False


def test_incomplete_schema_is_blocked(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_handoff_request(
        _request(schema=_schema(complete=False), path="/mnt/e/openclaw/capital_hilton_invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_mapping_request"]["validation_status"] == "SHEET_AUDIT_SCHEMA_INCOMPLETE"
    assert "po_reference" in payload["schema_mapping_request"]["missing_context"]
    assert payload["audit_handoff_readback"]["status"] == "SHEET_AUDIT_SCHEMA_INCOMPLETE"
    assert payload["live_audit_ready"] is False


def test_default_formula_policy_is_conservative(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_handoff_request(
        _request(schema=_schema(), path="/mnt/e/openclaw/capital_hilton_invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    policy = payload["formula_promotion_policy"]

    assert policy["selected_policy"] == "operator_confirmation_required"
    assert policy["operator_confirmation_required"] is True
    assert policy["formula_evaluation_allowed"] is False
    assert payload["machine_proof"]["formula_policy_default_conservative"] is True


def test_both_path_and_schema_present_makes_live_audit_ready(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_handoff_request(
        _request(schema=_schema(), path="/mnt/e/openclaw/capital_hilton_invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["live_audit_ready"] is True
    assert payload["audit_handoff_readback"]["status"] == "HANDOFF_READY_FOR_SHEET_AUDIT"
    assert payload["audit_handoff_readback"]["operator_headline"] == "Capital Hilton sheet audit is ready"
    template = payload["sheet_audit_request_template"]
    assert template["intended_use"] == "client_invoice_sheet_audit"
    assert template["approved_pc_workbook_path_authorized"] is True
    assert template["sheet_audit_schema"]["sheet_target"]["sheet_name"] == "Invoice"


def test_path_then_schema_merges_existing_handoff_contract(tmp_path):
    _seed_registry(tmp_path)
    first = handoff.process_handoff_request(
        _request(intended_use=handoff.PATH_APPROVAL_INTENDED_USE, path="/mnt/e/openclaw/capital_hilton_invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    handoff.write_exports(first, tmp_path)

    second = handoff.process_handoff_request(
        _request(intended_use=handoff.SCHEMA_MAPPING_INTENDED_USE, schema=_schema()),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert second["approved_workbook_path_ref"]["path_approval_status"] == "APPROVED_PC_PATH_CAPTURED"
    assert second["schema_mapping"]["schema_mapping_status"] == "SHEET_AUDIT_SCHEMA_CAPTURED"
    assert second["live_audit_ready"] is True


def test_capital_hilton_requires_explicit_client_workflow_world_refs(tmp_path):
    _seed_registry(tmp_path)

    payload = handoff.process_handoff_request(
        _request(schema=_schema(), path="/mnt/e/openclaw/capital_hilton_invoice.xlsx", workflow_ref="unknown"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["path_approval_request"]["validation_status"] == "HANDOFF_CONTEXT_MISSING"
    assert payload["schema_mapping_request"]["validation_status"] == "HANDOFF_CONTEXT_MISSING"
    assert payload["live_audit_ready"] is False
    assert "capital_hilton_invoice_workflow" in payload["audit_handoff_readback"]["missing_items"]


def test_export_writes_parseable_readmodel_and_operator_markdown(tmp_path, capsys):
    _seed_registry(tmp_path)

    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / handoff.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / handoff.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == handoff.READ_MODEL_ID
    assert summary["path_approval_status"] == "APPROVED_PC_PATH_CAPTURED"
    assert summary["schema_mapping_status"] in {"NO_SCHEMA_REQUESTED", "SHEET_AUDIT_SCHEMA_MISSING"}
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert "Path/schema handoff contract only" in operator


def test_generated_outputs_have_no_credentials_private_bodies_or_cell_reads(tmp_path):
    _seed_registry(tmp_path)
    payload = handoff.process_handoff_request(
        _request(schema=_schema(), path="/mnt/e/openclaw/capital_hilton_invoice.xlsx"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    handoff.write_exports(payload, tmp_path)
    combined = (tmp_path / handoff.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / handoff.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert payload["machine_proof"]["workbook_body_read_performed"] is False
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False
    assert payload["machine_proof"]["schema_inference_performed"] is False
    assert payload["machine_proof"]["formula_evaluation_performed"] is False
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined)
    for forbidden in ("actual secret", "credential value", "password value", "raw private body value", "cell value"):
        assert forbidden not in lowered
    assert all(value is False for value in payload["authority_boundary"].values())
