from __future__ import annotations

import pytest

from polish_loop.build_lifecycle_registry import BuildLifecycleRegistry


def test_record_and_history_round_trip(tmp_path):
    registry = BuildLifecycleRegistry(tmp_path / "lifecycle.sqlite3")

    registry.record(
        "task-1:1",
        "requested",
        task_id="task-1",
        attempt_no=1,
        detail={"owner": "orchestrator"},
    )
    registry.record(
        "task-1:1",
        "routed",
        task_id="task-1",
        attempt_no=1,
        reason="local_builder_available",
        detail={"status": "route", "model": "ornith:9b"},
    )
    registry.record("task-1:1", "leased", task_id="task-1", attempt_no=1)
    registry.record("task-1:1", "running", task_id="task-1", attempt_no=1)
    registry.record("task-1:1", "released", task_id="task-1", attempt_no=1)
    registry.record("task-1:1", "verified", task_id="task-1", attempt_no=1)

    history = registry.history("task-1:1")

    assert [event["stage"] for event in history] == [
        "requested",
        "routed",
        "leased",
        "running",
        "released",
        "verified",
    ]
    assert history[1]["reason"] == "local_builder_available"
    assert history[1]["detail"] == {"status": "route", "model": "ornith:9b"}
    assert history[0]["detail"] == {"owner": "orchestrator"}
    # Every event carries its own timestamp -- append-only provenance.
    assert all(event["recorded_at"] for event in history)


def test_history_is_isolated_per_build_unit(tmp_path):
    registry = BuildLifecycleRegistry(tmp_path / "lifecycle.sqlite3")

    registry.record("task-1:1", "requested", task_id="task-1", attempt_no=1)
    registry.record("task-2:1", "requested", task_id="task-2", attempt_no=1)
    registry.record("task-1:1", "deferred", task_id="task-1", attempt_no=1, reason="interactive_gpu_lease_active")

    assert [e["stage"] for e in registry.history("task-1:1")] == ["requested", "deferred"]
    assert [e["stage"] for e in registry.history("task-2:1")] == ["requested"]


def test_history_for_unknown_build_unit_is_empty(tmp_path):
    registry = BuildLifecycleRegistry(tmp_path / "lifecycle.sqlite3")

    assert registry.history("never-seen") == []


def test_latest_stage_reflects_most_recent_event(tmp_path):
    registry = BuildLifecycleRegistry(tmp_path / "lifecycle.sqlite3")

    assert registry.latest_stage("task-1:1") is None

    registry.record("task-1:1", "requested", task_id="task-1", attempt_no=1)
    assert registry.latest_stage("task-1:1") == "requested"

    registry.record("task-1:1", "lease_denied", task_id="task-1", attempt_no=1, reason="resource_busy")
    assert registry.latest_stage("task-1:1") == "lease_denied"


def test_records_deferrals_and_denials_honestly_not_as_success(tmp_path):
    registry = BuildLifecycleRegistry(tmp_path / "lifecycle.sqlite3")

    registry.record(
        "task-1:1",
        "deferred",
        task_id="task-1",
        attempt_no=1,
        reason="interactive_gpu_lease_active",
        detail={"defer_until": "interactive_idle"},
    )

    history = registry.history("task-1:1")
    assert history[0]["stage"] == "deferred"
    assert history[0]["reason"] == "interactive_gpu_lease_active"
    assert history[0]["detail"]["defer_until"] == "interactive_idle"


def test_unknown_stage_is_rejected():
    registry_path_owner = BuildLifecycleRegistry
    # Constructing with an unknown stage must fail loudly rather than silently
    # accepting an unrecognized lifecycle label into the append-only trail.
    with pytest.raises(ValueError):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            registry = registry_path_owner(Path(d) / "lifecycle.sqlite3")
            registry.record("task-1:1", "made_up_stage", task_id="task-1", attempt_no=1)


def test_registry_is_append_only_and_persists_across_instances(tmp_path):
    db_path = tmp_path / "lifecycle.sqlite3"
    first = BuildLifecycleRegistry(db_path)
    first.record("task-1:1", "requested", task_id="task-1", attempt_no=1)

    second = BuildLifecycleRegistry(db_path)
    second.record("task-1:1", "routed", task_id="task-1", attempt_no=1)

    assert [e["stage"] for e in first.history("task-1:1")] == ["requested", "routed"]
