"""SQLite-backed GPU lease arbiter for polish-loop builders and interactive agents.

This is the control primitive only. It does not start continuous building or unload
models itself; it records the lease decision and returns a preemption plan that callers
can honor between build units.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


RESOURCE_ID = "local_gpu"
DEFAULT_TTL_SECONDS = 900


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class GPUArbiter:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gpu_resource_leases (
                  resource_id TEXT PRIMARY KEY,
                  holder_type TEXT NOT NULL,
                  holder_id TEXT NOT NULL,
                  lease_nonce TEXT NOT NULL,
                  acquired_at TEXT NOT NULL,
                  heartbeat_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  preempted_holder_id TEXT,
                  updated_at TEXT NOT NULL
                )
                """
            )

    def current(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM gpu_resource_leases WHERE resource_id=?",
                (RESOURCE_ID,),
            ).fetchone()
        return dict(row) if row else None

    def _replace_lease(
        self,
        conn: sqlite3.Connection,
        *,
        holder_type: str,
        holder_id: str,
        now: datetime,
        ttl_seconds: int,
        preempted_holder_id: str = "",
    ) -> dict[str, Any]:
        nonce = uuid.uuid4().hex
        expires_at = now + timedelta(seconds=max(1, int(ttl_seconds)))
        conn.execute(
            """
            INSERT OR REPLACE INTO gpu_resource_leases
              (resource_id, holder_type, holder_id, lease_nonce, acquired_at, heartbeat_at,
               expires_at, preempted_holder_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                RESOURCE_ID,
                holder_type,
                holder_id,
                nonce,
                _iso(now),
                _iso(now),
                _iso(expires_at),
                preempted_holder_id,
                _iso(now),
            ),
        )
        return {
            "resource_id": RESOURCE_ID,
            "holder_type": holder_type,
            "holder_id": holder_id,
            "lease_nonce": nonce,
            "acquired_at": _iso(now),
            "heartbeat_at": _iso(now),
            "expires_at": _iso(expires_at),
            "preempted_holder_id": preempted_holder_id,
        }

    def acquire(
        self,
        holder_type: str,
        holder_id: str,
        *,
        now: datetime | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> dict[str, Any]:
        now = now or _now()
        holder_type = str(holder_type or "").strip().lower()
        holder_id = str(holder_id or "").strip()
        if holder_type not in {"build", "interactive"} or not holder_id:
            return {"status": "denied", "reason": "invalid_holder"}

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM gpu_resource_leases WHERE resource_id=?",
                (RESOURCE_ID,),
            ).fetchone()
            if row is None:
                lease = self._replace_lease(
                    conn,
                    holder_type=holder_type,
                    holder_id=holder_id,
                    now=now,
                    ttl_seconds=ttl_seconds,
                )
                lease.update({"status": "acquired", "preemption_required": False})
                return lease

            current = dict(row)
            expiry = _parse(current.get("expires_at"))
            if expiry is None or expiry <= now:
                lease = self._replace_lease(
                    conn,
                    holder_type=holder_type,
                    holder_id=holder_id,
                    now=now,
                    ttl_seconds=ttl_seconds,
                    preempted_holder_id=str(current.get("holder_id") or ""),
                )
                lease.update({"status": "acquired_reclaimed_expired", "preemption_required": False})
                return lease

            if current.get("holder_id") == holder_id and current.get("holder_type") == holder_type:
                return self.heartbeat(holder_id, str(current["lease_nonce"]), now=now, ttl_seconds=ttl_seconds)

            if holder_type == "interactive" and current.get("holder_type") == "build":
                lease = self._replace_lease(
                    conn,
                    holder_type=holder_type,
                    holder_id=holder_id,
                    now=now,
                    ttl_seconds=ttl_seconds,
                    preempted_holder_id=str(current.get("holder_id") or ""),
                )
                lease.update(
                    {
                        "status": "acquired_preempted_build",
                        "preemption_required": True,
                        "recommended_keep_alive": "0",
                    }
                )
                return lease

            reason = "interactive_active" if current.get("holder_type") == "interactive" else "resource_busy"
            return {
                "status": "denied",
                "reason": reason,
                "current_holder_type": current.get("holder_type"),
                "current_holder_id": current.get("holder_id"),
                "current_expires_at": current.get("expires_at"),
            }

    def heartbeat(
        self,
        holder_id: str,
        lease_nonce: str,
        *,
        now: datetime | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> dict[str, Any]:
        now = now or _now()
        expires_at = now + timedelta(seconds=max(1, int(ttl_seconds)))
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM gpu_resource_leases WHERE resource_id=?",
                (RESOURCE_ID,),
            ).fetchone()
            if row is None or row["holder_id"] != holder_id or row["lease_nonce"] != lease_nonce:
                return {"status": "denied", "reason": "stale_or_missing_lease"}
            conn.execute(
                """
                UPDATE gpu_resource_leases
                SET heartbeat_at=?, expires_at=?, updated_at=?
                WHERE resource_id=? AND holder_id=? AND lease_nonce=?
                """,
                (_iso(now), _iso(expires_at), _iso(now), RESOURCE_ID, holder_id, lease_nonce),
            )
        return {"status": "heartbeat_recorded", "holder_id": holder_id, "expires_at": _iso(expires_at)}

    def release(self, holder_id: str, lease_nonce: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM gpu_resource_leases WHERE resource_id=?",
                (RESOURCE_ID,),
            ).fetchone()
            if row is None or row["holder_id"] != holder_id or row["lease_nonce"] != lease_nonce:
                return {"status": "denied", "reason": "stale_or_missing_lease"}
            conn.execute("DELETE FROM gpu_resource_leases WHERE resource_id=?", (RESOURCE_ID,))
        return {"status": "released", "holder_id": holder_id}


__all__ = ["GPUArbiter", "RESOURCE_ID", "DEFAULT_TTL_SECONDS"]
