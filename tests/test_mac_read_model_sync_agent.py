import json
import subprocess
from pathlib import Path

from scripts.mac_read_model_sync_agent import (
    build_sync_command,
    run_agent_once,
)


def _write_marker(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"request_id": "fixture"}\n', encoding="utf-8")


def test_marker_present_triggers_sync_command_construction(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
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
        return subprocess.CompletedProcess(command, 0, "synced\n", "")

    status = run_agent_once(
        share_root=share,
        repo_root=repo,
        log_path=tmp_path / "agent.log",
        runner=runner,
    )

    assert status["status"] == "success"
    assert status["exit_code"] == 0
    assert calls[0]["command"] == [
        "python3",
        "scripts/sync_read_model_mirror.py",
        "--pull",
        "--format",
        "operator",
    ]
    assert calls[0]["cwd"] == repo.resolve()
    assert calls[0]["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert calls[0]["timeout_seconds"] == 600


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

    assert status["status"] == "marker_missing"
    assert status["exit_code"] == 0
    assert calls == []
    assert "marker_missing" in (tmp_path / "agent.log").read_text(encoding="utf-8")


def test_completion_marker_can_be_written(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    completion = share / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    _write_marker(share / "shuttle" / "to_mac" / "read_model_sync_required.json")

    status = run_agent_once(
        share_root=share,
        repo_root=tmp_path / "openclaw",
        log_path=tmp_path / "agent.log",
        runner=lambda command, cwd, env, timeout_seconds: subprocess.CompletedProcess(
            command, 0, "ok\n", ""
        ),
    )

    assert completion.is_file()
    payload = json.loads(completion.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["sync_exit_code"] == 0
    assert payload["request_marker_deleted"] is False
    assert status["completion_marker_written"] is True


def test_sync_failure_writes_failure_status(tmp_path):
    share = tmp_path / "openclaw_e"
    share.mkdir()
    completion = share / "shuttle" / "from_mac" / "read_model_sync_completed.json"
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
    assert status["status"] == "failure"
    assert status["exit_code"] == 7
    assert payload["status"] == "failure"
    assert payload["sync_stderr_tail"] == "failed\n"


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
        "openclawmissioncontrol",
    ]
    for token in forbidden:
        assert token not in text
