import json
from pathlib import Path

import invoice_review_state_machine as state_machine
import selected_record_invoice_artifact_generator_readiness as readiness
from scripts.export_selected_record_invoice_artifact_generator_readiness import main as export_main


FIXED_NOW = "2026-05-28T04:00:00+00:00"


def _state(**overrides):
    state = state_machine._default_state(generated_at=FIXED_NOW)
    state.update(
        {
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "invoice_record_selection_status": "OPERATOR_CONFIRMED",
            "invoice_period_status": "OPERATOR_CONFIRMED",
            "invoice_period_label": "May 2026",
            "invoice_record_label": "May tab / page 2",
            "generated_artifact_status": "ARTIFACT_GENERATOR_NOT_WIRED",
        }
    )
    state.update(overrides)
    return state


def _all_receipts():
    return (
        readiness.SOURCE_WORKBOOK_LINKAGE_RECEIPT,
        readiness.SELECTED_RECORD_RECEIPT,
        readiness.GENERATION_AUTHORITY_RECEIPT,
    )


def _matching_workbook_payloads():
    workbook_ref = "workbook_ref:client_invoice:capital_hilton:capital_hilton_invoice_workflow:match"
    registry = {
        "active_record": {
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "workbook_ref": workbook_ref,
        }
    }
    artifact = {
        "approved_readable_artifact": {
            "artifact_ref": workbook_ref,
            "artifact_kind": "invoice_workbook",
            "intended_use": "client_invoice_sheet_audit",
            "approved_for_read": True,
            "approved_for_write": False,
            "body_read": False,
            "content_extracted": False,
            "external_shared": False,
            "path_mapping_verified": True,
            "pc_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/source.xlsx",
            "mac_path": "/Volumes/openclaw_e/artifacts/invoice_workbooks/capital_hilton/source.xlsx",
            "scope_binding": {
                "world_ref": "finance",
                "workflow_ref": "capital_hilton_invoice_workflow",
                "client_ref": "capital_hilton",
            },
        }
    }
    return registry, artifact


def test_existing_fixture_generators_are_not_selected_record_safe():
    audit = readiness.audit_existing_generators()

    assert {item.module_ref for item in audit} == {
        "invoice_artifact_builder",
        "capital_hilton_invoice_artifact_generator",
    }
    assert all(item.found for item in audit)
    assert all(item.selected_record_safe is False for item in audit)
    assert "fixture" in audit[0].input_source.lower() or "constants" in audit[0].input_source.lower()


def test_existing_approved_source_workbook_reference_can_satisfy_linkage():
    registry, artifact = _matching_workbook_payloads()
    linkage = readiness.discover_source_workbook_linkage(
        workbook_registry_payload=registry,
        artifact_reference_payload=artifact,
    )

    assert linkage.source_workbook_found is True
    assert linkage.source_workbook_confirmed is True
    assert linkage.source_workbook_ref == registry["active_record"]["workbook_ref"]
    assert linkage.source_workbook_pc_path.startswith("/mnt/e/openclaw/")
    assert linkage.source_workbook_mac_path.startswith("/Volumes/openclaw_e/")
    assert linkage.receipt_name_if_confirmed == readiness.SOURCE_WORKBOOK_LINKAGE_RECEIPT
    assert linkage.no_workbook_body_read is True
    assert linkage.no_cell_read is True


def test_mismatched_workbook_registry_and_artifact_keeps_linkage_blocked():
    registry, artifact = _matching_workbook_payloads()
    registry["active_record"]["workbook_ref"] = "workbook_ref:client_invoice:capital_hilton:other"
    linkage = readiness.discover_source_workbook_linkage(
        workbook_registry_payload=registry,
        artifact_reference_payload=artifact,
    )

    assert linkage.source_workbook_found is True
    assert linkage.source_workbook_confirmed is False
    assert linkage.blocker == "ACTIVE_WORKBOOK_REF_DIFFERS_FROM_APPROVED_READABLE_ARTIFACT_REF"
    assert "Confirm which Capital Hilton workbook" in linkage.guided_action


def test_readiness_reports_missing_source_workbook_linkage():
    result = readiness.evaluate_readiness(
        state=_state(),
        receipts=(readiness.SELECTED_RECORD_RECEIPT, readiness.GENERATION_AUTHORITY_RECEIPT),
        source_workbook_ref=None,
        source_workbook_path=None,
        approved_generation_inputs={"line_items": []},
    )

    assert result.generator_ready is False
    assert "source_workbook_ref" in result.missing_inputs
    assert readiness.SOURCE_WORKBOOK_LINKAGE_RECEIPT in result.missing_inputs
    assert result.source_workbook_linkage_status == "MISSING_LINKAGE"


def test_readiness_reports_missing_generation_authority():
    result = readiness.evaluate_readiness(
        state=_state(),
        receipts=(readiness.SOURCE_WORKBOOK_LINKAGE_RECEIPT, readiness.SELECTED_RECORD_RECEIPT),
        source_workbook_ref="workbook_ref:capital_hilton_running",
        source_workbook_path="/Volumes/openclaw_e/finance/Capital Hilton.xlsx",
        approved_generation_inputs={"line_items": []},
    )

    assert result.safe_to_generate is False
    assert readiness.GENERATION_AUTHORITY_RECEIPT in result.missing_inputs
    assert "generation authority" in result.next_operator_action.lower()


def test_readiness_identifies_workbook_read_scope_without_reading_cells():
    result = readiness.evaluate_readiness(
        state=_state(),
        receipts=_all_receipts(),
        source_workbook_ref="workbook_ref:capital_hilton_running",
        source_workbook_path="/Volumes/openclaw_e/finance/Capital Hilton.xlsx",
        approved_generation_inputs={"line_items": [{"description": "fixture"}]},
    )

    assert result.safe_to_generate is True
    assert result.workbook_read_required is False
    assert result.allowed_read_scope == "approved_selected_record_inputs_only_no_workbook_body_or_cell_read"


def test_no_generation_happens_without_required_receipts(tmp_path):
    result = readiness.generate_selected_record_candidate_artifact(
        state=_state(),
        receipts=(readiness.SELECTED_RECORD_RECEIPT,),
        source_workbook_ref="workbook_ref:capital_hilton_running",
        source_workbook_path="/Volumes/openclaw_e/finance/Capital Hilton.xlsx",
        approved_generation_inputs={"line_items": [{"description": "fixture"}]},
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "GENERATOR_NOT_READY"
    assert result["artifact_created"] is False
    assert not list((tmp_path / "generated").glob("**/*"))


def test_all_fixture_safe_prerequisites_create_candidate_artifact_and_receipt(tmp_path):
    result = readiness.generate_selected_record_candidate_artifact(
        state=_state(source_workbook_status="CONFIRMED"),
        receipts=_all_receipts(),
        source_workbook_ref="workbook_ref:capital_hilton_running",
        source_workbook_path="/Volumes/openclaw_e/finance/Capital Hilton.xlsx",
        approved_generation_inputs={
            "line_items": [{"description": "operator-confirmed fixture", "amount": 1600}],
            "total": 1600,
        },
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    artifact_path = Path(result["artifact_path"])
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["status"] == "GENERATED_ARTIFACT_CREATED"
    assert artifact_path.is_file()
    assert result["artifact_hash"].startswith("sha256:")
    assert result["receipt"]["receipt_name"] == "selected_record_invoice_artifact_candidate_created_receipt"
    assert result["receipt"]["invoice_period_label"] == "May 2026"
    assert result["receipt"]["invoice_record_label"] == "May tab / page 2"
    assert artifact_payload["candidate_only"] is True
    assert artifact_payload["attachment_ready"] is False
    assert artifact_payload["approval_ready"] is False
    assert result["artifact_linked_confirmed"] is False
    assert all(value is False for value in result["authority_boundary"].values())


def test_export_read_model_reports_current_blockers(tmp_path):
    db_path = tmp_path / "invoice_review.sqlite"
    state_machine.init_store(db_path)
    with state_machine._connect(db_path) as conn:
        state_machine._upsert_state(conn, _state())
    assert export_main(["--db-path", str(db_path), "--export-root", str(tmp_path), "--generated-at", FIXED_NOW]) == 0
    payload = json.loads((tmp_path / readiness.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert payload["readiness"]["generator_ready"] is False
    assert "source_workbook_ref" in payload["readiness"]["missing_inputs"]
    assert payload["source_workbook_linkage"]["source_workbook_confirmed"] is False
    assert payload["machine_proof"]["existing_fixture_generators_not_selected_record_safe"] is True
    assert payload["machine_proof"]["no_cell_read"] is True


def test_generation_authority_receipt_shape_is_scoped_to_selected_invoice(tmp_path):
    db_path = tmp_path / "invoice_review.sqlite"
    state_machine.init_store(db_path)
    with state_machine._connect(db_path) as conn:
        state_machine._upsert_state(conn, _state())
    payload = readiness.build_payload(db_path=db_path, generated_at=FIXED_NOW)
    authority = payload["generation_authority_receipt"]

    assert authority["receipt_name"] == readiness.GENERATION_AUTHORITY_RECEIPT
    assert authority["status"] == "MISSING"
    assert authority["scope_required"]["client_ref"] == "capital_hilton"
    assert authority["scope_required"]["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert authority["scope_required"]["invoice_period_label"] == "May 2026"
    assert authority["scope_required"]["invoice_record_label"] == "May tab / page 2"
    assert authority["does_not_equal_execution"] is True
    assert authority["allows_send_submit_ledger"] is False


def test_no_send_coupa_email_ledger_authority_enabled():
    assert all(value is False for value in readiness.AUTHORITY_BOUNDARY.values())
