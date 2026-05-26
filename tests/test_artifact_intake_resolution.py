import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_audit_handoff as handoff
import client_invoice_workbook_registry as registry
import local_artifact_reference as artifacts
import openclaw_request_processor as processor
import openclaw_request_router as router

FIXED_NOW = "2026-05-26T02:00:00+00:00"


def _set_bridge_root(monkeypatch, tmp_path: Path) -> Path:
    bridge_root = tmp_path / "openclaw_bridge"
    monkeypatch.setattr(artifacts, "PC_SHARED_BRIDGE_ROOT", bridge_root)
    return bridge_root


def _package_file(
    bridge_root: Path,
    *,
    source_request_id: str = "source_request_123",
    filename: str = "capital_hilton_invoice.xlsx",
) -> Path:
    path = bridge_root / "artifacts" / "invoice_workbooks" / source_request_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"opaque workbook fixture bytes")
    return path


def _seed_registry_and_mapping(export_root: Path) -> None:
    reg_req = registry.register_workbook_request(
        registry.make_capital_hilton_fixture_request(created_at=FIXED_NOW),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    registry.write_exports(reg_req, export_root)

    cells = [
        ("invoice_number", "B2", "text", True),
        ("performance_dates", "B3", "text", True),
        ("rate", "B4", "currency", True),
        ("subtotal_or_total", "B5", "currency", True),
        ("po_reference", "B6", "text", True),
        ("notes_status", "B7", "text", False),
    ]
    schema = {
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
        "required_fields": [field for field, _, _, required in cells if required],
        "optional_fields": ["notes_status"],
    }

    handoff_req = {
        "request_id": "test_handoff_req",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "operator_goal": "Prepare Capital Hilton sheet audit handoff.",
        "intended_use": handoff.INTENDED_USE,
        "sheet_schema_mapping": schema,
        "created_at": FIXED_NOW,
    }
    res = handoff.process_handoff_request(handoff_req, export_root=export_root, generated_at=FIXED_NOW)
    handoff.write_exports(res, export_root)


def _intake_request(**overrides):
    payload = {
        "request_id": "source_request_123",
        "idempotency_key": "idemp_key_123",
        "payload_hash": "hash_123",
        "request_type": "ARTIFACT_INTAKE_REQUEST",
        "intended_use": "register_or_resolve_invoice_workbook_artifact",
        "artifact_intended_use": "client_invoice_sheet_audit",
        "artifact_kind": "invoice_workbook",
        "artifact_label": "Capital Hilton Invoice Workbook",
        "world_ref": "finance",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "client_ref": "capital_hilton",
        "project_ref": "",
        "shared_artifact_path": "/Volumes/openclaw_e/artifacts/invoice_workbooks/source_request_123/capital_hilton_invoice.xlsx",
        "file_display_name": "capital_hilton_invoice.xlsx",
        "operator_selected": True,
        "operator_approved_for_read": True,
        "approved_for_read": True,
        "approved_for_write": False,
        "path_mapping_verified": True,
        "path_translation_guessed": False,
        "body_read": False,
        "workbook_body_read": False,
        "spreadsheet_cell_read": False,
        "content_extracted": False,
        "ocr_performed": False,
        "external_shared": False,
        "external_llm_shared": False,
        "external_action": False,
        "created_at": FIXED_NOW,
        "authority_boundary": {
            "handler_execution_allowed": False,
            "workflow_execution_allowed": False,
            "model_call_allowed": False,
            "agent_dispatch_allowed": False,
            "worker_dispatch_allowed": False,
            "external_action_allowed": False,
            "file_body_read_allowed": False,
            "workbook_body_read_allowed": False,
            "spreadsheet_cell_read_allowed": False,
            "ocr_allowed": False,
            "browser_allowed": False,
            "network_allowed": False,
            "credential_handling_allowed": False,
            "response_publication_allowed": False,
        },
    }
    payload.update(overrides)
    return payload


def test_intake_request_routes_to_generic_intake_handler():
    _envelope, decision = router.route_request(_intake_request())
    assert decision.route_status == "ROUTE_MATCHED"
    assert decision.selected_handler_id == "register_or_resolve_invoice_workbook_artifact.generic"


def test_pattern_a_bridge_translation_and_auto_approval(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root)

    payload = artifacts.evaluate_artifact_reference(_intake_request(), generated_at=FIXED_NOW)

    receipt = payload["artifact_resolution_receipt"]
    readiness = payload["artifact_readiness_state"]
    approved = payload["approved_readable_artifact"]

    expected = bridge_root / "artifacts" / "invoice_workbooks" / "source_request_123" / "capital_hilton_invoice.xlsx"
    assert receipt["resolution_status"] == "APPROVED_PC_PATH_CAPTURED"
    assert receipt["pc_path_resolved"] == expected.resolve(strict=False).as_posix()
    assert receipt["path_mapping_verified"] is True
    assert receipt["operator_approved"] is True
    assert readiness["live_read_ready"] is True
    assert readiness["readiness_status"] == "ARTIFACT_READY_FOR_READ"
    assert approved["approved_for_read"] is True
    assert approved["approved_for_write"] is False
    assert approved["body_read"] is False
    assert approved["content_extracted"] is False


def test_intake_accepts_xlsm_as_opaque_workbook_artifact(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root, filename="capital_hilton_invoice.xlsm")

    req = _intake_request(
        shared_artifact_path="/Volumes/openclaw_e/artifacts/invoice_workbooks/source_request_123/capital_hilton_invoice.xlsm",
        file_display_name="capital_hilton_invoice.xlsm",
    )
    payload = artifacts.evaluate_artifact_reference(req, generated_at=FIXED_NOW)

    assert payload["artifact_resolution_receipt"]["resolution_status"] == "APPROVED_PC_PATH_CAPTURED"
    assert payload["approved_readable_artifact"]["approved_for_read"] is True


def test_intake_without_shared_path_uses_only_request_scoped_package(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    expected = _package_file(bridge_root)

    payload = artifacts.evaluate_artifact_reference(
        _intake_request(shared_artifact_path=""),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_resolution_receipt"]["resolution_status"] == "APPROVED_PC_PATH_CAPTURED"
    assert payload["artifact_resolution_receipt"]["pc_path_resolved"] == expected.resolve(strict=False).as_posix()
    assert payload["approved_readable_artifact"] is not None


def test_intake_rejects_flat_layout_without_request_scoped_directory(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    flat = bridge_root / "artifacts" / "invoice_workbooks" / "capital_hilton_invoice.xlsx"
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_bytes(b"opaque workbook fixture bytes")

    req = _intake_request(
        shared_artifact_path="/Volumes/openclaw_e/artifacts/invoice_workbooks/capital_hilton_invoice.xlsx"
    )
    payload = artifacts.evaluate_artifact_reference(req, generated_at=FIXED_NOW)

    receipt = payload["artifact_resolution_receipt"]
    assert receipt["resolution_status"] == "APPROVED_PC_PATH_REQUIRED"
    assert "request-scoped package layout" in receipt["validation_errors"][0]
    assert payload["approved_readable_artifact"] is None


def test_intake_rejects_prefix_path_escape(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root, source_request_id="source_request_1234")

    req = _intake_request(
        shared_artifact_path="/Volumes/openclaw_e/artifacts/invoice_workbooks/source_request_1234/capital_hilton_invoice.xlsx"
    )
    payload = artifacts.evaluate_artifact_reference(req, generated_at=FIXED_NOW)

    receipt = payload["artifact_resolution_receipt"]
    assert receipt["resolution_status"] == "APPROVED_PC_PATH_REQUIRED"
    assert "request-scoped package layout" in receipt["validation_errors"][0]
    assert payload["approved_readable_artifact"] is None


def test_intake_rejects_arbitrary_mac_paths_outside_bridge_root(monkeypatch, tmp_path):
    _set_bridge_root(monkeypatch, tmp_path)
    req = _intake_request(shared_artifact_path="/Volumes/other_vol/some_user/capital_hilton_invoice.xlsx")
    payload = artifacts.evaluate_artifact_reference(req, generated_at=FIXED_NOW)

    receipt = payload["artifact_resolution_receipt"]
    assert receipt["resolution_status"] == "APPROVED_PC_PATH_REQUIRED"
    assert "outside the approved bridge artifact root" in receipt["validation_errors"][0]
    assert payload["approved_readable_artifact"] is None


def test_intake_requires_verified_mapping_even_if_file_exists(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root)

    payload = artifacts.evaluate_artifact_reference(
        _intake_request(path_mapping_verified=False),
        generated_at=FIXED_NOW,
    )

    receipt = payload["artifact_resolution_receipt"]
    assert receipt["resolution_status"] == "APPROVED_PC_PATH_REQUIRED"
    assert "path_mapping_verified must be true" in receipt["validation_errors"][0]
    assert payload["approved_readable_artifact"] is None


def test_intake_requires_scope_binding(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root)

    payload = artifacts.evaluate_artifact_reference(
        _intake_request(client_ref=""),
        generated_at=FIXED_NOW,
    )

    readiness = payload["artifact_readiness_state"]
    assert readiness["readiness_status"] == "ARTIFACT_SCOPE_MISSING"
    assert "client_ref or project_ref" in readiness["missing_items"]
    assert payload["approved_readable_artifact"] is None


def test_intake_blocks_expected_scope_mismatch(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root)

    payload = artifacts.evaluate_artifact_reference(
        _intake_request(),
        expected_scope={
            "world_ref": "finance",
            "workflow_ref": "other_workflow",
            "client_ref": "capital_hilton",
        },
        generated_at=FIXED_NOW,
    )

    readiness = payload["artifact_readiness_state"]
    assert readiness["readiness_status"] == "ARTIFACT_SCOPE_MISMATCH"
    assert payload["approved_readable_artifact"] is None


def test_intake_blocks_guessed_path_translation(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root)

    payload = artifacts.evaluate_artifact_reference(
        _intake_request(path_translation_guessed=True),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_PATH_TRANSLATION_GUESSED_BLOCKED"
    assert payload["approved_readable_artifact"] is None


def test_intake_does_not_broad_scan_artifact_root(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root, source_request_id="other_request_999")

    payload = artifacts.evaluate_artifact_reference(
        _intake_request(shared_artifact_path=""),
        generated_at=FIXED_NOW,
    )

    receipt = payload["artifact_resolution_receipt"]
    assert receipt["resolution_status"] == "WORKBOOK_NOT_FOUND"
    assert receipt["candidates"] == ()
    assert payload["approved_readable_artifact"] is None


def test_unsafe_flags_block_resolution(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root)

    payload = artifacts.evaluate_artifact_reference(_intake_request(approved_for_write=True), generated_at=FIXED_NOW)
    assert payload["artifact_resolution_receipt"]["resolution_status"] == "ARTIFACT_WRITE_AUTHORITY_BLOCKED"
    assert payload["approved_readable_artifact"] is None

    payload = artifacts.evaluate_artifact_reference(_intake_request(body_read=True), generated_at=FIXED_NOW)
    assert payload["artifact_resolution_receipt"]["resolution_status"] == "ARTIFACT_BODY_OR_CONTENT_ALREADY_READ_BLOCKED"
    assert payload["approved_readable_artifact"] is None

    payload = artifacts.evaluate_artifact_reference(_intake_request(spreadsheet_cell_read=True), generated_at=FIXED_NOW)
    assert payload["artifact_resolution_receipt"]["resolution_status"] == "ARTIFACT_BODY_OR_CONTENT_ALREADY_READ_BLOCKED"
    assert payload["approved_readable_artifact"] is None


def test_handoff_readiness_promoted_integrated_processor(monkeypatch, tmp_path):
    bridge_root = _set_bridge_root(monkeypatch, tmp_path)
    _package_file(bridge_root)
    _seed_registry_and_mapping(tmp_path)

    req_file = tmp_path / "inbox" / "mission_control_artifact_intake_request_capital_hilton.json"
    req_file.parent.mkdir(parents=True, exist_ok=True)
    req_file.write_text(json.dumps(_intake_request()), encoding="utf-8")

    response = processor.process_request_path(
        req_file,
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert response.internal_status == "RESPONSE_READY"
    assert response.operator_headline == "Capital Hilton workbook approved"
    assert "approved the local read reference" in response.operator_message or "whitelisted sheet audit is ready" in response.operator_message
    assert response.detail_disclosure["client_invoice_audit_handoff"]["live_audit_ready"] is True
    assert (tmp_path / "local_artifact_reference.json").exists()
    assert (tmp_path / "client_invoice_audit_handoff.json").exists()


def test_handoff_readiness_remains_false_if_artifact_missing(monkeypatch, tmp_path):
    _set_bridge_root(monkeypatch, tmp_path)
    _seed_registry_and_mapping(tmp_path)

    req_file = tmp_path / "inbox" / "mission_control_artifact_intake_request_capital_hilton.json"
    req_file.parent.mkdir(parents=True, exist_ok=True)
    req_file.write_text(json.dumps(_intake_request(shared_artifact_path="")), encoding="utf-8")

    response = processor.process_request_path(
        req_file,
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert response.internal_status == "BLOCKED_WITH_REASON"
    assert response.operator_headline == "Workbook access blocked"
    assert response.detail_disclosure["client_invoice_audit_handoff"]["live_audit_ready"] is False
