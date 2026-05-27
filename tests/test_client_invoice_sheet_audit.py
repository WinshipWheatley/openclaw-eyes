import json
import re
import sys
import zipfile
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_sheet_audit as audit
import client_invoice_workbook_registry as registry
from scripts.export_client_invoice_sheet_audit import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"


def _write_fixture_xlsx(path: Path, cells: dict[str, tuple]) -> None:
    rows: dict[int, list[str]] = {}
    for cell_ref, spec in cells.items():
        row_number = int(re.search(r"[0-9]+", cell_ref).group(0))
        kind = spec[0]
        if kind == "inline":
            xml = f'<c r="{cell_ref}" t="inlineStr"><is><t>{spec[1]}</t></is></c>'
        elif kind == "number":
            xml = f'<c r="{cell_ref}"><v>{spec[1]}</v></c>'
        elif kind == "formula":
            xml = f'<c r="{cell_ref}"><f>{spec[1]}</f><v>{spec[2]}</v></c>'
        else:
            xml = f'<c r="{cell_ref}"/>'
        rows.setdefault(row_number, []).append(xml)
    sheet_rows = "\n".join(f'<row r="{row}">{"".join(values)}</row>' for row, values in sorted(rows.items()))
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Invoice" sheetId="1" r:id="rId1"/></sheets>
</workbook>
""",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
""",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{sheet_rows}</sheetData>
</worksheet>
""",
        )


def _seed_registry(export_root: Path, *, path_ref: str = "fixture_path_ref:capital_hilton_invoice_workbook") -> dict:
    request = registry.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    request["mac_visible_path_ref"] = path_ref
    payload = registry.register_workbook_request(request, export_root=export_root, generated_at=FIXED_NOW)
    registry.write_exports(payload, export_root)
    return payload


def _schema(*, include_formula_policy: bool = False) -> dict:
    formula_policy = (
        "ALLOW_CACHED_READBACK_IF_EXPLICITLY_ALLOWED"
        if include_formula_policy
        else "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS"
    )
    cells = [
        ("client_name", "A1", "text", True),
        ("invoice_number", "B2", "text", True),
        ("performance_dates", "B3", "text", True),
        ("rate", "B4", "currency", True),
        ("total", "B5", "currency", True),
        ("coupa_po_reference", "B6", "text", True),
        ("notes_status", "B7", "text", False),
    ]
    return {
        "schema_id": "capital_hilton_invoice_sheet_schema:v0",
        "schema_version": "v0",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "world_ref": "finance",
        "sheet_target": {
            "sheet_name": "Invoice",
            "allowed_cells": [
                {
                    "field_name": field_name,
                    "cell_ref": cell_ref,
                    "expected_value_type": expected_type,
                    "required": required,
                    "formula_policy": formula_policy,
                }
                for field_name, cell_ref, expected_type, required in cells
            ],
            "allowed_columns": [],
        },
        "required_fields": tuple(field for field, _cell, _type, required in cells if required),
        "optional_fields": ("notes_status",),
        "formula_cached_readback_policy": formula_policy,
        "known_facts": {"client_name": "Capital Hilton"},
    }


def _audit_request(*, workbook_path: Path | None = None, schema: dict | None = None, client_ref: str = "capital_hilton") -> dict:
    request = {
        "request_id": "mission_control_chat_request_capital_hilton_sheet_audit_fixture",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "world_ref": "finance",
        "client_ref": client_ref,
        "operator_goal": "Audit the Capital Hilton invoice sheet.",
        "operator_message": "Audit the Capital Hilton invoice sheet.",
        "sanitized_message_summary": "Audit the Capital Hilton invoice sheet.",
        "intended_use": audit.INTENDED_USE,
        "approved_pc_workbook_path_authorized": workbook_path is not None,
        "authority_boundary": dict(audit.AUTHORITY_BOUNDARY),
    }
    if workbook_path is not None:
        request["approved_pc_workbook_path"] = workbook_path.as_posix()
        request["approved_pc_workbook_path_ref"] = "approved_pc_path_ref:fixture_capital_hilton_invoice_workbook"
    if schema is not None:
        request["sheet_audit_schema"] = schema
    return request


def test_required_models_exist_with_required_fields():
    assert tuple(field.name for field in fields(audit.ClientInvoiceSheetAuditRequest)) == (
        "request_id",
        "source_request_id",
        "intended_use",
        "client_ref",
        "workflow_ref",
        "world_ref",
        "workbook_ref",
        "registry_readmodel_ref",
        "approved_pc_path_ref",
        "schema_ref",
        "authority_boundary",
        "validation_status",
        "missing_context",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(audit.ClientInvoiceSheetAuditSchema)) == (
        "schema_id",
        "schema_version",
        "client_ref",
        "workflow_ref",
        "world_ref",
        "sheet_target",
        "required_fields",
        "optional_fields",
        "expected_value_types",
        "formula_cached_readback_policy",
        "known_facts",
        "authority_boundary",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(audit.ClientInvoiceSheetAuditResult))[-9:-1] == (
        "body_ingested",
        "arbitrary_parse",
        "inferred_schema",
        "full_sheet_dump",
        "formula_evaluated",
        "macro_processed",
        "external_links_followed",
        "external_action",
    )
    assert "operator_headline" in tuple(field.name for field in fields(audit.ClientInvoiceSheetAuditReadback))


def test_no_workbook_registered_fails_closed(tmp_path):
    workbook = tmp_path / "invoice.xlsx"
    _write_fixture_xlsx(workbook, {"A1": ("inline", "Capital Hilton")})

    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_NO_WORKBOOK_REGISTERED"
    assert payload["audit_readback"]["next_action"] == "Next: Register or capture the Capital Hilton invoice workbook first."
    assert payload["machine_proof"]["workbook_opened"] is False
    assert payload["machine_proof"]["whitelisted_cells_read"] is False


def test_registered_workbook_without_approved_readable_pc_path_fails_closed(tmp_path):
    _seed_registry(tmp_path)

    payload = audit.run_audit(_audit_request(schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)

    assert payload["audit_result"]["status"] == "APPROVED_PC_PATH_REQUIRED"
    assert payload["audit_result"]["path_pc_readable"] is False
    assert payload["audit_readback"]["operator_headline"] == "PC-readable workbook needed"
    assert payload["machine_proof"]["workbook_opened"] is False


def test_mac_visible_path_is_not_guessed_or_translated(tmp_path):
    _seed_registry(tmp_path, path_ref="mac_path_ref:volumes_openclaw_e_capital_hilton_invoice_workbook")

    payload = audit.run_audit(_audit_request(schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)

    assert payload["audit_result"]["status"] == "APPROVED_PC_PATH_REQUIRED"
    assert "Mac-to-PC path" in payload["audit_readback"]["operator_message"]
    assert payload["audit_request"]["approved_pc_path_ref"] == ""
    assert payload["machine_proof"]["workbook_opened"] is False


def test_schema_missing_fails_closed_without_layout_inference(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice.xlsx"
    _write_fixture_xlsx(workbook, {"A1": ("inline", "Capital Hilton"), "Z99": ("inline", "NON_WHITELISTED_SENTINEL")})

    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=None), export_root=tmp_path, generated_at=FIXED_NOW)
    rendered = audit.stable_json(payload)

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_SCHEMA_MISSING"
    assert payload["audit_result"]["schema_explicit"] is False
    assert payload["audit_result"]["fields_read"] == ()
    assert payload["machine_proof"]["workbook_opened"] is False
    assert payload["machine_proof"]["inferred_schema"] is False
    assert "NON_WHITELISTED_SENTINEL" not in rendered


def test_happy_path_fixture_workbook_reads_whitelisted_cells_only(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice.xlsx"
    _write_fixture_xlsx(
        workbook,
        {
            "A1": ("inline", "Capital Hilton"),
            "B2": ("inline", "INV-2026-001"),
            "B3": ("inline", "2026-05-12, 2026-05-13"),
            "B4": ("number", "1600"),
            "B5": ("number", "1600"),
            "B6": ("inline", "PO-CH-12345"),
            "B7": ("inline", "Ready for local artifact prep"),
            "Z99": ("inline", "NON_WHITELISTED_SENTINEL"),
        },
    )

    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)
    fields = {field["field_name"]: field for field in payload["audit_result"]["fields_read"]}
    rendered = audit.stable_json(payload)

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_COMPLETE"
    assert payload["audit_readback"]["operator_headline"] == "Capital Hilton invoice sheet audited"
    assert payload["audit_result"]["po_reference_status"] == "PO_REFERENCE_PRESENT_VERIFIED_FROM_WHITELISTED_FIELD"
    assert fields["coupa_po_reference"]["value"] == "PO-CH-12345"
    assert fields["coupa_po_reference"]["accepted_as_openclaw_fact"] is True
    assert payload["machine_proof"]["workbook_opened"] is True
    assert payload["machine_proof"]["whitelisted_cells_read"] is True
    assert payload["machine_proof"]["full_sheet_dump"] is False
    assert "NON_WHITELISTED_SENTINEL" not in rendered
    assert '"rows"' not in rendered


def test_required_missing_field_is_detected(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice_missing_number.xlsx"
    _write_fixture_xlsx(
        workbook,
        {
            "A1": ("inline", "Capital Hilton"),
            "B2": ("inline", ""),
            "B3": ("inline", "2026-05-12"),
            "B4": ("number", "1600"),
            "B5": ("number", "1600"),
            "B6": ("inline", "PO-CH-12345"),
        },
    )

    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_REQUIRED_FIELD_MISSING"
    assert "invoice_number" in payload["audit_result"]["fields_missing"]
    assert payload["audit_readback"]["next_action"] == "Next: fix the invoice sheet fields listed below."


def test_po_reference_missing_remains_missing(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice_missing_po.xlsx"
    _write_fixture_xlsx(
        workbook,
        {
            "A1": ("inline", "Capital Hilton"),
            "B2": ("inline", "INV-2026-001"),
            "B3": ("inline", "2026-05-12"),
            "B4": ("number", "1600"),
            "B5": ("number", "1600"),
            "B6": ("inline", ""),
        },
    )

    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_REQUIRED_FIELD_MISSING"
    assert payload["audit_result"]["po_reference_status"] == "PO_REFERENCE_MISSING_OR_UNVERIFIED"
    assert "coupa_po_reference" in payload["audit_result"]["fields_missing"]
    assert payload["audit_readback"]["next_action"] == "Next: confirm the Coupa PO/reference."


def test_mapped_value_type_mismatches_are_not_promoted(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice_mismapped_values.xlsx"
    _write_fixture_xlsx(
        workbook,
        {
            "A1": ("inline", "Capital Hilton"),
            "B2": ("inline", "INV-2026-001"),
            "B3": ("inline", "2026-05-12"),
            "B4": ("number", "1600"),
            "B5": ("inline", "Dates"),
            "B6": ("inline", "2026-05-08, 2026-05-15, 2026-05-22"),
        },
    )

    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)
    fields = {field["field_name"]: field for field in payload["audit_result"]["fields_read"]}
    conflicts = {conflict["field_name"]: conflict for conflict in payload["audit_result"]["conflicts_vs_known_facts"]}

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_REQUIRED_FIELD_MISSING"
    assert payload["audit_result"]["po_reference_status"] == "PO_REFERENCE_MISSING_OR_UNVERIFIED"
    assert fields["total"]["accepted_as_openclaw_fact"] is False
    assert fields["total"]["promotion_status"] == "VALUE_TYPE_MISMATCH"
    assert fields["coupa_po_reference"]["accepted_as_openclaw_fact"] is False
    assert fields["coupa_po_reference"]["mismatch_reason"] == "PO_REFERENCE_LOOKS_LIKE_DATE_LIST"
    assert "total" in payload["audit_result"]["fields_missing"]
    assert "coupa_po_reference" in payload["audit_result"]["fields_missing"]
    assert conflicts["total"]["reason"] == "EXPECTED_CURRENCY_VALUE"


def test_formula_cells_are_reported_but_not_promoted_without_policy(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice_formula.xlsx"
    _write_fixture_xlsx(
        workbook,
        {
            "A1": ("inline", "Capital Hilton"),
            "B2": ("inline", "INV-2026-001"),
            "B3": ("inline", "2026-05-12"),
            "B4": ("number", "1600"),
            "B5": ("formula", "B4*1", "1600"),
            "B6": ("inline", "PO-CH-12345"),
        },
    )

    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)
    fields = {field["field_name"]: field for field in payload["audit_result"]["fields_read"]}

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_FORMULA_CONFIRMATION_REQUIRED"
    assert payload["audit_result"]["formula_evaluated"] is False
    assert payload["audit_result"]["fields_blocked_due_to_formula"][0]["field_name"] == "total"
    assert fields["total"]["value"] == 1600
    assert fields["total"]["formula_present"] is True
    assert fields["total"]["verified"] is False
    assert fields["total"]["accepted_as_openclaw_fact"] is False
    assert fields["total"]["promotion_status"] == "FORMULA_VALUE_REQUIRES_PROMOTION_POLICY"
    assert payload["audit_readback"]["next_action"] == "Next: confirm formula-derived values or approve a promotion policy."


def test_capital_hilton_binding_requires_explicit_client_workflow_world(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice.xlsx"
    _write_fixture_xlsx(workbook, {"A1": ("inline", "Acme")})

    payload = audit.run_audit(
        _audit_request(workbook_path=workbook, schema=_schema(), client_ref="acme"),
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert payload["audit_result"]["status"] == "SHEET_AUDIT_CONTEXT_MISSING"
    assert payload["machine_proof"]["workbook_opened"] is False


def test_export_writes_parseable_blocked_readmodel_and_operator_markdown(tmp_path, capsys):
    _seed_registry(tmp_path)

    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / audit.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / audit.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == audit.READ_MODEL_ID
    assert summary["status"] == "APPROVED_PC_PATH_REQUIRED"
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["workbook_opened"] is False
    assert payload["machine_proof"]["fixture_workbook_reads_are_test_only"] is True
    assert payload["machine_proof"]["live_capital_hilton_requires_approved_business_workbook_path"] is True
    assert "Whitelisted invoice sheet audit" in operator


def test_generated_outputs_have_no_credentials_private_bodies_or_full_sheet_dump(tmp_path):
    _seed_registry(tmp_path)
    workbook = tmp_path / "invoice.xlsx"
    _write_fixture_xlsx(workbook, {"A1": ("inline", "Capital Hilton"), "Z99": ("inline", "NON_WHITELISTED_SENTINEL")})
    payload = audit.run_audit(_audit_request(workbook_path=workbook, schema=_schema()), export_root=tmp_path, generated_at=FIXED_NOW)
    audit.write_exports(payload, tmp_path)
    combined = (tmp_path / audit.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / audit.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert payload["machine_proof"]["credential_handling_performed"] is False
    assert payload["machine_proof"]["raw_body_ingestion_performed"] is False
    assert payload["machine_proof"]["full_sheet_dump"] is False
    assert payload["machine_proof"]["arbitrary_parse"] is False
    assert "NON_WHITELISTED_SENTINEL" not in combined
    for forbidden in ("actual secret", "credential value", "password value", "raw private body value", "full row dump"):
        assert forbidden not in lowered
    assert all(value is False for value in payload["authority_boundary"].values())
