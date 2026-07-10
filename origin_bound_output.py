"""Typed, audience-safe outputs that can only be delivered by their bound adapter.

Runtime helpers may prepare text, documents, and approval prompts, but they do not own
Telegram credentials.  The live listener binds an :class:`OutputOrigin`, receives these
structured values, verifies the binding, and performs the sole network send.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping


OPERATOR_AUDIENCE = "operator"
GENERIC_SAFE_FAILURE = "Cassandra couldn't complete that request. Nothing was sent or changed."


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


@dataclass(frozen=True, slots=True)
class OutputOrigin:
    """The immutable route and audience that own an operator-visible output."""

    surface: str
    bot_identity: str
    chat_id: str
    source_message_id: str
    audience: str

    @classmethod
    def from_session_meta(
        cls,
        session_meta: Mapping[str, Any] | None,
        *,
        default_surface: str,
        default_bot_identity: str,
    ) -> "OutputOrigin":
        meta = session_meta or {}
        return cls(
            surface=_clean(meta.get("surface") or default_surface),
            bot_identity=_clean(meta.get("bot_identity") or default_bot_identity),
            chat_id=_clean(meta.get("sender_chat_id") or meta.get("chat_id")),
            source_message_id=_clean(meta.get("source_message_id")),
            audience=_clean(meta.get("source_user_label") or meta.get("audience") or "unverified_sender"),
        )

    @property
    def is_operator(self) -> bool:
        return self.audience == OPERATOR_AUDIENCE

    def binding_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.surface,
            self.bot_identity,
            self.chat_id,
            self.source_message_id,
            self.audience,
        )


def receipt_pointer(prefix: str, origin: OutputOrigin, *, salt: str = "") -> str:
    material = "|".join((*origin.binding_key(), _clean(salt)))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"{_clean(prefix) or 'origin-output'}-{digest}"


@dataclass(frozen=True, slots=True)
class OriginBoundOutput:
    """One transport-neutral output plus data that must remain internal."""

    origin: OutputOrigin
    delivery_id: str
    receipt_pointer: str
    kind: str
    operator_text: str
    generic_text: str = GENERIC_SAFE_FAILURE
    document_path: str = ""
    reply_markup: Mapping[str, Any] | None = None
    internal: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def guarded_text(
        cls,
        *,
        origin: OutputOrigin,
        delivery_id: str,
        receipt_pointer: str,
        operator_text: str,
        generic_text: str = GENERIC_SAFE_FAILURE,
        internal: Mapping[str, Any] | None = None,
        reply_markup: Mapping[str, Any] | None = None,
    ) -> "OriginBoundOutput":
        return cls(
            origin=origin,
            delivery_id=_clean(delivery_id),
            receipt_pointer=_clean(receipt_pointer),
            kind="text",
            operator_text=_clean(operator_text),
            generic_text=_clean(generic_text) or GENERIC_SAFE_FAILURE,
            reply_markup=reply_markup,
            internal=dict(internal or {}),
        )

    @classmethod
    def guarded_document(
        cls,
        *,
        origin: OutputOrigin,
        delivery_id: str,
        receipt_pointer: str,
        document_path: str,
        caption: str,
        generic_text: str = GENERIC_SAFE_FAILURE,
        internal: Mapping[str, Any] | None = None,
    ) -> "OriginBoundOutput":
        return cls(
            origin=origin,
            delivery_id=_clean(delivery_id),
            receipt_pointer=_clean(receipt_pointer),
            kind="document",
            operator_text=_clean(caption),
            generic_text=_clean(generic_text) or GENERIC_SAFE_FAILURE,
            document_path=str(document_path or ""),
            internal=dict(internal or {}),
        )

    def visible_text(self) -> str:
        return self.operator_text if self.origin.is_operator else self.generic_text


def collect_origin_outputs(value: Any) -> list[OriginBoundOutput]:
    """Collect structured outputs from cockpit result dictionaries without leaking internals."""

    found: list[OriginBoundOutput] = []
    seen: set[tuple[tuple[str, str, str, str, str], str]] = set()

    def visit(item: Any) -> None:
        if isinstance(item, OriginBoundOutput):
            key = (item.origin.binding_key(), item.delivery_id)
            if key not in seen:
                seen.add(key)
                found.append(item)
            return
        if isinstance(item, Mapping):
            if "origin_output" in item:
                visit(item.get("origin_output"))
            if "origin_outputs" in item:
                visit(item.get("origin_outputs"))
            if "results" in item:
                visit(item.get("results"))
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return found


class OriginMismatchError(RuntimeError):
    """Raised when an adapter is asked to deliver another origin's output."""


class OriginDeliveryTracker:
    """Bounded in-process duplicate guard for structured helper outputs.

    Telegram update-level idempotency is handled by the governed intake adapter.  This
    tracker separately guarantees that replaying one helper result cannot create a second
    transport send inside the same listener process.
    """

    def __init__(self, max_entries: int = 2048):
        self.max_entries = max(1, int(max_entries))
        self._delivered: OrderedDict[tuple[tuple[str, str, str, str, str], str], None] = OrderedDict()

    def claim(self, output: OriginBoundOutput, *, bound_origin: OutputOrigin) -> bool:
        if output.origin.binding_key() != bound_origin.binding_key():
            raise OriginMismatchError(
                "origin-bound output does not match the listener adapter binding"
            )
        key = (output.origin.binding_key(), output.delivery_id)
        if key in self._delivered:
            self._delivered.move_to_end(key)
            return False
        self._delivered[key] = None
        while len(self._delivered) > self.max_entries:
            self._delivered.popitem(last=False)
        return True

    def release(self, output: OriginBoundOutput) -> None:
        """Roll back a claim when the bound transport did not complete."""

        key = (output.origin.binding_key(), output.delivery_id)
        self._delivered.pop(key, None)


__all__ = [
    "GENERIC_SAFE_FAILURE",
    "OPERATOR_AUDIENCE",
    "OriginBoundOutput",
    "OriginDeliveryTracker",
    "OriginMismatchError",
    "OutputOrigin",
    "collect_origin_outputs",
    "receipt_pointer",
]
