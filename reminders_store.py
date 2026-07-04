"""Persistent reminder store with deterministic due queries.

This module stores reminders and returns reminders that are due. It performs no
external actions beyond producing operator-surfaceable reminder records.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REMINDERS_DB_PATH = "/home/openclaw/state/reminders/reminders.sqlite3"
REMINDER_SCHEMA_VERSION = "reminder_record_v0"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_aware_iso(value: str) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _reminder_id(text: str, due_at_utc_iso: str) -> str:
    digest = hashlib.sha256(
        _stable_json({"text": text, "due_at_utc_iso": due_at_utc_iso}).encode("utf-8")
    ).hexdigest()[:20]
    return f"reminder:{digest}"


class ReminderStore:
    """SQLite-backed reminder store."""

    def __init__(self, db_path: str = DEFAULT_REMINDERS_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    reminder_id        TEXT PRIMARY KEY,
                    text               TEXT NOT NULL,
                    due_at_utc_iso     TEXT NOT NULL,
                    created_at_utc_iso TEXT NOT NULL,
                    status             TEXT NOT NULL,
                    surfaced_at_utc_iso TEXT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders (status, due_at_utc_iso)"
            )
        finally:
            conn.close()

    def add_reminder(
        self,
        *,
        text: str,
        due_at_utc_iso: str,
        created_at_utc_iso: str | None = None,
    ) -> dict[str, Any]:
        reminder_text = str(text or "").strip()
        if not reminder_text:
            raise ValueError("reminder text is required")
        due_at = _parse_aware_iso(due_at_utc_iso).isoformat(timespec="seconds")
        created_at = _parse_aware_iso(created_at_utc_iso).isoformat(timespec="seconds") if created_at_utc_iso else _utc_now_iso()
        reminder_id = _reminder_id(reminder_text, due_at)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO reminders
                    (reminder_id, text, due_at_utc_iso, created_at_utc_iso, status, surfaced_at_utc_iso)
                VALUES (?, ?, ?, ?, 'active', NULL)
                """,
                (reminder_id, reminder_text, due_at, created_at),
            )
            row = conn.execute(
                """
                SELECT reminder_id, text, due_at_utc_iso, created_at_utc_iso, status
                FROM reminders
                WHERE reminder_id = ?
                """,
                (reminder_id,),
            ).fetchone()
            return self._public_row(row)
        finally:
            conn.close()

    def due_reminders(self, now_utc_iso: str) -> list[dict[str, Any]]:
        now = _parse_aware_iso(now_utc_iso).isoformat(timespec="seconds")
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT reminder_id, text, due_at_utc_iso, created_at_utc_iso, status
                FROM reminders
                WHERE status = 'active'
                  AND due_at_utc_iso <= ?
                ORDER BY due_at_utc_iso ASC, reminder_id ASC
                """,
                (now,),
            ).fetchall()
            return [self._public_row(row) for row in rows]
        finally:
            conn.close()

    def mark_surfaced(self, reminder_id: str, *, surfaced_at_utc_iso: str | None = None) -> dict[str, Any] | None:
        surfaced_at = _parse_aware_iso(surfaced_at_utc_iso).isoformat(timespec="seconds") if surfaced_at_utc_iso else _utc_now_iso()
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE reminders
                SET status = 'surfaced', surfaced_at_utc_iso = ?
                WHERE reminder_id = ? AND status = 'active'
                """,
                (surfaced_at, reminder_id),
            )
            row = conn.execute(
                """
                SELECT reminder_id, text, due_at_utc_iso, created_at_utc_iso, status
                FROM reminders
                WHERE reminder_id = ?
                """,
                (reminder_id,),
            ).fetchone()
            return self._public_row(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _public_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "reminder_id": row["reminder_id"],
            "text": row["text"],
            "due_at_utc_iso": row["due_at_utc_iso"],
            "created_at_utc_iso": row["created_at_utc_iso"],
            "status": row["status"],
            "surface_only": True,
        }


__all__ = ["DEFAULT_REMINDERS_DB_PATH", "REMINDER_SCHEMA_VERSION", "ReminderStore"]
