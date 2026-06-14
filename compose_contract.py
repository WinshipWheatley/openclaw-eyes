"""Shared types for the unified composer and gate pipeline.

This module is dependency-free by design. It defines the result shapes shared by
the composer, API transport, and future executor surfaces. It performs no
SQLite writes and has no external side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateState(str, Enum):
    READ_ONLY = "READ_ONLY"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    DONE = "DONE"
    REWORK = "REWORK"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


ACTION_INTENTS: frozenset[str] = frozenset(
    {
        "email_send",
        "sms_send",
        "invoice_send",
        "billing_continue",
        "phone_log",
        "obs_launch",
        "livestream_setup",
    }
)


def is_action_intent(intent: str | None) -> bool:
    return bool(intent) and intent in ACTION_INTENTS


@dataclass(frozen=True)
class ApprovalPreview:
    packet_id: str
    surface: str
    preview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "surface": self.surface,
            "preview": dict(self.preview),
        }


@dataclass(frozen=True)
class ComposeResult:
    intent: str
    gate_state: GateState
    segments: list[str] = field(default_factory=list)
    packet_id: str | None = None
    pending_approval: ApprovalPreview | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "gate_state": self.gate_state.value,
            "segments": list(self.segments),
            "packet_id": self.packet_id,
            "pending_approval": self.pending_approval.to_dict() if self.pending_approval else None,
            "meta": dict(self.meta),
        }

    @classmethod
    def read_only(cls, intent: str, segments: list[str], **meta: Any) -> "ComposeResult":
        return cls(intent=intent, gate_state=GateState.READ_ONLY, segments=segments, meta=meta)

    @classmethod
    def pending(
        cls,
        intent: str,
        packet_id: str,
        surface: str,
        segments: list[str],
        preview: dict[str, Any] | None = None,
        **meta: Any,
    ) -> "ComposeResult":
        return cls(
            intent=intent,
            gate_state=GateState.PENDING_APPROVAL,
            segments=segments,
            packet_id=packet_id,
            pending_approval=ApprovalPreview(
                packet_id=packet_id,
                surface=surface,
                preview=preview or {},
            ),
            meta=meta,
        )

    @classmethod
    def blocked(cls, intent: str, reason: str, **meta: Any) -> "ComposeResult":
        return cls(intent=intent, gate_state=GateState.BLOCKED, segments=[reason], meta=meta)


@dataclass(frozen=True)
class ExecutionReceipt:
    packet_id: str
    surface: str
    ok: bool
    detail: str = ""
    side_effect_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def gate_state(self) -> GateState:
        return GateState.DONE if self.ok else GateState.FAILED

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "surface": self.surface,
            "ok": self.ok,
            "gate_state": self.gate_state.value,
            "detail": self.detail,
            "side_effect_id": self.side_effect_id,
            "meta": dict(self.meta),
        }
