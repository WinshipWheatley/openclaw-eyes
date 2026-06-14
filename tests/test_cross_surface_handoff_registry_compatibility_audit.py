import json
import re
from pathlib import Path

import cross_surface_handoff_registry_compatibility_audit as audit
from scripts.export_cross_surface_handoff_registry_compatibility_audit import main as export_main


FIXED_NOW = "2026-05-24T18:30:00+00:00"


def _build() -> dict:
    return audit.build_cross_surface_handoff_registry_compatibility_audit(generated_at=FIXED_NOW)


def test_audit_is_deterministic_and_metadata_only():
    first = _build()
    second = _build()

    assert audit.stable_json(first) == audit.stable_json(second)
    assert first["schema_version"] == audit.SCHEMA_VERSION
    assert first["read_model_id"] == audit.READ_MODEL_ID
    assert first["contract_status"] == audit.CONTRACT_STATUS
    assert first["machine_proof"]["metadata_only_package_inspection"] is True
    assert first["machine_proof"]["no_migration_or_replacement_performed"] is True


def test_required_audit_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["handoff_compatibility_audit_model_present"] is True
    assert proof["handoff_bridge_compatibility_record_model_present"] is True
    assert proof["handoff_lifecycle_mapping_model_present"] is True
    assert proof["handoff_metadata_gap_model_present"] is True
    assert proof["handoff_migration_candidate_model_present"] is True
    assert proof["handoff_no_big_bang_migration_plan_model_present"] is True
    assert proof["handoff_compatibility_elioperator_report_model_present"] is True
    assert schemas["handoff_compatibility_audit"]["required_fields"] == list(audit.REQUIRED_AUDIT_FIELDS)
    assert schemas["handoff_bridge_compatibility_record"]["required_fields"] == list(
        audit.REQUIRED_RECORD_FIELDS
    )
    assert schemas["handoff_metadata_gap"]["required_fields"] == list(audit.REQUIRED_GAP_FIELDS)


def test_relevant_packages_and_intakes_are_represented():
    payload = _build()
    package_summaries = payload["package_manifest_summaries"]
    audited = payload["audit"]

    for name in audit.PACKAGE_NAMES:
        assert name in package_summaries
        assert package_summaries[name]["metadata_only_inspected"] is True
    assert "mission_control_capture_request_intake" in audited["audited_intake_contracts"]
    assert "capital_hilton_delivery_facts_capture_writer" in audited["audited_intake_contracts"]
    assert "capital_hilton_invoice_artifact_generator" in audited["audited_intake_contracts"]


def test_performance_dates_compatibility_record_exists():
    payload = _build()
    records = payload["compatibility_records_by_id"]
    record = records["record_performance_dates_capture_intake"]

    assert payload["machine_proof"]["performance_dates_record_present"] is True
    assert record["maps_to_artifact_type"] == "CAPTURE_REQUEST"
    assert record["maps_to_schema_ref"] == "mission_control_capture_request_intake.MissionControlBlockCaptureRequest"
    assert record["maps_to_block_id"] == "performance_dates"
    assert record["maps_to_operation"] == "add_dates"
    assert record["maps_to_target_handler"] == "mission_control_capture_request_intake"
    assert record["compatibility_status"] == "MOSTLY_COMPATIBLE"
    assert record["safe_to_patch_now"] is True


def test_po_coupa_compatibility_record_exists():
    payload = _build()
    records = payload["compatibility_records_by_id"]
    record = records["record_po_coupa_readback_package"]

    assert payload["machine_proof"]["po_coupa_record_present"] is True
    assert record["maps_to_artifact_type"] == "CAPTURE_READBACK"
    assert record["maps_to_block_id"] == "proof_po_reference"
    assert record["maps_to_operation"] == "set_needs_discovery"
    assert record["maps_to_lifecycle_state"] == "READBACK_READY"
    assert record["compatibility_status"] == "REGISTRY_READY"
    assert record["idempotency_present"] is True
    assert record["payload_hash_present"] is True


def test_invoice_artifact_preview_and_reusable_fact_records_exist():
    payload = _build()
    records = payload["compatibility_records_by_id"]
    artifact = records["record_invoice_artifact_preview"]
    reusable = records["record_reusable_fact_registry"]

    assert payload["machine_proof"]["invoice_artifact_preview_record_present"] is True
    assert artifact["maps_to_artifact_type"] == "INVOICE_ARTIFACT_PREVIEW"
    assert artifact["maps_to_lifecycle_state"] == "READBACK_READY"
    assert artifact["payload_hash_present"] is True
    assert payload["machine_proof"]["reusable_fact_record_present"] is True
    assert reusable["maps_to_artifact_type"] == "REUSABLE_FACT"
    assert reusable["compatibility_status"] == "DO_NOT_MIGRATE_YET"
    assert reusable["safe_to_patch_now"] is False


def test_lifecycle_mappings_exist():
    payload = _build()
    mappings = payload["lifecycle_mappings_by_id"]

    assert mappings["lifecycle_performance_dates_sqlite_written"]["registry_lifecycle_state"] == "WRITTEN"
    assert mappings["lifecycle_capture_readback_package_ready"]["registry_lifecycle_state"] == "READBACK_READY"
    assert mappings["lifecycle_delivery_facts_duplicate_noop"]["registry_lifecycle_state"] == "DUPLICATE_NOOP"
    assert mappings["lifecycle_invoice_artifact_preview_ready"]["registry_lifecycle_state"] == "READBACK_READY"


def test_metadata_gaps_and_migration_candidates_exist():
    payload = _build()
    gaps = payload["metadata_gaps_by_id"]
    candidates = payload["migration_candidates_by_id"]

    assert payload["machine_proof"]["metadata_gap_records_present"] is True
    assert gaps["gap_outbox_contract_payload_hash_idempotency"]["severity"] == "MUST_PATCH_BEFORE_MIGRATION"
    assert gaps["gap_reusable_fact_live_handler_absent"]["severity"] == "DO_NOT_PATCH_NOW"
    assert payload["machine_proof"]["migration_candidates_present"] is True
    assert candidates["candidate_add_post_office_metadata_to_performance_dates_intake"][
        "migration_type"
    ] == "ADD_METADATA_ONLY"
    assert candidates["candidate_leave_reusable_fact_bespoke_for_now"]["safe_to_do_now"] is False


def test_no_big_bang_plan_and_elioperator_report_exist():
    payload = _build()
    plan = payload["no_big_bang_migration_plan"]
    report = payload["elioperator_report"]

    assert payload["machine_proof"]["no_big_bang_plan_present"] is True
    assert "no file watcher" in plan["explicit_non_goals"]
    assert "no daemon" in plan["explicit_non_goals"]
    assert "no auto-import" in plan["explicit_non_goals"]
    assert "no live runtime queue" in plan["explicit_non_goals"]
    assert "no Telegram live integration" in plan["explicit_non_goals"]
    assert "no automatic agent dispatch" in plan["explicit_non_goals"]
    assert "no external actions" in plan["explicit_non_goals"]
    assert "no big-bang replacement" in plan["explicit_non_goals"]
    assert payload["machine_proof"]["elioperator_report_present"] is True
    assert "current Mac/PC handoff works" in report["plain_summary"]
    assert "Do not replace the working Mission Control capture intake." in report["what_not_to_touch"]


def test_all_live_authority_flags_false_and_no_replacement_performed():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for value in payload["authority_boundary"].values():
        assert value is False
    assert payload["machine_proof"]["no_migration_or_replacement_performed"] is True
    assert payload["machine_proof"]["package_manifest_raw_private_bodies_false"] is True


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
    assert data["machine_proof"]["raw_sensitive_fixture_values_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "PO-" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "cross_surface_handoff_registry_compatibility_audit.py",
            "scripts/export_cross_surface_handoff_registry_compatibility_audit.py",
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
