from __future__ import annotations

import json
from datetime import datetime


def test_investigate_timeout_reports_pending_approval(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    pending_path = tmp_path / "approval_pending.json"
    pending_path.write_text(
        json.dumps(
            {
                "id": "ABCD1234",
                "status": "pending",
                "action": "Google broker: cassandra → google.gmail.send",
                "requested_at": "2026-04-18 12:00:00",
            }
        ),
        encoding="utf-8",
    )

    sent: list[str] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", pending_path, raising=False)
    monkeypatch.setattr(failure, "notify_chief", lambda text: sent.append(text), raising=False)

    failure.investigate_cassandra_timeout("Can you email Winship and ask if it worked?")

    assert sent[0] == "Chief is working on Cassandra's failure for: Can you email Winship and ask if it worked?"
    assert "Outcome: Winship must fix it manually" in sent[1]
    assert "Guardian approval" in sent[1]


def test_investigate_timeout_reports_policy_block_before_runtime(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    sent: list[str] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    monkeypatch.setattr(failure, "notify_chief", lambda text: sent.append(text), raising=False)

    (tmp_path / "cassandra_correspondence.jsonl").write_text(
        json.dumps(
            {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "route": "email_send",
                "state": "blocked",
                "detail": "denied at approval gate",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    failure.investigate_cassandra_timeout("Please send Winship a note")

    assert "Outcome: Cassandra cannot do this because it is outside her lane / permission / scope" in sent[1]
    assert "denied at approval gate" in sent[1]


def test_investigate_timeout_reports_runtime_timeout_and_queues_task(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    sent: list[str] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    monkeypatch.setattr(failure, "notify_chief", lambda text: sent.append(text), raising=False)

    (tmp_path / "cassandra_listener.out").write_text(
        "[cassandra_listener] error: mock timeout downstream\n",
        encoding="utf-8",
    )

    failure.investigate_cassandra_timeout("What is the current capital hilton status now?")

    assert sent[0] == "Chief is working on Cassandra's failure for: What is the current capital hilton status now?"
    assert "Outcome: Chief can queue/autonomously fix it" in sent[1]
    assert "mock timeout downstream" in sent[1]
    assert "chief-cassandra-failure-" in sent[1]
