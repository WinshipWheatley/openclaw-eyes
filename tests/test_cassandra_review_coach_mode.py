import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_guided_review as guided
from cassandra_review_coach import build_coach_card, render_coach_reply
from cassandra_review_coach_packs import COACH_PACKS_BY_CATEGORY, REQUIRED_COACH_CATEGORIES
from operator_universal_intake import try_process_surface_operator_intake
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
            "source_artifacts": ["fixture_sleepy_capture.json"],
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
                    "identity:clara_reid",
                    "policy_decision",
                    "Clara Reid may help prepare business language.",
                    "Winship must decide Clara Reid public-facing boundaries.",
                ),
                _record(
                    "identity:niles_technical_director",
                    "policy_decision",
                    "Niles is provisional technical director context.",
                    "Winship must decide when Niles can be public-facing.",
                ),
                _record(
                    "identity:log_rhythm_records",
                    "do_not_import",
                    "Log Rhythm Records is old historical context.",
                    "Do not import Log Rhythm Records into active routing.",
                    action="reject",
                ),
                _record(
                    "rate:live_arts",
                    "needs_correction",
                    "Live Arts rates mix service types.",
                    "Split rates by service before promotion.",
                    action="revise",
                ),
                _record(
                    "client:capital_hilton",
                    "needs_source",
                    "Capital Hilton needs client/payer/contact role review.",
                    "Keep roles separate until Winship confirms them.",
                    action="source needed",
                ),
                _record(
                    "invoice:numbering",
                    "policy_decision",
                    "Invoice numbering is inconsistent.",
                    "Keep old invoices as history and choose one future convention.",
                ),
                _record(
                    "expense:labels",
                    "confirm_ready",
                    "Expense categories are provisional business labels.",
                    "Use expense categories as business labels only, pending CPA review.",
                    risk="Could be mistaken for professional classification.",
                    action="confirm",
                ),
                _record(
                    "venue:list",
                    "needs_correction",
                    "Venue list mixes places and business contexts.",
                    "Keep venues separate from mileage destinations and client records.",
                    action="revise",
                ),
                _record(
                    "blocked:raw_private_note",
                    "do_not_import",
                    "A raw private note should not be imported.",
                    "Keep raw private notes blocked from active import.",
                    action="reject",
                ),
                _record(
                    "general:data_room",
                    "policy_decision",
                    "OpenClaw needs a conservative default for ambiguous business details.",
                    "Choose the conservative default and keep ambiguous details provisional.",
                ),
            ],
        },
    )


def _start(tmp_path: Path, text: str = "Cassandra, coach me through the Data Room."):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json")
    return guided.process_guided_review_message(
        text,
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )


def _load_session(response: dict) -> dict:
    return json.loads(Path(response["artifact_refs"]["session_json"]).read_text(encoding="utf-8"))


def test_coach_packs_exist_for_all_required_categories():
    assert set(REQUIRED_COACH_CATEGORIES) <= set(COACH_PACKS_BY_CATEGORY)
    for category in REQUIRED_COACH_CATEGORIES:
        pack = COACH_PACKS_BY_CATEGORY[category]
        assert pack["schema_version"] == "REVIEW_COACH_PACK_V0"
        assert pack["plain_context"]
        assert pack["why_it_matters"]
        assert pack["recommended_default"]
        assert 2 <= len(pack["option_templates"]) <= 4
        assert pack["example_answers"]
        assert isinstance(pack["cpa_review_recommended"], bool)
        assert isinstance(pack["legal_review_recommended"], bool)


def test_coach_start_phrase_enables_coach_mode(tmp_path):
    response = _start(tmp_path)
    session = _load_session(response)

    assert response["status"] == "active"
    assert session["coach_mode_enabled"] is True
    assert session["coach_start_phrase_detected"] is True
    assert session["question_queue"][0]["coach_card"]["schema_version"] == "REVIEW_COACH_CARD_V0"


def test_telegram_coach_reply_is_concise_and_one_question_only(tmp_path):
    response = _start(tmp_path)
    reply = response["reply_text"]

    assert "Question 1 of" in reply
    assert "Question 2" not in reply
    assert "schema_version" not in reply
    assert "|" not in reply
    assert len(reply) < 1400
    assert "Commands: why, recommend, examples" in reply


def test_why_recommend_and_examples_do_not_record_answers(tmp_path):
    start = _start(tmp_path)
    review_root = tmp_path / "review"
    read_model_root = tmp_path / "read_models"
    first_question_id = start["current_question_id"]

    why = guided.process_guided_review_message(
        "why?",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    recommend = guided.process_guided_review_message(
        "what do you recommend?",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    examples = guided.process_guided_review_message(
        "examples",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:03:00+00:00",
    )
    session = _load_session(examples)

    assert "Why it matters:" in why["reply_text"]
    assert "My recommendation:" in recommend["reply_text"]
    assert "Example answers:" in examples["reply_text"]
    assert session["current_question_id"] == first_question_id
    assert session["answer_records"] == []
    assert [item["command"] for item in session["coach_interactions"]] == ["why", "recommend", "examples"]


def test_use_your_recommendation_records_default_option(tmp_path):
    _start(tmp_path)
    response = guided.process_guided_review_message(
        "use your recommendation",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(response)
    answer = session["answer_records"][0]

    assert response["progress"]["answered"] == 1
    assert answer["selected_option_id"] == "recommended_default"
    assert answer["review_status"] == "answered_pending_promotion"
    assert answer["authoritative"] is False
    assert answer["runtime_policy_changed"] is False


def test_revise_previous_supersedes_old_answer_and_rewinds(tmp_path):
    _start(tmp_path)
    first = guided.process_guided_review_message(
        "use your recommendation",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    first_session = _load_session(first)
    first_question_id = first_session["answer_records"][0]["question_id"]

    revised = guided.process_guided_review_message(
        "revise previous",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    revised_session = _load_session(revised)

    assert revised_session["current_question_id"] == first_question_id
    assert revised_session["answer_records"][0]["superseded"] is True
    assert revised_session["answer_records"][0]["active_for_promotion"] is False
    assert revised_session["answer_records"][0]["review_status"] == "superseded"
    assert "old answer stays in the audit trail" in revised["reply_text"]

    corrected = guided.process_guided_review_message(
        "Keep this manual-only until I say otherwise.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:03:00+00:00",
    )
    corrected_session = _load_session(corrected)
    active_answers = [a for a in corrected_session["answer_records"] if not a.get("superseded")]

    assert len(corrected_session["answer_records"]) == 2
    assert len(active_answers) == 1
    assert active_answers[0]["question_id"] == first_question_id


def test_direct_deposit_answer_is_not_recorded_against_identity_question(tmp_path):
    _start(tmp_path)
    first = guided.process_guided_review_message(
        "use your recommendation",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    first_session = _load_session(first)
    identity_question_id = first_session["current_question_id"]
    identity_question = next(
        question for question in first_session["question_queue"] if question["question_id"] == identity_question_id
    )

    assert identity_question["category"] == "identity/persona policy"

    mismatch = guided.process_guided_review_message(
        "Direct deposit stays manual approval only. Zelle and check are okay by default.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(mismatch)

    assert "That sounds like a payment/privacy answer" in mismatch["reply_text"]
    assert "we're currently reviewing identity/persona" in mismatch["reply_text"]
    assert "I have not recorded it yet" in mismatch["reply_text"]
    assert session["current_question_id"] == identity_question_id
    assert len(session["answer_records"]) == 1
    assert len(session["receipt_refs"]) == 1
    assert session["answered_questions"] == first_session["answered_questions"]
    assert all(
        "Direct deposit stays manual approval only" not in answer["raw_answer_text"]
        for answer in session["answer_records"]
    )
    assert session["coach_interactions"][-1]["command"] == "topic_mismatch_clarification"
    assert session["coach_interactions"][-1]["answer_recorded"] is False
    assert session["runtime_policy_changed"] is False
    assert session["authoritative"] is False


def test_cpa_and_legal_flags_propagate_to_answers_and_receipts(tmp_path):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json")
    rates = guided.process_guided_review_message(
        "review rates and venues",
        review_root=tmp_path / "rates_review",
        read_model_root=tmp_path / "rates_read_models",
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    rates_answer = guided.process_guided_review_message(
        "use your recommendation",
        review_root=tmp_path / "rates_review",
        read_model_root=tmp_path / "rates_read_models",
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    rates_session = _load_session(rates_answer)
    rates_record = rates_session["answer_records"][0]
    rates_receipt = json.loads(Path(rates_record["receipt_ref"].split("#", 1)[0]).read_text(encoding="utf-8"))

    assert rates["status"] == "active"
    assert rates_record["cpa_review_recommended"] is True
    assert rates_record["needs_professional_review"] is True
    assert rates_receipt["cpa_review_recommended"] is True
    assert rates_receipt["authoritative"] is False
    assert rates_receipt["runtime_policy_changed"] is False

    persona = guided.process_guided_review_message(
        "review Clara Reid rules",
        review_root=tmp_path / "persona_review",
        read_model_root=tmp_path / "persona_read_models",
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    persona_answer = guided.process_guided_review_message(
        "use your recommendation",
        review_root=tmp_path / "persona_review",
        read_model_root=tmp_path / "persona_read_models",
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    persona_session = _load_session(persona_answer)
    persona_record = persona_session["answer_records"][0]
    persona_receipt = json.loads(Path(persona_record["receipt_ref"].split("#", 1)[0]).read_text(encoding="utf-8"))

    assert persona["status"] == "active"
    assert persona_record["legal_review_recommended"] is True
    assert persona_record["needs_professional_review"] is True
    assert persona_receipt["legal_review_recommended"] is True
    assert persona_receipt["external_calls_performed"] is False


def test_no_tax_or_legal_advice_claims_are_emitted():
    card = build_coach_card(
        {
            "question_id": "q:expense",
            "category": "expense categories",
            "question_text": "How should expense labels be treated?",
        }
    )
    reply = render_coach_reply(card, "question")
    lowered = reply.lower()

    assert "tax advice" not in lowered
    assert "legal advice" not in lowered
    assert "cpa review recommended" in lowered


def test_done_writes_promotion_prompt_with_professional_review_flags(tmp_path):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json")
    guided.process_guided_review_message(
        "review rates and venues",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    guided.process_guided_review_message(
        "use your recommendation",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    done = guided.process_guided_review_message(
        "done",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    prompt = Path(done["artifact_refs"]["promotion_prompt"]).read_text(encoding="utf-8")

    assert done["status"] == "completed"
    assert "Active coach answers:" in prompt
    assert "Professional-review flags:" in prompt
    assert "CPA review recommended" in prompt
    assert "Keep CPA/legal-flagged items provisional pending professional review." in prompt
    assert "Ignore superseded answers." in prompt


def test_pre_coach_session_json_still_loads(tmp_path):
    review_root = tmp_path / "review"
    session_id = "data_room_review:legacy"
    legacy = {
        "schema_version": "REVIEW_SESSION_V0",
        "review_session_id": session_id,
        "topic": "data_room_reference_review",
        "topic_display_name": "OpenClaw Data Room / Reference Data Review",
        "created_at_utc": FIXED_NOW,
        "updated_at_utc": FIXED_NOW,
        "operator": "Winship",
        "surface": "telegram",
        "status": "active",
        "question_queue": [
            {
                "schema_version": "REVIEW_QUESTION_V0",
                "question_id": "review_question:legacy",
                "category": "data room review",
                "priority": 90,
                "question_text": "Legacy question?",
                "answer_status": "unanswered",
                "authoritative": False,
            }
        ],
        "current_question_id": "review_question:legacy",
        "answered_questions": [],
        "skipped_questions": [],
        "deferred_questions": [],
        "unresolved_questions": ["review_question:legacy"],
        "answer_records": [],
        "generated_prompt_refs": [],
        "receipt_refs": [],
        "watch_desk_refs": [],
        "authoritative": False,
        "runtime_policy_changed": False,
    }
    _write_json(review_root / "data_room_guided_review_session_data_room_review_legacy.json", legacy)
    _write_json(
        review_root / "data_room_guided_review_active_session.json",
        {"schema_version": "guided_review_active_session_index_v0", "review_session_id": session_id},
    )

    response = guided.process_guided_review_message(
        "why",
        review_root=review_root,
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(response)

    assert response["handled"] is True
    assert session["review_session_id"] == session_id
    assert session["coach_mode_enabled"] is True
    assert session["answer_records"] == []


def test_exact_send_and_guardian_approval_text_not_intercepted(tmp_path):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json")
    _start(tmp_path)

    for text in [
        "Approve exact send request exact_send_authority_request:abc123",
        "Guardian approval: approve this.",
    ]:
        assert (
            guided.process_guided_review_message(
                text,
                review_root=tmp_path / "review",
                read_model_root=tmp_path / "read_models",
                promotion_review_path=promotion,
                generated_at_utc="2026-06-12T12:01:00+00:00",
            )
            is None
        )


def test_universal_intake_messages_are_not_swallowed_by_active_review(tmp_path):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json")
    _start(tmp_path)

    assert (
        guided.process_guided_review_message(
            "I got paid $900 from Live Arts MD.",
            review_root=tmp_path / "review",
            read_model_root=tmp_path / "read_models",
            promotion_review_path=promotion,
            generated_at_utc="2026-06-12T12:01:00+00:00",
        )
        is None
    )

    intake = try_process_surface_operator_intake(
        "I got paid $900 from Live Arts MD.",
        surface="telegram",
        read_model_root=tmp_path / "intake_read_models",
        receipt_root=tmp_path / "intake_receipts",
        received_at_utc="2026-06-12T12:02:00+00:00",
    )
    assert intake is not None
    assert intake["action_type"] == "income_payment_log"


def test_watch_desk_has_one_guided_review_item_with_coach_state(tmp_path):
    response = _start(tmp_path)
    guided.process_guided_review_message(
        "use your recommendation",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )

    first = build_watch_desk_feed(
        read_model_root=tmp_path / "read_models",
        task_root=tmp_path / "tasks",
        generated_at=FIXED_NOW,
    )
    second = build_watch_desk_feed(
        read_model_root=tmp_path / "read_models",
        task_root=tmp_path / "tasks",
        generated_at=FIXED_NOW,
    )
    guided_items = [item for item in first["feed_items"] if item["item_id"].startswith("guided_review:")]

    assert response["watch_desk_refs"]
    assert len(guided_items) == 1
    assert guided_items[0]["state"]["coach_mode"] is True
    assert guided_items[0]["state"]["answered_count"] == 1
    assert guided_items[0]["state"]["cpa_flagged_count"] == 0
    assert guided_items[0]["state"]["legal_flagged_count"] == 0
    assert [item["item_id"] for item in first["feed_items"]] == [item["item_id"] for item in second["feed_items"]]
