import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_surface_request_contract as surface
from scripts.export_local_surface_request_contract import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"


def test_required_models_exist_with_required_fields():
    assert tuple(field.name for field in fields(surface.LocalSurfaceRequest)) == (
        "request_id",
        "surface_type",
        "human_label",
        "human_reason",
        "concise_spoken_guidance",
        "device_type_target",
        "device_type_allowed",
        "input_requirements",
        "allowed_file_types",
        "allowed_file_extensions",
        "accepted_result_type",
        "world_ref",
        "client_ref",
        "workflow_ref",
        "related_contract_ref",
        "authority_boundary",
        "raw_body_allowed",
        "external_model_share_allowed",
        "arbitrary_scan_allowed",
        "path_translation_guess_allowed",
        "external_action_allowed",
        "local_only",
        "requires_operator_confirmation",
        "safe_to_auto_open",
        "fallback_if_unavailable",
        "troubleshooting_code",
        "result_expectation",
    )
    assert tuple(field.name for field in fields(surface.DeviceContext)) == (
        "device_context_id",
        "device_type_target",
        "device_type_allowed",
        "path_ref_styles_allowed",
        "unknown_device_degrades_to_guidance",
        "local_only",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(surface.LocalSurfaceRequestResultExpectation)) == (
        "expectation_id",
        "accepted_result_type",
        "result_must_be_local_metadata_only",
        "raw_body_allowed",
        "path_translation_guess_allowed",
        "external_model_share_allowed",
        "validation_required_before_next_action",
        "next_safe_move",
    )


def _assert_safe_request(request: dict) -> None:
    assert surface.validate_surface_request(request) == ()
    assert request["raw_body_allowed"] is False
    assert request["external_model_share_allowed"] is False
    assert request["arbitrary_scan_allowed"] is False
    assert request["path_translation_guess_allowed"] is False
    assert request["external_action_allowed"] is False
    assert request["local_only"] is True
    assert all(value is False for value in request["authority_boundary"].values())


def test_open_file_picker_request_is_structured_and_safe():
    request = surface.build_examples()["capital_hilton_need_workbook_file"]

    assert request["surface_type"] == "OPEN_FILE_PICKER"
    assert request["human_label"] == "Choose the invoice workbook"
    assert request["client_ref"] == "capital_hilton"
    assert request["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert request["world_ref"] == "finance"
    assert ".xlsx" in request["allowed_file_extensions"]
    assert request["accepted_result_type"] == "file_metadata_manifest"
    assert request["result_expectation"]["result_must_be_local_metadata_only"] is True
    _assert_safe_request(request)


def test_field_mapping_panel_request_is_structured_and_safe():
    request = surface.build_examples()["capital_hilton_need_field_mapping"]
    fields_requested = {item["field"] for item in request["input_requirements"]}

    assert request["surface_type"] == "SHOW_FIELD_MAPPING_PANEL"
    assert request["human_label"] == "Tell OpenClaw where the fields are"
    assert fields_requested >= {
        "sheet_tab_name",
        "invoice_number",
        "performance_dates",
        "rate",
        "subtotal_or_total",
        "po_reference",
        "formula_policy",
    }
    assert request["accepted_result_type"] == "field_mapping_manifest"
    _assert_safe_request(request)


def test_confirmation_card_does_not_imply_execution_authority():
    request = surface.build_examples()["capital_hilton_need_confirmation"]

    assert request["surface_type"] == "SHOW_CONFIRMATION_CARD"
    assert request["human_label"] == "Confirm the safe plan"
    assert request["requires_operator_confirmation"] is True
    assert request["safe_to_auto_open"] is False
    assert request["accepted_result_type"] == "operator_confirmation_receipt"
    _assert_safe_request(request)


def test_package_preview_does_not_dispatch_anything():
    request = surface.build_examples()["video_package_preview"]

    assert request["surface_type"] == "SHOW_PACKAGE_PREVIEW"
    assert request["human_label"] == "Review the package"
    assert "invoice" not in json.dumps(request).lower()
    _assert_safe_request(request)


def test_troubleshooting_card_represents_blocked_path_without_guessing_translation():
    request = surface.build_examples()["capital_hilton_blocked_path"]

    assert request["surface_type"] == "SHOW_TROUBLESHOOTING_CARD"
    assert request["human_label"] == "Fix file access"
    assert request["troubleshooting_code"] == "APPROVED_PC_PATH_REQUIRED"
    assert "not guess path translation" in request["concise_spoken_guidance"].lower()
    _assert_safe_request(request)


def test_default_policy_privacy_posture_is_strict():
    policy = surface.default_policy()

    assert policy.raw_body_allowed_default is False
    assert policy.external_model_share_allowed_default is False
    assert policy.arbitrary_scan_allowed_default is False
    assert policy.path_translation_guess_allowed_default is False
    assert policy.external_action_allowed_default is False
    assert policy.local_only_default is True


def test_unknown_device_type_degrades_to_human_guidance():
    request = surface.make_surface_request(
        surface_type="OPEN_FILE_PICKER",
        human_label="Choose a file",
        human_reason="Unknown device should not auto-open.",
        concise_spoken_guidance="Choose a file if available.",
        device_type_target="watch",
        device_type_allowed=("watch",),
    )
    payload = surface.asdict(request) if hasattr(surface, "asdict") else request.__dict__

    assert payload["device_type_target"] == "unknown"
    assert payload["safe_to_auto_open"] is False
    assert payload["fallback_if_unavailable"] == "Unknown device type: show human-readable guidance only."
    _assert_safe_request(payload)


def test_cross_domain_examples_do_not_become_invoice_specific():
    examples = surface.build_examples()
    cross_domain_keys = {
        "music_niles_project_picker",
        "video_package_preview",
        "photos_picker",
        "admin_cassandra_confirmation",
        "guardian_protected_file_boundary",
    }

    assert cross_domain_keys <= set(examples)
    for key in cross_domain_keys:
        rendered = json.dumps(examples[key]).lower()
        assert "capital_hilton" not in rendered
        assert "capital hilton" not in rendered
        _assert_safe_request(examples[key])


def test_infer_surface_request_from_handoff_response_context():
    payload = {
        "response_kind": "CLIENT_INVOICE_AUDIT_HANDOFF",
        "next_action": "Next: provide the invoice tab name and cell mapping.",
        "detail_disclosure": {
            "client_invoice_audit_handoff": {
                "live_audit_ready": False,
                "audit_handoff_readback": {
                    "path_approval_status": "APPROVED_PC_PATH_CAPTURED",
                    "schema_mapping_status": "NO_SCHEMA_REQUESTED",
                },
            }
        },
    }

    request = surface.infer_surface_request(payload)

    assert request["surface_type"] == "SHOW_FIELD_MAPPING_PANEL"
    assert request["human_label"] == "Tell OpenClaw where the fields are"
    _assert_safe_request(request)


def test_generated_json_parses_and_has_no_active_authority(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / surface.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert summary["read_model_id"] == surface.READ_MODEL_ID
    assert summary["all_examples_validate"] is True
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["device_ui_implemented"] is False
    assert payload["machine_proof"]["app_launch_performed"] is False
    assert payload["machine_proof"]["file_body_read_performed"] is False


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = surface.build_payload(generated_at=FIXED_NOW)
    surface.write_exports(payload, tmp_path)
    combined = (tmp_path / surface.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / surface.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined)
    for forbidden in ("actual secret", "credential value", "password value", "raw private body value", "file body value"):
        assert forbidden not in lowered
