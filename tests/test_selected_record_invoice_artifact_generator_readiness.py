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


def test_existing_fixture_generators_are_not_selected_record_safe():
    audit = readiness.audit_existing_generators()

    assert {item.module_ref for item in audit} == {
        "invoice_artifact_builder",
        "capital_hilton_invoice_artifact_generator",
    }
    assert all(item.found for item in audit)
    assert all(item.selected_record_safe is False for item in audit)
    assert "fixture" in audit[0].input_source.lower() or "constants" in audit[0].input_source.lower()


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
    assert payload["machine_proof"]["existing_fixture_generators_not_selected_record_safe"] is True
    assert payload["machine_proof"]["no_cell_read"] is True


def test_no_send_coupa_email_ledger_authority_enabled():
    assert all(value is False for value in readiness.AUTHORITY_BOUNDARY.values())
