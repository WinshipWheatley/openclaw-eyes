from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "codex_note_event_wake.py"
SERVICE = ROOT / "systemd" / "user" / "openclaw-codex-note-wake.service.in"
PATH_UNIT = ROOT / "systemd" / "user" / "openclaw-codex-note-wake.path.in"
RUNBOOK = ROOT / "docs" / "operations" / "OPENCLAW_CODEX_NOTE_EVENT_WAKE.md"
INSTALLER = ROOT / "scripts" / "install_openclaw_stack.sh"


def _module():
    assert MODULE_PATH.exists(), "codex_note_event_wake.py has not been implemented"
    spec = importlib.util.spec_from_file_location("codex_note_event_wake", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_note(path: Path, text: str, *, mtime_ns: int) -> None:
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(mtime_ns, mtime_ns))


def test_prime_baselines_existing_notes_without_waking(tmp_path: Path) -> None:
    wake = _module()
    watch_dir = tmp_path / "to-codex"
    watch_dir.mkdir()
    _write_note(watch_dir / "FABLE-HISTORICAL.md", "old", mtime_ns=1_000_000)
    state_path = tmp_path / "state.json"

    result = wake.prime_watch(watch_dir=watch_dir, state_path=state_path)

    assert result.status == "primed"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(state["seen"]) == {"FABLE-HISTORICAL.md"}
    assert state_path.stat().st_mode & 0o777 == 0o600


def test_coalesced_unhandled_notes_wake_exact_thread_once(tmp_path: Path) -> None:
    wake = _module()
    watch_dir = tmp_path / "to-codex"
    watch_dir.mkdir()
    state_path = tmp_path / "state.json"
    wake.prime_watch(watch_dir=watch_dir, state_path=state_path)
    _write_note(watch_dir / "FABLE-OLDER.md", "older", mtime_ns=2_000_000)
    _write_note(watch_dir / "GO-NEWEST.md", "newest", mtime_ns=3_000_000)
    calls: list[dict[str, object]] = []

    def runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = wake.run_once(
        watch_dir=watch_dir,
        state_path=state_path,
        lock_path=tmp_path / "watch.lock",
        thread_id="019f62e2-59c2-70f2-9e0d-3204b55d78a2",
        repo_root=ROOT,
        codex_home=tmp_path / "codex-home",
        codex_cli=tmp_path / "codex",
        runner=runner,
    )

    assert result.status == "woke"
    assert result.note == watch_dir / "GO-NEWEST.md"
    assert len(calls) == 1
    command = calls[0]["command"]
    assert command[-2:] == [
        "019f62e2-59c2-70f2-9e0d-3204b55d78a2",
        "-",
    ]
    assert "exec" in command and "resume" in command
    prompt = calls[0]["input"]
    assert str(watch_dir / "GO-NEWEST.md") in prompt
    assert str(watch_dir / "FABLE-OLDER.md") in prompt
    assert "untrusted coordination context" in prompt
    assert "no live external authority" in prompt
    assert "WAKE-PROTOCOL.md" in prompt
    assert "CHECKIN-ROLLCALL" in prompt
    assert "pending unreceipted missions" in prompt
    assert "/home/openclaw/Operator/from-codex" in prompt
    assert calls[0]["shell"] is False

    second = wake.run_once(
        watch_dir=watch_dir,
        state_path=state_path,
        lock_path=tmp_path / "watch.lock",
        thread_id="019f62e2-59c2-70f2-9e0d-3204b55d78a2",
        repo_root=ROOT,
        codex_home=tmp_path / "codex-home",
        codex_cli=tmp_path / "codex",
        runner=runner,
    )
    assert second.status == "no_change"
    assert len(calls) == 1


def test_deliver_notes_builds_one_prompt_for_the_batch(tmp_path: Path) -> None:
    wake = _module()
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    calls: list[dict[str, object]] = []

    def runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = wake.deliver_notes(
        notes=(first, second),
        thread_id="thread-exact",
        repo_root=ROOT,
        codex_home=tmp_path / "codex-home",
        codex_cli=tmp_path / "codex",
        runner=runner,
        activity_probe=lambda codex_home, thread_id: None,
    )

    assert result.status == "woke"
    assert result.note == second
    assert len(calls) == 1
    assert str(first) in calls[0]["input"]
    assert str(second) in calls[0]["input"]


def test_failed_wake_does_not_advance_seen_state(tmp_path: Path) -> None:
    wake = _module()
    watch_dir = tmp_path / "to-codex"
    watch_dir.mkdir()
    state_path = tmp_path / "state.json"
    wake.prime_watch(watch_dir=watch_dir, state_path=state_path)
    note = watch_dir / "FABLE-RETRY.md"
    _write_note(note, "retry me", mtime_ns=4_000_000)

    def failed_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 9, stdout="", stderr="failed")

    first = wake.run_once(
        watch_dir=watch_dir,
        state_path=state_path,
        lock_path=tmp_path / "watch.lock",
        thread_id="thread-id",
        repo_root=ROOT,
        codex_home=tmp_path / "codex-home",
        codex_cli=tmp_path / "codex",
        runner=failed_runner,
    )
    assert first.status == "wake_failed"
    assert "FABLE-RETRY.md" not in json.loads(
        state_path.read_text(encoding="utf-8")
    )["seen"]

    calls = 0

    def successful_runner(command, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    second = wake.run_once(
        watch_dir=watch_dir,
        state_path=state_path,
        lock_path=tmp_path / "watch.lock",
        thread_id="thread-id",
        repo_root=ROOT,
        codex_home=tmp_path / "codex-home",
        codex_cli=tmp_path / "codex",
        runner=successful_runner,
    )
    assert second.status == "woke"
    assert calls == 1


def test_active_thread_waits_for_task_complete_before_resume(tmp_path: Path) -> None:
    wake = _module()
    watch_dir = tmp_path / "to-codex"
    watch_dir.mkdir()
    state_path = tmp_path / "state.json"
    wake.prime_watch(watch_dir=watch_dir, state_path=state_path)
    note = watch_dir / "FABLE-WHILE-BUSY.md"
    _write_note(note, "wait until idle", mtime_ns=5_000_000)
    session_file = tmp_path / "session.jsonl"
    session_file.write_text("", encoding="utf-8")
    probes = iter((session_file, None))
    waits: list[Path] = []
    calls = 0

    def activity_probe(codex_home: Path, thread_id: str):
        return next(probes)

    def event_waiter(path: Path) -> None:
        waits.append(path)

    def runner(command, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = wake.run_once(
        watch_dir=watch_dir,
        state_path=state_path,
        lock_path=tmp_path / "watch.lock",
        thread_id="thread-id",
        repo_root=ROOT,
        codex_home=tmp_path / "codex-home",
        codex_cli=tmp_path / "codex",
        runner=runner,
        activity_probe=activity_probe,
        event_waiter=event_waiter,
    )

    assert result.status == "woke"
    assert waits == [session_file]
    assert calls == 1


def test_symlinked_and_hidden_markdown_files_are_not_wake_candidates(
    tmp_path: Path,
) -> None:
    wake = _module()
    watch_dir = tmp_path / "to-codex"
    watch_dir.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (watch_dir / "FABLE-LINK.md").symlink_to(outside)
    (watch_dir / ".hidden.md").write_text("hidden", encoding="utf-8")

    assert wake.snapshot_notes(watch_dir) == {}


def test_units_are_event_driven_and_resume_is_bounded() -> None:
    assert SERVICE.exists()
    assert PATH_UNIT.exists()
    service = SERVICE.read_text(encoding="utf-8")
    path_unit = PATH_UNIT.read_text(encoding="utf-8")

    assert "codex_note_event_wake.py --once" in service
    assert "TimeoutStartSec=30min" in service
    assert "Restart=on-failure" in service
    assert "PathChanged=@REPO_ROOT@/Operator/to-codex" in path_unit
    assert "Unit=openclaw-codex-note-wake.service" in path_unit
    assert "OnUnitActiveSec" not in path_unit
    assert "OnCalendar" not in path_unit


def test_scoped_installer_primes_and_enables_only_note_watch_path(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "systemctl.calls"
    fake_systemctl = fake_bin / "systemctl"
    fake_systemctl.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"${SYSTEMCTL_CALLS}\"\n",
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o755)
    home = tmp_path / "home"
    env = dict(os.environ)
    env.update(
        HOME=str(home),
        PATH=f"{fake_bin}:{env['PATH']}",
        SYSTEMCTL_CALLS=str(calls),
    )

    completed = subprocess.run(
        [
            "bash",
            str(INSTALLER),
            "--apply",
            "--enable",
            "--codex-note-watch-only",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    installed = {
        path.name for path in (home / ".config" / "systemd" / "user").iterdir()
    }
    assert installed == {
        "openclaw-codex-note-wake.service",
        "openclaw-codex-note-wake.path",
    }
    assert calls.read_text(encoding="utf-8").splitlines() == [
        "--user daemon-reload",
        "--user enable --now openclaw-codex-note-wake.path",
    ]
    state = home / ".openclaw" / "codex_note_event_wake_state.json"
    assert state.exists()
    assert "Enabled and started repo-owned path:" in completed.stdout


def test_runbook_has_no_polling_and_exact_rollback() -> None:
    assert RUNBOOK.exists()
    source = RUNBOOK.read_text(encoding="utf-8")
    assert "systemd.path" in source
    assert "no periodic polling" in source.lower()
    assert "systemctl --user disable --now openclaw-codex-note-wake.path" in source
