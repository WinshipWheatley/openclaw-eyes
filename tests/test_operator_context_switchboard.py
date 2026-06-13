import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_guided_review as guided
import openclaw_chatgpt55_adapter as chatgpt55
import openclaw_gemini_form_adapter as gemini
from operator_context_switchboard import (
    ACTIVE_CONTEXTS_SCHEMA_VERSION,
    SCHEMA_VERSION,
    process_operator_context_switchboard_message,
    write_operator_active_contexts_read_model,
)
from watch_desk_feed import build_watch_desk_feed


FIXED_NOW = "2026-06-12T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _record(record_id, category, fact, proposed, *, risk="wrong runtime behavior", action="defer"):
    return {
        "record_id": record_id,
        "provisional_marker": "*",
        "authoritative": False,
        "promotion_requires_winship_confirmation": True,
        "review_category": category,
        "provisional_fact": f"* {fact}",
        "proposed_promoted_value": f"* {proposed}",
        "confidence": "medium",
        "source": "fixture_promotion_review.json#review_records",
        "risk_if_wrong": risk,
        "recommended_action": action,
    }


def _promotion_review(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
            "authoritative": False,
            "source_artifacts": ["fixture_operator_context_switchboard.json"],
            "review_records": [
                _record(
                    "privacy:payment_policy",
                    "policy_decision",
                    "Direct deposit, Zelle, and forwarded invoices need a safe default.",
                    "Winship must decide default payment privacy wording.",
                    risk="Could expose private payment instructions.",
                ),
                _record(
                    "identity:general",
                    "policy_decision",
                    "Identity and sender rules are provisional.",
                    "Winship must decide default identity and persona boundaries.",
                ),
                _record(
                    "rate:live_arts",
                    "needs_correction",
                    "Live Arts rates mix service types.",
                    "Split rates by service before promotion.",
                    action="revise",
                ),
            ],
        },
    )


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "review_root": tmp_path / "review",
        "read_model_root": tmp_path / "read_models",
        "switch_receipts": tmp_path / "switchboard_receipts",
        "intake_receipts": tmp_path / "intake_receipts",
    }


def _start(tmp_path: Path):
    paths = _paths(tmp_path)
    promotion = _promotion_review(paths["review_root"] / "promotion_review.json")
    return guided.process_guided_review_message(
        "Cassandra, coach me through the Data Room.",
        surface="telegram",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )


def _switch(tmp_path: Path, text: str, *, surface: str = "telegram", at: str = "2026-06-12T12:01:00+00:00"):
    paths = _paths(tmp_path)
    return process_operator_context_switchboard_message(
        text,
        surface=surface,
        source_agent="cassandra",
        operator="Winship",
        review_root=paths["review_root"],
        read_model_root=paths["read_model_root"],
        receipt_root=paths["switch_receipts"],
        operator_intake_receipt_root=paths["intake_receipts"],
        received_at_utc=at,
        operator_timezone="America/New_York",
    )


def _load_session(start_response: dict) -> dict:
    return json.loads(Path(start_response["artifact_refs"]["session_json"]).read_text(encoding="utf-8"))


def _gemini_result(request: dict) -> dict:
    return {
        "schema_version": gemini.TURN_RESULT_SCHEMA_VERSION,
        "request_id": request["request_id"],
        "form_session_id": request["form_session_id"],
        "review_session_id": request["review_session_id"],
        "question_id": request["current_question_id"],
        "assistant_reply": "I have the form and can help.",
        "operator_intent": "explain",
        "proposed_answer": {
            "plain_english": "",
            "normalized_decision": "",
            "confidence": "low",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "requires_winship_confirmation": False,
        "confirmed_by_winship": False,
        "should_record_now": False,
        "next_question_id": "",
        "chat_log_summary_update": "Gemini is ready.",
        "done_criteria_met": False,
        "facts_used": [request["current_question_id"]],
        "codex_finalization_recommended": False,
        "safety_flags": dict(gemini.SAFE_TURN_SAFETY_FLAGS),
    }


def _fake_gemini_provider(calls: list[dict]):
    def provider(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
        calls.append({"request_payload": request_payload, "request_body": request_body})
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(_gemini_result(request_payload))}]}}]}

    return provider


def _load_receipt(ref: str) -> dict:
    return json.loads(Path(ref.split("#", 1)[0]).read_text(encoding="utf-8"))


def _ref_path(ref: str) -> Path:
    return Path(ref.split("#", 1)[0])


def _force_current_question(response: dict, category: str) -> dict:
    session_path = Path(response["artifact_refs"]["session_json"])
    session = json.loads(session_path.read_text(encoding="utf-8"))
    question = next(item for item in session["question_queue"] if item["category"] == category)
    session["current_question_id"] = question["question_id"]
    _write_json(session_path, session)
    return question


def test_decision_schema_has_required_safety_flags(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "why?")

    assert decision["schema_version"] == SCHEMA_VERSION
    assert decision["decision"] == "current_task_control"
    for field in (
        "decision_id",
        "created_at_utc",
        "surface",
        "source_agent",
        "raw_text_hash",
        "active_contexts",
        "current_context_id",
        "detected_intent",
        "detected_lane",
        "detected_action_type",
        "confidence",
        "routed_to_agent",
        "routed_to_lane",
        "current_task_action",
        "handoff_reason",
        "operator_visible_reply",
        "receipt_refs",
        "watch_desk_refs",
        "safety_flags",
    ):
        assert field in decision
    assert decision["safety_flags"]["external_calls_performed"] is False
    assert decision["safety_flags"]["approval_created"] is False
    assert decision["safety_flags"]["invoice_marked_paid"] is False
    assert _load_session(start)["answer_records"] == []


def test_guided_review_active_why_stays_with_current_review(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "why?")
    assert decision["decision"] == "current_task_control"

    response = guided.process_guided_review_message(
        "why?",
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(response)
    assert "Why it matters:" in response["reply_text"]
    assert session["current_question_id"] == start["current_question_id"]
    assert session["answer_records"] == []


def test_payment_log_interrupts_review_without_recording_answer(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "I got paid $900 from Live Arts MD.")
    session = _load_session(start)
    intake_model = json.loads((_paths(tmp_path)["read_model_root"] / "operator_intake_events.json").read_text(encoding="utf-8"))
    event = intake_model["events"][0]
    feed = build_watch_desk_feed(read_model_root=_paths(tmp_path)["read_model_root"], generated_at="2026-06-12T12:02:00+00:00")

    assert decision["decision"] == "new_task_interrupt"
    assert decision["detected_action_type"] == "income_payment_log"
    assert decision["safety_flags"]["external_calls_performed"] is False
    assert "Logged the $900 Live Arts MD income note" in decision["operator_visible_reply"]
    assert "I did not mark any invoice paid" in decision["operator_visible_reply"]
    assert "Back to Data Room:" in decision["operator_visible_reply"]
    assert all(_ref_path(ref).is_file() for ref in decision["receipt_refs"])
    assert session["answer_records"] == []
    assert session["status"] == "paused"
    assert event["parsed"]["action_type"] == "income_payment_log"
    assert event["parsed"]["fields"]["amount"] == 900.0
    assert event["parsed"]["fields"]["payer"] == "Live Arts MD"
    assert event["parsed"]["fields"]["invoice_marked_paid"] is False
    assert all(
        not item.get("source_receipt_ref") or _ref_path(str(item["source_receipt_ref"])).is_file()
        for item in feed["feed_items"]
        if item["item_id"].startswith("operator_intake:")
    )


def test_payment_log_interrupts_live_gemini_lane_without_calling_gemini(tmp_path, monkeypatch):
    _start(tmp_path)
    calls: list[dict] = []
    monkeypatch.setenv("OPENCLAW_ENABLE_LIVE_GEMINI_FORM", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-redacted")
    monkeypatch.setattr(gemini, "DEFAULT_FORM_SESSION_READ_MODEL_PATH", _paths(tmp_path)["read_model_root"] / "data_room_gemini_form_session.json")
    monkeypatch.setattr(gemini, "DEFAULT_FORM_PRIMARY_ROOT", tmp_path / "gemini_form")
    monkeypatch.setattr(gemini, "DEFAULT_FORM_DURABLE_ROOT", tmp_path / "durable_gemini_form")

    guided.process_guided_review_message(
        "Cassandra, start the Gemini Data Room form lane.",
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        generated_at_utc="2026-06-12T12:01:00+00:00",
        gemini_form_provider=_fake_gemini_provider(calls),
    )
    calls.clear()

    decision = _switch(tmp_path, "I got paid $900 from Live Arts MD.", at="2026-06-12T12:02:00+00:00")
    session = guided._find_active_session(guided._review_root(_paths(tmp_path)["review_root"]))

    assert decision["decision"] == "new_task_interrupt"
    assert decision["safety_flags"]["external_calls_performed"] is False
    assert calls == []
    assert session["answer_records"] == []
    assert session["status"] == "paused"


def test_duplicate_payment_log_repairs_missing_local_receipt_ref(tmp_path):
    _start(tmp_path)
    first = _switch(tmp_path, "I got paid $900 from Live Arts MD.")
    first_path = _ref_path(first["receipt_refs"][0])
    assert first_path.is_file()

    first_path.unlink()
    second = _switch(tmp_path, "I got paid $900 from Live Arts MD.", at="2026-06-12T12:02:00+00:00")
    intake_model = json.loads((_paths(tmp_path)["read_model_root"] / "operator_intake_events.json").read_text(encoding="utf-8"))

    assert second["decision"] == "new_task_interrupt"
    assert second["receipt_refs"]
    assert all(_ref_path(ref).is_file() for ref in second["receipt_refs"])
    assert intake_model["event_count"] == 1
    assert intake_model["events"][0]["duplicate_detected"] is True
    assert intake_model["events"][0]["stop_condition"] == "duplicate_local_receipt_rematerialized"


def test_health_update_creates_operator_status_note_and_no_medical_advice(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "Health update: I slept badly and feel off today.")
    session = _load_session(start)
    receipt = _load_receipt(decision["receipt_refs"][0])

    assert decision["decision"] == "new_task_interrupt"
    assert decision["detected_action_type"] == "operator_status_note"
    assert "No medical advice or external action taken" in decision["operator_visible_reply"]
    assert "diagnose" not in decision["operator_visible_reply"].lower()
    assert "treat" not in decision["operator_visible_reply"].lower()
    assert session["answer_records"] == []
    assert session["status"] == "paused"
    assert receipt["note_type"] == "operator_status_note"
    assert receipt["tags"] == ["sleep", "mood"]
    assert receipt["medical_advice_given"] is False
    assert receipt["external_calls_performed"] is False


def test_mid_sentence_feeling_off_stays_with_review_not_health_note(tmp_path):
    start = _start(tmp_path)
    _force_current_question(start, "identity/persona policy")

    decision = _switch(tmp_path, "Honestly feeling off about exposing my home address on invoices.")
    contexts_path = _paths(tmp_path)["read_model_root"] / "operator_active_contexts.json"
    contexts_model = json.loads(contexts_path.read_text(encoding="utf-8")) if contexts_path.exists() else {}

    assert decision["decision"] == "current_task_continue"
    assert decision["detected_action_type"] == "guided_review_answer_candidate"
    assert decision["receipt_refs"] == []
    assert all(
        context.get("context_type") != "operator_status_note"
        for context in contexts_model.get("active_contexts", [])
    )
    assert _load_session(start)["answer_records"] == []


def test_album_routes_to_niles_without_daw_media_or_csv_mutation(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "album")
    session = _load_session(start)
    receipt = _load_receipt(decision["receipt_refs"][0])

    assert decision["decision"] == "new_task_stage"
    assert decision["routed_to_agent"] == "niles"
    assert decision["detected_action_type"] == "niles_album_progression"
    assert "No DAW, media, or CSV changes" in decision["operator_visible_reply"]
    assert "Back to Data Room:" in decision["operator_visible_reply"]
    assert session["answer_records"] == []
    assert session["status"] == "paused"
    assert receipt["action_type"] == "niles_album_progression"
    assert receipt["daw_action_taken"] is False
    assert receipt["daws_or_media_mutated"] is False
    assert receipt["media_or_session_mutated"] is False
    assert receipt["csv_mutated"] is False


def test_what_broke_routes_to_chief_system_lane(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "What broke?")
    session = _load_session(start)

    assert decision["decision"] == "new_task_stage"
    assert decision["routed_to_agent"] == "chief"
    assert decision["detected_action_type"] == "agent_lane_request"
    assert "Routed that to Chief/system review" in decision["operator_visible_reply"]
    assert "Back to Data Room:" in decision["operator_visible_reply"]
    assert session["answer_records"] == []
    assert session["status"] == "paused"


def test_pending_mismatch_yes_is_not_stolen_by_switchboard(tmp_path):
    start = _start(tmp_path)
    identity_question = _force_current_question(start, "identity/persona policy")
    mismatch = guided.process_guided_review_message(
        "Direct deposit stays manual approval only. Zelle and check are okay by default.",
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    assert _load_session(mismatch)["pending_interaction"]

    decision = _switch(tmp_path, "yes", at="2026-06-12T12:02:00+00:00")
    assert decision["decision"] == "current_task_continue"
    assert decision["detected_action_type"] == "guided_review_pending_interaction"

    confirmed = guided.process_guided_review_message(
        "yes",
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        generated_at_utc="2026-06-12T12:03:00+00:00",
    )
    session = _load_session(confirmed)
    assert session["current_question_id"] == identity_question["question_id"]
    assert session["answer_records"][0]["question_category"] == "payment privacy"
    assert session["answer_records"][0]["answer_source"] == "topic_switch_confirmed"


def test_guardian_approval_phrase_passes_through_untouched(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "YES:operator_action_approval_request_123")
    session = _load_session(start)

    assert decision["decision"] == "approval_passthrough"
    assert decision["routed_to_agent"] == "guardian"
    assert decision["operator_visible_reply"] == ""
    assert decision["receipt_refs"] == []
    assert session["answer_records"] == []
    assert not (_paths(tmp_path)["read_model_root"] / "operator_intake_events.json").exists()


def test_ambiguous_handle_that_thing_asks_short_clarification(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "handle that thing")
    session = _load_session(start)
    contexts_model = json.loads((_paths(tmp_path)["read_model_root"] / "operator_active_contexts.json").read_text(encoding="utf-8"))

    assert decision["decision"] == "clarification_needed"
    assert "current" in decision["operator_visible_reply"]
    assert "new task" in decision["operator_visible_reply"]
    assert any(
        context.get("context_type") == "switchboard_clarification"
        and context.get("status") == "pending"
        for context in contexts_model["active_contexts"]
    )
    assert session["answer_records"] == []
    assert session["status"] == "active"


def test_ambiguous_clarification_current_question_is_terminal_not_review_answer(tmp_path):
    start = _start(tmp_path)
    _switch(tmp_path, "handle that thing")

    decision = _switch(tmp_path, "current question", at="2026-06-12T12:02:00+00:00")
    session = _load_session(start)

    assert decision["decision"] == "current_task_control"
    assert decision["detected_action_type"] == "resolve_current_question"
    assert "staying with the current" in decision["operator_visible_reply"]
    assert session["answer_records"] == []


def test_ambiguous_clarification_new_task_is_terminal_not_review_answer(tmp_path):
    start = _start(tmp_path)
    _switch(tmp_path, "handle that thing")

    decision = _switch(tmp_path, "new task", at="2026-06-12T12:02:00+00:00")
    session = _load_session(start)

    assert decision["decision"] == "clarification_needed"
    assert decision["detected_action_type"] == "resolve_new_task"
    assert decision["routed_to_lane"] == "operator_context_switchboard"
    assert "What new task should I route" in decision["operator_visible_reply"]
    assert session["answer_records"] == []


def test_resume_data_room_reopens_paused_review(tmp_path):
    start = _start(tmp_path)
    _switch(tmp_path, "Health update: I slept badly and feel off today.")
    paused = _load_session(start)
    assert paused["status"] == "paused"

    decision = _switch(tmp_path, "continue Data Room", at="2026-06-12T12:02:00+00:00")
    resumed = _load_session(start)
    assert decision["decision"] == "resume_task"
    assert decision["current_task_action"] == "resume"
    assert resumed["status"] == "active"


def test_data_room_opener_uses_guided_review_route_not_switchboard(tmp_path):
    _start(tmp_path)
    text = "Cassandra, let's go over the thing where the system needs to know more specifics about gigs and payments."

    decision = _switch(tmp_path, text)
    assert decision is None

    response = guided.process_guided_review_message(
        text,
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    assert response["handled"] is True
    assert "Continuing the active OpenClaw Data Room" in response["reply_text"]
    assert response["authoritative"] is False
    assert response["runtime_policy_changed"] is False


def test_plain_data_room_start_phrase_uses_guided_review_not_lane_request(tmp_path):
    _start(tmp_path)
    text = "All right, let's start the Data room"

    decision = _switch(tmp_path, text)
    assert decision is None

    response = guided.process_guided_review_message(
        text,
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    assert response["handled"] is True
    assert "Continuing the active OpenClaw Data Room" in response["reply_text"]
    assert response["authoritative"] is False
    assert response["runtime_policy_changed"] is False


def test_vague_business_review_prompt_asks_guided_clarification_not_chief(tmp_path):
    _start(tmp_path)
    text = "review business stuff"

    decision = _switch(tmp_path, text)
    assert decision["decision"] == "clarification_needed"
    assert decision["routed_to_lane"] == "guided_review_session"
    assert "OpenClaw Data Room / Reference Data Review" in decision["operator_visible_reply"]
    assert "Invoice Policy Review" in decision["operator_visible_reply"]


def test_continue_album_resumes_niles_context_not_data_room(tmp_path):
    start = _start(tmp_path)
    _switch(tmp_path, "album")

    decision = _switch(tmp_path, "continue album", at="2026-06-12T12:02:00+00:00")
    session = _load_session(start)

    assert decision["decision"] == "resume_task"
    assert decision["routed_to_agent"] == "niles"
    assert decision["routed_to_lane"] == "niles_album_progression"
    assert "Continuing Niles album/progression" in decision["operator_visible_reply"]
    assert session["status"] == "paused"


def test_back_to_niles_resumes_niles_context_not_data_room(tmp_path):
    start = _start(tmp_path)
    _switch(tmp_path, "album")

    decision = _switch(tmp_path, "back to niles", at="2026-06-12T12:02:00+00:00")
    session = _load_session(start)

    assert decision["decision"] == "resume_task"
    assert decision["routed_to_agent"] == "niles"
    assert decision["routed_to_lane"] == "niles_album_progression"
    assert session["status"] == "paused"


def test_duplicate_niles_album_context_upserts_on_next_write(tmp_path):
    _start(tmp_path)
    _switch(tmp_path, "album")
    _switch(tmp_path, "album", at="2026-06-12T12:02:00+00:00")

    contexts_model = json.loads((_paths(tmp_path)["read_model_root"] / "operator_active_contexts.json").read_text(encoding="utf-8"))
    niles_contexts = [
        context
        for context in contexts_model["active_contexts"]
        if context.get("context_type") == "niles_album_progression"
    ]

    assert len(niles_contexts) == 1
    assert niles_contexts[0]["last_turn_at_utc"] == "2026-06-12T12:02:00+00:00"


def test_completed_operator_status_context_expires_after_24_hours(tmp_path):
    read_model_root = _paths(tmp_path)["read_model_root"]
    write_operator_active_contexts_read_model(
        [
            {
                "active_context_id": "operator_status_note:old",
                "context_type": "operator_status_note",
                "owner_agent": "cassandra",
                "topic": "operator_status_note",
                "status": "completed",
                "last_turn_at_utc": "2026-06-11T12:00:00+00:00",
                "source_session_ref": "receipt.json#receipt",
            }
        ],
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:00:01+00:00",
    )
    contexts_model = json.loads((read_model_root / "operator_active_contexts.json").read_text(encoding="utf-8"))

    assert contexts_model["active_contexts"] == []


def test_cassandra_brain_continue_album_returns_niles_without_guided_fallthrough(monkeypatch, tmp_path):
    import cassandra_brain

    _start(tmp_path)
    logged_rows = []

    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda query, packet: "event:test")
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None)
    monkeypatch.setattr(cassandra_brain, "answer_date_awareness_query", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None)

    def fail_call(*args, **kwargs):
        raise AssertionError("switchboard terminal resume should not call a model")

    def capture_log(user_text, replies, route="llm", metadata=None):
        logged_rows.append({"route": route, "replies": replies, "metadata": metadata or {}})

    monkeypatch.setattr(cassandra_brain, "_call", fail_call)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", capture_log)

    session = {
        "skip_followup_check": True,
        "source_user_label": "operator",
        "received_at_utc": "2026-06-12T12:01:00+00:00",
        "operator_timezone": "America/New_York",
        "guided_review_root": _paths(tmp_path)["review_root"],
        "guided_review_read_model_root": _paths(tmp_path)["read_model_root"],
        "operator_context_switchboard_receipt_root": _paths(tmp_path)["switch_receipts"],
        "operator_intake_read_model_root": _paths(tmp_path)["read_model_root"],
        "operator_intake_receipt_root": _paths(tmp_path)["intake_receipts"],
    }
    staged = cassandra_brain.handle("album", session=session)
    session["received_at_utc"] = "2026-06-12T12:02:00+00:00"
    resumed = cassandra_brain.handle("continue album", session=session)
    session_payload = _load_session({"artifact_refs": {"session_json": str(next(_paths(tmp_path)["review_root"].glob("data_room_guided_review_session_*.json")))}})

    assert "Staged album progression for Niles" in staged[0]
    assert resumed == ["Continuing Niles album/progression. No DAW, media, or CSV changes."]
    assert logged_rows[-1]["route"] == "operator_context_switchboard"
    assert logged_rows[-1]["metadata"]["decision"] == "resume_task"
    assert logged_rows[-1]["metadata"]["routed_to_lane"] == "niles_album_progression"
    assert session_payload["status"] == "paused"
    assert session_payload["answer_records"] == []


def test_cassandra_brain_context_switchboard_detour_precedes_live_chatgpt55_lane(monkeypatch, tmp_path):
    import cassandra_brain

    promotion = _promotion_review(_paths(tmp_path)["review_root"] / "promotion_review.json")
    monkeypatch.setenv("OPENCLAW_ENABLE_LIVE_CHATGPT55", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    monkeypatch.setattr(
        chatgpt55,
        "DEFAULT_LIVE_LANE_READ_MODEL_PATH",
        _paths(tmp_path)["read_model_root"] / "data_room_live_chatgpt55_lane.json",
    )
    monkeypatch.setattr(chatgpt55, "DEFAULT_LIVE_LANE_PRIMARY_ROOT", tmp_path / "live_lane")
    monkeypatch.setattr(chatgpt55, "DEFAULT_LIVE_LANE_DURABLE_ROOT", tmp_path / "durable_live_lane")
    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda query, packet: "event:test")
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None)
    monkeypatch.setattr(cassandra_brain, "answer_date_awareness_query", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None)

    calls: list[dict] = []

    def fake_provider(*, request_payload: dict, request_body: dict, model_label: str, timeout_seconds: int) -> dict:
        calls.append({"request_payload": request_payload, "request_body": request_body})
        result = {
            "schema_version": chatgpt55.TURN_RESULT_SCHEMA_VERSION,
            "request_id": request_payload["request_id"],
            "review_session_id": request_payload["review_session_id"],
            "question_id": request_payload["current_question_id"],
            "assistant_reply": "I have the form and can help.",
            "operator_intent": "explain",
            "proposed_answer": {
                "plain_english": "",
                "normalized_decision": "",
                "confidence": "low",
                "conditions": [],
                "caveats": [],
                "professional_review_flags": [],
            },
            "requires_winship_confirmation": False,
            "confirmed_by_winship": False,
            "should_record_now": False,
            "next_question_id": "",
            "chat_log_summary_update": "Ready.",
            "done_criteria_met": False,
            "facts_used": [request_payload["current_question_id"]],
            "safety_flags": dict(chatgpt55.SAFE_TURN_SAFETY_FLAGS),
        }
        return {"id": "resp_fake", "status": "completed", "output_text": json.dumps(result)}

    guided.process_guided_review_message(
        "Cassandra, coach me through the Data Room.",
        surface="telegram",
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    guided.process_guided_review_message(
        "Cassandra, start the ChatGPT 5.5 Data Room brain.",
        surface="telegram",
        review_root=_paths(tmp_path)["review_root"],
        read_model_root=_paths(tmp_path)["read_model_root"],
        generated_at_utc="2026-06-12T12:01:00+00:00",
        chatgpt55_provider=fake_provider,
    )
    calls.clear()

    replies = cassandra_brain.handle(
        "I got paid $900 from Live Arts MD.",
        session={
            "skip_followup_check": True,
            "source_user_label": "operator",
            "guided_review_root": _paths(tmp_path)["review_root"],
            "guided_review_read_model_root": _paths(tmp_path)["read_model_root"],
            "guided_review_promotion_review_path": promotion,
            "operator_context_switchboard_receipt_root": _paths(tmp_path)["switch_receipts"],
            "operator_intake_receipt_root": _paths(tmp_path)["intake_receipts"],
            "operator_intake_read_model_root": _paths(tmp_path)["read_model_root"],
            "received_at_utc": "2026-06-12T12:02:00+00:00",
            "operator_timezone": "America/New_York",
            "chatgpt55_provider": fake_provider,
        },
    )
    session_payload = _load_session({"artifact_refs": {"session_json": str(next(_paths(tmp_path)["review_root"].glob("data_room_guided_review_session_*.json")))}})

    assert "Logged the $900 Live Arts MD income note" in replies[0]
    assert "Back to Data Room:" in replies[0]
    assert calls == []
    assert session_payload["status"] == "paused"
    assert session_payload["answer_records"] == []


def test_watch_desk_shows_paused_review_and_staged_task_without_duplicate_feed(tmp_path):
    start = _start(tmp_path)
    _switch(tmp_path, "album")

    contexts_model = json.loads((_paths(tmp_path)["read_model_root"] / "operator_active_contexts.json").read_text(encoding="utf-8"))
    assert contexts_model["schema_version"] == ACTIVE_CONTEXTS_SCHEMA_VERSION
    feed = build_watch_desk_feed(read_model_root=_paths(tmp_path)["read_model_root"], generated_at="2026-06-12T12:02:00+00:00")
    item_ids = [item["item_id"] for item in feed["feed_items"]]
    guided_items = [item for item in feed["feed_items"] if item["item_id"] == f"guided_review:{start['review_session_id']}"]
    niles_items = [item for item in feed["feed_items"] if item["lane"] == "niles_creative"]

    assert len(item_ids) == len(set(item_ids))
    assert len(guided_items) == 1
    assert "paused" in guided_items[0]["plain_line"]
    assert niles_items
    assert "album progression staged" in niles_items[0]["plain_line"].lower()


def test_mac_composer_uses_same_switchboard_behavior(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "I got paid $900 from Live Arts MD.", surface="mac_composer")
    session = _load_session(start)

    assert decision["surface"] == "mac_composer"
    assert decision["decision"] == "new_task_interrupt"
    assert decision["detected_action_type"] == "income_payment_log"
    assert session["answer_records"] == []
    assert session["status"] == "paused"
