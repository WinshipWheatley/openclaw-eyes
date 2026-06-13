import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_guided_review as guided
import data_room_live_lm_brain as brain
import watch_desk_feed


FIXED_NOW = "2026-06-13T18:00:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _promotion_review(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
            "authoritative": False,
            "source_artifacts": ["fixture_data_room_lm_brain.json"],
            "review_records": [
                {
                    "record_id": "privacy:payment_policy",
                    "provisional_marker": "*",
                    "authoritative": False,
                    "promotion_requires_winship_confirmation": True,
                    "review_category": "policy_decision",
                    "provisional_fact": "* Payment instructions need a safe default.",
                    "proposed_promoted_value": "* Which payment instructions are safe to show by default?",
                    "confidence": "medium",
                    "source": "fixture#record",
                    "risk_if_wrong": "Could expose private payment instructions.",
                    "recommended_action": "defer",
                },
                {
                    "record_id": "identity:stage_name",
                    "provisional_marker": "*",
                    "authoritative": False,
                    "promotion_requires_winship_confirmation": True,
                    "review_category": "identity",
                    "provisional_fact": "* Stage name preference needs confirmation.",
                    "proposed_promoted_value": "* What name should Cassandra use in client-facing contexts?",
                    "confidence": "medium",
                    "source": "fixture#record",
                    "risk_if_wrong": "Could use the wrong identity in client-facing messages.",
                    "recommended_action": "defer",
                }
            ],
        },
    )


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "review_root": tmp_path / "review",
        "read_model_root": tmp_path / "read_models",
        "receipt_root": tmp_path / "receipts",
        "sqlite_path": tmp_path / "codex_work_package_lifecycle.sqlite",
        "package_root": tmp_path / "packages",
        "turn_root": tmp_path / "turns",
        "promotion_review_path": _promotion_review(tmp_path / "review" / "promotion_review.json"),
    }


def _request_from_prompt(prompt: str) -> dict:
    return json.loads(prompt.split("Request JSON:\n", 1)[1])


def _result_for_request(request: dict, *, intent: str = "clarification", answer: str = "", reply: str = "") -> dict:
    return {
        "schema_version": brain.RESULT_SCHEMA_VERSION,
        "request_id": request["request_id"],
        "review_session_id": request["review_session_id"],
        "question_id": request["current_question_id"],
        "assistant_reply": reply or "I have the Data Room form and can help you fill it out.",
        "operator_intent": intent,
        "proposed_answer": {
            "plain_english": answer,
            "normalized_decision": answer,
            "confidence": "medium" if answer else "",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "requires_winship_confirmation": bool(answer),
        "confirmed_by_winship": False,
        "should_record_now": False,
        "next_question_id": "",
        "chat_log_summary_update": "Data Room LM brain turn completed.",
        "facts_used": ["form_goal", "why_it_matters", "current_question", "safety_boundaries"],
        "safety_flags": dict(brain.SAFE_FALSE_FLAGS),
    }


def _runner(intent: str = "clarification", answer: str = "", reply: str = ""):
    def run(**kwargs):
        request = _request_from_prompt(kwargs["prompt"])
        return {
            "status": "codex_cli_completed",
            "returncode": 0,
            "raw_result_text": json.dumps(_result_for_request(request, intent=intent, answer=answer, reply=reply)),
        }

    return run


def _start(tmp_path: Path) -> tuple[dict, dict[str, Path]]:
    paths = _paths(tmp_path)
    response = guided.process_guided_review_message(
        "Cassandra, let's go over the Data Room setup.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        promotion_review_path=paths["promotion_review_path"],
        generated_at_utc=FIXED_NOW,
    )
    assert response is not None
    return response, paths


def _load_session(response: dict) -> dict:
    session_ref = response["artifact_refs"]["session_json"]
    return json.loads(Path(session_ref).read_text(encoding="utf-8"))


def test_readiness_turn_creates_no_answer_record_and_activates_lane(tmp_path):
    _start_response, paths = _start(tmp_path)

    response = guided.process_guided_review_message(
        "Cassandra, start the Data Room LM brain.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:01:00+00:00",
        live_lm_brain_runner=_runner(reply="I have the Data Room form and can help you fill it out."),
        live_lm_brain_sqlite_path=paths["sqlite_path"],
        live_lm_brain_package_root=paths["package_root"],
        live_lm_brain_turn_root=paths["turn_root"],
    )
    session = _load_session(response)
    status = json.loads((paths["read_model_root"] / "data_room_live_lm_brain_status.json").read_text(encoding="utf-8"))

    assert response["reply_text"] == brain.READY_NOTIFICATION_TEXT
    assert "gemini" not in response["reply_text"].lower()
    assert "chatgpt" not in response["reply_text"].lower()
    assert session["data_room_live_lm_brain"]["active"] is True
    assert session["data_room_live_lm_brain_notification_text"] == brain.READY_NOTIFICATION_TEXT
    assert session["answer_records"] == []
    assert status["live_lm_brain_ready"] is True
    assert status["access_mode"] == "openai_codex_cli"
    assert status["package_size_class"] in {"tiny", "small"}
    assert status["authority_boundary"]["confirmed_reference_data_allowed"] is False
    assert status["authority_boundary"]["hydration_allowed"] is False
    assert status["authority_boundary"]["runtime_mutation_allowed"] is False


def test_candidate_result_creates_pending_candidate_only_then_confirmation_records(tmp_path):
    _start_response, paths = _start(tmp_path)
    guided.process_guided_review_message(
        "Cassandra, start the Data Room LM brain.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:01:00+00:00",
        live_lm_brain_runner=_runner(),
        live_lm_brain_sqlite_path=paths["sqlite_path"],
        live_lm_brain_package_root=paths["package_root"],
        live_lm_brain_turn_root=paths["turn_root"],
    )

    candidate = guided.process_guided_review_message(
        "For trusted clients only.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:02:00+00:00",
        live_lm_brain_runner=_runner(
            intent="answer_candidate",
            answer="Use direct payment instructions only for trusted clients.",
            reply="That sounds like a candidate; should I record it?",
        ),
        live_lm_brain_sqlite_path=paths["sqlite_path"],
        live_lm_brain_package_root=paths["package_root"],
        live_lm_brain_turn_root=paths["turn_root"],
    )
    session = _load_session(candidate)

    assert session["pending_interaction"]["kind"] == "answer_candidate"
    assert session["answer_records"] == []

    confirmed = guided.process_guided_review_message(
        "yes that's right",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:03:00+00:00",
    )
    confirmed_session = _load_session(confirmed)

    assert confirmed_session["pending_interaction"] == {}
    assert confirmed_session["answer_records"][0]["raw_answer_text"] == "Use direct payment instructions only for trusted clients."
    assert confirmed_session["answer_records"][0]["answer_source"] == "natural_candidate_confirmed"


def test_model_result_cannot_record_directly(tmp_path):
    request = brain.build_live_lm_turn_request(
        {
            "review_session_id": "data_room_review:test",
            "current_question_id": "review_question:test",
            "question_queue": [{"question_id": "review_question:test", "question_text": "Question?", "category": "payment"}],
        },
        "Record this.",
        created_at_utc=FIXED_NOW,
    )
    result = _result_for_request(request, intent="answer_candidate", answer="Record it.")
    result["should_record_now"] = True

    assert "should_record_now_must_be_false" in brain.validate_live_lm_turn_result(result, request)


def test_malformed_lm_result_blocks_without_ready_status(tmp_path):
    _start_response, paths = _start(tmp_path)

    def malformed(**_kwargs):
        return {"status": "codex_cli_completed", "returncode": 0, "raw_result_text": "not json"}

    response = guided.process_guided_review_message(
        "Cassandra, start the Data Room LM brain.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:01:00+00:00",
        live_lm_brain_runner=malformed,
        live_lm_brain_sqlite_path=paths["sqlite_path"],
        live_lm_brain_package_root=paths["package_root"],
        live_lm_brain_turn_root=paths["turn_root"],
    )
    status = json.loads((paths["read_model_root"] / "data_room_live_lm_brain_status.json").read_text(encoding="utf-8"))

    assert "Data Room LM brain blocked" in response["reply_text"]
    assert status["live_lm_brain_ready"] is False
    assert "data_room_live_lm_brain_notification_text" not in _load_session(response)
    assert status["last_error"]


def test_gemini_blocked_status_does_not_prevent_codex_lm_brain(tmp_path):
    _start_response, paths = _start(tmp_path)
    _write_json(
        paths["read_model_root"] / "data_room_gemini_form_session.json",
        {
            "schema_version": "DATA_ROOM_GEMINI_FORM_SESSION_STATUS_V0",
            "live_ready": False,
            "blocked_reason": "blocked_provider_rate_limited",
            "provider": "gemini",
        },
    )

    response = guided.process_guided_review_message(
        "Cassandra, use the LM brain for this Data Room form.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:01:00+00:00",
        live_lm_brain_runner=_runner(reply="I have the Data Room form and can help you fill it out."),
        live_lm_brain_sqlite_path=paths["sqlite_path"],
        live_lm_brain_package_root=paths["package_root"],
        live_lm_brain_turn_root=paths["turn_root"],
    )
    status = json.loads((paths["read_model_root"] / "data_room_live_lm_brain_status.json").read_text(encoding="utf-8"))

    assert response["reply_text"] == brain.READY_NOTIFICATION_TEXT
    assert status["provider"] == "openai"
    assert status["access_mode"] == "openai_codex_cli"
    assert status["live_lm_brain_ready"] is True


def test_context_switchboard_detour_is_not_routed_through_lm_brain(tmp_path):
    _start_response, paths = _start(tmp_path)
    guided.process_guided_review_message(
        "Cassandra, start the Data Room LM brain.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:01:00+00:00",
        live_lm_brain_runner=_runner(),
        live_lm_brain_sqlite_path=paths["sqlite_path"],
        live_lm_brain_package_root=paths["package_root"],
        live_lm_brain_turn_root=paths["turn_root"],
    )

    def should_not_run(**_kwargs):
        raise AssertionError("context switchboard detour should not invoke the Data Room LM brain")

    response = guided.process_guided_review_message(
        "I got paid $900 from Live Arts MD.",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["receipt_root"],
        generated_at_utc="2026-06-13T18:02:00+00:00",
        live_lm_brain_runner=should_not_run,
        live_lm_brain_sqlite_path=paths["sqlite_path"],
        live_lm_brain_package_root=paths["package_root"],
        live_lm_brain_turn_root=paths["turn_root"],
    )

    assert response is None


def test_timeout_blocks_without_retry(tmp_path):
    _start_response, paths = _start(tmp_path)

    def timeout(**_kwargs):
        return {"status": "timeout_with_no_result", "returncode": 124, "raw_result_text": ""}

    run = brain.run_live_lm_turn(
        _load_session(_start_response),
        brain.READINESS_USER_TURN,
        created_at_utc="2026-06-13T18:01:00+00:00",
        codex_runner=timeout,
        sqlite_path=paths["sqlite_path"],
        package_root=paths["package_root"],
        turn_root=paths["turn_root"],
        read_model_path=paths["read_model_root"] / "data_room_live_lm_brain_status.json",
    )

    assert run["status"] == "blocked_timeout"
    assert run["status_read_model"]["live_lm_brain_ready"] is False


def test_medium_or_large_package_blocks_before_cli_dispatch(tmp_path, monkeypatch):
    start_response, paths = _start(tmp_path)
    runner_called = False

    def fake_create(*_args, **_kwargs):
        return {
            "status": "canonical_worker_package_queued",
            "package_state": {
                "package_id": "codex_work_package:too_big",
                "authority_grant_ref": "",
                "package_json": {"package_size_class": "medium", "cli_dispatch_allowed": False},
                "package_files": {},
            },
        }

    def should_not_run(**_kwargs):
        nonlocal runner_called
        runner_called = True
        return {}

    monkeypatch.setattr(brain.lifecycle, "create_worker_package_from_assignment_loop", fake_create)

    run = brain.run_live_lm_turn(
        _load_session(start_response),
        brain.READINESS_USER_TURN,
        created_at_utc="2026-06-13T18:01:00+00:00",
        codex_runner=should_not_run,
        sqlite_path=paths["sqlite_path"],
        package_root=paths["package_root"],
        turn_root=paths["turn_root"],
        read_model_path=paths["read_model_root"] / "data_room_live_lm_brain_status.json",
    )

    assert run["status"] == "blocked_package_too_large"
    assert runner_called is False


def test_watch_desk_projects_data_room_live_lm_brain_item(tmp_path):
    read_root = tmp_path / "read_models"
    brain.write_live_lm_brain_status(
        {
            "status": "ready",
            "live_lm_brain_ready": True,
            "provider": "openai",
            "access_mode": "openai_codex_cli",
            "worker_kind": "openai_codex_cli",
            "active_session_id": "data_room_review:test",
            "current_question_id": "review_question:test",
            "last_error": "",
        },
        path=read_root / "data_room_live_lm_brain_status.json",
        bridge_root=None,
    )

    feed = watch_desk_feed.build_watch_desk_feed(read_model_root=read_root, task_root=tmp_path / "tasks")
    item = next(row for row in feed["feed_items"] if row["item_id"] == "data_room_live_lm_brain:data_room_review:test")

    assert item["lane"] == "cassandra_ar"
    assert item["state"]["live_lm_brain_ready"] is True
    assert item["state"]["execution_allowed"] is False
