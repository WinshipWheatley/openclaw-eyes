from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("show my unread emails", "unread_list"),
        ("any new emails?", "unread_list"),
        ("new messages?", "unread_list"),
        ("any emails?", "unread_list"),
        ("unread emails", "unread_list"),
        ("did I get an email from Dane this week?", "metadata_read"),
        ("did we get sent anything from Dane this week?", "metadata_read"),
        ("find messages from Experian", "metadata_read"),
        ("message from Dane", "metadata_read"),
        ("email history", "metadata_read"),
        ("send an email to Dane about Friday", "draft_send"),
        ("send a Gmail to Alex", "draft_send"),
        ("forward that email to Dane", "draft_send"),
        ("follow-up email to Dane", "draft_send"),
        ("could you email Dane and ask if Friday works?", "draft_send"),
        ("draft a message to Dane", "draft_send"),
        ("please send Dane a note about Friday", "draft_send"),
        ("reply to Dane's email", "reply"),
        ("check email replies from Dad", "reply"),
        ("send the intro emails", "outreach"),
        ("send the Cassandra outreach emails", "outreach"),
        ("who owes me money?", "none"),
        ("is the system running smooth?", "none"),
        ("who did we send the last invoice to?", "none"),
        ("did the deployment message clear?", "none"),
        ("any messages from the deployment queue?", "none"),
        ("send a text message to Dane", "none"),
        ("send a Telegram message to Dane", "none"),
        ("do not check email", "none"),
        ("don't show my unread emails", "none"),
        ("no need to check email", "none"),
        ("do not show unread messages", "none"),
    ),
)
def test_email_owner_covers_paraphrases_and_collision_negatives(
    text: str,
    expected: str,
) -> None:
    from email_intent import classify_email_intent

    assert classify_email_intent(text).value == expected


def test_owner_keeps_reply_lookup_and_reply_draft_authority_distinct() -> None:
    from email_intent import email_intent_requires_draft, email_intent_requires_read

    lookup = "check email replies from Dad"
    draft = "reply to Dane's email"

    assert email_intent_requires_read(lookup) is True
    assert email_intent_requires_draft(lookup) is False
    assert email_intent_requires_read(draft) is False
    assert email_intent_requires_draft(draft) is True


@pytest.mark.parametrize(
    ("text", "context"),
    (
        ("did the service respond?", "system deploy"),
        ("draft a follow-up", "music album"),
    ),
)
def test_arbitrary_world_context_cannot_grant_email_authority(
    text: str,
    context: str,
) -> None:
    from email_intent import EmailIntent, classify_email_intent

    assert classify_email_intent(text, context=context) is EmailIntent.NONE


def test_st_annes_glenn_lane_restores_bounded_read_and_draft_ownership() -> None:
    from email_intent import (
        EmailIntent,
        classify_email_intent,
        email_intent_requires_draft,
        email_intent_requires_read,
    )

    context = "finance st_annes"
    read = "Did Glenn acknowledge the invoice or payment timing?"
    draft = "Never mind, just draft what I should ask Glenn."
    read_paraphrase = "Has Glenn replied about the payment?"
    draft_paraphrase = "Could you draft what we should ask Glenn about the invoice?"

    assert classify_email_intent(read, context=context) is EmailIntent.REPLY
    assert email_intent_requires_read(read, context=context) is True
    assert email_intent_requires_draft(read, context=context) is False
    assert classify_email_intent(draft, context=context) is EmailIntent.DRAFT_SEND
    assert email_intent_requires_read(draft, context=context) is False
    assert email_intent_requires_draft(draft, context=context) is True
    assert classify_email_intent(read_paraphrase, context=context) is EmailIntent.REPLY
    assert classify_email_intent(draft_paraphrase, context=context) is EmailIntent.DRAFT_SEND


@pytest.mark.parametrize(
    ("text", "context"),
    (
        ("Did Glenn acknowledge the invoice or payment timing?", "finance capital_hilton"),
        ("Never mind, just draft what I should ask Glenn.", "finance live_arts_md"),
        ("Did Glennard acknowledge the invoice or payment timing?", "finance st_annes"),
        ("did the service respond?", "finance st_annes"),
        ("draft a follow-up", "finance st_annes"),
        ("Glenn acknowledged the invoice yesterday.", "finance st_annes"),
        ("We should acknowledge Glenn at the meeting.", "finance st_annes"),
        ("Did Glenn respond at the meeting?", "finance st_annes"),
        ("Draft what I should ask Glenn at the meeting.", "finance st_annes"),
        ("Did Glenn acknowledge the system status?", "finance st_annes"),
    ),
)
def test_st_annes_lane_context_does_not_grant_unbounded_email_authority(
    text: str,
    context: str,
) -> None:
    from email_intent import EmailIntent, classify_email_intent

    assert classify_email_intent(text, context=context) is EmailIntent.NONE


def test_business_ops_classifier_and_packet_preserve_email_authority_boundaries() -> None:
    from business_ops_intent import classify_business_ops_intent
    from business_ops_packet import assemble_business_ops_packet

    read_intent = classify_business_ops_intent(
        "did we get sent anything from Dane this week?"
    )
    read_packet = assemble_business_ops_packet(
        "did we get sent anything from Dane this week?",
        "cassandra",
        intent=read_intent,
    )
    read_caps = {cap.name for cap in read_packet.permitted_capabilities}

    draft_intent = classify_business_ops_intent("send an email to Dane about Friday")
    draft_packet = assemble_business_ops_packet(
        "send an email to Dane about Friday",
        "cassandra",
        intent=draft_intent,
    )
    draft_caps = {cap.name for cap in draft_packet.permitted_capabilities}

    assert read_intent.intent_name == "email_search"
    assert read_intent.trigger == "metadata_read"
    assert read_packet.action_status == "read_only"
    assert "gmail_metadata" in read_caps
    assert "email_draft" not in read_caps

    assert draft_intent.intent_name == "email_draft"
    assert draft_intent.trigger == "draft_send"
    assert draft_packet.action_status == "draft_only_until_guardian_approval"
    assert draft_packet.execution_authority is False
    assert "email_draft" in draft_caps
    assert "gmail_metadata" not in draft_caps
    assert "email_send" not in draft_caps


def test_business_ops_packet_rejects_a_caller_supplied_email_label_without_owner_match() -> None:
    from business_ops_intent import IntentFrame
    from business_ops_packet import assemble_business_ops_packet

    packet = assemble_business_ops_packet(
        "hello there",
        "cassandra",
        intent=IntentFrame("email_search", "read_only", "email", 1.0, "caller"),
    )

    assert not {
        "gmail_metadata",
        "email_draft",
        "email_send",
    }.intersection(cap.name for cap in packet.permitted_capabilities)


def test_cassandra_gmail_gate_delegates_and_business_terms_do_not_grant_access() -> None:
    import cassandra_brain

    metadata = cassandra_brain.decide_gmail_intent(
        "did we get sent anything from Dane this week?"
    )
    draft = cassandra_brain.decide_gmail_intent(
        "send an email to Dane about Friday"
    )
    reply_lookup = cassandra_brain.decide_gmail_intent(
        "check email replies from Dad"
    )
    reply_draft = cassandra_brain.decide_gmail_intent("reply to Dane's email")
    unrelated_invoice = cassandra_brain.decide_gmail_intent(
        "prepare the July invoice"
    )

    assert metadata.allowed is True
    assert metadata.trigger == "metadata_read"
    assert draft.allowed is True
    assert draft.trigger == "draft_send"
    assert reply_lookup.category == "email_search"
    assert reply_draft.category == "email_draft"
    assert unrelated_invoice.allowed is False
    assert unrelated_invoice.category == "none"


def test_cassandra_metadata_fetch_uses_owner_for_b_k3_shape(monkeypatch) -> None:
    import cassandra_brain
    import google_access_broker

    calls: list[tuple[str, str, dict]] = []

    def fake_call(actor: str, capability: str, payload: dict) -> dict:
        calls.append((actor, capability, payload))
        return {
            "ok": True,
            "data": [
                {
                    "from_name": "Dane",
                    "from_email": "dane@example.com",
                    "subject": "Friday",
                    "date_raw": format_datetime(datetime.now(timezone.utc)),
                    "labels": ["INBOX", "UNREAD"],
                },
                {
                    "from_name": "Experian",
                    "from_email": "alerts@example.com",
                    "subject": "Distractor",
                    "date_raw": format_datetime(datetime.now(timezone.utc)),
                    "labels": ["INBOX"],
                },
            ],
        }

    monkeypatch.setattr(google_access_broker, "call", fake_call)

    context = cassandra_brain._fetch_gmail_context(
        "did we get sent anything from Dane this week?"
    )
    assert "Dane" in context
    assert "Friday" in context
    assert "Experian" not in context
    assert "Distractor" not in context
    assert calls == [
        (
            "cassandra",
            "google.gmail.read.metadata",
            {"max_results": 10, "query": "from:Dane newer_than:7d"},
        )
    ]

    calls.clear()
    assert cassandra_brain._fetch_gmail_context(
        "send an email to Dane about Friday"
    ) == ""
    assert calls == []


def test_cassandra_metadata_fetch_distinguishes_grounded_absence_from_outage(
    monkeypatch,
) -> None:
    import cassandra_brain
    import google_access_broker

    monkeypatch.setattr(
        google_access_broker,
        "call",
        lambda *_args, **_kwargs: {"ok": True, "data": []},
    )
    assert cassandra_brain._fetch_gmail_context(
        "did we get sent anything from Dane this week?"
    ) == "[GMAIL DATA — no matching inbox messages]"

    monkeypatch.setattr(
        google_access_broker,
        "call",
        lambda *_args, **_kwargs: {"ok": False, "data": None, "error": "offline"},
    )
    assert cassandra_brain._fetch_gmail_context(
        "did we get sent anything from Dane this week?"
    ) == "[GMAIL DATA — inbox unreachable]"


def test_cassandra_send_outreach_and_reply_wrappers_are_owner_consumers(
    monkeypatch,
) -> None:
    import cassandra_brain
    import cassandra_capability
    import cassandra_outreach

    monkeypatch.setattr(cassandra_capability, "EMAIL_DRAFT_CONNECTED", True)

    assert cassandra_brain._detect_send_email_intent(
        "send an email to Dane about Friday"
    ) is True
    assert cassandra_brain._detect_send_email_intent(
        "did we get sent anything from Dane this week?"
    ) is False
    assert cassandra_brain._detect_outreach_email_intent(
        "send the intro emails"
    ) is True
    assert cassandra_outreach._detect_inner_circle_email_reply_intent(
        "check email replies from Dad"
    ) is True
    assert cassandra_outreach._detect_inner_circle_email_reply_intent(
        "reply to Dane's email"
    ) is False


def test_capability_loop_consumes_owner_without_conflating_read_and_draft() -> None:
    import capability_authority_loop as loop

    assert loop.detects_read_only_email_lookup_intent(
        "did we get sent anything from Dane this week?"
    ) is True
    assert loop.detects_read_only_email_lookup_intent(
        "reply to Dane's email"
    ) is False
    assert loop.detect_capability_intent(
        "check email replies from Dad"
    ) == loop.READ_ONLY_EMAIL_LOOKUP
    assert loop.detect_capability_intent(
        "reply to Dane's email"
    ) == loop.FOLLOW_UP_DRAFT_GENERATOR


def test_chief_routes_only_owner_kinds_its_email_adapter_can_safely_handle() -> None:
    import chief_router

    assert chief_router.email_intent("send an email to Dane about Friday") is True
    assert chief_router.email_intent("email history") is True
    assert chief_router.email_intent(
        "did we get sent anything from Dane this week?"
    ) is False


def test_consumer_modules_no_longer_define_parallel_email_tables() -> None:
    import cassandra_brain
    import cassandra_outreach
    import capability_authority_loop

    assert not hasattr(cassandra_brain, "_GMAIL_QUERY_WORDS")
    assert not hasattr(cassandra_brain, "_SEND_EMAIL_KEYWORDS")
    assert not hasattr(cassandra_brain, "_OUTREACH_EMAIL_PATTERNS")
    assert not hasattr(cassandra_outreach, "_EMAIL_REPLY_BRIDGE_PATTERNS")
    assert not hasattr(capability_authority_loop, "EMAIL_LOOKUP_TERMS")
    assert not hasattr(capability_authority_loop, "FOLLOW_UP_DRAFT_TERMS")

    sources = {
        name: Path(name).read_text(encoding="utf-8")
        for name in (
            "business_ops_intent.py",
            "business_ops_packet.py",
            "capability_authority_loop.py",
            "cassandra_outreach.py",
            "chief_router.py",
        )
    }
    assert all("from email_intent import" in source for source in sources.values())
