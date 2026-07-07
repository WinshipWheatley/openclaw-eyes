"""Tests for the read-model auto-refresh registry and runner.

These tests never invoke a real generator script. They use a fake registry
and a mocked subprocess-style runner so the suite stays hermetic and fast,
per the Priority-3 build instructions.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from read_model_freshness_audit import discover_packet_read_models
from read_model_auto_refresh import (
    READ_MODEL_REFRESH_REGISTRY,
    refresh_step,
    run_auto_refresh,
)


FIXED_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def _fixed_now() -> datetime:
    return FIXED_NOW


class _FakeCompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeRunner:
    """Records every invocation and never touches a real subprocess."""

    def __init__(self, *, on_call=None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._on_call = on_call

    def __call__(self, cmd, *, cwd=None, capture_output=None, text=None, timeout=None):
        self.calls.append({"cmd": list(cmd), "cwd": cwd, "timeout": timeout})
        if self._on_call is not None:
            return self._on_call(cmd, cwd=cwd, timeout=timeout)
        return _FakeCompletedProcess(returncode=0)


def _write_read_model(root: Path, name: str, *, generated_at: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(
        json.dumps({"generated_at": generated_at, "payload": "x"}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Registry-shape tests (no execution involved)
# ---------------------------------------------------------------------------


def test_registry_covers_every_discovered_packet_read_model():
    discovered = set(discover_packet_read_models())
    registered = set(READ_MODEL_REFRESH_REGISTRY)
    missing = discovered - registered
    assert not missing, f"read-models missing an explicit registry disposition: {sorted(missing)}"


def test_registry_has_25_known_sources_including_the_missing_one():
    # Anchor to the real audit result (25 sources, including the currently
    # missing reynolds_gig_setup_status.json) so registry drift is caught.
    assert len(READ_MODEL_REFRESH_REGISTRY) >= 25
    assert "reynolds_gig_setup_status.json" in READ_MODEL_REFRESH_REGISTRY


def test_packet_dankness_read_models_are_registered_for_safe_local_refresh():
    for name in ("packet_dankness_log.json", "packet_dankness_escalations.json"):
        entry = READ_MODEL_REFRESH_REGISTRY[name]
        assert entry["refreshable"] is True
        assert entry["steps"][0]["args"] == ["scripts/export_packet_dankness_read_models.py"]


def test_every_registry_entry_has_an_explicit_disposition():
    for name, entry in READ_MODEL_REFRESH_REGISTRY.items():
        assert "refreshable" in entry, f"{name} missing refreshable flag"
        assert isinstance(entry["refreshable"], bool), f"{name} refreshable must be bool"
        if entry["refreshable"]:
            steps = entry.get("steps")
            assert steps, f"{name} is refreshable but has no steps"
            for step in steps:
                assert step.get("args"), f"{name} has a step with no args"
        else:
            reason = entry.get("reason", "")
            assert reason and reason.strip(), f"{name} is not refreshable but has no reason"


def test_refresh_step_helper_builds_expected_shape():
    step = refresh_step("scripts/export_agent_presence_read_model.py", "--format", "json")
    assert step["args"] == ["scripts/export_agent_presence_read_model.py", "--format", "json"]
    assert step["generated_at_flag"] is None
    assert step["timeout_seconds"] > 0


# ---------------------------------------------------------------------------
# Runner behavior tests (fixture dirs + fake registry + mocked runner only)
# ---------------------------------------------------------------------------


def test_dry_run_plans_without_executing_or_writing_receipt(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "stale_source.json", generated_at="2026-05-01T00:00:00+00:00")

    fake_registry = {
        "stale_source.json": {
            "refreshable": True,
            "reason": "fake local exporter",
            "steps": [refresh_step("fake_exporter.py", "--format", "json")],
        },
    }
    runner = _FakeRunner()

    result = run_auto_refresh(
        14,
        names=["stale_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=True,
        runner=runner,
        now=_fixed_now,
    )

    assert runner.calls == []
    assert not (read_model_root / "read_model_auto_refresh_status.json").exists()
    item = result["items"][0]
    assert item["result"] == "planned"
    assert item["planned_commands"], "dry run should still describe the plan"


def test_stale_refreshable_source_gets_refreshed_and_receipt_is_written(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "stale_source.json", generated_at="2026-05-01T00:00:00+00:00")

    def _on_call(cmd, *, cwd, timeout):
        # Simulate what the real generator would do: write a fresh file.
        _write_read_model(read_model_root, "stale_source.json", generated_at="2026-07-01T12:00:00+00:00")
        return _FakeCompletedProcess(returncode=0, stdout="ok")

    runner = _FakeRunner(on_call=_on_call)
    fake_registry = {
        "stale_source.json": {
            "refreshable": True,
            "reason": "fake local exporter",
            "steps": [refresh_step("fake_exporter.py", "--format", "json")],
        },
    }

    result = run_auto_refresh(
        14,
        names=["stale_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    assert len(runner.calls) == 1
    assert runner.calls[0]["cwd"] == tmp_path
    item = result["items"][0]
    assert item["before_status"] == "stale"
    assert item["after_status"] == "fresh"
    assert item["result"] == "refreshed"
    assert result["summary"]["refreshed_count"] == 1
    assert result["summary"]["failed_count"] == 0

    receipt_path = read_model_root / "read_model_auto_refresh_status.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["summary"]["refreshed_count"] == 1
    assert receipt["dry_run"] is False


def test_generator_failure_is_recorded_honestly_and_not_retried(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "stale_source.json", generated_at="2026-05-01T00:00:00+00:00")

    runner = _FakeRunner(
        on_call=lambda cmd, cwd, timeout: _FakeCompletedProcess(
            returncode=1, stderr="boom: fixture explicitly fails"
        )
    )
    fake_registry = {
        "stale_source.json": {
            "refreshable": True,
            "reason": "fake local exporter",
            "steps": [refresh_step("fake_exporter.py", "--format", "json")],
        },
    }

    result = run_auto_refresh(
        14,
        names=["stale_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    assert len(runner.calls) == 1, "a failed generator must not be retried within one run"
    item = result["items"][0]
    assert item["result"] == "failed"
    assert "boom" in item["action"]["stderr_tail"]
    assert result["summary"]["failed_count"] == 1
    assert result["summary"]["refreshed_count"] == 0


def test_not_refreshable_entry_is_skipped_and_reason_is_preserved(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "unsafe_source.json", generated_at="2026-05-01T00:00:00+00:00")

    runner = _FakeRunner()
    fake_registry = {
        "unsafe_source.json": {
            "refreshable": False,
            "reason": "producer would mutate a live shared mount; needs a supervised run",
        },
    }

    result = run_auto_refresh(
        14,
        names=["unsafe_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    assert runner.calls == []
    item = result["items"][0]
    assert item["result"] == "not_refreshable"
    assert "supervised run" in item["reason"]
    assert result["summary"]["not_refreshable_count"] == 1


def test_missing_registry_entry_is_reported_honestly_not_silently_skipped(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "unregistered_source.json", generated_at="2026-05-01T00:00:00+00:00")

    result = run_auto_refresh(
        14,
        names=["unregistered_source.json"],
        registry={},
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=_FakeRunner(),
        now=_fixed_now,
    )

    item = result["items"][0]
    assert item["result"] == "no_registry_entry"
    assert result["summary"]["no_registry_entry_count"] == 1


def test_fresh_source_is_skipped_without_calling_the_runner(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "fresh_source.json", generated_at="2026-06-30T00:00:00+00:00")

    runner = _FakeRunner()
    fake_registry = {
        "fresh_source.json": {
            "refreshable": True,
            "reason": "fake local exporter",
            "steps": [refresh_step("fake_exporter.py")],
        },
    }

    result = run_auto_refresh(
        14,
        names=["fresh_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    assert runner.calls == []
    item = result["items"][0]
    assert item["result"] == "skipped_fresh"


def test_generated_at_flag_is_injected_with_a_fresh_timestamp(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "frozen_ts_source.json", generated_at="2026-05-01T00:00:00+00:00")

    def _on_call(cmd, *, cwd, timeout):
        _write_read_model(read_model_root, "frozen_ts_source.json", generated_at="2026-07-01T12:00:00+00:00")
        return _FakeCompletedProcess(returncode=0)

    runner = _FakeRunner(on_call=_on_call)
    fake_registry = {
        "frozen_ts_source.json": {
            "refreshable": True,
            "reason": "module hardcodes a frozen default generated_at",
            "steps": [
                refresh_step(
                    "fake_exporter_with_frozen_default.py",
                    generated_at_flag="--generated-at",
                )
            ],
        },
    }

    run_auto_refresh(
        14,
        names=["frozen_ts_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    assert len(runner.calls) == 1
    cmd = runner.calls[0]["cmd"]
    assert "--generated-at" in cmd
    flag_index = cmd.index("--generated-at")
    assert cmd[flag_index + 1] == FIXED_NOW.isoformat()


def test_still_stale_after_refresh_is_reported_not_masked_as_success(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "stubborn_source.json", generated_at="2026-05-01T00:00:00+00:00")

    # The fake generator "succeeds" (exit 0) but does not actually touch the file,
    # simulating a bug like a frozen default that keeps rewriting the same old date.
    runner = _FakeRunner()
    fake_registry = {
        "stubborn_source.json": {
            "refreshable": True,
            "reason": "fake local exporter",
            "steps": [refresh_step("fake_exporter.py")],
        },
    }

    result = run_auto_refresh(
        14,
        names=["stubborn_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    item = result["items"][0]
    assert item["result"] == "still_stale_after_refresh"
    assert result["summary"]["still_stale_after_refresh_count"] == 1
    assert result["summary"]["refreshed_count"] == 0


def test_multi_step_registry_entry_runs_steps_in_order(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "two_step_source.json", generated_at="2026-05-01T00:00:00+00:00")

    seen_order: list[str] = []

    def _on_call(cmd, *, cwd, timeout):
        seen_order.append(cmd[1])
        if cmd[1] == "step_two.py":
            _write_read_model(read_model_root, "two_step_source.json", generated_at="2026-07-01T12:00:00+00:00")
        return _FakeCompletedProcess(returncode=0)

    runner = _FakeRunner(on_call=_on_call)
    fake_registry = {
        "two_step_source.json": {
            "refreshable": True,
            "reason": "build then export",
            "steps": [refresh_step("step_one.py"), refresh_step("step_two.py")],
        },
    }

    result = run_auto_refresh(
        14,
        names=["two_step_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    assert seen_order == ["step_one.py", "step_two.py"]
    assert result["items"][0]["result"] == "refreshed"


def test_multi_step_entry_stops_after_first_failing_step(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "two_step_fail_source.json", generated_at="2026-05-01T00:00:00+00:00")

    seen_order: list[str] = []

    def _on_call(cmd, *, cwd, timeout):
        seen_order.append(cmd[1])
        if cmd[1] == "step_one.py":
            return _FakeCompletedProcess(returncode=1, stderr="step one failed")
        return _FakeCompletedProcess(returncode=0)

    runner = _FakeRunner(on_call=_on_call)
    fake_registry = {
        "two_step_fail_source.json": {
            "refreshable": True,
            "reason": "build then export",
            "steps": [refresh_step("step_one.py"), refresh_step("step_two.py")],
        },
    }

    result = run_auto_refresh(
        14,
        names=["two_step_fail_source.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    assert seen_order == ["step_one.py"], "second step must not run once the first has failed"
    assert result["items"][0]["result"] == "failed"


def test_summary_counts_are_internally_consistent(tmp_path: Path):
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model(read_model_root, "fresh.json", generated_at="2026-06-30T00:00:00+00:00")
    _write_read_model(read_model_root, "stale.json", generated_at="2026-05-01T00:00:00+00:00")
    _write_read_model(read_model_root, "unsafe.json", generated_at="2026-05-01T00:00:00+00:00")
    _write_read_model(read_model_root, "unregistered.json", generated_at="2026-05-01T00:00:00+00:00")

    def _on_call(cmd, *, cwd, timeout):
        _write_read_model(read_model_root, "stale.json", generated_at="2026-07-01T12:00:00+00:00")
        return _FakeCompletedProcess(returncode=0)

    runner = _FakeRunner(on_call=_on_call)
    fake_registry = {
        "fresh.json": {"refreshable": True, "reason": "x", "steps": [refresh_step("e.py")]},
        "stale.json": {"refreshable": True, "reason": "x", "steps": [refresh_step("e.py")]},
        "unsafe.json": {"refreshable": False, "reason": "no safe local path"},
    }

    result = run_auto_refresh(
        14,
        names=["fresh.json", "stale.json", "unsafe.json", "unregistered.json"],
        registry=fake_registry,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=False,
        runner=runner,
        now=_fixed_now,
    )

    summary = result["summary"]
    assert summary["source_count"] == 4
    assert summary["refreshed_count"] == 1
    assert summary["skipped_fresh_count"] == 1
    assert summary["not_refreshable_count"] == 1
    assert summary["no_registry_entry_count"] == 1
    assert summary["failed_count"] == 0
    # Every item accounted for exactly once.
    counted = (
        summary["refreshed_count"]
        + summary["skipped_fresh_count"]
        + summary["not_refreshable_count"]
        + summary["no_registry_entry_count"]
        + summary["failed_count"]
        + summary["still_stale_after_refresh_count"]
    )
    assert counted == summary["source_count"]


def test_real_registry_dry_run_end_to_end_is_safe(tmp_path: Path):
    """Exercises the real production registry in dry-run mode.

    Dry run never shells out, so this is safe to run against the real
    registry/discovery wiring without touching any live generator.
    """
    read_model_root = tmp_path / "generated" / "read_models"
    read_model_root.mkdir(parents=True)
    runner = _FakeRunner()

    result = run_auto_refresh(
        14,
        read_model_root=read_model_root,
        repo_root=tmp_path,
        dry_run=True,
        runner=runner,
        now=_fixed_now,
    )

    assert runner.calls == []
    assert result["summary"]["source_count"] >= 25
    names = {item["name"] for item in result["items"]}
    assert "reynolds_gig_setup_status.json" in names
