"""Build Lifecycle Registry -- append-only provenance trail for polish-loop builds.

Implements the narrow, buildable slice of the intent behind
``Operator/RESOURCE-AWARE-MODEL-ORCHESTRATION-SPEC.md`` Component 5 ("Build Lifecycle
Governance"): every build unit's lifecycle -- requested, routed, deferred, leased,
lease_denied, running, preempted, released, verified, failed -- is recorded once, with a
timestamp and an honest reason, and never rewritten. This module deliberately does NOT
attempt the full spec (no "quality grade" scoring, no anti-amnesia runtime guard); it is
the provenance ledger those could be layered on top of later.

Honesty invariant: deferrals and denials are first-class stages, not omissions or
disguised failures. A caller that decides not to run a build (GPU busy, capability
unavailable) records that decision here exactly as it happened.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("/home/openclaw/.openclaw/polish_loop/build_lifecycle.sqlite")
BUSY_TIMEOUT_MS = 5000

STAGES = frozenset(
    {
        "requested",
        "routed",
        "deferred",
        "leased",
        "lease_denied",
        "running",
        "preempted",
        "released",
        "verified",
        "failed",
    }
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class BuildLifecycleRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=BUSY_TIMEOUT_MS / 1000)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS build_lifecycle_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  build_unit_id TEXT NOT NULL,
                  task_id TEXT,
                  attempt_no INTEGER,
                  stage TEXT NOT NULL,
                  reason TEXT,
                  detail TEXT,
                  recorded_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_build_lifecycle_unit "
                "ON build_lifecycle_events(build_unit_id, id)"
            )

    def record(
        self,
        build_unit_id: str,
        stage: str,
        *,
        task_id: str | None = None,
        attempt_no: int | None = None,
        reason: str | None = None,
        detail: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        """Append one lifecycle event. Never updates or deletes prior events."""
        if stage not in STAGES:
            raise ValueError(f"unknown build lifecycle stage: {stage!r} (expected one of {sorted(STAGES)})")
        recorded_at = now or _iso_now()
        encoded_detail = json.dumps(detail, sort_keys=True, default=str) if detail is not None else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO build_lifecycle_events
                  (build_unit_id, task_id, attempt_no, stage, reason, detail, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(build_unit_id), task_id, attempt_no, stage, reason, encoded_detail, recorded_at),
            )
            conn.commit()
            event_id = cur.lastrowid
        return {
            "id": event_id,
            "build_unit_id": build_unit_id,
            "task_id": task_id,
            "attempt_no": attempt_no,
            "stage": stage,
            "reason": reason,
            "detail": detail,
            "recorded_at": recorded_at,
        }

    def history(self, build_unit_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM build_lifecycle_events WHERE build_unit_id=? ORDER BY id ASC",
                (str(build_unit_id),),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            raw_detail = item.get("detail")
            if raw_detail:
                try:
                    item["detail"] = json.loads(raw_detail)
                except (TypeError, ValueError):
                    pass
            else:
                item["detail"] = None
            events.append(item)
        return events

    def latest_stage(self, build_unit_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT stage FROM build_lifecycle_events WHERE build_unit_id=? ORDER BY id DESC LIMIT 1",
                (str(build_unit_id),),
            ).fetchone()
        return row["stage"] if row else None


__all__ = ["BuildLifecycleRegistry", "DEFAULT_DB_PATH", "STAGES"]
