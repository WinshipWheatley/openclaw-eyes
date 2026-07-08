"""Immutable, versioned operator-stated recurrence rule record.

Task 136a: "I send St Anne's a new invoice on the first of every month" is an operator
STATEMENT of a recurring business rule -- captured once, remembered, and consumed by
derivation. Records are IMMUTABLE + VERSIONED (mirrors ar_expected_receivable_record's
supersedes pattern): a stated correction creates a NEW version superseding the old, never
edits or deletes. Consumers read ONLY latest-unsuperseded.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

VALID_EVENT_TYPES = frozenset({"invoice_send"})
VALID_SCHEDULE_KINDS = frozenset({"monthly_day"})


@dataclass(frozen=True)
class RecurrenceRuleRecord:
    rule_id: str
    rule_version_id: str
    client_ref: str
    event_type: str
    schedule_kind: str
    schedule_day: int
    stated_as_of: str
    provenance_raw: str
    truth_status: str
    source_ref: str
    supersedes_rule_version_id: str | None = None
    terminated: bool = False

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("rule_id is required")
        if not self.rule_version_id:
            raise ValueError("rule_version_id is required")
        if not self.client_ref:
            raise ValueError("client_ref is required")
        if self.event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"unknown event_type: {self.event_type!r}")
        if self.schedule_kind not in VALID_SCHEDULE_KINDS:
            raise ValueError(f"unknown schedule_kind: {self.schedule_kind!r}")
        if type(self.schedule_day) is not int or not (1 <= self.schedule_day <= 28):
            raise ValueError("schedule_day must be an integer 1-28 (calendar-safe across all months)")
        if not str(self.stated_as_of or "").strip():
            raise ValueError("stated_as_of is required")
        if not str(self.provenance_raw or "").strip():
            raise ValueError("provenance_raw is required (verbatim operator text)")
        if not str(self.truth_status or "").strip():
            raise ValueError("truth_status is required")
        if not str(self.source_ref or "").strip():
            raise ValueError("source_ref is required")


def create_recurrence_rule(
    *,
    client_ref: str,
    event_type: str,
    schedule_kind: str,
    schedule_day: int,
    stated_as_of: str,
    provenance_raw: str,
    source_ref: str,
    truth_status: str = "operator_directive",
    rule_id: str | None = None,
    supersedes_rule_version_id: str | None = None,
    terminated: bool = False,
) -> RecurrenceRuleRecord:
    if not rule_id:
        rule_id = f"rule:{uuid.uuid4().hex}"
    return RecurrenceRuleRecord(
        rule_id=rule_id,
        rule_version_id=f"rule_ver:{uuid.uuid4().hex}",
        client_ref=client_ref,
        event_type=event_type,
        schedule_kind=schedule_kind,
        schedule_day=schedule_day,
        stated_as_of=stated_as_of,
        provenance_raw=provenance_raw,
        truth_status=truth_status,
        source_ref=source_ref,
        supersedes_rule_version_id=supersedes_rule_version_id,
        terminated=terminated,
    )
