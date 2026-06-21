from __future__ import annotations

import json
from pathlib import Path


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
