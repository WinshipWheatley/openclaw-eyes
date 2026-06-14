import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import invoice_review_bundle as bundle
from scripts.export_invoice_review_bundle import main as export_main


FIXED_NOW = "2026-05-27T12:00:00+00:00"


def _capital(receipts=()):
    return bundle.build_capital_hilton_bundle(present_receipts=receipts, generated_at=FIXED_NOW)


def test_capital_hilton_bundle_includes_excel_invoice_artifact_slot():
    payload = _capital()

    artifact = payload["excel_invoice_artifact"]
    assert artifact["artifact_ref"].startswith("local_artifact_ref:")
    assert artifact["display_name"] == "Capital Hilton Excel invoice candidate"
    assert "preview_available" in artifact
    assert artifact["proof_status"] == "GENERATED_INVOICE_ARTIFACT_CANDIDATE"
    assert artifact["attachment_ready"] is False


def test_capital_hilton_bundle_includes_clara_draft_slot():
    payload = _capital()
    draft = payload["clara_email_draft"]

    assert draft["selected_voice"] == "CLARA"
    assert draft["draft_only"] is True
    assert draft["sent"] is False
    assert "Hi Annette" in draft["body"]


def test_capital_hilton_bundle_includes_coupa_proof_requirement():
    proof = _capital()["coupa_invoice_proof"]

    assert proof["required"] is True
    assert proof["rail_ref"] == "supplier_portal_rail"
    assert proof["supplier_portal_provider"] == "COUPA"
    assert proof["provider_display_name"] == "Coupa supplier portal"
    assert proof["portal_submission_action_allowed"] is False
    assert proof["status"] == "MISSING"
    assert proof["proof_ref"] is None


def test_bundle_shows_coupa_proof_missing_when_absent():
    payload = _capital()

    assert "Coupa submission proof is still required." in payload["blockers"]
    assert payload["helm_card"]["primary_warning"] == (
        "OpenClaw needs the current invoice page/period before it can attach the Excel invoice."
    )


def test_candidate_contacts_are_unconfirmed_without_receipt():
    payload = _capital()
    recipients = payload["recipients"]

    names = {item["display_name"] for item in recipients["to_candidates"] + recipients["cc_candidates"]}
    roles = {item["role"] for item in recipients["to_candidates"] + recipients["cc_candidates"]}
    assert names == {"Annette", "Chyna", "Will"}
    assert {"finance_primary", "finance_secondary", "relationship_contact"} <= roles
    assert recipients["confirmation_status"] == "CANDIDATE_UNCONFIRMED"
    assert all(
        item["confirmation_status"] == "CANDIDATE_UNCONFIRMED"
        for item in recipients["to_candidates"] + recipients["cc_candidates"]
    )


def test_guardian_approval_request_exposes_button_labels_not_typed_code():
    payload = _capital()
    request = payload["guardian_approval_request"]

    assert request["approval_required"] is True
    assert request["status"] == "BLOCKED_PREREQUISITES_MISSING"
    assert request["send_allowed"] is False
    assert tuple(button["label"] for button in request["buttons"]) == bundle.APPROVAL_BUTTONS
    assert payload["operator_copy"]["button_labels"] == bundle.APPROVAL_BUTTONS
    assert payload["operator_copy"]["approval_question"] == "Review the Capital Hilton invoice package?"


def test_existing_generated_artifact_without_invoice_record_linkage_is_candidate_only():
    payload = _capital()
    artifact = payload["excel_invoice_artifact"]

    assert artifact["preview_available"] is True
    assert artifact["proof_status"] == "GENERATED_INVOICE_ARTIFACT_CANDIDATE"
    assert artifact["linkage_status"] == "NEEDS_INVOICE_SELECTION"
    assert artifact["bridge_relative_ref"] == artifact["preview_ref"]
    assert artifact["pc_bridge_ref"].startswith("/mnt/e/openclaw/generated/invoice_artifacts/")
    assert artifact["mac_visible_ref"].startswith("/Volumes/openclaw_e/generated/invoice_artifacts/")
    assert "generated_invoice_artifact_linkage_receipt" in artifact["missing_linkage_receipts"]
    assert payload["machine_proof"]["existing_artifact_without_invoice_record_linkage_is_candidate_only"] is True


def test_bundle_exposes_preview_section_without_generating_pdf_or_image():
    payload = _capital()
    preview = payload["preview_section"]

    assert preview["preview_kind"] == "EXCEL"
    assert preview["preview_available"] is False
    assert preview["preview_limited"] is True
    assert preview["preview_mac_path"].startswith("/Volumes/openclaw_e/generated/invoice_artifacts/")
    assert preview["preview_status"] == "EXCEL_CANDIDATE_OPEN_FILE_ONLY"
    assert "Candidate only" in preview["candidate_notice"]
    assert preview["generation_performed"] is False
    assert payload["machine_proof"]["preview_section_present"] is True
    assert payload["machine_proof"]["preview_generation_performed"] is False


def test_open_and_reveal_actions_use_mac_visible_paths():
    payload = _capital()
    actions = payload["artifact_inspection_actions"]

    assert actions["open_file_available"] is True
    assert actions["open_file_mac_path"].startswith("/Volumes/openclaw_e/generated/invoice_artifacts/")
    assert actions["reveal_in_finder_available"] is True
    assert actions["reveal_in_finder_mac_path"] == actions["open_file_mac_path"]
    assert actions["pop_out_available"] is True
    assert actions["artifact_remains_candidate"] is True
    assert actions["external_action"] is False
    assert payload["machine_proof"]["artifact_inspection_paths_are_mac_visible"] is True


def test_right_workbook_wrong_page_correction_is_governed_no_external_action():
    payload = _capital()
    actions = {action["label"]: action for action in payload["correction_actions"]}

    action = actions["Right Workbook, Wrong Page"]
    assert action["enabled"] is True
    assert action["requires_followup"] is True
    assert action["action_kind"] == "start_invoice_record_selection"
    assert action["resulting_request_kind"] == "invoice_page_selection_request"
    assert action["no_external_action"] is True
    assert action["mutates_workbook"] is False
    assert action["mutates_production_state"] is False
    assert action["hidden_request_payload"]["request_kind"] == "start_invoice_record_selection"
    assert payload["machine_proof"]["right_workbook_wrong_page_no_external_action"] is True


def test_bundle_blocks_attachment_readiness_when_invoice_sheet_page_period_is_unknown():
    payload = _capital()

    assert payload["invoice_selection"]["workbook_may_contain_multiple_invoice_records"] is True
    assert payload["invoice_selection"]["invoice_record_state"] == "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
    assert payload["invoice_period"]["status"] == "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
    assert payload["excel_invoice_artifact"]["attachment_ready"] is False
    assert "Which invoice page/period should OpenClaw prepare for Capital Hilton?" in payload["blockers"]
    assert "OpenClaw needs the current invoice page/period before it can attach the Excel invoice." in payload["blockers"]


def test_bundle_cannot_ask_for_send_approval_until_artifact_is_linked_to_selected_invoice():
    receipts = {
        "invoice_attachment_proof_receipt",
        "clara_email_draft_receipt",
        "recipient_confirmation_receipt",
    }
    payload = _capital(receipts)

    assert payload["excel_invoice_artifact"]["proof_status"] == "GENERATED_INVOICE_ARTIFACT_CANDIDATE"
    assert payload["excel_invoice_artifact"]["attachment_ready"] is False
    assert payload["guardian_approval_request"]["operator_question"] == "Review the Capital Hilton invoice package?"


def test_approval_footer_is_disabled_with_clear_reasons():
    payload = _capital()
    footer = payload["approval_footer"]

    assert footer["approval_ready"] is False
    assert set(footer["approval_disabled_reasons"]) >= {
        "Coupa proof missing",
        "Invoice record/page not selected",
        "Generated artifact not linked",
        "Recipients unconfirmed",
        "Attachment not ready",
    }
    approve = next(button for button in footer["approval_buttons"] if button["label"] == "APPROVE")
    assert approve["enabled"] is False
    assert "Approval is disabled" in footer["sticky_footer_operator_copy"]
    assert payload["machine_proof"]["approval_footer_ready"] is False


def test_proof_timeline_is_plain_primary_copy_with_hidden_refs_only():
    payload = _capital()
    timeline = payload["review_proof_timeline"]

    labels = [item["label"] for item in timeline]
    assert labels == [
        "Active workbook",
        "Invoice page/period",
        "Generated invoice artifact",
        "Coupa portal proof",
        "Clara draft",
        "Recipients",
        "Guardian approval request",
        "Operator approval",
        "Email send",
        "Payment watch",
        "Ledger/tax evidence",
    ]
    primary_text = json.dumps([item["operator_copy"] for item in timeline]).lower()
    assert "source_request_id" not in primary_text
    assert "sqlite" not in primary_text
    assert "gate 2" not in primary_text
    assert all("hidden_internal_refs" in item for item in timeline)
    assert payload["machine_proof"]["proof_timeline_present"] is True
    assert payload["machine_proof"]["actionable_timeline_present"] is True


def test_every_incomplete_timeline_step_has_action_or_disabled_reason():
    payload = _capital()

    for step in payload["review_proof_timeline"]:
        if step["status"] == "COMPLETE":
            continue
        action = step["primary_action"]
        assert action is not None, step["title"]
        assert action["action_ref"], step["title"]
        assert action["enabled"] or action["disabled_reason"], step["title"]
    assert payload["machine_proof"]["incomplete_timeline_steps_have_actions_or_disabled_reasons"] is True


def test_no_visible_button_lacks_action_ref():
    payload = _capital()
    visible_buttons = [
        *payload["correction_actions"],
        *payload["approval_footer"]["approval_buttons"],
        *payload["guardian_approval_request"]["buttons"],
    ]

    assert all(button["action_ref"] for button in visible_buttons)
    assert payload["machine_proof"]["visible_buttons_have_action_refs"] is True


def test_wrong_workbook_maps_to_replace_source_reference_not_deletion():
    payload = _capital()
    actions = {action["label"]: action for action in payload["correction_actions"]}
    wrong_workbook = actions["Wrong Workbook"]

    assert wrong_workbook["action_kind"] == "replace_source_workbook_reference"
    hidden = wrong_workbook["hidden_request_payload"]
    assert hidden["physical_deletion_allowed"] is False
    assert "delete" not in json.dumps(hidden).lower()
    assert wrong_workbook["no_external_action"] is True


def test_start_coupa_proof_step_is_proof_intake_not_browser_automation():
    payload = _capital()
    coupa_step = next(step for step in payload["review_proof_timeline"] if step["title"] == "Coupa portal proof")
    action = coupa_step["primary_action"]
    hidden = action["hidden_request_payload"]

    assert action["label"] == "Start Coupa proof step"
    assert action["action_kind"] == "request_supplier_portal_submission_proof"
    assert action["intended_use"] == "request_supplier_portal_submission_proof"
    assert hidden["proof_intake_only"] is True
    assert hidden["portal_provider"] == "COUPA"
    assert hidden["provider_display_name"] == "Coupa supplier portal"
    assert hidden["requires_purchase_order"] is True
    assert hidden["canonical_action_kind"] == "request_supplier_portal_submission_proof"
    assert hidden["compatibility_action_kind"] == "request_coupa_submission_proof"
    assert hidden["no_external_action"] is True
    assert hidden["browser_action"] is False
    assert hidden["browser_automation_allowed"] is False
    assert hidden["portal_submission_allowed"] is False
    assert hidden["portal_submission_action_allowed"] is False
    assert hidden["coupa_submit_allowed"] is False
    assert hidden["supplier_portal_submit_allowed"] is False


def test_recipient_review_action_does_not_invent_emails():
    payload = _capital()
    recipients_step = next(step for step in payload["review_proof_timeline"] if step["title"] == "Recipients")
    action = recipients_step["primary_action"]
    hidden = action["hidden_request_payload"]

    assert action["action_kind"] == "review_and_confirm_recipients"
    assert hidden["candidate_contacts"] == ("Annette", "Chyna", "Will")
    assert hidden["email_addresses_known"] is False
    assert hidden["do_not_invent_emails"] is True
    assert "@" not in json.dumps(hidden)


def test_approval_action_is_disabled_until_prerequisites_exist():
    payload = _capital()
    footer_approve = next(button for button in payload["approval_footer"]["approval_buttons"] if button["label"] == "APPROVE")
    guardian_step = next(step for step in payload["review_proof_timeline"] if step["title"] == "Guardian approval request")

    assert footer_approve["enabled"] is False
    assert footer_approve["disabled_reason"]
    assert guardian_step["status"] == "BLOCKED"
    assert guardian_step["primary_action"]["action_kind"] == "show_approval_prerequisites"
    assert guardian_step["primary_action"]["no_external_action"] is True


def test_email_send_action_is_disabled_until_approval_and_attachment_prerequisites_exist():
    payload = _capital()
    email_step = next(step for step in payload["review_proof_timeline"] if step["title"] == "Email send")
    action = email_step["primary_action"]

    assert action["action_kind"] == "prepare_send_approval_request"
    assert action["enabled"] is False
    assert "approval" in action["disabled_reason"].lower()
    assert action["hidden_request_payload"]["email_send_allowed"] is False


def test_action_payloads_are_hidden_metadata_not_primary_operator_copy():
    payload = _capital()
    primary_text = json.dumps(payload["operator_copy"]).lower()
    timeline_text = json.dumps(
        [
            step["operator_summary"]
            for step in payload["review_proof_timeline"]
        ]
    ).lower()

    assert "hidden_request_payload" not in primary_text
    assert "action_kind" not in primary_text
    assert "idempotency_key" not in primary_text
    assert "hidden_request_payload" not in timeline_text
    assert "action_kind" not in timeline_text


def test_linkage_receipts_can_confirm_generated_artifact_without_enabling_send():
    receipts = {
        "active_workbook_confirmed_receipt",
        "invoice_record_selected_receipt",
        "invoice_period_confirmed_receipt",
        "generated_invoice_artifact_linkage_receipt",
        "invoice_attachment_proof_receipt",
        "clara_email_draft_receipt",
        "recipient_confirmation_receipt",
    }
    payload = _capital(receipts)

    assert payload["excel_invoice_artifact"]["proof_status"] == "GENERATED_INVOICE_ARTIFACT_CONFIRMED"
    assert payload["excel_invoice_artifact"]["attachment_ready"] is True
    assert payload["guardian_approval_request"]["operator_question"] == (
        "Approve sending this Excel invoice email to Annette with Chyna and Will copied?"
    )
    assert payload["guardian_approval_request"]["send_allowed"] is False
    assert payload["authority_boundary"]["email_send_allowed"] is False


def test_approval_button_metadata_exists_internally_but_is_hidden_from_operator_copy():
    payload = _capital()
    internal = payload["hidden_backend_proof"]
    operator_text = json.dumps(payload["operator_copy"]).lower()

    assert internal["approval_ref"].startswith("guardian_invoice_review_approval:")
    assert len(internal["button_refs"]) == len(bundle.APPROVAL_BUTTONS)
    assert len(internal["internal_action_refs"]) == len(bundle.APPROVAL_BUTTONS)
    assert "button_ref" not in operator_text
    assert "internal_action_ref" not in operator_text
    assert "approval_ref" not in operator_text


def test_draft_does_not_imply_sent():
    payload = _capital()

    assert payload["clara_email_draft"]["draft_only"] is True
    assert payload["clara_email_draft"]["sent"] is False
    assert payload["machine_proof"]["draft_does_not_imply_sent"] is True


def test_approval_request_does_not_imply_send():
    payload = _capital({"guardian_approval_receipt", "operator_approval_receipt"})

    assert payload["guardian_approval_request"]["approval_required"] is True
    assert payload["guardian_approval_request"]["send_allowed"] is False
    assert payload["machine_proof"]["approval_does_not_imply_send"] is True


def test_guardian_output_validation_does_not_imply_guardian_approval_request():
    payload = _capital()
    status = payload["semantic_status"]

    assert status["guardian_output_validation_status"] == "PASSED_FOR_DRAFT_DISPLAY_ONLY"
    assert status["guardian_approval_request_status"] == "BLOCKED_PREREQUISITES_MISSING"
    assert payload["proof_shelf_copy"]["guardian_output_validation"] == (
        "Safety check passed for showing this draft/status only."
    )
    assert payload["machine_proof"]["guardian_output_validation_does_not_imply_approval_request"] is True


def test_guardian_approval_request_does_not_imply_operator_approval():
    receipts = {
        "active_workbook_confirmed_receipt",
        "invoice_record_selected_receipt",
        "invoice_period_confirmed_receipt",
        "generated_invoice_artifact_linkage_receipt",
        "invoice_attachment_proof_receipt",
        "clara_email_draft_receipt",
        "recipient_confirmation_receipt",
    }
    payload = _capital(receipts)

    assert payload["semantic_status"]["guardian_approval_request_status"] == "READY_TO_REQUEST_OPERATOR_APPROVAL"
    assert payload["semantic_status"]["operator_approval_status"] == "NOT_GRANTED"
    assert payload["guardian_approval_request"]["send_allowed"] is False


def test_operator_approval_does_not_imply_execution():
    payload = _capital({"guardian_approval_receipt", "operator_approval_receipt"})
    status = payload["semantic_status"]

    assert status["operator_approval_status"] == "GRANTED_FOR_SPECIFIC_PACKAGE"
    assert status["email_send_execution_status"] == "NOT_SENT"
    assert status["portal_submission_execution_status"] == "NOT_SUBMITTED"


def test_send_is_blocked_unless_approval_and_send_execution_receipts_exist():
    blocked = _capital({"guardian_approval_receipt", "operator_approval_receipt"})
    ready_receipts = {"guardian_approval_receipt", "operator_approval_receipt", "email_send_receipt"}
    after_receipts = _capital(ready_receipts)

    assert "Send is blocked until approval and send execution receipts exist." in blocked["blockers"]
    assert blocked["machine_proof"]["send_blocked_without_required_receipts"] is True
    assert after_receipts["machine_proof"]["send_blocked_without_required_receipts"] is False
    assert after_receipts["authority_boundary"]["email_send_allowed"] is False


def test_capital_hilton_workbook_may_contain_multiple_invoice_records():
    payload = _capital()

    assert payload["invoice_selection"]["workbook_may_contain_multiple_invoice_records"] is True
    assert "INVOICE_RECORD_SELECTED" in bundle.INVOICE_REVIEW_STATES


def test_non_coupa_client_recipe_does_not_require_coupa_by_default():
    payload = bundle.build_payload(generated_at=FIXED_NOW)
    non_coupa = payload["non_coupa_recipe_example"]

    assert non_coupa["client_ref"] == "st_annes"
    assert non_coupa["coupa_invoice_proof"]["required"] is False
    assert payload["machine_proof"]["non_coupa_client_does_not_require_coupa"] is True


def test_capital_hilton_review_bundle_puts_coupa_portal_proof_before_email_send_success():
    payload = _capital({"email_send_receipt"})
    status = payload["semantic_status"]

    assert status["primary_invoice_trigger"] == "COUPA_SUPPLIER_PORTAL_INVOICE"
    assert status["coupa_portal_rail_status"] == "PRIMARY_PAYMENT_TRIGGER_BLOCKED_PROOF_MISSING"
    assert status["coupa_submission_proof_status"] == "MISSING"
    assert "Coupa submission proof is still required." in payload["blockers"]


def test_no_email_coupa_browser_send_action_is_enabled():
    payload = bundle.build_payload(generated_at=FIXED_NOW)

    assert payload["machine_proof"]["all_action_authority_false"] is True
    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["machine_proof"]["send_action_enabled"] is False
    assert payload["machine_proof"]["coupa_action_enabled"] is False
    assert payload["machine_proof"]["pdf_excel_generation_performed"] is False


def test_operator_copy_contains_no_backend_jargon():
    payload = _capital()
    operator_text = json.dumps(payload["operator_copy"]).lower()

    for term in bundle.OPERATOR_JARGON_BLOCKLIST:
        assert term not in operator_text
    assert payload["machine_proof"]["operator_copy_jargon_free"] is True


def test_export_writes_parseable_json_and_operator_summary(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / bundle.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == bundle.READ_MODEL_ID
    assert summary["button_labels"] == list(bundle.APPROVAL_BUTTONS)
    assert payload["capital_hilton_bundle"]["guardian_approval_request"]["approval_required"] is True
    assert "Review the Capital Hilton invoice package." in operator
    assert "Nothing has been sent." in operator
    assert "SQLite" not in operator
    assert "Gate 2" not in operator


def test_export_contains_no_secret_or_live_action_path(tmp_path):
    payload = bundle.build_payload(generated_at=FIXED_NOW)
    bundle.write_exports(payload, tmp_path)
    combined = (tmp_path / bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / bundle.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert "api_key" not in lowered
    assert "password" not in lowered
    assert "secret" not in lowered
    assert "sent=true" not in lowered
    assert "send_allowed=true" not in lowered
