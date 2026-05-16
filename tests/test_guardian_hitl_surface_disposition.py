import json
from pathlib import Path

from guardian_hitl_surface_disposition import (
    DISPOSITIONS,
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    SURFACES,
    build_guardian_hitl_surface_disposition,
    build_guardian_hitl_surface_disposition_ready_packet,
    export_guardian_hitl_surface_disposition,
    format_guardian_hitl_surface_disposition,
)


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _by_id(payload):
    return {item["surface_id"]: item for item in payload["surfaces"]}


def test_every_discovered_hitl_surface_has_valid_disposition():
    payload = build_guardian_hitl_surface_disposition(generated_at=FIXED_NOW)

    assert payload["schema_version"] == "guardian_hitl_surface_disposition_v0"
    assert payload["surface_count"] == len(SURFACES)
    assert payload["surfaces"]
    assert {item["disposition"] for item in payload["surfaces"]} <= DISPOSITIONS
    assert all(item["recommended_next_action"] for item in payload["surfaces"])
    assert all(item["risk_if_kept"] for item in payload["surfaces"])
    assert all(item["risk_if_removed"] for item in payload["surfaces"])


def test_required_surfaces_have_explicit_dispositions():
    payload = build_guardian_hitl_surface_disposition(generated_at=FIXED_NOW)
    by_id = _by_id(payload)

    expected = {
        "operator_action_path",
        "operator_action_inbox",
        "hitl_action_service",
        "hitl_pending_store",
        "approval_pending_json",
        "hitl_pending_state_json",
        "hitl_audit_jsonl",
        "chief_approval_brain",
        "chief_guardian_listener",
        "chief_guardian_sender",
        "hitl_notification_service",
        "cassandra_recovery_clearance",
    }
    assert expected <= by_id.keys()
    assert by_id["operator_action_path"]["disposition"] == "keep_canonical"
    assert by_id["operator_action_inbox"]["disposition"] == "keep_canonical"
    assert by_id["cassandra_recovery_clearance"]["disposition"] == "keep_canonical"
    assert by_id["chief_approval_brain"]["disposition"] == "keep_compatibility_shim"
    assert by_id["chief_guardian_listener"]["disposition"] == "keep_compatibility_shim"
    assert by_id["approval_pending_json"]["disposition"] == "keep_compatibility_shim"
    assert by_id["hitl_pending_store"]["disposition"] == "replace_with_sqlite_operator_action"
    assert by_id["hitl_action_service"]["disposition"] == "replace_with_sqlite_operator_action"
    assert by_id["hitl_pending_action_legacy"]["disposition"] == "retire_after_migration"
    assert by_id["repo_b_approval_tree"]["disposition"] == "block_no_go"


def test_old_json_state_is_not_marked_obsolete_or_deleted():
    payload = build_guardian_hitl_surface_disposition(generated_at=FIXED_NOW)
    by_id = _by_id(payload)

    assert payload["runtime_authority_changed"] is False
    assert payload["old_hitl_deleted"] is False
    assert by_id["approval_pending_json"]["actively_referenced"].startswith("yes")
    assert by_id["approval_pending_json"]["disposition"] == "keep_compatibility_shim"
    assert by_id["hitl_pending_state_json"]["disposition"] == "keep_compatibility_shim"
    assert "must not delete" in by_id["approval_pending_json"]["safe"]
    assert "obsolete" not in by_id["approval_pending_json"]["recommended_next_action"].lower()


def test_safety_flags_keep_memory_import_and_remote_builder_blocked():
    payload = build_guardian_hitl_surface_disposition(generated_at=FIXED_NOW)
    packet = build_guardian_hitl_surface_disposition_ready_packet()

    assert payload["safe_to_plan_adapters"] is True
    assert payload["safe_to_import_cassandra_chief_memory"] is False
    assert payload["safe_to_enable_remote_builder"] is False
    assert payload["boundaries"]["repo_b_execution_allowed"] is False
    assert packet["safe_to_plan_adapters"] is True
    assert packet["safe_to_import_cassandra_chief_memory"] is False
    assert packet["safe_to_enable_remote_builder"] is False
    assert packet["runtime_authority_changed"] is False
    assert packet["old_hitl_deleted"] is False


def test_no_repo_b_import_or_execution_surface_is_allowed():
    payload = build_guardian_hitl_surface_disposition(generated_at=FIXED_NOW)
    by_id = _by_id(payload)

    repo_b = by_id["repo_b_approval_tree"]
    assert repo_b["disposition"] == "block_no_go"
    assert "not imported or executed" in repo_b["actively_referenced"]
    assert payload["repo_b_execution_allowed"] is False
    assert payload["boundaries"]["repo_b_execution_allowed"] is False


def test_operator_output_includes_stays_replaces_retires_blocks():
    payload = build_guardian_hitl_surface_disposition(generated_at=FIXED_NOW)
    rendered = format_guardian_hitl_surface_disposition(payload)

    assert "## What Stays Canonical" in rendered
    assert "## Compatibility Only" in rendered
    assert "## Replace With SQLite Operator Action / Guardian Contract" in rendered
    assert "## Retire Later" in rendered
    assert "## Dangerous / Blocked" in rendered
    assert "## Cannot Touch Yet" in rendered
    assert "Operator Action stays canonical" in rendered
    assert "Do not import Cassandra/Chief memory as authority." in rendered


def test_export_writes_generated_json_and_operator_packet(tmp_path):
    summary = export_guardian_hitl_surface_disposition(
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    json_path = tmp_path / JSON_EXPORT_NAME
    operator_path = tmp_path / OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["safe_to_plan_adapters"] is True
    assert summary["safe_to_import_cassandra_chief_memory"] is False

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == "guardian_hitl_surface_disposition_v0"
    assert "Memory import and remote-builder work remain unsafe." in rendered


def test_ready_packet_file_matches_required_shape():
    path = Path("docs/operations/GUARDIAN_HITL_SURFACE_DISPOSITION_READY_PACKET.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "guardian_hitl_surface_disposition_ready_packet_v0"
    assert payload["prompt_2_ready"] is True
    assert payload["recommended_lane"] == "Guardian HITL SQLite Compatibility Adapter Plan v0"
    assert payload["safe_to_plan_adapters"] is True
    assert payload["safe_to_import_cassandra_chief_memory"] is False
    assert payload["safe_to_enable_remote_builder"] is False
    assert payload["runtime_authority_changed"] is False
    assert payload["old_hitl_deleted"] is False
    assert "do not wire adapters yet" in payload["must_not_do"]
