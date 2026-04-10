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


def test_run_outreach_draft_uses_broker_logs_and_notifies(tmp_path, monkeypatch):
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
        return {"ok": True, "data": {"draft_id": "d1", "message_id": "m1"}, "error": ""}

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    results = outreach.run_outreach(dry_run=False, mode="draft")

    assert len(results) == 3
    assert all(row["status"] == "draft" for row in results)
    assert len(broker_calls) == 3
    assert all(call[1] == "google.gmail.draft.create" for call in broker_calls)
    assert all(call[2]["cc"] == outreach.get_review_inbox() for call in broker_calls)
    assert len(sent_messages) == 3
    assert "Draper Placeholder" in sent_messages[0]
    assert all(json.loads(line)["status"] == "draft" for line in log_path.read_text(encoding="utf-8").splitlines())


def test_run_outreach_draft_uses_configured_review_inbox(tmp_path, monkeypatch):
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

    broker_calls = []

    monkeypatch.setenv("CASSANDRA_EMAIL_REVIEW_INBOX", "winshipwheatley@gmail.com")
    monkeypatch.setattr(outreach, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(outreach, "_OUTREACH_LOG", log_path, raising=False)
    monkeypatch.setattr(outreach, "_notify_winship", lambda text: None, raising=False)

    def fake_broker(agent, capability, params):
        broker_calls.append((agent, capability, params))
        return {"ok": True, "data": {"draft_id": "d1", "message_id": "m1"}, "error": ""}

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    outreach.run_outreach(dry_run=False, mode="draft")

    assert broker_calls
    assert all(call[2]["cc"] == "winshipwheatley@gmail.com" for call in broker_calls)


def test_run_outreach_uses_pinned_email_when_contacts_returns_no_match(tmp_path, monkeypatch):
    import cassandra_outreach as outreach

    nicknames_path = tmp_path / "contact_nicknames.json"
    log_path = tmp_path / "cassandra_outreach.jsonl"
    nicknames_path.write_text(
        json.dumps(
            {
                "dad": {"name": "Dad Placeholder", "pinned_email": "dad@example.com"},
                "mom": {"name": "Mom Placeholder", "pinned_email": "mom@example.com"},
                "draper": {"name": "Draper Placeholder", "pinned_email": "draper@example.com"},
            }
        ),
        encoding="utf-8",
    )

    broker_calls = []
    monkeypatch.setattr(outreach, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(outreach, "_OUTREACH_LOG", log_path, raising=False)
    monkeypatch.setattr(outreach, "_notify_winship", lambda text: None, raising=False)

    def fake_broker(agent, capability, params):
        broker_calls.append((agent, capability, params))
        if capability == "google.contacts.read":
            return {"ok": True, "data": [], "error": ""}
        if capability == "google.gmail.draft.create":
            return {"ok": True, "data": {"draft_id": "d1", "message_id": "m1"}, "error": ""}
        raise AssertionError(f"unexpected capability {capability}")

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    results = outreach.run_outreach(dry_run=False, mode="draft")

    assert len(results) == 3
    draft_calls = [call for call in broker_calls if call[1] == "google.gmail.draft.create"]
    assert len(draft_calls) == 3
    assert draft_calls[0][2]["to"] == "draper@example.com"
    assert draft_calls[1][2]["to"] == "dad@example.com"
    assert draft_calls[2][2]["to"] == "mom@example.com"


def test_run_outreach_rejects_send_mode(tmp_path, monkeypatch):
    import cassandra_outreach as outreach

    nicknames_path = tmp_path / "contact_nicknames.json"
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
    monkeypatch.setattr(outreach, "_NICKNAMES_PATH", nicknames_path, raising=False)

    try:
        outreach.run_outreach(dry_run=False, mode="send")
    except RuntimeError as exc:
        assert "draft-only" in str(exc)
    else:
        raise AssertionError("send mode should be rejected for the pilot")


def test_cassandra_handle_routes_intro_email_request(monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(
        "cassandra_outreach.run_outreach",
        lambda dry_run=False, mode="draft": [
            {"nickname": "draper", "display_name": "Draper", "status": "draft"},
            {"nickname": "dad", "display_name": "Dad", "status": "draft"},
            {"nickname": "mom", "display_name": "Mom", "status": "draft"},
        ],
    )
    monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *args, **kwargs: None, raising=False)

    replies = cassandra_brain.handle("send the intro emails")

    assert replies == ["Intro email drafts prepared for Draper, Dad, Mom."]


def test_cassandra_contact_gap_detection_queues_upgrade_and_followup(tmp_path, monkeypatch):
    import cassandra_brain

    nicknames_path = tmp_path / "contact_nicknames.json"
    tasks_dir = tmp_path / "tasks"
    archive_dir = tmp_path / "archive"
    followup_log = tmp_path / "cassandra_pending_followups.jsonl"
    tasks_dir.mkdir()
    archive_dir.mkdir()
    nicknames_path.write_text(
        json.dumps({"dad": {"name": "Dad", "telegram_chat_id": 42}}),
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
    monkeypatch.setattr(cassandra_brain, "_detect_file_verify_intent", lambda text: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_detect_payment_verify_intent", lambda text: False, raising=False)
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


def test_cassandra_followup_processor_creates_email_draft_for_email_origin(tmp_path, monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)

    followup_log = tmp_path / "cassandra_pending_followups.jsonl"
    archive_dir = tmp_path / "archive"
    nicknames_path = tmp_path / "contact_nicknames.json"
    archive_dir.mkdir()
    nicknames_path.write_text(
        json.dumps(
            {
                "dad": {
                    "name": "Dad",
                    "tier": "inner_circle",
                    "pinned_email": "dad@example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    record = {
        "timestamp": "2026-03-31T00:00:00",
        "sender_name": "Dad",
        "sender_chat_id": None,
        "sender_channel": "email",
        "sender_email": "dad@example.com",
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

    broker_calls = []
    telegram_sent = []
    monkeypatch.setattr(cassandra_brain, "_FOLLOWUP_LOG", followup_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_ARCHIVE", archive_dir, raising=False)
    monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "handle",
        lambda text, session=None: ["That file is present now."],
        raising=False,
    )
    monkeypatch.setattr(cassandra_brain, "_capability_flag_value", lambda flag_name: True, raising=False)
    monkeypatch.setattr(cassandra_brain, "get_review_inbox", lambda: "review@example.com", raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_review_grounded_email_draft",
        lambda **kwargs: {
            "status": "allowed",
            "subject": kwargs["draft_subject"],
            "body": kwargs["draft_body"],
            "detail": "",
            "queued_task_name": None,
            "user_reply": "",
        },
        raising=False,
    )

    def fake_broker(agent, capability, payload):
        broker_calls.append((agent, capability, payload))
        return {"ok": True, "data": {"draft_id": "d1", "message_id": "m1", "thread_id": "t1"}, "error": ""}

    monkeypatch.setattr(cassandra_brain, "broker_call", fake_broker, raising=False)
    monkeypatch.setattr("cassandra_sender.send_message", lambda text, chat_id=None: telegram_sent.append((text, chat_id)))

    completed = cassandra_brain.process_pending_followups()

    assert len(completed) == 1
    assert telegram_sent == []
    assert len(broker_calls) == 1
    assert broker_calls[0][1] == "google.gmail.draft.create"
    assert broker_calls[0][2]["to"] == "dad@example.com"
    assert broker_calls[0][2]["cc"] == "review@example.com"
    assert broker_calls[0][2]["subject"].startswith("Follow-up:")
    assert broker_calls[0][2]["body"] == "That file is present now."
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
        json.dumps({"dad": {"name": "Dad", "telegram_chat_id": 42}}),
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

    assert len(replies) == 1
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


def test_verify_sender_on_channel_accepts_pinned_email_without_name_match(tmp_path, monkeypatch):
    import cassandra_brain

    nicknames_path = tmp_path / "contact_nicknames.json"
    nicknames_path.write_text(
        json.dumps(
            {
                "dad": {
                    "name": "Dad",
                    "tier": "inner_circle",
                    "pinned_email": "dad@example.com",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)

    contact = cassandra_brain.verify_sender_on_channel(
        sender_name="Different Display Name",
        sender_id="DAD@example.com",
        channel="email",
    )

    assert contact is not None
    assert contact["nickname"] == "dad"


def test_handle_surfaces_pinned_inner_circle_email_reply_summary(tmp_path, monkeypatch):
    import cassandra_brain

    nicknames_path = tmp_path / "contact_nicknames.json"
    bridge_log = tmp_path / "cassandra_email_bridge.jsonl"
    analysis_log = tmp_path / "cassandra_email_thread_analysis.jsonl"
    thread_state = tmp_path / "cassandra_email_thread_state.json"
    correspondence_log = tmp_path / "cassandra_correspondence.jsonl"
    nicknames_path.write_text(
        json.dumps(
            {
                "dad": {
                    "name": "Dad",
                    "tier": "inner_circle",
                    "pinned_email": "dad@example.com",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_BRIDGE_LOG", bridge_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_THREAD_ANALYSIS_LOG", analysis_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_THREAD_STATE", thread_state, raising=False)
    monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", correspondence_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *args, **kwargs: None, raising=False)
    correspondence_log.write_text(
        json.dumps(
            {
                "ts": "2026-04-05 08:45:00",
                "recipient": "Dad",
                "recipient_email": "dad@example.com",
                "state": "draft",
                "subject": "Hilton deposit",
                "thread_id": "t1",
                "route": "email_send",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_broker(agent, capability, params):
        if capability == "google.gmail.read.metadata":
            return {
                "ok": True,
                "data": [
                    {
                        "message_id": "m1",
                        "thread_id": "t1",
                        "from_name": "Different Display Name",
                        "from_email": "dad@example.com",
                        "subject": "Re: Hilton deposit",
                        "date_raw": "Sun, 05 Apr 2026 09:00:00 -0400",
                        "in_reply_to": "<msg-0@example.com>",
                        "references": "",
                        "labels": ["INBOX", "UNREAD"],
                        "snippet": "Did the Hilton payment come through yet?",
                    },
                    {
                        "message_id": "m2",
                        "thread_id": "t2",
                        "from_name": "Outsider",
                        "from_email": "outsider@example.com",
                        "subject": "Re: Random",
                        "date_raw": "Sun, 05 Apr 2026 08:00:00 -0400",
                        "in_reply_to": "<msg-1@example.com>",
                        "references": "",
                        "labels": ["INBOX", "UNREAD"],
                        "snippet": "Hello there",
                    },
                    {
                        "message_id": "m3",
                        "thread_id": "t3",
                        "from_name": "Dad",
                        "from_email": "dad@example.com",
                        "subject": "Checking in",
                        "date_raw": "Sun, 05 Apr 2026 07:00:00 -0400",
                        "in_reply_to": "",
                        "references": "",
                        "labels": ["INBOX"],
                        "snippet": "Not a reply thread",
                    },
                ],
                "error": "",
            }
        assert capability == "google.gmail.read.body"
        return {
            "ok": True,
            "data": {
                "thread_id": "t1",
                "messages": [
                    {
                        "message_id": "m1",
                        "thread_id": "t1",
                        "from_name": "Different Display Name",
                        "from_email": "dad@example.com",
                        "subject": "Re: Hilton deposit",
                        "date_raw": "Sun, 05 Apr 2026 09:00:00 -0400",
                        "internal_date": "1712322000000",
                        "body_text": "Did the Hilton payment come through yet?",
                        "snippet": "Did the Hilton payment come through yet?",
                    },
                    {
                        "message_id": "m4",
                        "thread_id": "t1",
                        "from_name": "Winship",
                        "from_email": "winship@example.com",
                        "subject": "Re: Hilton deposit",
                        "date_raw": "Sun, 05 Apr 2026 10:00:00 -0400",
                        "internal_date": "1712325600000",
                        "body_text": "The Hilton payment has not come through yet.",
                        "snippet": "The Hilton payment has not come through yet.",
                    },
                ],
            },
            "error": "",
        }

    monkeypatch.setattr(cassandra_brain, "broker_call", fake_broker, raising=False)

    replies = cassandra_brain.handle(
        "check inner circle email replies",
        {"sender_name": "Winship", "sender_chat_id": 99, "skip_followup_check": True},
    )

    assert len(replies) == 1
    assert "I found 1 pinned inner-circle email reply" in replies[0]
    assert "Dad — allowed lane, unread." in replies[0]
    assert "Subject: Re: Hilton deposit" in replies[0]
    assert "Linked thread: draft via thread_id" in replies[0]
    assert "Answered in thread: Did the Hilton payment come through yet?" in replies[0]
    assert "safe to route through the normal draft-review flow" in replies[0]

    log_entries = [json.loads(line) for line in bridge_log.read_text(encoding="utf-8").splitlines()]
    assert len(log_entries) == 1
    assert log_entries[0]["message_id"] == "m1"
    assert log_entries[0]["status"] == "admitted"
    assert log_entries[0]["lane"] == "allowed"
    analysis_entries = [json.loads(line) for line in analysis_log.read_text(encoding="utf-8").splitlines()]
    assert analysis_entries[0]["reply_round"] == 1
    assert analysis_entries[0]["linked_outbound"]["thread_id"] == "t1"
    assert analysis_entries[0]["question_bundles"][0]["status"] == "answered_in_thread"


def test_handle_marks_caution_email_reply_for_review(tmp_path, monkeypatch):
    import cassandra_brain

    nicknames_path = tmp_path / "contact_nicknames.json"
    bridge_log = tmp_path / "cassandra_email_bridge.jsonl"
    analysis_log = tmp_path / "cassandra_email_thread_analysis.jsonl"
    thread_state = tmp_path / "cassandra_email_thread_state.json"
    nicknames_path.write_text(
        json.dumps(
            {
                "mom": {
                    "name": "Mom",
                    "tier": "inner_circle",
                    "pinned_email": "mom@example.com",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_BRIDGE_LOG", bridge_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_THREAD_ANALYSIS_LOG", analysis_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_THREAD_STATE", thread_state, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "broker_call",
        lambda agent, capability, params: (
            {
                "ok": True,
                "data": [
                    {
                        "message_id": "m10",
                        "thread_id": "t10",
                        "from_name": "Mom",
                        "from_email": "mom@example.com",
                        "subject": "Re: Hilton pay",
                        "date_raw": "Sun, 05 Apr 2026 10:00:00 -0400",
                        "in_reply_to": "<msg-9@example.com>",
                        "references": "",
                        "labels": ["INBOX", "UNREAD"],
                        "snippet": "How much did the Hilton gig pay?",
                    }
                ],
                "error": "",
            }
            if capability == "google.gmail.read.metadata"
            else {
                "ok": True,
                "data": {
                    "thread_id": "t10",
                    "messages": [
                        {
                            "message_id": "m10",
                            "thread_id": "t10",
                            "from_name": "Mom",
                            "from_email": "mom@example.com",
                            "subject": "Re: Hilton pay",
                            "date_raw": "Sun, 05 Apr 2026 10:00:00 -0400",
                            "internal_date": "1712325600000",
                            "body_text": "How much did the Hilton gig pay?",
                            "snippet": "How much did the Hilton gig pay?",
                        }
                    ],
                },
                "error": "",
            }
        ),
        raising=False,
    )

    replies = cassandra_brain.handle(
        "check inner circle email replies",
        {"sender_name": "Winship", "sender_chat_id": 99, "skip_followup_check": True},
    )

    assert "Mom — caution lane, unread." in replies[0]
    assert "Needs Winship review: How much did the Hilton gig pay?" in replies[0]
    assert "I held that for Winship review." in replies[0]

    log_entries = [json.loads(line) for line in bridge_log.read_text(encoding="utf-8").splitlines()]
    assert log_entries[0]["status"] == "held"
    assert log_entries[0]["lane"] == "caution"
    analysis_entries = [json.loads(line) for line in analysis_log.read_text(encoding="utf-8").splitlines()]
    assert analysis_entries[0]["question_bundles"][0]["status"] == "needs_winship_review"
