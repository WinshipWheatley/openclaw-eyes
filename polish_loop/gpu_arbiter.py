"""SQLite-backed GPU lease arbiter for polish-loop builders and interactive agents.

This is the control primitive only. It does not start continuous building or unload
models itself; it records the lease decision and returns a preemption plan that callers
can honor between build units.

Concurrency note: every read-decide-write sequence (acquire/heartbeat/release) runs
inside a single ``BEGIN IMMEDIATE`` transaction, mirroring the pattern already used by
``polish_loop.control_plane.ControlPlaneLedger._tx``. ``BEGIN IMMEDIATE`` takes SQLite's
write lock before the read happens, so two concurrent callers can never both observe "no
lease yet" and both report success for the same GPU -- the second caller blocks (up to
``BUSY_TIMEOUT_MS``) until the first transaction commits, then makes its decision against
the now-current row.
"""

from __future__ import annotations

import contextlib
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator


RESOURCE_ID = "local_gpu"
DEFAULT_TTL_SECONDS = 900
BUSY_TIMEOUT_MS = 5000


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
        conn = sqlite3.connect(self.db_path, timeout=BUSY_TIMEOUT_MS / 1000)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextlib.contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Open one connection and run the whole block inside BEGIN IMMEDIATE.

        Taking the write lock up front (rather than letting sqlite3's default
        deferred-transaction behavior start it lazily on the first write) is what
        makes the read-then-write sequence in acquire()/heartbeat()/release() atomic
        across concurrent connections.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        # Idempotent DDL only (CREATE TABLE IF NOT EXISTS) -- unlike
        # acquire()/heartbeat()/release() there is no prior-state decision being made
        # here, so a plain (deferred) transaction is sufficient and avoids making
        # every GPUArbiter(...) construction contend for the exclusive write lock.
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

    def _heartbeat_locked(
        self,
        conn: sqlite3.Connection,
        holder_id: str,
        lease_nonce: str,
        *,
        now: datetime,
        ttl_seconds: int,
    ) -> dict[str, Any]:
        """Extend a live lease's TTL using the caller's already-open transaction.

        Success is decided solely by the UPDATE's rowcount -- there is no separate
        pre-check SELECT to go stale between reading and writing. If the WHERE clause
        (resource_id + holder_id + lease_nonce) doesn't match any row (because the
        lease expired, was released, or was preempted by someone else), rowcount is 0
        and this honestly reports denial instead of claiming a heartbeat happened.
        """
        expires_at = now + timedelta(seconds=max(1, int(ttl_seconds)))
        cur = conn.execute(
            """
            UPDATE gpu_resource_leases
            SET heartbeat_at=?, expires_at=?, updated_at=?
            WHERE resource_id=? AND holder_id=? AND lease_nonce=?
            """,
            (_iso(now), _iso(expires_at), _iso(now), RESOURCE_ID, holder_id, lease_nonce),
        )
        if cur.rowcount != 1:
            return {"status": "denied", "reason": "stale_or_missing_lease"}
        return {"status": "heartbeat_recorded", "holder_id": holder_id, "expires_at": _iso(expires_at)}

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

        with self._tx() as conn:
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
                # Re-entrant acquire from the same live holder is just a heartbeat.
                # Reuse the already-open transaction/connection instead of calling
                # self.heartbeat() (which would try to open a second BEGIN IMMEDIATE
                # on the same file from this same call stack and deadlock against
                # ourselves until busy_timeout expired).
                return self._heartbeat_locked(
                    conn, holder_id, str(current["lease_nonce"]), now=now, ttl_seconds=ttl_seconds
                )

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
        with self._tx() as conn:
            return self._heartbeat_locked(conn, holder_id, lease_nonce, now=now, ttl_seconds=ttl_seconds)

    def release(self, holder_id: str, lease_nonce: str) -> dict[str, Any]:
        with self._tx() as conn:
            cur = conn.execute(
                "DELETE FROM gpu_resource_leases WHERE resource_id=? AND holder_id=? AND lease_nonce=?",
                (RESOURCE_ID, holder_id, lease_nonce),
            )
            if cur.rowcount != 1:
                return {"status": "denied", "reason": "stale_or_missing_lease"}
        return {"status": "released", "holder_id": holder_id}


__all__ = ["GPUArbiter", "RESOURCE_ID", "DEFAULT_TTL_SECONDS", "BUSY_TIMEOUT_MS"]
