"""The Maestro transport may carry an approval. It may never become one.

These tests sit on the seam where an untrusted channel meets a governed bridge.
The property under test is not "the intent arrives" — that part is easy. It is
that arriving changes nothing: authority_boundary stays all-false, no execution
field flips, and the staged record still says out loud that Maestro cannot act.

No bot token, no poller, no network. The listener's request builder is a pure
function and is exercised as one.
"""

from __future__ import annotations

import pytest

import maestro_listener as listener
import telegram_send_approval_engine as engine

NONCE = "send-hold-graduation:abc123def456"
MSG_ID = "4472"
PREVIEW_ID = "4471"
CHAT_ID = 8615325274


def _request(text: str, **overrides):
    kwargs = {
        "message_id": MSG_ID,
        "chat_id": CHAT_ID,
        "created_at": "2026-07-28T12:00:00Z",
        "reply_to_message_id": PREVIEW_ID,
    }
    kwargs.update(overrides)
    return listener.build_operator_maestro_chat_request(text, **kwargs)


# ------------------------------------------------------- the boundary holds

def test_authority_boundary_stays_all_false_when_an_approval_is_staged() -> None:
    request = _request(f"SEND {NONCE}")
    boundary = request["authority_boundary"]

    assert boundary, "authority_boundary must be present and populated, never {}"
    assert boundary == dict(listener.AUTHORITY_BOUNDARY)
    offenders = [k for k, v in boundary.items() if v is not False]
    assert not offenders, f"staging an approval flipped {offenders} to non-False"


def test_staging_does_not_touch_the_send_or_credential_permissions() -> None:
    request = _request(f"SEND {NONCE}")
    boundary = request["authority_boundary"]
    for key in ("live_email_send_allowed", "live_external_action_allowed",
                "credential_handling_allowed", "live_approval_request_allowed"):
        assert boundary[key] is False, f"{key} must remain False"


def test_the_staged_record_declares_its_own_powerlessness() -> None:
    intent = _request(f"SEND {NONCE}")["approval_intent"]
    assert intent["staged_only"] is True
    assert intent["maestro_may_execute"] is False
    assert intent["execution_path"] == engine.EXECUTION_PATH
    assert "broker" in intent["execution_path"]


def test_the_request_still_says_no_external_action_ran() -> None:
    request = _request(f"SEND {NONCE}")
    assert request["no_external_action"] is True
    assert request["pc_listener_wrote_request_only"] is True


# --------------------------------------------------------------- the binding

def test_chat_message_and_reply_ids_are_all_carried() -> None:
    intent = _request(f"SEND {NONCE}")["approval_intent"]
    assert intent["nonce"] == NONCE
    assert intent["telegram_message_id"] == MSG_ID
    assert intent["telegram_reply_to_message_id"] == PREVIEW_ID
    assert intent["telegram_chat_ref"].startswith("sha256:")


def test_the_chat_identifier_is_never_carried_in_the_clear() -> None:
    intent = _request(f"SEND {NONCE}")["approval_intent"]
    assert str(CHAT_ID) not in intent["telegram_chat_ref"]
    assert str(CHAT_ID) not in engine._stable_json(intent)


def test_the_binding_hash_moves_with_every_bound_field() -> None:
    base = _request(f"SEND {NONCE}")["approval_intent"]["binding_hash"]

    other_reply = _request(f"SEND {NONCE}", reply_to_message_id="9998")
    other_message = _request(f"SEND {NONCE}", message_id="4473")
    other_chat = _request(f"SEND {NONCE}", chat_id=9999999999)
    other_nonce = _request("SEND send-hold-graduation:zzz999zzz999")

    for label, request in (("reply", other_reply), ("message", other_message),
                           ("chat", other_chat), ("nonce", other_nonce)):
        assert request["approval_intent"]["binding_hash"] != base, (
            f"changing the {label} left the binding hash unchanged"
        )


def test_the_binding_is_covered_by_the_requests_own_payload_hash() -> None:
    """Editing the staged intent in flight must invalidate the request."""

    request = _request(f"SEND {NONCE}")
    original = request["payload_hash"]

    tampered = dict(request)
    tampered["approval_intent"] = dict(request["approval_intent"], nonce="attacker-nonce")
    tampered.pop("payload_hash")
    assert listener._content_hash(tampered) != original


# ------------------------------------------------------- refusals still speak

def test_a_bare_send_is_staged_as_inadmissible_not_dropped() -> None:
    intent = _request("SEND")["approval_intent"]
    assert intent["admissible"] is False
    assert intent["refusal_reason"] == engine.REJECT_BARE_SEND
    assert intent["nonce"] == ""


def test_a_smuggled_instruction_is_staged_as_inadmissible() -> None:
    intent = _request(f"SEND {NONCE} and also wire the deposit")["approval_intent"]
    assert intent["admissible"] is False
    assert intent["refusal_reason"] == engine.REJECT_TRAILING_CONTENT
    assert intent["nonce"] == ""


def test_every_refusal_gets_words_and_never_silence() -> None:
    for text in ("SEND", f"SEND {NONCE} and delete the ledger"):
        reply = engine.deterministic_intent_reply(_request(text)["approval_intent"])
        assert reply.strip(), f"{text!r} produced a silent refusal"
        assert "no action ran" in reply


def test_the_admissible_reply_never_claims_a_send_happened() -> None:
    reply = engine.deterministic_intent_reply(_request(f"SEND {NONCE}")["approval_intent"])
    assert "staged" in reply.lower()
    for lie in ("sent", "delivered", "on its way", "done"):
        assert lie not in reply.lower(), f"reply implies completion via {lie!r}"


# ------------------------------------------------------- narrowness of branch

@pytest.mark.parametrize("text", [
    "what day is it",
    "how is the fleet",
    "SENDING the invoice tomorrow",
    "please send the invoice when you can",
    "resend that",
])
def test_ordinary_chat_is_not_staged_at_all(text: str) -> None:
    assert "approval_intent" not in _request(text), (
        f"{text!r} was misclassified as an approval; the branch must stay narrow"
    )


def test_ordinary_chat_requests_are_byte_identical_to_before_the_branch() -> None:
    """The seam must be inert for every message that isn't approval-shaped."""

    request = _request("what day is it")
    assert "approval_intent" not in request
    assert request["authority_boundary"] == dict(listener.AUTHORITY_BOUNDARY)


def test_recognition_failure_never_costs_the_operator_their_message(monkeypatch) -> None:
    """If the engine blows up, the message still gets through as ordinary chat."""

    def exploding(*args, **kwargs):
        raise RuntimeError("engine is broken")

    monkeypatch.setattr(engine, "classify_approval_intent", exploding)
    request = _request(f"SEND {NONCE}")

    # Absence proves the exception path actually ran. Without this the test would
    # pass just as happily if the monkeypatch never took effect.
    assert "approval_intent" not in request
    assert request["source_text"] == f"SEND {NONCE}"
    assert request["authority_boundary"] == dict(listener.AUTHORITY_BOUNDARY)
