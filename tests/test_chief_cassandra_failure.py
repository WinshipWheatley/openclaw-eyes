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
                    "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            ),
        encoding="utf-8",
    )

    sent: list[tuple[str, str | None]] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", pending_path, raising=False)
    monkeypatch.setattr(
        failure,
        "notify_chief",
        lambda text, parse_mode=None: sent.append((text, parse_mode)),
        raising=False,
    )

    failure.investigate_cassandra_timeout("Can you email Winship and ask if it worked?")

    assert sent[0] == (
        "Chief is working on Cassandra's failure for: Can you email Winship and ask if it worked?",
        None,
    )
    assert "Outcome: Winship must fix it manually" in sent[1][0]
    assert "Guardian approval" in sent[1][0]


def test_investigate_timeout_reports_policy_block_before_runtime(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    sent: list[tuple[str, str | None]] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    monkeypatch.setattr(
        failure,
        "notify_chief",
        lambda text, parse_mode=None: sent.append((text, parse_mode)),
        raising=False,
    )

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

    assert "Outcome: Cassandra cannot do this because it is outside her lane / permission / scope" in sent[1][0]
    assert "denied at approval gate" in sent[1][0]


def test_investigate_timeout_reports_runtime_timeout_and_queues_task(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    sent: list[tuple[str, str | None]] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    monkeypatch.setattr(
        failure,
        "notify_chief",
        lambda text, parse_mode=None: sent.append((text, parse_mode)),
        raising=False,
    )

    (tmp_path / "cassandra_listener.out").write_text(
        "[cassandra_listener] error: mock timeout downstream\n",
        encoding="utf-8",
    )

    failure.investigate_cassandra_timeout("What is the current capital hilton status now?")

    assert sent[0] == (
        "Chief is working on Cassandra's failure for: What is the current capital hilton status now?",
        None,
    )
    assert "Outcome: Sent to polish loop for repair; Chief will verify the result" in sent[1][0]
    assert "mock timeout downstream" in sent[1][0]
    assert "chief-cassandra-failure-" in sent[1][0]
    assert "harness-test the result and report WORKING" in sent[1][0]

    task_files = list((tmp_path / "tasks").glob("*chief-cassandra-failure-*.md"))
    assert len(task_files) == 1
    task_text = task_files[0].read_text(encoding="utf-8")
    assert "Use this Chief failure packet as a polish-loop repair task" in task_text
    assert '"repair_agent": "polish_loop"' in task_text
    assert '"chief_role": "diagnose_route_and_harness_verify"' in task_text
    assert '"cassandra_brain.py"' in task_text
    assert '"print or edit secrets"' in task_text
    assert '"focused tests pass"' in task_text
    assert '"chief_harness_contract"' in task_text
    assert "pytest -q tests/test_chief_cassandra_failure.py" in task_text


def test_investigate_timeout_prefers_fresh_timestamped_cassandra_evidence(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    sent: list[tuple[str, str | None]] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_MODEL_ROUTE_LOG", tmp_path / "cassandra_model_routes.jsonl", raising=False)
    monkeypatch.setattr(failure, "_EXTERNAL_LLM_LOG", tmp_path / "external_llm_log.csv", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    monkeypatch.setattr(
        failure,
        "notify_chief",
        lambda text, parse_mode=None: sent.append((text, parse_mode)),
        raising=False,
    )

    (tmp_path / "cassandra_listener.out").write_text(
        "[cassandra_listener] error: name 'deep' is not defined\n",
        encoding="utf-8",
    )
    (tmp_path / "cassandra_model_routes.jsonl").write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "task_class": "cassandra_extract_classify",
                "validation_outcome": "parse_failed",
                "model": "nemotron-3-nano:4b",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "external_llm_log.csv").write_text(
        "timestamp,caller,model,prompt_words,response_words,latency_ms,success\n"
        + f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},cassandra_brain,claude-sonnet-4-6,79,0,4828,False\n",
        encoding="utf-8",
    )

    failure.investigate_cassandra_timeout(
        "Cassandra, put Doctor Appointment on my calendar tomorrow at 2:30 PM for 45 minutes."
    )

    assert "parse-failed" in sent[1][0]
    assert "name 'deep' is not defined" not in sent[1][0]


def test_investigate_timeout_reports_orientation_local_model_timeout(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    sent: list[tuple[str, str | None]] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_MODEL_ROUTE_LOG", tmp_path / "cassandra_model_routes.jsonl", raising=False)
    monkeypatch.setattr(failure, "_EXTERNAL_LLM_LOG", tmp_path / "external_llm_log.csv", raising=False)
    monkeypatch.setattr(failure, "_OLLAMA_DIAGNOSTICS_LOG", tmp_path / "ollama_diagnostics.jsonl", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    monkeypatch.setattr(
        failure,
        "notify_chief",
        lambda text, parse_mode=None: sent.append((text, parse_mode)),
        raising=False,
    )

    (tmp_path / "cassandra_model_routes.jsonl").write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "task_class": "cassandra_user_reply",
                "model": "gemma4:26b",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "ollama_diagnostics.jsonl").write_text(
        json.dumps(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event": "ollama_call",
                "exception_type": "TimeoutError",
                "task_class": None,
                "model": "gemma4:26b",
                "timeout": 60,
                "prompt_words": 508,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    failure.investigate_cassandra_timeout("Cassandra test, draft a text-only answer: where are we?")

    assert "orientation/status reply exhausted the listener budget" in sent[1][0]
    assert "falling through to local Ollama `gemma4:26b`" in sent[1][0]
    assert "no configured external Cassandra language model" in sent[1][0]


def test_investigate_timeout_reports_calendar_delete_gap_in_plain_text(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    sent: list[tuple[str, str | None]] = []
    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CONVO_LOG", tmp_path / "cassandra_conversations.jsonl", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    monkeypatch.setattr(
        failure,
        "notify_chief",
        lambda text, parse_mode=None: sent.append((text, parse_mode)),
        raising=False,
    )

    request = "Cassandra, remove the two Doctor Appointment events tomorrow at 2:30 PM from my calendar."
    (tmp_path / "cassandra_conversations.jsonl").write_text(
        json.dumps(
            {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user": request,
                "replies": ["I'm here — something went quiet on my end. Try again."],
                "route": "llm",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    failure.investigate_cassandra_timeout(request)

    assert sent[0] == (f"Chief is working on Cassandra's failure for: {request}", None)
    assert "did not execute the requested calendar deletion" in sent[1][0]
    assert "no wired calendar-delete capability" in sent[1][0]
    assert sent[1][1] is None
