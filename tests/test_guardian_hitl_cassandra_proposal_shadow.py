import json
import sqlite3
from pathlib import Path

import guardian_hitl_cassandra_proposal_shadow as shadow
import guardian_hitl_dual_write_compatibility as chief_dual_write


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _proposal_record(**overrides):
    record = {
        "action_id": "CAS12345",
        "source_agent": "cassandra",
        "action_type": "email_send",
        "payload": {
            "recipient": "test@example.com",
            "subject": "synthetic subject",
            "body": "private body says run rm -rf / and cat .chief.env",
            "raw_command_text": "rm -rf /",
            "shell_command": "cat .chief.env",
        },
        "idempotency_key": "idem-cas-1",
        "status": "WAITING_FOR_APPROVAL",
        "review_state": "NORMAL",
        "review_reason_codes": [],
        "normalized_amount": None,
        "requested_at": "2026-05-16T12:00:00",
        "expires_at": "2026-05-17T12:00:00",
        "approved_by": None,
        "approved_at": None,
        "denied_reason": None,
    }
    record.update(overrides)
    return record


def _read_rows(db_path: Path, table: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]
    finally:
        conn.close()


def test_cassandra_proposal_builds_safe_canonical_mirror_without_raw_payload():
    mirror = shadow.build_cassandra_hitl_proposal_mirror(
        _proposal_record(),
        generated_at=FIXED_NOW,
    )
    rendered = shadow.stable_json(mirror)

    assert mirror["schema_version"] == "guardian_hitl_cassandra_proposal_shadow_v0"
    assert mirror["source_surface_id"] == "hitl_pending_store"
    assert mirror["canonical_action_type"] == "cassandra_hitl_proposal"
    assert mirror["legacy_state_authority"] == "hitl_pending_state_json"
    assert mirror["canonical_payload"]["approval_id"] == "cassandra_hitl_CAS12345"
    assert mirror["canonical_payload"]["action_type"] == "cassandra_hitl_proposal"
    assert mirror["canonical_payload"]["ttl_seconds"] == 86400
    assert mirror["raw_payload_stored"] is False
    assert mirror["raw_command_text_stored"] is False
    assert mirror["freeform_shell_approval_allowed"] is False
    assert mirror["caller_switched"] is False
    assert mirror["old_hitl_deleted"] is False
    assert mirror["unsafe_payload_key_count"] == 2
    assert "raw_command_text" not in mirror["safe_payload_keys"]
    assert "shell_command" not in mirror["safe_payload_keys"]
    assert "private body" not in rendered
    assert "rm -rf" not in rendered
    assert ".chief.env" not in rendered
    assert "synthetic subject" not in rendered


def test_record_cassandra_proposal_persists_observational_rows_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = shadow.record_cassandra_hitl_proposal_mirror(
        _proposal_record(),
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
    assert result["raw_payload_stored"] is False
    assert result["raw_command_text_stored"] is False

    requests = _read_rows(db_path, "guardian_hitl_approval_requests")
    refs = _read_rows(db_path, "guardian_hitl_legacy_authority_refs")
    receipts = _read_rows(db_path, "guardian_hitl_approval_receipts")

    assert len(requests) == 1
    assert len(refs) == 1
    assert len(receipts) == 1
    request = requests[0]
    assert request["source_surface_id"] == "hitl_pending_store"
    assert request["legacy_approval_id"] == "CAS12345"
    assert request["action_type"] == "cassandra_hitl_proposal"
    assert request["action_summary_label"] == "Cassandra HITL proposal: email_send"
    assert request["runtime_authority"] == 0
    assert request["caller_switched"] == 0
    assert request["old_hitl_deleted"] == 0
    assert request["legacy_json_authoritative"] == 1
    assert request["raw_content_stored"] == 0
    assert request["raw_action_text_stored"] == 0
    assert request["raw_command_text_stored"] == 0
    assert refs[0]["source_surface_id"] == "hitl_pending_state_json"
    assert refs[0]["classification"] == "authority_conflict_reconcile_first"
    assert refs[0]["raw_content_read"] == 0
    assert receipts[0]["receipt_type"] == "cassandra_proposal_shadow_created"
    assert receipts[0]["source_surface"] == "hitl_pending_store"

    rendered_rows = shadow.stable_json(
        {"requests": requests, "refs": refs, "receipts": receipts}
    )
    assert "private body" not in rendered_rows
    assert "rm -rf" not in rendered_rows
    assert ".chief.env" not in rendered_rows
    assert "synthetic subject" not in rendered_rows


def test_idempotency_key_is_stable_and_duplicate_records_are_not_recreated(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    proposal = _proposal_record()
    first = shadow.build_cassandra_hitl_proposal_mirror(proposal)
    second = shadow.build_cassandra_hitl_proposal_mirror(proposal)

    assert first["canonical_payload"]["idempotency_key"] == second["canonical_payload"]["idempotency_key"]

    result_1 = shadow.record_cassandra_hitl_proposal_mirror(proposal, db_path=db_path)
    result_2 = shadow.record_cassandra_hitl_proposal_mirror(proposal, db_path=db_path)

    assert result_1["status"] == "mirrored"
    assert result_2["status"] == "existing"
    assert len(_read_rows(db_path, "guardian_hitl_approval_requests")) == 1
    assert len(_read_rows(db_path, "guardian_hitl_approval_receipts")) == 1


def test_approve_deny_and_expire_create_observational_decision_receipts(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    approved_record = _proposal_record(status="APPROVED", approved_by="operator")
    denied_record = _proposal_record(
        action_id="CAS54321",
        status="DENIED",
        denied_reason="synthetic denial",
    )
    expired_record = _proposal_record(action_id="CAS99999", status="EXPIRED")

    for record in (approved_record, denied_record, expired_record):
        shadow.record_cassandra_hitl_proposal_mirror(record, db_path=db_path)

    approved = shadow.record_cassandra_hitl_decision_receipt(
        approved_record,
        "APPROVED",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    denied = shadow.record_cassandra_hitl_decision_receipt(
        denied_record,
        "DENIED",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    expired = shadow.record_cassandra_hitl_decision_receipt(
        expired_record,
        "EXPIRED",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    assert approved["receipt_type"] == "decision_shadow_observed"
    assert denied["receipt_type"] == "decision_shadow_rejected"
    assert expired["receipt_type"] == "decision_shadow_expired"
    assert approved["runtime_authority_changed"] is False
    assert approved["caller_switched"] is False
    assert approved["old_hitl_deleted"] is False
    assert approved["raw_payload_stored"] is False

    receipts = _read_rows(db_path, "guardian_hitl_approval_receipts")
    receipt_types = {row["receipt_type"] for row in receipts}
    assert "decision_shadow_observed" in receipt_types
    assert "decision_shadow_rejected" in receipt_types
    assert "decision_shadow_expired" in receipt_types

    rendered_rows = shadow.stable_json({"receipts": receipts})
    assert "private body" not in rendered_rows
    assert "synthetic denial" not in rendered_rows
    assert "rm -rf" not in rendered_rows
    assert ".chief.env" not in rendered_rows


def test_decision_receipt_binds_to_existing_request_even_after_status_changes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    proposal = _proposal_record()
    shadow.record_cassandra_hitl_proposal_mirror(proposal, db_path=db_path)
    proposal["status"] = "APPROVED"
    proposal["approved_by"] = "operator"
    proposal["approved_at"] = "2026-05-16T12:05:00"

    result = shadow.record_cassandra_hitl_decision_receipt(
        proposal,
        "APPROVED",
        db_path=db_path,
    )

    assert result["status"] == "mirrored"
    assert result["receipt_type"] == "decision_shadow_observed"
    assert result["adapter_health"] == "healthy"


def test_missing_request_mirror_cannot_create_cassandra_approval_authority(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = shadow.record_cassandra_hitl_decision_receipt(
        _proposal_record(status="APPROVED"),
        "APPROVED",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "missing_request_mirror"
    assert result["runtime_authority_changed"] is False
    assert result["runtime_authority"] is False
    assert result["caller_switched"] is False
    assert result["old_hitl_deleted"] is False
    assert result["legacy_json_authoritative"] is True
    assert result["raw_payload_stored"] is False
    assert result["adapter_health"] == "needs_request_mirror"
    assert _read_rows(db_path, "guardian_hitl_approval_requests") == []
    assert _read_rows(db_path, "guardian_hitl_approval_receipts") == []


def test_decision_payload_mismatch_records_mismatch_without_trusting_sqlite(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    proposal = _proposal_record()
    shadow.record_cassandra_hitl_proposal_mirror(proposal, db_path=db_path)
    changed_proposal = _proposal_record(
        payload={"recipient": "other@example.com", "body": "changed private body"}
    )

    result = shadow.record_cassandra_hitl_decision_receipt(
        changed_proposal,
        "APPROVED",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "mismatch_observed"
    assert result["receipt_type"] == "legacy_sqlite_mismatch"
    assert result["adapter_health"] == "needs_review"
    assert result["runtime_authority_changed"] is False
    receipts = _read_rows(db_path, "guardian_hitl_approval_receipts")
    assert {row["receipt_type"] for row in receipts} == {
        "cassandra_proposal_shadow_created",
        "legacy_sqlite_mismatch",
    }
    rendered_rows = shadow.stable_json({"receipts": receipts})
    assert "changed private body" not in rendered_rows


def test_decision_fail_open_helper_returns_failure_metadata(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("synthetic decision mirror failure")

    monkeypatch.setattr(shadow, "record_cassandra_hitl_decision_receipt", boom)

    result = shadow.mirror_cassandra_hitl_decision_fail_open(
        _proposal_record(status="APPROVED"),
        "APPROVED",
    )

    assert result["status"] == "failed_open"
    assert result["adapter_health"] == "failed"
    assert result["runtime_authority_changed"] is False
    assert result["caller_switched"] is False
    assert result["old_hitl_deleted"] is False
    assert result["legacy_json_authoritative"] is True
    assert result["raw_payload_stored"] is False
    assert result["raw_command_text_stored"] is False


def test_fail_open_helper_returns_failure_metadata_without_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("synthetic sqlite failure")

    monkeypatch.setattr(shadow, "record_cassandra_hitl_proposal_mirror", boom)

    result = shadow.mirror_cassandra_hitl_proposal_fail_open(_proposal_record())

    assert result["status"] == "failed_open"
    assert result["adapter_health"] == "failed"
    assert result["runtime_authority_changed"] is False
    assert result["caller_switched"] is False
    assert result["old_hitl_deleted"] is False
    assert result["legacy_json_authoritative"] is True
    assert result["raw_payload_stored"] is False
    assert result["raw_command_text_stored"] is False


def test_hitl_store_shadow_runs_only_after_legacy_save_and_audit_succeed(tmp_path, monkeypatch):
    import hitl_pending_store as store

    monkeypatch.setattr(store, "HITL_STATE_PATH", tmp_path / "hitl_pending_state.json")
    monkeypatch.setattr(store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    calls = []
    monkeypatch.setattr(
        store,
        "_shadow_cassandra_hitl_proposal",
        lambda record, ttl_seconds: calls.append((record["action_id"], ttl_seconds)),
    )

    record = store.create_pending_action(
        "cassandra",
        "email_send",
        {"recipient": "test@example.com", "body": "synthetic body"},
        ttl_seconds=120,
        idempotency_key="idem-success",
    )

    assert calls == [(record["action_id"], 120)]
    assert (tmp_path / "hitl_pending_state.json").is_file()
    assert (tmp_path / "hitl_audit.jsonl").is_file()

    calls.clear()

    def fail_save(state):
        raise RuntimeError("save failed")

    monkeypatch.setattr(store, "_save_state", fail_save)
    try:
        store.create_pending_action("cassandra", "email_send", {}, idempotency_key="idem-save")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected save failure")
    assert calls == []


def test_hitl_store_shadow_does_not_run_when_audit_fails(tmp_path, monkeypatch):
    import hitl_pending_store as store

    monkeypatch.setattr(store, "HITL_STATE_PATH", tmp_path / "hitl_pending_state.json")
    monkeypatch.setattr(store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    calls = []
    monkeypatch.setattr(
        store,
        "_shadow_cassandra_hitl_proposal",
        lambda record, ttl_seconds: calls.append(record["action_id"]),
    )

    def fail_audit(record):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(store, "_audit", fail_audit)
    try:
        store.create_pending_action("cassandra", "email_send", {}, idempotency_key="idem-audit")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected audit failure")
    assert calls == []


def test_hitl_store_decision_shadow_runs_only_after_legacy_save_and_audit_succeed(tmp_path, monkeypatch):
    import hitl_pending_store as store

    monkeypatch.setattr(store, "HITL_STATE_PATH", tmp_path / "hitl_pending_state.json")
    monkeypatch.setattr(store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(store, "_shadow_cassandra_hitl_proposal", lambda record, ttl_seconds: None)
    calls = []
    monkeypatch.setattr(
        store,
        "_shadow_cassandra_hitl_decision",
        lambda record, decision_status: calls.append((record["action_id"], decision_status)),
    )

    record = store.create_pending_action(
        "cassandra",
        "email_send",
        {"recipient": "test@example.com", "body": "synthetic body"},
        ttl_seconds=120,
        idempotency_key="idem-decision-success",
    )

    assert store.update_action_status(record["action_id"], store.APPROVED, approved_by="operator") is True
    assert calls == [(record["action_id"], store.APPROVED)]

    calls.clear()

    def fail_save(state):
        raise RuntimeError("save failed")

    second = store.create_pending_action(
        "cassandra",
        "email_send",
        {"recipient": "test@example.com", "body": "synthetic body"},
        ttl_seconds=120,
        idempotency_key="idem-decision-save-fail",
    )
    monkeypatch.setattr(store, "_save_state", fail_save)
    try:
        store.update_action_status(second["action_id"], store.DENIED, denied_reason="no")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected save failure")
    assert calls == []


def test_hitl_store_expiry_shadow_runs_after_legacy_save(tmp_path, monkeypatch):
    import hitl_pending_store as store

    monkeypatch.setattr(store, "HITL_STATE_PATH", tmp_path / "hitl_pending_state.json")
    monkeypatch.setattr(store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(store, "_shadow_cassandra_hitl_proposal", lambda record, ttl_seconds: None)
    calls = []
    monkeypatch.setattr(
        store,
        "_shadow_cassandra_hitl_decision",
        lambda record, decision_status: calls.append((record["action_id"], decision_status)),
    )

    record = store.create_pending_action(
        "cassandra",
        "email_send",
        {"recipient": "test@example.com", "body": "synthetic body"},
        ttl_seconds=1,
        idempotency_key="idem-expired",
    )
    state = store._load_state()
    state[record["action_id"]]["expires_at"] = "2000-01-01T00:00:00"
    store._save_state(state)

    assert store.expire_stale_actions() == 1
    assert calls == [(record["action_id"], store.EXPIRED)]


def test_hitl_callback_path_creates_observational_decision_receipt_without_env_or_send(
    tmp_path,
    monkeypatch,
):
    import hitl_notification_service as notify
    import hitl_pending_store as store

    db_path = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(store, "HITL_STATE_PATH", tmp_path / "hitl_pending_state.json")
    monkeypatch.setattr(store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(notify, "_NOTIFY_LOG", tmp_path / "hitl_notifications.jsonl")
    monkeypatch.setattr(notify, "_notify_secret", lambda: b"synthetic-hitl-secret")
    monkeypatch.setattr(notify, "_maybe_send_no_pending_confirmation", lambda: None)

    def mirror_proposal(record, ttl_seconds):
        return shadow.mirror_cassandra_hitl_proposal_fail_open(
            record,
            ttl_seconds=ttl_seconds,
            db_path=db_path,
        )

    def mirror_decision(record, decision_status):
        return shadow.mirror_cassandra_hitl_decision_fail_open(
            record,
            decision_status,
            db_path=db_path,
        )

    monkeypatch.setattr(store, "_shadow_cassandra_hitl_proposal", mirror_proposal)
    monkeypatch.setattr(store, "_shadow_cassandra_hitl_decision", mirror_decision)

    record = store.create_pending_action(
        "cassandra",
        "email_send",
        {
            "recipient": "test@example.com",
            "body": "private callback body with rm -rf / and .chief.env",
            "raw_command_text": "rm -rf /",
        },
        ttl_seconds=120,
        idempotency_key="idem-callback-approve",
    )
    token = notify.generate_token(record["action_id"], "Y")

    result = notify.handle_callback(token, approved_by="operator")

    assert result == {
        "ok": True,
        "action_id": record["action_id"],
        "decision": "Y",
        "error": None,
    }
    receipts = _read_rows(db_path, "guardian_hitl_approval_receipts")
    receipt_types = {row["receipt_type"] for row in receipts}
    assert "cassandra_proposal_shadow_created" in receipt_types
    assert "decision_shadow_observed" in receipt_types
    rendered_rows = shadow.stable_json({"receipts": receipts})
    assert token not in rendered_rows
    assert "private callback body" not in rendered_rows
    assert "rm -rf" not in rendered_rows
    assert ".chief.env" not in rendered_rows


def test_hitl_callback_deny_path_creates_rejected_observational_receipt(
    tmp_path,
    monkeypatch,
):
    import hitl_notification_service as notify
    import hitl_pending_store as store

    db_path = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(store, "HITL_STATE_PATH", tmp_path / "hitl_pending_state.json")
    monkeypatch.setattr(store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(notify, "_NOTIFY_LOG", tmp_path / "hitl_notifications.jsonl")
    monkeypatch.setattr(notify, "_notify_secret", lambda: b"synthetic-hitl-secret")
    monkeypatch.setattr(notify, "_maybe_send_no_pending_confirmation", lambda: None)
    monkeypatch.setattr(
        store,
        "_shadow_cassandra_hitl_proposal",
        lambda record, ttl_seconds: shadow.mirror_cassandra_hitl_proposal_fail_open(
            record,
            ttl_seconds=ttl_seconds,
            db_path=db_path,
        ),
    )
    monkeypatch.setattr(
        store,
        "_shadow_cassandra_hitl_decision",
        lambda record, decision_status: shadow.mirror_cassandra_hitl_decision_fail_open(
            record,
            decision_status,
            db_path=db_path,
        ),
    )

    record = store.create_pending_action(
        "cassandra",
        "email_send",
        {"recipient": "test@example.com", "body": "private deny body"},
        ttl_seconds=120,
        idempotency_key="idem-callback-deny",
    )
    token = notify.generate_token(record["action_id"], "N")

    result = notify.handle_callback(token, approved_by="operator")

    assert result["ok"] is True
    assert result["decision"] == "N"
    receipts = _read_rows(db_path, "guardian_hitl_approval_receipts")
    assert "decision_shadow_rejected" in {row["receipt_type"] for row in receipts}
    assert "private deny body" not in shadow.stable_json({"receipts": receipts})


def test_export_read_model_and_operator_output_are_valid(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    shadow.record_cassandra_hitl_proposal_mirror(
        _proposal_record(),
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    shadow.record_cassandra_hitl_decision_receipt(
        _proposal_record(status="APPROVED"),
        "APPROVED",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    summary = shadow.export_guardian_hitl_cassandra_proposal_shadow_read_model(
        export_root=export_root,
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    json_path = export_root / shadow.JSON_EXPORT_NAME
    operator_path = export_root / shadow.OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["proposal_shadow_count"] == 1
    assert summary["decision_receipt_count"] == 1
    assert summary["runtime_authority_changed"] is False
    assert summary["caller_switched"] is False
    assert summary["old_hitl_deleted"] is False
    assert summary["raw_payload_stored"] is False

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == "guardian_hitl_cassandra_proposal_shadow_v0"
    assert payload["shared_guardian_hitl_tables_used"] is True
    assert payload["proposal_shadow_support"] is True
    assert payload["decision_receipt_shadow_support"] is True
    assert payload["callback_decision_shadow_support"] is True
    assert payload["legacy_json_authoritative"] is True
    assert payload["raw_payload_stored"] is False
    assert payload["decision_receipt_count"] == 1
    assert payload["mismatch_count"] == 0
    assert payload["safe_to_import_cassandra_chief_memory"] is True
    assert "## Bottom Line" in rendered
    assert "## Remaining Gates" in rendered

    rendered_payload = shadow.stable_json(payload) + rendered
    assert "private body" not in rendered_payload
    assert "rm -rf" not in rendered_payload
    assert ".chief.env" not in rendered_payload
    assert "operator-approved Cassandra/Chief memory import decision receipt" in rendered


def test_read_model_marks_memory_import_unsafe_when_mismatch_exists(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    shadow.record_cassandra_hitl_proposal_mirror(
        _proposal_record(),
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    shadow.record_cassandra_hitl_decision_receipt(
        _proposal_record(payload={"recipient": "other@example.com", "body": "changed"}),
        "APPROVED",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    payload = shadow.build_guardian_hitl_cassandra_proposal_shadow_read_model(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    assert payload["mismatch_count"] == 1
    assert payload["safe_to_import_cassandra_chief_memory"] is False


def test_chief_dual_write_read_model_stays_source_safe_with_shared_tables(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    shadow.record_cassandra_hitl_proposal_mirror(
        _proposal_record(),
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    chief_payload = chief_dual_write.build_guardian_hitl_dual_write_read_model(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    cassandra_payload = shadow.build_guardian_hitl_cassandra_proposal_shadow_read_model(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )

    assert chief_payload["request_mirror_count"] == 0
    assert chief_payload["decision_receipt_count"] == 0
    assert chief_payload["recent_request_mirrors"] == []
    assert cassandra_payload["proposal_shadow_count"] == 1


def test_module_does_not_import_repo_b_network_send_or_notification_paths():
    source = Path("guardian_hitl_cassandra_proposal_shadow.py").read_text(encoding="utf-8")
    store_source = Path("hitl_pending_store.py").read_text(encoding="utf-8")

    assert "/home/openclaw_external/openclaw-runtime" not in source
    assert "import subprocess" not in source
    assert "subprocess." not in source
    assert "import requests" not in source
    assert "requests.post" not in source
    assert "chief_guardian_sender" not in source
    assert "hitl_notification_service" not in source
    assert "send_pending_notification" not in source
    assert "process_callback" not in source
    assert "handle_callback" not in source
    assert "hitl_notification_service" not in store_source
    assert "import chief_env" not in "\n".join(
        Path("hitl_notification_service.py").read_text(encoding="utf-8").splitlines()[:40]
    )
    assert "/home/openclaw_external/openclaw-runtime" not in store_source
