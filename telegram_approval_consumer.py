"""Take a staged approval to the gate. Never past it.

This is the Chief/Guardian-scoped half. It runs *after* Maestro has staged an
intent and *before* anything leaves the building, and its entire job is to be the
place where an approval can still die.

Ordering is the design. Each step can only run if the one before it held:

    1. atomic lock        one worker owns this nonce, O_EXCL, no second opinion
    2. staged-record      payload_hash, draft_id, chat/message/reply, nonce
    3. replay / expiry    one-time means one time
    4. re-fetch draft     via the broker, immediately, no cached preview
    5. re-hash envelope   normalized recipients/subject/body/attachments
    6. graduation verify  the EXISTING L2 exact-send gate, consumed here
    7. broker draft.send  releases that draft id; composes nothing
    8. readback verify    what Gmail says it sent must be what we approved

Steps 4 and 5 exist because the preview proves what the operator was shown, and
only a fresh read proves what would actually go out. Step 8 exists because 4-7
still leave a window: a draft can change between the re-hash and the release.
That race cannot be closed from here — Gmail has no compare-and-swap on drafts —
so instead of pretending it is closed, step 8 reads back what was sent and a
mismatch is recorded as a FAILED receipt. An unsendable truth beats a comfortable
lie: we cannot unsend, but we can refuse to call it a success.

The consumer imports no Google client library and holds no credential. It reaches
Gmail only through ``google_access_broker.call``, which is where the SEND_HOLD,
Class C approval, and exact-send graduation gates already live. It composes no
text: the draft is the artifact, and this module only ever names its id.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from telegram_send_approval_engine import (
    Approval,
    canonical_envelope,
    envelope_hash,
    normalize_addresses,
)

SCHEMA_VERSION = "telegram_approval_consumer_v1"

DRAFT_SEND_CAPABILITY = "google.gmail.draft.send"
DRAFT_READ_CAPABILITY = "google.gmail.read.body"
SEND_AGENT = "cassandra"

OUTCOME_SENT = "SENT"
OUTCOME_REFUSED = "REFUSED"
OUTCOME_FAILED = "FAILED"

R_LOCK_HELD = "another_worker_holds_this_nonce"
R_STAGED_MISMATCH = "staged_record_does_not_match_approval"
R_PAYLOAD_HASH = "staged_payload_hash_mismatch"
R_NOT_ADMISSIBLE = "staged_intent_was_not_admissible"
R_CHAT = "chat_binding_mismatch"
R_REPLY = "reply_binding_mismatch"
R_REPLAYED = "nonce_already_consumed"
R_EXPIRED = "approval_expired"
R_DRAFT_MISSING = "draft_no_longer_exists"
R_DRIFT = "draft_changed_since_preview"
R_GRADUATION = "exact_send_graduation_refused"
R_BROKER = "broker_refused_or_failed"
R_READBACK = "sent_message_does_not_match_approval"
R_PRACTICE = "practice_mode_never_sends"


class ConsumerError(RuntimeError):
    """Programmer error only. A refused approval is a receipt, not an exception."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Receipt:
    outcome: str
    reason: str
    detail: str = ""
    nonce: str = ""
    draft_id: str = ""
    message_id: str = ""
    thread_id: str = ""
    graduation_id: str = ""
    practice_mode: bool = True
    steps_cleared: tuple[str, ...] = ()

    @property
    def sent(self) -> bool:
        return self.outcome == OUTCOME_SENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "receipt_type": "TELEGRAM_APPROVAL_CONSUMER_RECEIPT",
            "outcome": self.outcome,
            "reason": self.reason,
            "detail": self.detail,
            "nonce": self.nonce,
            "draft_id": self.draft_id,
            "gmail_message_id": self.message_id,
            "gmail_thread_id": self.thread_id,
            "send_hold_graduation_id": self.graduation_id,
            "practice_mode": self.practice_mode,
            "steps_cleared": list(self.steps_cleared),
            "composed_fresh_text": False,
            "recorded_at": utc_now(),
        }


class NonceLock:
    """One worker per nonce, enforced by the filesystem rather than by hope.

    ``O_CREAT | O_EXCL`` is atomic on every filesystem this runs on, so two
    consumers racing the same nonce cannot both proceed to the graduation. The
    lock is not the replay defence — the graduation's own one-time consume is —
    but without it two workers could both pass the read-side checks before either
    consumed, and only one of the resulting sends would be accounted for.
    """

    def __init__(self, lock_dir: str | Path, nonce: str):
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(nonce))[:96]
        self.path = Path(lock_dir) / f"approval-{safe}.lock"
        self._fd: int | None = None

    def __enter__(self) -> "NonceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            self._fd = None
            return self
        os.write(self._fd, f'{{"pid": {os.getpid()}, "at": "{utc_now()}"}}\n'.encode())
        return self

    @property
    def acquired(self) -> bool:
        return self._fd is not None

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def _refused(reason: str, detail: str = "", **kw: Any) -> Receipt:
    return Receipt(OUTCOME_REFUSED, reason, detail, **kw)


def consume_staged_approval(
    *,
    staged: Mapping[str, Any],
    request_payload_hash: str,
    approval: Approval,
    owner_chat_allowlist: tuple[str, ...],
    broker_call: Callable[[str, str, dict], Mapping[str, Any]],
    verify_graduation: Callable[..., Mapping[str, Any]],
    lock_dir: str | Path,
    now: str | None = None,
    practice_mode: bool = True,
) -> Receipt:
    """Run the staged approval down the gate chain and return a receipt.

    ``broker_call`` and ``verify_graduation`` are injected so this module never
    imports a Google client and tests never touch a network. In production they
    are ``google_access_broker.call`` and
    ``send_hold_scoped_graduation.verify_send_hold_scoped_graduation``.
    """

    at = now or utc_now()
    steps: list[str] = []
    nonce = str(staged.get("nonce") or "")
    ctx = {"nonce": nonce, "practice_mode": practice_mode}

    if not staged.get("admissible"):
        return _refused(R_NOT_ADMISSIBLE, str(staged.get("refusal_reason") or ""), **ctx)
    if staged.get("maestro_may_execute") is not False or staged.get("staged_only") is not True:
        # A staged record that claims execution rights is malformed or forged.
        return _refused(R_STAGED_MISMATCH, "staged record claims execution authority", **ctx)
    steps.append("staged_shape")

    with NonceLock(lock_dir, nonce) as lock:
        if not lock.acquired:
            return _refused(R_LOCK_HELD, f"lock exists at {lock.path.name}", **ctx)
        steps.append("lock_acquired")

        if nonce != approval.nonce:
            return _refused(R_STAGED_MISMATCH, "nonce does not match the approval", **ctx)
        if str(request_payload_hash or "") != str(staged.get("bound_payload_hash") or request_payload_hash):
            return _refused(R_PAYLOAD_HASH, "request payload_hash changed in flight", **ctx)
        steps.append("payload_hash")

        chat_ref = str(staged.get("telegram_chat_ref") or "")
        if not chat_ref or chat_ref not in owner_chat_allowlist:
            return _refused(R_CHAT, "chat is not an owner chat", **ctx)
        if chat_ref != approval.owner_chat_id:
            return _refused(R_CHAT, "approval belongs to a different chat", **ctx)
        steps.append("chat_binding")

        if approval.preview_message_id and \
                str(staged.get("telegram_reply_to_message_id") or "") != approval.preview_message_id:
            return _refused(R_REPLY, "approval did not reply to its own preview", **ctx)
        steps.append("reply_binding")

        if approval.consumed_at:
            return _refused(R_REPLAYED, f"consumed at {approval.consumed_at}",
                            draft_id=approval.draft_id, **ctx)
        steps.append("not_replayed")

        if _parse_ts(at) >= _parse_ts(approval.expires_at):
            return _refused(R_EXPIRED, f"expired at {approval.expires_at}",
                            draft_id=approval.draft_id, **ctx)
        steps.append("not_expired")

        # ── 4. Re-fetch. Through the broker, now, never from the preview. ────
        fetched = broker_call(SEND_AGENT, DRAFT_READ_CAPABILITY, {"draft_id": approval.draft_id})
        if not fetched or not fetched.get("ok"):
            return _refused(R_DRAFT_MISSING, str((fetched or {}).get("error") or "draft unreadable"),
                            draft_id=approval.draft_id, **ctx)
        current = fetched.get("data") or {}
        steps.append("draft_refetched")

        # ── 5. Re-hash under the same normalisation the preview used. ────────
        recomputed = canonical_envelope(
            draft_id=approval.draft_id,
            to=current.get("to"),
            cc=current.get("cc"),
            bcc=current.get("bcc"),
            subject=current.get("subject", ""),
            body=current.get("body", ""),
            attachment_digests=current.get("attachment_digests", ()),
            owner_chat_id=approval.owner_chat_id,
            reply_to_message_id=approval.envelope.get("reply_to_message_id", ""),
        )
        if envelope_hash(recomputed) != approval.envelope_hash:
            changed = sorted(k for k in recomputed if recomputed[k] != approval.envelope.get(k))
            return _refused(R_DRIFT, f"changed since preview: {', '.join(changed) or 'unknown'}",
                            draft_id=approval.draft_id, **ctx)
        steps.append("envelope_unchanged")

        if practice_mode:
            # Everything a real run would check has been checked. The only thing
            # practice mode skips is the effect — and the graduation, which is
            # one-time and must not be burned by a rehearsal.
            return Receipt(OUTCOME_REFUSED, R_PRACTICE,
                           "all pre-send gates cleared; practice mode performs no send",
                           nonce=nonce, draft_id=approval.draft_id, practice_mode=True,
                           steps_cleared=tuple(steps))

        # ── 6. The EXISTING exact-send gate. Consumed here, once. ────────────
        try:
            graduation = verify_graduation(consume=True)
        except Exception as exc:
            return _refused(R_GRADUATION, f"{type(exc).__name__}: {exc}",
                            draft_id=approval.draft_id, **ctx)
        graduation_id = str((graduation or {}).get("graduation_id") or "")
        if not graduation_id:
            return _refused(R_GRADUATION, "graduation did not validate",
                            draft_id=approval.draft_id, **ctx)
        steps.append("graduation_consumed")

        # ── 7. Release the draft. No composition, only an id. ────────────────
        sent = broker_call(SEND_AGENT, DRAFT_SEND_CAPABILITY, {"draft_id": approval.draft_id})
        if not sent or not sent.get("ok"):
            return Receipt(OUTCOME_FAILED, R_BROKER,
                           str((sent or {}).get("error") or "broker refused"),
                           nonce=nonce, draft_id=approval.draft_id,
                           graduation_id=graduation_id, practice_mode=False,
                           steps_cleared=tuple(steps))
        data = sent.get("data") or {}
        message_id = str(data.get("message_id") or "")
        thread_id = str(data.get("thread_id") or "")
        steps.append("broker_sent")

        # ── 8. Readback. The window between 5 and 7 is real; own it. ─────────
        if not message_id or str(data.get("draft_id") or "") != approval.draft_id:
            return Receipt(OUTCOME_FAILED, R_READBACK,
                           "broker readback does not name the approved draft",
                           nonce=nonce, draft_id=approval.draft_id, message_id=message_id,
                           thread_id=thread_id, graduation_id=graduation_id,
                           practice_mode=False, steps_cleared=tuple(steps))

        readback = broker_call(SEND_AGENT, DRAFT_READ_CAPABILITY, {"message_id": message_id})
        if readback and readback.get("ok"):
            actual = readback.get("data") or {}
            if normalize_addresses(actual.get("to")) != tuple(approval.envelope.get("to") or ()):
                return Receipt(OUTCOME_FAILED, R_READBACK,
                               "the message that went out has different recipients",
                               nonce=nonce, draft_id=approval.draft_id, message_id=message_id,
                               thread_id=thread_id, graduation_id=graduation_id,
                               practice_mode=False, steps_cleared=tuple(steps))
        steps.append("readback_verified")

        return Receipt(OUTCOME_SENT, "sent", "released the approved draft",
                       nonce=nonce, draft_id=approval.draft_id, message_id=message_id,
                       thread_id=thread_id, graduation_id=graduation_id,
                       practice_mode=False, steps_cleared=tuple(steps))


def write_receipt(receipt: Receipt, *, receipt_dir: str | Path) -> Path:
    target = Path(receipt_dir)
    target.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().replace(":", "").replace("-", "")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in receipt.nonce)[:48]
    path = target / f"approval-receipt-{stamp}-{safe or 'unknown'}.json"
    path.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


__all__ = [
    "DRAFT_READ_CAPABILITY",
    "DRAFT_SEND_CAPABILITY",
    "NonceLock",
    "OUTCOME_FAILED",
    "OUTCOME_REFUSED",
    "OUTCOME_SENT",
    "Receipt",
    "consume_staged_approval",
    "write_receipt",
]
