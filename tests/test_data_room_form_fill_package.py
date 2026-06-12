import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_guided_review as guided
import data_room_form_fill_package as form_fill


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


def _promotion_review(path: Path, *, sensitive: bool = False) -> Path:
    payment_fact = "Direct deposit, Zelle, and forwarded invoices need a safe default."
    payment_proposed = "Winship must decide default payment privacy wording."
    if sensitive:
        payment_fact = "Routing 123456789 and SSN 123-45-6789 must not be exposed."
        payment_proposed = "Keep raw bank account 987654321 details out of model prompts."
    return _write_json(
        path,
        {
            "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
            "authoritative": False,
            "source_artifacts": ["fixture_sleepy_capture.json"],
            "review_records": [
                _record(
                    "privacy:payment_policy",
                    "policy_decision",
                    payment_fact,
                    payment_proposed,
                    risk="Could expose private payment instructions.",
                ),
                _record(
                    "identity:general",
                    "policy_decision",
                    "Identity and sender rules are provisional.",
                    "Winship must decide default identity and persona boundaries.",
                ),
                _record(
                    "expense:labels",
                    "confirm_ready",
                    "Expense categories are provisional business labels.",
                    "Use expense categories as business labels only, pending CPA review.",
                    risk="Could be mistaken for professional classification.",
                    action="confirm",
                ),
            ],
        },
    )


def _start(tmp_path: Path, *, sensitive: bool = False):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json", sensitive=sensitive)
    return guided.process_guided_review_message(
        "Cassandra, coach me through the Data Room.",
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )


def _load_session(response: dict) -> dict:
    return json.loads(Path(response["artifact_refs"]["session_json"]).read_text(encoding="utf-8"))


def _turn_result(package: dict, *, confirmed: bool, question_id: str = "") -> dict:
    question_id = question_id or package["current_question_id"]
    return {
        "schema_version": form_fill.TURN_RESULT_SCHEMA_VERSION,
        "package_id": package["package_id"],
        "review_session_id": package["review_session_id"],
        "turn_id": "turn:fixture",
        "assistant_reply": "That default is conservative and keeps details private.",
        "operator_intent": "answer_candidate",
        "question_id": question_id,
        "question_status": "candidate_pending" if not confirmed else "answered",
        "proposed_answer": {
            "plain_english": "Use manual approval for private payment details.",
            "normalized_decision": "manual approval for private payment details",
            "confidence": "medium",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "requires_winship_confirmation": True,
        "confirmed_by_winship": confirmed,
        "questions_updated": [
            {
                "question_id": question_id,
                "source_refs": ["privacy:payment_policy"],
            }
        ],
        "chat_log_summary_update": "Winship chose a conservative payment privacy default.",
        "next_question_id": "",
        "done_criteria_met": False,
        "safety_flags": dict(form_fill.TURN_SAFETY_FLAGS),
    }


def test_package_contains_all_active_review_questions(tmp_path):
    response = _start(tmp_path)
    session = _load_session(response)

    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    assert package["schema_version"] == "DATA_ROOM_FORM_FILL_PACKAGE_V0"
    assert package["review_session_id"] == session["review_session_id"]
    assert package["total_questions"] == len(session["question_queue"]) == 3
    assert len(package["form_questions"]) == 3
    assert package["current_question"]["question_id"] == session["current_question_id"]
    assert package["current_question_index"] == 1
    assert package["safety_boundaries"]["chatgpt_mutates_openclaw"] is False


def test_package_includes_current_question_and_prior_answers(tmp_path):
    start = _start(tmp_path)
    guided.process_guided_review_message(
        "Direct deposit stays manual approval only.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(start)
    session = guided._find_active_session(guided._review_root(tmp_path / "review"))

    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    assert package["answered_questions"]
    assert "Latest provisional answer" in package["prior_chat_log_summary"]
    assert package["recent_turns"]
    assert package["current_question"]["question_id"] != start["current_question_id"]


def test_prompt_includes_role_rules_schema_and_done_criteria(tmp_path):
    session = _load_session(_start(tmp_path))
    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    prompt = form_fill.render_chatgpt55_form_fill_prompt(package)

    assert "You are helping Winship complete an OpenClaw Data Room setup form." in prompt
    assert "You do not mutate OpenClaw." in prompt
    assert form_fill.TURN_RESULT_SCHEMA_VERSION in prompt
    assert "Done criteria:" in prompt
    assert "Form package:" in prompt


def test_manual_handoff_does_not_claim_live_chatgpt_brain(tmp_path):
    session = _load_session(_start(tmp_path))
    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    assert form_fill.live_chatgpt55_advisory_path_verified() is False
    notification = form_fill.readiness_notification_text(live_chatgpt55_connected=False)
    prompt = form_fill.render_chatgpt55_form_fill_prompt(package)

    assert "My brain for this Data Room lane is ChatGPT 5.5" not in notification
    assert "not pretending ChatGPT is live inside me yet" in notification
    assert "You do not mutate OpenClaw." in prompt


def test_live_notification_wording_requires_verified_live_flag():
    manual = form_fill.readiness_notification_text(live_chatgpt55_connected=False)
    live = form_fill.readiness_notification_text(live_chatgpt55_connected=True)

    assert "My brain for this Data Room lane is ChatGPT 5.5" not in manual
    assert "safe package/handoff lane" in manual
    assert "My brain for this Data Room lane is ChatGPT 5.5" in live


def test_forbidden_sensitive_data_is_redacted(tmp_path):
    session = _load_session(_start(tmp_path, sensitive=True))

    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)
    rendered = json.dumps(package, sort_keys=True)

    assert "123456789" not in rendered
    assert "987654321" not in rendered
    assert "123-45-6789" not in rendered
    assert "[REDACTED_SENSITIVE_DETAIL]" in rendered


def test_artifact_link_normalizer_creates_operator_openable_path(tmp_path):
    session = _load_session(_start(tmp_path))
    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    refs = form_fill.write_data_room_form_fill_artifacts(
        package,
        output_root=tmp_path / "form_fill",
        durable_root=tmp_path / "durable_form_fill",
        export_operator_copy=True,
        operator_report_root=tmp_path / "operator_reports",
        operator_task_id="data_room_form_fill_test",
    )
    operator_copy = refs["operator_openable_copy"]

    assert Path(operator_copy["operator_copy_path"]).is_file()
    assert Path(operator_copy["manifest_path"]).is_file()
    assert Path(operator_copy["open_me_path"]).is_file()
    assert "Open from Windows" in "\n".join(operator_copy["open_instructions"])


def test_turn_result_validates(tmp_path):
    session = _load_session(_start(tmp_path))
    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    validation = form_fill.validate_form_fill_turn_result(_turn_result(package, confirmed=True), package=package)

    assert validation["valid"] is True
    assert validation["can_record_provisional_answer"] is True


def test_unconfirmed_turn_result_does_not_record_answer(tmp_path):
    response = _start(tmp_path)
    session = _load_session(response)
    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    result = form_fill.ingest_form_fill_turn_result_as_candidate(
        _turn_result(package, confirmed=False),
        package=package,
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        output_root=tmp_path / "form_fill",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    updated = _load_session(response)

    assert result["accepted"] is True
    assert result["recorded_provisional_answer"] is False
    assert updated["answer_records"] == []
    assert Path(result["turn_log_path"]).read_text(encoding="utf-8").strip()


def test_confirmed_turn_result_becomes_provisional_answer_only(tmp_path):
    response = _start(tmp_path)
    session = _load_session(response)
    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    result = form_fill.ingest_form_fill_turn_result_as_candidate(
        _turn_result(package, confirmed=True),
        package=package,
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        output_root=tmp_path / "form_fill",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    updated = _load_session(response)

    assert result["recorded_provisional_answer"] is True
    assert updated["answer_records"][0]["answer_source"] == "chatgpt55_form_fill_confirmed"
    assert updated["answer_records"][0]["review_status"] == "answered_pending_promotion"
    assert updated["answer_records"][0]["authoritative"] is False
    assert updated["runtime_policy_changed"] is False
    assert result["confirmed_reference_data_created"] is False
    assert not list(tmp_path.rglob("*confirmed_reference_data*"))


def test_done_criteria_computed_when_questions_resolved(tmp_path):
    response = _start(tmp_path)
    session = _load_session(response)
    now = "2026-06-12T12:01:00+00:00"
    for question in list(session["question_queue"]):
        guided._apply_answer(
            session,
            "Confirmed as a provisional setup answer.",
            surface="test",
            review_root=tmp_path / "review",
            receipt_root=None,
            now=now,
            question_id_override=question["question_id"],
            extra_answer_fields={"affected_record_ids": question["source_record_ids"]},
        )
    guided._persist_session(session, review_root=tmp_path / "review")

    package = form_fill.build_data_room_form_fill_package(session, created_at_utc=FIXED_NOW)

    assert package["done_criteria"]["every_question_answered_skipped_or_deferred"] is True
    assert package["done_criteria"]["all_answered_items_have_question_id_and_source_refs"] is True
    assert package["done_criteria"]["done"] is True


def test_cassandra_command_surface_writes_package_and_prompt(tmp_path, monkeypatch):
    start = _start(tmp_path)
    monkeypatch.setattr(form_fill, "DEFAULT_FORM_FILL_ROOT", tmp_path / "form_fill")
    monkeypatch.setattr(form_fill, "DEFAULT_DURABLE_FORM_FILL_ROOT", tmp_path / "durable_form_fill")
    monkeypatch.setattr(form_fill, "DEFAULT_OPERATOR_REPORT_ROOT", tmp_path / "operator_reports")

    response = guided.process_guided_review_message(
        "Cassandra, open a ChatGPT 5.5 lane for this Data Room form.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )

    refs = response["artifact_refs"]["data_room_form_fill_refs"][-1]
    assert response["reply_text"] == form_fill.EXPECTED_PACKAGE_REPLY
    assert refs["external_model_invoked"] is False
    assert refs["confirmed_reference_data_created"] is False
    assert Path(refs["primary"]["package_path"]).is_file()
    assert Path(refs["primary"]["prompt_path"]).is_file()
    assert Path(refs["durable"]["package_path"]).is_file()
    assert Path(refs["durable"]["prompt_path"]).is_file()
    assert Path(refs["operator_openable_copy"]["operator_copy_path"]).is_file()
    assert "My brain for this Data Room lane is ChatGPT 5.5" not in response["reply_text"]
    assert response["review_session_id"] == start["review_session_id"]
