import json
import sys
from pathlib import Path

import pytest

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


def _payment_instructions_review(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
            "authoritative": False,
            "source_artifacts": ["fixture_sleepy_capture.json"],
            "review_records": [
                _record(
                    "business_identity:payment_instructions",
                    "policy_decision",
                    "Operator note includes business identity field label: payment instructions.",
                    "What payment instructions are safe to show by default?",
                    risk="Could expose private payment instructions.",
                ),
                _record(
                    "identity:general",
                    "policy_decision",
                    "Identity and sender rules are provisional.",
                    "When should Winship be used?",
                ),
            ],
        },
    )


def _identity_only_review(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
            "authoritative": False,
            "source_artifacts": ["fixture_sleepy_capture.json"],
            "review_records": [
                _record(
                    "identity:general",
                    "policy_decision",
                    "Identity and sender rules are provisional.",
                    "When should Winship be used?",
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


def _force_current_question(response: dict, question_id: str) -> dict:
    session_path = Path(response["artifact_refs"]["session_json"])
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["current_question_id"] = question_id
    _write_json(session_path, session)
    return session


def _start_identity_question_with_unanswered_payment(tmp_path: Path):
    start = _start(tmp_path)
    session = _load_session(start)
    payment_question = next(question for question in session["question_queue"] if question["category"] == "payment privacy")
    identity_question = next(question for question in session["question_queue"] if question["category"] == "identity/persona policy")
    _force_current_question(start, identity_question["question_id"])
    return payment_question, identity_question


def _trigger_payment_privacy_mismatch(tmp_path: Path):
    payment_question, identity_question = _start_identity_question_with_unanswered_payment(tmp_path)
    mismatch = guided.process_guided_review_message(
        "Direct deposit stays manual approval only. Zelle and check are okay by default.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    return mismatch, payment_question, identity_question


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
    mismatch, payment_question, identity_question = _trigger_payment_privacy_mismatch(tmp_path)
    session = _load_session(mismatch)
    pending = session["pending_interaction"]

    assert "That sounds like a payment/privacy answer" in mismatch["reply_text"]
    assert "this question is about identity/persona" in mismatch["reply_text"]
    assert "I have not recorded it yet" in mismatch["reply_text"]
    assert session["current_question_id"] == identity_question["question_id"]
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []
    assert pending["kind"] == "topic_switch"
    assert pending["original_utterance"] == "Direct deposit stays manual approval only. Zelle and check are okay by default."
    assert pending["original_utterance_hash"].startswith("sha256:")
    assert pending["detected_topic"] == "payment privacy"
    assert pending["current_question_id"] == identity_question["question_id"]
    assert pending["target_question_id"] == payment_question["question_id"]
    assert pending["turns_remaining"] == 3
    assert pending["authoritative"] is False
    assert pending["runtime_policy_changed"] is False
    assert session["coach_interactions"][-1]["command"] == "topic_mismatch_clarification"
    assert session["coach_interactions"][-1]["answer_recorded"] is False
    assert session["runtime_policy_changed"] is False
    assert session["authoritative"] is False

    confirmed = guided.process_guided_review_message(
        "yes",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    confirmed_session = _load_session(confirmed)
    answer = confirmed_session["answer_records"][0]
    receipt = json.loads(Path(answer["receipt_ref"].split("#", 1)[0]).read_text(encoding="utf-8"))

    assert confirmed_session["pending_interaction"] == {}
    assert confirmed_session["current_question_id"] == identity_question["question_id"]
    assert answer["question_id"] == payment_question["question_id"]
    assert answer["question_category"] == "payment privacy"
    assert answer["raw_answer_text"] == "Direct deposit stays manual approval only. Zelle and check are okay by default."
    assert "manual_approval_only" in answer["normalized_answer"]
    assert answer["answer_source"] == "topic_switch_confirmed"
    assert answer["switched_from_question_id"] == identity_question["question_id"]
    assert answer["category_mismatch_resolved"] is True
    assert receipt["raw_answer_text"] == answer["raw_answer_text"]
    assert receipt["answer_source"] == "topic_switch_confirmed"
    assert receipt["category_mismatch_resolved"] is True
    assert receipt["authoritative"] is False
    assert receipt["runtime_policy_changed"] is False


@pytest.mark.parametrize("switch_phrase", ["switch", "yes switch", "yes, switch to payment privacy"])
def test_pending_switch_phrase_variants_record_original_without_loop(tmp_path, switch_phrase):
    case_root = tmp_path / switch_phrase.replace(" ", "_").replace(",", "")
    mismatch, payment_question, _identity_question = _trigger_payment_privacy_mismatch(case_root)
    session = _load_session(mismatch)

    assert session["pending_interaction"]["target_question_id"] == payment_question["question_id"]

    switched = guided.process_guided_review_message(
        switch_phrase,
        review_root=case_root / "review",
        read_model_root=case_root / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    switched_session = _load_session(switched)
    answer = switched_session["answer_records"][0]

    assert "That sounds like a payment/privacy answer" not in switched["reply_text"]
    assert switched_session["pending_interaction"] == {}
    assert answer["question_id"] == payment_question["question_id"]
    assert answer["raw_answer_text"] == "Direct deposit stays manual approval only. Zelle and check are okay by default."
    assert answer["answer_source"] == "topic_switch_confirmed"
    assert "switch" not in answer["raw_answer_text"].lower()


def test_pending_no_clears_without_recording_and_keeps_current_question(tmp_path):
    _mismatch, _payment_question, identity_question = _trigger_payment_privacy_mismatch(tmp_path)

    declined = guided.process_guided_review_message(
        "no",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(declined)

    assert "I did not record that" in declined["reply_text"]
    assert session["pending_interaction"] == {}
    assert session["current_question_id"] == identity_question["question_id"]
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_pending_record_it_here_requires_explicit_acknowledgement(tmp_path):
    _mismatch, _payment_question, identity_question = _trigger_payment_privacy_mismatch(tmp_path)

    recorded = guided.process_guided_review_message(
        "record it here",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(recorded)
    answer = session["answer_records"][0]
    receipt = json.loads(Path(answer["receipt_ref"].split("#", 1)[0]).read_text(encoding="utf-8"))

    assert session["pending_interaction"] == {}
    assert answer["question_id"] == identity_question["question_id"]
    assert answer["question_category"] == "identity/persona policy"
    assert answer["raw_answer_text"] == "Direct deposit stays manual approval only. Zelle and check are okay by default."
    assert answer["answer_source"] == "topic_mismatch_recorded_here"
    assert answer["category_mismatch_acknowledged"] is True
    assert answer["mismatch_original_hint"] == "payment privacy"
    assert receipt["category_mismatch_acknowledged"] is True
    assert receipt["mismatch_original_hint"] == "payment privacy"


def test_pending_switch_without_matching_target_writes_parked_note(tmp_path):
    promotion = _identity_only_review(tmp_path / "review" / "promotion_review.json")
    guided.process_guided_review_message(
        "Cassandra, walk me through the Data Room setup.",
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    mismatch = guided.process_guided_review_message(
        "Direct deposit stays manual approval only. Zelle and check are okay by default.",
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    mismatch_session = _load_session(mismatch)

    assert mismatch_session["pending_interaction"]["target_question_id"] == ""

    parked = guided.process_guided_review_message(
        "yes",
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(parked)
    parked_ref = session["parked_note_refs"][0]
    parked_note = json.loads(Path(parked_ref.split("#", 1)[0]).read_text(encoding="utf-8"))

    assert "I parked that payment/privacy note" in parked["reply_text"]
    assert session["pending_interaction"] == {}
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []
    assert parked_note["authoritative"] is False
    assert parked_note["runtime_policy_changed"] is False
    assert parked_note["confirmed_reference_data_generated"] is False
    assert parked_note["original_utterance_hash"].startswith("sha256:")
    assert parked_note["detected_topic"] == "payment privacy"
    assert parked_note["reason"] == "no_matching_question_in_current_session"
    assert not list((tmp_path / "review").glob("*confirmed_reference*"))


def test_bare_yes_outside_pending_does_not_record_confirmation(tmp_path):
    start = _start(tmp_path)
    first_question_id = start["current_question_id"]

    response = guided.process_guided_review_message(
        "yes",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(response)

    assert response["reply_text"] == "Yes to what? Can you give me the answer in a sentence?"
    assert session["current_question_id"] == first_question_id
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_natural_pending_confirmation_records_candidate_not_confirmation_phrase(tmp_path):
    start = _start(tmp_path)
    first_question_id = start["current_question_id"]

    proposed = guided.process_guided_review_message(
        "let me ramble for a second: direct deposit should stay manual unless trusted clients ask for it.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    proposed_session = _load_session(proposed)

    assert "Here's the thread I'm hearing" in proposed["reply_text"]
    assert "Should I record this as:" in proposed["reply_text"]
    assert proposed_session["pending_interaction"]["kind"] == "answer_candidate"
    assert proposed_session["current_question_id"] == first_question_id
    assert proposed_session["answer_records"] == []
    assert proposed_session["receipt_refs"] == []

    confirmed = guided.process_guided_review_message(
        "yes that’s right",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(confirmed)
    answer = session["answer_records"][0]

    assert session["pending_interaction"] == {}
    assert answer["question_id"] == first_question_id
    assert answer["raw_answer_text"] == "direct deposit should stay manual unless trusted clients ask for it"
    assert "yes" not in answer["raw_answer_text"].lower()
    assert answer["answer_source"] == "natural_candidate_confirmed"
    assert answer["authoritative"] is False
    assert answer["runtime_policy_changed"] is False


def test_natural_yes_variant_without_pending_asks_yes_to_what(tmp_path):
    start = _start(tmp_path)
    first_question_id = start["current_question_id"]

    response = guided.process_guided_review_message(
        "yes that’s right",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(response)

    assert response["reply_text"] == "Yes to what? Can you give me the answer in a sentence?"
    assert session["current_question_id"] == first_question_id
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_pending_candidate_revision_creates_revised_candidate_without_receipt(tmp_path):
    _start(tmp_path)
    guided.process_guided_review_message(
        "let me ramble for a second: use the loose version for clients.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )

    revised = guided.process_guided_review_message(
        "no, but maybe direct deposit is manual-only except for trusted clients who ask.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(revised)

    assert "Should I record this as:" in revised["reply_text"]
    assert "direct deposit is manual-only except for trusted clients who ask" in revised["reply_text"]
    assert session["pending_interaction"]["kind"] == "answer_candidate"
    assert session["pending_interaction"]["candidate_text"] == "direct deposit is manual-only except for trusted clients who ask"
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_pending_candidate_conditional_answer_stays_unrecorded_until_confirmed(tmp_path):
    _start(tmp_path)
    guided.process_guided_review_message(
        "let me ramble for a second: direct deposit is usually manual approval only.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )

    conditional = guided.process_guided_review_message(
        "for new clients no, for trusted clients yes",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(conditional)

    assert "Should I record this as:" in conditional["reply_text"]
    assert "for new clients no, for trusted clients yes" in conditional["reply_text"].lower()
    assert session["pending_interaction"]["kind"] == "answer_candidate"
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_bare_conditional_answer_asks_for_condition_without_recording(tmp_path):
    start = _start(tmp_path)

    response = guided.process_guided_review_message(
        "sometimes",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(response)

    assert response["reply_text"] == "What condition should decide it?"
    assert session["current_question_id"] == start["current_question_id"]
    assert session["pending_interaction"]["kind"] == "condition_request"
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_pending_condition_request_accepts_condition_then_requires_confirmation(tmp_path):
    start = _start(tmp_path)
    first_question_id = start["current_question_id"]

    guided.process_guided_review_message(
        "it depends",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )

    candidate = guided.process_guided_review_message(
        "only for trusted clients",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    candidate_session = _load_session(candidate)

    assert "Should I record this as: only for trusted clients?" in candidate["reply_text"]
    assert candidate_session["pending_interaction"]["kind"] == "answer_candidate"
    assert candidate_session["pending_interaction"]["candidate_text"] == "only for trusted clients"
    assert candidate_session["current_question_id"] == first_question_id
    assert candidate_session["answer_records"] == []
    assert candidate_session["receipt_refs"] == []

    confirmed = guided.process_guided_review_message(
        "yes that's right",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:03:00+00:00",
    )
    session = _load_session(confirmed)

    assert session["pending_interaction"] == {}
    assert session["answer_records"][0]["raw_answer_text"] == "only for trusted clients"
    assert session["answer_records"][0]["question_id"] == first_question_id


@pytest.mark.parametrize(
    "text,expected",
    [
        ("eli5", "ELI5"),
        ("explain it like I’m five", "ELI5"),
        ("give me an analogy", "Analogy"),
        ("what does that mean?", "My recommendation:"),
        ("what does that mean exactly?", "My recommendation:"),
        ("hmm what do you think?", "My recommendation:"),
        ("I don't know", "My recommendation:"),
        ("examples", "Example answers:"),
    ],
)
def test_natural_explanation_variants_do_not_record_answers(tmp_path, text, expected):
    start = _start(tmp_path)

    response = guided.process_guided_review_message(
        text,
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(response)

    assert expected in response["reply_text"]
    assert session["current_question_id"] == start["current_question_id"]
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_thought_dump_proposes_candidate_without_receipt(tmp_path):
    start = _start(tmp_path)

    response = guided.process_guided_review_message(
        "I don’t know, but trusted repeat clients can use Zelle and everyone else should stay manual.",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(response)

    assert "Here's the thread I'm hearing" in response["reply_text"]
    assert "Should I record this as:" in response["reply_text"]
    assert session["current_question_id"] == start["current_question_id"]
    assert session["pending_interaction"]["kind"] == "answer_candidate"
    assert session["answer_records"] == []
    assert session["receipt_refs"] == []


def test_pending_topic_switch_natural_confirmation_records_original_under_target(tmp_path):
    _mismatch, payment_question, _identity_question = _trigger_payment_privacy_mismatch(tmp_path)

    confirmed = guided.process_guided_review_message(
        "yes, put it under payment privacy",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    session = _load_session(confirmed)
    answer = session["answer_records"][0]

    assert session["pending_interaction"] == {}
    assert answer["question_id"] == payment_question["question_id"]
    assert answer["question_category"] == "payment privacy"
    assert answer["raw_answer_text"] == "Direct deposit stays manual approval only. Zelle and check are okay by default."
    assert answer["answer_source"] == "topic_switch_confirmed"


def test_payment_instructions_sequence_records_payment_privacy_not_identity(tmp_path):
    promotion = _payment_instructions_review(tmp_path / "review" / "promotion_review.json")
    review_root = tmp_path / "review"
    read_model_root = tmp_path / "read_models"

    start = guided.process_guided_review_message(
        "Cassandra, walk me through the Data Room setup.",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    start_session = _load_session(start)
    first_question = start_session["question_queue"][0]

    assert first_question["question_text"].startswith("What payment instructions are safe to show by default?")
    assert first_question["category"] == "payment privacy"
    assert first_question["coach_card"]["category"] == "payment privacy"
    assert "direct deposit" in first_question["coach_card"]["recommended_default"].lower()
    assert "winship as the default business identity" not in start["reply_text"].lower()

    recommended = guided.process_guided_review_message(
        "use your recommendation",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    recommended_session = _load_session(recommended)
    first_answer = recommended_session["answer_records"][0]
    first_receipt = json.loads(Path(first_answer["receipt_ref"].split("#", 1)[0]).read_text(encoding="utf-8"))

    assert first_answer["question_id"] == first_question["question_id"]
    assert first_answer["question_category"] == "payment privacy"
    assert first_answer["selected_option_id"] == "recommended_default"
    assert first_answer["legal_review_recommended"] is False
    assert first_receipt["question_category"] == "payment privacy"
    assert first_receipt["legal_review_recommended"] is False
    assert "safer payment privacy default" in first_answer["raw_answer_text"].lower()

    revised = guided.process_guided_review_message(
        "revise previous",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    revised_session = _load_session(revised)
    assert revised_session["current_question_id"] == first_question["question_id"]
    assert revised_session["answer_records"][0]["superseded"] is True
    assert "Question 1 of 2 - payment privacy" in revised["reply_text"]

    corrected = guided.process_guided_review_message(
        "Direct deposit stays manual approval only. Zelle and check are okay by default.",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:03:00+00:00",
    )
    corrected_session = _load_session(corrected)
    active_answers = [answer for answer in corrected_session["answer_records"] if not answer.get("superseded")]
    corrected_answer = active_answers[0]
    corrected_receipt = json.loads(Path(corrected_answer["receipt_ref"].split("#", 1)[0]).read_text(encoding="utf-8"))

    assert "That sounds like a payment/privacy answer" not in corrected["reply_text"]
    assert "Recorded: direct deposit stays manual approval only; Zelle and check are okay by default (provisional)." in corrected["reply_text"]
    assert corrected_answer["question_id"] == first_question["question_id"]
    assert corrected_answer["question_category"] == "payment privacy"
    assert corrected_answer["legal_review_recommended"] is False
    assert corrected_receipt["question_category"] == "payment privacy"
    assert corrected_receipt["authoritative"] is False
    assert corrected_receipt["runtime_policy_changed"] is False
    assert corrected_receipt["external_calls_performed"] is False
    assert corrected_receipt["approval_created"] is False
    assert corrected_receipt["invoice_or_ledger_mutated"] is False
    assert "routing number" not in corrected_answer["raw_answer_text"].lower()
    assert "account number" not in corrected_answer["raw_answer_text"].lower()


def test_payment_answer_still_prompts_mismatch_for_true_identity_question(tmp_path):
    promotion = _payment_instructions_review(tmp_path / "review" / "promotion_review.json")
    review_root = tmp_path / "review"
    read_model_root = tmp_path / "read_models"

    guided.process_guided_review_message(
        "Cassandra, walk me through the Data Room setup.",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    recommended = guided.process_guided_review_message(
        "use your recommendation",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session_before = _load_session(recommended)
    identity_question_id = session_before["current_question_id"]
    identity_question = next(
        question for question in session_before["question_queue"] if question["question_id"] == identity_question_id
    )
    assert identity_question["category"] == "identity/persona policy"

    mismatch = guided.process_guided_review_message(
        "Direct deposit stays manual approval only. Zelle and check are okay by default.",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:03:00+00:00",
    )
    session = _load_session(mismatch)

    assert "That sounds like a payment/privacy answer" in mismatch["reply_text"]
    assert "this question is about identity/persona" in mismatch["reply_text"]
    assert "I have not recorded it yet" in mismatch["reply_text"]
    assert session["current_question_id"] == identity_question_id
    assert len(session["answer_records"]) == 1
    assert len(session["receipt_refs"]) == 1
    assert session["pending_interaction"]["kind"] == "topic_switch"
    assert session["pending_interaction"]["target_question_id"] == ""
    assert session["coach_interactions"][-1]["command"] == "topic_mismatch_clarification"
    assert session["coach_interactions"][-1]["answer_recorded"] is False


def test_payment_contact_trust_gate_stays_payment_privacy_without_legal_flag(tmp_path):
    review_root = tmp_path / "review"
    read_model_root = tmp_path / "read_models"
    promotion = _write_json(
        review_root / "promotion_review.json",
        {
            "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
            "authoritative": False,
            "source_artifacts": ["fixture_payment_contact_review.json"],
            "review_records": [
                _record(
                    "business_identity:payment_contact_details",
                    "policy_decision",
                    "Payment/contact details may need trust-gated handling.",
                    "Which payment/contact details are trust-gated?",
                    risk="Could expose payment or contact details too broadly.",
                ),
                _record(
                    "identity:general",
                    "policy_decision",
                    "Identity and sender rules are provisional.",
                    "When should Winship be used?",
                ),
            ],
        },
    )

    start = guided.process_guided_review_message(
        "Cassandra, walk me through the Data Room setup.",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )
    session = _load_session(start)
    first_question = session["question_queue"][0]

    assert first_question["category"] == "payment privacy"
    assert first_question["coach_card"]["category"] == "payment privacy"
    assert first_question["coach_card"]["legal_review_recommended"] is False

    answer = guided.process_guided_review_message(
        "use your recommendation",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        promotion_review_path=promotion,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    answer_session = _load_session(answer)
    answer_record = answer_session["answer_records"][0]

    assert answer_record["question_category"] == "payment privacy"
    assert answer_record["legal_review_recommended"] is False
    assert answer_record["authoritative"] is False


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
