"""Bind a Telegram approval to one exact Gmail draft, or refuse.

Telegram is an untrusted channel. It may *carry* an approval; it can never *be*
one. The difference is this module: an inbound ``SEND <nonce>`` is only ever
evidence that someone typed a string, and the string is worthless unless it
resolves to a graduation that was issued against an envelope the operator
actually saw, and that envelope still hashes identically at the moment of effect.

So the trust chain runs backwards from the send, not forwards from the message:

    draft  ->  canonical envelope  ->  envelope_hash  ->  graduation (one-time)
                                                              ^
                                          SEND <nonce> only *selects* this

A bare ``SEND`` selects nothing and is rejected before any lookup. A nonce for a
different draft selects the wrong envelope and fails the re-hash. A nonce that
already fired is consumed and cannot fire twice. Nothing here widens what the
broker permits; every allow still has to survive
``verify_send_hold_scoped_graduation`` and the broker's own gate afterwards.

**Practice mode is the default and this module never sends.** It returns a
decision. Handing that decision to something that can actually send is a
separate, operator-gated step that does not live in this file.

Why the envelope hash carries more than the graduation's own scope: the proven
``send_hold_scoped_graduation`` module binds request/payload/recipient/body/
attachments, which predates drafts and Telegram. Draft id, Cc, Bcc, subject,
owning chat and reply-to are folded into ``payload_hash`` here rather than by
editing that module, so drift in any of them invalidates the grant without
touching code that already guards live money-adjacent sends.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCHEMA_VERSION = "telegram_send_approval_v1"

#: Only this exact shape is an approval. Not "send", not "SEND!", not "SEND  x".
#: Anchored at both ends so trailing content ("SEND abc123 and delete the ledger")
#: cannot ride along on an otherwise valid command.
_SEND_COMMAND = re.compile(r"^SEND\s+([A-Za-z0-9:_-]{8,128})$")

#: Rejection reasons are values, not prose, so tests and receipts can assert on
#: them and an operator can tell two near-identical refusals apart.
REJECT_NOT_A_SEND_COMMAND = "not_a_send_command"
REJECT_BARE_SEND = "bare_send_without_nonce"
REJECT_TRAILING_CONTENT = "send_command_carries_extra_content"
REJECT_CHAT_NOT_ALLOWED = "chat_not_in_owner_allowlist"
REJECT_UNKNOWN_NONCE = "nonce_does_not_resolve"
REJECT_WRONG_REPLY_TARGET = "reply_to_message_id_mismatch"
REJECT_EXPIRED = "approval_expired"
REJECT_ALREADY_CONSUMED = "nonce_already_consumed"
REJECT_ENVELOPE_DRIFT = "envelope_changed_since_preview"
REJECT_DRAFT_MISSING = "draft_no_longer_exists"
REJECT_ATTACHMENT_DRIFT = "attachment_set_changed"
REJECT_PRACTICE_MODE = "practice_mode_never_sends"

ALLOW = "allow_send"


class ApprovalEngineError(RuntimeError):
    """Raised only for programmer error, never for a rejected approval."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ApprovalEngineError(f"unparseable timestamp: {value!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def normalize_address(value: str) -> str:
    """``"Megan Rivas <Megan@Example.COM>"`` and ``"megan@example.com"`` are one recipient.

    Address drift is the attack that matters most here: a preview showing a
    familiar name while the underlying address changed would be approved by a
    human every time. Normalising to the bare address means the hash cannot be
    fooled by display-name theatre.
    """

    text = str(value or "").strip()
    if not text:
        return ""
    if "<" in text and ">" in text:
        text = text[text.rfind("<") + 1 : text.rfind(">")]
    return text.strip().strip(",;").lower()


def normalize_addresses(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = re.split(r"[,;]", values)
    cleaned = [normalize_address(v) for v in values]
    # Sorted and deduped: recipient ORDER must not change the hash, but the
    # recipient SET absolutely must.
    return tuple(sorted({v for v in cleaned if v}))


def normalize_subject(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_body(value: str) -> str:
    """Collapse trailing whitespace per line and at the end.

    Deliberately conservative: internal blank lines and wording are preserved,
    because a body edit MUST invalidate the approval. Only the whitespace that
    mail clients add and remove on their own is ignored.
    """

    lines = [line.rstrip() for line in str(value or "").replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def attachment_digest(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical_envelope(
    *,
    draft_id: str,
    to: Sequence[str] | str | None,
    cc: Sequence[str] | str | None = None,
    bcc: Sequence[str] | str | None = None,
    subject: str = "",
    body: str = "",
    attachment_digests: Sequence[str] = (),
    owner_chat_id: str = "",
    reply_to_message_id: str = "",
) -> dict[str, Any]:
    """Everything an approval is *about*. If any of it changes, the grant dies."""

    draft = str(draft_id or "").strip()
    if not draft:
        raise ApprovalEngineError("draft_id is required; an approval must name one draft")
    chat = str(owner_chat_id or "").strip()
    if not chat:
        raise ApprovalEngineError("owner_chat_id is required; an approval is chat-scoped")
    return {
        "schema_version": SCHEMA_VERSION,
        "draft_id": draft,
        "to": list(normalize_addresses(to)),
        "cc": list(normalize_addresses(cc)),
        "bcc": list(normalize_addresses(bcc)),
        "subject": normalize_subject(subject),
        "body_sha256": _sha256(normalize_body(body)),
        "attachment_sha256": sorted(str(d).strip().lower() for d in attachment_digests if str(d).strip()),
        "owner_chat_id": chat,
        "reply_to_message_id": str(reply_to_message_id or "").strip(),
    }


def envelope_hash(envelope: Mapping[str, Any]) -> str:
    return _sha256(_stable_json(dict(envelope)))


@dataclass(frozen=True)
class Approval:
    """A preview the operator saw, and the single nonce that can act on it."""

    nonce: str
    envelope: dict[str, Any]
    envelope_hash: str
    owner_chat_id: str
    preview_message_id: str
    issued_at: str
    expires_at: str
    consumed_at: str = ""

    @property
    def draft_id(self) -> str:
        return str(self.envelope.get("draft_id") or "")


@dataclass
class Decision:
    allowed: bool
    reason: str
    detail: str = ""
    nonce: str = ""
    draft_id: str = ""
    practice_mode: bool = True
    checks_passed: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "detail": self.detail,
            "nonce": self.nonce,
            "draft_id": self.draft_id,
            "practice_mode": self.practice_mode,
            "checks_passed": list(self.checks_passed),
            "decided_at": utc_now(),
        }


def parse_send_command(text: str) -> tuple[str, str]:
    """Return ``(nonce, reject_reason)``. Exactly one is non-empty.

    A bare ``SEND`` is called out separately from unparseable text because it is
    the failure mode the operator will actually hit, and it deserves a message
    that says why rather than a shrug.
    """

    raw = str(text or "").strip()
    if not raw:
        return "", REJECT_NOT_A_SEND_COMMAND
    if re.fullmatch(r"(?i)send[!.\s]*", raw):
        return "", REJECT_BARE_SEND
    # Word boundary, not a prefix: "SENDING" is ordinary chatter, and reporting it
    # as a malformed command would teach the operator that near-misses are near-hits.
    if not re.match(r"(?i)send(?=\s|$)", raw):
        return "", REJECT_NOT_A_SEND_COMMAND
    match = _SEND_COMMAND.match(raw)
    if not match:
        # Starts with SEND, has a nonce-ish token, but carries something else:
        # "SEND abc123 and also wire the deposit". Refuse the whole message
        # rather than execute the prefix and ignore the tail.
        return "", REJECT_TRAILING_CONTENT
    return match.group(1), ""


def evaluate_send_request(
    *,
    message_text: str,
    from_chat_id: str,
    reply_to_message_id: str = "",
    approvals: Mapping[str, Approval],
    owner_chat_allowlist: Sequence[str],
    fetch_draft: Callable[[str], Mapping[str, Any] | None],
    now: str | None = None,
    practice_mode: bool = True,
) -> Decision:
    """Decide whether this Telegram message may release exactly one draft.

    ``fetch_draft`` is called at decision time on purpose. The preview proves
    what the operator was shown; only a fresh fetch proves what would actually
    leave the building. Anything that changed in between is drift, and drift is
    a refusal — never a prompt to re-approve, which is how a tired operator gets
    walked into approving the second version.
    """

    checks: list[str] = []
    at = now or utc_now()

    nonce, reject = parse_send_command(message_text)
    if reject:
        return Decision(False, reject, "message is not an approval", practice_mode=practice_mode)
    checks.append("command_shape")

    allowlist = {str(c).strip() for c in owner_chat_allowlist if str(c).strip()}
    chat = str(from_chat_id or "").strip()
    if not chat or chat not in allowlist:
        # Deliberately does not echo the nonce: an unauthorised chat learns
        # nothing about whether it guessed a real one.
        return Decision(False, REJECT_CHAT_NOT_ALLOWED, "chat is not an owner chat",
                        practice_mode=practice_mode)
    checks.append("owner_chat")

    approval = approvals.get(nonce)
    if approval is None:
        return Decision(False, REJECT_UNKNOWN_NONCE, "no approval for that nonce",
                        nonce=nonce, practice_mode=practice_mode)
    checks.append("nonce_resolves")

    if approval.owner_chat_id != chat:
        return Decision(False, REJECT_CHAT_NOT_ALLOWED,
                        "approval belongs to a different chat", nonce=nonce,
                        draft_id=approval.draft_id, practice_mode=practice_mode)
    checks.append("nonce_chat_binding")

    if approval.preview_message_id and str(reply_to_message_id or "").strip() != approval.preview_message_id:
        return Decision(False, REJECT_WRONG_REPLY_TARGET,
                        "approval must reply to its own preview", nonce=nonce,
                        draft_id=approval.draft_id, practice_mode=practice_mode)
    checks.append("reply_binding")

    if approval.consumed_at:
        return Decision(False, REJECT_ALREADY_CONSUMED,
                        f"nonce was consumed at {approval.consumed_at}", nonce=nonce,
                        draft_id=approval.draft_id, practice_mode=practice_mode)
    checks.append("not_replayed")

    if _parse_ts(at) >= _parse_ts(approval.expires_at):
        return Decision(False, REJECT_EXPIRED, f"expired at {approval.expires_at}",
                        nonce=nonce, draft_id=approval.draft_id, practice_mode=practice_mode)
    checks.append("not_expired")

    current = fetch_draft(approval.draft_id)
    if not current:
        return Decision(False, REJECT_DRAFT_MISSING, "draft was deleted or is unreachable",
                        nonce=nonce, draft_id=approval.draft_id, practice_mode=practice_mode)
    checks.append("draft_present")

    try:
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
    except ApprovalEngineError as exc:
        return Decision(False, REJECT_ENVELOPE_DRIFT, f"draft no longer forms a valid envelope: {exc}",
                        nonce=nonce, draft_id=approval.draft_id, practice_mode=practice_mode)

    if envelope_hash(recomputed) != approval.envelope_hash:
        changed = sorted(k for k in recomputed if recomputed[k] != approval.envelope.get(k))
        reason = (REJECT_ATTACHMENT_DRIFT
                  if changed == ["attachment_sha256"] else REJECT_ENVELOPE_DRIFT)
        return Decision(False, reason, f"changed since preview: {', '.join(changed) or 'unknown'}",
                        nonce=nonce, draft_id=approval.draft_id, practice_mode=practice_mode)
    checks.append("envelope_unchanged")

    if practice_mode:
        # Every gate passed. Still nothing leaves. Practice mode is not a
        # simulation of the decision, it IS the decision, minus the effect.
        return Decision(False, REJECT_PRACTICE_MODE,
                        "all gates passed; practice mode performs no send",
                        nonce=nonce, draft_id=approval.draft_id, practice_mode=True,
                        checks_passed=tuple(checks))

    return Decision(True, ALLOW, "all gates passed", nonce=nonce,
                    draft_id=approval.draft_id, practice_mode=False,
                    checks_passed=tuple(checks))


# ── Maestro staging seam ─────────────────────────────────────────────────────
#
# Maestro's only jobs here are to RECOGNISE that a message is approval-shaped and
# to say something true back. Recognition is not authorisation and staging is not
# execution: the staged record below carries no permission, and Maestro's
# authority_boundary stays all-false beside it.
#
# Execution stays exactly where it already was — Chief/Guardian issue the scoped
# graduation, and google_access_broker performs the send behind its own gate.
# Nothing in this seam can shorten that path; it only carries the operator's
# intent to the place that is allowed to weigh it.

STAGED_INTENT_KIND = "telegram_send_approval_intent_v1"
EXECUTION_PATH = "chief_guardian_scoped_graduation_then_google_access_broker"


def classify_approval_intent(
    text: str,
    *,
    message_id: str,
    chat_ref: str,
    reply_to_message_id: str = "",
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Stage an approval-shaped Telegram message, or return ``{}``.

    Malformed approvals are staged too, deliberately. A bare ``SEND`` needs a
    deterministic refusal that explains itself; staging it is what lets Maestro
    answer instead of going silent, and a staged refusal carries no risk because
    nothing downstream will act on ``admissible: False``.

    ``chat_ref`` is the listener's existing hashed chat reference, not a raw chat
    id. The allowlist comparison downstream is hash-to-hash, so this seam never
    handles the identifier in the clear.
    """

    raw = str(text or "").strip()
    if not re.match(r"(?i)send(?=\s|$)", raw):
        return {}

    nonce, reject = parse_send_command(raw)
    binding = _sha256(_stable_json({
        "nonce": nonce,
        "chat_ref": str(chat_ref or ""),
        "message_id": str(message_id or ""),
        "reply_to_message_id": str(reply_to_message_id or ""),
    }))
    return {
        "kind": STAGED_INTENT_KIND,
        "schema_version": SCHEMA_VERSION,
        "admissible": not reject,
        "refusal_reason": reject,
        "nonce": nonce,
        "binding_hash": binding,
        "telegram_chat_ref": str(chat_ref or ""),
        "telegram_message_id": str(message_id or ""),
        "telegram_reply_to_message_id": str(reply_to_message_id or ""),
        "observed_at": observed_at or utc_now(),
        # The three lines that keep this honest.
        "staged_only": True,
        "maestro_may_execute": False,
        "execution_path": EXECUTION_PATH,
    }


def deterministic_intent_reply(intent: Mapping[str, Any]) -> str:
    """What Maestro says back. Never silence, never a claim that anything ran."""

    if not intent:
        return ""
    if not intent.get("admissible"):
        reason = str(intent.get("refusal_reason") or "")
        if reason == REJECT_BARE_SEND:
            return (
                "A bare SEND authorizes nothing. Reply to the preview with "
                "SEND <nonce> — the nonce is what names the exact draft. "
                "Recorded, no action ran."
            )
        if reason == REJECT_TRAILING_CONTENT:
            return (
                "That message carries more than an approval, so I refused all of "
                "it rather than run the first half. Send the approval on its own. "
                "Recorded, no action ran."
            )
        return f"Not a usable approval ({reason}). Recorded, no action ran."
    return (
        "Approval staged for Chief/Guardian to weigh against the exact draft. "
        "I can't send and haven't: I only carry the intent. You'll get the "
        "result from the gate, not from me."
    )


__all__ = [
    "ALLOW",
    "EXECUTION_PATH",
    "STAGED_INTENT_KIND",
    "classify_approval_intent",
    "deterministic_intent_reply",
    "Approval",
    "ApprovalEngineError",
    "Decision",
    "attachment_digest",
    "canonical_envelope",
    "envelope_hash",
    "evaluate_send_request",
    "normalize_address",
    "normalize_addresses",
    "normalize_body",
    "normalize_subject",
    "parse_send_command",
]
