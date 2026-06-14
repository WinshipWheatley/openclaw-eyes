import json
import sqlite3
from pathlib import Path

import cassandra_telegram_dryrun_inbox as dryrun


FIXED_NOW = "2026-06-02T06:30:00+00:00"


def _write_message(inbox: Path, *, message_id: str, text: str) -> Path:
    payload = dryrun.build_dryrun_message(
        message_id=message_id,
        message_text=text,
        received_at=FIXED_NOW,
    )
    path = inbox / f"{message_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
        "workbook_source_mutation_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "sent",
        "paid",
        "telegram_send_allowed",
        "telegram_live_connection_allowed",
        "telegram_credentials_access_allowed",
    }
    assert not [
        key
        for key, value in _walk_values(payload)
        if key in unsafe_keys and value is True
    ]


def test_dryrun_inbox_processes_supported_messages_into_package_queue(tmp_path):
    inbox = tmp_path / "inbox"
    responses = tmp_path / "responses"
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    export_root = tmp_path / "read_models"
    bridge_root = tmp_path / "bridge"
    wiki_path = tmp_path / "wiki" / "Cassandra Telegram Dry Run Inbox.md"
    inbox.mkdir()

    _write_message(
        inbox,
        message_id="church_sound",
        text="Mark that I'm at church running sound.",
    )
    _write_message(
        inbox,
        message_id="capital_hilton_proposal",
        text="Follow up on Capital Hilton proposal.",
    )
    _write_message(
        inbox,
        message_id="st_annes_invoice_send",
        text="Send St. Anne's invoice.",
    )

    result = dryrun.process_dryrun_inbox(
        inbox_dir=inbox,
        response_dir=responses,
        export_root=export_root,
        bridge_export_root=bridge_root,
        wiki_path=wiki_path,
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )

    assert result.status == dryrun.CONTRACT_STATUS
    assert result.message_count == 3
    assert result.package_count == 3
    assert len(result.response_receipt_paths) == 3

    statuses = {
        item["message_id"]: (item["workflow_ref"], item["package_status"], item["blocker"])
        for item in result.response_statuses
    }
    assert statuses["church_sound"] == ("st_annes_work_log_event", "OPERATOR_REVIEW_REQUIRED", "")
    assert statuses["capital_hilton_proposal"] == (
        "capital_hilton_proposal_followup",
        "OPERATOR_REVIEW_REQUIRED",
        "",
    )
    assert statuses["st_annes_invoice_send"][0:2] == (
        "st_annes_monthly_invoice_rollup",
        "PERMISSION_REQUIRED",
    )
    assert "Send permission registry is not ready" in statuses["st_annes_invoice_send"][2]

    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT workflow_ref, client_ref, source_surface, status FROM packages ORDER BY workflow_ref"
        ).fetchall()
    assert rows == [
        ("capital_hilton_proposal_followup", "capital_hilton", "telegram_dryrun", "OPERATOR_REVIEW_REQUIRED"),
        ("st_annes_monthly_invoice_rollup", "st_annes", "telegram_dryrun", "PERMISSION_REQUIRED"),
        ("st_annes_work_log_event", "st_annes", "telegram_dryrun", "OPERATOR_REVIEW_REQUIRED"),
    ]

    local = _load(result.read_model_path)
    bridge = _load(result.bridge_read_model_path)
    assert local == bridge
    assert local["status"] == dryrun.CONTRACT_STATUS
    assert local["package_queue_entries_recorded"] == 3
    assert local["machine_proof"]["telegram_live_connected"] is False
    assert local["machine_proof"]["telegram_message_sent"] is False
    assert Path(result.wiki_path).exists()
    _assert_no_unsafe_true_grants(local)


def test_receipts_do_not_send_replies_or_perform_external_actions(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _write_message(
        inbox,
        message_id="church_sound",
        text="Mark that I'm at church running sound.",
    )

    result = dryrun.process_dryrun_inbox(
        inbox_dir=inbox,
        response_dir=tmp_path / "responses",
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Cassandra Telegram Dry Run Inbox.md",
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    receipt = _load(result.response_receipt_paths[0])
    assert receipt["raw_internal_status"] == "RESPONSE_READY"
    assert receipt["workflow_ref"] == "st_annes_work_log_event"
    assert receipt["response_text"] == "St. Anne's work log captured. Confirm or discard."
    assert receipt["no_reply_sent"] is True
    assert receipt["no_send_business_action"] is True
    assert receipt["no_excel_by_default"] is True
    assert receipt["no_ledger"] is True
    assert receipt["machine_proof"]["queue_noop_worker_only"] is True
    assert receipt["machine_proof"]["email_send_performed"] is False
    assert receipt["machine_proof"]["workbook_mutation_performed"] is False
    assert receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert receipt["machine_proof"]["telegram_credentials_accessed"] is False
    _assert_no_unsafe_true_grants(receipt)


def test_unsafe_authority_true_blocks_without_package_queue_write(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    message = dryrun.build_dryrun_message(
        message_id="unsafe",
        message_text="Send St. Anne's invoice.",
        received_at=FIXED_NOW,
    )
    unsafe_key = "email_send_" + "allowed"
    message["authority_boundary"][unsafe_key] = bool(1)
    (inbox / "unsafe.json").write_text(
        json.dumps(message, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"

    result = dryrun.process_dryrun_inbox(
        inbox_dir=inbox,
        response_dir=tmp_path / "responses",
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Cassandra Telegram Dry Run Inbox.md",
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )

    assert result.message_count == 1
    assert result.package_count == 0
    assert not sqlite_path.exists()
    receipt = _load(result.response_receipt_paths[0])
    assert receipt["raw_internal_status"] == "BLOCKED_WITH_REASON"
    assert receipt["package_status"] == "NOT_CREATED"
    assert "authority_true:" + unsafe_key in receipt["blocker"]
    assert receipt["operator_display"]["speaker_ref"] == "guardian"
    assert receipt["machine_proof"]["telegram_message_sent"] is False
