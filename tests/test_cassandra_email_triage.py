import builtins
import inspect
import json
import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _metadata(**overrides):
    data = {
        "message_id": "msg-1",
        "thread_id": "thread-1",
        "from_name": "Promo Desk",
        "from_email": "Deals <DEALS@Promo.Example.COM>",
        "subject": "Spring equipment sale",
        "snippet": "Save 20 percent on stands and cases this week.",
        "labels": ["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        "body_text": "PRIVATE BODY CONTENT SHOULD NOT BE USED",
    }
    data.update(overrides)
    return data


def _candidate_metadata(**overrides):
    data = _metadata(**overrides)
    data.pop("body_text", None)
    return data


def test_valid_synthetic_metadata_builds_clear_operator_prompt():
    import cassandra_email_triage as triage

    prompt = triage.build_email_triage_operator_prompt(_metadata())

    assert "Cassandra email triage training" in prompt
    assert "google.gmail.read.metadata" in prompt
    assert "Message ID: msg-1" in prompt
    assert "Thread ID: thread-1" in prompt
    assert "Promo Desk <deals@promo.example.com>" in prompt
    assert "Sender domain: promo.example.com" in prompt
    assert "Spring equipment sale" in prompt
    assert "CATEGORY_PROMOTIONS" in prompt
    assert "useful_promo" in prompt
    assert "manual_review" in prompt
    assert "PRIVATE BODY CONTENT" not in prompt
    assert "google.gmail.read.body" not in prompt


def test_builds_clear_training_question_from_synthetic_gmail_metadata():
    import cassandra_email_triage as triage

    question = triage.build_email_triage_training_question(_metadata())

    assert "Cassandra email triage training" in question
    assert "Reply with a simple classification" in question
    assert "junk, promo, useful promo" in question
    assert "This records training intent only" in question
    assert "Message ID: msg-1" in question
    assert "Thread ID: thread-1" in question
    assert "PRIVATE BODY CONTENT" not in question
    assert "google.gmail.read.body" not in question


def test_sender_domain_is_derived_safely_from_sender_email(tmp_path):
    import cassandra_email_triage as triage

    entry = triage.record_email_triage_classification(
        metadata=_metadata(from_email="News <NEWS@Example.ORG>"),
        operator_classification="newsletter",
        future_suggested_handling="ask_again_next_time",
        classification_source="operator",
        log_path=tmp_path / "triage.jsonl",
    )

    assert entry["sender_email"] == "news@example.org"
    assert entry["sender_domain"] == "example.org"
    assert triage.derive_sender_domain("not-an-email") == ""


@pytest.mark.parametrize("field", ["message_id", "thread_id"])
def test_required_message_and_thread_ids_validate(tmp_path, field):
    import cassandra_email_triage as triage

    metadata = _metadata(**{field: ""})
    with pytest.raises(ValueError, match=f"{field} is required"):
        triage.record_email_triage_classification(
            metadata=metadata,
            operator_classification="promotional",
            future_suggested_handling="suggest_folder_or_label",
            log_path=tmp_path / "triage.jsonl",
        )


def test_allowed_categories_and_handling_constants_are_stable():
    import cassandra_email_triage as triage

    assert triage.EMAIL_TRIAGE_CATEGORIES == (
        "junk",
        "promotional",
        "useful_promo",
        "newsletter",
        "receipt",
        "invoice_payment",
        "gig_lead",
        "client_vendor",
        "travel_hotel_event",
        "music_business_admin",
        "sensitive_legal_cpa_musiclaw_publishing",
        "unknown_manual_review",
    )
    assert triage.EMAIL_TRIAGE_SUGGESTED_HANDLINGS == (
        "ignore_future_similar",
        "ask_again_next_time",
        "suggest_folder_or_label",
        "manual_review",
        "possible_follow_up_later",
    )


def test_unknown_category_rejects_without_writing(tmp_path):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    with pytest.raises(ValueError, match="invalid operator_classification"):
        triage.record_email_triage_classification(
            metadata=_metadata(),
            operator_classification="chase_money",
            future_suggested_handling="manual_review",
            log_path=log_path,
        )

    assert not log_path.exists()


def test_append_only_jsonl_recording_uses_tmp_path(tmp_path):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    first = triage.record_email_triage_classification(
        metadata=_metadata(message_id="msg-1", thread_id="thread-1"),
        operator_classification="promotional",
        future_suggested_handling="suggest_folder_or_label",
        confidence=0.9,
        classification_source="operator",
        created_at="2026-04-29 09:00:00",
        log_path=log_path,
    )
    second = triage.record_email_triage_classification(
        metadata=_metadata(message_id="msg-2", thread_id="thread-2"),
        operator_classification="receipt",
        future_suggested_handling="suggest_folder_or_label",
        confidence=1,
        classification_source="operator",
        created_at="2026-04-29 09:01:00",
        log_path=log_path,
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == first
    assert json.loads(lines[1]) == second
    assert first["source_capability"] == "google.gmail.read.metadata"


def test_loading_replay_normalizes_entries(tmp_path):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    triage.record_email_triage_classification(
        metadata=_metadata(from_email="Alerts <ALERTS@example.net>"),
        operator_classification="receipt",
        future_suggested_handling="suggest_folder_or_label",
        confidence="0.75",
        classification_source="operator",
        log_path=log_path,
    )

    records = triage.load_email_triage_classifications(log_path=log_path)

    assert len(records) == 1
    assert records[0]["_log_index"] == 0
    assert records[0]["sender_email"] == "alerts@example.net"
    assert records[0]["sender_domain"] == "example.net"
    assert records[0]["confidence"] == 0.75
    assert records[0]["source_capability"] == "google.gmail.read.metadata"



def test_loading_skips_malformed_lines_by_default_and_can_include_them(tmp_path):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    log_path.write_text("{not-json\n", encoding="utf-8")

    assert triage.load_email_triage_classifications(log_path=log_path) == []
    invalid = triage.load_email_triage_classifications(log_path=log_path, include_invalid=True)

    assert invalid[0]["_log_index"] == 0
    assert invalid[0]["_raw_line"] == "{not-json"
    assert invalid[0]["_invalid_reason"]


def test_sensitive_category_requires_manual_review_handling(tmp_path):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    with pytest.raises(ValueError, match="manual_review"):
        triage.record_email_triage_classification(
            metadata=_metadata(),
            operator_classification="sensitive_legal_cpa_musiclaw_publishing",
            future_suggested_handling="ignore_future_similar",
            log_path=log_path,
        )
    assert not log_path.exists()

    entry = triage.record_email_triage_classification(
        metadata=_metadata(),
        operator_classification="sensitive_legal_cpa_musiclaw_publishing",
        future_suggested_handling="manual_review",
        sensitivity_flags={"legal": True, "promo": False},
        log_path=log_path,
    )

    assert entry["future_suggested_handling"] == "manual_review"
    assert entry["sensitivity_flags"] == ["legal", "sensitive_category"]


@pytest.mark.parametrize(
    ("response_text", "expected_category", "expected_handling"),
    [
        ("junk", "junk", "ignore_future_similar"),
        ("promo", "promotional", "suggest_folder_or_label"),
        ("useful promo", "useful_promo", "possible_follow_up_later"),
        ("newsletter", "newsletter", "suggest_folder_or_label"),
        ("receipt", "receipt", "suggest_folder_or_label"),
        ("invoice", "invoice_payment", "possible_follow_up_later"),
        ("payment", "invoice_payment", "possible_follow_up_later"),
        ("gig lead", "gig_lead", "possible_follow_up_later"),
        ("client", "client_vendor", "manual_review"),
        ("travel", "travel_hotel_event", "suggest_folder_or_label"),
        ("not sure", "unknown_manual_review", "manual_review"),
        ("unknown / manual review", "unknown_manual_review", "manual_review"),
    ],
)
def test_resolves_simple_operator_responses_to_classification_intent(
    tmp_path,
    response_text,
    expected_category,
    expected_handling,
):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    entry = triage.resolve_email_triage_operator_response(
        _metadata(),
        response_text,
        confidence=0.8,
        created_at="2026-04-29 11:00:00",
        log_path=log_path,
    )

    assert entry["operator_classification"] == expected_category
    assert entry["future_suggested_handling"] == expected_handling
    assert entry["classification_source"] == "operator"
    assert entry["confidence"] == 0.8
    assert entry["operator_response_text"] == response_text
    assert entry["source_capability"] == "google.gmail.read.metadata"

    records = triage.load_email_triage_classifications(log_path=log_path)
    assert len(records) == 1
    assert records[0]["operator_classification"] == expected_category
    assert records[0]["future_suggested_handling"] == expected_handling


@pytest.mark.parametrize(
    "response_text",
    [
        "delete it",
        "archive it",
        "move it",
        "label it promo",
        "reply to it",
        "send an email",
        "create a draft",
        "draft a reply",
    ],
)
def test_rejects_live_action_operator_responses_without_recording(tmp_path, response_text):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    with pytest.raises(ValueError, match="unsafe operator response"):
        triage.resolve_email_triage_operator_response(
            _metadata(),
            response_text,
            log_path=log_path,
        )

    assert not log_path.exists()


def test_resolver_records_sensitive_response_as_manual_review(tmp_path):
    import cassandra_email_triage as triage

    entry = triage.resolve_email_triage_operator_response(
        _metadata(),
        "sensitive legal CPA publishing",
        log_path=tmp_path / "triage.jsonl",
    )

    assert entry["operator_classification"] == "sensitive_legal_cpa_musiclaw_publishing"
    assert entry["future_suggested_handling"] == "manual_review"
    assert entry["sensitivity_flags"] == ["operator_marked_sensitive", "sensitive_category"]


def test_selects_low_risk_promotional_synthetic_email():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(
            message_id="msg-promo",
            thread_id="thread-promo",
            subject="Weekend sale on studio gear",
            snippet="Marketing note with a coupon code.",
            labels=["INBOX", "CATEGORY_PROMOTIONS"],
        )
    ]

    candidate = triage.select_email_triage_training_candidate(messages, prior_records=[])

    assert candidate == messages[0]


def test_candidate_selection_skips_already_classified_message_id():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(message_id="msg-1", thread_id="thread-1", subject="Newsletter sale"),
        _candidate_metadata(message_id="msg-2", thread_id="thread-2", subject="Newsletter digest"),
    ]
    prior_records = [{"message_id": "msg-1", "thread_id": "older-thread"}]

    candidate = triage.select_email_triage_training_candidate(messages, prior_records)

    assert candidate["message_id"] == "msg-2"


def test_candidate_selection_skips_missing_message_id():
    import cassandra_email_triage as triage

    candidate = triage.select_email_triage_training_candidate(
        [_candidate_metadata(message_id="", thread_id="thread-1", subject="Promo sale")],
        prior_records=[],
    )

    assert candidate is None


def test_candidate_selection_skips_missing_thread_id():
    import cassandra_email_triage as triage

    candidate = triage.select_email_triage_training_candidate(
        [_candidate_metadata(message_id="msg-1", thread_id="", subject="Promo sale")],
        prior_records=[],
    )

    assert candidate is None


@pytest.mark.parametrize("field_name", ["body", "body_text", "payload", "raw", "mime", "parts", "messages", "full_message"])
def test_candidate_selection_skips_body_or_full_message_shaped_records(field_name):
    import cassandra_email_triage as triage

    metadata = _candidate_metadata(subject="Promo sale")
    metadata[field_name] = "private full-message content"

    candidate = triage.select_email_triage_training_candidate([metadata], prior_records=[])

    assert candidate is None


def test_candidate_selection_does_not_mutate_input_metadata():
    import cassandra_email_triage as triage

    metadata = _candidate_metadata(
        message_id="msg-copy",
        thread_id="thread-copy",
        subject="Newsletter sale",
        labels=["INBOX", "CATEGORY_PROMOTIONS"],
    )
    before = json.loads(json.dumps(metadata))

    candidate = triage.select_email_triage_training_candidate([metadata], prior_records=[])

    assert metadata == before
    assert candidate == before
    assert candidate is not metadata


def test_candidate_selection_returns_none_when_all_unsafe_or_already_classified():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(message_id="msg-old", thread_id="thread-old", subject="Newsletter sale"),
        _candidate_metadata(message_id="msg-legal", thread_id="thread-legal", subject="Legal tax CPA matter"),
        _candidate_metadata(message_id="msg-private", thread_id="thread-private", subject="Private correspondence"),
    ]
    prior_records = [{"message_id": "msg-old", "thread_id": "thread-old"}]

    candidate = triage.select_email_triage_training_candidate(messages, prior_records)

    assert candidate is None


def test_candidate_selection_prefers_newsletter_over_invoice_payment_client_or_gig_items():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(message_id="msg-payment", thread_id="thread-payment", subject="Payment invoice update"),
        _candidate_metadata(message_id="msg-client", thread_id="thread-client", subject="Client vendor gig lead"),
        _candidate_metadata(message_id="msg-news", thread_id="thread-news", subject="Newsletter sale digest"),
    ]

    candidate = triage.select_email_triage_training_candidate(messages, prior_records=[])

    assert candidate["message_id"] == "msg-news"


def test_candidate_selection_can_use_loaded_jsonl_prior_records(tmp_path):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    triage.record_email_triage_classification(
        metadata=_candidate_metadata(message_id="msg-old", thread_id="thread-old"),
        operator_classification="promotional",
        future_suggested_handling="suggest_folder_or_label",
        log_path=log_path,
    )
    prior_records = triage.load_email_triage_classifications(log_path=log_path)
    messages = [
        _candidate_metadata(message_id="msg-old", thread_id="thread-old", subject="Promo old"),
        _candidate_metadata(message_id="msg-new", thread_id="thread-new", subject="Newsletter sale"),
    ]

    candidate = triage.select_email_triage_training_candidate(messages, prior_records)

    assert candidate["message_id"] == "msg-new"


def test_builds_unsent_operator_question_packet_from_safe_synthetic_metadata():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(
            message_id="msg-packet",
            thread_id="thread-packet",
            from_name="Newsletter Desk",
            from_email="News <NEWS@Example.COM>",
            subject="Weekly newsletter sale",
            snippet="A metadata-only digest with a discount code.",
            labels=["INBOX", "CATEGORY_PROMOTIONS"],
        )
    ]

    packet = triage.build_email_triage_operator_message_packet(
        messages,
        prior_records=[],
        created_at="2026-04-30 10:00:00",
    )

    assert packet["ok"] is True
    assert packet["packet_type"] == "email_triage_training.operator_question"
    assert packet["schema_version"] == triage.EMAIL_TRIAGE_SCHEMA_VERSION
    assert packet["created_at"] == "2026-04-30 10:00:00"
    assert packet["delivery_status"] == "not_sent"
    assert packet["source_capability"] == "google.gmail.read.metadata"
    assert packet["message_id"] == "msg-packet"
    assert packet["thread_id"] == "thread-packet"
    assert packet["sender_name"] == "Newsletter Desk"
    assert packet["sender_email"] == "news@example.com"
    assert packet["sender_domain"] == "example.com"
    assert packet["subject_preview"] == "Weekly newsletter sale"
    assert packet["snippet_preview"] == "A metadata-only digest with a discount code."
    assert packet["gmail_labels_seen"] == ["INBOX", "CATEGORY_PROMOTIONS"]
    assert "Reply with a simple classification" in packet["operator_question"]
    assert packet["records_training_intent_only"] is True


def test_operator_message_packet_includes_allowed_replies_and_disallowed_live_actions():
    import cassandra_email_triage as triage

    packet = triage.build_email_triage_operator_message_packet(
        [_candidate_metadata(message_id="msg-actions", thread_id="thread-actions", subject="Newsletter sale")],
        prior_records=[],
        created_at="2026-04-30 10:01:00",
    )

    assert packet["allowed_reply_examples"] == [
        "junk",
        "promo",
        "useful promo",
        "newsletter",
        "receipt",
        "not sure",
    ]
    assert "gmail_draft_creation" in packet["disallowed_live_actions"]
    assert "send_email" in packet["disallowed_live_actions"]
    assert "request_guardian_approval" in packet["disallowed_live_actions"]
    assert "modify_gmail_labels" in packet["disallowed_live_actions"]
    assert "delete_email" in packet["disallowed_live_actions"]


def test_operator_message_packet_excludes_body_or_full_message_fields():
    import cassandra_email_triage as triage

    packet = triage.build_email_triage_operator_message_packet(
        [_candidate_metadata(message_id="msg-clean", thread_id="thread-clean", subject="Promo sale")],
        prior_records=[],
        created_at="2026-04-30 10:02:00",
    )

    forbidden_fields = {"body", "body_text", "payload", "raw", "mime", "parts", "messages", "full_message"}
    assert forbidden_fields.isdisjoint(packet)
    assert "PRIVATE BODY CONTENT" not in json.dumps(packet)


def test_operator_message_packet_returns_no_candidate_packet_when_all_unsafe_or_classified():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(message_id="msg-old", thread_id="thread-old", subject="Newsletter sale"),
        _candidate_metadata(message_id="msg-legal", thread_id="thread-legal", subject="Legal CPA tax matter"),
    ]
    prior_records = [{"message_id": "msg-old", "thread_id": "thread-old"}]

    packet = triage.build_email_triage_operator_message_packet(messages, prior_records)

    assert packet == {
        "ok": False,
        "packet_type": "email_triage_training.no_candidate",
        "reason": "no_safe_unclassified_candidate",
        "delivery_status": "not_sent",
        "operator_question": "",
    }


def test_operator_message_packet_respects_prior_thread_suppression():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(message_id="msg-same-thread", thread_id="thread-old", subject="Newsletter sale"),
        _candidate_metadata(message_id="msg-new-thread", thread_id="thread-new", subject="Newsletter digest"),
    ]
    prior_records = [{"message_id": "msg-old", "thread_id": "thread-old"}]

    packet = triage.build_email_triage_operator_message_packet(
        messages,
        prior_records,
        created_at="2026-04-30 10:03:00",
        suppress_prior_threads=True,
    )

    assert packet["message_id"] == "msg-new-thread"


def test_operator_message_packet_can_allow_same_thread_when_thread_suppression_disabled():
    import cassandra_email_triage as triage

    messages = [_candidate_metadata(message_id="msg-same-thread", thread_id="thread-old", subject="Newsletter sale")]
    prior_records = [{"message_id": "msg-old", "thread_id": "thread-old"}]

    packet = triage.build_email_triage_operator_message_packet(
        messages,
        prior_records,
        created_at="2026-04-30 10:04:00",
        suppress_prior_threads=False,
    )

    assert packet["ok"] is True
    assert packet["message_id"] == "msg-same-thread"


def test_operator_message_packet_does_not_mutate_inputs():
    import cassandra_email_triage as triage

    messages = [_candidate_metadata(message_id="msg-immutable", thread_id="thread-immutable", subject="Promo sale")]
    prior_records = [{"message_id": "msg-old", "thread_id": "thread-old"}]
    messages_before = json.loads(json.dumps(messages))
    prior_before = json.loads(json.dumps(prior_records))

    triage.build_email_triage_operator_message_packet(
        messages,
        prior_records,
        created_at="2026-04-30 10:05:00",
    )

    assert messages == messages_before
    assert prior_records == prior_before


def test_renders_safe_operator_question_packet_clearly():
    import cassandra_email_triage as triage

    packet = triage.build_email_triage_operator_message_packet(
        [
            _candidate_metadata(
                message_id="msg-display",
                thread_id="thread-display",
                from_name="Promo Desk",
                from_email="Deals <deals@example.com>",
                subject="Newsletter sale",
                snippet="Save on cases this week.",
                labels=["INBOX", "CATEGORY_PROMOTIONS"],
            )
        ],
        prior_records=[],
        created_at="2026-04-30 12:00:00",
    )

    display = triage.render_email_triage_operator_packet(packet)

    assert "Cassandra email triage training" in display
    assert "Metadata-only display" in display
    assert "No Gmail action will be taken" in display
    assert "Delivery status: not_sent" in display
    assert "Promo Desk <deals@example.com>" in display
    assert "Subject: Newsletter sale" in display
    assert "Snippet: Save on cases this week." in display
    assert "Gmail labels seen: INBOX, CATEGORY_PROMOTIONS" in display
    assert "junk, promo, useful promo, newsletter, receipt, not sure" in display
    assert "delete/archive/label/reply/send/draft" in display


def test_operator_display_preserves_not_sent_status():
    import cassandra_email_triage as triage

    display = triage.build_email_triage_operator_display(
        [_candidate_metadata(message_id="msg-display-status", thread_id="thread-display-status")],
        prior_records=[],
        created_at="2026-04-30 12:01:00",
    )

    assert display["delivery_status"] == "not_sent"
    assert display["packet"]["delivery_status"] == "not_sent"
    assert "Delivery status: not_sent" in display["display_text"]


def test_renders_no_candidate_packet_deterministically():
    import cassandra_email_triage as triage

    packet = triage.build_email_triage_operator_message_packet(
        [_candidate_metadata(message_id="msg-old", thread_id="thread-old", subject="Legal CPA tax matter")],
        prior_records=[],
    )

    display = triage.render_email_triage_operator_packet(packet)

    assert packet == {
        "ok": False,
        "packet_type": "email_triage_training.no_candidate",
        "reason": "no_safe_unclassified_candidate",
        "delivery_status": "not_sent",
        "operator_question": "",
    }
    assert display == "\n".join(
        [
            "Cassandra email triage training",
            "Status: no safe unclassified metadata candidate.",
            "Delivery status: not_sent",
            "No Gmail action will be taken.",
        ]
    )


def test_operator_display_excludes_body_or_full_message_fields():
    import cassandra_email_triage as triage

    packet = triage.build_email_triage_operator_message_packet(
        [_candidate_metadata(message_id="msg-display-clean", thread_id="thread-display-clean", subject="Promo sale")],
        prior_records=[],
        created_at="2026-04-30 12:02:00",
    )
    polluted_packet = dict(packet)
    polluted_packet.update({"body_text": "PRIVATE BODY CONTENT SHOULD NOT BE USED", "payload": "FULL MESSAGE"})

    display = triage.render_email_triage_operator_packet(polluted_packet)

    assert "PRIVATE BODY CONTENT" not in display
    assert "FULL MESSAGE" not in display
    assert "body_text" not in display
    assert "payload" not in display


def test_operator_display_does_not_mutate_packet_or_input_messages():
    import cassandra_email_triage as triage

    messages = [_candidate_metadata(message_id="msg-display-copy", thread_id="thread-display-copy", subject="Promo sale")]
    prior_records = [{"message_id": "msg-old", "thread_id": "thread-old"}]
    packet = triage.build_email_triage_operator_message_packet(messages, prior_records, created_at="2026-04-30 12:03:00")
    messages_before = json.loads(json.dumps(messages))
    prior_before = json.loads(json.dumps(prior_records))
    packet_before = json.loads(json.dumps(packet))

    display = triage.render_email_triage_operator_packet(packet)
    built = triage.build_email_triage_operator_display(
        messages,
        prior_records,
        created_at="2026-04-30 12:03:00",
    )

    assert display
    assert built["display_text"]
    assert messages == messages_before
    assert prior_records == prior_before
    assert packet == packet_before


def test_operator_display_only_path_does_not_write_jsonl(monkeypatch, tmp_path):
    import cassandra_email_triage as triage

    log_path = tmp_path / "triage.jsonl"
    monkeypatch.setattr(triage, "EMAIL_TRIAGE_TRAINING_LOG", log_path)

    triage.build_email_triage_operator_display(
        [_candidate_metadata(message_id="msg-no-write", thread_id="thread-no-write", subject="Newsletter sale")],
        prior_records=[],
        created_at="2026-04-30 12:04:00",
    )

    assert not log_path.exists()


def test_operator_display_builds_from_synthetic_messages_and_prior_records():
    import cassandra_email_triage as triage

    messages = [
        _candidate_metadata(message_id="msg-old", thread_id="thread-old", subject="Newsletter old"),
        _candidate_metadata(message_id="msg-display-new", thread_id="thread-display-new", subject="Newsletter sale"),
    ]
    prior_records = [{"message_id": "msg-old", "thread_id": "thread-old"}]

    display = triage.build_email_triage_operator_display(
        messages,
        prior_records,
        created_at="2026-04-30 12:05:00",
    )

    assert display["ok"] is True
    assert display["display_type"] == "email_triage_training.operator_display"
    assert display["packet_type"] == "email_triage_training.operator_question"
    assert display["message_id"] == "msg-display-new"
    assert "Message ID: msg-display-new" in display["display_text"]


def test_operator_display_returns_no_candidate_display_from_synthetic_messages():
    import cassandra_email_triage as triage

    display = triage.build_email_triage_operator_display(
        [_candidate_metadata(message_id="msg-unsafe", thread_id="thread-unsafe", subject="Legal CPA tax matter")],
        prior_records=[],
        created_at="2026-04-30 12:06:00",
    )

    assert display["ok"] is False
    assert display["packet_type"] == "email_triage_training.no_candidate"
    assert display["message_id"] == ""
    assert display["thread_id"] == ""
    assert display["display_text"] == "\n".join(
        [
            "Cassandra email triage training",
            "Status: no safe unclassified metadata candidate.",
            "Delivery status: not_sent",
            "No Gmail action will be taken.",
        ]
    )


def test_no_live_broker_sender_guardian_draft_send_or_model_surfaces_are_used(monkeypatch, tmp_path):
    import cassandra_email_triage as triage

    source = inspect.getsource(triage)
    forbidden_tokens = (
        "google_access_broker",
        "broker_call",
        "cassandra_sender",
        "send_message",
        "chief_guardian",
        "chief_approval",
        "create_gmail_draft",
        "google.gmail.draft.create",
        "google.gmail.send",
        "google.gmail.read.body",
        "ollama_call",
        "nemotron_call",
        "claude",
        "gemini",
        "codex",
        "aider",
        "external_model_packet_policy",
    )
    for token in forbidden_tokens:
        assert token not in source

    forbidden_modules = {
        "google_access_broker",
        "cassandra_sender",
        "chief_guardian_sender",
        "chief_guardian_listener",
        "chief_approval_brain",
        "chief_llm",
    }
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    prompt = triage.build_email_triage_operator_prompt(_metadata())
    question = triage.build_email_triage_training_question(_metadata())
    entry = triage.resolve_email_triage_operator_response(
        metadata=_metadata(),
        response_text="junk",
        log_path=tmp_path / "triage.jsonl",
    )
    records = triage.load_email_triage_classifications(log_path=tmp_path / "triage.jsonl")
    candidate = triage.select_email_triage_training_candidate(
        [_candidate_metadata(message_id="msg-candidate", thread_id="thread-candidate")],
        records,
    )
    packet = triage.build_email_triage_operator_message_packet(
        [_candidate_metadata(message_id="msg-packet-guard", thread_id="thread-packet-guard")],
        records,
        created_at="2026-04-30 10:06:00",
    )
    display_text = triage.render_email_triage_operator_packet(packet)
    display = triage.build_email_triage_operator_display(
        [_candidate_metadata(message_id="msg-display-guard", thread_id="thread-display-guard")],
        records,
        created_at="2026-04-30 12:07:00",
    )

    assert "google.gmail.read.body" not in prompt
    assert "google.gmail.read.body" not in question
    assert entry["source_capability"] == "google.gmail.read.metadata"
    assert records[0]["source_capability"] == "google.gmail.read.metadata"
    assert candidate["message_id"] == "msg-candidate"
    assert packet["delivery_status"] == "not_sent"
    assert packet["source_capability"] == "google.gmail.read.metadata"
    assert "No Gmail action will be taken" in display_text
    assert display["delivery_status"] == "not_sent"