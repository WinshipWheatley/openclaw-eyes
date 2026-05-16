import json
from pathlib import Path

from guardian_hitl_sqlite_authority_contract import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_guardian_hitl_sqlite_authority_contract,
    build_guardian_hitl_sqlite_contract_ready_packet,
    export_guardian_hitl_sqlite_authority_contract,
    format_guardian_hitl_sqlite_authority_contract,
    validate_canonical_approval_payload,
)


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _valid_payload():
    return {
        "approval_id": "ghitl_fixture_approval",
        "action_type": "cassandra_clara_fact_import_review",
        "actor": "cassandra",
        "target": "memory_authority_substrate",
        "payload_hash": "sha256:fixture",
        "payload_schema_version": "fixture_payload_v0",
        "source_intent_ref": "intent_fixture_001",
        "idempotency_key": "idem_fixture_001",
        "requested_at": "2026-05-16T12:00:00+00:00",
        "expires_at": "2026-05-16T13:00:00+00:00",
        "ttl_seconds": 3600,
        "authority_scope": "schema_review_only",
        "risk_tier": "review_required",
    }


def test_contract_defines_canonical_sqlite_approval_object():
    payload = build_guardian_hitl_sqlite_authority_contract(generated_at=FIXED_NOW)
    approval_object = payload["canonical_approval_object"]

    assert payload["schema_version"] == "guardian_hitl_sqlite_authority_contract_v0"
    assert payload["contract_defined"] is True
    assert payload["canonical_state_store"] == "SQLite business_ops ledger"
    assert approval_object["immutable_payload_required"] is True
    assert approval_object["payload_hash_required"] is True
    assert approval_object["idempotency_key_required"] is True
    assert approval_object["ttl_required"] is True
    assert approval_object["exact_action_binding_required"] is True
    assert approval_object["receipt_required"] is True
    assert {
        "approval_id",
        "action_type",
        "actor",
        "target",
        "payload_hash",
        "idempotency_key",
        "expires_at",
        "ttl_seconds",
    } <= set(approval_object["required_request_fields"])


def test_validate_canonical_payload_requires_identity_ttl_and_idempotency():
    payload = _valid_payload()
    result = validate_canonical_approval_payload(payload)

    assert result["valid"] is True
    assert result["errors"] == []

    missing = dict(payload)
    del missing["idempotency_key"]
    missing["ttl_seconds"] = 0
    result = validate_canonical_approval_payload(missing)

    assert result["valid"] is False
    assert any("idempotency_key" in error for error in result["errors"])
    assert "ttl_seconds_must_be_positive_integer" in result["errors"]


def test_raw_command_text_and_freeform_shell_payloads_are_forbidden():
    payload = _valid_payload()
    payload["shell_command"] = "rm -rf /"
    payload["nested"] = {"raw_command_text": "python3 dangerous.py"}

    result = validate_canonical_approval_payload(payload)

    assert result["valid"] is False
    assert any("shell_command" in error for error in result["errors"])
    assert any("nested.raw_command_text" in error for error in result["errors"])


def test_send_runtime_and_remote_builder_classes_need_explicit_authorized_packet():
    payload = _valid_payload()
    payload["action_class"] = "remote_builder"

    result = validate_canonical_approval_payload(payload)

    assert result["valid"] is False
    assert "explicit_authorized_packet_ref_required_for_action_class" in result["errors"]

    payload["explicit_authorized_packet_ref"] = "approved_packet_fixture"
    assert validate_canonical_approval_payload(payload)["valid"] is True


def test_runtime_authority_old_hitl_and_legacy_json_flags_stay_conservative():
    payload = build_guardian_hitl_sqlite_authority_contract(generated_at=FIXED_NOW)

    assert payload["runtime_authority_changed"] is False
    assert payload["old_hitl_deleted"] is False
    assert payload["legacy_json_still_active"] is True
    assert payload["old_hitl_classification"] == "authority_conflict_reconcile_first"
    assert payload["sqlite_schema_applied_to_runtime_db"] is False
    assert payload["boundaries"]["freeform_shell_approval_allowed"] is False
    assert payload["boundaries"]["raw_command_text_allowed"] is False


def test_old_json_remains_authority_conflict_while_active_paths_reference_it():
    payload = build_guardian_hitl_sqlite_authority_contract(generated_at=FIXED_NOW)
    refs = {item["state_id"]: item for item in payload["legacy_json_state_refs"]}

    assert refs["approval_pending_json"]["used_by_current_repo_a"] is True
    assert refs["approval_pending_json"]["classification"] == "authority_conflict_reconcile_first"
    assert refs["approval_pending_json"]["raw_content_read"] is False
    assert refs["hitl_pending_state_json"]["used_by_current_repo_a"] is True
    assert refs["hitl_audit_jsonl"]["classification"] == "authority_conflict_reconcile_first"


def test_cassandra_recovery_remains_fixed_scope_not_general_runtime_authority():
    payload = build_guardian_hitl_sqlite_authority_contract(generated_at=FIXED_NOW)
    recovery = payload["cassandra_recovery_clearance"]

    assert recovery["classification"] == "active_special_case"
    assert recovery["fixed_scope"] is True
    assert recovery["general_runtime_authority"] is False
    assert recovery["recovery_action_id"] == "cassandra_systemd_user_start"


def test_memory_import_remote_builder_and_send_paths_remain_unsafe():
    payload = build_guardian_hitl_sqlite_authority_contract(generated_at=FIXED_NOW)
    packet = build_guardian_hitl_sqlite_contract_ready_packet()

    assert payload["safe_to_import_cassandra_chief_memory"] is False
    assert payload["safe_to_enable_remote_builder"] is False
    assert payload["safe_to_expand_send_paths"] is False
    assert packet["safe_to_import_cassandra_chief_memory"] is False
    assert packet["safe_to_enable_remote_builder"] is False
    assert packet["safe_to_expand_send_paths"] is False
    assert packet["runtime_authority_changed"] is False
    assert packet["old_hitl_deleted"] is False


def test_export_writes_generated_json_and_operator_read_model(tmp_path):
    summary = export_guardian_hitl_sqlite_authority_contract(
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    json_path = tmp_path / JSON_EXPORT_NAME
    operator_path = tmp_path / OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["contract_defined"] is True
    assert summary["runtime_authority_changed"] is False

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == "guardian_hitl_sqlite_authority_contract_v0"
    assert "Raw command text and freeform shell approval are forbidden." in rendered
    assert "Cassandra/Chief memory import safe now: `false`" in rendered


def test_operator_rendering_and_ready_packet_shape():
    payload = build_guardian_hitl_sqlite_authority_contract(generated_at=FIXED_NOW)
    rendered = format_guardian_hitl_sqlite_authority_contract(payload)
    packet = build_guardian_hitl_sqlite_contract_ready_packet()

    assert "The canonical approval contract is now defined" in rendered
    assert "Do not delete or deprecate old HITL JSON" in rendered
    assert packet["schema_version"] == "guardian_hitl_sqlite_authority_contract_ready_packet_v0"
    assert packet["contract_defined"] is True
    assert packet["legacy_json_still_active"] is True
    assert packet["recommended_next_lane"] == "Guardian HITL SQLite Contract Adapter Plan v0"


def test_ready_packet_json_file_matches_required_shape():
    path = Path("docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_READY_PACKET.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "guardian_hitl_sqlite_authority_contract_ready_packet_v0"
    assert payload["contract_defined"] is True
    assert payload["runtime_authority_changed"] is False
    assert payload["old_hitl_deleted"] is False
    assert payload["legacy_json_still_active"] is True
    assert payload["safe_to_import_cassandra_chief_memory"] is False
    assert payload["safe_to_enable_remote_builder"] is False
    assert payload["safe_to_expand_send_paths"] is False
    assert "do not create general runtime execution authority" in payload["must_not_do"]
