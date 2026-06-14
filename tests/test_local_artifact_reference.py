import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_artifact_reference as artifacts
from scripts.export_local_artifact_reference import main as export_main


FIXED_NOW = "2026-05-26T02:00:00+00:00"


def _request(**overrides):
    payload = {
        "request_id": "artifact_reference_fixture",
        "request_type": "ARTIFACT_REFERENCE_APPROVAL",
        "artifact_ref": "artifact_ref:fixture:capital_hilton_workbook",
        "artifact_kind": "invoice_workbook",
        "artifact_label": "Capital Hilton invoice workbook fixture",
        "intended_use": artifacts.APPROVAL_INTENDED_USE,
        "artifact_intended_use": "client_invoice_sheet_audit",
        "world_ref": "finance",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "client_ref": "capital_hilton",
        "approved_pc_readable_path": "/mnt/e/openclaw/fixtures/capital_hilton_invoice_workbook.xlsx",
        "path_mapping_verified": True,
        "operator_approved": True,
        "approved_for_read": True,
        "approved_for_write": False,
        "body_read": False,
        "content_extracted": False,
        "external_shared": False,
        "approval_source": "fixture_operator_approval",
        "created_at": FIXED_NOW,
    }
    payload.update(overrides)
    return payload


def test_required_models_exist():
    assert "artifact_ref" in tuple(field.name for field in fields(artifacts.LocalArtifactReference))
    assert "approved_for_read" in tuple(field.name for field in fields(artifacts.ApprovedReadableArtifact))
    assert "validation_errors" in tuple(field.name for field in fields(artifacts.ArtifactApprovalReceipt))
    assert "binding_status" in tuple(field.name for field in fields(artifacts.ArtifactScopeBinding))
    assert "live_read_ready" in tuple(field.name for field in fields(artifacts.ArtifactReadinessState))


def test_artifact_approval_request_shape_is_recognized():
    assert artifacts.is_artifact_approval_request(_request()) is True
    assert artifacts.is_artifact_approval_request(_request(intended_use="client_invoice_sheet_audit")) is False


def test_generic_approved_artifact_reference_can_be_created():
    payload = artifacts.evaluate_artifact_reference(
        _request(),
        expected_scope={
            "world_ref": "finance",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "client_ref": "capital_hilton",
        },
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_READY_FOR_READ"
    assert payload["artifact_readiness_state"]["live_read_ready"] is True
    assert payload["approved_readable_artifact"]["approved_for_read"] is True
    assert payload["approved_readable_artifact"]["approved_for_write"] is False
    assert payload["approved_readable_artifact"]["body_read"] is False
    assert payload["machine_proof"]["generic_artifact_reference_contract"] is True
    assert payload["machine_proof"]["capital_hilton_fixture_only"] is False


def test_scope_binding_is_required():
    payload = artifacts.evaluate_artifact_reference(
        _request(world_ref="", workflow_ref="", client_ref="", project_ref=""),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_scope_binding"]["binding_status"] == "ARTIFACT_SCOPE_MISSING"
    assert payload["artifact_readiness_state"]["live_read_ready"] is False
    assert "client_ref or project_ref" in payload["artifact_readiness_state"]["missing_items"]


def test_pc_readable_path_is_distinct_from_mac_path_metadata():
    payload = artifacts.evaluate_artifact_reference(
        _request(approved_pc_readable_path="/Volumes/openclaw_e/Capital Hilton.xlsx", mac_path="/Volumes/openclaw_e/Capital Hilton.xlsx"),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_MAC_PATH_NOT_PC_READABLE"
    assert payload["approved_readable_artifact"] is None
    assert payload["machine_proof"]["path_translation_guessed"] is False


def test_unverified_path_mapping_blocks_approval():
    payload = artifacts.evaluate_artifact_reference(
        _request(path_mapping_verified=False),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_PC_PATH_REQUIRED"
    assert payload["artifact_readiness_state"]["live_read_ready"] is False
    assert payload["approved_readable_artifact"] is None


def test_read_approval_is_distinct_from_write_approval():
    payload = artifacts.evaluate_artifact_reference(
        _request(approved_for_write=True),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_WRITE_AUTHORITY_BLOCKED"
    assert payload["artifact_readiness_state"]["live_read_ready"] is False
    assert payload["machine_proof"]["approved_for_write"] is True


def test_body_or_content_read_blocks_readiness():
    payload = artifacts.evaluate_artifact_reference(
        _request(body_read=True),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_BODY_OR_CONTENT_ALREADY_READ_BLOCKED"
    assert payload["approved_readable_artifact"] is None
    assert payload["machine_proof"]["body_read_performed"] is False


def test_content_extraction_blocks_readiness():
    payload = artifacts.evaluate_artifact_reference(
        _request(content_extracted=True),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_BODY_OR_CONTENT_ALREADY_READ_BLOCKED"
    assert payload["approved_readable_artifact"] is None


def test_external_share_blocks_readiness():
    payload = artifacts.evaluate_artifact_reference(
        _request(external_shared=True),
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_EXTERNAL_SHARE_BLOCKED"
    assert payload["approved_readable_artifact"] is None


def test_unknown_or_mismatched_scope_does_not_unlock_readiness():
    payload = artifacts.evaluate_artifact_reference(
        _request(client_ref="st_annes"),
        expected_scope={
            "world_ref": "finance",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "client_ref": "capital_hilton",
        },
        generated_at=FIXED_NOW,
    )

    assert payload["artifact_readiness_state"]["readiness_status"] == "ARTIFACT_SCOPE_MISMATCH"
    assert payload["approved_readable_artifact"] is None


def test_find_approved_readable_artifact_respects_scope_and_kind():
    payload = artifacts.evaluate_artifact_reference(_request(), generated_at=FIXED_NOW)

    found = artifacts.find_approved_readable_artifact(
        payload,
        world_ref="finance",
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="capital_hilton",
        artifact_kind="invoice_workbook",
        intended_use="client_invoice_sheet_audit",
    )
    missing = artifacts.find_approved_readable_artifact(
        payload,
        world_ref="finance",
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="st_annes",
        artifact_kind="invoice_workbook",
        intended_use="client_invoice_sheet_audit",
    )

    assert found is not None
    assert missing is None


def test_export_writes_parseable_readmodel_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / artifacts.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / artifacts.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == artifacts.READ_MODEL_ID
    assert summary["live_read_ready"] is True
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert "Approved PC-readable artifact reference contract only" in operator


def test_generated_outputs_have_no_credentials_private_bodies_or_active_authority(tmp_path):
    payload = artifacts.evaluate_artifact_reference(_request(), generated_at=FIXED_NOW)
    artifacts.write_exports(payload, tmp_path)
    combined = (tmp_path / artifacts.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / artifacts.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert payload["machine_proof"]["workbook_body_read_performed"] is False
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False
    assert payload["machine_proof"]["ocr_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined)
    assert "password value" not in lowered
    assert all(value is False for value in payload["authority_boundary"].values())
