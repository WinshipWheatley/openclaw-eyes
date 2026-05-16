import json
from pathlib import Path

from guardian_hitl_authority_reconciliation import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_guardian_hitl_authority_reconciliation,
    build_guardian_hitl_prompt_2_ready_packet,
    export_guardian_hitl_authority_reconciliation,
    format_guardian_hitl_authority_reconciliation,
)


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _by_surface_id(payload):
    return {item["surface_id"]: item for item in payload["all_surfaces"]}


def test_read_model_keeps_old_hitl_as_authority_conflict_not_obsolete():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)

    assert payload["schema_version"] == "guardian_hitl_authority_reconciliation_v0"
    assert payload["runtime_authority_changed"] is False
    assert payload["old_hitl_deleted"] is False
    assert payload["old_hitl_classification"] == "authority_conflict_reconcile_first"
    assert payload["old_hitl_obsolete"] is False
    assert payload["boundaries"]["old_hitl_json_jsonl_may_not_be_labeled_obsolete"] is True
    assert payload["boundaries"]["old_hitl_json_jsonl_delete_allowed"] is False
    assert payload["boundaries"]["old_hitl_json_jsonl_migration_allowed"] is False


def test_old_json_state_is_not_labeled_obsolete_when_current_code_references_it():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)
    state_files = {item["state_id"]: item for item in payload["approval_state_files"]}

    approval_pending = state_files["approval_pending_json"]
    assert approval_pending["used_by_current_repo_a"] is True
    assert approval_pending["classification"] == "authority_conflict_reconcile_first"
    assert approval_pending["raw_content_read"] is False

    hitl_state = state_files["hitl_pending_state_json"]
    assert hitl_state["used_by_current_repo_a"] is True
    assert hitl_state["classification"] == "authority_conflict_reconcile_first"


def test_surface_groups_cover_active_mixed_legacy_test_docs_and_unknown():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)
    by_id = _by_surface_id(payload)

    assert payload["active_authority_surfaces"]
    assert payload["mixed_authority_surfaces"]
    assert payload["legacy_reference_surfaces"]
    assert payload["test_only_surfaces"]
    assert payload["docs_only_surfaces"]
    assert payload["unknown_surfaces"]

    assert by_id["operator_action_path"]["current_classification"] == "active_runtime_path"
    assert by_id["chief_approval_brain"]["current_classification"] == "active_runtime_path"
    assert by_id["chief_approval_brain"]["authority_conflict"] is True
    assert by_id["hitl_pending_store"]["current_classification"] == "mixed_or_conflicting"
    assert by_id["hitl_pending_action_legacy"]["current_classification"] == "legacy_reference"
    assert by_id["repo_b_approval_tree"]["current_classification"] == "legacy_reference"
    assert by_id["live_service_usage"]["current_classification"] == "unknown"


def test_authority_decision_table_has_required_columns():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)

    required = {
        "surface",
        "file_path",
        "caller_callee",
        "state_store",
        "approval_object",
        "ttl_idempotency",
        "current_classification",
        "risk",
        "next_action",
    }
    assert payload["authority_decision_table"]
    for row in payload["authority_decision_table"]:
        assert required <= row.keys()


def test_cassandra_recovery_trace_is_fixed_scope_special_case():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)
    trace = payload["cassandra_recovery_trace"]

    assert trace["classification"] == "active_special_case"
    assert trace["fixed_scope"] is True
    assert trace["agent_id"] == "cassandra"
    assert trace["recovery_action_id"] == "cassandra_systemd_user_start"
    assert trace["request"]["execution_occurs"] is False
    assert trace["guardian_approval"]["execution_occurs"] is False
    assert trace["clearance_record"]["raw_command_text_allowed"] is False
    assert trace["execution_attempt"]["live_execution_observed_in_this_lane"] is False


def test_future_approval_contract_forbids_raw_command_and_freeform_shell():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)
    contract = payload["future_approval_contract"]

    assert contract["immutable_payload_required"] is True
    assert contract["idempotency_key_required"] is True
    assert contract["ttl_required"] is True
    assert contract["exact_action_binding_required"] is True
    assert contract["receipt_required"] is True
    assert contract["raw_command_text_allowed"] is False
    assert contract["freeform_shell_approval_allowed"] is False
    assert "raw shell strings" in contract["forbidden"]


def test_memory_import_remote_builder_and_send_expansion_remain_unsafe():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)
    packet = build_guardian_hitl_prompt_2_ready_packet()

    assert payload["boundaries"]["safe_to_import_cassandra_chief_memory"] is False
    assert payload["boundaries"]["safe_to_enable_remote_builder"] is False
    assert payload["boundaries"]["safe_to_expand_send_paths"] is False
    assert packet["safe_to_import_cassandra_chief_memory"] is False
    assert packet["safe_to_enable_remote_builder"] is False
    assert packet["safe_to_expand_send_paths"] is False
    assert packet["runtime_authority_changed"] is False
    assert packet["old_hitl_deleted"] is False


def test_export_writes_generated_json_and_operator_packet(tmp_path):
    summary = export_guardian_hitl_authority_reconciliation(
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    json_path = tmp_path / JSON_EXPORT_NAME
    operator_path = tmp_path / OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["old_hitl_classification"] == "authority_conflict_reconcile_first"
    assert summary["runtime_authority_changed"] is False
    assert summary["old_hitl_deleted"] is False

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == "guardian_hitl_authority_reconciliation_v0"
    assert "Old HITL cannot be deleted or labeled obsolete yet" in rendered
    assert "Cassandra/Chief memory import is not safe yet" in rendered


def test_operator_rendering_is_concise_and_no_repo_b_execution_claim():
    payload = build_guardian_hitl_authority_reconciliation(generated_at=FIXED_NOW)
    rendered = format_guardian_hitl_authority_reconciliation(payload)

    assert "OpenClaw currently has more than one approval shape in play" in rendered
    assert "Repo B" not in rendered or payload["repo_b_execution_allowed"] is False
    assert payload["repo_b_execution_allowed"] is False
    assert payload["boundaries"]["repo_b_execution_allowed"] is False
    assert "No raw data" not in rendered


def test_ready_packet_json_file_matches_required_shape():
    path = Path("docs/operations/GUARDIAN_HITL_AUTHORITY_RECONCILIATION_PROMPT_2_READY_PACKET.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "guardian_hitl_authority_reconciliation_prompt_2_ready_packet_v0"
    assert payload["prompt_2_ready"] is True
    assert payload["recommended_lane"] == "Guardian HITL SQLite Authority Contract v0"
    assert payload["old_hitl_classification"] == "authority_conflict_reconcile_first"
    assert payload["runtime_authority_changed"] is False
    assert payload["old_hitl_deleted"] is False
    assert payload["safe_to_import_cassandra_chief_memory"] is False
    assert payload["safe_to_enable_remote_builder"] is False
    assert payload["safe_to_expand_send_paths"] is False
