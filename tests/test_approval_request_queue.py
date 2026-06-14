import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import approval_request_queue as queue


FIXED_NOW = "2026-06-03T13:15:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "gate_decision_ledger.json", {"status": "GATE_DECISION_LEDGER_READY"})
    _write_json(
        root / "workroom_review_decision_contract.json",
        {"status": "WORKROOM_REVIEW_DECISION_CONTRACT_READY"},
    )
    _write_json(root / "operator_next_decision.json", {"status": "READY"})
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
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "business_action_performed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_builds_central_approval_queue(tmp_path):
    read_model = queue.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "approval_request_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "APPROVAL_REQUEST_QUEUE_READY"
    actions = {request["requested_action"]: request for request in read_model["approval_requests"]}
    assert {
        "approve_review_packet_for_record",
        "request_review_packet_rework",
        "approve_email_draft_send",
        "approve_coupa_submit",
        "approve_workbook_mutation",
        "approve_pdf_export",
        "approve_ledger_post",
    } == set(actions)
    assert actions["approve_email_draft_send"]["owner_speaker_ref"] == "guardian"
    assert actions["approve_coupa_submit"]["status"] == "pending"
    assert actions["approve_ledger_post"]["business_action_performed"] is False
    assert "send_email" in actions["approve_email_draft_send"]["forbidden_options"]
    assert all(request["safe_options"] for request in read_model["approval_requests"])
    _assert_no_unsafe_true_grants(read_model)


def test_operator_next_decision_ready_status_is_accepted(tmp_path):
    read_model = queue.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "approval_request_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    observed = {
        row["precondition_ref"]: row
        for row in read_model["preconditions"]
    }["operator_next_decision"]
    assert observed["observed_status"] == "READY"
    assert observed["ready"] is True


def test_missing_gate_decision_ledger_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "gate_decision_ledger.json", {"status": "NOT_READY"})

    read_model = queue.build_read_model(
        read_model_root=root,
        sqlite_path=tmp_path / "approval_request_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "APPROVAL_REQUEST_QUEUE_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_sqlite_local_bridge_equal_and_wiki(tmp_path):
    result = queue.export_approval_request_queue(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "system_knowledge" / "approval_request_queue.sqlite",
        wiki_path=tmp_path / "wiki" / "Approval Request Queue.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "does not execute approvals" in wiki
    conn = sqlite3.connect(result["sqlite_path"])
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0]
    finally:
        conn.close()
    assert row_count == local["approval_request_count"]
    assert result["status"] == "APPROVAL_REQUEST_QUEUE_READY"
    _assert_no_unsafe_true_grants(local)
