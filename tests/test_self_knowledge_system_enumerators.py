from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import self_knowledge_system_enumerators as sen  # noqa: E402


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


# --- processes -----------------------------------------------------------

def test_enumerate_processes_parses_rows(monkeypatch):
    output = (
        "  PID  PPID USER     COMM             ARGS\n"
        "    1     0 root     systemd          /sbin/init\n"
        "  123     1 openclaw python3          python3 chief_listener.py\n"
    )

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "ps"
        return _completed(stdout=output)

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_processes()

    assert result["status"] == "ok"
    assert len(result["rows"]) == 2
    assert result["rows"][1]["pid"] == "123"
    assert result["rows"][1]["user"] == "openclaw"
    assert "chief_listener.py" in result["rows"][1]["args"]


def test_enumerate_processes_unavailable_when_ps_missing(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("ps not found")

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_processes()

    assert result["status"] == "unavailable"
    assert "reason" in result


def test_enumerate_processes_unavailable_on_timeout(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_processes()

    assert result["status"] == "unavailable"
    assert "timeout" in result["reason"].lower()


# --- crontab ---------------------------------------------------------------

def test_enumerate_user_crontab_parses_lines(monkeypatch):
    output = "# comment\n\n*/5 * * * * /usr/bin/true\n"

    def fake_run(cmd, **kwargs):
        assert cmd == ["crontab", "-l"]
        return _completed(stdout=output, returncode=0)

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_user_crontab()

    assert result["status"] == "ok"
    assert result["rows"] == ["*/5 * * * * /usr/bin/true"]


def test_enumerate_user_crontab_no_crontab_is_ok_empty(monkeypatch):
    def fake_run(cmd, **kwargs):
        return _completed(stdout="", stderr="no crontab for openclaw", returncode=1)

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_user_crontab()

    assert result["status"] == "ok"
    assert result["rows"] == []


def test_enumerate_user_crontab_unavailable_when_missing(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("crontab not found")

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_user_crontab()

    assert result["status"] == "unavailable"


# --- systemd user services --------------------------------------------------

def test_enumerate_systemd_user_services_parses_rows(monkeypatch):
    output = (
        "chief-listener.service     loaded active running Chief listener\n"
        "hermes-gateway.service     loaded active running Hermes gateway\n"
    )

    def fake_run(cmd, **kwargs):
        assert cmd[:2] == ["systemctl", "--user"]
        return _completed(stdout=output)

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_systemd_user_services()

    assert result["status"] == "ok"
    assert len(result["rows"]) == 2
    assert result["rows"][0]["unit"] == "chief-listener.service"
    assert result["rows"][0]["active"] == "active"


def test_enumerate_systemd_user_services_unavailable_when_missing(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("systemctl not found")

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_systemd_user_services()

    assert result["status"] == "unavailable"


# --- listening ports ---------------------------------------------------------

def test_enumerate_listening_ports_parses_rows(monkeypatch):
    output = (
        "State   Recv-Q  Send-Q   Local Address:Port    Peer Address:Port   Process\n"
        "LISTEN  0       128      127.0.0.1:8771        0.0.0.0:*            users:((\"kokoro\",pid=999,fd=7))\n"
    )

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "ss"
        return _completed(stdout=output)

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_listening_ports()

    assert result["status"] == "ok"
    assert len(result["rows"]) == 1
    assert result["rows"][0]["local_address_port"] == "127.0.0.1:8771"
    assert result["rows"][0]["state"] == "LISTEN"


def test_enumerate_listening_ports_unavailable_when_missing(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("ss not found")

    monkeypatch.setattr(sen.subprocess, "run", fake_run)

    result = sen.enumerate_listening_ports()

    assert result["status"] == "unavailable"


# --- on-disk sqlite databases ------------------------------------------------

def test_enumerate_sqlite_databases_finds_files_including_generated(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "polish_loop").mkdir()
    (repo / "polish_loop" / "control_plane.sqlite3").write_bytes(b"x" * 10)
    generated = repo / "generated"
    generated.mkdir()
    (generated / "read_models").mkdir()
    (generated / "read_models" / "cache.sqlite").write_bytes(b"y" * 5)
    (repo / ".venv").mkdir()
    (repo / ".venv" / "ignored.sqlite").write_bytes(b"z")
    (repo / ".git").mkdir()
    (repo / ".git" / "ignored2.db").write_bytes(b"z")

    result = sen.enumerate_sqlite_databases(repo)

    assert result["status"] == "ok"
    rels = sorted(r["relative_path"] for r in result["rows"])
    assert rels == ["generated/read_models/cache.sqlite", "polish_loop/control_plane.sqlite3"]


def test_enumerate_sqlite_databases_bounded_by_max_results(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for i in range(5):
        (repo / f"{i}.sqlite").write_bytes(b"x")

    result = sen.enumerate_sqlite_databases(repo, max_results=2)

    assert result["status"] == "ok"
    assert len(result["rows"]) == 2


def test_enumerate_sqlite_databases_unavailable_on_bad_root(tmp_path):
    missing = tmp_path / "does_not_exist"

    result = sen.enumerate_sqlite_databases(missing)

    assert result["status"] == "unavailable"
