import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_event_bridge_adapter as adapter
import openclaw_event_bridge_contract as contract
import simple_invoice_event_bridge_rail_registry as registry


FIXED_NOW = "2026-05-31T14:03:30+00:00"


def _route(event: dict) -> dict:
    return contract.route_event(event, now=FIXED_NOW)


def _workflow_payload(response: dict) -> dict:
    return response["structured_actions"][0]["workflow_payload"]


def test_approve_pdf_candidate_validates_with_required_fields():
    event = contract.make_live_arts_approve_pdf_candidate_event()

    validation = contract.validate_event(event, now=FIXED_NOW)
    response = _route(event)
    payload = _workflow_payload(response)

    assert validation.valid is True
    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_ACTION_ROUTED"
    assert response["structured_actions"][0]["handler_id"] == "invoice_review_action_request.live_arts_md"
    assert payload["action_kind"] == "approve_pdf_candidate"
    assert payload["payload"]["candidate_sha256"]
    assert payload["payload"]["observed_page_count"] == payload["payload"]["expected_page_count"] == 1
    assert payload["payload"]["operator_visual_review"] is True
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["ledger_posting_allowed"] is False
    assert payload["authority_boundary"]["browser_access_allowed"] is False
    assert payload["authority_boundary"]["portal_access_allowed"] is False


def test_reject_pdf_candidate_validates_with_required_fields():
    event = contract.make_live_arts_reject_pdf_candidate_event()

    validation = contract.validate_event(event, now=FIXED_NOW)
    response = _route(event)
    payload = _workflow_payload(response)

    assert validation.valid is True
    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_ACTION_ROUTED"
    assert response["structured_actions"][0]["handler_id"] == "invoice_review_action_request.live_arts_md"
    assert payload["action_kind"] == "reject_pdf_candidate"
    assert payload["payload"]["candidate_ref"] == "pdf_export_candidate_receipt:e4d6fc03cd5ca9fb"
    assert payload["payload"]["observed_page_count"] == 7
    assert payload["payload"]["expected_page_count"] == 1
    assert payload["payload"]["reason_code"] == "WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE"
    assert payload["payload"]["desired_page_known"] is False
    assert "observed_desired_pdf_page" not in payload["payload"]
    assert payload["payload"]["operator_visual_review"] is True
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["ledger_posting_allowed"] is False
    assert payload["authority_boundary"]["browser_access_allowed"] is False
    assert payload["authority_boundary"]["portal_access_allowed"] is False


def test_reject_pdf_candidate_requires_reason_code():
    event = contract.make_live_arts_reject_pdf_candidate_event(reason_code="")

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert "MISSING_REQUIRED_ACTION_FIELD:reason_code" in response["error_message"]


def test_reject_pdf_candidate_validates_without_observed_desired_pdf_page():
    event = contract.make_live_arts_reject_pdf_candidate_event(desired_page_known=None)

    response = _route(event)
    payload = _workflow_payload(response)

    assert response["route_status"] == "ROUTE_MATCHED"
    assert "desired_page_known" not in payload["payload"]
    assert "observed_desired_pdf_page" not in payload["payload"]


def test_reject_pdf_candidate_validates_with_desired_page_known_false():
    event = contract.make_live_arts_reject_pdf_candidate_event(desired_page_known=False)

    response = _route(event)
    payload = _workflow_payload(response)

    assert response["route_status"] == "ROUTE_MATCHED"
    assert payload["payload"]["desired_page_known"] is False
    assert "observed_desired_pdf_page" not in payload["payload"]


def test_reject_pdf_candidate_does_not_default_desired_page_to_two():
    event = contract.make_live_arts_reject_pdf_candidate_event()

    payload = event["payload"]

    assert payload["desired_page_known"] is False
    assert "observed_desired_pdf_page" not in payload
    assert 2 not in (
        payload.get("observed_desired_pdf_page"),
        payload.get("desired_pdf_page"),
    )


def test_reject_pdf_candidate_accepts_scope_mismatch_page_counts():
    event = contract.make_live_arts_reject_pdf_candidate_event(
        observed_page_count=7,
        expected_page_count=1,
        reason_code="WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE",
        desired_page_known=False,
    )

    response = _route(event)
    payload = _workflow_payload(response)

    assert response["route_status"] == "ROUTE_MATCHED"
    assert payload["payload"]["observed_page_count"] == 7
    assert payload["payload"]["expected_page_count"] == 1
    assert payload["payload"]["reason_code"] == "WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE"
    assert payload["payload"]["desired_page_known"] is False
    assert "observed_desired_pdf_page" not in payload["payload"]


def test_reject_pdf_candidate_accepts_known_observed_desired_pdf_page_only_when_marked_known():
    event = contract.make_live_arts_reject_pdf_candidate_event(
        desired_page_known=True,
        observed_desired_pdf_page=3,
    )

    response = _route(event)
    payload = _workflow_payload(response)

    assert response["route_status"] == "ROUTE_MATCHED"
    assert payload["payload"]["desired_page_known"] is True
    assert payload["payload"]["observed_desired_pdf_page"] == 3


def test_reject_pdf_candidate_rejects_page_value_when_desired_page_marked_unknown():
    event = contract.make_live_arts_reject_pdf_candidate_event(
        desired_page_known=False,
        observed_desired_pdf_page=2,
    )

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert "DESIRED_PAGE_UNKNOWN_BUT_OBSERVED_DESIRED_PDF_PAGE_PRESENT" in response["error_message"]


def test_approve_pdf_candidate_page_count_mismatch_is_invalid():
    event = contract.make_live_arts_approve_pdf_candidate_event(
        observed_page_count=1,
        expected_page_count=2,
    )

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert "PDF_CANDIDATE_PAGE_COUNT_MISMATCH" in response["error_message"]


def test_pdf_candidate_decision_rejects_email_send_authority():
    event = contract.make_live_arts_approve_pdf_candidate_event()
    event["authority_boundary"]["email_send_allowed"] = True

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert response["error_code"] == "AUTHORITY_SEMANTICS_DRIFT:UNSAFE_TRUE_GRANT:authority_boundary.email_send_allowed"


def test_pdf_candidate_decision_rejects_ledger_posting_authority():
    event = contract.make_live_arts_reject_pdf_candidate_event()
    event["authority_boundary"]["ledger_posting_allowed"] = True

    response = _route(event)

    assert response["route_status"] == "ROUTE_REJECTED_VALIDATION"
    assert "authority_boundary.ledger_posting_allowed" in response["error_message"]


def test_live_arts_pdf_candidate_decision_routes_to_simple_invoice_rail():
    event = contract.make_live_arts_approve_pdf_candidate_event()

    response = adapter.route_event_bridge_envelope(event, now=FIXED_NOW)

    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["router_decision"]["selected_handler_id"] == "invoice_review_action_request.live_arts_md"
    assert response["processor_request"]["action_kind"] == "approve_pdf_candidate"
    assert response["processor_request"]["rail_ref"] == registry.RAIL_REF
    assert response["machine_proof"]["email_send_performed"] is False
    assert response["machine_proof"]["ledger_post_performed"] is False
    assert response["machine_proof"]["browser_access_performed"] is False
    assert response["machine_proof"]["coupa_access_performed"] is False


def test_st_annes_placeholder_route_remains_intact():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)
    profile = next(item for item in payload["client_profiles"] if item["client_ref"] == "st_annes")

    assert profile["uses_rail"] == registry.RAIL_REF
    assert profile["supplier_portal_required"] is False
    assert profile["purchase_order_required"] is False
    assert profile["selected_invoice_status"] == "UNKNOWN_OR_PLANNED"
    assert profile["prepare_pdf_action_descriptor"]["status"] == "PLANNED_OR_UNKNOWN_SCOPE"
    assert payload["registered_simple_invoice_decision_handlers"] == ("invoice_review_action_request.live_arts_md",)
    assert "invoice_review_action_request.st_annes" not in payload["registered_simple_invoice_decision_handlers"]
    assert profile["pdf_candidate_decision_action_shapes"]["approve_pdf_candidate"]["handler_id"] == ""
    assert (
        profile["pdf_candidate_decision_action_shapes"]["approve_pdf_candidate"]["route_registration_status"]
        == "PLANNED_NOT_REGISTERED_FOR_PLACEHOLDER_SCOPE"
    )


def test_capital_hilton_remains_outside_simple_invoice_rail():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)
    separation = payload["capital_hilton_separation"]

    assert separation["client_ref"] == "capital_hilton"
    assert separation["simple_invoice_rail_required"] is False
    assert separation["supplier_portal_extension_required"] is True
    assert separation["purchase_order_extension_required"] is True
    assert "invoice_review_action_request.capital_hilton" not in payload["registered_simple_invoice_decision_handlers"]
