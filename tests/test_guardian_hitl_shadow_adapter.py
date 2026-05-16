import json
from pathlib import Path

from guardian_hitl_shadow_adapter import (
    CHOICE_PENDING_CLASSIFICATION,
    JSON_EXPORT_NAME,
    OLD_HITL_CLASSIFICATION,
    OPERATOR_EXPORT_NAME,
    build_guardian_hitl_shadow_adapter,
    export_guardian_hitl_shadow_adapter,
    format_guardian_hitl_shadow_adapter,
)


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _by_source(payload):
    return {item["source_surface_id"]: item for item in payload["shadow_records"]}


def test_shadow_adapter_is_read_model_only():
    payload = build_guardian_hitl_shadow_adapter(generated_at=FIXED_NOW)

    assert payload["schema_version"] == "guardian_hitl_shadow_adapter_v0"
    assert payload["runtime_authority_changed"] is False
    assert payload["runtime_authority"] is False
    assert payload["shadow_only"] is True
    assert payload["dual_write_enabled"] is False
    assert payload["caller_switched"] is False
    assert payload["old_hitl_deleted"] is False
    assert payload["real_approval_request_created"] is False
    assert payload["canonical_request_persisted"] is False
    assert payload["boundaries"]["read_model_only"] is True
    assert payload["boundaries"]["data_imported"] is False
    assert payload["boundaries"]["runtime_services_modified"] is False


def test_legacy_surfaces_map_into_canonical_shape_without_authority():
    payload = build_guardian_hitl_shadow_adapter(generated_at=FIXED_NOW)
    by_id = _by_source(payload)

    expected = {
        "chief_approval_brain",
        "approval_pending_json",
        "hitl_pending_store",
        "hitl_action_service",
        "hitl_pending_state_json",
        "hitl_audit_jsonl",
        "hitl_notification_service",
        "google_access_broker_approval_hook",
    }
    assert expected <= by_id.keys()
    assert payload["shadow_record_count"] == len(payload["shadow_records"])

    for record in payload["shadow_records"]:
        assert record["shadow_only"] is True
        assert record["dual_write_enabled"] is False
        assert record["caller_switched"] is False
        assert record["old_hitl_deleted"] is False
        assert record["runtime_authority"] is False
        assert record["real_approval_request_created"] is False
        assert record["can_approve"] is False
        assert record["can_execute"] is False
        assert record["canonical_target"]["state_store"] == "SQLite business_ops ledger"
        assert "approval_id" in record["canonical_target"]["required_request_fields"]
        assert "decision_receipt_id" in record["canonical_target"]["required_decision_fields"]
        assert "receipt_id" in record["canonical_target"]["required_receipt_fields"]


def test_old_hitl_json_classification_is_preserved_where_applicable():
    payload = build_guardian_hitl_shadow_adapter(generated_at=FIXED_NOW)
    by_id = _by_source(payload)

    assert payload["old_hitl_classification"] == OLD_HITL_CLASSIFICATION
    for surface_id in (
        "approval_pending_json",
        "hitl_pending_store",
        "hitl_pending_state_json",
        "hitl_audit_jsonl",
        "hitl_notification_service",
    ):
        assert by_id[surface_id]["old_hitl_classification"] == OLD_HITL_CLASSIFICATION


def test_no_live_hitl_json_files_are_written_deleted_or_read():
    payload = build_guardian_hitl_shadow_adapter(generated_at=FIXED_NOW)

    assert payload["live_legacy_store_read"] is False
    assert payload["live_legacy_store_written"] is False
    assert payload["live_legacy_store_deleted"] is False
    for record in payload["shadow_records"]:
        assert record["live_legacy_store_read"] is False
        assert record["live_legacy_store_written"] is False
        assert record["live_legacy_store_deleted"] is False
        assert record["raw_content_read"] is False


def test_choice_pending_is_not_guardian_approval_authority():
    payload = build_guardian_hitl_shadow_adapter(generated_at=FIXED_NOW)

    assert payload["choice_pending_classification"] == CHOICE_PENDING_CLASSIFICATION
    assert payload["choice_pending_is_guardian_approval_authority"] is False
    assert all(
        item["source_surface_id"] != "choice_pending_json_bridge"
        for item in payload["shadow_records"]
    )
    assert any(
        item["surface_id"] == "choice_pending_json_bridge"
        and item["classification"] == CHOICE_PENDING_CLASSIFICATION
        and item["guardian_approval_authority"] is False
        for item in payload["unmapped_surfaces"]
    )


def test_raw_command_freeform_shell_and_repo_b_runtime_remain_blocked():
    payload = build_guardian_hitl_shadow_adapter(generated_at=FIXED_NOW)

    assert payload["raw_command_or_shell_allowed"] is False
    forbidden = payload["canonical_contract_summary"]["forbidden_payload_keys"]
    assert "raw_command_text" in forbidden
    assert "freeform_shell" in forbidden
    assert "shell_command" in forbidden
    assert payload["repo_b_execution_allowed"] is False
    assert payload["repo_b_code_imported"] is False
    assert any(item["surface_id"] == "repo_b_approval_tree" for item in payload["blocked_surfaces"])
    assert any(
        item["surface_id"] == "raw_command_or_freeform_shell_approval"
        for item in payload["blocked_surfaces"]
    )


def test_export_writes_generated_json_and_operator_markdown(tmp_path):
    summary = export_guardian_hitl_shadow_adapter(
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    json_path = tmp_path / JSON_EXPORT_NAME
    operator_path = tmp_path / OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["shadow_only"] is True
    assert summary["dual_write_enabled"] is False

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == "guardian_hitl_shadow_adapter_v0"
    assert payload["runtime_authority_changed"] is False
    assert payload["shadow_only"] is True
    assert "## What Was Mapped" in rendered
    assert "## Still Legacy Or Mixed" in rendered
    assert "## Shadow Only" in rendered
    assert "## Not Guardian Approval Authority" in rendered
    assert "## Before Dual-Write" in rendered


def test_operator_markdown_mentions_no_runtime_changes():
    payload = build_guardian_hitl_shadow_adapter(generated_at=FIXED_NOW)
    rendered = format_guardian_hitl_shadow_adapter(payload)

    assert "No runtime behavior changed" in rendered
    assert "Dual-write enabled: `false`" in rendered
    assert "Callers switched: `false`" in rendered
    assert "Old HITL deleted: `false`" in rendered


def test_repo_b_code_is_not_imported_or_executed_by_module_source():
    source = Path("guardian_hitl_shadow_adapter.py").read_text(encoding="utf-8")

    assert "/home/openclaw_external/openclaw-runtime" not in source
    assert "import chief_approval_brain" not in source
    assert "import hitl_pending_store" not in source
    assert "import chief_guardian_listener" not in source
    assert "subprocess" not in source
