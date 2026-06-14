"""Inert local future-action queue helper used by Cassandra connector checks.

This module defines the local shape for queued future actions. It does not run
workers, schedule external jobs, send messages, or mutate business systems.
"""

from __future__ import annotations

import calendar
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("/mnt/c/OpenClaw/logs/cassandra_future_actions.db")
_SUPPORTED_TIME_FORMATS = (
    "later today at 6 PM",
    "today at 6 PM",
    "tonight at 6 PM",
    "tomorrow at 9 AM",
    "next week at 9 AM",
    "next month at 9 AM",
    "2026-04-03 at 9 AM",
)


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


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS future_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_text TEXT NOT NULL,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            chat_id TEXT,
            created_at TEXT NOT NULL,
            delivered_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def _normalize_due_at(raw_due_at: datetime) -> datetime:
    return raw_due_at.replace(second=0, microsecond=0)


def _add_one_month(raw_dt: datetime) -> datetime:
    if raw_dt.month == 12:
        year = raw_dt.year + 1
        month = 1
    else:
        year = raw_dt.year
        month = raw_dt.month + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(raw_dt.day, last_day)
    return raw_dt.replace(year=year, month=month, day=day)


def _parse_due_at(text: str, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now()
    lowered = text.lower()

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
    hour = 9
    minute = 0
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0

    if "tomorrow" in lowered:
        target = now + timedelta(days=1)
        return _normalize_due_at(target.replace(hour=hour, minute=minute))
    if "later today" in lowered or "today" in lowered or "tonight" in lowered:
        target = now
        return _normalize_due_at(target.replace(hour=hour, minute=minute))
    if "next week" in lowered:
        target = now + timedelta(days=7)
        return _normalize_due_at(target.replace(hour=hour, minute=minute))
    if "next month" in lowered:
        target = _add_one_month(now)
        return _normalize_due_at(target.replace(hour=hour, minute=minute))

    explicit = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lowered)
    if explicit:
        target = datetime.strptime(explicit.group(1), "%Y-%m-%d")
        return _normalize_due_at(target.replace(hour=hour, minute=minute))

    return None


def enqueue_request(text: str, chat_id: str | int | None = None) -> dict[str, str | bool]:
    due_at = _parse_due_at(text)
    if due_at is None:
        supported = ", ".join(_SUPPORTED_TIME_FORMATS)
        return {
            "ok": False,
            "message": (
                "I understood that as a reminder request, but that time format isn't supported yet. "
                f"Try one of these instead: {supported}."
            ),
        }

    created_at = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO future_actions (request_text, due_at, chat_id, created_at) VALUES (?, ?, ?, ?)",
            (text.strip(), due_at.isoformat(timespec="seconds"), str(chat_id or ""), created_at),
        )
        conn.commit()

    return {
        "ok": True,
        "message": f"Queued. I'll surface that on {due_at.strftime('%Y-%m-%d at %I:%M %p')}",
    }


def pending_count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM future_actions WHERE status = 'pending'").fetchone()
    return int(row[0]) if row else 0


def _normalize_chat_id(raw_chat_id: Any) -> str | None:
    if raw_chat_id is None:
        return None
    value = str(raw_chat_id).strip()
    if not value:
        return None
    if re.fullmatch(r"-?\d+", value):
        return value
    return None


def dispatch_due_actions(send_callable: Any) -> list[dict[str, str]]:
    now_iso = datetime.now().isoformat(timespec="seconds")
    delivered: list[dict[str, str]] = []

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, request_text, due_at, chat_id
            FROM future_actions
            WHERE status = 'pending' AND due_at <= ?
            ORDER BY due_at ASC
            """,
            (now_iso,),
        ).fetchall()

        for row in rows:
            reminder = f"Reminder: {row['request_text']}"
            raw_chat_id = row["chat_id"]
            chat_id = _normalize_chat_id(raw_chat_id)
            if raw_chat_id and chat_id is None:
                conn.execute(
                    "UPDATE future_actions SET status = 'invalid_chat', delivered_at = ? WHERE id = ?",
                    (now_iso, row["id"]),
                )
                continue
            try:
                send_callable(reminder, chat_id)
            except Exception:
                continue
            delivered.append(
                {
                    "id": str(row["id"]),
                    "request_text": row["request_text"],
                    "due_at": row["due_at"],
                }
            )
            conn.execute(
                "UPDATE future_actions SET status = 'delivered', delivered_at = ? WHERE id = ?",
                (now_iso, row["id"]),
            )

        conn.commit()

    return delivered
