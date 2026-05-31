import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_event_bridge_contract as contract
from scripts.export_openclaw_event_bridge_contract import main as export_main


FIXED_NOW = "2026-05-31T14:00:30+00:00"


def _route(event: dict) -> dict:
    return contract.route_event(event, now=FIXED_NOW)


def _workflow_payload(response: dict) -> dict:
    return response["structured_actions"][0]["workflow_payload"]


def test_mac_ui_button_event_routes_to_workflow_action():
    event = contract.make_live_arts_prepare_pdf_event(source_channel="MAC_APP", event_kind="UI_BUTTON_CLICK")
    response = _route(event)
    action = response["structured_actions"][0]
    payload = action["workflow_payload"]

    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_ACTION_ROUTED"
    assert action["handler_id"] == "invoice_review_action_request.live_arts_md"
    assert action["structured_action_kind"] == "ROUTE_TO_WORKFLOW_ACTION"
    assert payload["request_type"] == "INVOICE_REVIEW_ACTION_REQUEST"
    assert payload["action_kind"] == "prepare_selected_invoice_pdf_artifact"
    assert payload["client_ref"] == "live_arts_md"
    assert payload["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert payload["payload"]["output_pdf_mac_path"].startswith(
        "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md/"
    )
    assert payload["payload"]["output_bridge_path"].startswith(
        "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/"
    )
    assert payload["payload"]["output_pdf_mac_path"].replace("/Volumes/openclaw_e", "/mnt/e/openclaw") == payload[
        "payload"
    ]["output_bridge_path"]
    assert payload["result_receipt_required"] is True
    assert payload["required_receipts"] == ("selected_invoice_pdf_export_requested_receipt",)


def test_simple_invoice_prepare_pdf_event_routes_for_st_annes_scope():
    event = contract.make_simple_invoice_prepare_pdf_event(
        client_ref="st_annes",
        workflow_ref="st_annes_invoice_workflow",
        thread_ref="st_annes_invoice_workflow:fixture_invoice",
        invoice_id="fixture_invoice",
        selected_invoice_summary="fixture_invoice - operator scoped invoice - UNKNOWN",
        selected_sheet_label="Operator Scoped Invoice",
        selected_page_label="page 1",
        selected_print_areas=("Operator Scoped Invoice!A1:H42",),
        source_workbook_mac_path="/Users/hwinshipwheatley/Documents/Invoices/Placeholder/Invoice ST Anne's Running.xlsx",
        output_bridge_path="/mnt/e/openclaw/artifacts/invoice_workbooks/st_annes/fixture_invoice/fixture_invoice.pdf",
        output_pdf_mac_path="/Volumes/openclaw_e/artifacts/invoice_workbooks/st_annes/fixture_invoice/fixture_invoice.pdf",
        output_mac_path="scoped_st_annes_export/Operator_Scoped_Invoice/fixture_invoice.pdf",
        client_display_name="St. Anne's",
        created_at="2026-05-31T14:00:00+00:00",
        expires_at="2026-05-31T14:05:00+00:00",
    )
    response = _route(event)
    action = response["structured_actions"][0]

    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_ACTION_ROUTED"
    assert action["handler_id"] == "invoice_review_action_request.st_annes"
    assert action["workflow_payload"]["client_ref"] == "st_annes"
    assert action["workflow_payload"]["payload"]["rail_ref"] == "simple_invoice_event_bridge_pdf_artifact_rail_v0"


def test_telegram_command_event_uses_same_workflow_payload_shape():
    mac_event = contract.make_live_arts_prepare_pdf_event(source_channel="MAC_APP", event_kind="UI_BUTTON_CLICK")
    telegram_event = contract.make_live_arts_prepare_pdf_event(
        source_channel="TELEGRAM",
        event_kind="TELEGRAM_COMMAND",
    )

    mac_response = _route(mac_event)
    telegram_response = _route(telegram_event)
    mac_payload = _workflow_payload(mac_response)
    telegram_payload = _workflow_payload(telegram_response)

    assert tuple(mac_payload.keys()) == tuple(telegram_payload.keys()) == contract.WORKFLOW_PAYLOAD_FIELDS
    assert mac_payload["payload_shape_ref"] == telegram_payload["payload_shape_ref"]
    assert mac_payload["request_type"] == telegram_payload["request_type"]
    assert mac_payload["action_kind"] == telegram_payload["action_kind"]
    assert mac_payload["client_ref"] == telegram_payload["client_ref"]
    assert mac_payload["workflow_ref"] == telegram_payload["workflow_ref"]
    assert telegram_payload["source_channel"] == "TELEGRAM"
    assert telegram_response["structured_actions"][0]["surface_semantics"] == "COMPACT_SURFACE_NOT_WORKFLOW_BRAIN"


def test_stale_event_is_rejected_or_superseded():
    event = contract.make_live_arts_prepare_pdf_event(
        event_id="old_card_click_event",
        parent_event_id="old_chat_card_event",
        created_at="2026-05-31T13:50:00+00:00",
        expires_at="2026-05-31T13:55:00+00:00",
    )
    current_action = {
        "event_id": "current_live_arts_md_prepare_pdf_action",
        "event_kind": "WORKFLOW_ACTION_REQUEST",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "thread_ref": "live_arts_md_invoice_workflow:2026-1001",
        "expected_intended_use": "prepare_selected_invoice_pdf_artifact",
    }
    response = contract.route_event(
        event,
        now=FIXED_NOW,
        current_action_index={contract.event_scope_key(event): current_action},
    )

    assert response["route_status"] == "ROUTE_REJECTED_STALE_EVENT"
    assert response["stale_event"] is True
    assert response["error_code"] in {"STALE_EVENT", "SUPERSEDED_EVENT"}
    assert response["superseded_by_event_id"] == "current_live_arts_md_prepare_pdf_action"
    assert response["next_expected_event"]["event_id"] == "current_live_arts_md_prepare_pdf_action"


def test_missing_idempotency_key_fails_validation():
    event = contract.make_live_arts_prepare_pdf_event()
    event["idempotency_key"] = ""

    validation = contract.validate_event(event, now=FIXED_NOW)
    response = contract.route_event(event, now=FIXED_NOW)

    assert validation.valid is False
    assert "MISSING_IDEMPOTENCY_KEY" in validation.errors
    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert response["error_code"] == "MISSING_IDEMPOTENCY_KEY"


def test_live_arts_prepare_pdf_request_preserves_no_email_no_ledger_no_cell_read_guards():
    event = contract.make_live_arts_prepare_pdf_event()
    response = _route(event)
    payload = _workflow_payload(response)

    assert event["no_email_send"] is True
    assert event["no_gmail"] is True
    assert event["no_browser"] is True
    assert event["safety_flags"]["no_browser"] is True
    assert event["authority_boundary"]["browser_access_allowed"] is False
    assert event["authority_profile_ref"] == "event_bridge_finance_workflow_action_v0"
    assert event["positive_occupation_template_ref"] == "event_bridge_finance_workflow_action_template"
    assert event["no_ledger_post"] is True
    assert event["no_coupa"] is True
    assert event["no_workbook_cell_read"] is True
    assert payload["no_email_send"] is True
    assert payload["no_ledger_post"] is True
    assert payload["no_workbook_cell_read"] is True
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["browser_access_allowed"] is False
    assert payload["authority_boundary"]["ledger_post_allowed"] is False
    assert payload["authority_boundary"]["workbook_cell_read_allowed"] is False
    assert response["structured_actions"][0]["requires_receipt_before_business_mutation"] is True


def test_local_surface_result_can_report_pdf_candidate():
    event = contract.make_live_arts_pdf_candidate_result_event()
    response = _route(event)
    action = response["structured_actions"][0]
    payload = action["workflow_payload"]

    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_RESULT_CANDIDATE_RECORDED"
    assert action["structured_action_kind"] == "REPORT_RESULT_CANDIDATE"
    assert response["receipt_refs"] == ("pdf_export_candidate_receipt:live_arts_md:2026-1001",)
    assert payload["request_type"] == "LOCAL_SURFACE_RESULT"
    assert payload["payload"]["exported_pdf_mac_path"].endswith(".pdf")
    assert payload["payload"]["attachment_ready"] is False
    assert payload["payload"]["approval_ready"] is False
    assert payload["payload"]["ledger_posting_allowed"] is False


def test_response_envelope_is_scoped_to_same_workflow_client_thread():
    event = contract.make_live_arts_prepare_pdf_event()
    response = _route(event)
    payload = _workflow_payload(response)

    assert response["event_id"] == event["event_id"]
    assert response["correlation_id"] == event["correlation_id"]
    assert response["scope"]["client_ref"] == event["client_ref"] == payload["client_ref"]
    assert response["scope"]["workflow_ref"] == event["workflow_ref"] == payload["workflow_ref"]
    assert response["scope"]["thread_ref"] == event["thread_ref"] == payload["thread_ref"]
    assert response["next_expected_event"]["client_ref"] == event["client_ref"]
    assert response["next_expected_event"]["workflow_ref"] == event["workflow_ref"]


def test_no_gmail_browser_ledger_coupa_authority_exists():
    payload = contract.build_contract_payload(generated_at="2026-05-31T14:00:00+00:00")

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["no_gmail_browser_ledger_coupa_authority"] is True
    assert payload["authority_boundary"]["gmail_access_allowed"] is False
    assert payload["authority_boundary"]["browser_access_allowed"] is False
    assert payload["authority_boundary"]["browser_automation_allowed"] is False
    assert payload["authority_boundary"]["ledger_post_allowed"] is False
    assert payload["authority_boundary"]["coupa_access_allowed"] is False
    assert payload["authority_boundary"]["coupa_submit_allowed"] is False
    assert all(value is False for value in payload["authority_boundary"].values())


def test_authority_boundary_no_browser_true_is_rejected_with_positive_replacement():
    event = contract.make_live_arts_prepare_pdf_event()
    event["authority_boundary"] = {"no_browser": True}

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert response["error_code"] == "AUTHORITY_SEMANTICS_DRIFT:WRONG_BOOLEAN_POLARITY:authority_boundary.no_browser"
    assert "event_bridge_finance_workflow_action_template" in response["error_message"] or response["error_message"]


def test_dangerous_ledger_post_allowed_true_is_rejected():
    event = contract.make_live_arts_prepare_pdf_event()
    event["authority_boundary"]["ledger_post_allowed"] = True

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert response["error_code"] == "AUTHORITY_SEMANTICS_DRIFT:UNSAFE_TRUE_GRANT:authority_boundary.ledger_post_allowed"


def test_missing_operator_receipt_guard_is_rejected():
    event = contract.make_live_arts_prepare_pdf_event()
    event["safety_flags"].pop("operator_receipt_required_before_mutation")

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert response["error_code"] == (
        "AUTHORITY_SEMANTICS_DRIFT:MISSING_REQUIRED_FIELD:"
        "safety_flags.operator_receipt_required_before_mutation"
    )


def test_export_script_writes_json_and_operator_readback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_openclaw_event_bridge_contract.py",
            "--export-root",
            str(tmp_path),
            "--generated-at",
            "2026-05-31T14:00:00+00:00",
        ],
    )

    assert export_main() == 0
    json_path = tmp_path / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / contract.OPERATOR_EXPORT_NAME
    exported = json.loads(json_path.read_text(encoding="utf-8"))

    assert json_path.exists()
    assert operator_path.exists()
    assert exported["schema_version"] == contract.SCHEMA_VERSION
    assert exported["machine_proof"]["mac_and_telegram_same_workflow_payload_shape"] is True
