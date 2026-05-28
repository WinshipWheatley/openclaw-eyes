import json
from pathlib import Path

import client_invoice_workflow_framework as framework
import invoice_review_action_request_handler as action_handler
import invoice_review_state_machine as state_machine
import live_arts_md_invoice_review_bundle as bundle
from scripts.export_live_arts_md_invoice_review_bundle import main as export_main


FIXED_NOW = "2026-05-28T15:00:00+00:00"


def _confirmed_workbook_payload():
    return {
        "registry": {
            "client_records": [
                {
                    "client_ref": "live_arts_md",
                    "workflow_ref": "live_arts_md_invoice_workflow",
                    "workbook_ref": "workbook_ref:live_arts_md:running",
                    "workbook_display_name": "Invoice Live Arts MD! Running.xlsx",
                    "workbook_path_ref": "path_ref:operator_selected_live_arts_md_workbook",
                    "workbook_extension": ".xlsx",
                    "workbook_status": "WORKBOOK_CONFIRMED",
                    "approved_for_metadata_read": True,
                    "approved_for_cell_read": False,
                }
            ]
        }
    }


def test_live_arts_md_recipe_does_not_require_coupa_or_po():
    recipe = framework.recipes_by_client_ref()["live_arts_md"]

    assert not framework.recipe_selects_rail(recipe, framework.SUPPLIER_PORTAL_RAIL)
    assert not framework.recipe_selects_rail(recipe, framework.PURCHASE_ORDER_RAIL)
    assert recipe["client_specific_portal_requirements"]["supplier_portal_required"] is False
    assert recipe["client_specific_portal_requirements"]["purchase_order_required"] is False


def test_missing_source_workbook_produces_guided_source_action():
    payload = bundle.build_payload(generated_at=FIXED_NOW, workbook_registry_payload={})
    live = payload["live_arts_md_bundle"]

    assert live["source_workbook"]["status"] == "SOURCE_WORKBOOK_REQUIRED"
    assert live["blockers"][0] == "Choose the Live Arts MD source workbook."
    assert live["actionable_blockers"][0]["primary_action"]["label"] == "Choose Live Arts MD source workbook"
    action = live["actionable_blockers"][0]["primary_action"]
    assert action["action_kind"] == "replace_source_workbook_reference"
    assert action["hidden_request_payload"]["intended_use"] == "replace_source_workbook_reference"
    assert action["hidden_request_payload"]["expected_workbook_display_name"] == "Invoice Live Arts MD! Running.xlsx"


def test_live_arts_md_source_workbook_selection_surface_exists(tmp_path):
    payload = bundle.build_payload(generated_at=FIXED_NOW, workbook_registry_payload={})
    action_payload = dict(
        payload["live_arts_md_bundle"]["actionable_blockers"][0]["primary_action"]["hidden_request_payload"]
    )
    result = action_handler.process_action_request(
        {
            "request_id": "live_arts_md_choose_source_workbook",
            "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
            "client_ref": "live_arts_md",
            "workflow_ref": "live_arts_md_invoice_workflow",
            "action_kind": "replace_source_workbook_reference",
            "hidden_request_payload": action_payload,
        },
        generated_at=FIXED_NOW,
        db_path=tmp_path / "live_arts_md_source_surface.sqlite",
        export_root=tmp_path / "live_arts_md_source_surface_read_models",
        bridge_export_root=None,
        event_db_path=tmp_path / "live_arts_md_source_surface_events.sqlite",
        event_export_root=tmp_path / "live_arts_md_source_surface_events",
    )

    surface = result["local_surface_request"]
    assert surface["surface_type"] == "SHOW_SOURCE_WORKBOOK_SELECTION_PANEL"
    assert surface["client_ref"] == "live_arts_md"
    assert surface["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert surface["operator_copy"] == "Choose the Live Arts MD source workbook. No workbook cells will be read."
    assert surface["no_workbook_body_read"] is True
    assert surface["no_cell_read"] is True


def test_confirmed_source_workbook_does_not_read_cells_and_enables_selection():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        generated_at=FIXED_NOW,
    )

    assert live["source_workbook"]["status"] == "CONFIRMED"
    assert live["source_workbook"]["approved_for_cell_read"] is False
    assert live["source_workbook"]["no_cell_read"] is True
    assert live["invoice_selection"]["primary_action"]["enabled"] is True
    assert live["invoice_selection"]["status"] == "NEEDS_SELECTION"


def test_live_arts_md_workbook_confirmation_writes_receipt_and_refreshes_bundle(tmp_path):
    db_path = tmp_path / "invoice_review_state.sqlite"
    export_root = tmp_path / "generated" / "read_models"
    bridge_root = tmp_path / "bridge" / "generated" / "read_models"

    result = state_machine.process_source_workbook_selection_result(
        {
            "request_id": "live_arts_md_source_workbook_result",
            "request_type": "LOCAL_SURFACE_RESULT",
            "kind": "LOCAL_SURFACE_RESULT",
            "type": "LOCAL_SURFACE_RESULT",
            "intended_use": "confirm_source_workbook_reference",
            "client_ref": "live_arts_md",
            "workflow_ref": "live_arts_md_invoice_workflow",
            "source_action_ref": "replace_source_workbook_reference",
            "operator_provided": True,
            "operator_confirmed": True,
            "artifact_ref": "workbook_ref:client_invoice:live_arts_md:operator_selected",
            "workbook_display_name": "Invoice Live Arts MD! Running.xlsx",
            "workbook_extension": ".xlsx",
            "file_size_bytes": 12345,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "no_external_action": True,
            "physical_deletion_allowed": False,
        },
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )
    receipt = state_machine.read_receipt(db_path, result.action_receipt["receipt_id"])
    source_payload = json.loads((export_root / bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_payload = json.loads((bridge_root / bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    live = source_payload["live_arts_md_bundle"]

    assert result.status == "COMPLETED"
    assert receipt["receipt_name"] == "source_workbook_reference_confirmed_receipt"
    assert receipt["client_ref"] == "live_arts_md"
    assert result.state_snapshot["source_workbook_status"] == "CONFIRMED"
    assert result.state_snapshot["invoice_record_selection_status"] == "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
    assert live["source_workbook"]["status"] == "CONFIRMED"
    assert live["invoice_selection"]["status"] == "NEEDS_SELECTION"
    assert live["invoice_artifact"]["status"] == "ARTIFACT_REQUIRED"
    assert live["invoice_artifact"]["attachment_ready"] is False
    assert live["approval_footer"]["approval_ready"] is False
    assert live["supplier_portal_invoice_submission"]["required"] is False
    assert source_payload == bridge_payload


def test_invoice_page_selection_follows_existing_pattern():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        generated_at=FIXED_NOW,
    )
    action = live["invoice_selection"]["primary_action"]

    assert action["action_kind"] == "start_invoice_record_selection"
    assert action["hidden_request_payload"]["intended_use"] == "select_invoice_record_or_period"
    assert action["hidden_request_payload"]["no_workbook_body_read"] is True
    assert action["hidden_request_payload"]["no_cell_read"] is True


def test_manual_artifact_link_validates_metadata_only(tmp_path):
    artifact = tmp_path / "live_arts_md_invoice.pdf"
    artifact.write_bytes(b"%PDF-1.4 synthetic invoice candidate\n")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path=artifact.as_posix(),
        present_receipts=("invoice_record_selection_operator_confirmed_receipt",),
        generated_at=FIXED_NOW,
    )

    assert live["invoice_artifact"]["status"] == "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE"
    assert live["invoice_artifact"]["metadata"]["metadata_only"] is True
    assert live["invoice_artifact"]["metadata"]["body_read"] is False
    assert live["invoice_artifact"]["hash"].startswith("sha256:")


def test_artifact_candidate_does_not_imply_attachment_readiness(tmp_path):
    artifact = tmp_path / "live_arts_md_invoice.pdf"
    artifact.write_bytes(b"%PDF-1.4 synthetic invoice candidate\n")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path=artifact.as_posix(),
        present_receipts=("invoice_record_selection_operator_confirmed_receipt",),
        generated_at=FIXED_NOW,
    )

    assert live["invoice_artifact"]["candidate_only"] is True
    assert live["invoice_artifact"]["attachment_ready"] is False
    assert live["approval_footer"]["approval_ready"] is False


def test_clara_draft_is_draft_only_and_uses_clara_voice():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert live["clara_email_draft"]["selected_voice"] == "CLARA"
    assert live["clara_email_draft"]["draft_only"] is True
    assert live["clara_email_draft"]["sent"] is False
    assert "Attached is" not in live["clara_email_draft"]["body"]


def test_missing_recipient_info_blocks_send_readiness():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        present_receipts=("invoice_record_selection_operator_confirmed_receipt",),
        generated_at=FIXED_NOW,
    )

    assert live["recipient_state"]["status"] == "RECIPIENT_INFO_REQUIRED"
    assert live["recipient_state"]["recipient_email_invented"] is False
    assert live["send_readiness"]["manual_send_package_status"] == "BLOCKED_PREREQUISITES"


def test_approval_send_remains_disabled_until_receipts_exist(tmp_path):
    artifact = tmp_path / "live_arts_md_invoice.pdf"
    artifact.write_bytes(b"%PDF-1.4 synthetic invoice candidate\n")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path=artifact.as_posix(),
        present_receipts=(
            "invoice_record_selection_operator_confirmed_receipt",
            "operator_provided_invoice_artifact_linked_candidate_receipt",
        ),
        generated_at=FIXED_NOW,
    )

    assert live["approval_footer"]["approval_ready"] is False
    assert "Confirm the Live Arts MD recipient/contact." in live["approval_footer"]["approval_disabled_reasons"]
    assert live["send_readiness"]["sent_receipt_confirmed"] is False


def test_payment_watch_remains_readiness_only_until_send_payment_receipts():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert live["payment_watch"]["payment_watch_status"] == "READINESS_ONLY"
    assert live["payment_watch"]["bank_ledger_match_required"] is True
    assert live["payment_watch"]["ledger_posting_allowed"] is False


def test_capital_hilton_can_reuse_simple_rails_plus_supplier_portal():
    recipes = framework.recipes_by_client_ref()

    for rail_ref in (
        framework.SOURCE_WORKBOOK_RAIL,
        framework.INVOICE_PERIOD_SHEET_RAIL,
        framework.EXCEL_INVOICE_GENERATION_RAIL,
        framework.CLARA_EMAIL_DRAFT_RAIL,
        framework.GUARDIAN_APPROVAL_RAIL,
        framework.EXTERNAL_SEND_RAIL,
        framework.PAYMENT_WATCH_RAIL,
    ):
        assert framework.recipe_selects_rail(recipes["capital_hilton"], rail_ref)
        assert framework.recipe_selects_rail(recipes["live_arts_md"], rail_ref)
    assert framework.recipe_selects_rail(recipes["capital_hilton"], framework.SUPPLIER_PORTAL_RAIL)
    assert not framework.recipe_selects_rail(recipes["live_arts_md"], framework.SUPPLIER_PORTAL_RAIL)


def test_no_send_email_coupa_browser_ledger_or_workbook_read_action_enabled():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert all(value is False for value in live["authority_boundary"].values())
    assert live["machine_proof"]["no_action_authority"] is True


def test_export_writes_json_operator_and_bridge(tmp_path):
    export_root = tmp_path / "read_models"
    bridge_root = tmp_path / "bridge"
    assert export_main(
        [
            "--export-root",
            str(export_root),
            "--bridge-export-root",
            str(bridge_root),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0
    source = export_root / bundle.JSON_EXPORT_NAME
    bridge = bridge_root / bundle.JSON_EXPORT_NAME
    operator = export_root / bundle.OPERATOR_EXPORT_NAME

    assert source.is_file()
    assert bridge.is_file()
    assert operator.is_file()
    assert json.loads(source.read_text(encoding="utf-8"))["live_arts_md_bundle"]["client_ref"] == "live_arts_md"
    assert source.read_bytes() == bridge.read_bytes()
