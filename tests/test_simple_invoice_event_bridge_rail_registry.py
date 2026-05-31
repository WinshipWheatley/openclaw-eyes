import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_event_bridge_adapter as adapter
import openclaw_event_bridge_contract as contract
import simple_invoice_event_bridge_rail_registry as registry
import simple_invoice_workflow_fixtures as fixtures
from scripts.export_simple_invoice_event_bridge_rail_registry import main as export_main


FIXED_NOW = "2026-05-31T14:00:30+00:00"


def _profile(payload: dict, client_ref: str) -> dict:
    return next(item for item in payload["client_profiles"] if item["client_ref"] == client_ref)


def _st_annes_seed_candidate() -> dict:
    return {
        "invoice_id": "st_annes_fixture_invoice",
        "sheet_label": "Operator Scoped Invoice",
        "work_type": "UNKNOWN_PLACEHOLDER_SCOPE",
        "amount_display": "UNKNOWN",
        "operator_provided_ranges": ("Operator Scoped Invoice!A1:H42",),
        "selected_page_label": "page 1",
    }


def test_live_arts_uses_generic_simple_invoice_event_bridge_rail():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)
    profile = _profile(payload, "live_arts_md")

    assert payload["rail_ref"] == "simple_invoice_event_bridge_pdf_artifact_rail_v0"
    assert profile["uses_rail"] == payload["rail_ref"]
    assert profile["prepare_pdf_action_descriptor"]["prepare_action_kind"] == "prepare_selected_invoice_pdf_artifact"
    assert profile["prepare_pdf_action_descriptor"]["invoice_id"] == "2026-1001"
    assert profile["prepare_pdf_event_template"]["payload"]["rail_ref"] == payload["rail_ref"]
    assert payload["machine_proof"]["all_simple_clients_use_generic_rail"] is True


def test_st_annes_placeholder_uses_same_rail_without_coupa_or_po():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)
    profile = _profile(payload, "st_annes")

    assert profile["uses_rail"] == payload["rail_ref"]
    assert profile["supplier_portal_required"] is False
    assert profile["purchase_order_required"] is False
    assert profile["supplier_portal_provider"] is None
    assert profile["selected_invoice_status"] == "UNKNOWN_OR_PLANNED"
    assert profile["prepare_pdf_action_descriptor"]["status"] == "PLANNED_OR_UNKNOWN_SCOPE"


def test_generic_rail_code_has_no_client_specific_constants():
    source = Path(registry.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "2026-1001",
        "Live Arts MD",
        "live_arts_md_invoice_workflow",
        "June 2026 Speaker Rental",
        "/prepare_live_arts_pdf",
    ):
        assert forbidden not in source


def test_prepare_pdf_action_descriptor_is_generated_from_fixture_config():
    fixture = fixtures.LIVE_ARTS_MD_SIMPLE_INVOICE_FIXTURE
    descriptor = registry.build_prepare_pdf_action_descriptor(fixture)

    assert descriptor["client_ref"] == fixture.client_ref
    assert descriptor["workflow_ref"] == fixture.workflow_ref
    assert descriptor["source_workbook_mac_path"] == fixture.expected_workbook_path
    assert descriptor["output_pdf_mac_path"].startswith("/Volumes/openclaw_e/artifacts/invoice_workbooks/")
    assert descriptor["output_bridge_path"].startswith("/mnt/e/openclaw/artifacts/invoice_workbooks/")
    assert descriptor["output_pdf_mac_path"].replace("/Volumes/openclaw_e", "/mnt/e/openclaw") == descriptor[
        "output_bridge_path"
    ]
    assert descriptor["event_envelope_fields"] == contract.EVENT_ENVELOPE_FIELDS
    assert descriptor["request_payload_ready"] is True


def test_event_bridge_safety_flags_are_identical_and_authority_grants_false():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)
    profiles = payload["client_profiles"]
    first_flags = profiles[0]["safety_flags"]

    assert payload["machine_proof"]["simple_clients_have_identical_safety_flags"] is True
    assert all(profile["safety_flags"] == first_flags for profile in profiles)
    assert payload["machine_proof"]["dangerous_authority_grants_false"] is True
    assert all(value is False for value in payload["authority_boundary"].values())
    for profile in profiles:
        assert all(value is False for value in profile["authority_boundary"].values())


def test_st_annes_can_instantiate_same_event_bridge_action_shape_when_scoped():
    fixture = fixtures.ST_ANNES_SIMPLE_INVOICE_FIXTURE
    descriptor = registry.build_prepare_pdf_action_descriptor(
        fixture,
        selected_candidate=_st_annes_seed_candidate(),
        source_workbook={"source_workbook_mac_path": fixture.expected_workbook_path},
    )
    event = registry.make_prepare_pdf_event_from_descriptor(
        descriptor,
        created_at="2026-05-31T14:00:00+00:00",
        expires_at="2026-05-31T14:05:00+00:00",
    )
    response = adapter.route_event_bridge_envelope(event, now=FIXED_NOW)

    assert descriptor["request_payload_ready"] is True
    assert event["client_ref"] == "st_annes"
    assert event["payload"]["action_kind"] == "prepare_selected_invoice_pdf_artifact"
    assert event["payload"]["rail_ref"] == registry.RAIL_REF
    assert event["payload"]["output_pdf_mac_path"] == descriptor["output_pdf_mac_path"]
    assert event["safety_flags"]["no_browser"] is True
    assert all(value is False for value in event["authority_boundary"].values())
    assert response["route_status"] == "ROUTE_MATCHED"
    assert response["workflow_status"] == "WORKFLOW_ACTION_ROUTED"
    assert response["router_decision"]["selected_handler_id"] == "invoice_review_action_request.st_annes"
    assert response["machine_proof"]["handler_execution_performed"] is False
    assert response["machine_proof"]["pdf_export_performed"] is False


def test_manual_attach_link_is_fallback_only():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)

    assert payload["machine_proof"]["manual_attach_link_fallback_only"] is True
    for profile in payload["client_profiles"]:
        fallback = profile["prepare_pdf_action_descriptor"]["manual_attach_link_fallback"]
        assert fallback["role"] == "FALLBACK_ONLY"
        assert fallback["primary_path"] is False


def test_capital_hilton_supplier_portal_extension_stays_separate():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)
    separation = payload["capital_hilton_separation"]

    assert separation["client_ref"] == "capital_hilton"
    assert separation["simple_invoice_rail_required"] is False
    assert separation["supplier_portal_extension_required"] is True
    assert separation["purchase_order_extension_required"] is True
    assert payload["machine_proof"]["simple_clients_do_not_inherit_coupa"] is True


def test_no_live_execution_authority_or_action_claims_are_added():
    payload = registry.build_registry_payload(generated_at=FIXED_NOW)

    for key in registry.NO_LIVE_ACTION_CLAIMS:
        assert payload["machine_proof"][key] is False
    assert payload["machine_proof"]["router_registers_simple_prepare_handlers"] is True


def test_export_writes_parseable_readmodel_and_operator_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_simple_invoice_event_bridge_rail_registry.py",
            "--export-root",
            str(tmp_path),
            "--generated-at",
            FIXED_NOW,
        ],
    )

    assert export_main() == 0
    json_path = tmp_path / registry.JSON_EXPORT_NAME
    operator_path = tmp_path / registry.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")

    assert payload["read_model_id"] == registry.READ_MODEL_ID
    assert payload["machine_proof"]["all_simple_clients_use_generic_rail"] is True
    assert "raw backend" not in operator.lower()
    assert "no live action authority" in operator
