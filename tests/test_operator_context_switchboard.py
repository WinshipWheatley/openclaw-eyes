import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_guided_review as guided
from operator_context_switchboard import (
    ACTIVE_CONTEXTS_SCHEMA_VERSION,
    SCHEMA_VERSION,
    process_operator_context_switchboard_message,
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


def _load_receipt(ref: str) -> dict:
    return json.loads(Path(ref.split("#", 1)[0]).read_text(encoding="utf-8"))


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

    assert decision["decision"] == "new_task_interrupt"
    assert decision["detected_action_type"] == "income_payment_log"
    assert decision["safety_flags"]["external_calls_performed"] is False
    assert "Data Room review is still open" in decision["operator_visible_reply"]
    assert session["answer_records"] == []
    assert session["status"] == "paused"
    assert event["parsed"]["action_type"] == "income_payment_log"
    assert event["parsed"]["fields"]["amount"] == 900.0
    assert event["parsed"]["fields"]["payer"] == "Live Arts MD"
    assert event["parsed"]["fields"]["invoice_marked_paid"] is False


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


def test_album_routes_to_niles_without_daw_media_or_csv_mutation(tmp_path):
    start = _start(tmp_path)
    decision = _switch(tmp_path, "album")
    session = _load_session(start)
    receipt = _load_receipt(decision["receipt_refs"][0])

    assert decision["decision"] == "new_task_stage"
    assert decision["routed_to_agent"] == "niles"
    assert decision["detected_action_type"] == "niles_album_progression"
    assert "No DAW or media files touched" in decision["operator_visible_reply"]
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
    assert "Data Room review is still open" in decision["operator_visible_reply"]
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

    assert decision["decision"] == "clarification_needed"
    assert "current" in decision["operator_visible_reply"]
    assert "new task" in decision["operator_visible_reply"]
    assert session["answer_records"] == []
    assert session["status"] == "active"


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
