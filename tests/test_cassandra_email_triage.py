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
    entry = triage.record_email_triage_classification(
        metadata=_metadata(),
        operator_classification="junk",
        future_suggested_handling="ignore_future_similar",
        log_path=tmp_path / "triage.jsonl",
    )
    records = triage.load_email_triage_classifications(log_path=tmp_path / "triage.jsonl")

    assert "google.gmail.read.body" not in prompt
    assert entry["source_capability"] == "google.gmail.read.metadata"
    assert records[0]["source_capability"] == "google.gmail.read.metadata"