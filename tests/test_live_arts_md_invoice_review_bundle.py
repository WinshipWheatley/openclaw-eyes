import json
from pathlib import Path

import client_invoice_workflow_framework as framework
import invoice_review_action_request_handler as action_handler
import invoice_review_state_machine as state_machine
import live_arts_md_invoice_review_bundle as bundle
import live_arts_md_workbook_handoff
from scripts.export_live_arts_md_invoice_review_bundle import main as export_main


FIXED_NOW = "2026-05-28T15:00:00+00:00"
MAC_ARTIFACT_ROOT = "/Volumes/openclaw_e/artifacts/invoice_workbooks"
BRIDGE_ARTIFACT_ROOT = "/mnt/e/openclaw/artifacts/invoice_workbooks"
EXPECTED_OUTPUT_FILENAME = "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"
EXPECTED_OUTPUT_PDF_MAC_PATH = (
    f"{MAC_ARTIFACT_ROOT}/live_arts_md/2026-1001/{EXPECTED_OUTPUT_FILENAME}"
)
EXPECTED_OUTPUT_BRIDGE_PATH = (
    f"{BRIDGE_ARTIFACT_ROOT}/live_arts_md/2026-1001/{EXPECTED_OUTPUT_FILENAME}"
)


def _artifact_relative_path(path: str, root: str) -> str:
    assert path.startswith(f"{root}/")
    return path[len(root):]


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


def _confirmed_workbook_payload_with_mac_path():
    payload = _confirmed_workbook_payload()
    payload["registry"]["client_records"][0]["workbook_path_ref"] = (
        live_arts_md_workbook_handoff.SOURCE_WORKBOOK_MAC_PATH
    )
    payload["registry"]["client_records"][0]["source_workbook_mac_path"] = (
        live_arts_md_workbook_handoff.SOURCE_WORKBOOK_MAC_PATH
    )
    return payload


def _selected_live_arts_candidate(invoice_id: str = "2026-1001"):
    candidates = live_arts_md_workbook_handoff.invoice_candidates()
    return dict(next(candidate for candidate in candidates if candidate["invoice_id"] == invoice_id))


def _selected_2026_1001_receipt():
    return {
        "receipt_event": "live_arts_md_invoice_candidate_selected_receipt",
        "receipt_id": "live_arts_md_invoice_candidate_selected:test",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "sheet_label": "June 2026 Speaker Rental",
        "validation_errors": [],
    }


def _manual_send_payload(**overrides):
    payload = {
        "execution_context": {
            "execution_venue": "MAC_LOCAL",
            "execution_actor": "OPERATOR",
            "assistant_actor": "CODEX_DESKTOP_SPARK",
            "openclaw_executed": False,
            "manual_execution": True,
            "send_method": "manual_gmail",
            "artifact_exported_on": "MAC_EXCEL",
            "proof_required": True,
        },
        "sent_timestamp": "2026-05-28T14:32:00-04:00",
        "to": ("Dane",),
        "cc": ("Draper", "Earnie", "Winship"),
        "subject": "Live Arts MD invoice",
        "attachment_filename": "Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf",
        "invoice_id": "2026-1001",
        "amount": 900,
        "work_or_period": "June 2026 Speaker Rental",
        "artifact_path": "/Users/hwinshipwheatley/Desktop/Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf",
        "manual_send_receipt_available": True,
        "screenshot_ref": "live_arts_md_manual_send_screenshot",
        "proof_refs": ("manual_send_receipt",),
    }
    payload.update(overrides)
    return payload


def test_live_arts_md_recipe_does_not_require_coupa_or_po():
    recipe = framework.recipes_by_client_ref()["live_arts_md"]

    assert not framework.recipe_selects_rail(recipe, framework.SUPPLIER_PORTAL_RAIL)
    assert not framework.recipe_selects_rail(recipe, framework.PURCHASE_ORDER_RAIL)
    assert recipe["client_specific_portal_requirements"]["supplier_portal_required"] is False
    assert recipe["client_specific_portal_requirements"]["purchase_order_required"] is False


def test_supplier_portal_not_required_is_not_an_action_blocker():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selection_receipt_payload=_selected_2026_1001_receipt(),
        generated_at=FIXED_NOW,
    )

    assert live["supplier_portal_invoice_submission"]["required"] is False
    assert not any("Supplier portal proof: Not required" in blocker for blocker in live["blockers"])


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
        consume_existing_selection_receipt=False,
    )

    assert live["source_workbook"]["status"] == "CONFIRMED"
    assert live["source_workbook"]["approved_for_cell_read"] is False
    assert live["source_workbook"]["no_cell_read"] is True
    assert live["invoice_selection"]["primary_action"]["enabled"] is True
    assert live["invoice_selection"]["status"] == "NEEDS_CANDIDATE_SELECTION"
    assert live["next_safe_move"] == "Invoice candidate selection has not been confirmed."


def test_confirmed_2026_1001_selection_receipt_promotes_current_bundle_state():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selection_receipt_payload=_selected_2026_1001_receipt(),
        generated_at=FIXED_NOW,
    )

    assert live["invoice_selection"]["status"] == "OPERATOR_CONFIRMED"
    assert live["invoice_selection"]["selected_invoice_ids"] == ("2026-1001",)
    assert live["invoice_selection"]["selected_invoice_summary"] == "2026-1001 — June 2026 Speaker Rental — $900"
    assert live["candidate_selection_rail"]["candidate_selection_status"] == "OPERATOR_CONFIRMED"
    assert live["candidate_selection_rail"]["presentation_hints"]["candidate_list_collapsed"] is True
    assert live["invoice_candidate_register"]["candidate_list_status"] == "COLLAPSED_AFTER_CONFIRMED_SELECTION"
    assert [item["invoice_id"] for item in live["invoice_candidate_register"]["invoice_candidates"]] == ["2026-1001"]
    assert live["invoice_candidate_register"]["urgent_actions"] == ()
    assert live["invoice_selection"]["primary_action"]["enabled"] is False


def test_confirmed_selection_enables_scoped_prepare_pdf_primary_action():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selection_receipt_payload=_selected_2026_1001_receipt(),
        generated_at=FIXED_NOW,
    )
    action = live["actionable_blockers"][0]["primary_action"]
    payload = action["hidden_request_payload"]

    assert action["label"] == "Prepare invoice PDF"
    assert action["enabled"] is True
    assert payload["action_kind"] == "prepare_selected_invoice_pdf_artifact"
    assert payload["client_ref"] == "live_arts_md"
    assert payload["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert payload["invoice_id"] == "2026-1001"
    assert payload["selected_sheet_label"] == "June 2026 Speaker Rental"
    assert payload["selected_page_label"] == "page 1"
    assert payload["selected_print_areas"] == (
        "June 2026 Speaker Rental!G2:G5",
        "June 2026 Speaker Rental!F40:G43",
        "June 2026 Speaker Rental!B49:G53",
    )
    assert payload["source_workbook_mac_path"] == live_arts_md_workbook_handoff.SOURCE_WORKBOOK_MAC_PATH
    assert payload["output_filename"] == "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"
    assert payload["execution_venue"] == "MAC_LOCAL"
    assert payload["required_capability"] == "MAC_EXCEL_PDF_EXPORT"
    assert payload["result_intended_use"] == "selected_invoice_pdf_export_completed_candidate"
    assert payload["no_physical_printing"] is True
    assert payload["no_email_send"] is True
    assert payload["no_gmail"] is True
    assert payload["no_browser"] is True
    assert payload["no_ledger_post"] is True
    assert payload["no_coupa"] is True
    assert payload["no_source_workbook_mutation"] is True
    assert payload["no_workbook_cell_read"] is True


def test_missing_receipt_keeps_clear_candidate_selection_blocker():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        consume_existing_selection_receipt=False,
        generated_at=FIXED_NOW,
    )

    assert live["invoice_selection"]["status"] == "NEEDS_CANDIDATE_SELECTION"
    assert live["blockers"][0] == "Invoice candidate selection has not been confirmed."
    assert live["next_safe_move"] == "Invoice candidate selection has not been confirmed."
    assert live["invoice_selection"]["primary_action"]["hidden_request_payload"]["intended_use"] == (
        "select_live_arts_md_invoice_candidate"
    )


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
    assert live["invoice_selection"]["status"] == "OPERATOR_CONFIRMED"
    assert live["invoice_selection"]["selected_invoice_ids"] == ["2026-1001"]
    assert live["invoice_selection"]["selected_invoice_summary"] == "2026-1001 — June 2026 Speaker Rental — $900"
    assert live["invoice_artifact"]["status"] == "ARTIFACT_REQUIRED"
    assert live["invoice_artifact"]["attachment_ready"] is False
    assert live["approval_footer"]["approval_ready"] is False
    assert live["supplier_portal_invoice_submission"]["required"] is False
    assert source_payload == bridge_payload


def test_invoice_candidate_selection_replaces_page_selection_after_handoff():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        generated_at=FIXED_NOW,
        consume_existing_selection_receipt=False,
    )
    action = live["invoice_selection"]["primary_action"]

    assert action["action_kind"] == "select_invoice_candidate"
    assert action["hidden_request_payload"]["intended_use"] == "select_live_arts_md_invoice_candidate"
    assert action["hidden_request_payload"]["no_workbook_body_read"] is True
    assert action["hidden_request_payload"]["no_cell_read"] is True
    assert {item["invoice_id"] for item in live["invoice_candidate_register"]["invoice_candidates"]} == {
        "2026-1001",
        "2026-1002",
        "2026-1003",
    }


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


def test_known_existing_pdfs_are_not_trusted_as_selected_invoice_artifacts():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selection_receipt_payload=_selected_2026_1001_receipt(),
        generated_at=FIXED_NOW,
    )
    guardrails = live["invoice_artifact"]["known_artifact_guardrails"]

    assert guardrails["desktop_pdf"]["path"].endswith(
        "Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf"
    )
    assert guardrails["desktop_pdf"]["known_page_count"] == 7
    assert guardrails["desktop_pdf"]["trusted_as_selected_invoice_artifact"] is False
    assert guardrails["bridge_pdf_placeholder"]["expected_placeholder_size_bytes"] == 14
    assert guardrails["bridge_pdf_placeholder"]["trusted_as_selected_invoice_artifact"] is False
    assert guardrails["bridge_pdf_placeholder"]["status"] in {
        "INVALID_PLACEHOLDER",
        "INVALID_UNTRUSTED_EXISTING_BRIDGE_ARTIFACT",
    }
    assert live["invoice_artifact"]["attachment_ready"] is False
    assert live["clara_email_draft"]["attachment_ready"] is False
    assert live["approval_footer"]["approval_ready"] is False


def test_clara_draft_is_draft_only_and_uses_clara_voice():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert live["clara_email_draft"]["selected_voice"] == "CLARA"
    assert live["clara_email_draft"]["external_identity"] == "CLARA_REID"
    assert live["clara_email_draft"]["draft_only"] is True
    assert live["clara_email_draft"]["sent"] is False
    assert live["clara_email_draft"]["send_allowed"] is False
    assert "Clara Reid" in live["clara_email_draft"]["body"]
    assert "Attached is" not in live["clara_email_draft"]["body"]


def test_live_arts_md_bundle_includes_clara_comms_rail():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)
    comms = live["client_comms_thread"]

    assert comms["comms_thread_status"] == "DRAFT_READY"
    assert comms["external_identity"] == "CLARA_REID"
    assert comms["selected_voice"] == "CLARA"
    assert comms["channel"] == "email"
    assert comms["draft_only"] is True
    assert comms["sent"] is False
    assert comms["first_contact_intro_policy_ref"] == "generated/read_models/client_comms_thread_rail.json#first_contact_intro_policy"
    assert live["machine_proof"]["client_comms_thread_rail_consumed"] is True


def test_first_contact_intro_required_for_first_live_arts_invoice_email():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert live["client_comms_thread"]["first_contact_intro_required"] is True
    assert live["client_comms_thread"]["first_contact_intro_policy"]["intro_required"] is True
    assert "I'm Clara Reid" in live["clara_email_draft"]["body"]
    assert "invoice package organized" in live["clara_email_draft"]["body"]


def test_missing_recipient_info_blocks_send_readiness():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        present_receipts=("invoice_record_selection_operator_confirmed_receipt",),
        generated_at=FIXED_NOW,
    )

    assert live["recipient_state"]["status"] == "RECIPIENT_INFO_REQUIRED"
    assert live["recipient_state"]["recipient_email_invented"] is False
    assert live["recipient_state"]["primary_action"]["hidden_request_payload"]["intended_use"] == "review_or_provide_recipient"
    assert live["send_readiness"]["manual_send_package_status"] == "BLOCKED_PREREQUISITES"


def test_operator_handoff_adds_invoice_choices_without_workbook_parse():
    live = bundle.build_live_arts_md_bundle(
        generated_at=FIXED_NOW,
        consume_existing_selection_receipt=False,
    )
    register = live["invoice_candidate_register"]

    assert live["operator_workbook_handoff"]["operator_provided"] is True
    assert live["operator_workbook_handoff"]["workbook_body_read"] is False
    assert live["operator_workbook_handoff"]["cell_read"] is False
    assert live["next_safe_move"] == "Invoice candidate selection has not been confirmed."
    assert register["primary_next_action"] == "Choose which Live Arts MD invoice to prepare."
    labels = {item["sheet_label"] for item in register["invoice_candidates"]}
    assert labels == {"June 2026 Speaker Rental", "June 2026 AV Tech", "July 2026"}


def test_live_arts_invoice_candidate_choices_show_today_urgent_paths():
    live = bundle.build_live_arts_md_bundle(
        generated_at=FIXED_NOW,
        consume_existing_selection_receipt=False,
    )
    actions = {item["label"]: item for item in live["invoice_candidate_register"]["urgent_actions"]}

    assert "Select June 2026 Speaker Rental" in actions
    assert "Select June 2026 AV Tech" in actions
    assert "Review July 2026 later" in actions
    assert actions["Select June 2026 Speaker Rental"]["hidden_request_payload"]["invoice_id"] == "2026-1001"
    assert actions["Select June 2026 AV Tech"]["hidden_request_payload"]["invoice_id"] == "2026-1002"
    assert actions["Review July 2026 later"]["enabled"] is False


def test_clara_draft_does_not_imply_attachment_readiness():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert live["clara_email_draft"]["draft_only"] is True
    assert live["invoice_artifact"]["attachment_ready"] is False
    assert live["clara_email_draft"]["attachment_claim"] == "attachment not ready yet"
    assert live["clara_email_draft"]["draft_status"] in {
        "DRAFT_PREVIEW_NOT_SEND_READY",
        "DRAFT_BLOCKED_PENDING_PREREQUISITES",
    }


def test_guardian_approval_and_send_execution_receipts_are_required():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert live["client_comms_thread"]["guardian_approval_required"] is True
    assert live["client_comms_thread"]["send_execution_receipt_required"] is True
    assert live["send_readiness"]["guardian_approval_required"] is True
    assert live["send_readiness"]["operator_approval_receipt_required"] is True
    assert live["send_readiness"]["email_send_execution_receipt_required"] is True
    assert "guardian_approval_request_receipt" in live["client_comms_thread"]["required_receipts_before_send"]
    assert "email_send_receipt" in live["client_comms_thread"]["required_receipts_before_send"]


def test_thread_watch_not_active_without_send_receipt():
    live = bundle.build_live_arts_md_bundle(generated_at=FIXED_NOW)

    assert live["client_comms_thread"]["thread_watch_status"] == "BLOCKED_UNTIL_SENT_RECEIPT"
    assert live["client_comms_thread"]["thread_watch_future_gated"] is True
    assert live["client_comms_thread"]["live_gmail_polling_active"] is False


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

    assert live["payment_watch"]["payment_watch_status"] == "READINESS_ONLY_NOT_ACTIVE"
    assert live["payment_watch"]["bank_ledger_read_performed"] is False
    assert live["payment_watch"]["bank_ledger_match_required"] is True
    assert live["payment_watch"]["ledger_posting_allowed"] is False
    assert live["ledger_planning"]["silent_ledger_mutation_allowed"] is False
    assert live["ledger_planning"]["current_ledger_pointer_manifest_required"] is True


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
    assert live["client_comms_thread"]["live_gmail_polling_active"] is False
    assert live["client_comms_thread"]["gmail_draft_created"] is False


def test_manual_send_provenance_is_operator_executed_and_not_openclaw():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=_manual_send_payload(),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    manual_send = live["manual_send_proof"]
    execution = manual_send["execution_context"]

    assert manual_send["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert execution["openclaw_executed"] is False
    assert execution["manual_execution"] is True
    assert execution["execution_actor"] == "OPERATOR"
    assert execution["assistant_actor"] == "CODEX_DESKTOP_SPARK"
    assert live["send_readiness"]["email_send_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert live["client_comms_thread"]["send_execution_status"] == "NOT_SENT"


def test_manual_send_proof_pending_when_required_fields_missing():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=_manual_send_payload(subject=""),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    manual_send = live["manual_send_proof"]
    assert manual_send["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_PENDING
    assert "subject" in manual_send["missing_required_fields"]


def test_manual_send_proof_missing_screenshot_ref_prompts_operator_capture_request():
    screenshotless_payload = _manual_send_payload(screenshot_ref="")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=screenshotless_payload,
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    manual_send = live["manual_send_proof"]
    assert manual_send["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_PENDING
    assert "proof screenshot/ref" in manual_send["missing_required_fields"]
    assert (
        manual_send["proof_capture_request"]
        == "Add sent-email screenshot or sent-mail proof for Live Arts MD invoice 2026-1001."
    )
    assert live["send_readiness"]["email_send_status"] == bundle.MANUAL_SEND_PROOF_STATUS_PENDING
    assert live["payment_watch"]["payment_watch_status"] == bundle.PAYMENT_WATCH_STATUS_READINESS_ONLY


def test_manual_send_proof_confirmed_adds_manual_send_proof_confirmed_receipt(tmp_path):
    screenshot = tmp_path / "live_arts_md_manual_send_screenshot.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=_manual_send_payload(screenshot_ref=screenshot.as_posix()),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    manual_send = live["manual_send_proof"]
    assert manual_send["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert manual_send["proof_capture_type"] == bundle.PROOF_CAPTURE_TYPE_FILE_BACKED
    assert manual_send["proof_strength"] == bundle.PROOF_STRENGTH_FILE_VERIFIED
    assert manual_send["file_backed_proof"] is True
    assert manual_send["screenshot_file_verified"] is True
    assert manual_send["proof_capture_metadata"]["is_path"] is True
    assert manual_send["proof_capture_metadata"]["proof_path_status"] == "metadata_valid"
    assert manual_send["proof_receipts"] == (bundle.MANUAL_SEND_PROOF_CONFIRMED_RECEIPT,)
    assert live["send_readiness"]["email_send_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert live["payment_watch"]["payment_watch_status"] == bundle.PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT
    assert live["payment_watch"]["next_operator_copy"] == (
        "Payment watch is active for Live Arts MD invoice 2026-1001. Ledger posting remains blocked until bank/payment proof exists."
    )
    assert live["payment_watch"]["expected_receivable_status"] == "OPEN"
    assert live["payment_watch"]["expected_client"] == "Live Arts MD"
    assert live["payment_watch"]["invoice_id"] == "2026-1001"
    assert live["payment_watch"]["expected_amount"] == 900
    assert live["payment_watch"]["work_type"] == "Speaker Rental"
    assert live["payment_watch"]["work_or_period"] == "June 2026 Speaker Rental"
    assert live["payment_watch"]["receipt_status"] == "UNPAID"
    assert live["payment_watch"]["ledger_match_status"] == "NOT_MATCHED"
    assert live["payment_watch"]["ledger_handoff_status"] == "PLANNING_ONLY_NO_MUTATION"
    assert live["payment_watch"]["ledger_posting_allowed"] is False
    assert "Capture bank/payment proof for invoice 2026-1001." in live["payment_watch"]["allowed_next_steps"]


def test_manual_send_proof_confirmed_without_file_path_reference_only():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=_manual_send_payload(),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    manual_send = live["manual_send_proof"]
    assert manual_send["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert manual_send["proof_capture_type"] == bundle.PROOF_CAPTURE_TYPE_REFERENCE_ONLY
    assert manual_send["proof_strength"] == bundle.PROOF_STRENGTH_OPERATOR_ATTESTED_REFERENCE
    assert manual_send["file_backed_proof"] is False
    assert manual_send["screenshot_file_verified"] is False
    assert manual_send["proof_capture_metadata"]["is_path"] is False
    assert manual_send["proof_capture_metadata"]["proof_path_status"] == "reference_only"
    assert live["payment_watch"]["payment_watch_status"] == bundle.PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT
    assert live["payment_watch"]["send_proof_strength"] == bundle.PROOF_STRENGTH_OPERATOR_ATTESTED_REFERENCE
    assert live["payment_watch"]["review_status"] == bundle.PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PAYMENT


def test_manual_send_proof_confirmed_without_manual_send_receipt_when_screenshot_provided(tmp_path):
    screenshot = tmp_path / "live_arts_md_manual_send_screenshot.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=_manual_send_payload(screenshot_ref=screenshot.as_posix(), proof_refs=()),
        present_receipts=(),
        generated_at=FIXED_NOW,
    )

    manual_send = live["manual_send_proof"]
    assert manual_send["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert manual_send["proof_capture_type"] == bundle.PROOF_CAPTURE_TYPE_FILE_BACKED
    assert manual_send["proof_strength"] == bundle.PROOF_STRENGTH_FILE_VERIFIED
    assert manual_send["file_backed_proof"] is True
    assert manual_send["screenshot_file_verified"] is True
    assert manual_send["proof_capture_metadata"]["is_path"] is True
    assert manual_send["proof_capture_metadata"]["proof_path_status"] == "metadata_valid"
    assert manual_send["proof_receipts"] == (bundle.MANUAL_SEND_PROOF_CONFIRMED_RECEIPT,)
    assert live["send_readiness"]["email_send_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert live["payment_watch"]["payment_watch_status"] == bundle.PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT


def test_payment_watch_readiness_does_not_advance_without_capture_proof():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=_manual_send_payload(screenshot_ref=""),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    assert live["manual_send_proof"]["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_PENDING
    assert live["payment_watch"]["payment_watch_status"] == bundle.PAYMENT_WATCH_STATUS_READINESS_ONLY


def test_payment_watch_readiness_requires_manual_send_proof_then_ready():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path="/tmp/live_arts_md_invoice.pdf",
        manual_send_proof=_manual_send_payload(),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )
    candidates = {
        item["invoice_id"]: item for item in live["invoice_candidate_register"]["invoice_candidates"]
    }

    assert live["manual_send_proof"]["proof_status"] == bundle.MANUAL_SEND_PROOF_STATUS_CONFIRMED
    assert live["payment_watch"]["payment_watch_status"] == bundle.PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT
    assert live["payment_watch"]["ledger_posting_allowed"] is False
    assert live["payment_watch"]["expected_receivable_status"] == "OPEN"
    assert live["payment_watch"]["review_status"] == bundle.PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PAYMENT
    assert live["payment_watch"]["ledger_match_status"] == "NOT_MATCHED"
    assert live["payment_watch"]["next_operator_copy"] == (
        "Payment watch is active for Live Arts MD invoice 2026-1001. Ledger posting remains blocked until bank/payment proof exists."
    )
    assert candidates["2026-1001"]["receipt_status"] == "UNPAID"


def test_pdf_artifact_metadata_recorded_without_workbook_cell_or_body_reading():
    artifact = Path("/tmp/live_arts_md_invoice.pdf")
    artifact.write_bytes(b"%PDF-1.4 synthetic invoice candidate\n")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        operator_artifact_path=artifact.as_posix(),
        manual_send_proof=_manual_send_payload(artifact_path=artifact.as_posix()),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    assert live["source_workbook"]["approved_for_cell_read"] is False
    assert live["source_workbook"]["no_cell_read"] is True
    assert live["source_workbook"]["no_workbook_body_read"] is True
    assert live["manual_send_proof"]["artifact_path"] == artifact.as_posix()
    assert live["manual_send_proof"]["proof_capture_provided"] is True


def test_pdf_export_rail_appears_after_invoice_selected():
    selected_candidate = _selected_live_arts_candidate("2026-1001")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        generated_at=FIXED_NOW,
    )
    artifact_step = live["proof_timeline"][2]
    pdf_action = artifact_step["primary_action"]
    manual_action = artifact_step["secondary_actions"][0]

    assert artifact_step["title"] == "Invoice artifact"
    assert artifact_step["status"] == "NEEDS_ACTION"
    assert pdf_action["action_kind"] == "prepare_selected_invoice_pdf_artifact"
    assert pdf_action["label"] == "Prepare invoice PDF"
    assert manual_action["label"] == "Attach existing PDF"
    assert live["invoice_artifact"]["pdf_export_package"]["status"] == bundle.PDF_EXPORT_PACKAGE_READY_FOR_MAC


def test_pdf_export_package_scoped_to_selected_candidate():
    selected_candidate = _selected_live_arts_candidate("2026-1001")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        generated_at=FIXED_NOW,
    )
    package = live["invoice_artifact"]["pdf_export_package"]

    assert package["execution_venue"] == bundle.PDF_EXPORT_EXECUTION_VENUE
    assert package["required_capability"] == bundle.PDF_EXPORT_REQUIRED_CAPABILITY
    assert package["invoice_id"] == "2026-1001"
    assert package["selected_sheet_label"] == "June 2026 Speaker Rental"
    assert package["selected_page_label"] == "page 1"
    assert package["selected_print_areas"] == (
        "June 2026 Speaker Rental!G2:G5",
        "June 2026 Speaker Rental!F40:G43",
        "June 2026 Speaker Rental!B49:G53",
    )
    assert package["output_filename"] == EXPECTED_OUTPUT_FILENAME
    assert package["output_pdf_mac_path"] == EXPECTED_OUTPUT_PDF_MAC_PATH
    assert package["output_pdf_mac_path"].startswith(f"{MAC_ARTIFACT_ROOT}/")
    assert package["output_bridge_path"] == EXPECTED_OUTPUT_BRIDGE_PATH
    assert package["output_bridge_path"].startswith(f"{BRIDGE_ARTIFACT_ROOT}/")
    assert _artifact_relative_path(package["output_pdf_mac_path"], MAC_ARTIFACT_ROOT) == _artifact_relative_path(
        package["output_bridge_path"],
        BRIDGE_ARTIFACT_ROOT,
    )
    assert package["source_workbook_path"] == live_arts_md_workbook_handoff.SOURCE_WORKBOOK_MAC_PATH
    assert "scoped_live_arts_md_export/June_2026_Speaker_Rental/2026-1001.pdf" in package["output_path_policy"]
    assert package["workbook_cell_read_required"] is False
    assert package["operator_review_required_after_export"] is True
    placement = live["invoice_artifact"]["artifact_placement_policy"]
    assert placement["canonical_artifact_ref"] == "live_arts_md_invoice_pdf_2026-1001"
    assert placement["output_pdf_mac_path"] == EXPECTED_OUTPUT_PDF_MAC_PATH
    assert placement["output_bridge_path"] == EXPECTED_OUTPUT_BRIDGE_PATH
    assert placement["output_pc_reference_path"] == EXPECTED_OUTPUT_BRIDGE_PATH
    assert placement["local_role"] == "MAC_HELPER_WRITE_DESTINATION"
    assert placement["bridge_role"] == "PC_READ_MODEL_REFERENCE_AND_MIRROR_DESTINATION"


def test_pdf_export_package_restricts_external_actions():
    selected_candidate = _selected_live_arts_candidate("2026-1001")
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        generated_at=FIXED_NOW,
    )
    package = live["invoice_artifact"]["pdf_export_package"]

    assert package["no_physical_printing"] is True
    assert package["no_email_send"] is True
    assert package["no_gmail"] is True
    assert package["no_ledger_post"] is True
    assert package["no_coupa"] is True
    assert package["no_source_workbook_mutation"] is True
    assert package["required_receipts"] == (bundle.PDF_EXPORT_COMPLETION_RECEIPT,)


def test_missing_output_pdf_mac_path_blocks_ready_for_mac(monkeypatch):
    selected_candidate = _selected_live_arts_candidate("2026-1001")
    monkeypatch.setattr(bundle.simple_builder, "_pdf_output_mac_path", lambda **_kwargs: "")

    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        generated_at=FIXED_NOW,
    )
    package = live["invoice_artifact"]["pdf_export_package"]

    assert package["status"] == bundle.PDF_EXPORT_BLOCKED_OUTPUT_PATH_CONTRACT
    assert "output_pdf_mac_path" in package["missing_requirements"]
    assert package["request_payload_ready"] is False
    assert package["status"] != bundle.PDF_EXPORT_PACKAGE_READY_FOR_MAC


def test_pdf_export_does_not_claim_attachment_ready_until_completion_receipt():
    selected_candidate = _selected_live_arts_candidate("2026-1001")
    pending = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        generated_at=FIXED_NOW,
    )
    completed = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        present_receipts=(bundle.PDF_EXPORT_COMPLETION_RECEIPT,),
        generated_at=FIXED_NOW,
    )

    assert pending["invoice_artifact"]["attachment_ready"] is False
    assert completed["invoice_artifact"]["attachment_ready"] is False
    assert completed["invoice_artifact"]["artifact_review_status"] == "OPERATOR_REVIEW_REQUIRED"
    assert completed["proof_timeline"][2]["status"] == "CANDIDATE"


def test_pdf_export_blocked_with_missing_print_scope():
    selected_candidate = _selected_live_arts_candidate("2026-1001")
    selected_candidate["operator_provided_ranges"] = ()
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        generated_at=FIXED_NOW,
    )

    package = live["invoice_artifact"]["pdf_export_package"]
    assert package["status"] == bundle.PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE
    assert package["missing_requirements"] == ("selected_print_areas",)
    assert (
        package["operator_review_prompt"]
        == "Confirm selected print area for invoice 2026-1001."
    )
    assert any(
        blocker == package["operator_review_prompt"]
        for blocker in live["blockers"]
    )


def test_manual_artifact_action_remains_fallback_when_pdf_export_blocked():
    selected_candidate = _selected_live_arts_candidate("2026-1001")
    selected_candidate["operator_provided_ranges"] = ()
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload_with_mac_path(),
        selected_invoice_candidate=selected_candidate,
        generated_at=FIXED_NOW,
    )
    artifact_step = live["proof_timeline"][2]
    pdf_action = artifact_step["primary_action"]
    manual_action = artifact_step["secondary_actions"][0]

    assert artifact_step["title"] == "Invoice artifact"
    assert pdf_action["label"] == "Prepare invoice PDF"
    assert pdf_action["enabled"] is False
    assert pdf_action["disabled_reason"] == "Confirm selected print area for invoice 2026-1001."
    assert manual_action["label"] == "Attach existing PDF"
    assert manual_action["enabled"] is True
    assert manual_action["operator_visible_message"] == "Attach existing PDF"


def test_no_gmail_browser_or_send_action_performed():
    live = bundle.build_live_arts_md_bundle(
        workbook_registry_payload=_confirmed_workbook_payload(),
        manual_send_proof=_manual_send_payload(),
        present_receipts=("manual_send_receipt",),
        generated_at=FIXED_NOW,
    )

    boundary = live["authority_boundary"]
    assert boundary["email_send_performed"] is False
    assert boundary["gmail_access_performed"] is False
    assert boundary["browser_automation_performed"] is False
    assert boundary["coupa_access_performed"] is False
    assert boundary["ledger_posting_performed"] is False
    assert live["client_comms_thread"]["gmail_draft_created"] is False
    assert live["client_comms_thread"]["live_gmail_polling_active"] is False
    assert live["send_readiness"]["manual_send_proof"]["manual_send_receipt_available"] is True


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
