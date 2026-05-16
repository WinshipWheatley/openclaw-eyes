import json
import sqlite3
from pathlib import Path

import guardian_hitl_dual_write_compatibility as dual_write


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _pending(*, action: str = "Google broker: cassandra -> google.gmail.send") -> dict:
    return {
        "id": "ABCD1234",
        "action": action,
        "requester": "google_broker",
        "requested_at": "2026-05-16 12:00:00",
        "status": "pending",
        "decision": None,
        "options": 2,
        "tier": 2,
        "hash": "HASH1234",
        "approval_context": {
            "action_label": "send email",
            "subject": "synthetic subject",
        },
    }


def _read_rows(db_path: Path, table: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]
    finally:
        conn.close()


def test_chief_pending_dict_builds_safe_canonical_mirror_without_raw_text():
    raw_action = "run shell command: rm -rf / && cat .chief.env"
    pending = _pending(action=raw_action)
    pending["approval_context"] = {
        "raw_command_text": "rm -rf /",
        "shell_command": "cat .chief.env",
        "action_label": "unsafe command",
    }

    mirror = dual_write.build_chief_approval_request_mirror(
        pending,
        generated_at=FIXED_NOW,
    )
    rendered = dual_write.stable_json(mirror)

    assert mirror["schema_version"] == "guardian_hitl_dual_write_compatibility_v0"
    assert mirror["canonical_payload"]["approval_id"] == "ABCD1234"
    assert mirror["canonical_payload"]["action_type"] == "chief_approval_request"
    assert mirror["canonical_payload"]["ttl_seconds"] == 86400
    assert mirror["canonical_payload"]["expires_at"] == "2026-05-17T12:00:00+00:00"
    assert mirror["raw_action_text_stored"] is False
    assert mirror["raw_command_text_stored"] is False
    assert mirror["freeform_shell_approval_allowed"] is False
    assert mirror["unsafe_context_key_count"] == 2
    assert "raw_command_text" not in mirror["approval_context_safe_keys"]
    assert "shell_command" not in mirror["approval_context_safe_keys"]
    assert "rm -rf" not in rendered
    assert ".chief.env" not in rendered
    assert "unsafe command" not in rendered


def test_record_chief_approval_request_mirror_persists_observational_rows_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = dual_write.record_chief_approval_request_mirror(
        _pending(),
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "mirrored"
    assert result["runtime_authority_changed"] is False
    assert result["runtime_authority"] is False
    assert result["dual_write_enabled"] is True
    assert result["caller_switched"] is False
    assert result["old_hitl_deleted"] is False
    assert result["legacy_json_authoritative"] is True
    assert result["raw_content_stored"] is False
    assert result["raw_action_text_stored"] is False
    assert result["raw_command_text_stored"] is False

    requests = _read_rows(db_path, "guardian_hitl_approval_requests")
    refs = _read_rows(db_path, "guardian_hitl_legacy_authority_refs")
    receipts = _read_rows(db_path, "guardian_hitl_approval_receipts")

    assert len(requests) == 1
    assert len(refs) == 1
    assert len(receipts) == 1
    request = requests[0]
    assert request["approval_id"] == "ABCD1234"
    assert request["source_surface_id"] == "chief_approval_brain"
    assert request["action_summary_label"] == "Chief approval request"
    assert request["runtime_authority"] == 0
    assert request["dual_write_enabled"] == 1
    assert request["caller_switched"] == 0
    assert request["old_hitl_deleted"] == 0
    assert request["legacy_json_authoritative"] == 1
    assert request["raw_content_stored"] == 0
    assert request["raw_action_text_stored"] == 0
    assert request["raw_command_text_stored"] == 0
    assert refs[0]["classification"] == "authority_conflict_reconcile_first"
    assert refs[0]["raw_content_read"] == 0
    assert receipts[0]["receipt_type"] == "request_shadow_created"

    rendered_rows = dual_write.stable_json(
        {"requests": requests, "refs": refs, "receipts": receipts}
    )
    assert "Google broker: cassandra" not in rendered_rows
    assert "synthetic subject" not in rendered_rows
    assert "send email" not in rendered_rows


def test_idempotency_key_is_stable_and_duplicate_records_are_not_recreated(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    pending = _pending()
    first = dual_write.build_chief_approval_request_mirror(pending)
    second = dual_write.build_chief_approval_request_mirror(pending)

    assert first["canonical_payload"]["idempotency_key"] == second["canonical_payload"]["idempotency_key"]

    result_1 = dual_write.record_chief_approval_request_mirror(pending, db_path=db_path)
    result_2 = dual_write.record_chief_approval_request_mirror(pending, db_path=db_path)

    assert result_1["status"] == "mirrored"
    assert result_2["status"] == "existing"
    assert len(_read_rows(db_path, "guardian_hitl_approval_requests")) == 1
    assert len(_read_rows(db_path, "guardian_hitl_approval_receipts")) == 1


def test_fail_open_helper_returns_failure_metadata_without_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("synthetic sqlite failure")

    monkeypatch.setattr(dual_write, "record_chief_approval_request_mirror", boom)

    result = dual_write.mirror_chief_approval_request_fail_open(_pending())

    assert result["status"] == "failed_open"
    assert result["adapter_health"] == "failed"
    assert result["runtime_authority_changed"] is False
    assert result["caller_switched"] is False
    assert result["old_hitl_deleted"] is False
    assert result["legacy_json_authoritative"] is True
    assert result["raw_command_text_stored"] is False


def test_read_model_and_operator_export_shape(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    dual_write.record_chief_approval_request_mirror(
        _pending(),
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    summary = dual_write.export_guardian_hitl_dual_write_read_model(
        export_root=export_root,
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    json_path = export_root / dual_write.JSON_EXPORT_NAME
    operator_path = export_root / dual_write.OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["request_mirror_count"] == 1
    assert summary["runtime_authority_changed"] is False
    assert summary["callers_switched"] is False
    assert summary["old_hitl_deleted"] is False
    assert summary["raw_action_text_stored"] is False
    assert summary["raw_command_text_stored"] is False

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == "guardian_hitl_dual_write_compatibility_v0"
    assert payload["legacy_json_authoritative"] is True
    assert payload["runtime_authority_changed"] is False
    assert payload["callers_switched"] is False
    assert payload["old_hitl_deleted"] is False
    assert payload["raw_action_text_stored"] is False
    assert payload["raw_command_text_stored"] is False
    assert "## Bottom Line" in rendered
    assert "## Still Blocked" in rendered


def test_module_does_not_import_repo_b_send_network_or_subprocess():
    source = Path("guardian_hitl_dual_write_compatibility.py").read_text(encoding="utf-8")

    assert "/home/openclaw_external/openclaw-runtime" not in source
    assert "subprocess" not in source
    assert "import requests" not in source
    assert "requests.post" not in source
    assert "chief_guardian_sender" not in source
    assert "approval_pending.json').read" not in source
