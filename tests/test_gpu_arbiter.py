from __future__ import annotations

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
