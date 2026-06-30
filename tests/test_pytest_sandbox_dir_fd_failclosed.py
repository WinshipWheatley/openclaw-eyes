"""Regression: the pytest sandbox must NOT fail open on dir_fd-relative removals.

A prior 'fix' passed dir_fd os.remove/os.unlink straight through to the real OS call,
bypassing the sandbox's path mapping — a fail-open sandbox escape. These tests assert the
control fails CLOSED: dir_fd removals get resolved + sandbox-mapped, or are refused."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openclaw_pytest_sandbox import OpenClawPytestSandbox  # noqa: E402


def _bare():
    return OpenClawPytestSandbox.__new__(OpenClawPytestSandbox)


def test_dir_fd_remove_redirects_protected_path_instead_of_bypassing(tmp_path):
    s = _bare()
    real_dir = tmp_path / "realdir"
    real_dir.mkdir()
    victim = real_dir / "protected.sqlite"
    victim.write_text("real-data")
    sandbox_target = tmp_path / "sandboxed.sqlite"
    sandbox_target.write_text("x")

    calls = []
    s._original_os_remove = lambda *a, **k: calls.append((a, k))
    s._mapped_path_for_unlink = (
        lambda p: sandbox_target if p is not None and Path(p).name == "protected.sqlite" else None
    )

    fd = os.open(str(real_dir), os.O_RDONLY)
    try:
        s._guarded_os_remove("protected.sqlite", dir_fd=fd)
    finally:
        os.close(fd)

    # redirected to the sandbox target (no dir_fd), NOT bypassed to the real file
    assert calls == [((sandbox_target,), {})], calls
    assert victim.exists()  # the real protected file was never touched


def test_dir_fd_remove_unresolvable_fails_closed():
    s = _bare()
    s._original_os_remove = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not passthrough"))
    s._mapped_path_for_unlink = lambda p: None
    with pytest.raises(PermissionError):
        s._guarded_os_remove("x", dir_fd=999999)  # invalid fd -> unresolvable -> refuse


def test_dir_fd_remove_unprotected_temp_is_honored(tmp_path):
    s = _bare()
    real_dir = tmp_path / "d"
    real_dir.mkdir()
    (real_dir / "temp.txt").write_text("x")
    calls = []
    s._original_os_remove = lambda *a, **k: calls.append((a, k))
    s._mapped_path_for_unlink = lambda p: None  # not a protected path

    fd = os.open(str(real_dir), os.O_RDONLY)
    try:
        s._guarded_os_remove("temp.txt", dir_fd=fd)
    finally:
        os.close(fd)

    assert calls and calls[0][0][0] == "temp.txt" and calls[0][1].get("dir_fd") == fd


def test_dir_fd_unlink_also_fails_closed():
    s = _bare()
    s._original_os_unlink = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not passthrough"))
    s._mapped_path_for_unlink = lambda p: None
    with pytest.raises(PermissionError):
        s._guarded_os_unlink("x", dir_fd=999999)
