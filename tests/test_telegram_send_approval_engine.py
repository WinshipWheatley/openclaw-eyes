"""Adversarial tests: try to make an untrusted channel authorize a send.

Every test here is an attack, not a demonstration. The engine passes only if it
refuses. The one "happy path" test exists to prove the refusals aren't coming
from a function that rejects everything — a gate that never opens is not secure,
it's broken, and the two look identical from the outside.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import telegram_send_approval_engine as engine

OWNER_CHAT = "8615325274"
OTHER_CHAT = "9999999999"
PREVIEW_MSG_ID = "4471"
NONCE = "send-hold-graduation:abc123def456"

BASE_DRAFT = {
    "to": ["Megan Rivas <Megan@Example.COM>"],
    "cc": [],
    "bcc": [],
    "subject": "  Invoice   0042 ",
    "subject_normalized": "Invoice 0042",
    "body": "Hi Megan,\n\nInvoice attached.  \n\nThanks\n",
    "attachment_digests": ["sha256:" + "a" * 64],
}


def _ts(offset_seconds: int = 0) -> str:
    moment = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _envelope(**overrides):
    payload = {
        "draft_id": "r-draft-0042",
        "to": BASE_DRAFT["to"],
        "cc": BASE_DRAFT["cc"],
        "bcc": BASE_DRAFT["bcc"],
        "subject": BASE_DRAFT["subject"],
        "body": BASE_DRAFT["body"],
        "attachment_digests": BASE_DRAFT["attachment_digests"],
        "owner_chat_id": OWNER_CHAT,
        "reply_to_message_id": PREVIEW_MSG_ID,
    }
    payload.update(overrides)
    return engine.canonical_envelope(**payload)


def _approval(**overrides) -> engine.Approval:
    env = overrides.pop("envelope", None) or _envelope()
    fields = {
        "nonce": NONCE,
        "envelope": env,
        "envelope_hash": engine.envelope_hash(env),
        "owner_chat_id": OWNER_CHAT,
        "preview_message_id": PREVIEW_MSG_ID,
        "issued_at": _ts(-60),
        "expires_at": _ts(600),
    }
    fields.update(overrides)
    return engine.Approval(**fields)


def _fetcher(draft=None):
    payload = dict(BASE_DRAFT if draft is None else draft)
    return lambda draft_id: payload


def _evaluate(**overrides):
    approval = overrides.pop("approval", None) or _approval()
    kwargs = {
        "message_text": f"SEND {NONCE}",
        "from_chat_id": OWNER_CHAT,
        "reply_to_message_id": PREVIEW_MSG_ID,
        "approvals": {approval.nonce: approval},
        "owner_chat_allowlist": [OWNER_CHAT],
        "fetch_draft": _fetcher(),
        "now": _ts(),
        "practice_mode": True,
    }
    kwargs.update(overrides)
    return engine.evaluate_send_request(**kwargs)


# ---------------------------------------------------------------- non-vacuity

def test_a_fully_valid_approval_clears_every_gate() -> None:
    """If this fails, every refusal below proves nothing."""

    decision = _evaluate(practice_mode=False)
    assert decision.allowed is True, decision.to_dict()
    assert decision.reason == engine.ALLOW
    for gate in ("command_shape", "owner_chat", "nonce_resolves", "nonce_chat_binding",
                 "reply_binding", "not_replayed", "not_expired", "draft_present",
                 "envelope_unchanged"):
        assert gate in decision.checks_passed


def test_practice_mode_refuses_even_when_everything_passes() -> None:
    decision = _evaluate(practice_mode=True)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_PRACTICE_MODE
    # It must have actually run the gates, not short-circuited at the top.
    assert "envelope_unchanged" in decision.checks_passed


# ------------------------------------------------------------- command shape

@pytest.mark.parametrize("text", ["SEND", "send", "  SEND  ", "Send!", "SEND."])
def test_a_bare_send_authorizes_nothing(text: str) -> None:
    decision = _evaluate(message_text=text)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_BARE_SEND


def test_a_send_cannot_smuggle_a_second_instruction() -> None:
    decision = _evaluate(message_text=f"SEND {NONCE} and also delete the ledger")
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_TRAILING_CONTENT


@pytest.mark.parametrize("text", [
    "please send the invoice",
    "yes go ahead",
    "approved",
    "SENDING",
    "",
])
def test_natural_language_approval_is_not_an_approval(text: str) -> None:
    decision = _evaluate(message_text=text)
    assert decision.allowed is False
    assert decision.reason in {engine.REJECT_NOT_A_SEND_COMMAND, engine.REJECT_BARE_SEND}


def test_telegram_cannot_authorize_an_unrelated_gated_action() -> None:
    for text in ("SEND money to Draper", "SEND wire $5000", "SEND and cutover production"):
        decision = _evaluate(message_text=text)
        assert decision.allowed is False
        assert decision.reason != engine.ALLOW


# ------------------------------------------------------------------- identity

def test_a_stranger_chat_cannot_approve() -> None:
    decision = _evaluate(from_chat_id=OTHER_CHAT)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_CHAT_NOT_ALLOWED


def test_rejecting_a_stranger_leaks_no_nonce_validity() -> None:
    """A wrong chat must not learn whether it guessed a live nonce."""

    real = _evaluate(from_chat_id=OTHER_CHAT, message_text=f"SEND {NONCE}")
    fake = _evaluate(from_chat_id=OTHER_CHAT, message_text="SEND totally-made-up-nonce")
    assert real.reason == fake.reason == engine.REJECT_CHAT_NOT_ALLOWED
    assert real.nonce == fake.nonce == ""
    assert real.draft_id == fake.draft_id == ""


def test_an_allowlisted_chat_cannot_use_another_chats_approval() -> None:
    approval = _approval(owner_chat_id=OTHER_CHAT)
    decision = _evaluate(approval=approval, from_chat_id=OWNER_CHAT,
                         owner_chat_allowlist=[OWNER_CHAT, OTHER_CHAT])
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_CHAT_NOT_ALLOWED


def test_approval_must_reply_to_its_own_preview() -> None:
    decision = _evaluate(reply_to_message_id="9998")
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_WRONG_REPLY_TARGET


def test_an_unknown_nonce_resolves_to_nothing() -> None:
    decision = _evaluate(message_text="SEND send-hold-graduation:not-a-real-one")
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_UNKNOWN_NONCE


# ---------------------------------------------------------------- time/replay

def test_a_consumed_nonce_cannot_fire_twice() -> None:
    decision = _evaluate(approval=_approval(consumed_at=_ts(-10)), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_ALREADY_CONSUMED


def test_an_expired_approval_is_dead_not_renewable() -> None:
    decision = _evaluate(approval=_approval(expires_at=_ts(-1)), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_EXPIRED


def test_expiry_is_exclusive_at_the_boundary() -> None:
    decision = _evaluate(approval=_approval(expires_at=_ts()), now=_ts(), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_EXPIRED


# ------------------------------------------------------------------- drift

def test_recipient_swapped_after_preview_kills_the_approval() -> None:
    hostile = dict(BASE_DRAFT, to=["attacker@elsewhere.example"])
    decision = _evaluate(fetch_draft=_fetcher(hostile), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_ENVELOPE_DRIFT
    assert "to" in decision.detail


def test_an_added_bcc_kills_the_approval() -> None:
    hostile = dict(BASE_DRAFT, bcc=["quiet-copy@elsewhere.example"])
    decision = _evaluate(fetch_draft=_fetcher(hostile), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_ENVELOPE_DRIFT
    assert "bcc" in decision.detail


def test_a_display_name_change_alone_does_not_kill_it() -> None:
    """Normalisation must be real, or every approval dies of client formatting."""

    same = dict(BASE_DRAFT, to=["megan@example.com"])
    decision = _evaluate(fetch_draft=_fetcher(same), practice_mode=False)
    assert decision.allowed is True, decision.to_dict()


def test_body_edited_after_preview_kills_the_approval() -> None:
    hostile = dict(BASE_DRAFT, body="Hi Megan,\n\nPlease wire to the new account.\n")
    decision = _evaluate(fetch_draft=_fetcher(hostile), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_ENVELOPE_DRIFT
    assert "body_sha256" in decision.detail


def test_subject_edited_after_preview_kills_the_approval() -> None:
    hostile = dict(BASE_DRAFT, subject="Re: something else entirely")
    decision = _evaluate(fetch_draft=_fetcher(hostile), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_ENVELOPE_DRIFT


def test_attachment_swapped_kills_the_approval_and_says_so_precisely() -> None:
    hostile = dict(BASE_DRAFT, attachment_digests=["sha256:" + "b" * 64])
    decision = _evaluate(fetch_draft=_fetcher(hostile), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_ATTACHMENT_DRIFT


def test_a_missing_attachment_kills_the_approval() -> None:
    hostile = dict(BASE_DRAFT, attachment_digests=[])
    decision = _evaluate(fetch_draft=_fetcher(hostile), practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_ATTACHMENT_DRIFT


def test_a_deleted_draft_kills_the_approval() -> None:
    decision = _evaluate(fetch_draft=lambda draft_id: None, practice_mode=False)
    assert decision.allowed is False
    assert decision.reason == engine.REJECT_DRAFT_MISSING


def test_the_draft_is_refetched_at_decision_time_not_trusted_from_preview() -> None:
    calls: list[str] = []

    def watching(draft_id: str):
        calls.append(draft_id)
        return dict(BASE_DRAFT)

    _evaluate(fetch_draft=watching, practice_mode=False)
    assert calls == ["r-draft-0042"], "the draft must be re-read immediately before sending"


# ------------------------------------------------------------- normalisation

def test_recipient_order_does_not_change_the_hash_but_the_set_does() -> None:
    a = _envelope(to=["b@example.com", "a@example.com"])
    b = _envelope(to=["a@example.com", "b@example.com"])
    c = _envelope(to=["a@example.com", "b@example.com", "c@example.com"])
    assert engine.envelope_hash(a) == engine.envelope_hash(b)
    assert engine.envelope_hash(a) != engine.envelope_hash(c)


def test_trailing_whitespace_is_ignored_but_wording_is_not() -> None:
    a = _envelope(body="Hello   \n\nThanks\n")
    b = _envelope(body="Hello\n\nThanks")
    c = _envelope(body="Hello\n\nRegards")
    assert engine.envelope_hash(a) == engine.envelope_hash(b)
    assert engine.envelope_hash(a) != engine.envelope_hash(c)


def test_an_envelope_without_a_draft_or_chat_cannot_be_built() -> None:
    with pytest.raises(engine.ApprovalEngineError):
        engine.canonical_envelope(draft_id="", to=["a@b.c"], owner_chat_id=OWNER_CHAT)
    with pytest.raises(engine.ApprovalEngineError):
        engine.canonical_envelope(draft_id="d", to=["a@b.c"], owner_chat_id="")


def test_the_module_has_no_send_capability_at_all() -> None:
    """Structural, not documented: this file cannot perform a send.

    The decision and the effect are separated on purpose. If someone later adds
    a sender here, this fails and they have to justify it deliberately.
    """

    import ast
    import inspect

    # Checked against the parsed module, not its text: a substring scan trips on
    # prose that merely NAMES the broker, and would push the next author to stop
    # explaining where execution actually lives. You cannot send without
    # importing something, so the import graph is the real constraint.
    tree = ast.parse(inspect.getsource(engine))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {
        "smtplib", "google_access_broker", "email_send_executor", "requests",
        "urllib", "http", "socket", "subprocess", "googleapiclient",
    }
    offenders = sorted(imported & forbidden)
    assert not offenders, (
        f"the decision engine imports {offenders}; deciding and sending must stay "
        "in separate files so neither can quietly acquire the other's powers"
    )
