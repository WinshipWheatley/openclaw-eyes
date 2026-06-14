import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dead_letter_queue as dlq


FIXED_NOW = "2026-06-03T13:30:00+00:00"
RAW_BODY = "RAW_PROMPT_BODY_SHOULD_NOT_APPEAR"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY"})
    _write_json(root / "workflow_package_request_consumer_status.json", {"status": "WORKFLOW_PACKAGE_RAIL_STATUS_READY"})
    _write_json(root / "operator_conversation_journal.json", {"status": "OPERATOR_CONVERSATION_JOURNAL_READY"})
    return root


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _assert_no_unsafe_true_grants(payload: dict) -> None:
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "business_action_performed",
        "retry_executed",
        "raw_body_stored",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_builds_dead_letter_queue_for_recoverable_failures(tmp_path):
    read_model = dlq.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "dead_letter_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "DEAD_LETTER_QUEUE_READY"
    failure_kinds = {entry["failure_kind"] for entry in read_model["dead_letters"]}
    assert {
        "malformed_request",
        "missing_required_field",
        "unsafe_authority_requested",
        "unknown_workflow_ref",
        "stale_response",
        "missing_bridge_file",
        "service_not_current",
        "permission_required",
        "provider_gate_required",
    } == failure_kinds
    assert all(entry["raw_body_stored"] is False for entry in read_model["dead_letters"])
    assert all(entry["next_safe_action"] for entry in read_model["dead_letters"])
    assert read_model["machine_proof"]["retry_executed"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_raw_request_body_is_not_dumped(tmp_path):
    read_model = dlq.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "dead_letter_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    rendered = json.dumps(read_model)
    assert RAW_BODY not in rendered
    assert "raw_body_stored" in rendered
    _assert_no_unsafe_true_grants(read_model)


def test_missing_consumer_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "workflow_package_request_consumer_status.json", {"status": "NOT_READY"})

    read_model = dlq.build_read_model(
        read_model_root=root,
        sqlite_path=tmp_path / "dead_letter_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "DEAD_LETTER_QUEUE_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_sqlite_local_bridge_equal_and_wiki(tmp_path):
    result = dlq.export_dead_letter_queue(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "system_knowledge" / "dead_letter_queue.sqlite",
        wiki_path=tmp_path / "wiki" / "Dead Letter Queue.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "No retries are executed" in wiki
    conn = sqlite3.connect(result["sqlite_path"])
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM dead_letters").fetchone()[0]
    finally:
        conn.close()
    assert row_count == local["dead_letter_count"]
    assert result["status"] == "DEAD_LETTER_QUEUE_READY"
    _assert_no_unsafe_true_grants(local)
