"""Inert local future-action queue helper used by Cassandra connector checks.

This module defines the local shape for queued future actions. It does not run
workers, schedule external jobs, send messages, or mutate business systems.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class FutureActionQueueItem:
    """Metadata-only description of a future action candidate."""

    action_id: str
    requested_by: str
    summary: str
    status: str = "queued_candidate"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload["created_at"]:
            payload["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return payload


def build_future_action_candidate(*, action_id: str, requested_by: str, summary: str) -> dict[str, Any]:
    """Return a candidate record without dispatching or executing it."""

    return FutureActionQueueItem(
        action_id=action_id,
        requested_by=requested_by,
        summary=summary,
    ).to_dict()
