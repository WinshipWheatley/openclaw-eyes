import json
import re
from pathlib import Path

import cross_surface_handoff_registry_metadata_alignment as alignment
from scripts.export_cross_surface_handoff_registry_metadata_alignment import main as export_main


FIXED_NOW = "2026-05-24T19:30:00+00:00"


def _build() -> dict:
    return alignment.build_cross_surface_handoff_registry_metadata_alignment(generated_at=FIXED_NOW)


def test_alignment_is_deterministic_and_metadata_only():
    first = _build()
    second = _build()

    assert alignment.stable_json(first) == alignment.stable_json(second)
    assert first["schema_version"] == alignment.SCHEMA_VERSION
    assert first["read_model_id"] == alignment.READ_MODEL_ID
    assert first["contract_status"] == alignment.CONTRACT_STATUS
    assert first["machine_proof"]["live_behavior_changed"] is False
    assert first["machine_proof"]["live_registry_migration_added"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["handoff_metadata_alignment_patch_model_present"] is True
    assert proof["handoff_aligned_metadata_shape_model_present"] is True
    assert proof["handoff_metadata_patch_candidate_model_present"] is True
    assert proof["handoff_metadata_no_regression_check_model_present"] is True
    assert proof["handoff_metadata_elioperator_report_model_present"] is True
    assert schemas["handoff_metadata_alignment_patch"]["required_fields"] == list(
        alignment.REQUIRED_PATCH_FIELDS
    )
    assert schemas["handoff_aligned_metadata_shape"]["required_fields"] == list(
        alignment.REQUIRED_SHAPE_FIELDS
    )
    assert schemas["handoff_metadata_no_regression_check"]["required_fields"] == list(
        alignment.REQUIRED_NO_REGRESSION_FIELDS
    )


def test_additive_metadata_shape_includes_required_post_office_fields():
    payload = _build()
    shape = payload["aligned_metadata_shapes_by_id"]["aligned_po_coupa_delivery_facts_readback"]

    for field in alignment.POST_OFFICE_METADATA_FIELDS:
        assert field in shape
    assert shape["artifact_type"] == "DELIVERY_FACT_UPDATE"
    assert shape["schema_ref"] == (
        "capital_hilton_delivery_facts_capture_writer.CapitalHiltonDeliveryFactCaptureReadback"
    )
    assert shape["lifecycle_state"] == "READBACK_READY"
    assert payload["machine_proof"]["all_required_post_office_fields_modeled"] is True


def test_missing_fields_are_reported_not_faked():
    payload = _build()
    performance = payload["aligned_metadata_shapes_by_id"]["aligned_performance_dates_capture_readback"]
    intake = payload["aligned_metadata_shapes_by_id"]["aligned_delivery_facts_capture_intake_package"]

    assert performance["idempotency_key"] is None
    assert performance["payload_hash"] is None
    assert "idempotency_key" in performance["missing_fields"]
    assert "payload_hash" in performance["missing_fields"]
    assert "Older performance-date readback" in performance["missing_field_reasons"]["idempotency_key"]
    assert intake["idempotency_key"] is None
    assert intake["payload_hash"] is None
    assert "concrete capture request file" in intake["missing_field_reasons"]["payload_hash"]
    assert payload["machine_proof"]["missing_fields_reported_not_faked"] is True


def test_required_examples_exist():
    payload = _build()
    examples = payload["examples"]
    shapes = payload["aligned_metadata_shapes_by_id"]

    assert payload["machine_proof"]["performance_dates_example_present"] is True
    assert payload["machine_proof"]["po_coupa_readback_example_present"] is True
    assert payload["machine_proof"]["delivery_capture_intake_example_present"] is True
    assert payload["machine_proof"]["invoice_artifact_example_present"] is True
    assert payload["machine_proof"]["reusable_fact_compatibility_example_present"] is True
    for ref in examples.values():
        assert ref in shapes


def test_performance_dates_and_po_coupa_examples_are_safe():
    payload = _build()
    performance = payload["aligned_metadata_shapes_by_id"]["aligned_performance_dates_capture_readback"]
    po = payload["aligned_metadata_shapes_by_id"]["aligned_po_coupa_delivery_facts_readback"]

    assert performance["artifact_type"] == "CAPTURE_READBACK"
    assert performance["lifecycle_state"] == "DUPLICATE_NOOP"
    assert performance["authority_boundary"]["external_action_allowed"] is False
    assert po["block_id"] == "proof_po_reference"
    assert po["operation"] == "set_needs_discovery"
    assert po["privacy_boundary"]["raw_value_allowed"] is False
    assert po["authority_boundary"]["coupa_access_allowed"] is False
    assert "Needs Discovery" in po["safe_display_summary"]


def test_delivery_capture_intake_invoice_and_reusable_fact_examples():
    payload = _build()
    capture = payload["aligned_metadata_shapes_by_id"]["aligned_delivery_facts_capture_intake_package"]
    artifact = payload["aligned_metadata_shapes_by_id"]["aligned_invoice_artifact_preview"]
    reusable = payload["aligned_metadata_shapes_by_id"]["aligned_reusable_fact_future_compatibility"]

    assert capture["artifact_type"] == "CAPTURE_REQUEST"
    assert capture["target_handler"] == "capital_hilton_delivery_facts_capture_writer"
    assert capture["reply_to_surface"] == "Mission Control Mac"
    assert artifact["artifact_type"] == "INVOICE_ARTIFACT_PREVIEW"
    assert artifact["payload_hash"].startswith("sha256:a135264f8df")
    assert artifact["authority_boundary"]["email_send_allowed"] is False
    assert reusable["artifact_type"] == "REUSABLE_FACT"
    assert reusable["privacy_boundary"]["tokenized_value_ref_allowed"] is True
    assert reusable["privacy_boundary"]["raw_value_allowed"] is False
    assert "live_handler" in reusable["missing_fields"]


def test_no_regression_check_preserves_existing_behavior():
    payload = _build()
    check = payload["no_regression_check"]

    assert check["package_paths_unchanged"] is True
    assert check["existing_manifest_fields_preserved"] is True
    assert check["existing_consumers_not_required_to_parse_new_metadata"] is True
    assert check["live_behavior_changed"] is False
    assert check["live_registry_migration_added"] is False
    assert check["watcher_or_daemon_added"] is False
    assert check["external_authority_changed"] is False
    assert payload["machine_proof"]["package_paths_unchanged"] is True


def test_authority_and_non_goals_stay_closed():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["all_shape_external_authority_false"] is True
    for value in payload["authority_boundary"].values():
        assert value is False
    for non_goal in [
        "no live post-office runtime",
        "no watcher",
        "no daemon",
        "no auto-import",
        "no auto-consume",
        "no automatic handler dispatch",
        "no live Telegram",
        "no agent dispatch",
        "no migration or replacement of working rails",
        "no Mac Swift change",
    ]:
        assert non_goal in payload["explicit_non_goals"]


def test_do_not_migrate_items_remain_explicit():
    payload = _build()
    candidates = payload["patch_candidates_by_id"]

    assert candidates["candidate_reusable_fact_future_metadata_only"]["safe_to_align_now"] is False
    assert candidates["candidate_reusable_fact_future_metadata_only"][
        "compatibility_status_before"
    ] == "DO_NOT_MIGRATE_YET"
    assert "candidate_reusable_fact_future_metadata_only" in payload["machine_proof"]["do_not_migrate_items_remain"]


def test_elioperator_report_exists():
    payload = _build()
    report = payload["elioperator_report"]

    assert payload["machine_proof"]["elioperator_report_present"] is True
    assert "standard metadata shape" in report["plain_summary"]
    assert "No existing package path changed." in report["what_did_not_change"]
    assert any("Future packages can say what they are" in item for item in report["why_it_matters"])


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])

    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")
    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_protected_payload_examples_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "PO-" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "cross_surface_handoff_registry_metadata_alignment.py",
            "scripts/export_cross_surface_handoff_registry_metadata_alignment.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
