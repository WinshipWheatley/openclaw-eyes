import json
import sqlite3


def test_pending_followup_inspection_returns_counts_not_message_text(tmp_path):
    import cassandra_send_status_dry_run as dry_run

    path = tmp_path / "followups.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"status": "pending", "original_message": "private body"}),
                json.dumps({"status": "completed", "followup_reply_sent": "private reply"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = dry_run.inspect_pending_followups(path)

    assert report["pending_count"] == 1
    assert report["total_count"] == 2
    assert report["raw_message_text_returned"] is False
    assert "private body" not in json.dumps(report)


def test_future_action_inspection_returns_counts_not_request_text_or_chat_ids(tmp_path):
    import cassandra_send_status_dry_run as dry_run

    db_path = tmp_path / "future_actions.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE future_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_text TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                chat_id TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO future_actions (request_text, due_at, status, chat_id, created_at) VALUES (?, ?, ?, ?, ?)",
            ("private reminder text", "2026-05-17T08:00:00", "pending", "123456", "2026-05-17T07:00:00"),
        )

    report = dry_run.inspect_future_actions(db_path, now_iso="2026-05-17T09:00:00")

    assert report["pending_count"] == 1
    assert report["due_count"] == 1
    assert report["request_text_returned"] is False
    assert report["chat_ids_returned"] is False
    assert "private reminder text" not in json.dumps(report)
    assert "123456" not in json.dumps(report)


def test_status_read_model_shape_blocks_all_delivery(monkeypatch):
    import cassandra_send_status_dry_run as dry_run

    monkeypatch.setattr(
        dry_run,
        "inspect_pending_followups",
        lambda path=dry_run.FOLLOWUP_LOG_PATH: {
            "pending_count": 2,
            "total_count": 3,
            "raw_message_text_returned": False,
            "delivery_blocked": True,
        },
    )
    monkeypatch.setattr(
        dry_run,
        "inspect_future_actions",
        lambda db_path=dry_run.FUTURE_ACTION_DB_PATH, now_iso=None: {
            "pending_count": 1,
            "due_count": 1,
            "request_text_returned": False,
            "chat_ids_returned": False,
            "dispatch_blocked": True,
        },
    )
    monkeypatch.setattr(
        dry_run,
        "inspect_briefing_scheduler",
        lambda: {
            "due_slots": ["morning"],
            "due_count": 1,
            "pending_count": 0,
            "telegram_delivery_blocked": True,
            "voice_delivery_blocked": True,
            "raw_briefing_text_returned": False,
        },
    )

    payload = dry_run.build_status_read_model(generated_at="2026-05-17T13:00:00+00:00")

    assert payload["schema_version"] == "cassandra_send_status_dry_run_v0"
    assert payload["runtime_authority_changed"] is False
    assert payload["send_authority_added"] is False
    assert payload["real_telegram_send_triggered"] is False
    assert payload["real_gmail_or_email_send_triggered"] is False
    assert payload["real_briefing_delivery_triggered"] is False
    assert payload["real_voice_delivery_triggered"] is False
    assert payload["niles_used_for_cassandra_path"] is False
    assert payload["services"]["watcher"]["advanced_beyond_startup_guard"] is True
    assert payload["services"]["briefing_scheduler"]["advanced_beyond_startup_guard"] is True

    watcher_fired = payload["services"]["watcher"]["would_have_fired"]
    assert watcher_fired["pending_followup_processing"]["would_run_if_real_mode"] is True
    assert watcher_fired["future_action_dispatch"]["would_run_if_real_mode"] is True
    assert watcher_fired["email_gmail_polling"]["blocked_in_dry_run"] is True

    scheduler_fired = payload["services"]["briefing_scheduler"]["would_have_fired"]
    assert scheduler_fired["briefing_generation"]["would_run_if_real_mode"] is True
    assert scheduler_fired["telegram_briefing_delivery"]["blocked_in_dry_run"] is True
    assert scheduler_fired["voice_briefing_delivery"]["blocked_in_dry_run"] is True
