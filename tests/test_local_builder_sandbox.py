from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import polish_loop.local_builder as local_builder


@pytest.fixture(autouse=True)
def reset_builder_paths(tmp_path):
    original = (
        local_builder.WORK_DIR,
        local_builder.LOOP_DIR,
        local_builder.PC_OUTPUT,
        local_builder.TASK_MD,
        local_builder.STATUS_JSON,
        local_builder.PC_CONTEXT,
        local_builder.MAC_REVIEW,
        local_builder.PROMPT_FILE,
        local_builder.LOG_FILE,
        frozenset(local_builder.WRITABLE_PATHS),
    )
    yield
    (
        local_builder.WORK_DIR,
        local_builder.LOOP_DIR,
        local_builder.PC_OUTPUT,
        local_builder.TASK_MD,
        local_builder.STATUS_JSON,
        local_builder.PC_CONTEXT,
        local_builder.MAC_REVIEW,
        local_builder.PROMPT_FILE,
        local_builder.LOG_FILE,
        writable_paths,
    ) = original
    local_builder.WRITABLE_PATHS = writable_paths


@pytest.mark.parametrize(
    "command",
    [
        "git status; rm -rf x",
        "git status && rm -rf x",
        "git status | cat",
        "git status `rm -rf x`",
        "git status $(rm -rf x)",
    ],
)
def test_run_command_rejects_shell_control_metacharacters(monkeypatch, command):
    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("shell-control command must not reach subprocess.run")

    monkeypatch.setattr(local_builder.subprocess, "run", forbidden_run)

    result = local_builder._exec_run_command({"command": command})

    assert result.startswith("ERROR: command not allowed")
    assert "shell control" in result


@pytest.mark.parametrize(
    "command",
    [
        "awk 'BEGIN{system(\"echo owned\")}' /dev/null",
        "find . -maxdepth 0 -exec echo owned +",
        "find . -maxdepth 0 -execdir echo owned +",
        "tar --to-command echo -xf archive.tar",
        "/usr/bin/tar --to-command echo -xf archive.tar",
        "xargs echo owned",
        "env python -m pytest tests/test_local_builder_sandbox.py -q",
        "sed -e 's/a/b/e' README.md",
    ],
)
def test_run_command_rejects_exec_capable_primitives(monkeypatch, command):
    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("exec-capable command must not reach subprocess.run")

    monkeypatch.setattr(local_builder.subprocess, "run", forbidden_run)

    result = local_builder._exec_run_command({"command": command})

    assert result.startswith("ERROR: command not allowed")


@pytest.mark.parametrize(
    "command, expected_argv",
    [
        ("git status", ["git", "status"]),
        ("python -m pytest tests/test_local_builder_sandbox.py -q", ["python", "-m", "pytest", "tests/test_local_builder_sandbox.py", "-q"]),
        ("python -m py_compile polish_loop/local_builder.py", ["python", "-m", "py_compile", "polish_loop/local_builder.py"]),
    ],
)
def test_run_command_allows_explicit_safe_commands_without_shell(monkeypatch, tmp_path, command, expected_argv):
    worktree = tmp_path / "builder-worktree"
    worktree.mkdir()
    local_builder._configure_runtime_paths(worktree)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(local_builder.subprocess, "run", fake_run)

    result = local_builder._exec_run_command({"command": command})

    assert "ok" in result
    assert calls
    argv, kwargs = calls[0]
    assert argv == expected_argv
    assert kwargs.get("shell") is not True
    assert kwargs["cwd"] == str(worktree)


def test_run_command_uses_configured_worktree_not_live_repo(monkeypatch, tmp_path):
    live_repo = tmp_path / "live-openclaw"
    worktree = tmp_path / "isolated-worktree"
    live_repo.mkdir()
    worktree.mkdir()
    local_builder._configure_runtime_paths(
        worktree,
        pc_output_path=live_repo / "polish_loop" / "current" / "pc_output.md",
    )
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="on worktree\n", stderr="")

    monkeypatch.setattr(local_builder.subprocess, "run", fake_run)

    result = local_builder._exec_run_command({"command": "git status"})

    assert "on worktree" in result
    assert calls[0][1]["cwd"] == str(worktree)
    assert calls[0][1]["cwd"] != str(live_repo)
    assert local_builder.PC_OUTPUT == live_repo / "polish_loop" / "current" / "pc_output.md"


def test_read_file_rejects_absolute_live_repo_path_outside_worktree(tmp_path):
    live_repo = tmp_path / "live-openclaw"
    worktree = tmp_path / "isolated-worktree"
    live_file = live_repo / "polish_loop" / "task.md"
    worktree.mkdir(parents=True)
    live_file.parent.mkdir(parents=True)
    live_file.write_text("live task must not be read through builder tools\n", encoding="utf-8")
    local_builder._configure_runtime_paths(
        worktree,
        pc_output_path=live_repo / "polish_loop" / "current" / "pc_output.md",
    )

    result = local_builder._exec_read_file({"path": str(live_file)})

    assert result.startswith("ERROR: read denied outside builder worktree")


def test_isolated_builder_worktree_adds_and_removes_throwaway_worktree(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    worktree_root = tmp_path / "worktrees"
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[:4] == ["git", "worktree", "add", "--detach"]:
            Path(argv[4]).mkdir(parents=True)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setenv("OPENCLAW_LOCAL_BUILDER_WORKTREE_ROOT", str(worktree_root))
    monkeypatch.setattr(local_builder.subprocess, "run", fake_run)

    with local_builder._isolated_builder_worktree(repo) as worktree:
        assert worktree != repo
        assert worktree.is_dir()
        created_worktree = worktree

    assert not created_worktree.exists()
    assert calls[0][0][:4] == ["git", "worktree", "add", "--detach"]
    assert calls[0][1]["cwd"] == str(repo)
    assert calls[-1][0][:4] == ["git", "worktree", "remove", "--force"]
    assert calls[-1][1]["cwd"] == str(repo)
