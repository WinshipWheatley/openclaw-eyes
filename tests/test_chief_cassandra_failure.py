from __future__ import annotations

import json
from datetime import datetime


def _origin_meta(source_message_id: str) -> dict:
    return {
        "surface": "cassandra_telegram",
        "bot_identity": "cassandra",
        "sender_chat_id": 4242,
        "source_message_id": source_message_id,
        "source_user_label": "operator",
    }


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

    monkeypatch.setattr(failure, "_APPROVAL_PENDING", pending_path, raising=False)
    result = failure.investigate_cassandra_timeout(
        "Can you email Winship and ask if it worked?",
        _origin_meta("pending-approval"),
    )

    assert "Outcome: Winship must fix it manually" in result.internal_report
    assert "Guardian approval" in result.internal_report
    assert "Guardian approval" not in result.output.visible_text()
    assert result.receipt_pointer in result.output.visible_text()


def test_investigate_timeout_reports_policy_block_before_runtime(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
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

    result = failure.investigate_cassandra_timeout(
        "Please send Winship a note",
        _origin_meta("policy-block"),
    )

    assert "Outcome: Cassandra cannot do this because it is outside her lane / permission / scope" in result.internal_report
    assert "denied at approval gate" in result.internal_report
    assert "denied at approval gate" not in result.output.visible_text()


def test_investigate_timeout_reports_runtime_timeout_and_queues_task(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
    (tmp_path / "cassandra_listener.out").write_text(
        "[cassandra_listener] error: mock timeout downstream\n",
        encoding="utf-8",
    )

    result = failure.investigate_cassandra_timeout(
        "What is the current capital hilton status now?",
        _origin_meta("runtime-timeout"),
    )
    assert "Outcome: Sent to polish loop for repair; Chief will verify the result" in result.internal_report
    assert "mock timeout downstream" in result.internal_report
    assert "chief-cassandra-failure-" in result.internal_report
    assert "harness-test the result and report WORKING" in result.internal_report
    assert "mock timeout downstream" not in result.output.visible_text()

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

    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_MODEL_ROUTE_LOG", tmp_path / "cassandra_model_routes.jsonl", raising=False)
    monkeypatch.setattr(failure, "_EXTERNAL_LLM_LOG", tmp_path / "external_llm_log.csv", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
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

    result = failure.investigate_cassandra_timeout(
        "Cassandra, put Doctor Appointment on my calendar tomorrow at 2:30 PM for 45 minutes.",
        _origin_meta("fresh-evidence"),
    )

    assert "parse-failed" in result.internal_report
    assert "name 'deep' is not defined" not in result.internal_report
    assert "parse-failed" not in result.output.visible_text()


def test_investigate_timeout_reports_orientation_local_model_timeout(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_MODEL_ROUTE_LOG", tmp_path / "cassandra_model_routes.jsonl", raising=False)
    monkeypatch.setattr(failure, "_EXTERNAL_LLM_LOG", tmp_path / "external_llm_log.csv", raising=False)
    monkeypatch.setattr(failure, "_OLLAMA_DIAGNOSTICS_LOG", tmp_path / "ollama_diagnostics.jsonl", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
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

    result = failure.investigate_cassandra_timeout(
        "Cassandra test, draft a text-only answer: where are we?",
        _origin_meta("orientation-timeout"),
    )

    assert "orientation/status reply exhausted the listener budget" in result.internal_report
    assert "falling through to local Ollama `gemma4:26b`" in result.internal_report
    assert "no configured external Cassandra language model" in result.internal_report
    assert "gemma4:26b" not in result.output.visible_text()


def test_investigate_timeout_reports_calendar_delete_gap_in_plain_text(monkeypatch, tmp_path):
    import chief_cassandra_failure as failure

    monkeypatch.setattr(failure, "_APPROVAL_PENDING", tmp_path / "approval_pending.json", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CORRESPONDENCE_LOG", tmp_path / "cassandra_correspondence.jsonl", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_LISTENER_LOG", tmp_path / "cassandra_listener.out", raising=False)
    monkeypatch.setattr(failure, "_CASSANDRA_CONVO_LOG", tmp_path / "cassandra_conversations.jsonl", raising=False)
    monkeypatch.setattr(failure, "_POLISH_TASKS_DIR", tmp_path / "tasks", raising=False)
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

    result = failure.investigate_cassandra_timeout(
        request,
        _origin_meta("calendar-delete-gap"),
    )

    assert "did not execute the requested calendar deletion" in result.internal_report
    assert "no wired calendar-delete capability" in result.internal_report
    assert "calendar-delete" not in result.output.visible_text()
