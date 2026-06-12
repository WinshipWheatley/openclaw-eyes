import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_brain
import cassandra_guided_review as guided
from operator_universal_intake import try_process_surface_operator_intake
from watch_desk_feed import build_watch_desk_feed


FIXED_NOW = "2026-06-12T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _record(record_id, category, fact, proposed, *, confidence="medium", risk="wrong runtime behavior", action="defer"):
    return {
        "record_id": record_id,
        "provisional_marker": "*",
        "authoritative": False,
        "promotion_requires_winship_confirmation": True,
        "review_category": category,
        "provisional_fact": f"* {fact}",
        "proposed_promoted_value": f"* {proposed}",
        "confidence": confidence,
        "source": "fixture_promotion_review.json#review_records",
        "risk_if_wrong": risk,
        "recommended_action": action,
    }


def _promotion_review(path: Path) -> Path:
    payload = {
        "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
        "authoritative": False,
        "source_artifacts": [
            "/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_sleepy_capture_v0.json"
        ],
        "review_records": [
            _record(
                "business_identity:payment_contact_exposure_policy",
                "policy_decision",
                "Phone, address, Zelle, and direct deposit exposure need trust-tiered review.",
                "Winship must define which payment instructions are safe by default and which require manual approval.",
                confidence="high",
                risk="Could expose private payment details.",
                action="defer",
            ),
            _record(
                "identity:clara_reid",
                "policy_decision",
                "Clara Reid can eventually send invoices but not as default for every client.",
                "Winship must decide Clara signature, sender, and original-invoice vs follow-up policy.",
                action="defer",
            ),
            _record(
                "identity:niles_technical_director",
                "policy_decision",
                "Niles is a provisional technical director persona.",
                "Winship must define when Niles can be public-facing.",
                action="defer",
            ),
            _record(
                "identity:log_rhythm_records_off_limits",
                "do_not_import",
                "Log Rhythm Records is off-limits, historical, and not active.",
                "Do not import Log Rhythm Records into active identity/client/sender/routing logic.",
                confidence="high",
                risk="Could revive a historical identity.",
                action="reject",
            ),
            _record(
                "rate:live_arts_multiple_services",
                "needs_correction",
                "Live Arts Maryland has speaker rental and A/V support mixed together.",
                "Split Live Arts service records by source and service type.",
                risk="Wrong service grouping could create wrong invoices.",
                action="revise",
            ),
            _record(
                "client:capital_hilton",
                "needs_source",
                "Capital Hilton is a current stable gig but needs rate/service/payment rhythm.",
                "Promote only after Winship confirms rate, service, rhythm, Annette, and Will contact handling.",
                confidence="medium-high",
                risk="Wrong assumptions could affect a current client.",
                action="source needed",
            ),
            _record(
                "invoice_policy:numbering_and_filename",
                "policy_decision",
                "Invoice numbering is inconsistent; WL-YYYY-#### is proposed only.",
                "Winship must decide whether to reset future numbering and map old invoices.",
                action="defer",
            ),
            _record(
                "expense_categories:provisional_labels",
                "confirm_ready",
                "Expense categories are provisional business labels only.",
                "Use expense categories as business labels only, not tax logic.",
                risk="Could be mistaken for tax advice.",
                action="confirm",
            ),
            _record(
                "venues:provisional_list",
                "needs_correction",
                "Venue list mixes venues, mileage destinations, and client contexts.",
                "Promote only reviewed venues and keep mileage destinations separate.",
                action="revise",
            ),
        ],
    }
    return _write_json(path, payload)


def _start(tmp_path: Path, text: str = "Cassandra, let's go over the Data Room."):
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


def test_data_room_session_creation_loads_questions_and_returns_first_question(tmp_path):
    response = _start(tmp_path)
    session = _load_session(response)

    assert response["handled"] is True
    assert response["status"] == "active"
    assert response["review_session_id"].startswith("data_room_review:")
    assert "Cool. I found 9 provisional Data Room review items" in response["reply_text"]
    assert "Question 1 of 9" in response["reply_text"]
    assert session["schema_version"] == "REVIEW_SESSION_V0"
    assert session["authoritative"] is False
    assert session["runtime_policy_changed"] is False
    assert len(session["question_queue"]) == 9
    first_question = session["question_queue"][0]
    assert first_question["schema_version"] == "REVIEW_QUESTION_V0"
    assert first_question["category"] == "payment privacy"
    assert "direct deposit" in first_question["question_text"].lower()


def test_question_flow_records_answers_skip_defer_summary_and_done_artifacts(tmp_path):
    start = _start(tmp_path)
    review_root = tmp_path / "review"
    read_model_root = tmp_path / "read_models"

    answer = guided.process_guided_review_message(
        "Direct deposit stays manual approval only; Zelle is okay for trusted clients.",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session = _load_session(answer)
    assert answer["progress"]["answered"] == 1
    assert session["answer_records"][0]["schema_version"] == "REVIEW_ANSWER_V0"
    assert session["answer_records"][0]["authoritative"] is False
    assert session["answer_records"][0]["runtime_policy_changed"] is False
    assert "manual_approval_only" in session["answer_records"][0]["normalized_answer"]
    assert Path(session["answer_records"][0]["receipt_ref"].split("#", 1)[0]).is_file()

    skipped = guided.process_guided_review_message(
        "skip",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:02:00+00:00",
    )
    assert skipped["progress"]["skipped"] == 1

    deferred = guided.process_guided_review_message(
        "defer",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:03:00+00:00",
    )
    assert deferred["progress"]["deferred"] == 1

    nexted = guided.process_guided_review_message(
        "next question",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:04:00+00:00",
    )
    assert nexted["progress"]["skipped"] == 2

    summary = guided.process_guided_review_message(
        "summarize",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:05:00+00:00",
    )
    assert "Data Room review progress:" in summary["reply_text"]

    done = guided.process_guided_review_message(
        "done",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:06:00+00:00",
    )
    assert done["status"] == "completed"
    assert Path(done["artifact_refs"]["operator_markdown"]).is_file()
    prompt_path = Path(done["artifact_refs"]["promotion_prompt"])
    assert prompt_path.is_file()
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_V0" in prompt
    assert done["artifact_refs"]["session_json"] in prompt
    assert "Keep unresolved, skipped, deferred" in prompt
    assert "Do not import Log Rhythm Records" in prompt


def test_safety_redacts_sensitive_patterns_and_never_promotes(tmp_path):
    response = _start(tmp_path)
    review_root = tmp_path / "review"
    read_model_root = tmp_path / "read_models"

    answered = guided.process_guided_review_message(
        "Use routing number 123456789 and account 9876543210 for direct deposit.",
        surface="telegram",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc="2026-06-12T12:01:00+00:00",
    )
    session_text = Path(answered["artifact_refs"]["session_json"]).read_text(encoding="utf-8")
    session = json.loads(session_text)
    receipt_text = Path(session["answer_records"][0]["receipt_ref"].split("#", 1)[0]).read_text(encoding="utf-8")

    assert "123456789" not in session_text
    assert "9876543210" not in session_text
    assert "123456789" not in receipt_text
    assert "9876543210" not in receipt_text
    assert session["answer_records"][0]["sensitive_detail_redacted"] is True
    assert all(record["authoritative"] is False for record in session["answer_records"])
    assert session["runtime_policy_changed"] is False
    assert not list(review_root.glob("*confirmed_reference_data*"))
    assert any("Log Rhythm Records" in q["question_text"] for q in session["question_queue"])
    assert any("direct deposit" in q["question_text"].lower() for q in session["question_queue"])
    assert answered["safety_flags"]["external_calls_performed"] is False
    assert answered["safety_flags"]["approval_created"] is False
    assert answered["safety_flags"]["invoice_or_ledger_mutated"] is False


def test_routing_recognizes_guided_review_without_swallowing_generic_or_exact_send(tmp_path, monkeypatch):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json")
    logged = {}

    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda query, packet: "event:test")
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None)
    monkeypatch.setattr(cassandra_brain, "answer_date_awareness_query", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None)

    def capture_log(user_text, replies, route="llm", metadata=None):
        logged["route"] = route
        logged["metadata"] = metadata or {}

    monkeypatch.setattr(cassandra_brain, "_log_conversation", capture_log)
    replies = cassandra_brain.handle(
        "Cassandra, let's go over the Data Room.",
        session={
            "skip_followup_check": True,
            "guided_review_root": tmp_path / "review",
            "guided_review_read_model_root": tmp_path / "read_models",
            "guided_review_promotion_review_path": promotion,
            "received_at_utc": FIXED_NOW,
        },
    )

    assert len(replies) == 1
    assert "Question 1 of 9" in replies[0]
    assert logged["route"] == "guided_review_session"
    assert logged["metadata"]["runtime_policy_changed"] is False

    assert guided.process_guided_review_message(
        "hello Cassandra",
        review_root=tmp_path / "fresh_review",
        promotion_review_path=promotion,
    ) is None
    assert guided.process_guided_review_message(
        "Approve exact send request abc123",
        review_root=tmp_path / "review",
        promotion_review_path=promotion,
    ) is None

    income = try_process_surface_operator_intake(
        "I got paid $900 from Live Arts MD.",
        surface="telegram",
        read_model_root=tmp_path / "intake_read_models",
        receipt_root=tmp_path / "intake_receipts",
        received_at_utc=FIXED_NOW,
    )
    assert income is not None
    assert income["action_type"] == "income_payment_log"


def test_mac_composer_callable_contract_returns_guided_review_response(tmp_path):
    promotion = _promotion_review(tmp_path / "review" / "promotion_review.json")

    response = guided.process_guided_review_message(
        "review invoice policy",
        surface="mac_composer",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion,
        generated_at_utc=FIXED_NOW,
    )

    assert response["handled"] is True
    assert response["status"] == "active"
    assert response["artifact_refs"]["session_json"]
    assert response["safety_flags"]["external_calls_performed"] is False
    session = _load_session(response)
    assert session["surface"] == "mac_composer"
    assert all(
        any(term in q["question_text"].lower() for term in ("invoice", "payment", "payee", "direct deposit"))
        for q in session["question_queue"]
    )


def test_active_session_appears_in_watch_desk_without_duplicates(tmp_path):
    response = _start(tmp_path)

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

    assert len(guided_items) == 1
    assert "Data Room review in progress:" in guided_items[0]["plain_line"]
    assert guided_items[0]["source_receipt_ref"].endswith("#session")
    assert guided_items[0]["push_allowed"] is False
    assert [item["item_id"] for item in first["feed_items"]] == [item["item_id"] for item in second["feed_items"]]
