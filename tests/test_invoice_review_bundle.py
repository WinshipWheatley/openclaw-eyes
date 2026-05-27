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
    assert "generated_invoice_artifact_linkage_receipt" in artifact["missing_linkage_receipts"]
    assert payload["machine_proof"]["existing_artifact_without_invoice_record_linkage_is_candidate_only"] is True


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
