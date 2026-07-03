from __future__ import annotations

import json
from pathlib import Path

from polish_loop.gpu_arbiter import GPUArbiter


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "orchestration"
    (workspace / "loop" / "to-pc").mkdir(parents=True)
    (workspace / "inbox" / "to-claude").mkdir(parents=True)
    return workspace


def test_autoscaler_spawns_one_exit_on_complete_worker_and_writes_telemetry(tmp_path: Path, monkeypatch) -> None:
    from scripts import openclaw_fleet_autoscaler as autoscaler

    workspace = _workspace(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    telemetry_path = tmp_path / "fleet_telemetry.json"
    task = workspace / "loop" / "to-pc" / "030-BUILD-auto-scaler-daemon.md"
    task.write_text("BUILD: autoscaler", encoding="utf-8")
    calls = []

    class FakePopen:
        pid = 4242

        def __init__(self, command, **kwargs):
            calls.append({"command": command, "kwargs": kwargs})

    monkeypatch.setenv("OPENCLAW_AUTOSCALER_WORKER_COMMAND", "python worker_once.py")

    payload = autoscaler.tick(
        workspace=workspace,
        repo_root=repo_root,
        telemetry_path=telemetry_path,
        process_lines=[],
        popen=FakePopen,
    )

    assert payload["spawned"] is True
    assert payload["spawned_task"] == task.name
    assert payload["spawned_pid"] == 4242
    assert calls[0]["command"] == ["python", "worker_once.py"]
    assert calls[0]["kwargs"]["start_new_session"] is True
    assert calls[0]["kwargs"]["cwd"] == str(repo_root)
    env = calls[0]["kwargs"]["env"]
    assert env["EXIT_ON_COMPLETE"] == "1"
    assert env["OPENCLAW_SEND_HOLD"] == "1"
    assert env["OPENCLAW_TEST_MODE"] == "1"
    assert env["OPENCLAW_DIRECTIVE_PATH"] == task.as_posix()
    written = json.loads(telemetry_path.read_text(encoding="utf-8"))
    assert written["exit_on_complete_enforced"] is True
    assert written["queued_task_count"] == 1


def test_autoscaler_does_not_spawn_while_gate_running(tmp_path: Path) -> None:
    from scripts import openclaw_fleet_autoscaler as autoscaler

    workspace = _workspace(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    task = workspace / "loop" / "to-pc" / "031-BUILD-niles-specs-promotion.md"
    task.write_text("BUILD: niles", encoding="utf-8")
    calls = []

    payload = autoscaler.tick(
        workspace=workspace,
        repo_root=repo_root,
        telemetry_path=tmp_path / "fleet_telemetry.json",
        process_lines=["123 bash scripts/green_gate.sh codex/branch"],
        popen=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert payload["spawned"] is False
    assert payload["gate_running"] is True
    assert payload["gate_available"] is False
    assert calls == []


def test_autoscaler_skips_already_claimed_directives(tmp_path: Path) -> None:
    from scripts import openclaw_fleet_autoscaler as autoscaler

    workspace = _workspace(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    task = workspace / "loop" / "to-pc" / "032-BUILD-niles-osc-controller.md"
    task.write_text("BUILD: niles osc", encoding="utf-8")
    (workspace / "inbox" / "to-claude" / "PC-CODEX-1-CLAIM-032-NILES-OSC.md").write_text(
        "claimed", encoding="utf-8"
    )

    payload = autoscaler.tick(
        workspace=workspace,
        repo_root=repo_root,
        telemetry_path=tmp_path / "fleet_telemetry.json",
        process_lines=[],
        dry_run=True,
    )

    assert payload["queued_task_count"] == 0
    assert payload["spawned"] is False
    assert payload["dry_run"] is False


def test_autoscaler_defers_while_interactive_gpu_lease_active(tmp_path: Path) -> None:
    from scripts import openclaw_fleet_autoscaler as autoscaler

    workspace = _workspace(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    telemetry_path = tmp_path / "fleet_telemetry.json"
    lease_db_path = tmp_path / "gpu_leases.sqlite3"
    GPUArbiter(lease_db_path).acquire("interactive", "operator-session", ttl_seconds=600)
    task = workspace / "loop" / "to-pc" / "033-BUILD-niles-stage-plot-email-ingest.md"
    task.write_text("BUILD: niles stage plot", encoding="utf-8")
    calls = []

    payload = autoscaler.tick(
        workspace=workspace,
        repo_root=repo_root,
        telemetry_path=telemetry_path,
        process_lines=[],
        popen=lambda *args, **kwargs: calls.append((args, kwargs)),
        dry_run=True,
        lease_db_path=lease_db_path,
    )

    assert payload["spawned"] is False
    assert payload["dry_run"] is False
    assert payload["scale_decision"] == "defer_interactive_gpu_lease"
    assert payload["defer_until"] == "interactive_idle"
    assert payload["gpu_lease"]["gpu"] == "interactive_active"
    assert payload["gpu_lease"]["gpu_holder_id"] == "operator-session"
    assert payload["scale_plan"] == {
        "action": "defer",
        "reason": "interactive_gpu_lease_active",
        "task": task.name,
        "planned_worker_count": 0,
        "max_workers": 1,
    }
    assert calls == []


def test_autoscaler_idle_gpu_dry_run_proposes_bounded_scale_plan(tmp_path: Path) -> None:
    from scripts import openclaw_fleet_autoscaler as autoscaler

    workspace = _workspace(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    telemetry_path = tmp_path / "fleet_telemetry.json"
    lease_db_path = tmp_path / "gpu_leases.sqlite3"
    task = workspace / "loop" / "to-pc" / "034-BUILD-stage-plot-delta-check.md"
    task.write_text("BUILD: stage plot delta", encoding="utf-8")
    calls = []

    payload = autoscaler.tick(
        workspace=workspace,
        repo_root=repo_root,
        telemetry_path=telemetry_path,
        process_lines=[],
        popen=lambda *args, **kwargs: calls.append((args, kwargs)),
        dry_run=True,
        max_workers=3,
        lease_db_path=lease_db_path,
    )

    assert payload["spawned"] is False
    assert payload["dry_run"] is True
    assert payload["spawned_task"] == task.name
    assert payload["scale_decision"] == "dry_run_scale_up"
    assert payload["gpu_lease"]["gpu"] == "idle"
    assert payload["scale_plan"] == {
        "action": "spawn_one_worker",
        "reason": "gpu_idle_capacity_available",
        "task": task.name,
        "planned_worker_count": 1,
        "max_workers": 3,
        "dry_run": True,
    }
    assert calls == []


def test_autoscaler_cli_is_disabled_without_once(capsys) -> None:
    from scripts import openclaw_fleet_autoscaler as autoscaler

    assert autoscaler.main([]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["autoscaler_enabled"] is False
    assert payload["scale_decision"] == "disabled"


def test_autoscaler_cli_once_forces_dry_run(tmp_path: Path, monkeypatch, capsys) -> None:
    from scripts import openclaw_fleet_autoscaler as autoscaler

    captured = {}

    def fake_tick(**kwargs):
        captured.update(kwargs)
        return {"schema_version": "fleet_telemetry_v0", "scale_decision": "dry_run_scale_up"}

    monkeypatch.setattr(autoscaler, "tick", fake_tick)

    rc = autoscaler.main(
        [
            "--once",
            "--workspace",
            str(tmp_path / "workspace"),
            "--repo-root",
            str(tmp_path / "repo"),
            "--lease-db-path",
            str(tmp_path / "gpu.sqlite"),
            "--max-workers",
            "2",
        ]
    )

    assert rc == 0
    assert captured["dry_run"] is True
    assert captured["max_workers"] == 2
    assert captured["lease_db_path"] == tmp_path / "gpu.sqlite"
    assert json.loads(capsys.readouterr().out)["scale_decision"] == "dry_run_scale_up"
