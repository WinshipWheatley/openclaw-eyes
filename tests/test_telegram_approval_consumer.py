"""The consumer must refuse in every way an approval can be wrong.

Fakes only: no credential is loaded, no Google client is imported, no socket is
opened. The broker and the graduation are injected, so every test asserts about
the *decision chain*, not about Gmail.

The property that matters most is ordering. A gate that runs after the send is
decoration. Several tests below assert not just that something was refused, but
that the send was never attempted — because "refused" and "sent then regretted"
look identical in a boolean.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import telegram_approval_consumer as consumer
import telegram_send_approval_engine as engine

CHAT_REF = "sha256:aabbccddeeff"
OTHER_CHAT_REF = "sha256:111111111111"
NONCE = "send-hold-graduation:abc123def456"
PREVIEW_ID = "4471"
DRAFT_ID = "r-draft-0042"
PAYLOAD_HASH = "sha256:" + "9" * 64

DRAFT = {
    "to": ["Megan Rivas <Megan@Example.COM>"],
    "cc": [],
    "bcc": [],
    "subject": "Invoice 0042",
    "body": "Hi Megan,\n\nInvoice attached.\n",
    "attachment_digests": ["sha256:" + "a" * 64],
}


def _ts(offset: int = 0) -> str:
    moment = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _approval(**over) -> engine.Approval:
    env = engine.canonical_envelope(
        draft_id=DRAFT_ID, to=DRAFT["to"], cc=DRAFT["cc"], bcc=DRAFT["bcc"],
        subject=DRAFT["subject"], body=DRAFT["body"],
        attachment_digests=DRAFT["attachment_digests"],
        owner_chat_id=CHAT_REF, reply_to_message_id=PREVIEW_ID,
    )
    fields = {
        "nonce": NONCE, "envelope": env, "envelope_hash": engine.envelope_hash(env),
        "owner_chat_id": CHAT_REF, "preview_message_id": PREVIEW_ID,
        "issued_at": _ts(-60), "expires_at": _ts(600),
    }
    fields.update(over)
    return engine.Approval(**fields)


def _staged(**over) -> dict:
    payload = {
        "kind": engine.STAGED_INTENT_KIND, "admissible": True, "refusal_reason": "",
        "nonce": NONCE, "telegram_chat_ref": CHAT_REF, "telegram_message_id": "4472",
        "telegram_reply_to_message_id": PREVIEW_ID, "staged_only": True,
        "maestro_may_execute": False, "execution_path": engine.EXECUTION_PATH,
    }
    payload.update(over)
    return payload


class FakeBroker:
    """Records every call so tests can assert on what was NOT attempted."""

    def __init__(self, draft=None, send_ok=True, send_data=None, readback=None, read_ok=True):
        self.calls: list[tuple[str, str, dict]] = []
        self.draft = dict(DRAFT if draft is None else draft)
        self.send_ok = send_ok
        self.send_data = send_data
        self.readback = readback
        self.read_ok = read_ok

    def __call__(self, agent, capability, params):
        self.calls.append((agent, capability, dict(params)))
        if capability == consumer.DRAFT_READ_CAPABILITY:
            if params.get("message_id"):
                if self.readback is None:
                    return {"ok": True, "data": dict(self.draft)}
                return {"ok": True, "data": dict(self.readback)}
            if not self.read_ok:
                return {"ok": False, "data": None, "error": "draft not found"}
            return {"ok": True, "data": dict(self.draft)}
        if capability == consumer.DRAFT_SEND_CAPABILITY:
            if not self.send_ok:
                return {"ok": False, "data": None, "error": "SEND_HOLD active"}
            data = self.send_data if self.send_data is not None else {
                "draft_id": params["draft_id"], "message_id": "m-99", "thread_id": "t-77",
            }
            return {"ok": True, "data": data}
        raise AssertionError(f"unexpected capability: {capability}")

    @property
    def sent(self) -> bool:
        return any(c[1] == consumer.DRAFT_SEND_CAPABILITY for c in self.calls)

    @property
    def capabilities(self) -> list[str]:
        return [c[1] for c in self.calls]


def _graduation(ok=True, exc=None):
    state = {"consumed": 0}

    def verify(*, consume=False, **_kw):
        if exc is not None:
            raise exc
        if consume:
            state["consumed"] += 1
        return {"graduation_id": "grad-1"} if ok else {}

    verify.state = state  # type: ignore[attr-defined]
    return verify


def _run(tmp_path, **over):
    kwargs = {
        "staged": _staged(),
        "request_payload_hash": PAYLOAD_HASH,
        "approval": _approval(),
        "owner_chat_allowlist": (CHAT_REF,),
        "broker_call": FakeBroker(),
        "verify_graduation": _graduation(),
        "lock_dir": tmp_path / "locks",
        "now": _ts(),
        "practice_mode": False,
    }
    kwargs.update(over)
    return consumer.consume_staged_approval(**kwargs), kwargs["broker_call"]


# ------------------------------------------------------------- non-vacuity

def test_a_fully_valid_approval_does_send(tmp_path) -> None:
    receipt, broker = _run(tmp_path)
    assert receipt.sent is True, receipt.to_dict()
    assert receipt.outcome == consumer.OUTCOME_SENT
    assert receipt.message_id == "m-99"
    assert receipt.thread_id == "t-77"
    assert receipt.graduation_id == "grad-1"
    for step in ("lock_acquired", "chat_binding", "not_replayed", "not_expired",
                 "draft_refetched", "envelope_unchanged", "graduation_consumed",
                 "broker_sent", "readback_verified"):
        assert step in receipt.steps_cleared


def test_practice_mode_clears_every_gate_and_still_sends_nothing(tmp_path) -> None:
    grad = _graduation()
    receipt, broker = _run(tmp_path, practice_mode=True, verify_graduation=grad)
    assert receipt.sent is False
    assert receipt.reason == consumer.R_PRACTICE
    assert "envelope_unchanged" in receipt.steps_cleared
    assert broker.sent is False
    assert grad.state["consumed"] == 0, "practice mode must not burn a one-time graduation"


# ------------------------------------------------------------ no live access

def test_the_consumer_imports_no_google_client_and_no_credentials() -> None:
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(consumer))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {"googleapiclient", "google", "google_auth_oauthlib", "smtplib",
                 "requests", "urllib", "http", "socket", "ssl"}
    assert not (imported & forbidden), f"consumer imports {sorted(imported & forbidden)}"


def test_gmail_is_only_ever_reached_through_the_broker(tmp_path) -> None:
    _, broker = _run(tmp_path)
    assert set(broker.capabilities) <= {consumer.DRAFT_READ_CAPABILITY,
                                        consumer.DRAFT_SEND_CAPABILITY}


def test_the_consumer_never_composes_text(tmp_path) -> None:
    _, broker = _run(tmp_path)
    send = [c for c in broker.calls if c[1] == consumer.DRAFT_SEND_CAPABILITY][0]
    assert set(send[2]) == {"draft_id"}, f"send carried extra params: {send[2]}"


# --------------------------------------------------------------- the ordering

def test_the_draft_is_refetched_before_the_graduation_is_consumed(tmp_path) -> None:
    order: list[str] = []
    broker = FakeBroker()
    real_call = broker.__call__

    def tracking(agent, capability, params):
        order.append(f"broker:{capability}")
        return real_call(agent, capability, params)

    def verify(*, consume=False, **_kw):
        order.append("graduation")
        return {"graduation_id": "grad-1"}

    _run(tmp_path, broker_call=tracking, verify_graduation=verify)
    assert order.index(f"broker:{consumer.DRAFT_READ_CAPABILITY}") < order.index("graduation")
    assert order.index("graduation") < order.index(f"broker:{consumer.DRAFT_SEND_CAPABILITY}")


def test_no_toctou_the_draft_read_happens_inside_the_lock(tmp_path) -> None:
    """A refusal before the lock must not have touched Gmail at all."""

    lock = consumer.NonceLock(tmp_path / "locks", NONCE)
    with lock:
        assert lock.acquired
        receipt, broker = _run(tmp_path)
        assert receipt.reason == consumer.R_LOCK_HELD
        assert broker.calls == [], "a locked-out worker still read the draft"


def test_the_lock_is_released_so_a_later_run_can_proceed(tmp_path) -> None:
    first, _ = _run(tmp_path)
    assert first.sent
    second, broker = _run(tmp_path)
    assert second.reason != consumer.R_LOCK_HELD


# ------------------------------------------------------------------ refusals

def test_no_send_on_recipient_drift(tmp_path) -> None:
    hostile = dict(DRAFT, to=["attacker@elsewhere.example"])
    receipt, broker = _run(tmp_path, broker_call=FakeBroker(draft=hostile))
    assert receipt.reason == consumer.R_DRIFT
    assert broker.sent is False


def test_no_send_on_body_drift(tmp_path) -> None:
    hostile = dict(DRAFT, body="Please wire to the new account.\n")
    receipt, broker = _run(tmp_path, broker_call=FakeBroker(draft=hostile))
    assert receipt.reason == consumer.R_DRIFT
    assert broker.sent is False


def test_no_send_on_attachment_drift(tmp_path) -> None:
    hostile = dict(DRAFT, attachment_digests=["sha256:" + "b" * 64])
    receipt, broker = _run(tmp_path, broker_call=FakeBroker(draft=hostile))
    assert receipt.reason == consumer.R_DRIFT
    assert broker.sent is False


def test_no_send_when_the_draft_vanished(tmp_path) -> None:
    receipt, broker = _run(tmp_path, broker_call=FakeBroker(read_ok=False))
    assert receipt.reason == consumer.R_DRAFT_MISSING
    assert broker.sent is False


def test_no_send_on_replay(tmp_path) -> None:
    receipt, broker = _run(tmp_path, approval=_approval(consumed_at=_ts(-5)))
    assert receipt.reason == consumer.R_REPLAYED
    assert broker.sent is False


def test_no_send_on_stale_nonce(tmp_path) -> None:
    receipt, broker = _run(tmp_path, approval=_approval(expires_at=_ts(-1)))
    assert receipt.reason == consumer.R_EXPIRED
    assert broker.sent is False


def test_no_send_from_the_wrong_chat(tmp_path) -> None:
    receipt, broker = _run(tmp_path, staged=_staged(telegram_chat_ref=OTHER_CHAT_REF))
    assert receipt.reason == consumer.R_CHAT
    assert broker.sent is False


def test_no_send_when_the_reply_target_is_wrong(tmp_path) -> None:
    receipt, broker = _run(tmp_path, staged=_staged(telegram_reply_to_message_id="9998"))
    assert receipt.reason == consumer.R_REPLY
    assert broker.sent is False


def test_no_send_when_the_graduation_refuses(tmp_path) -> None:
    receipt, broker = _run(tmp_path, verify_graduation=_graduation(ok=False))
    assert receipt.reason == consumer.R_GRADUATION
    assert broker.sent is False


def test_no_send_when_the_graduation_raises(tmp_path) -> None:
    receipt, broker = _run(tmp_path, verify_graduation=_graduation(exc=RuntimeError("stale")))
    assert receipt.reason == consumer.R_GRADUATION
    assert broker.sent is False


def test_an_inadmissible_staged_record_never_reaches_the_lock(tmp_path) -> None:
    receipt, broker = _run(tmp_path, staged=_staged(admissible=False,
                                                    refusal_reason=engine.REJECT_BARE_SEND))
    assert receipt.reason == consumer.R_NOT_ADMISSIBLE
    assert broker.calls == []


def test_a_staged_record_claiming_execution_rights_is_rejected(tmp_path) -> None:
    """Forged or malformed staging must not be honoured."""

    for forged in ({"maestro_may_execute": True}, {"staged_only": False}):
        receipt, broker = _run(tmp_path, staged=_staged(**forged))
        assert receipt.reason == consumer.R_STAGED_MISMATCH
        assert broker.sent is False


# ------------------------------------------------------------------ readback

def test_broker_refusal_is_a_failure_receipt_not_a_success(tmp_path) -> None:
    receipt, _ = _run(tmp_path, broker_call=FakeBroker(send_ok=False))
    assert receipt.outcome == consumer.OUTCOME_FAILED
    assert receipt.reason == consumer.R_BROKER
    assert receipt.sent is False


def test_a_readback_naming_a_different_draft_fails_the_receipt(tmp_path) -> None:
    broker = FakeBroker(send_data={"draft_id": "some-other-draft",
                                   "message_id": "m-99", "thread_id": "t-77"})
    receipt, _ = _run(tmp_path, broker_call=broker)
    assert receipt.outcome == consumer.OUTCOME_FAILED
    assert receipt.reason == consumer.R_READBACK


def test_a_send_with_no_message_id_is_never_reported_as_sent(tmp_path) -> None:
    broker = FakeBroker(send_data={"draft_id": DRAFT_ID, "message_id": "", "thread_id": ""})
    receipt, _ = _run(tmp_path, broker_call=broker)
    assert receipt.outcome == consumer.OUTCOME_FAILED
    assert receipt.reason == consumer.R_READBACK


def test_a_sent_message_with_different_recipients_fails_the_receipt(tmp_path) -> None:
    """The window between re-hash and release is real. Own it in the receipt."""

    broker = FakeBroker(readback=dict(DRAFT, to=["someone-else@elsewhere.example"]))
    receipt, _ = _run(tmp_path, broker_call=broker)
    assert receipt.outcome == consumer.OUTCOME_FAILED
    assert receipt.reason == consumer.R_READBACK
    assert receipt.message_id == "m-99", "a failed readback must still record what went out"


# ------------------------------------------------------------------- receipts

def test_receipts_carry_gmail_ids_and_never_claim_composition(tmp_path) -> None:
    receipt, _ = _run(tmp_path)
    payload = receipt.to_dict()
    assert payload["gmail_message_id"] == "m-99"
    assert payload["gmail_thread_id"] == "t-77"
    assert payload["composed_fresh_text"] is False
    assert payload["send_hold_graduation_id"] == "grad-1"
    assert payload["outcome"] == consumer.OUTCOME_SENT


def test_a_refusal_receipt_is_written_and_readable(tmp_path) -> None:
    import json

    receipt, _ = _run(tmp_path, approval=_approval(expires_at=_ts(-1)))
    path = consumer.write_receipt(receipt, receipt_dir=tmp_path / "receipts")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["outcome"] == consumer.OUTCOME_REFUSED
    assert payload["reason"] == consumer.R_EXPIRED
    assert payload["gmail_message_id"] == ""
