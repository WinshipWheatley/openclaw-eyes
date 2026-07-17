from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_warm_client_draft_routes_to_clara_not_payment_lookup(monkeypatch) -> None:
    import cassandra_brain

    logged: list[dict] = []
    prompt = (
        "Cassandra, draft a warm note to Draper asking him to forward the St. Anne's "
        "invoice to Glenn and copy Winship."
    )

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_process_operator_context_switchboard_message", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_process_guided_review_message", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_try_universal_operator_intake", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_payment_verify_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_cassandra_context_clean", lambda *args, **kwargs: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_tokenize", lambda prompt: (prompt, None), raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_rehydrate_reply", lambda reply, ctx: reply, raising=False)
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *args, **kwargs: "I checked your recent Gmail notifications but didn't see that payment yet.",
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_handle_payment_verification_request",
        lambda text: "I checked your recent Gmail notifications but didn't see that payment yet.",
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append(
            {"route": route, "replies": replies, **dict(kwargs.get("metadata") or {})}
        ),
        raising=False,
    )

    replies = cassandra_brain.handle(prompt, session={"skip_followup_check": True})

    assert len(replies) == 1
    reply = replies[0]
    assert "Hi Draper," in reply
    assert "Please forward this to Glenn after your review, or let me know if there are any issues." in reply
    assert "Warmly,\nClara Reid" in reply
    assert "Nothing has been sent" in reply
    assert "recent Gmail notifications" not in reply
    assert "payment" not in reply.lower()
    assert logged[-1]["route"] == "clara_client_voice_draft"
    assert logged[-1]["gmail_polled"] is False
    assert logged[-1]["email_send_performed"] is False


def test_short_warm_note_to_draper_produces_inline_clara_draft_before_staging(monkeypatch) -> None:
    import cassandra_brain

    logged: list[dict] = []
    prompt = "draft a warm note to Draper"

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_process_operator_context_switchboard_message", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_process_guided_review_message", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_try_universal_operator_intake", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_payment_verify_context", lambda *args, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_cassandra_context_clean", lambda *args, **kwargs: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_tokenize", lambda prompt: (prompt, None), raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_rehydrate_reply", lambda reply, ctx: reply, raising=False)
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_handle_operator_objective",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("warm client draft should not route to objective staging")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *args, **kwargs: "Finance candidates: 51; Capital Hilton Coupa...",
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append(
            {"route": route, "replies": replies, **dict(kwargs.get("metadata") or {})}
        ),
        raising=False,
    )

    replies = cassandra_brain.handle(prompt, session={"skip_followup_check": True})

    assert len(replies) == 1
    reply = replies[0]
    assert "Clara draft (review only - not sent):" in reply
    assert "Hi Draper," in reply
    assert "Please forward this to Glenn after your review, or let me know if there are any issues." in reply
    assert "Warmly,\nClara Reid" in reply
    assert "Nothing has been sent" in reply
    assert "Finance candidates" not in reply
    assert "ROUTE_TO_STAGING" not in reply
    assert "send_reply_email_action" not in reply
    assert logged[-1]["route"] == "clara_client_voice_draft"
    assert logged[-1]["gmail_draft_created"] is False
    assert logged[-1]["email_send_performed"] is False


def test_objective_followup_review_request_is_not_clara_draft() -> None:
    import cassandra_brain

    prompt = (
        "Cassandra, have we received any emails from Annette at Capital Hilton? "
        "If not, send a follow-up tomorrow but show me the draft before sending."
    )

    assert cassandra_brain._detect_clara_client_voice_draft_intent(prompt) is False
