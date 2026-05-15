import json
import os
import subprocess
import sys
import time
from pathlib import Path

from scripts.mac_read_model_sync_agent import (
    build_sync_command,
    run_agent_once,
)


def _write_marker(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"request_id": "fixture"}\n', encoding="utf-8")


def _sync_stdout(
    *,
    copied_count: int = 30,
    manifest_sha256: str = "a" * 64,
    manifest_path: str = "/Volumes/openclaw_e/mac_generated_read_models_manifest.json",
) -> str:
    return json.dumps(
        {
            "status": "needs_pc_import",
            "mac_sync": {
                "copied_count": copied_count,
                "manifest_sha256": manifest_sha256,
                "pc_drop_written": True,
                "pc_drop_manifest_path": manifest_path,
                "git_pull": {
                    "command": "git pull origin main",
                    "exit_code": 0,
                    "stdout": "Already up to date.\n",
                    "stderr": "",
                },
            },
        }
    )


def test_marker_present_triggers_sync_command_construction(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    manifest = share / "mac_generated_read_models_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    _write_marker(share / "shuttle" / "to_mac" / "read_model_sync_required.json")
    repo = tmp_path / "openclaw"
    repo.mkdir()
    calls = []

    def runner(command, cwd, env, timeout_seconds):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env,
                "timeout_seconds": timeout_seconds,
            }
        )
        return subprocess.CompletedProcess(
            command,
            0,
            _sync_stdout(manifest_path=manifest.as_posix()),
            "",
        )

    status = run_agent_once(
        share_root=share,
        repo_root=repo,
        log_path=tmp_path / "agent.log",
        runner=runner,
    )

    assert status["status"] == "synced"
    assert status["exit_code"] == 0
    assert calls[0]["command"] == [
        sys.executable,
        "scripts/sync_read_model_mirror.py",
        "--pull",
        "--format",
        "json",
    ]
    assert calls[0]["cwd"] == repo.resolve()
    assert calls[0]["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert calls[0]["timeout_seconds"] == 600
    assert status["marker_seen"] is True


def test_missing_share_logs_share_missing(tmp_path):
    calls = []
    status = run_agent_once(
        share_root=tmp_path / "missing_share",
        repo_root=tmp_path / "openclaw",
        log_path=tmp_path / "agent.log",
        runner=lambda *args: calls.append(args),
    )

    assert status["status"] == "share_missing"
    assert status["exit_code"] == 0
    assert calls == []
    assert "share_missing" in (tmp_path / "agent.log").read_text(encoding="utf-8")
    assert status["marker_seen"] is False
    assert status["manifest_written"] is False


def test_missing_marker_exits_cleanly(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    calls = []

    status = run_agent_once(
        share_root=share,
        repo_root=tmp_path / "openclaw",
        log_path=tmp_path / "agent.log",
        runner=lambda *args: calls.append(args),
    )

    assert status["status"] == "skipped_no_marker"
    assert status["exit_code"] == 0
    assert calls == []
    assert "skipped_no_marker" in (tmp_path / "agent.log").read_text(encoding="utf-8")
    status_marker = share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
    payload = json.loads(status_marker.read_text(encoding="utf-8"))
    assert payload["status"] == "skipped_no_marker"
    assert payload["marker_seen"] is False
    assert payload["manifest_written"] is False


def test_completion_marker_can_be_written(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    completion = share / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    status_marker = share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
    manifest = share / "mac_generated_read_models_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    _write_marker(share / "shuttle" / "to_mac" / "read_model_sync_required.json")

    status = run_agent_once(
        share_root=share,
        repo_root=tmp_path / "openclaw",
        log_path=tmp_path / "agent.log",
        runner=lambda command, cwd, env, timeout_seconds: subprocess.CompletedProcess(
            command,
            0,
            _sync_stdout(
                copied_count=26,
                manifest_sha256="b" * 64,
                manifest_path=manifest.as_posix(),
            ),
            "",
        ),
    )

    assert completion.is_file()
    payload = json.loads(completion.read_text(encoding="utf-8"))
    assert payload["status"] == "synced"
    assert payload["source"] == "mac_read_model_sync_agent"
    assert payload["manifest_sha256"] == "b" * 64
    assert payload["copied_file_count"] == 26
    assert payload["runtime_authority"] is False
    assert payload["network_authority"] is False
    assert status["completion_marker_written"] is True
    heartbeat = json.loads(status_marker.read_text(encoding="utf-8"))
    assert heartbeat["status"] == "synced"
    assert heartbeat["marker_seen"] is True
    assert heartbeat["manifest_written"] is True
    assert heartbeat["manifest_sha256"] == "b" * 64


def test_sync_failure_writes_failure_status(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    completion = share / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    status_marker = share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
    _write_marker(share / "shuttle" / "to_mac" / "read_model_sync_required.json")

    status = run_agent_once(
        share_root=share,
        repo_root=tmp_path / "openclaw",
        log_path=tmp_path / "agent.log",
        runner=lambda command, cwd, env, timeout_seconds: subprocess.CompletedProcess(
            command, 7, "", "failed\n"
        ),
    )

    payload = json.loads(completion.read_text(encoding="utf-8"))
    assert status["status"] == "error"
    assert status["exit_code"] == 7
    assert payload["status"] == "error"
    assert payload["source"] == "mac_read_model_sync_agent"
    heartbeat = json.loads(status_marker.read_text(encoding="utf-8"))
    assert heartbeat["status"] == "error"
    assert heartbeat["error"] == "failed\n"


def test_status_heartbeat_written_on_sync_error(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    status_marker = share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
    _write_marker(share / "shuttle" / "to_mac" / "read_model_sync_required.json")

    status = run_agent_once(
        share_root=share,
        repo_root=tmp_path / "openclaw",
        log_path=tmp_path / "agent.log",
        runner=lambda command, cwd, env, timeout_seconds: subprocess.CompletedProcess(
            command, 9, "", "nope\n"
        ),
    )

    payload = json.loads(status_marker.read_text(encoding="utf-8"))
    assert status["status"] == "error"
    assert payload["status"] == "error"
    assert payload["marker_seen"] is True
    assert payload["manifest_written"] is False
    assert payload["runtime_authority"] is False


def test_completed_marker_newer_than_request_writes_idle_heartbeat(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    request = share / "shuttle" / "to_mac" / "read_model_sync_required.json"
    completion = share / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    manifest = share / "mac_generated_read_models_manifest.json"
    _write_marker(request)
    completion.parent.mkdir(parents=True, exist_ok=True)
    completion.write_text('{"status": "synced"}\n', encoding="utf-8")
    manifest.write_text("{}\n", encoding="utf-8")
    now = time.time()
    os.utime(request, (now - 10, now - 10))
    os.utime(completion, (now, now))
    calls = []

    status = run_agent_once(
        share_root=share,
        repo_root=tmp_path / "openclaw",
        log_path=tmp_path / "agent.log",
        runner=lambda *args: calls.append(args),
    )

    status_marker = share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
    payload = json.loads(status_marker.read_text(encoding="utf-8"))
    assert status["status"] == "idle"
    assert status["marker_seen"] is True
    assert payload["status"] == "idle"
    assert payload["marker_seen"] is True
    assert payload["manifest_written"] is True
    assert calls == []


def test_existing_marker_file_is_replaced_when_direct_write_is_blocked(tmp_path, monkeypatch):
    target = tmp_path / "marker.json"
    target.write_text("{}\n", encoding="utf-8")
    original_write_text = Path.write_text

    def blocked_existing_write(self, *args, **kwargs):
        if self == target:
            raise OSError("direct write blocked")
        return original_write_text(self, *args, **kwargs)

    from scripts import mac_read_model_sync_agent as agent

    monkeypatch.setattr(Path, "write_text", blocked_existing_write)
    result = agent.write_json_marker(target, {"status": "synced"})

    assert result["write_method"] == "replace_after_direct_failed"
    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "synced"


def test_build_sync_command_can_disable_pull_for_tests():
    assert build_sync_command(pull=False) == [
        "python3",
        "scripts/sync_read_model_mirror.py",
        "--format",
        "operator",
    ]


def test_agent_sources_have_no_forbidden_external_or_destructive_behavior():
    paths = [
        Path("scripts/mac_read_model_sync_agent.py"),
        Path("scripts/sync_read_model_mirror.py"),
        Path("launchd/com.openclaw.read-model-sync.plist"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)

    forbidden = [
        '"ssh"',
        "'ssh'",
        '"scp"',
        "'scp'",
        "rsync ",
        "docker run",
        "ollama run",
        "ollama pull",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        "shutil.rmtree",
        "shutil.move",
        "openclawmissioncontrol",
    ]
    for token in forbidden:
        assert token not in text
