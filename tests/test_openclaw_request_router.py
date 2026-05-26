import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_request_router as router


def _request(**overrides):
    payload = {
        "request_id": "capital_hilton_invoice_workflow_field_mapping_fixture",
        "request_type": "LOCAL_SURFACE_RESULT",
        "intended_use": "client_invoice_sheet_schema_mapping",
        "world_ref": "finance",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "client_ref": "capital_hilton",
        "authority_boundary": {
            "external_action_allowed": False,
            "model_call_allowed": False,
        },
    }
    payload.update(overrides)
    return payload


def test_router_dispatches_local_surface_result_by_kind_and_intended_use():
    envelope, decision = router.route_request(
        _request(),
        source_request_filename="mission_control_chat_request_field_mapping.json",
        filename_request_family="CHAT",
    )

    assert envelope.filename_request_family == "CHAT"
    assert envelope.request_kind == "LOCAL_SURFACE_RESULT"
    assert decision.route_status == "ROUTE_MATCHED"
    assert decision.selected_handler_id == "client_invoice_sheet_schema_mapping.capital_hilton"
    assert decision.matched_by == ("request_kind", "intended_use", "world_ref", "workflow_ref", "client_ref")


def test_unknown_intended_use_is_parked_without_handler_execution():
    _envelope, decision = router.route_request(_request(intended_use="future_custom_client_action"))

    assert decision.route_status == "ROUTE_REJECTED_UNREGISTERED_INTENT"
    assert decision.parked is True
    assert decision.selected_handler_id == ""
    assert decision.next_safe_move


def test_router_dispatches_artifact_reference_approval_by_intended_use():
    payload = _request(
        request_type="ARTIFACT_REFERENCE_APPROVAL",
        intended_use="approve_readable_artifact_reference",
        artifact_intended_use="client_invoice_sheet_audit",
        artifact_kind="invoice_workbook",
    )

    envelope, decision = router.route_request(payload)

    assert envelope.request_kind == "ARTIFACT_REFERENCE_APPROVAL"
    assert decision.route_status == "ROUTE_MATCHED"
    assert decision.selected_handler_id == "approve_readable_artifact_reference.generic"
    assert decision.matched_by == ("request_kind", "intended_use")


def test_router_dispatches_local_surface_artifact_reference_approval():
    payload = _request(
        request_type="LOCAL_SURFACE_RESULT",
        intended_use="approve_readable_artifact_reference",
        artifact_intended_use="client_invoice_sheet_audit",
        artifact_kind="invoice_workbook",
    )

    _envelope, decision = router.route_request(payload)

    assert decision.route_status == "ROUTE_MATCHED"
    assert decision.selected_handler_id == "approve_readable_artifact_reference.generic"


def test_unsafe_authority_blocks_before_handler_match():
    payload = _request(authority_boundary={"external_action_allowed": True})

    _envelope, decision = router.route_request(payload)

    assert decision.route_status == "ROUTE_BLOCKED_AUTHORITY"
    assert decision.parked is True
    assert decision.selected_handler_id == ""


def test_future_handler_can_register_without_transport_semantics_change():
    handler = router.RequestHandlerRegistration(
        handler_id="niles.struna.scene_mapping",
        handler_label="Niles Struna scene mapping",
        request_kind="LOCAL_SURFACE_RESULT",
        intended_use="music_scene_mapping",
        world_refs=("music",),
        workflow_refs=("struna_scene_workflow",),
        client_refs=(),
        project_refs=("struna",),
        adapter_available=True,
        next_safe_move="Record local music scene mapping metadata only.",
    )
    payload = _request(
        intended_use="music_scene_mapping",
        world_ref="music",
        workflow_ref="struna_scene_workflow",
        client_ref="unknown",
        project_ref="struna",
    )

    envelope, decision = router.route_request(payload, handlers=(handler,))

    assert envelope.request_kind == "LOCAL_SURFACE_RESULT"
    assert decision.route_status == "ROUTE_MATCHED"
    assert decision.selected_handler_id == "niles.struna.scene_mapping"


def test_contract_payload_has_no_live_authority():
    payload = router.build_contract_payload()

    assert payload["machine_proof"]["handler_registration_boundary_present"] is True
    assert payload["machine_proof"]["future_handlers_can_register_without_transport_change"] is True
    assert all(value is False for value in payload["authority_boundary"].values())
    assert asdict(router.capital_hilton_field_mapping_handler()) in payload["registered_handlers"]
    assert any(handler["handler_id"] == "approve_readable_artifact_reference.generic" for handler in payload["registered_handlers"])
