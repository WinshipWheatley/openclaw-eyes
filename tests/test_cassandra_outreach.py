import json
from pathlib import Path


def test_run_outreach_dry_run_builds_three_personalized_emails(tmp_path, monkeypatch):
    import cassandra_outreach as outreach

    nicknames_path = tmp_path / "contact_nicknames.json"
    log_path = tmp_path / "cassandra_outreach.jsonl"
    nicknames_path.write_text(
        json.dumps(
            {
                "dad": "Dad Placeholder",
                "mom": "Mom Placeholder",
                "draper": "Draper Placeholder",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(outreach, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(outreach, "_OUTREACH_LOG", log_path, raising=False)

    results = outreach.run_outreach(dry_run=True)

    assert [row["nickname"] for row in results] == ["draper", "dad", "mom"]
    assert all(row["status"] == "dry_run" for row in results)
    assert "Work-related stuff is fair game too" in results[0]["body"]
    assert "Financial questions are welcome too" in results[1]["body"]
    assert "warm hello and a real-world test" in results[2]["body"]
    assert not log_path.exists()


def test_run_outreach_send_uses_broker_logs_and_notifies(tmp_path, monkeypatch):
    import cassandra_outreach as outreach

    nicknames_path = tmp_path / "contact_nicknames.json"
    log_path = tmp_path / "cassandra_outreach.jsonl"
    nicknames_path.write_text(
        json.dumps(
            {
                "dad": {"name": "Dad Placeholder", "email": "dad@example.com"},
                "mom": {"name": "Mom Placeholder", "email": "mom@example.com"},
                "draper": {"name": "Draper Placeholder", "email": "draper@example.com"},
            }
        ),
        encoding="utf-8",
    )

    sent_messages = []
    broker_calls = []

    monkeypatch.setattr(outreach, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(outreach, "_OUTREACH_LOG", log_path, raising=False)
    monkeypatch.setattr(outreach, "_notify_winship", sent_messages.append, raising=False)

    def fake_broker(agent, capability, params):
        broker_calls.append((agent, capability, params))
        return {"ok": True, "data": {"message_id": "m1"}, "error": ""}

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    results = outreach.run_outreach(dry_run=False)

    assert len(results) == 3
    assert all(row["status"] == "sent" for row in results)
    assert len(broker_calls) == 3
    assert all(call[1] == "google.gmail.send" for call in broker_calls)
    assert len(sent_messages) == 3
    assert "Draper Placeholder" in sent_messages[0]
    assert all(json.loads(line)["status"] == "sent" for line in log_path.read_text(encoding="utf-8").splitlines())


def test_cassandra_handle_routes_intro_email_request(monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(
        "cassandra_outreach.run_outreach",
        lambda dry_run=False: [
            {"nickname": "draper", "display_name": "Draper", "status": "sent"},
            {"nickname": "dad", "display_name": "Dad", "status": "sent"},
            {"nickname": "mom", "display_name": "Mom", "status": "sent"},
        ],
    )

    replies = cassandra_brain.handle("send the intro emails")

    assert replies == ["Intro emails sent to Draper, Dad, Mom."]


def test_cassandra_contact_gap_detection_queues_upgrade_and_followup(tmp_path, monkeypatch):
    import cassandra_brain

    nicknames_path = tmp_path / "contact_nicknames.json"
    tasks_dir = tmp_path / "tasks"
    archive_dir = tmp_path / "archive"
    followup_log = tmp_path / "cassandra_pending_followups.jsonl"
    tasks_dir.mkdir()
    archive_dir.mkdir()
    nicknames_path.write_text(
        json.dumps({"dad": {"name": "Dad"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_TASKS_DIR", tasks_dir, raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_ARCHIVE", archive_dir, raising=False)
    monkeypatch.setattr(cassandra_brain, "_FOLLOWUP_LOG", followup_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "build_context_snapshot", lambda state=None: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda query: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda query: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda query: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda prompt, deep, cloud_ok=False: "I can't verify that file from here.",
        raising=False,
    )

    replies = cassandra_brain.handle(
        "Can you check whether that file exists?",
        {"sender_name": "Dad", "sender_chat_id": 42},
    )

    assert len(replies) == 1
    assert "I can't verify that file from here." in replies[0]
    assert "I'll follow up when I can." in replies[0]
    task_files = list(tasks_dir.glob("cas-upgrade-file_verify-*.md"))
    assert len(task_files) == 1
    records = [json.loads(line) for line in followup_log.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["status"] == "pending"
    assert records[0]["gap_type"] == "file_verify"
    assert records[0]["sender_name"] == "Dad"


def test_cassandra_followup_processor_replies_when_upgrade_is_archived(tmp_path, monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)

    followup_log = tmp_path / "cassandra_pending_followups.jsonl"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    record = {
        "timestamp": "2026-03-31T00:00:00",
        "sender_name": "Dad",
        "sender_chat_id": 42,
        "original_message": "Can you check whether that file exists?",
        "partial_reply_sent": "Partial",
        "gap_type": "file_verify",
        "upgrade_task_name": "cas-upgrade-file_verify-20260331T000000",
        "status": "pending",
    }
    followup_log.write_text(json.dumps(record) + "\n", encoding="utf-8")
    (archive_dir / "closeout_cas-upgrade-file_verify-20260331T000000_20260331T010000.ok").write_text(
        "done",
        encoding="utf-8",
    )

    sent = []
    monkeypatch.setattr(cassandra_brain, "_FOLLOWUP_LOG", followup_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_ARCHIVE", archive_dir, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "handle",
        lambda text, session=None: ["That file is present now."],
        raising=False,
    )
    monkeypatch.setattr(cassandra_brain, "_capability_flag_value", lambda flag_name: True, raising=False)
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-token")
    monkeypatch.setenv("CASSANDRA_CHAT_ID", "0")
    monkeypatch.setattr("cassandra_sender.send_message", lambda text, chat_id=None: sent.append((text, chat_id)))

    completed = cassandra_brain.process_pending_followups()

    assert len(completed) == 1
    assert sent == [("That file is present now.", 42)]
    updated = [json.loads(line) for line in followup_log.read_text(encoding="utf-8").splitlines()]
    assert updated[0]["status"] == "completed"
    assert updated[0]["followup_reply_sent"] == "That file is present now."


def test_cassandra_gap_followup_is_not_used_for_non_designated_sender(tmp_path, monkeypatch):
    import cassandra_brain

    nicknames_path = tmp_path / "contact_nicknames.json"
    tasks_dir = tmp_path / "tasks"
    followup_log = tmp_path / "cassandra_pending_followups.jsonl"
    tasks_dir.mkdir()
    nicknames_path.write_text(
        json.dumps({"dad": {"name": "Dad"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_TASKS_DIR", tasks_dir, raising=False)
    monkeypatch.setattr(cassandra_brain, "_FOLLOWUP_LOG", followup_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "build_context_snapshot", lambda state=None: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda query: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda query: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda query: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda prompt, deep, cloud_ok=False: "I can't verify that file from here.",
        raising=False,
    )

    replies = cassandra_brain.handle(
        "Can you check whether that file exists?",
        {"sender_name": "Winship", "sender_chat_id": 99},
    )

    assert replies == ["I can't verify that file from here."]
    assert list(tasks_dir.glob("cas-upgrade-file_verify-*.md")) == []
    assert not followup_log.exists()


def test_designated_contact_lookup_matches_name_or_chat_id(tmp_path, monkeypatch):
    import cassandra_brain

    nicknames_path = tmp_path / "contact_nicknames.json"
    nicknames_path.write_text(
        json.dumps(
            {
                "dad": {"name": "Dad", "telegram_chat_id": 42},
                "mom": {"name": "Mom"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)

    assert cassandra_brain.is_designated_contact_sender(sender_name="Dad", sender_chat_id=None) is True
    assert cassandra_brain.is_designated_contact_sender(sender_name="Unknown", sender_chat_id=42) is True
    assert cassandra_brain.is_designated_contact_sender(sender_name="Winship", sender_chat_id=99) is False
