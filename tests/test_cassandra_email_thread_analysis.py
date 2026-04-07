import json
import os
import sys
from datetime import datetime


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_analyze_email_thread_queues_grounded_capability_gap(tmp_path, monkeypatch):
    import cassandra_brain

    tasks_dir = tmp_path / "tasks"
    archive_dir = tmp_path / "archive"
    analysis_log = tmp_path / "analysis.jsonl"
    thread_state = tmp_path / "thread_state.json"
    tasks_dir.mkdir()
    archive_dir.mkdir()

    monkeypatch.setattr(cassandra_brain, "_POLISH_TASKS_DIR", tasks_dir, raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_ARCHIVE", archive_dir, raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_STATUS", tmp_path / "status.json", raising=False)
    monkeypatch.setattr(cassandra_brain, "_POLISH_TASK_FILE", tmp_path / "task.md", raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_THREAD_ANALYSIS_LOG", analysis_log, raising=False)
    monkeypatch.setattr(cassandra_brain, "_EMAIL_THREAD_STATE", thread_state, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_fetch_email_thread_messages",
        lambda message: (
            [
                {
                    "message_id": "m1",
                    "thread_id": "t-gap",
                    "from_name": "Dad",
                    "from_email": "dad@example.com",
                    "subject": "Re: file check",
                    "date_raw": "Sun, 05 Apr 2026 09:00:00 -0400",
                    "internal_date": "1712322000000",
                    "body_text": "Can you check whether that file exists?",
                    "snippet": "Can you check whether that file exists?",
                }
            ],
            "gmail.read.body",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_capability_flag_value",
        lambda flag_name: False if flag_name == "FILE_VERIFY_CONNECTED" else True,
        raising=False,
    )

    analysis = cassandra_brain._analyze_inner_circle_email_thread(
        {
            "message_id": "m1",
            "thread_id": "t-gap",
            "from_name": "Dad",
            "from_email": "dad@example.com",
            "subject": "Re: file check",
            "snippet": "Can you check whether that file exists?",
        },
        {
            "nickname": "dad",
            "display_name": "Dad",
        },
    )

    assert analysis["question_bundles"][0]["status"] == "needs_capability"
    task_files = list(tasks_dir.glob("cas-upgrade-file_verify-*.md"))
    assert len(task_files) == 1
    task_text = task_files[0].read_text(encoding="utf-8")
    assert "Inbound email thread id: t-gap" in task_text
    assert "Grounded unanswered question: Can you check whether that file exists?" in task_text


def test_predict_likely_next_questions_uses_grounded_next_step(monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain,
        "get_finance_status_answer",
        lambda query: "Capital Hilton payment is not in motion yet. Next: Upload the SmartSpend invoice.",
        raising=False,
    )

    predictions = cassandra_brain._predict_likely_next_questions(
        [
            {
                "bundle_id": "b1",
                "question": "Did the Hilton payment come through yet?",
            }
        ]
    )

    assert predictions == [
        {
            "question": "What needs to happen next?",
            "because": "Upload the SmartSpend invoice.",
            "bundle_id": "b1",
        }
    ]


def test_advance_email_thread_cadence_parks_after_bounded_followup(tmp_path, monkeypatch):
    import cassandra_brain

    thread_state = tmp_path / "thread_state.json"
    monkeypatch.setattr(cassandra_brain, "_EMAIL_THREAD_STATE", thread_state, raising=False)

    unresolved = [
        {
            "bundle_id": "t1-q1",
            "question": "Did the Hilton payment come through yet?",
            "status": "answer_now",
            "last_asked_at": "2026-04-05T09:00:00",
            "capability_gaps": [],
        }
    ]

    first = cassandra_brain._advance_email_thread_cadence(
        thread_id="t1",
        contact_name="Dad",
        unresolved_bundles=unresolved,
        predictions=[],
        now=datetime(2026, 4, 9, 12, 0, 0),
    )
    second = cassandra_brain._advance_email_thread_cadence(
        thread_id="t1",
        contact_name="Dad",
        unresolved_bundles=unresolved,
        predictions=[{"question": "What needs to happen next?", "because": "Upload the invoice."}],
        now=datetime(2026, 4, 13, 12, 0, 1),
    )

    assert first["status"] == "followup_due"
    assert "One short follow-up is reasonable now." in first["user_update"]
    assert second["status"] == "parked"
    assert "parked this thread" in second["user_update"]
    saved = json.loads(thread_state.read_text(encoding="utf-8"))
    assert saved["t1"]["status"] == "parked"
