from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polish_loop.capability_availability_router import route_build_capability  # noqa: E402
from polish_loop.gpu_arbiter import GPUArbiter  # noqa: E402


def test_routes_local_builder_when_gpu_is_idle(tmp_path):
    decision = route_build_capability(
        "profile: standard\ngoal: fix a bounded local bug",
        lease_db_path=tmp_path / "leases.sqlite",
        local_model=("chief-fast:latest", "local_model_available"),
    )

    assert decision["status"] == "route"
    assert decision["executor"] == "local_builder"
    assert decision["runner"] == "ollama"
    assert decision["model"] == "chief-fast:latest"
    assert decision["decision_reason"] == "local_builder_available"
    assert decision["signals"]["gpu"] == "idle"


def test_defers_builder_while_interactive_agent_holds_gpu(tmp_path):
    db = tmp_path / "leases.sqlite"
    arbiter = GPUArbiter(db)
    now = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    arbiter.acquire(
        "interactive",
        "cassandra-chat",
        now=now,
        ttl_seconds=900,
    )

    decision = route_build_capability(
        "profile: standard\ngoal: run a polish-loop build",
        lease_db_path=db,
        local_model=("chief-fast:latest", "local_model_available"),
        now=now,
    )

    assert decision["status"] == "defer"
    assert decision["decision_reason"] == "interactive_gpu_lease_active"
    assert decision["defer_until"] == "interactive_idle"
    assert decision["signals"]["gpu_holder_id"] == "cassandra-chat"


def test_never_routes_cloud_without_explicit_safe_packet(tmp_path):
    decision = route_build_capability(
        "profile: standard\ngoal: use codex if available",
        lease_db_path=tmp_path / "leases.sqlite",
        local_model=("chief-fast:latest", "local_model_available"),
        cloud_requested=True,
        cloud_allowed=False,
        cloud_headroom={"codex": {"available": True}},
    )

    assert decision["status"] == "route"
    assert decision["executor"] == "local_builder"
    assert decision["runner"] == "ollama"
    assert decision["signals"]["cloud"] == "blocked_not_explicitly_allowed"
    assert "local" in decision["explanation"].lower()


def test_defers_honestly_when_no_local_model_and_cloud_quota_unavailable(tmp_path):
    decision = route_build_capability(
        "profile: architect\ngoal: build a complex multi-step feature",
        lease_db_path=tmp_path / "leases.sqlite",
        local_model=(None, "no_fitting_model"),
        cloud_requested=True,
        cloud_allowed=True,
        cloud_headroom={"codex": {"available": False, "reason": "quota_exceeded"}},
    )

    assert decision["status"] == "defer"
    assert decision["decision_reason"] == "no_available_capability"
    assert decision["defer_until"] == "capability_returns"
    assert decision["signals"]["local_model_reason"] == "no_fitting_model"
    assert decision["signals"]["cloud"] == "quota_unavailable"


def test_quota_like_runner_output_routes_to_local_not_silent_stall(tmp_path):
    quota_output = tmp_path / "pc_output.md"
    quota_output.write_text("Quota exceeded. Try again later.")

    decision = route_build_capability(
        "profile: standard\ngoal: continue after quota response",
        lease_db_path=tmp_path / "leases.sqlite",
        local_model=("chief-fast:latest", "local_model_available"),
        previous_runner_output=quota_output,
        cloud_requested=True,
        cloud_allowed=True,
        cloud_headroom={"codex": {"available": True}},
    )

    assert decision["status"] == "route"
    assert decision["runner"] == "ollama"
    assert decision["signals"]["previous_runner_output"] == "quota_message"
    assert decision["decision_reason"] == "cloud_quota_message_local_fallback"
