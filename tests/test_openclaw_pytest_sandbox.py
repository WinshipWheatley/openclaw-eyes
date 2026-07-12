from __future__ import annotations

import socket
import sqlite3
import subprocess
import os
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import PYTEST_SANDBOX
from openclaw_pytest_sandbox import OpenClawTestSandboxViolation


def test_network_socket_access_fails_closed():
    with pytest.raises(OpenClawTestSandboxViolation):
        socket.create_connection(("127.0.0.1", 11434), timeout=0.01)


def test_live_runtime_subprocess_access_fails_closed():
    with pytest.raises(OpenClawTestSandboxViolation):
        subprocess.run(["ollama", "list"], check=False)


def test_git_network_subprocess_access_fails_closed():
    with pytest.raises(OpenClawTestSandboxViolation):
        subprocess.run(["git", "ls-remote", "git@github.com:example/example.git"], check=False)


def test_git_local_ls_remote_is_allowed(tmp_path):
    subprocess.run(["git", "init", "--bare", "remote.git"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)

    result = subprocess.run(
        ["git", "ls-remote", "--heads", str(tmp_path / "remote.git")],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0


def test_git_local_remote_get_url_is_allowed(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    subprocess.run(
        ["git", "config", "remote.origin.url", "git@github.com:example/example.git"],
        cwd=tmp_path,
        check=True,
    )

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.stdout.strip() == "git@github.com:example/example.git"


def test_live_bridge_write_redirects_to_pytest_sandbox():
    live_path = Path("/mnt/e/openclaw/mission_control_responses/to_mac/pytest_sandbox_guard.txt")
    shadow_path = (
        PYTEST_SANDBOX.redirect_root
        / "mnt_e"
        / "openclaw"
        / "mission_control_responses"
        / "to_mac"
        / "pytest_sandbox_guard.txt"
    )
    if shadow_path.exists():
        shadow_path.unlink()

    live_path.write_text("sandboxed\n", encoding="utf-8")

    assert shadow_path.read_text(encoding="utf-8") == "sandboxed\n"


def test_live_business_ledger_redirects_to_isolated_sqlite():
    connection = sqlite3.connect("/home/openclaw/.openclaw/business_ops/ledger.sqlite")
    try:
        db_path = connection.execute("PRAGMA database_list").fetchone()[2]
    finally:
        connection.close()

    assert Path(db_path).resolve(strict=False) == PYTEST_SANDBOX.isolated_ledger.resolve(strict=False)


def test_tmp_sqlite_redirects_to_gate_run_root_when_enabled(tmp_path, monkeypatch):
    sqlite_root = tmp_path / "gate-sqlite"
    monkeypatch.setenv("OPENCLAW_PYTEST_REDIRECT_TMP_SQLITE", "1")
    monkeypatch.setenv("OPENCLAW_PYTEST_TMP_SQLITE_ROOT", str(sqlite_root))
    live_tmp_db = Path(f"/tmp/openclaw_pytest_gate_collision_{os.getpid()}.sqlite")

    connection = sqlite3.connect(live_tmp_db)
    try:
        db_path = connection.execute("PRAGMA database_list").fetchone()[2]
    finally:
        connection.close()

    assert Path(db_path).resolve(strict=False) == (sqlite_root / live_tmp_db.name).resolve(strict=False)
    # ``Path.exists`` is deliberately sandbox-aware and therefore observes the
    # redirected database. Use the unpatched primitive to prove the physical
    # /tmp target itself was never created.
    assert not PYTEST_SANDBOX._original_path_exists(live_tmp_db)


def test_send_hold_is_visible_from_sandbox_not_live_bridge():
    live_path = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")

    assert live_path.is_file() is True
    assert live_path.read_text(encoding="utf-8") == "SEND_HOLD active for pytest sandbox.\n"


def test_live_runtime_atomic_replace_redirects_to_pytest_sandbox():
    live_path = Path("/mnt/c/OpenClaw/logs/cassandra_state.json")
    live_tmp = live_path.with_name(f"{live_path.name}.tmp")
    shadow_path = (
        PYTEST_SANDBOX.redirect_root
        / "mnt_c"
        / "OpenClaw"
        / "logs"
        / "cassandra_state.json"
    )
    if shadow_path.exists():
        shadow_path.unlink()

    live_tmp.write_text('{"sandboxed": true}\n', encoding="utf-8")
    os.replace(live_tmp, live_path)

    assert shadow_path.read_text(encoding="utf-8") == '{"sandboxed": true}\n'


def test_live_runtime_mkstemp_atomic_replace_stays_in_pytest_sandbox():
    """State hygiene uses mkstemp + replace; both halves must share the shadow."""
    live_path = Path("/mnt/c/OpenClaw/logs/cassandra_state.json")
    shadow_path = (
        PYTEST_SANDBOX.redirect_root
        / "mnt_c"
        / "OpenClaw"
        / "logs"
        / "cassandra_state.json"
    )
    if shadow_path.exists():
        shadow_path.unlink()

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{live_path.name}.",
        suffix=".tmp",
        dir=str(live_path.parent),
    )
    temporary = Path(temporary_name)
    assert temporary.is_relative_to(PYTEST_SANDBOX.redirect_root)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(b'{"sandboxed_mkstemp": true}\n')
    os.replace(temporary, live_path)

    assert shadow_path.read_text(encoding="utf-8") == '{"sandboxed_mkstemp": true}\n'


@pytest.mark.parametrize("bytes_mode", (False, True))
def test_mkstemp_implicit_live_tempdir_is_mapped_with_original_path_type(
    monkeypatch,
    bytes_mode,
):
    """An implicit tempfile.tempdir is still an effective write directory."""
    live_dir = "/mnt/c/OpenClaw/logs"
    observed = {}

    def spy_mkstemp(*, suffix, prefix, dir, text):
        observed.update(suffix=suffix, prefix=prefix, dir=dir, text=text)
        return 123, dir

    monkeypatch.setattr(
        PYTEST_SANDBOX,
        "_original_tempfile_mkstemp",
        spy_mkstemp,
    )
    monkeypatch.setattr(
        tempfile,
        "tempdir",
        os.fsencode(live_dir) if bytes_mode else live_dir,
    )
    prefix = b"safe-" if bytes_mode else "safe-"
    suffix = b".tmp" if bytes_mode else ".tmp"

    _, returned_path = PYTEST_SANDBOX._guarded_tempfile_mkstemp(
        prefix=prefix,
        suffix=suffix,
    )

    expected = PYTEST_SANDBOX.redirect_root / "mnt_c" / "OpenClaw" / "logs"
    expected_value = os.fsencode(expected) if bytes_mode else str(expected)
    assert observed["dir"] == expected_value
    assert returned_path == expected_value


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("prefix", "/tmp/escape-"),
        ("prefix", b"/tmp/escape-"),
        ("prefix", "../escape-"),
        ("prefix", b"../escape-"),
        ("suffix", "/escape.tmp"),
        ("suffix", b"/escape.tmp"),
    ),
)
def test_mkstemp_path_bearing_components_fail_closed(monkeypatch, field, value):
    monkeypatch.setattr(
        PYTEST_SANDBOX,
        "_original_tempfile_mkstemp",
        lambda **_kwargs: pytest.fail("unsafe tempfile reached stdlib mkstemp"),
    )
    kwargs = {
        "prefix": b"safe-" if isinstance(value, bytes) else "safe-",
        "suffix": b".tmp" if isinstance(value, bytes) else ".tmp",
        "dir": b"/mnt/c/OpenClaw/logs" if isinstance(value, bytes) else "/mnt/c/OpenClaw/logs",
    }
    kwargs[field] = value

    with pytest.raises(OpenClawTestSandboxViolation, match="path-bearing tempfile"):
        PYTEST_SANDBOX._guarded_tempfile_mkstemp(**kwargs)


def test_mac_generated_read_model_read_uses_local_artifact():
    local_path = Path("generated/read_models/helm_composer_contract.json").resolve(strict=False)
    live_mirror_path = Path("/mnt/e/openclaw/generated/read_models/helm_composer_contract.json")

    assert live_mirror_path.read_text(encoding="utf-8") == local_path.read_text(encoding="utf-8")


def test_missing_mac_generated_read_model_looks_missing_without_live_read():
    live_mirror_path = Path("/mnt/e/openclaw/generated/read_models/pytest_missing_read_model.json")

    assert live_mirror_path.exists() is False
    with pytest.raises(FileNotFoundError):
        live_mirror_path.read_text(encoding="utf-8")


def test_mac_generated_read_model_exists_uses_local_artifact():
    live_mirror_path = Path("/mnt/e/openclaw/generated/read_models/helm_composer_contract.json")

    assert live_mirror_path.exists() is True
    assert live_mirror_path.is_file() is True


def test_live_checkout_sys_path_insert_is_ignored():
    live_root = "/home/openclaw"
    live_tools = "/home/openclaw/tools"
    repo_root = str(PYTEST_SANDBOX.repo_root)

    sys.path.insert(0, live_root)
    sys.path.insert(0, live_tools)

    assert live_root not in sys.path
    assert live_tools not in sys.path
    assert sys.path[0] == repo_root
