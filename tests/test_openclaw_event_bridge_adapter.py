import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_event_bridge_adapter as adapter
import openclaw_event_bridge_contract as contract


FIXED_NOW = "2026-05-31T14:00:30+00:00"


def _route(event: dict, *, now: str = FIXED_NOW) -> dict:
    return adapter.route_event_bridge_envelope(event, now=now)


def test_valid_mac_prepare_pdf_event_routes_into_existing_handler_selection():
    event = contract.make_live_arts_prepare_pdf_event(
        event_kind="WORKFLOW_ACTION_REQUEST",
        source_channel="MAC_APP",
    )

    response = _route(event)
    request = response["processor_request"]

    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_ACTION_ROUTED"
    assert response["correlation_id"] == event["correlation_id"]
    assert response["router_decision"]["selected_handler_id"] == "invoice_review_action_request.live_arts_md"
    assert response["router_decision"]["selected_handler_label"] == "Live Arts MD invoice review guided action"
    assert request["request_id"] == event["event_id"]
    assert request["event_id"] == event["event_id"]
    assert request["idempotency_key"] == event["idempotency_key"]
    assert request["correlation_id"] == event["correlation_id"]
    assert request["client_ref"] == "live_arts_md"
    assert request["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert request["thread_ref"] == event["thread_ref"]
    assert request["request_type"] == "INVOICE_REVIEW_ACTION_REQUEST"
    assert request["intended_use"] == "prepare_selected_invoice_pdf_artifact"
    assert request["hidden_request_payload"]["no_external_action"] is True


def test_invalid_missing_idempotency_key_fails_before_router_call():
    event = contract.make_live_arts_prepare_pdf_event()
    event["idempotency_key"] = ""

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert response["workflow_status"] == "WORKFLOW_BLOCKED"
    assert response["error_code"] == "MISSING_IDEMPOTENCY_KEY"
    assert "MISSING_IDEMPOTENCY_KEY" in response["error_message"]
    assert response["processor_request"] == {}
    assert response["machine_proof"]["router_called"] is False


def test_missing_client_workflow_scope_fails_before_router_call():
    event = contract.make_live_arts_prepare_pdf_event()
    event["client_ref"] = ""
    event["workflow_ref"] = ""

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert "MISSING_SCOPE:client_ref" in response["error_message"]
    assert "MISSING_SCOPE:workflow_ref" in response["error_message"]
    assert response["processor_request"] == {}


def test_false_no_ledger_post_guard_fails():
    event = contract.make_live_arts_prepare_pdf_event()
    event["no_ledger_post"] = False

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert response["error_code"] == "GUARD_NOT_TRUE:no_ledger_post"
    assert "GUARD_NOT_TRUE:no_ledger_post" in response["error_message"]
    assert response["machine_proof"]["handler_selected"] is False


def test_telegram_compact_event_validates_to_same_route_shape_without_runtime():
    mac_event = contract.make_live_arts_prepare_pdf_event(
        event_kind="WORKFLOW_ACTION_REQUEST",
        source_channel="MAC_APP",
    )
    telegram_event = contract.make_live_arts_prepare_pdf_event(
        event_kind="TELEGRAM_COMMAND",
        source_channel="TELEGRAM",
    )

    mac_response = _route(mac_event)
    telegram_response = _route(telegram_event)
    mac_request = mac_response["processor_request"]
    telegram_request = telegram_response["processor_request"]

    assert telegram_response["route_status"] == "ROUTE_MATCHED"
    assert telegram_response["router_decision"]["selected_handler_id"] == mac_response["router_decision"]["selected_handler_id"]
    assert telegram_request["request_type"] == mac_request["request_type"]
    assert telegram_request["intended_use"] == mac_request["intended_use"]
    assert telegram_request["client_ref"] == mac_request["client_ref"]
    assert telegram_request["workflow_ref"] == mac_request["workflow_ref"]
    assert telegram_request["source_channel"] == "TELEGRAM"
    assert telegram_response["machine_proof"]["telegram_runtime_started"] is False


def test_stale_event_produces_stale_response_without_route():
    event = contract.make_live_arts_prepare_pdf_event(
        event_id="old_live_arts_prepare_pdf_event",
        created_at="2026-05-31T13:50:00+00:00",
        expires_at="2026-05-31T13:55:00+00:00",
        parent_event_id="old_chat_card",
    )
    current_action = {
        "event_id": "current_live_arts_prepare_pdf_event",
        "event_kind": "WORKFLOW_ACTION_REQUEST",
        "expected_intended_use": "prepare_selected_invoice_pdf_artifact",
    }

    response = adapter.route_event_bridge_envelope(
        event,
        now=FIXED_NOW,
        current_action_index={contract.event_scope_key(event): current_action},
    )

    assert response["route_status"] == "ROUTE_REJECTED_STALE_EVENT"
    assert response["stale_event"] is True
    assert response["superseded_by_event_id"] == "current_live_arts_prepare_pdf_event"
    assert response["next_expected_event"]["event_id"] == "current_live_arts_prepare_pdf_event"
    assert response["processor_request"] == {}
    assert response["machine_proof"]["router_called"] is False


def test_local_surface_result_pdf_candidate_maps_to_existing_result_route():
    event = contract.make_live_arts_pdf_candidate_result_event(source_channel="MAC_APP")

    response = _route(event)
    request = response["processor_request"]

    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_RESULT_ROUTE_MATCHED"
    assert response["router_decision"]["selected_handler_id"] == "selected_invoice_pdf_export_completed_candidate.live_arts_md"
    assert request["request_type"] == "LOCAL_SURFACE_RESULT"
    assert request["intended_use"] == "selected_invoice_pdf_export_completed_candidate"
    assert request["exported_pdf_mac_path"].endswith(".pdf")
    assert request["hidden_request_payload"]["no_external_action"] is True


def test_no_gmail_browser_ledger_coupa_authority_is_introduced():
    event = contract.make_live_arts_prepare_pdf_event()
    response = _route(event)
    request = response["processor_request"]

    for boundary in (
        response["authority_boundary"],
        request["authority_boundary"],
        response["structured_actions"][0]["authority_boundary"],
    ):
        assert boundary["gmail_access_allowed"] is False
        assert boundary["browser_automation_allowed"] is False
        assert boundary["ledger_post_allowed"] is False
        assert boundary["coupa_access_allowed"] is False
        assert boundary["coupa_submit_allowed"] is False
        assert all(value is False for value in boundary.values())
    assert response["machine_proof"]["gmail_access_performed"] is False
    assert response["machine_proof"]["browser_access_performed"] is False
    assert response["machine_proof"]["coupa_access_performed"] is False
    assert response["machine_proof"]["ledger_post_performed"] is False
