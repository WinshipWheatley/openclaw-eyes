from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from polish_loop.gpu_arbiter import GPUArbiter


def _t(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def test_build_lease_acquires_empty_gpu(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")

    result = arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:00:00"))

    assert result["status"] == "acquired"
    assert result["holder_type"] == "build"
    assert result["preemption_required"] is False


def test_interactive_preempts_build_and_requests_unload_plan(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:00:00"))

    result = arbiter.acquire("interactive", "cassandra", now=_t("2026-07-01T12:01:00"))

    assert result["status"] == "acquired_preempted_build"
    assert result["holder_type"] == "interactive"
    assert result["preemption_required"] is True
    assert result["preempted_holder_id"] == "builder-1"
    assert result["recommended_keep_alive"] == "0"


def test_build_is_denied_while_interactive_lease_is_active(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    arbiter.acquire("interactive", "maestro", now=_t("2026-07-01T12:00:00"), ttl_seconds=900)

    result = arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:05:00"))

    assert result["status"] == "denied"
    assert result["reason"] == "interactive_active"
    assert result["current_holder_id"] == "maestro"


def test_expired_interactive_lease_is_reclaimed_for_build(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    arbiter.acquire("interactive", "maestro", now=_t("2026-07-01T12:00:00"), ttl_seconds=60)

    result = arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:02:00"))

    assert result["status"] == "acquired_reclaimed_expired"
    assert result["holder_type"] == "build"


def test_wrong_nonce_cannot_release_live_lease(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    acquired = arbiter.acquire("interactive", "maestro", now=_t("2026-07-01T12:00:00"))

    denied = arbiter.release("maestro", "wrong")
    current = arbiter.current()

    assert denied["status"] == "denied"
    assert current is not None
    assert current["lease_nonce"] == acquired["lease_nonce"]


def test_heartbeat_extends_lease(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    acquired = arbiter.acquire("interactive", "maestro", now=_t("2026-07-01T12:00:00"), ttl_seconds=60)

    result = arbiter.heartbeat(
        "maestro",
        acquired["lease_nonce"],
        now=_t("2026-07-01T12:00:30"),
        ttl_seconds=120,
    )

    assert result["status"] == "heartbeat_recorded"
    assert result["expires_at"] == "2026-07-01T12:02:30+00:00"


def test_same_holder_reacquire_renews_existing_lease(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    acquired = arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:00:00"), ttl_seconds=60)

    renewed = arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:00:30"), ttl_seconds=180)
    current = arbiter.current()

    assert renewed["status"] == "heartbeat_recorded"
    assert current is not None
    assert current["lease_nonce"] == acquired["lease_nonce"]
    assert current["expires_at"] == renewed["expires_at"]


# --- Concurrency regression coverage -----------------------------------------
#
# The original implementation did a SELECT (autocommit) followed by a separate
# INSERT/UPDATE statement, so two concurrent callers could both observe "no
# lease yet" and both return status="acquired" for the same GPU (TOCTOU). The
# fix wraps the whole read-decide-write sequence in one BEGIN IMMEDIATE
# transaction per call, which takes SQLite's write lock before the read, so a
# second caller is forced to wait until the first transaction commits and then
# see the up-to-date row. These tests prove that serialization holds -- not by
# hoping for unlucky thread timing, but by directly demonstrating the write
# lock blocks a concurrent writer, and that concurrent acquire() calls never
# produce two winners.


def test_begin_immediate_transaction_blocks_concurrent_writer(tmp_path):
    db_path = tmp_path / "control.sqlite3"
    # Construct both arbiters before the manual writer opens its transaction, so
    # the only thing that can block on the write lock is the acquire() call itself
    # (schema creation is a separate, already-completed, idempotent DDL step).
    GPUArbiter(db_path)
    second_arbiter = GPUArbiter(db_path)

    blocker = sqlite3.connect(db_path, timeout=0.1)
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute(
        """
        INSERT OR REPLACE INTO gpu_resource_leases
          (resource_id, holder_type, holder_id, lease_nonce, acquired_at, heartbeat_at,
           expires_at, preempted_holder_id, updated_at)
        VALUES ('local_gpu', 'interactive', 'manual-writer', 'manual-nonce',
                '2026-07-01T12:00:00+00:00', '2026-07-01T12:00:00+00:00',
                '2026-07-01T12:15:00+00:00', '', '2026-07-01T12:00:00+00:00')
        """
    )
    # Deliberately do not commit yet -- this holds the exclusive write lock,
    # exactly like a concurrent acquire()/heartbeat()/release() call would
    # while its own BEGIN IMMEDIATE transaction is open.

    outcome: dict[str, object] = {}

    def attempt_acquire() -> None:
        outcome["result"] = second_arbiter.acquire(
            "build", "builder-x", now=_t("2026-07-01T12:01:00")
        )

    worker = threading.Thread(target=attempt_acquire)
    worker.start()
    time.sleep(0.3)
    try:
        # The concurrent acquire() must still be blocked on the write lock;
        # it cannot have raced ahead and read a stale/empty table.
        assert worker.is_alive(), "acquire() should block while the writer holds BEGIN IMMEDIATE"
    finally:
        blocker.commit()
        blocker.close()

    worker.join(timeout=5)
    assert not worker.is_alive()
    result = outcome["result"]
    assert result["status"] == "denied"
    assert result["reason"] == "interactive_active"
    assert result["current_holder_id"] == "manual-writer"


def test_concurrent_acquire_never_produces_two_winners(tmp_path):
    db_path = tmp_path / "control.sqlite3"
    GPUArbiter(db_path)  # pre-create schema so both threads race on the same table

    for _ in range(20):
        db_path.unlink(missing_ok=True)
        for suffix in ("", "-wal", "-shm"):
            extra = db_path.with_name(db_path.name + suffix)
            extra.unlink(missing_ok=True)
        arbiter_a = GPUArbiter(db_path)
        arbiter_b = GPUArbiter(db_path)
        barrier = threading.Barrier(2)
        results: dict[str, dict] = {}

        def call(name: str, arbiter: GPUArbiter, holder_id: str) -> None:
            barrier.wait(timeout=5)
            results[name] = arbiter.acquire("interactive", holder_id)

        t1 = threading.Thread(target=call, args=("a", arbiter_a, "session-a"))
        t2 = threading.Thread(target=call, args=("b", arbiter_b, "session-b"))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        winners = [r for r in results.values() if r["status"] == "acquired"]
        losers = [r for r in results.values() if r["status"] == "denied"]
        assert len(winners) == 1, results
        assert len(losers) == 1, results
        assert losers[0]["reason"] == "interactive_active"

        current = arbiter_a.current()
        assert current is not None
        assert current["holder_id"] == winners[0]["holder_id"]


def test_heartbeat_denies_when_lease_no_longer_matches_holder(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    acquired = arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:00:00"), ttl_seconds=900)

    # A different holder preempts the lease -- builder-1's nonce is now stale.
    arbiter.acquire("interactive", "cassandra", now=_t("2026-07-01T12:00:10"))

    stale = arbiter.heartbeat(
        "builder-1", acquired["lease_nonce"], now=_t("2026-07-01T12:00:20")
    )
    current = arbiter.current()

    assert stale["status"] == "denied"
    assert stale["reason"] == "stale_or_missing_lease"
    # The stale heartbeat must not have silently kept the old holder alive or
    # touched the new holder's lease.
    assert current is not None
    assert current["holder_id"] == "cassandra"
    assert current["heartbeat_at"] == "2026-07-01T12:00:10+00:00"


def test_heartbeat_on_empty_resource_is_denied_not_silently_recorded(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")

    result = arbiter.heartbeat("nobody", "no-nonce", now=_t("2026-07-01T12:00:00"))

    assert result["status"] == "denied"
    assert result["reason"] == "stale_or_missing_lease"
    assert arbiter.current() is None


def test_release_is_atomic_and_reports_denied_on_zero_rowcount(tmp_path):
    arbiter = GPUArbiter(tmp_path / "control.sqlite3")
    acquired = arbiter.acquire("build", "builder-1", now=_t("2026-07-01T12:00:00"))

    first = arbiter.release("builder-1", acquired["lease_nonce"])
    second = arbiter.release("builder-1", acquired["lease_nonce"])

    assert first["status"] == "released"
    assert second["status"] == "denied"
    assert second["reason"] == "stale_or_missing_lease"
    assert arbiter.current() is None
