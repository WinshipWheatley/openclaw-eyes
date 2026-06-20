import json
import os
import pytest
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLISH_LOOP_DIR = ROOT / "polish_loop"

if str(POLISH_LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(POLISH_LOOP_DIR))

import lane_launcher  # noqa: E402
import orchestrator  # noqa: E402


def _config(tmp_path, *, max_parallel_lanes=2):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return lane_launcher.LauncherConfig(
        repo_root=repo_root,
        registry_path=tmp_path / "lane_registry.json",
        lanes_root=tmp_path / "lanes",
        log_path=tmp_path / "lane_events.jsonl",
        gate_token_dir=tmp_path / "gate_tokens",
        base_ref="origin/codex/maestro-author",
        max_parallel_lanes=max_parallel_lanes,
        default_worker_command=(sys.executable, "-c", "import time; time.sleep(60)"),
    )


def _authorized_decision(*lanes):
    return {
        "decision_id": "parallel-decision-1",
        "authorized_by": "Opus 4.8 orchestrator",
        "parallel_lanes_authorized": True,
        "human_supervised": True,
        "lanes": list(lanes),
    }


def _patch_launch(monkeypatch):
    run_calls = []
    popen_calls = []

    def fake_run(command, **kwargs):
        run_calls.append({"command": command, "kwargs": kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    class FakePopen:
        def __init__(self, command, **kwargs):
            self.pid = 4100 + len(popen_calls)
            popen_calls.append({"command": command, "kwargs": kwargs, "pid": self.pid})

    monkeypatch.setattr(lane_launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(lane_launcher.subprocess, "Popen", FakePopen)
    return run_calls, popen_calls


def test_rejects_unauthorized_parallelization_without_launch(tmp_path, monkeypatch):
    config = _config(tmp_path)
    run_calls, popen_calls = _patch_launch(monkeypatch)
    decision = {
        "decision_id": "no-auth",
        "authorized_by": "builder",
        "parallel_lanes_authorized": True,
        "human_supervised": False,
        "lanes": [{"lane_id": "a", "task": "Build A"}],
    }

    result = lane_launcher.submit_parallelization_decision(decision, config=config)

    assert result["status"] == "rejected"
    assert "supervision" in result["reason"]
    assert run_calls == []
    assert popen_calls == []
    assert not config.registry_path.exists()


def test_launches_up_to_capacity_and_queues_overflow(tmp_path, monkeypatch):
    config = _config(tmp_path, max_parallel_lanes=2)
    run_calls, popen_calls = _patch_launch(monkeypatch)
    decision = _authorized_decision(
        {"lane_id": "A one", "task": "Fix one"},
        {"lane_id": "B two", "task": "Fix two", "branch": "codex/custom-b-two"},
        {"lane_id": "C three", "task": "Fix three"},
    )

    result = lane_launcher.submit_parallelization_decision(decision, config=config)

    assert result["status"] == "accepted"
    assert result["launched"] == ["a-one", "b-two"]
    assert result["queued"] == ["c-three"]
    assert len(run_calls) == 2
    assert len(popen_calls) == 2
    assert run_calls[0]["command"] == [
        "git",
        "worktree",
        "add",
        "-B",
        "codex/polish-lane-a-one",
        str(config.lanes_root / "a-one"),
        "origin/codex/maestro-author",
    ]
    assert run_calls[1]["command"][4] == "codex/custom-b-two"

    registry = lane_launcher.load_registry(config.registry_path)
    assert registry["lanes"]["a-one"]["status"] == "running"
    assert registry["lanes"]["a-one"]["pid"] == 4100
    assert registry["lanes"]["a-one"]["bounds"]["send_hold"] is True
    assert registry["lanes"]["a-one"]["gate_policy"]["worker_may_run_full_gate_without_token"] is False
    assert registry["lanes"]["c-three"]["status"] == "queued"
    assert registry["queue"] == ["c-three"]
    events = [json.loads(line) for line in config.log_path.read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events].count("lane_launched") == 2
    assert any(event["event_type"] == "lane_queued" and event["lane_id"] == "c-three" for event in events)


def test_detached_worker_inherits_bounds_and_lane_environment(tmp_path, monkeypatch):
    config = _config(tmp_path, max_parallel_lanes=1)
    _, popen_calls = _patch_launch(monkeypatch)

    lane_launcher.submit_parallelization_decision(
        _authorized_decision({"lane_id": "detached", "task": "Build safely"}),
        config=config,
    )

    call = popen_calls[0]
    assert call["kwargs"]["cwd"] == str(config.lanes_root / "detached")
    assert call["kwargs"]["stdin"] == subprocess.DEVNULL
    assert call["kwargs"]["stderr"] == subprocess.STDOUT
    assert call["kwargs"]["start_new_session"] is True
    env = call["kwargs"]["env"]
    assert env["OPENCLAW_SEND_HOLD"] == "1"
    assert env["OPENCLAW_TEST_MODE"] == "1"
    assert env["OPENCLAW_LANE_ID"] == "detached"
    assert env["OPENCLAW_GATE_SERIALIZED"] == "1"


def test_reap_marks_dead_running_lane_without_removing_history(tmp_path):
    config = _config(tmp_path)
    registry = lane_launcher.load_registry(config.registry_path)
    registry["lanes"]["old"] = {
        "lane_id": "old",
        "status": "running",
        "pid": 999999,
        "branch": "codex/polish-lane-old",
        "task": "Old task",
    }
    lane_launcher.save_registry(registry, config.registry_path)

    result = lane_launcher.reap_lanes(config=config, pid_alive=lambda _pid: False)

    assert result["reaped"] == ["old"]
    updated = lane_launcher.load_registry(config.registry_path)
    assert updated["lanes"]["old"]["status"] == "dead"
    assert updated["lanes"]["old"]["pid"] == 999999
    assert "reaped_at" in updated["lanes"]["old"]


def test_heartbeat_updates_existing_lane_record(tmp_path):
    config = _config(tmp_path)
    registry = lane_launcher.load_registry(config.registry_path)
    registry["lanes"]["live"] = {"lane_id": "live", "status": "running", "pid": 1234}
    lane_launcher.save_registry(registry, config.registry_path)

    updated = lane_launcher.record_lane_heartbeat("live", config=config)

    assert updated["heartbeat_at"]
    assert lane_launcher.load_registry(config.registry_path)["lanes"]["live"]["heartbeat_at"] == updated["heartbeat_at"]


def test_gate_token_state_serializes_full_green_gate(tmp_path):
    token_dir = tmp_path / "gate_tokens"
    token_dir.mkdir()
    claim = token_dir / "CLAIM-GATE-TOKEN-C-SELF-SCALE-1.md"
    release = token_dir / "RELEASE-GATE-TOKEN-C-SELF-SCALE-1.md"

    claim.write_text("claimed\n", encoding="utf-8")
    assert lane_launcher.active_gate_token_present(token_dir) is True
    state = lane_launcher.gate_token_state(token_dir)
    assert state["gate_available"] is False
    assert state["latest_claim"] == claim.name

    release.write_text("released\n", encoding="utf-8")
    claim_time = claim.stat().st_mtime
    os.utime(release, (claim_time + 1, claim_time + 1))

    assert lane_launcher.active_gate_token_present(token_dir) is False
    assert lane_launcher.gate_token_state(token_dir)["gate_available"] is True


def test_orchestrator_submit_lanes_delegates_to_launcher(tmp_path, monkeypatch, capsys):
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json.dumps(_authorized_decision({"lane_id": "x", "task": "Do x"})), encoding="utf-8")
    calls = {}

    def fake_submit(decision, *, config):
        calls["decision"] = decision
        calls["repo_root"] = config.repo_root
        return {"status": "accepted", "decision_id": decision["decision_id"], "launched": ["x"], "queued": []}

    monkeypatch.setattr(lane_launcher, "submit_parallelization_decision", fake_submit)

    with pytest.raises(SystemExit) as exc:
        orchestrator.cmd_submit_lanes(str(decision_path))

    assert exc.value.code == 0
    assert calls["decision"]["decision_id"] == "parallel-decision-1"
    assert calls["repo_root"] == orchestrator.REPO_ROOT
    assert '"launched": [\n    "x"\n  ]' in capsys.readouterr().out
